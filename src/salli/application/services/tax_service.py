from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any

from salli.domain.accounting.models import Account, StoredJournalEntry
from salli.domain.secrets import error_label
from salli.domain.tax import engine
from salli.domain.tax.models import LedgerView, TaxComputation, TaxPack
from salli.domain.tax.packs import registry


def _build_ledger_view(
    entries: list[StoredJournalEntry],
    accounts: list[Account],
) -> LedgerView:
    """
    Aggregate posting data into the LedgerView the tax engine expects.

    Two things here are load-bearing.

    **Classification is by `Account.tax_role`, never by name.** The previous
    version matched substrings against `Account.name` and required the credit
    accounts to be typed `liability`, but onboarding seeds them as assets
    ("4110 APIT Receivable", `asset`) — which is the correct accounting for tax
    you may reclaim. The two disagreed, so `apit_withheld` was zero for every
    user who onboarded through the product and their tax payable was overstated
    by the whole amount already withheld from their salary.

    **Amounts are accumulated signed, not by direction.** Each bucket adds
    `base_signed` in its own natural direction, so a reversing entry cancels the
    original arithmetically. Filtering on `Direction` instead — the old
    behaviour — put the reversal on the ignored side while the original still
    counted, so reversed income stayed taxable forever and reversed donations
    stayed deducted. `reverse_entry` is the only sanctioned way to correct a
    posted entry (entries are immutable), so tax has to honour it.

    Buckets are clamped at zero: a net-negative income or credit total means the
    ledger is mid-correction or malformed, and a negative figure would silently
    *increase* someone's refund rather than fail visibly.
    """
    acc_map = {a.id: a for a in accounts}

    total_income = Decimal(0)
    foreign_service_income = Decimal(0)
    apit_withheld = Decimal(0)
    ait_withheld = Decimal(0)
    foreign_tax_paid = Decimal(0)
    qualifying_payments = Decimal(0)

    for entry in entries:
        for posting in entry.postings:
            acc = acc_map.get(posting.account_id)
            if acc is None:
                continue

            # Income and the credits/deductions accrue in opposite directions,
            # so each is normalised to "positive means more of this bucket".
            credit_positive = -posting.base_signed  # CR increases income
            debit_positive = posting.base_signed  # DR increases a credit/deduction

            if acc.type == "income":
                total_income += credit_positive
                if acc.tax_role == "fsi_income":
                    foreign_service_income += credit_positive

            if acc.tax_role == "apit_credit":
                apit_withheld += debit_positive
            elif acc.tax_role == "ait_credit":
                ait_withheld += debit_positive
            elif acc.tax_role == "foreign_tax_credit":
                foreign_tax_paid += debit_positive
            elif acc.tax_role == "qualifying_payment":
                qualifying_payments += debit_positive

    zero = Decimal(0)
    return LedgerView(
        total_income=max(zero, total_income),
        foreign_service_income=max(zero, foreign_service_income),
        apit_withheld=max(zero, apit_withheld),
        ait_withheld=max(zero, ait_withheld),
        foreign_tax_paid=max(zero, foreign_tax_paid),
        qualifying_payments=max(zero, qualifying_payments),
    )


def _stored_field(stored: object, key: str) -> str:
    """Read a field from a stored computation.

    `get_latest` returns the raw JSONB blob rather than re-hydrating it, and
    rows written before a field existed simply lack the key — so this tolerates
    both shapes and reports "—" when the value was never recorded.
    """
    if stored is None:
        return "—"
    if isinstance(stored, dict):
        value = stored.get(key)
        return "—" if value is None else str(value)
    return str(getattr(stored, key, "—"))


def _same_money(a: object, b: object) -> bool:
    """Numeric equality for two money values that may be strings, Decimals, or
    the "—" placeholder for a value that was never recorded."""
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except (InvalidOperation, ValueError):
        return False


def _fmt_money(value: object) -> str:
    """Trim the trailing scale money picks up from `Numeric(20,8)` so a report
    reads "250000" rather than "250000.00000000"."""
    try:
        d = Decimal(str(value)).normalize()
    except (InvalidOperation, ValueError):
        return str(value)
    # normalize() turns 250000 into 2.5E+5; expand it back to plain notation.
    return f"{d:f}"


class TaxService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    async def compute_tax(self, user_id: str, year: str, *, persist: bool = True) -> TaxComputation:
        """Compute this user's tax for `year` from their current ledger.

        `persist=False` computes without recording the result — used to preview
        what a recompute would produce before writing it.
        """
        pack = registry.get_pack("LK", year)
        async with self._uow_factory() as uow:
            entries = await uow.ledger.get_entries(
                user_id,
                from_date=pack.period_start,
                to_date=pack.period_end,
            )
            accounts = await uow.ledger.get_accounts(user_id)
            ledger_view = _build_ledger_view(entries, accounts)
            computation = engine.compute(ledger_view, pack)
            if persist:
                await uow.tax_computations.save(user_id, computation)
        return computation

    async def get_latest_computation(self, user_id: str, year: str) -> TaxComputation | None:
        async with self._uow_factory() as uow:
            return await uow.tax_computations.get_latest(user_id, year)

    async def list_computation_keys(self) -> list[tuple[str, str]]:
        """Every (user_id, year) with a stored computation. Admin-only."""
        async with self._uow_factory() as uow:
            return await uow.tax_computations.list_computation_keys()

    async def recompute_stored(self, *, apply: bool) -> list[dict[str, Any]]:
        """Re-run every stored computation against the current engine.

        `/tax/latest` serves the most recently *saved* result, so a user who
        computed their tax before an engine fix keeps seeing the old figure
        until they happen to press Recompute — and a wrong tax number is
        precisely the thing they would act on. This re-runs each one and, with
        `apply=True`, records the corrected result.

        A row is only written when the figure actually moves, so re-running this
        is cheap and does not pile up identical history entries.

        Returns one report row per stored computation, whether or not it moved,
        so an operator can see the blast radius before applying it.
        """
        report: list[dict[str, Any]] = []
        for user_id, year in await self.list_computation_keys():
            try:
                stored = await self.get_latest_computation(user_id, year)
                fresh = await self.compute_tax(user_id, year, persist=False)
            except Exception as exc:  # noqa: BLE001 — one bad row must not halt the sweep
                report.append({"user_id": user_id, "year": year, "error": error_label(exc)})
                continue

            old_payable = _stored_field(stored, "tax_payable")
            old_credits = _stored_field(stored, "total_credits")

            # Compared numerically, not as strings. Credit totals carry the
            # fx_rate's scale (`Numeric(20,8)`), so the same amount can be
            # written "250000" one day and "250000.00000000" the next — and a
            # string comparison would call that a change and rewrite the row on
            # every sweep.
            changed = not (
                _same_money(old_payable, fresh.tax_payable)
                and _same_money(old_credits, fresh.total_credits)
            )

            if changed and apply:
                await self.compute_tax(user_id, year, persist=True)

            report.append(
                {
                    "user_id": user_id,
                    "year": year,
                    "old_tax_payable": _fmt_money(old_payable),
                    "new_tax_payable": _fmt_money(fresh.tax_payable),
                    "old_credits": _fmt_money(old_credits),
                    "new_credits": _fmt_money(fresh.total_credits),
                    "new_refund_due": _fmt_money(fresh.refund_due),
                    "changed": changed,
                    "applied": bool(changed and apply),
                }
            )
        return report

    def list_packs(self) -> list[TaxPack]:
        return registry.list_packs()
