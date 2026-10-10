"""
The planning assumptions behind the FI figures, in real terms.

Pure domain: no I/O.

**Real terms by default.** Every projection runs after inflation, in today's
money, so the FI number stays a flat line the projected balances can be
compared with. A real return is broadly the same whatever the currency, so one
neutral figure works anywhere: there is no table by country or currency.

**Placeholders.** Two figures have one: the base scenario's real return and
the safe withdrawal rate, both a round 4%. They are labelled as placeholders
wherever they are used: they are nobody's forecast and no country's figure,
and every FI response says which of the figures it used are placeholders
(`FiAssumptions.placeholders`). Projections never wait for real ones.

**The user's own** (`OwnAssumptions`), set by the user or their agent, each
with a `source` and a `note`, and stored as user data:

- `real_return`: the base scenario's yearly return after inflation;
- `nominal_return`: or its return before inflation, which needs `inflation`
  to become a real one (set one of the two, not both);
- `inflation`: yearly. It has no placeholder. Without it every figure is in
  today's money only; with it, projections show future money too;
- `safe_withdrawal_rate`: what the FI number is built on.

**What applies** (`resolve`): the user's own figure; then their FIRE
strategy's (its real returns and withdrawal rate); then the placeholder.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, cast

Origin = Literal["user", "strategy", "placeholder"]

#: What a user may set, in the order they are shown.
NAMES: tuple[str, ...] = ("real_return", "nominal_return", "inflation", "safe_withdrawal_rate")

#: The plausible range of each, as yearly fractions, so that "5" typed for 5%
#: is refused rather than applied.
BOUNDS: dict[str, tuple[Decimal, Decimal]] = {
    "real_return": (Decimal("-0.05"), Decimal("0.15")),
    "nominal_return": (Decimal("-0.05"), Decimal("1")),
    "inflation": (Decimal("-0.05"), Decimal("1")),
    "safe_withdrawal_rate": (Decimal("0.01"), Decimal("0.10")),
}

#: How long a source or a note may be.
MAX_SOURCE_LENGTH = 500
MAX_NOTE_LENGTH = 1000

#: The conservative and growth scenarios sit this far below and above the
#: base real return, unless the user's FIRE strategy chose all three. Part of
#: the method (a spread to show uncertainty), not an assumption about a market.
SCENARIO_SPREAD = Decimal("0.02")


@dataclass(frozen=True)
class Placeholder:
    value: Decimal
    #: Says it is a placeholder, and why it is this figure.
    source: str


PLACEHOLDERS: dict[str, Placeholder] = {
    "real_return": Placeholder(
        Decimal("0.04"),
        "Placeholder: a round 4% a year after inflation, not a forecast and not any "
        "country's figure. Set your own, with its source.",
    ),
    "safe_withdrawal_rate": Placeholder(
        Decimal("0.04"),
        "Placeholder: a round 4%, the rule of thumb most writing on financial independence "
        "starts from. Not a recommendation: the rate that lasts differs between markets and "
        "periods. Set your own, with its source.",
    ),
}


# ── Scenarios ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Scenarios:
    """A yearly return for each of the three projection scenarios."""

    conservative: Decimal
    base: Decimal
    growth: Decimal

    @classmethod
    def around(cls, base: Decimal, spread: Decimal = SCENARIO_SPREAD) -> Scenarios:
        return cls(base - spread, base, base + spread)

    def as_dict(self) -> dict[str, Decimal]:
        return {"conservative": self.conservative, "base": self.base, "growth": self.growth}


def real_return(nominal: Decimal, inflation: Decimal) -> Decimal:
    """The Fisher relation: a nominal yearly return with inflation taken out."""
    if inflation <= Decimal(-1):
        return nominal
    return (Decimal(1) + nominal) / (Decimal(1) + inflation) - Decimal(1)


def nominal_return(real: Decimal, inflation: Decimal) -> Decimal:
    """The Fisher relation the other way: a real yearly return with inflation put in."""
    return (Decimal(1) + real) * (Decimal(1) + inflation) - Decimal(1)


# ── The user's own ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OwnFigure:
    """One assumption the user (or their agent) set."""

    value: Decimal
    #: Where it comes from: a URL or a citation. Optional, and asked for.
    source: str | None = None
    #: Anything else worth knowing about it.
    note: str | None = None
    #: When it was set, ISO 8601; informative only.
    set_at: str | None = None

    def as_stored(self) -> dict[str, str]:
        stored = {"value": f"{self.value:f}"}
        for key in ("source", "note", "set_at"):
            text = getattr(self, key)
            if text:
                stored[key] = text
        return stored


def _text(value: object, limit: int, what: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"The {what} must be text")
    text = " ".join(value.split())
    if len(text) > limit:
        raise ValueError(f"The {what} is longer than {limit} characters")
    return text or None


def check_value(name: str, value: object) -> Decimal:
    """`value` as a Decimal, or a ValueError when it is not a plausible yearly
    fraction for `name`."""
    if name not in BOUNDS:
        raise ValueError(f"Not an FI assumption: {name!r}. They are: {', '.join(NAMES)}")
    if isinstance(value, (float, bool)):
        raise ValueError(
            f"{name} must be a decimal string such as '0.03', not a float or a boolean"
        )
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a number such as 0.03 for 3%, got {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be a number such as 0.03 for 3%, got {value!r}")
    low, high = BOUNDS[name]
    if not (low <= number <= high):
        raise ValueError(
            f"{name} must be a yearly fraction from {low} to {high} (0.03 for 3%), got {number}"
        )
    return number.normalize() if number != 0 else Decimal(0)


def own_figure(
    name: str,
    value: object,
    source: object = None,
    note: object = None,
    set_at: str | None = None,
) -> OwnFigure:
    """A validated figure the user set: a plausible value, and a source and
    note of reasonable length (whitespace collapsed)."""
    return OwnFigure(
        value=check_value(name, value),
        source=_text(source, MAX_SOURCE_LENGTH, "source"),
        note=_text(note, MAX_NOTE_LENGTH, "note"),
        set_at=set_at,
    )


@dataclass(frozen=True)
class OwnAssumptions:
    """What the user set; None where they have not."""

    real_return: OwnFigure | None = None
    nominal_return: OwnFigure | None = None
    inflation: OwnFigure | None = None
    safe_withdrawal_rate: OwnFigure | None = None

    def get(self, name: str) -> OwnFigure | None:
        return cast("OwnFigure | None", getattr(self, name))

    @classmethod
    def from_stored(cls, raw: object) -> OwnAssumptions:
        """As stored (`as_stored`). Read leniently: an entry that does not
        parse is left out rather than making the user's figures unreadable."""
        if not isinstance(raw, Mapping):
            return cls()
        stored = cast("Mapping[str, Any]", raw)
        figures: dict[str, OwnFigure] = {}
        for name in NAMES:
            entry = stored.get(name)
            if not isinstance(entry, Mapping):
                continue
            item = cast("Mapping[str, Any]", entry)
            try:
                figures[name] = own_figure(
                    name,
                    item.get("value"),
                    item.get("source"),
                    item.get("note"),
                    item.get("set_at") if isinstance(item.get("set_at"), str) else None,
                )
            except ValueError:
                continue
        return cls(**figures)

    def as_stored(self) -> dict[str, dict[str, str]]:
        return {
            name: figure.as_stored() for name in NAMES if (figure := self.get(name)) is not None
        }

    def changed(self, changes: Mapping[str, OwnFigure | None]) -> OwnAssumptions:
        """These figures with `changes` applied (None clears one), checked
        for consistency (`check_consistent`)."""
        unknown = set(changes) - set(NAMES)
        if unknown:
            raise ValueError(
                f"Not FI assumptions: {', '.join(sorted(unknown))}. They are: {', '.join(NAMES)}"
            )
        updated = replace(self, **dict(changes))
        check_consistent(updated)
        return updated


def check_consistent(own: OwnAssumptions) -> None:
    """A ValueError unless the figures can all be used together."""
    if own.real_return is not None and own.nominal_return is not None:
        raise ValueError(
            "Set a real return or a nominal one, not both: clear one of them "
            "(the nominal return becomes a real one with your inflation)"
        )
    if own.nominal_return is not None and own.inflation is None:
        raise ValueError(
            "A nominal return needs your inflation figure to become a real one: set "
            "inflation too, or set a real return instead"
        )


# ── What applies ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StrategyFigures:
    """The real returns and withdrawal rate a user's FIRE strategy chose.
    `real_returns` is None for a strategy stored without them."""

    safe_withdrawal_rate: Decimal
    real_returns: Scenarios | None = None
    version: int | None = None


@dataclass(frozen=True)
class Applied:
    value: Decimal
    origin: Origin
    #: Where it comes from, in words: the user's citation, the strategy, or
    #: the placeholder's label.
    source: str
    note: str | None = None


_NO_SOURCE = "Set by you; no source given."

#: How the figures read in a sentence.
_LABELS = {
    "real_return": "the real return",
    "nominal_return": "the nominal return",
    "inflation": "inflation",
    "safe_withdrawal_rate": "the safe withdrawal rate",
}


@dataclass(frozen=True)
class FiAssumptions:
    """The assumptions a figure was computed with, and where each came from."""

    #: The base scenario's yearly return after inflation.
    real_return: Applied
    safe_withdrawal_rate: Applied
    #: The three scenarios' real returns.
    real_returns: Scenarios
    #: The user's inflation, or None: then figures are in today's money only.
    inflation: Applied | None = None
    #: The user's nominal return, when it is what the real return came from.
    nominal_return: Applied | None = None

    @property
    def placeholders(self) -> tuple[str, ...]:
        """Which of the figures used are placeholders."""
        return tuple(
            name
            for name in ("real_return", "safe_withdrawal_rate")
            if cast(Applied, getattr(self, name)).origin == "placeholder"
        )

    @property
    def status(self) -> Literal["placeholder", "user"]:
        """ "placeholder" while any figure used is one; "user" once every one
        was set by the user, their agent or their FIRE strategy."""
        return "placeholder" if self.placeholders else "user"

    @property
    def nominal_returns(self) -> Scenarios | None:
        """The scenarios' returns before inflation, when the user set inflation."""
        if self.inflation is None:
            return None
        i = self.inflation.value
        r = self.real_returns
        return Scenarios(
            nominal_return(r.conservative, i),
            nominal_return(r.base, i),
            nominal_return(r.growth, i),
        )

    @property
    def message(self) -> str:
        """What a person should know about these assumptions, in a sentence or two."""
        parts: list[str] = []
        if self.placeholders:
            names = " and ".join(_LABELS[n] for n in self.placeholders)
            parts.append(
                f"Using placeholder assumptions for {names}: round figures, not forecasts. "
                "Set your own, with a source, to replace them."
            )
        else:
            parts.append("Using your own assumptions.")
        if self.inflation is None:
            parts.append(
                "Figures are in today's money; set your inflation to see them in future money too."
            )
        return " ".join(parts)


def _yours(figure: OwnFigure) -> Applied:
    return Applied(figure.value, "user", figure.source or _NO_SOURCE, figure.note)


def resolve(own: OwnAssumptions, strategy: StrategyFigures | None = None) -> FiAssumptions:
    """The assumptions that apply: the user's own, then their FIRE strategy's,
    then the placeholders. A nominal return without inflation (which
    `check_consistent` keeps from being stored) is not used."""
    inflation = _yours(own.inflation) if own.inflation is not None else None

    nominal: Applied | None = None
    if own.real_return is not None:
        base = _yours(own.real_return)
        scenarios = Scenarios.around(base.value)
    elif own.nominal_return is not None and own.inflation is not None:
        nominal = _yours(own.nominal_return)
        real = real_return(own.nominal_return.value, own.inflation.value)
        base = Applied(
            real,
            "user",
            f"Your nominal return of {own.nominal_return.value:f} less your inflation of "
            f"{own.inflation.value:f}. The return: {nominal.source} The inflation: "
            f"{own.inflation.source or _NO_SOURCE}",
            own.nominal_return.note,
        )
        scenarios = Scenarios.around(real)
    elif strategy is not None and strategy.real_returns is not None:
        version = f" (version {strategy.version})" if strategy.version else ""
        base = Applied(
            strategy.real_returns.base,
            "strategy",
            f"The real returns your FIRE strategy{version} chose.",
        )
        scenarios = strategy.real_returns
    else:
        placeholder = PLACEHOLDERS["real_return"]
        base = Applied(placeholder.value, "placeholder", placeholder.source)
        scenarios = Scenarios.around(placeholder.value)

    if own.safe_withdrawal_rate is not None:
        swr = _yours(own.safe_withdrawal_rate)
    elif strategy is not None:
        version = f" (version {strategy.version})" if strategy.version else ""
        swr = Applied(
            strategy.safe_withdrawal_rate,
            "strategy",
            f"The rate your FIRE strategy{version} chose.",
        )
    else:
        placeholder = PLACEHOLDERS["safe_withdrawal_rate"]
        swr = Applied(placeholder.value, "placeholder", placeholder.source)

    return FiAssumptions(
        real_return=base,
        safe_withdrawal_rate=swr,
        real_returns=scenarios,
        inflation=inflation,
        nominal_return=nominal,
    )
