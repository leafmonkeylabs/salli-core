"""
DataPortabilityService — export everything a user has stored, or permanently
delete it all. Composes over the already-existing per-domain services for
export (no new reads); delete_account deletes via the dedicated
DataPortabilityRepository, which handles the constraint-driven table
ordering (see adapters/db/repositories.py's SQLDataPortabilityRepository),
then the person's uploaded files and their conversations with the AI.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any

from salli.application.services.reconciliation_service import normal_sign
from salli.domain.export import plaintext
from salli.domain.money import from_minor

if TYPE_CHECKING:
    from salli.application.ports import ConversationStore, StoragePort
    from salli.extensions import UserDataExporter

_log = logging.getLogger(__name__)


class DataPortabilityService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        profile_svc: Any,
        ledger_svc: Any,
        tax_svc: Any,
        budget_svc: Any,
        debt_svc: Any,
        portfolio_svc: Any,
        subscription_svc: Any,
        insurance_svc: Any,
        fi_svc: Any,
        advisor_svc: Any,
        documents_svc: Any,
        reminders_svc: Any,
        exporters: Sequence[UserDataExporter] = (),
        chatgpt: Any = None,
        notifications: Any = None,
        storage: StoragePort | None = None,
        conversations: ConversationStore | None = None,
        pseudonym_key: str = "",
    ) -> None:
        self._uow_factory = uow_factory
        self._profile = profile_svc
        self._ledger = ledger_svc
        self._tax = tax_svc
        self._budget = budget_svc
        self._debt = debt_svc
        self._portfolio = portfolio_svc
        self._subscription = subscription_svc
        self._insurance = insurance_svc
        self._fi = fi_svc
        self._advisor = advisor_svc
        self._documents = documents_svc
        self._reminders = reminders_svc
        # Extensions' own per-user data (salli/extensions.py), appended last.
        self._exporters = exporters
        # ChatGPTConnectionService: a connected plan's session is ended with
        # OpenAI before its tokens are deleted.
        self._chatgpt = chatgpt
        # NotificationService: the digest's preferences and delivery log.
        self._notifications = notifications
        # Uploaded files, and the AI's conversations (none without a
        # Postgres checkpointer: then nothing outlives the process).
        self._storage = storage
        self._conversations = conversations
        # Keys the pseudonym an erased account's audit rows keep.
        self._pseudonym_key = pseudonym_key

    async def export_plaintext(self, user_id: str, fmt: str) -> str:
        """The whole ledger as a Beancount file or an hledger journal.

        Every account, inactive ones included — an entry posted to an account
        that has since been closed still has to name it — and every entry,
        with the postings cleared against a statement and each completed
        reconciliation's closing balance."""
        if fmt not in ("beancount", "hledger"):
            raise ValueError(f"Unknown format {fmt!r}: beancount or hledger")
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(user_id)
            base = await uow.user_profiles.base_currency(user_id)
            assertions = await self._assertions(uow, user_id, accounts)
            cleared: set[str] = set()
            for account in accounts:
                rows = await uow.reconciliations.postings(
                    user_id, account.id, "0001-01-01", "9999-12-31"
                )
                cleared |= {r["posting_id"] for r in rows if r["cleared"]}
        render = plaintext.beancount if fmt == "beancount" else plaintext.hledger
        return render(accounts, entries, base, cleared, assertions)

    @staticmethod
    async def _assertions(uow: Any, user_id: str, accounts: list[Any]) -> list[plaintext.Assertion]:
        """Each completed reconciliation's closing balance, debit-positive."""
        by_id = {a.id: a for a in accounts}
        assertions: list[plaintext.Assertion] = []
        for s in await uow.reconciliations.statements(user_id):
            account = by_id.get(s["account_id"])
            if s["reconciliation"] is None or account is None:
                continue
            closing = from_minor(s["closing_balance_minor"], account.currency)
            assertions.append(
                plaintext.Assertion(
                    account.id,
                    str(s["period_end"]),
                    normal_sign(account) * closing,
                    account.currency,
                    s["id"],
                )
            )
        return assertions

    async def export_all(self, user_id: str) -> dict[str, Any]:
        """
        Everything Salli has stored about this user, as one JSON-serializable
        dict. Reuses each domain's existing read methods rather than querying
        tables directly.

        tax_computations are every stored computation, newest first, each
        with the rule set version that computed it and its inputs;
        conversations are read from the LangGraph checkpointer.
        """
        entries = await self._ledger.get_entries(user_id)
        computations = await self._tax.list_computations(user_id)

        data: dict[str, Any] = {
            "user_id": user_id,
            "profile": await self._profile.get_profile(user_id),
            "accounts": [
                {
                    "id": a.id,
                    "code": a.code,
                    "name": a.name,
                    "type": a.type,
                    "currency": a.currency,
                    "parent_id": a.parent_id,
                    "is_active": a.is_active,
                    "tax_role": a.tax_role,
                    "equity_role": a.equity_role,
                }
                # Closed accounts too: entries still refer to them.
                for a in await self._ledger.list_accounts(user_id, include_inactive=True)
            ],
            "journal_entries": [
                {
                    "id": e.id,
                    "entry_date": e.entry_date,
                    "description": e.description,
                    "source": e.source,
                    "external_ref": e.external_ref,
                    "reverses": e.reverses,
                    "reversed_by": e.reversed_by,
                    # Who posted it, and its place in the hash chain.
                    "created_by": e.created_by,
                    "created_via": e.created_via,
                    "seq": e.seq,
                    "hash": e.hash,
                    "postings": [
                        {
                            "account_id": p.account_id,
                            "direction": p.direction.name,
                            "amount": str(p.amount),
                            "currency": p.currency,
                            # What the base-currency amount was booked at, and from where.
                            "fx_rate": str(p.fx_rate),
                            "fx_rate_source": p.fx_rate_source,
                            "tags": dict(p.tags),
                        }
                        for p in e.postings
                    ],
                }
                for e in entries
            ],
            "tax_computations": computations,
            "tax_returns": await self._tax.list_returns(user_id),
            "budgets": await self._budget.list_budgets(user_id),
            "debts": await self._debt.list_debts(user_id, active_only=False),
            "holdings": await self._portfolio.list_holdings(user_id, active_only=False),
            "holding_transactions": await self._portfolio.export_transactions(user_id),
            "holding_prices": await self._portfolio.list_prices(user_id),
            "investment_policies": await self._investment_policies(user_id),
            "recurring_subscriptions": await self._subscription.list_subscriptions(
                user_id, active_only=False
            ),
            "insurance_policies": await self._insurance.list_policies(user_id, active_only=False),
            "insurance_targets": await self._insurance.list_targets(user_id),
            "goals": await self._fi.list_goals(user_id),
            "fi_score_history": await self._fi.get_score_history(user_id),
            "fire_strategies": await self._fire_strategies(user_id),
            "advisor_reports": await self._advisor.export_reports(user_id),
            "reminders_and_alerts": await self._reminders.list_reminders(user_id),
            "documents": await self._documents.list_documents(user_id),
            "statements": await self._statements(user_id),
            "bank_connections": await self._bank_connections(user_id),
            "tax_rule_sets": await self._tax_rule_sets(user_id),
            **await self._decisions(user_id),
            "conversations": (
                await self._conversations.export(user_id) if self._conversations else []
            ),
            "audit_log": await self._audit_log(user_id),
        }
        data.update(
            await self._notifications.export(user_id)
            if self._notifications is not None
            else {"notification_preferences": None, "notification_deliveries": []}
        )
        # Where the books and a reconciled statement disagree.
        data["warnings"] = await self._warnings(user_id)
        for export in self._exporters:
            data.update(await export(user_id))
        return data

    async def _audit_log(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return list(await uow.audit_log.list(user_id, limit=None))

    async def _warnings(self, user_id: str) -> list[str]:
        """Where the books and a reconciled bank statement disagree: the
        plain-text exports' balance assertions fail there."""
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(user_id)
            assertions = await self._assertions(uow, user_id, accounts)
        return plaintext.disagreements(assertions, entries, plaintext.account_names(accounts))

    async def _statements(self, user_id: str) -> list[dict[str, Any]]:
        """Every imported statement with its parsed transactions, in any state
        (the account deletion removes them too)."""
        from salli.application.services.parsing_service import transaction_view

        async with self._uow_factory() as uow:
            statements = await uow.statements.export(user_id)
        return [
            {**st, "transactions": [transaction_view(t) for t in st["transactions"]]}
            for st in statements
        ]

    async def _fire_strategies(self, user_id: str) -> list[dict[str, Any]]:
        """The FIRE strategies an earlier Salli drafted, as stored."""
        async with self._uow_factory() as uow:
            return list(await uow.fire_strategies.export(user_id))

    async def _tax_rule_sets(self, user_id: str) -> list[dict[str, Any]]:
        """Every tax rule set the user (or their agent) wrote, with every
        version's document, status and validation report."""
        async with self._uow_factory() as uow:
            return list(await uow.tax_rule_sets.export(user_id))

    async def _investment_policies(self, user_id: str) -> list[dict[str, Any]]:
        """Every version of the investment policy statement, oldest first."""
        async with self._uow_factory() as uow:
            return list(await uow.investment_policies.list(user_id))

    async def _decisions(self, user_id: str) -> dict[str, Any]:
        """Every principle (archived ones too), and the decision journal
        exactly as recorded: each entry, note and review with its hash."""
        import datetime as dt

        from salli.application.services.principle_service import principle_view
        from salli.domain.decisions import journal

        async with self._uow_factory() as uow:
            principles = await uow.principles.list(user_id, include_archived=True)
            entries = await uow.decisions.list_full(user_id)
        records = [
            {
                "entry": r["content"],
                "hash": r["hash"],
                "notes": [{"note": n["content"], "hash": n["hash"]} for n in r["notes"]],
                "reviews": [{"review": v["content"], "hash": v["hash"]} for v in r["reviews"]],
            }
            for r in entries
        ]
        exported = journal.export(records, dt.datetime.now(dt.UTC))
        # The export as a whole says when it was made; the journal's own
        # stamp would only make two exports of the same data differ.
        del exported["exported_at"]
        return {
            "principles": [principle_view(p) for p in principles],
            "decision_journal": exported,
        }

    async def _bank_connections(self, user_id: str) -> list[dict[str, Any]]:
        """Each bank connection with its accounts, their mappings and the
        bank's last balances. Never the credential: the repository's list
        holds none."""
        async with self._uow_factory() as uow:
            connections = await uow.bank_connections.list(user_id)
        return [
            {
                **c,
                "accounts": [
                    {**a, "balance": None if a.get("balance") is None else str(a["balance"])}
                    for a in c.get("accounts", [])
                ],
            }
            for c in connections
        ]

    async def delete_account(self, user_id: str) -> dict[str, int]:
        """Permanently delete every row belonging to this user, then their
        uploaded files and conversations. Irreversible.

        A connected ChatGPT plan is signed out first, so its renewable session
        ends with OpenAI rather than outliving the account; best effort, since
        the deletion must go ahead regardless.

        The rows go first, in one transaction, so a file or a thread that
        can't be deleted never leaves the database half erased: the counts
        then say `stored_files_failed` or `conversations_failed` (1), for the
        operator to finish by hand."""
        if self._chatgpt is not None:
            try:
                await self._chatgpt.disconnect(user_id)
            except Exception:
                _log.warning("Could not end a ChatGPT session before deleting an account")
        from salli.application.services.login_service import sign_in_key
        from salli.domain.audit_chain import pseudonym

        async with self._uow_factory() as uow:
            login = await uow.logins.get(user_id)
            counts = await uow.data_portability.delete_all(
                user_id,
                pseudonym(self._pseudonym_key, user_id),
                [sign_in_key(login["email"])] if login else [],
            )
        self._profile.forget(user_id)
        if self._storage is not None:
            await self._erase(counts, "stored_files", self._storage.delete_user, user_id)
        if self._conversations is not None:
            await self._erase(counts, "conversations", self._conversations.delete_all, user_id)
        return counts

    @staticmethod
    async def _erase(
        counts: dict[str, int],
        name: str,
        delete: Callable[[str], Awaitable[int]],
        user_id: str,
    ) -> None:
        try:
            counts[name] = await delete(user_id)
        except Exception as exc:  # noqa: BLE001 — the rows are gone already; say what is left
            # The type only: an exception's text may quote the person's data.
            # The id is what the operator needs to finish the erasure.
            _log.warning(
                "erase_incomplete user=%s part=%s error=%s", user_id, name, type(exc).__name__
            )
            counts[f"{name}_failed"] = 1
