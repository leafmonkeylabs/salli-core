"""
The planning assumptions behind the FI figures: inflation, the returns of the
three projection scenarios, and the safe withdrawal rate.

Pure domain: no I/O.

**Defaults depend on the base currency.** Projections run in the base currency,
in today's money, so that currency's inflation is what turns a nominal return
into a real one. Every figure in the table says where it comes from. They are
round and deliberately conservative: starting points for a user to adjust,
never forecasts. Inflation is each central bank's own published target, a
policy commitment rather than a statistic. Returns are one round global figure
below the long-run record. The safe withdrawal rate is the 4% rule everywhere,
with its caveat. Sri Lanka keeps exactly the figures Salli always used.

**What applies.** A figure the user set on their profile wins; then their
FIRE strategy's own returns and withdrawal rate, which the strategy was built
around; then their currency's defaults (`resolve`).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Origin = Literal["user", "strategy", "default"]

#: The table row for a currency Salli has no figures of its own for.
OTHER = "other"

#: The conservative and growth scenarios sit this far below and above the base
#: return, in nominal terms: the spread of Salli's original 6/10/14% defaults.
SPREAD = Decimal("0.04")

#: What a user may set, so that "5" typed for 5% is refused, not applied.
BOUNDS: dict[str, tuple[Decimal, Decimal]] = {
    "inflation": (Decimal("-0.05"), Decimal("1")),
    "real_return": (Decimal("-0.05"), Decimal("0.15")),
    "safe_withdrawal_rate": (Decimal("0.01"), Decimal("0.10")),
}


@dataclass(frozen=True)
class Figure:
    """A default, and where it comes from."""

    value: Decimal
    source: str


@dataclass(frozen=True)
class Returns:
    """Nominal yearly returns of the three projection scenarios."""

    conservative: Decimal
    base: Decimal
    growth: Decimal
    source: str


def real_return(nominal: Decimal, inflation: Decimal) -> Decimal:
    """The Fisher relation: a nominal yearly return with inflation taken out
    (the same conversion the engine makes: fi.engine.real_return)."""
    if inflation <= Decimal(-1):
        return nominal
    return (Decimal(1) + nominal) / (Decimal(1) + inflation) - Decimal(1)


def returns_from_real(real: Decimal, inflation: Decimal, source: str) -> Returns:
    """Scenarios around a base `real` return: its nominal equivalent at
    `inflation`, and `SPREAD` either side of it."""
    base = (Decimal(1) + real) * (Decimal(1) + inflation) - Decimal(1)
    return Returns(base - SPREAD, base, base + SPREAD, source)


@dataclass(frozen=True)
class RegionalDefaults:
    #: The base currency these are the defaults for, or OTHER.
    region: str
    #: What it is called: "Sri Lankan rupee".
    name: str
    inflation: Figure
    safe_withdrawal_rate: Figure
    #: The base scenario's yearly return after inflation. The scenarios follow
    #: from it at whatever inflation applies, so it stays the same real return
    #: when a user sets their own inflation.
    real_return: Figure | None = None
    #: Or nominal scenarios of the region's own, which inflation then turns
    #: real, as it does a strategy's (Sri Lanka keeps Salli's original ones).
    nominal_returns: Returns | None = None

    def __post_init__(self) -> None:
        if (self.real_return is None) == (self.nominal_returns is None):
            raise ValueError(f"{self.region}: give a real return or nominal returns, not both")

    def returns(self, inflation: Decimal) -> Returns:
        """The scenarios' nominal returns, at `inflation`."""
        if self.nominal_returns is not None:
            return self.nominal_returns
        assert self.real_return is not None  # __post_init__
        return returns_from_real(self.real_return.value, inflation, self.real_return.source)


# ── The table ────────────────────────────────────────────────────────────────

_SWR = Figure(
    Decimal("0.04"),
    "The 4% rule: Bengen (1994), 'Determining Withdrawal Rates Using Historical Data', "
    "Journal of Financial Planning, and Cooley, Hubbard and Walz (1998), the Trinity "
    "study. It comes from US market history; studies of other countries (Pfau, 2010) "
    "found lower rates were the safe ones there, so treat it as a starting point.",
)

_REAL = Figure(
    Decimal("0.04"),
    "A round, conservative 4% a year after inflation for a diversified portfolio, below "
    "the about 5% world equities returned after inflation since 1900 (Dimson, Marsh and "
    "Staunton, UBS Global Investment Returns Yearbook). Conservative and growth "
    "scenarios sit 4 points below and above it, nominal. Not a forecast.",
)


def _target(region: str, name: str, inflation: str, source: str) -> RegionalDefaults:
    return RegionalDefaults(
        region=region,
        name=name,
        inflation=Figure(Decimal(inflation), source),
        safe_withdrawal_rate=_SWR,
        real_return=_REAL,
    )


REGIONAL_DEFAULTS: dict[str, RegionalDefaults] = {
    # Salli's original defaults, unchanged: 5% inflation, scenarios of 6, 10
    # and 14% nominal, and the 4% rule.
    "LKR": RegionalDefaults(
        region="LKR",
        name="Sri Lankan rupee",
        inflation=Figure(
            Decimal("0.05"),
            "The Central Bank of Sri Lanka's 5% inflation target (flexible inflation "
            "targeting under the Central Bank of Sri Lanka Act No. 16 of 2023), and "
            "Salli's original default. Inflation in Sri Lanka has swung far from it, so "
            "this is a long-run planning figure, not a forecast.",
        ),
        safe_withdrawal_rate=_SWR,
        nominal_returns=Returns(
            Decimal("0.06"),
            Decimal("0.10"),
            Decimal("0.14"),
            "Salli's original Sri Lankan defaults: 6, 10 and 14% a year, nominal. Round "
            "figures, not a forecast.",
        ),
    ),
    "USD": _target(
        "USD",
        "US dollar",
        "0.02",
        "The Federal Reserve's longer-run inflation goal of 2% (FOMC, Statement on "
        "Longer-Run Goals and Monetary Policy Strategy).",
    ),
    "EUR": _target(
        "EUR",
        "euro",
        "0.02",
        "The European Central Bank's 2% inflation target over the medium term (ECB "
        "monetary policy strategy, 2021).",
    ),
    "GBP": _target(
        "GBP",
        "pound sterling",
        "0.02",
        "The Bank of England's 2% inflation target, set in HM Treasury's remit.",
    ),
    "JPY": _target(
        "JPY",
        "Japanese yen",
        "0.02",
        "The Bank of Japan's 2% price stability target (joint statement with the "
        "Government of Japan, January 2013).",
    ),
    "CAD": _target(
        "CAD",
        "Canadian dollar",
        "0.02",
        "The Bank of Canada's 2% inflation target, the midpoint of its 1% to 3% range.",
    ),
    "AUD": _target(
        "AUD",
        "Australian dollar",
        "0.025",
        "The midpoint of the Reserve Bank of Australia's 2% to 3% inflation target.",
    ),
    "NZD": _target(
        "NZD",
        "New Zealand dollar",
        "0.02",
        "The Reserve Bank of New Zealand's inflation target of 1% to 3%, focused on "
        "its 2% midpoint.",
    ),
    "INR": _target(
        "INR",
        "Indian rupee",
        "0.04",
        "The Reserve Bank of India's 4% inflation target, within a 2% to 6% band "
        "(its flexible inflation targeting framework).",
    ),
}

#: For every other currency. Higher inflation makes the same nominal return
#: worth less, so the placeholder errs high.
FALLBACK = _target(
    OTHER,
    "any other currency",
    "0.05",
    "Salli has no figure for this currency: a round, cautious placeholder. Set your own "
    "on your profile.",
)


def regional_defaults(base_currency: str | None) -> RegionalDefaults:
    return REGIONAL_DEFAULTS.get((base_currency or "").upper(), FALLBACK)


# ── What applies ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Overrides:
    """What a user set on their profile; None where they use the default."""

    inflation: Decimal | None = None
    real_return: Decimal | None = None
    safe_withdrawal_rate: Decimal | None = None


def check_override(name: str, value: Decimal | None) -> Decimal | None:
    """`value`, or a ValueError when it is not a plausible yearly fraction."""
    if value is None:
        return None
    low, high = BOUNDS[name]
    if not (low <= value <= high):
        raise ValueError(
            f"{name} must be a yearly fraction from {low} to {high} (0.03 for 3%), got {value}"
        )
    return value


@dataclass(frozen=True)
class StrategyFigures:
    """The returns and withdrawal rate a user's FIRE strategy chose."""

    safe_withdrawal_rate: Decimal
    returns: Returns


@dataclass(frozen=True)
class Applied:
    value: Decimal
    origin: Origin
    source: str


@dataclass(frozen=True)
class FiAssumptions:
    """The assumptions a figure was computed with, and where each came from."""

    #: Whose defaults applied: the base currency, or OTHER.
    region: str
    inflation: Applied
    #: Nominal, for the three scenarios.
    returns: Returns
    #: The base scenario's, after inflation.
    real_return: Applied
    safe_withdrawal_rate: Applied

    @property
    def scenario_real_returns(self) -> dict[str, Decimal]:
        inflation = self.inflation.value
        return {
            "conservative": real_return(self.returns.conservative, inflation),
            "base": real_return(self.returns.base, inflation),
            "growth": real_return(self.returns.growth, inflation),
        }


_YOURS = "Set on your profile."


def resolve(
    base_currency: str | None,
    overrides: Overrides,
    strategy: StrategyFigures | None = None,
) -> FiAssumptions:
    """The assumptions that apply: the user's own, then their strategy's, then
    the defaults for their currency."""
    defaults = regional_defaults(base_currency)

    if overrides.inflation is not None:
        inflation = Applied(overrides.inflation, "user", _YOURS)
    else:
        inflation = Applied(defaults.inflation.value, "default", defaults.inflation.source)

    origin: Origin
    if overrides.real_return is not None:
        returns = returns_from_real(
            overrides.real_return,
            inflation.value,
            f"{_YOURS} Conservative and growth scenarios sit 4 points below and above it, nominal.",
        )
        origin = "user"
    elif strategy is not None:
        returns, origin = strategy.returns, "strategy"
    else:
        returns, origin = defaults.returns(inflation.value), "default"

    if overrides.safe_withdrawal_rate is not None:
        swr = Applied(overrides.safe_withdrawal_rate, "user", _YOURS)
    elif strategy is not None:
        swr = Applied(
            strategy.safe_withdrawal_rate, "strategy", "The rate your FIRE strategy chose."
        )
    else:
        swr = Applied(
            defaults.safe_withdrawal_rate.value, "default", defaults.safe_withdrawal_rate.source
        )

    return FiAssumptions(
        region=defaults.region,
        inflation=inflation,
        returns=returns,
        real_return=Applied(real_return(returns.base, inflation.value), origin, returns.source),
        safe_withdrawal_rate=swr,
    )
