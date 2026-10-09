"""Pack registry — maps (country, year) to the canonical TaxPack instance.

Every pack is validated at import. A malformed pack computes silently wrong tax
rather than failing, and tax is exactly the thing nobody re-checks by hand — so
the cost of a bad pack is a wrong number a user acts on.
"""

from __future__ import annotations

from decimal import Decimal

from salli.domain.tax.models import TaxPack
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26


class InvalidTaxPack(ValueError):
    """A pack whose bands or rates could not produce a correct computation."""


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
