"""
DataPortabilityService — export everything a user has stored, or permanently
delete it all. Composes over the already-existing per-domain services for
export (no new reads); delete_account deletes via the dedicated
DataPortabilityRepository, which handles the constraint-driven table
ordering (see adapters/db/repositories.py's SQLDataPortabilityRepository).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from salli.domain.export import plaintext
from salli.domain.tax.packs.registry import list_packs

if TYPE_CHECKING:
    from salli.extensions import UserDataExporter

_log = logging.getLogger(__name__)

#: The year the export's `tax_computation_2025_26` key is named after. A name,
#: not "the current year": the key predates exports of every year.
_LEGACY_EXPORT_YEAR = "2025/26"


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

    async def export_plaintext(self, user_id: str, fmt: str) -> str:
        """The whole ledger as a Beancount file or an hledger journal.

        Every account, inactive ones included — an entry posted to an account
        that has since been closed still has to name it — and every entry."""
        if fmt not in ("beancount", "hledger"):
            raise ValueError(f"Unknown format {fmt!r}: beancount or hledger")
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(user_id)
            base = await uow.user_profiles.base_currency(user_id)
        render = plaintext.beancount if fmt == "beancount" else plaintext.hledger
        return render(accounts, entries, base)

    async def export_all(self, user_id: str) -> dict[str, Any]:
        """
        Everything Salli has stored about this user, as one JSON-serializable
        dict. Reuses each domain's existing read methods rather than querying
        tables directly.

        Known scope limits, documented rather than silently incomplete:
        - tax_computations: the latest computation for each tax year a pack
          covers; earlier recomputations of a year are not included
        - chat message content lives in the LangGraph checkpointer (Postgres,
          managed by AsyncPostgresSaver), not in these domain tables — it is
          not included here
        """
        entries = await self._ledger.get_entries(user_id)
        # Every tax year a pack covers, not only the one this export once knew.
        years = sorted({pack.year for pack in list_packs()})
        computations = {
            year: await self._tax.get_latest_computation(user_id, year) for year in years
        }

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
                    "reversed_by": e.reversed_by,
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
            # Kept for exports read by older tools, holding what its name says:
            # the 2025/26 computation, whichever year is current now.
            # `tax_computations` has every year.
            "tax_computation_2025_26": self._computation_to_dict(
                computations.get(_LEGACY_EXPORT_YEAR)
            ),
            "tax_computations": [
                self._computation_to_dict(c) for c in computations.values() if c is not None
            ],
            "budgets": await self._budget.list_budgets(user_id),
            "debts": await self._debt.list_debts(user_id, active_only=False),
            "holdings": await self._portfolio.list_holdings(user_id, active_only=False),
            "holding_transactions": await self._portfolio.export_transactions(user_id),
            "holding_prices": await self._portfolio.list_prices(user_id),
            "recurring_subscriptions": await self._subscription.list_subscriptions(
                user_id, active_only=False
            ),
            "insurance_policies": await self._insurance.list_policies(user_id, active_only=False),
            "insurance_targets": await self._insurance.list_targets(user_id),
            "goals": await self._fi.list_goals(user_id),
            "fi_score_history": await self._fi.get_score_history(user_id),
            "advisor_reports": await self._advisor.list_reports(user_id),
            "reminders_and_alerts": await self._reminders.list_reminders(user_id),
            "documents": await self._documents.list_documents(user_id),
            "statements": await self._statements(user_id),
            "bank_connections": await self._bank_connections(user_id),
            "tax_rule_sets": await self._tax_rule_sets(user_id),
        }
        for export in self._exporters:
            data.update(await export(user_id))
        return data

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

    async def _tax_rule_sets(self, user_id: str) -> list[dict[str, Any]]:
        """Every tax rule set the user (or their agent) wrote, with every
        version's document, status and validation report."""
        async with self._uow_factory() as uow:
            return await uow.tax_rule_sets.export(user_id)

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

    @staticmethod
    def _computation_to_dict(computation: Any) -> dict[str, Any] | None:
        if computation is None:
            return None
        import dataclasses
        import json

        # TaxComputationRepository.get_latest() deserializes the stored JSON as a
        # plain dict rather than reconstructing the TaxComputation dataclass.
        if dataclasses.is_dataclass(computation) and not isinstance(computation, type):
            computation = dataclasses.asdict(computation)
        return json.loads(json.dumps(computation, default=str))

    async def delete_account(self, user_id: str) -> dict[str, int]:
        """Permanently delete every row belonging to this user. Irreversible.

        A connected ChatGPT plan is signed out first, so its renewable session
        ends with OpenAI rather than outliving the account; best effort, since
        the deletion must go ahead regardless."""
        if self._chatgpt is not None:
            try:
                await self._chatgpt.disconnect(user_id)
            except Exception:
                _log.warning("Could not end a ChatGPT session before deleting an account")
        async with self._uow_factory() as uow:
            counts = await uow.data_portability.delete_all(user_id)
        self._profile.forget(user_id)
        return counts
