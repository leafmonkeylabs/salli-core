"""
Capital-market assumptions (`salli.cma/1`, docs/baseline.md#capital-market-assumptions).

Pure domain: no I/O.

A CMA pack is user data, as tax rules are: per asset class an expected
yearly return after inflation and a volatility, the correlations between
classes, the yield cash earns after inflation, inflation itself, and the
reference mix the figures are for; each figure with its source and date.
A country's pack is a document a person (or their agent) writes and cites;
the code holds only the engine and `PLACEHOLDER`, a neutral pack labelled as
one wherever it is used.

What a pack decides (`resolve` in `assumptions.py`, the monthly timeline,
the Monte Carlo): the real return when the user set none (the mix's
expected return), inflation when the user set none, what cash earns, and
the volatility the Monte Carlo draws returns with, and how fat its tails
are (the optional `degrees_of_freedom` of its Student-t draws; without one,
`TAILS`, a labelled placeholder).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from salli.domain import canonical

FORMAT = "salli.cma/1"

#: The plausible range of each kind of figure, as yearly fractions.
_BOUNDS: dict[str, tuple[Decimal, Decimal]] = {
    "real_return": (Decimal("-0.10"), Decimal("0.20")),
    "volatility": (Decimal(0), Decimal("0.80")),
    "cash_yield": (Decimal("-0.10"), Decimal("0.10")),
    "inflation": (Decimal("-0.05"), Decimal("1")),
    "correlation": (Decimal(-1), Decimal(1)),
    "degrees_of_freedom": (Decimal(3), Decimal(100)),
}

_MAX_CLASSES = 20
_MAX_TEXT = 500


@dataclass(frozen=True)
class Figure:
    """One figure of a pack, and where it comes from."""

    value: Decimal
    source: str
    #: The day the source gave it (YYYY-MM-DD).
    date: str


@dataclass(frozen=True)
class AssetClass:
    key: str
    label: str
    real_return: Figure
    volatility: Figure


@dataclass(frozen=True)
class CmaPack:
    name: str
    version: str
    classes: tuple[AssetClass, ...]
    #: (class a, class b) → correlation, both orders; 1 on the diagonal.
    correlations: Mapping[tuple[str, str], Decimal]
    cash_yield: Figure
    inflation: Figure | None
    #: The reference mix the expected return and volatility are for: class →
    #: weight, the weights summing to 1.
    mix: Mapping[str, Decimal]
    #: Set for the code's neutral pack: it is a placeholder.
    placeholder: bool = False
    #: The Student-t degrees of freedom the Monte Carlo draws with: the
    #: lower, the fatter the tails. None: `TAILS`, a placeholder.
    degrees_of_freedom: Figure | None = None
    #: The stored pack's id and content hash, when it is one.
    pack_id: str | None = None
    content_hash: str | None = None

    def correlation(self, a: str, b: str) -> Decimal:
        return Decimal(1) if a == b else self.correlations.get((a, b), Decimal(0))

    @property
    def expected_return(self) -> Decimal:
        """The mix's expected yearly real return: its weighted mean."""
        by_key = {c.key: c for c in self.classes}
        return sum((w * by_key[k].real_return.value for k, w in self.mix.items()), Decimal(0))

    @property
    def volatility(self) -> Decimal:
        """The mix's yearly volatility, √(wᵀΣw) over the classes' volatilities
        and correlations."""
        by_key = {c.key: c for c in self.classes}
        variance = Decimal(0)
        for a, wa in self.mix.items():
            for b, wb in self.mix.items():
                variance += (
                    wa
                    * wb
                    * by_key[a].volatility.value
                    * by_key[b].volatility.value
                    * self.correlation(a, b)
                )
        return variance.sqrt() if variance > 0 else Decimal(0)

    @property
    def tails(self) -> Decimal:
        """The degrees of freedom the Monte Carlo draws with."""
        return TAILS if self.degrees_of_freedom is None else self.degrees_of_freedom.value

    @property
    def label(self) -> str:
        return f"{self.name} {self.version}"


_PLACEHOLDER_SOURCE = (
    "Placeholder: a neutral round figure, not a forecast and not any market's. "
    "Import and activate your own capital-market assumptions, with sources."
)

#: The degrees of freedom drawn with when a pack gives none: a placeholder,
#: a round figure for tails fatter than a normal's, labelled as one.
TAILS = Decimal(5)

#: The neutral pack used while the user has none active: one class whose
#: return is the real-return placeholder, a round volatility, and cash
#: earning nothing after inflation. Labelled as a placeholder everywhere.
PLACEHOLDER = CmaPack(
    name="Placeholder",
    version="1",
    classes=(
        AssetClass(
            "growth",
            "Growth assets",
            Figure(Decimal("0.04"), _PLACEHOLDER_SOURCE, "2026-01-01"),
            Figure(Decimal("0.12"), _PLACEHOLDER_SOURCE, "2026-01-01"),
        ),
    ),
    correlations={},
    cash_yield=Figure(Decimal(0), _PLACEHOLDER_SOURCE, "2026-01-01"),
    inflation=None,
    mix={"growth": Decimal(1)},
    placeholder=True,
)


# ── Reading a document ───────────────────────────────────────────────────────


def _text(raw: object, what: str, *, required: bool = True) -> str:
    if raw is None and not required:
        return ""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{what} must be non-empty text")
    text = " ".join(raw.split())
    if len(text) > _MAX_TEXT:
        raise ValueError(f"{what} is longer than {_MAX_TEXT} characters")
    return text


def _number(raw: object, what: str, kind: str) -> Decimal:
    if isinstance(raw, float | bool) or raw is None:
        raise ValueError(f"{what} must be a decimal string such as '0.03'")
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise ValueError(f"{what} must be a decimal string such as '0.03'") from None
    if not value.is_finite():
        raise ValueError(f"{what} must be a decimal string such as '0.03'")
    low, high = _BOUNDS[kind]
    if not low <= value <= high:
        unit = "" if kind == "degrees_of_freedom" else " (a yearly fraction)"
        raise ValueError(f"{what} must be from {low} to {high}{unit}, not {value}")
    return value


def _figure(raw: object, what: str, kind: str) -> Figure:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{what} must be an object with value, source and date")
    item = cast("Mapping[str, Any]", raw)
    day = item.get("date")
    try:
        dt.date.fromisoformat(str(day))
    except ValueError:
        raise ValueError(f"{what}.date must be a day, YYYY-MM-DD") from None
    return Figure(
        _number(item.get("value"), f"{what}.value", kind),
        _text(item.get("source"), f"{what}.source"),
        str(day),
    )


def parse(document: object) -> CmaPack:
    """A `salli.cma/1` document as a pack, or a ValueError saying what is
    wrong with it (the first problem found)."""
    if not isinstance(document, Mapping):
        raise ValueError("A CMA pack is a JSON object")
    doc = cast("Mapping[str, Any]", document)
    if doc.get("format") != FORMAT:
        raise ValueError(f'A CMA pack says "format": "{FORMAT}"')
    raw_classes = doc.get("asset_classes")
    if not isinstance(raw_classes, Mapping) or not raw_classes:
        raise ValueError("asset_classes must be an object of at least one class")
    if len(cast("Mapping[str, Any]", raw_classes)) > _MAX_CLASSES:
        raise ValueError(f"A pack has at most {_MAX_CLASSES} asset classes")
    classes: list[AssetClass] = []
    for key, raw in cast("Mapping[str, Any]", raw_classes).items():
        if not isinstance(raw, Mapping):
            raise ValueError(f"asset_classes.{key} must be an object")
        item = cast("Mapping[str, Any]", raw)
        classes.append(
            AssetClass(
                str(key),
                _text(item.get("label", key), f"asset_classes.{key}.label"),
                _figure(item.get("real_return"), f"asset_classes.{key}.real_return", "real_return"),
                _figure(item.get("volatility"), f"asset_classes.{key}.volatility", "volatility"),
            )
        )
    keys = {c.key for c in classes}

    correlations: dict[tuple[str, str], Decimal] = {}
    raw_corr = doc.get("correlations", [])
    if not isinstance(raw_corr, list):
        raise ValueError("correlations must be a list of {a, b, value, source, date}")
    for i, raw in enumerate(cast("list[Any]", raw_corr)):
        if not isinstance(raw, Mapping):
            raise ValueError(f"correlations[{i}] must be an object")
        item = cast("Mapping[str, Any]", raw)
        a, b = item.get("a"), item.get("b")
        if a not in keys or b not in keys or a == b:
            raise ValueError(f"correlations[{i}] must name two different asset classes")
        figure = _figure(item, f"correlations[{i}]", "correlation")
        correlations[(str(a), str(b))] = correlations[(str(b), str(a))] = figure.value

    raw_mix = doc.get("mix")
    if not isinstance(raw_mix, Mapping) or not raw_mix:
        raise ValueError("mix must be an object of asset class → weight, summing to 1")
    mix: dict[str, Decimal] = {}
    for key, raw in cast("Mapping[str, Any]", raw_mix).items():
        if key not in keys:
            raise ValueError(f"mix names {key!r}, which is not one of the asset classes")
        try:
            weight = Decimal(str(raw)) if not isinstance(raw, float | bool) else Decimal(-1)
        except InvalidOperation:
            weight = Decimal(-1)
        if not Decimal(0) <= weight <= Decimal(1):
            raise ValueError(f"mix.{key} must be a weight from 0 to 1 in a decimal string")
        mix[str(key)] = weight
    if sum(mix.values(), Decimal(0)) != 1:
        raise ValueError("The mix's weights must sum to 1")

    inflation = doc.get("inflation")
    tails = doc.get("degrees_of_freedom")
    pack = CmaPack(
        name=_text(doc.get("name"), "name"),
        version=_text(doc.get("version"), "version"),
        classes=tuple(classes),
        correlations=correlations,
        cash_yield=_figure(doc.get("cash_yield"), "cash_yield", "cash_yield"),
        inflation=None if inflation is None else _figure(inflation, "inflation", "inflation"),
        mix=mix,
        degrees_of_freedom=None
        if tails is None
        else _figure(tails, "degrees_of_freedom", "degrees_of_freedom"),
    )
    return pack


def content_hash(document: object) -> str:
    """The pack's content hash: the same figures, the same hash."""
    return canonical.digest(document)


def stored(document: object, pack_id: str, digest: str) -> CmaPack:
    """A stored, valid document as a pack carrying its id and hash."""
    pack = parse(document)
    return CmaPack(
        pack.name,
        pack.version,
        pack.classes,
        pack.correlations,
        pack.cash_yield,
        pack.inflation,
        pack.mix,
        degrees_of_freedom=pack.degrees_of_freedom,
        pack_id=pack_id,
        content_hash=digest,
    )


def summary(pack: CmaPack) -> dict[str, Any]:
    """What every response says about the pack it used."""
    return {
        "id": pack.pack_id,
        "name": pack.name,
        "version": pack.version,
        "placeholder": pack.placeholder,
        "expected_real_return": canonical.decimal_text(pack.expected_return),
        "volatility": canonical.decimal_text(pack.volatility.quantize(Decimal("0.0001"))),
        "cash_yield": canonical.decimal_text(pack.cash_yield.value),
        "inflation": None
        if pack.inflation is None
        else canonical.decimal_text(pack.inflation.value),
        "degrees_of_freedom": canonical.decimal_text(pack.tails),
    }
