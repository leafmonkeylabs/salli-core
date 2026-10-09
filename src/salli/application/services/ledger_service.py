from __future__ import annotations

import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.application.fx import rate_to_base
from salli.domain.accounting import ledger as ledger_ops
from salli.domain.accounting.models import (
    Account,
    AccountType,
    Direction,
    JournalEntry,
    Posting,
    Source,
    StoredJournalEntry,
    Tag,
    TaxRole,
)
from salli.domain.currency import normalize_currency, quantize
from salli.domain.money import from_minor
from salli.domain.subscription import engine as subscription_engine
from salli.domain.subscription.models import Subscription


class LedgerService:
    def __init__(self, uow_factory: Callable[[], Any], fx: Any = None) -> None:
        self._uow_factory = uow_factory
        # Rates for postings in a currency other than the owner's base one
        # that arrive without their own (see application/fx.py).
        self._fx = fx

    async def base_currency(self, user_id: str) -> str:
        """The ISO code this user's ledger is measured in."""
        async with self._uow_factory() as uow:
            return await uow.user_profiles.base_currency(user_id)

    async def add_account(
        self,
        user_id: str,
        code: str,
        name: str,
        type: AccountType,
        currency: str | None = None,
        parent_id: str | None = None,
        tax_role: TaxRole | None = None,
    ) -> str:
        """Open an account, held in `currency` — the user's base currency unless
        another is named (a USD savings account in a rupee ledger)."""
        async with self._uow_factory() as uow:
            held_in = (
                normalize_currency(currency)
                if currency
                else await uow.user_profiles.base_currency(user_id)
            )
            account = Account(
                id=str(uuid.uuid4()),
                user_id=user_id,
                code=code,
                name=name,
                type=type,
                currency=held_in,
                parent_id=parent_id,
                tax_role=tax_role,
            )
            return await uow.ledger.save_account(user_id, account)

    async def list_accounts(self, user_id: str) -> list[Account]:
        async with self._uow_factory() as uow:
            return await uow.ledger.get_accounts(user_id)

    async def get_account(self, user_id: str, account_id: str) -> Account | None:
        async with self._uow_factory() as uow:
            return await uow.ledger.get_account(user_id, account_id)

    async def add_entry(
        self,
        user_id: str,
        entry_date: str,
        description: str,
        source: Source,
        postings_data: list[dict[str, Any]],
        external_ref: str | None = None,
    ) -> str:
        base = await self.base_currency(user_id)
        postings: list[Posting] = []
        for p in postings_data:
            # Strict here, where postings enter Salli: an unknown code is
            # refused rather than stored with a guessed number of decimals.
            currency = normalize_currency(p.get("currency") or base)
            rate, rate_source = await rate_to_base(
                self._fx, currency, base, entry_date, p.get("fx_rate")
            )
            postings.append(
                Posting(
                    **{
                        **p,
                        "currency": currency,
                        "fx_rate": rate,
                        "fx_rate_source": p.get("fx_rate_source") or rate_source,
                    }
                )
            )
        # JournalEntry.__init__ runs must_balance validator — raises ValueError if unbalanced
        entry = JournalEntry(
            entry_date=entry_date,
            description=description,
            source=source,
            external_ref=external_ref,
            postings=postings,
        )
        async with self._uow_factory() as uow:
            return await uow.ledger.save_entry(user_id, entry)

    async def get_entries(
        self,
        user_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[StoredJournalEntry]:
        async with self._uow_factory() as uow:
            return await uow.ledger.get_entries(user_id, from_date, to_date)

    async def get_entry(self, user_id: str, entry_id: str) -> StoredJournalEntry | None:
        async with self._uow_factory() as uow:
            return await uow.ledger.get_entry_by_id(user_id, entry_id)

    async def get_entry_provenance(self, user_id: str, entry_id: str) -> dict[str, Any] | None:
        """Resolve an entry's source + external_ref into human-readable provenance:
        the original bank-statement transaction, or an attached manual receipt."""
        async with self._uow_factory() as uow:
            entry = await uow.ledger.get_entry_by_id(user_id, entry_id)
            if entry is None:
                return None

            provenance: dict[str, Any] = {
                "entry_id": entry.id,
                "entry_date": entry.entry_date,
                "description": entry.description,
                "source": entry.source,
                "external_ref": entry.external_ref,
                "statement": None,
                "receipt": None,
            }

            if entry.source == "statement" and entry.external_ref:
                txns = await uow.statements.get_by_ids(user_id, [entry.external_ref])
                if txns:
                    txn = txns[0]
                    statement_info = None
                    if txn.statement_id:
                        statement_info = await uow.statements.get_statement(
                            user_id, txn.statement_id
                        )
                    raw = txn.raw
                    provenance["statement"] = {
                        "parsed_transaction_id": txn.id,
                        "raw_description": raw.description,
                        # At the statement currency's precision, and saying
                        # which currency that is: a statement need not be in
                        # the base currency.
                        "raw_amount": str(quantize(raw.amount, raw.currency, strict=False)),
                        "currency": raw.currency,
                        "raw_date": raw.date,
                        "bank_ref": raw.bank_ref,
                        "statement": statement_info,
                    }
            elif entry.source == "manual" and entry.external_ref:
                doc = await uow.agent_documents.get(user_id, entry.external_ref)
                if doc:
                    provenance["receipt"] = {
                        "document_id": doc["id"],
                        "title": doc["title"],
                        "mime_type": doc["mime_type"],
                        "storage_key": doc.get("storage_key"),
                    }

            # Subscription association is always derived at query time — never
            # stored on the entry — per the immutable-journal-entry invariant.
            accounts = await uow.ledger.get_accounts(user_id)
            base = await uow.user_profiles.base_currency(user_id)
            subscriptions = await uow.recurring_subscriptions.list(user_id, active_only=True)
            possible_subscriptions: list[dict[str, Any]] = []
            for s in subscriptions:
                sub = Subscription(
                    name=s["name"],
                    amount=from_minor(s["amount_minor"], base),
                    frequency=s["frequency"],
                    next_due_date=s["next_due_date"],
                    account_id=s["account_id"],
                    grace_days=s["grace_days"],
                    amount_tolerance_pct=Decimal(s["amount_tolerance_pct"]),
                )
                matches = subscription_engine.find_matches(sub, [entry], accounts)
                if any(m.entry_id == entry.id for m in matches):
                    possible_subscriptions.append({"subscription_id": s["id"], "name": s["name"]})
            provenance["possible_subscriptions"] = possible_subscriptions

        return provenance

    async def get_trial_balance(
        self,
        user_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Decimal]:
        async with self._uow_factory() as uow:
            entries: list[StoredJournalEntry] = await uow.ledger.get_entries(
                user_id, from_date, to_date
            )
        return ledger_ops.trial_balance(entries)

    async def get_income_statement(
        self,
        user_id: str,
        from_date: str,
        to_date: str,
        income_account_ids: set[str],
        expense_account_ids: set[str],
    ) -> Decimal:
        async with self._uow_factory() as uow:
            entries = await uow.ledger.get_entries(user_id, from_date, to_date)
        return ledger_ops.income_for_period(entries, income_account_ids, expense_account_ids)

    async def get_net_worth(
        self,
        user_id: str,
        asset_account_ids: set[str],
        liability_account_ids: set[str],
    ) -> Decimal:
        async with self._uow_factory() as uow:
            entries = await uow.ledger.get_entries(user_id)
        return ledger_ops.net_worth(entries, asset_account_ids, liability_account_ids)

    async def update_account(
        self,
        user_id: str,
        account_id: str,
        code: str,
        name: str,
        type: str,
        currency: str | None = None,
        tax_role: str | None = None,
    ) -> None:
        """Edit an account. `currency` None leaves it as it is; it can only
        change while the account has no entries, because its postings are
        amounts in that currency."""
        async with self._uow_factory() as uow:
            account = await uow.ledger.get_account(user_id, account_id)
            if account is None:
                raise KeyError(account_id)
            held_in = normalize_currency(currency) if currency else account.currency
            if held_in != account.currency and any(
                p.account_id == account_id
                for entry in await uow.ledger.get_entries(user_id)
                for p in entry.postings
            ):
                raise ValueError(
                    f"This account has entries in {account.currency}, so its currency can't change"
                )
            await uow.ledger.update_account(
                user_id,
                account_id,
                code=code,
                name=name,
                type=type,
                currency=held_in,
                tax_role=tax_role,
            )

    async def ensure_system_tags(self, user_id: str, tags: list[tuple[str, str, str]]) -> None:
        """Seed the closed `need` tag axis. Idempotent."""
        async with self._uow_factory() as uow:
            await uow.ledger.ensure_system_tags(user_id, tags)

    async def list_tags(self, user_id: str, kind: str | None = None) -> list[Tag]:
        async with self._uow_factory() as uow:
            return await uow.ledger.list_tags(user_id, kind)

    async def set_posting_tags(self, user_id: str, posting_id: str, tags: dict[str, str]) -> None:
        """Retag a posting. The money is immutable; how it is classified is not."""
        async with self._uow_factory() as uow:
            await uow.ledger.set_posting_tags(user_id, posting_id, tags)

    async def deactivate_account(self, user_id: str, account_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.ledger.deactivate_account(user_id, account_id)

    async def reactivate_account(self, user_id: str, account_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.ledger.reactivate_account(user_id, account_id)

    async def get_account_overview(
        self,
        user_id: str,
        account_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any] | None:
        """Account detail + full-history running balance, sliced to [from_date, to_date]
        for display — the running balance itself is always computed over the account's
        entire history so figures stay historically accurate even under a date filter.

        Two balances: `current_balance` in the user's base currency (what the
        account is worth in their ledger), and `balance` in the account's own
        currency (what the bank shows) — the same number unless the account is
        held in another currency. `balance` is None when it cannot be known
        (see `ledger.native_signed`)."""
        async with self._uow_factory() as uow:
            account = await uow.ledger.get_account(user_id, account_id)
            if account is None:
                return None
            all_entries = await uow.ledger.get_entries(user_id)
            base = await uow.user_profiles.base_currency(user_id)

        history = ledger_ops.account_history(all_entries, account_id, account.currency, base)
        current_balance = history[-1][1] if history else Decimal(0)
        native_balance = history[-1][2] if history else Decimal(0)

        def native(amount: Decimal | None) -> str | None:
            return None if amount is None else str(quantize(amount, account.currency))

        transactions = [
            {
                "entry_id": entry.id,
                "entry_date": entry.entry_date,
                "description": entry.description,
                "source": entry.source,
                "external_ref": entry.external_ref,
                "running_balance": str(quantize(base_balance, base)),
                "running_balance_native": native(native_running),
            }
            for entry, base_balance, native_running in history
            if (from_date is None or entry.entry_date >= from_date)
            and (to_date is None or entry.entry_date <= to_date)
        ]

        return {
            "account": {
                "id": account.id,
                "code": account.code,
                "name": account.name,
                "type": account.type,
                "currency": account.currency,
                "parent_id": account.parent_id,
                "is_active": account.is_active,
            },
            "base_currency": base,
            "current_balance": str(quantize(current_balance, base)),
            "balance": native(native_balance),
            "transactions": transactions,
        }

    async def reverse_entry(self, user_id: str, entry_id: str) -> str:
        """Create a reversing journal entry and mark the original as reversed."""
        async with self._uow_factory() as uow:
            original = await uow.ledger.get_entry_by_id(user_id, entry_id)
            if original is None:
                raise ValueError(f"Entry {entry_id} not found")
            if original.reversed_by:
                raise ValueError("Entry is already reversed")

            reversed_postings = [
                Posting(
                    account_id=p.account_id,
                    direction=Direction(-p.direction.value),
                    amount=p.amount,
                    currency=p.currency,
                    fx_rate=p.fx_rate,
                    fx_rate_source=p.fx_rate_source,
                    # The reversal carries the original's tags. Without them a
                    # spend-by-category report would count the original and miss
                    # its reversal, overstating that category forever — the same
                    # failure the tax view had before it netted reversals out.
                    tags=dict(p.tags),
                )
                for p in original.postings
            ]
            reversing = JournalEntry(
                entry_date=original.entry_date,
                description=f"REVERSAL: {original.description}",
                source="manual",
                postings=reversed_postings,
            )
            reversing_id = await uow.ledger.save_entry(user_id, reversing)
            await uow.ledger.set_reversed_by(entry_id, reversing_id)
        return reversing_id
