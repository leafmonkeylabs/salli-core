"""
DataPortabilityService — export everything a user has stored, or permanently
delete it all. Composes over the already-existing per-domain services for
export (no new reads); delete_account deletes via the dedicated
DataPortabilityRepository, which handles the constraint-driven table
ordering (see adapters/db/repositories.py's SQLDataPortabilityRepository).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from salli.domain.export import plaintext

if TYPE_CHECKING:
    from salli.extensions import UserDataExporter


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
        - accounts: active accounts only (list_accounts has no include-inactive
          option today)
        - tax_computations: only the current pack year (2025/26) — there is no
          "list all years" method, only get_latest_computation(year)
        - chat message content lives in the LangGraph checkpointer (Postgres,
          managed by AsyncPostgresSaver), not in these domain tables — it is
          not included here
        """
        entries = await self._ledger.get_entries(user_id)
        tax_computation = await self._tax.get_latest_computation(user_id, "2025/26")

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
                }
                for a in await self._ledger.list_accounts(user_id)
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
                        }
                        for p in e.postings
                    ],
                }
                for e in entries
            ],
            "tax_computation_2025_26": self._computation_to_dict(tax_computation),
            "budgets": await self._budget.list_budgets(user_id),
            "debts": await self._debt.list_debts(user_id, active_only=False),
            "holdings": await self._portfolio.list_holdings(user_id, active_only=False),
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
        }
        for export in self._exporters:
            data.update(await export(user_id))
        return data

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
        """Permanently delete every row belonging to this user. Irreversible."""
        async with self._uow_factory() as uow:
            counts = await uow.data_portability.delete_all(user_id)
        self._profile.forget(user_id)
        return counts
