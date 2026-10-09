from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from salli.domain.accounting.models import Account, StoredJournalEntry
from salli.domain.jurisdiction import country_phrase
from salli.domain.secrets import error_label
from salli.domain.tax import engine
from salli.domain.tax.models import (
    CREDITED_KINDS,
    FSI_INCOME_ROLE,
    QUALIFYING_PAYMENT_ROLE,
    CurrentTaxYear,
    LedgerView,
    TaxComputation,
    TaxPack,
)
from salli.domain.tax.packs import registry


def _build_ledger_view(
    entries: list[StoredJournalEntry],
    accounts: list[Account],
    pack: TaxPack | None = None,
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

    **Only the roles `pack` declares count.** A role another country's pack
    declares means nothing to this one. Without a pack, every role the engine
    knows counts.
    """
    acc_map = {a.id: a for a in accounts}
    declared = pack.tax_roles if pack is not None else None

    def role(acc: Account) -> str | None:
        if acc.tax_role is None or (declared is not None and acc.tax_role not in declared):
            return None
        return acc.tax_role

    total_income = Decimal(0)
    foreign_service_income = Decimal(0)
    withheld = dict.fromkeys(CREDITED_KINDS.values(), Decimal(0))
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
            tax_role = role(acc)

            if acc.type == "income":
                total_income += credit_positive
                if tax_role == FSI_INCOME_ROLE:
                    foreign_service_income += credit_positive

            if tax_role in CREDITED_KINDS:
                withheld[CREDITED_KINDS[tax_role]] += debit_positive
            elif tax_role == QUALIFYING_PAYMENT_ROLE:
                qualifying_payments += debit_positive

    zero = Decimal(0)
    return LedgerView(
        total_income=max(zero, total_income),
        foreign_service_income=max(zero, foreign_service_income),
        apit_withheld=max(zero, withheld["apit_withheld"]),
        ait_withheld=max(zero, withheld["ait_withheld"]),
        foreign_tax_paid=max(zero, withheld["foreign_tax_paid"]),
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


class TaxPackCurrencyError(ValueError):
    """The user's ledger is not in the currency their tax pack computes in."""


class NoTaxPackError(ValueError):
    """Salli has no tax pack that can compute this user's tax."""


@dataclass(frozen=True)
class TaxJurisdiction:
    """Whose tax packs compute a user's tax, and why."""

    #: The country, or None when Salli cannot tell.
    country: str | None
    #: "tax_residency" when the user said where they are taxed. "base_currency"
    #: when they have not, and the packs of exactly one country compute in
    #: their base currency: so a rupee ledger keeps being computed with Sri
    #: Lanka's packs, as it always was, until its owner says otherwise.
    source: Literal["tax_residency", "base_currency"] | None
    tax_residency: str | None
    base_currency: str | None


def jurisdiction_of(profile: dict[str, Any] | None) -> TaxJurisdiction:
    profile = profile or {}
    residency = profile.get("tax_residency") or None
    base = profile.get("base_currency") or None
    if residency:
        return TaxJurisdiction(residency, "tax_residency", residency, base)
    inferred = registry.country_for_currency(base) if base else None
    if inferred:
        return TaxJurisdiction(inferred, "base_currency", None, base)
    return TaxJurisdiction(None, None, None, base)


def _no_pack(where: TaxJurisdiction) -> NoTaxPackError:
    if where.country is None:
        countries = sorted({country_phrase(p.country) for p in registry.list_packs()})
        return NoTaxPackError(
            "Salli doesn't know where you are taxed. Set your tax residency on your "
            f"profile; it has tax packs for {', '.join(countries)}."
        )
    if not registry.packs_for(where.country):
        return NoTaxPackError(f"Salli has no tax pack for {country_phrase(where.country)} yet.")
    return NoTaxPackError(
        f"Salli's tax packs for {country_phrase(where.country)} are for years that have not begun."
    )


class TaxService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    # ── Whose tax, which year ────────────────────────────────────────────────

    async def jurisdiction(self, user_id: str) -> TaxJurisdiction:
        async with self._uow_factory() as uow:
            return jurisdiction_of(await uow.user_profiles.get(user_id))

    async def current_tax_year(
        self, user_id: str, today: datetime.date | None = None
    ) -> tuple[TaxJurisdiction, CurrentTaxYear | None]:
        """The tax year the user is in today, in their country (registry
        .current_tax_year), with how their country was decided."""
        where = await self.jurisdiction(user_id)
        return where, registry.current_tax_year(where.country, today or datetime.date.today())

    async def pack(self, user_id: str, year: str | None = None) -> TaxPack:
        """The pack that computes `year` for this user: their country's pack for
        it (KeyError when there is none), or, with no year, the latest year
        their country's packs have begun. NoTaxPackError with no country."""
        where = await self.jurisdiction(user_id)
        if where.country is None:
            raise _no_pack(where)
        if year:
            return registry.get_pack(where.country, year)
        latest = registry.latest_pack(where.country, datetime.date.today())
        if latest is None:
            raise _no_pack(where)
        return latest

    async def default_year(self, user_id: str) -> str:
        """The year a computation uses when none is named: the latest one Salli
        can compute for the user."""
        return (await self.pack(user_id)).year

    # ── Computations ─────────────────────────────────────────────────────────

    async def compute_tax(
        self,
        user_id: str,
        year: str | None = None,
        *,
        persist: bool = True,
        country: str | None = None,
    ) -> TaxComputation:
        """Compute this user's tax for `year` from their current ledger, with
        their country's pack; with no year, the latest year Salli can compute.

        `country` overrides theirs: a stored computation is recomputed with the
        country it was made for. `persist=False` computes without recording the
        result — used to preview what a recompute would produce before writing it.
        """
        if country and year:
            pack = registry.get_pack(country, year)
        else:
            pack = await self.pack(user_id, year)
        async with self._uow_factory() as uow:
            base = await uow.user_profiles.base_currency(user_id)
            if base != pack.currency:
                # A pack's bands, reliefs and caps are amounts in its own
                # currency. Applied to a ledger kept in another, every one of
                # them would be wrong by the exchange rate.
                raise TaxPackCurrencyError(
                    f"The {pack.country} {pack.year} tax pack computes in {pack.currency}, "
                    f"but this ledger is kept in {base}. Salli has no tax pack for it yet."
                )
            entries = await uow.ledger.get_entries(
                user_id,
                from_date=pack.period_start,
                to_date=pack.period_end,
            )
            accounts = await uow.ledger.get_accounts(user_id)
            ledger_view = _build_ledger_view(entries, accounts, pack)
            computation = engine.compute(ledger_view, pack)
            if persist:
                await uow.tax_computations.save(user_id, computation)
        return computation

    async def get_latest_computation(
        self, user_id: str, year: str | None = None
    ) -> TaxComputation | None:
        """The last computation stored for `year`; with no year, for the latest
        year Salli can compute for the user (None when it can compute none)."""
        if year is None:
            try:
                year = await self.default_year(user_id)
            except NoTaxPackError:
                return None
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
                # With the country it was made for, whatever the user's is now.
                # The oldest rows record none, and were all Sri Lankan.
                made_for = _stored_field(stored, "pack_country")
                country = made_for if made_for != "—" else "LK"
                fresh = await self.compute_tax(user_id, year, persist=False, country=country)
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
                await self.compute_tax(user_id, year, persist=True, country=country)

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
