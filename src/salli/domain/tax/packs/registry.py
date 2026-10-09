"""Pack registry — maps (country, year) to the canonical TaxPack instance.

Every pack is validated at import. A malformed pack computes silently wrong tax
rather than failing, and tax is exactly the thing nobody re-checks by hand — so
the cost of a bad pack is a wrong number a user acts on.
"""

from __future__ import annotations

import re
from decimal import Decimal

from salli.domain.tax.models import CREDITED_KINDS, TAX_ROLE_PATTERN, StarterAccount, TaxPack
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26

_ACCOUNT_TYPES = frozenset({"asset", "liability", "equity", "income", "expense"})


class InvalidTaxPack(ValueError):
    """A pack whose bands or rates could not produce a correct computation."""


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
