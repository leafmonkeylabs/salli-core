"""Pack registry — maps (country, year) to the canonical TaxPack instance.

Every pack is validated at import. A malformed pack computes silently wrong tax
rather than failing, and tax is exactly the thing nobody re-checks by hand — so
the cost of a bad pack is a wrong number a user acts on.
"""

from __future__ import annotations

import datetime
import re
from decimal import Decimal

from salli.domain.tax.models import (
    CREDITED_KINDS,
    TAX_ROLE_PATTERN,
    CurrentTaxYear,
    StarterAccount,
    TaxPack,
    TaxYear,
    year_label,
)
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26

_ACCOUNT_TYPES = frozenset({"asset", "liability", "equity", "income", "expense"})


class InvalidTaxPack(ValueError):
    """A pack whose bands or rates could not produce a correct computation."""


def _year_from(year_start: str, start: datetime.date) -> TaxYear:
    """The tax year beginning on `start`, which falls on `year_start`."""
    first = start.replace(month=int(year_start[:2]), day=int(year_start[3:]))
    after = first.replace(year=first.year + 1)
    return TaxYear("", year_label(year_start, first), first, after - datetime.timedelta(days=1))


def _month_day(value: str, reference_year: int) -> datetime.date | None:
    """ "04-01" as a date in `reference_year`, or None if it is not one."""
    if not re.fullmatch(r"\d{2}-\d{2}", value):
        return None
    try:
        return datetime.date(reference_year, int(value[:2]), int(value[3:]))
    except ValueError:
        return None


def _validate_year(pack: TaxPack, where: str) -> None:
    """The year's shape is a real day of every year, and the pack's period is
    exactly one such year, named the way every year of it is named."""
    if _month_day(pack.year_start, 2001) is None:  # 2001: no 29 February to start on
        raise InvalidTaxPack(f"{where}: year_start {pack.year_start!r} is not an MM-DD date")
    try:
        start = datetime.date.fromisoformat(pack.period_start)
        end = datetime.date.fromisoformat(pack.period_end)
    except ValueError:
        raise InvalidTaxPack(f"{where}: the period is not two YYYY-MM-DD dates") from None
    year = _year_from(pack.year_start, start)
    if (start, end) != (year.start, year.end):
        raise InvalidTaxPack(
            f"{where}: the period {pack.period_start} to {pack.period_end} is not one tax "
            f"year starting {pack.year_start}"
        )
    if end.strftime("%m-%d") != pack.year_end:
        raise InvalidTaxPack(f"{where}: year_end {pack.year_end!r} is not the period's last day")
    if pack.year != year_label(pack.year_start, start):
        raise InvalidTaxPack(
            f"{where}: a year starting {pack.period_start} is called "
            f"{year_label(pack.year_start, start)!r}"
        )


def _validate_roles(pack: TaxPack, where: str) -> None:
    """Withholding kinds the engine credits, and starter accounts that carry
    only roles the pack declares."""
    codes = [kind.code for kind in pack.withholding_kinds]
    if len(set(codes)) != len(codes):
        raise InvalidTaxPack(f"{where}: a withholding kind is declared twice")
    for kind in pack.withholding_kinds:
        if not re.fullmatch(TAX_ROLE_PATTERN, kind.code):
            raise InvalidTaxPack(f"{where}: {kind.code!r} is not a tax role code")
        # A kind the engine has nowhere to put would be dropped from the bill
        # without a word: refuse it until the engine credits it.
        if kind.code not in CREDITED_KINDS:
            raise InvalidTaxPack(f"{where}: the engine does not credit {kind.code!r}")
        if not kind.label.strip() or not kind.description.strip():
            raise InvalidTaxPack(f"{where}: {kind.code} needs a label and a description")

    account_codes = [account.code for account in pack.starter_accounts]
    if len(set(account_codes)) != len(account_codes):
        raise InvalidTaxPack(f"{where}: a starter account code is used twice")
    for account in pack.starter_accounts:
        if account.tax_role not in pack.tax_roles:
            raise InvalidTaxPack(
                f"{where}: starter account {account.code} carries {account.tax_role!r}, "
                "which the pack does not declare"
            )
        if account.type not in _ACCOUNT_TYPES or not account.name.strip():
            raise InvalidTaxPack(f"{where}: starter account {account.code} is malformed")


def validate_pack(pack: TaxPack) -> None:
    """Reject a pack the engine would misapply.

    The engine walks bands in order, treating each `upto` as the cumulative
    ceiling and the final `upto=None` as the open-ended top. Nothing else checks
    that shape holds, and every violation below produces a plausible-looking but
    wrong figure rather than an error.
    """
    where = f"{pack.country}/{pack.year} v{pack.version}"

    if not pack.bands:
        raise InvalidTaxPack(f"{where}: has no bands")

    # Exactly one open-ended band, and it must be last — otherwise the engine
    # stops there and every band beyond it is silently never applied.
    open_ended = [i for i, b in enumerate(pack.bands) if b.upto is None]
    if len(open_ended) != 1 or open_ended[0] != len(pack.bands) - 1:
        raise InvalidTaxPack(
            f"{where}: exactly one band must be open-ended (upto=None) and it must be last"
        )

    # Thresholds are cumulative ceilings, so they must strictly ascend. A
    # repeated or out-of-order threshold yields a zero-width or negative band.
    previous = Decimal(0)
    for band in pack.bands[:-1]:
        assert band.upto is not None  # guarded above
        if band.upto <= previous:
            raise InvalidTaxPack(
                f"{where}: band thresholds must strictly ascend (saw {band.upto} after {previous})"
            )
        previous = band.upto

    for band in pack.bands:
        if not (Decimal(0) <= band.rate <= Decimal(1)):
            raise InvalidTaxPack(
                f"{where}: rate {band.rate} is not a fraction between 0 and 1 "
                "(0.06 for 6%, never 6)"
            )

    if pack.personal_relief < 0:
        raise InvalidTaxPack(f"{where}: personal relief cannot be negative")

    fsi = pack.foreign_service_income
    if fsi is not None and not (Decimal(0) <= fsi.max_rate <= Decimal(1)):
        raise InvalidTaxPack(f"{where}: FSI rate {fsi.max_rate} is not a fraction between 0 and 1")

    if pack.rounding not in ("nearest_rupee", "truncate_rupee"):
        raise InvalidTaxPack(f"{where}: unknown rounding mode {pack.rounding!r}")

    if pack.qualifying_payment_cap < 0 or not (
        Decimal(0) <= pack.qualifying_payment_fraction <= Decimal(1)
    ):
        raise InvalidTaxPack(f"{where}: qualifying-payment relief is out of range")

    _validate_year(pack, where)
    _validate_roles(pack, where)


_REGISTRY: dict[tuple[str, str], TaxPack] = {
    ("LK", "2025/26"): LK_2025_26,
}

# Fail at import rather than at the first user's computation.
for _pack in _REGISTRY.values():
    validate_pack(_pack)


def get_pack(country: str, year: str) -> TaxPack:
    key = (country.upper(), year)
    pack = _REGISTRY.get(key)
    if pack is None:
        available = ", ".join(f"{c}/{y}" for c, y in _REGISTRY)
        raise KeyError(f"No tax pack for {country}/{year}. Available: {available}")
    return pack


def list_packs() -> list[TaxPack]:
    return list(_REGISTRY.values())


def packs_for(country: str | None) -> list[TaxPack]:
    """The packs for `country`, oldest tax year first; none for None."""
    if not country:
        return []
    found = [p for p in _REGISTRY.values() if p.country == country.upper()]
    return sorted(found, key=lambda p: p.period_start)


def country_for_currency(currency: str) -> str | None:
    """The one country whose packs compute in `currency`, or None when there is
    none, or more than one to choose from."""
    countries = {p.country for p in _REGISTRY.values() if p.currency == currency.upper()}
    return countries.pop() if len(countries) == 1 else None


# ── Tax years ────────────────────────────────────────────────────────────────


def tax_year(country: str, on: datetime.date) -> TaxYear | None:
    """The tax year of `country` that `on` falls in, shaped as its packs declare
    (the newest pack's, should the country ever change it). None when Salli has
    no pack for the country, so does not know its tax year."""
    packs = packs_for(country)
    if not packs:
        return None
    year_start = packs[-1].year_start
    first = on.replace(month=int(year_start[:2]), day=int(year_start[3:]))
    if on < first:
        first = first.replace(year=first.year - 1)
    year = _year_from(year_start, first)
    return TaxYear(country.upper(), year.label, year.start, year.end)


def pack_for(country: str, on: datetime.date) -> TaxPack | None:
    """The pack whose tax year `on` falls in, or None when Salli has none."""
    day = on.isoformat()
    return next(
        (p for p in packs_for(country) if p.period_start <= day <= p.period_end),
        None,
    )


def latest_pack(country: str, on: datetime.date) -> TaxPack | None:
    """The newest pack whose tax year had begun by `on`: the latest year Salli
    can compute. None when it has no pack for the country, or only future ones."""
    day = on.isoformat()
    begun = [p for p in packs_for(country) if p.period_start <= day]
    return begun[-1] if begun else None


def current_tax_year(country: str | None, on: datetime.date) -> CurrentTaxYear | None:
    """Where someone taxed in `country` stands on `on`: the tax year they are in,
    its pack if there is one, and the latest year Salli can compute. None with
    no country, or a country Salli has no pack for."""
    if not country:
        return None
    year = tax_year(country, on)
    if year is None:
        return None
    return CurrentTaxYear(year=year, pack=pack_for(country, on), latest=latest_pack(country, on))


# ── Tax roles ────────────────────────────────────────────────────────────────


def _roles_of(packs: list[TaxPack]) -> tuple[str, ...]:
    """The roles `packs` declare, each once, in the order they declare them."""
    return tuple(dict.fromkeys(role for pack in packs for role in pack.tax_roles))


def tax_roles(country: str | None) -> tuple[str, ...]:
    """The tax roles the packs of `country` declare, over every year Salli has.
    None (no residency) and a country without packs declare none."""
    return _roles_of(packs_for(country))


def all_tax_roles() -> tuple[str, ...]:
    """Every tax role any pack declares."""
    return _roles_of(list(_REGISTRY.values()))


def allowed_tax_roles(country: str | None) -> tuple[str, ...]:
    """What an account's tax role may be set to, for someone taxed in `country`.

    The packs of their country decide. A user who has not said where they are
    taxed may use any role a pack declares: they are not refused the roles they
    could always use, and computing their tax still needs a country, whose
    pack credits only what it declares.
    """
    return tax_roles(country) if country else all_tax_roles()


def starter_accounts(country: str | None) -> tuple[StarterAccount, ...]:
    """What a resident of `country` adds to the starter chart of accounts, from
    the country's newest pack. Nothing without a residency, or a pack."""
    packs = packs_for(country)
    return packs[-1].starter_accounts if packs else ()
