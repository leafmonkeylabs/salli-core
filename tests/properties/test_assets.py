"""
Properties of an asset a scenario buys and of a recurring change's real
growth (docs/design/decision-lab-phase-3.md, section 3, "Tests"), over the
baseline's random ledgers (tests/properties/test_baseline.py):

- an asset with no growth and no selling costs, bought for cash, leaves net
  worth unchanged at the end of the month it is bought;
- a higher growth of the asset's value never lowers net worth at any
  month's end (so bisection on it is sound);
- at the growth the break-even finds, the buying option ends level or
  ahead, and a basis point lower it is behind;
- a recurring change's `real_growth` of 0 gives exactly the figures it gave
  without one.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salli.domain.baseline import timelines
from salli.domain.scenarios import comparison, engine, schema
from tests.baseline_ledger import Ledger
from tests.properties.test_baseline import AS_OF, ledgers

_SETTINGS = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
_CENT = Decimal("0.01")

prices = st.decimals(min_value=Decimal("1000"), max_value=Decimal("900000"), places=2)
days_ahead = st.integers(min_value=0, max_value=700)
growths = st.decimals(min_value=Decimal("-0.05"), max_value=Decimal("0.10"), places=4)
selling = st.sampled_from(["0", "0.015", "0.03", "0.08"])


def _day(offset: int) -> str:
    return (AS_OF + dt.timedelta(days=offset)).isoformat()


def _doc(*changes: dict[str, object], years: int = 3, label: str | None = None) -> schema.Scenario:
    return schema.load(
        {
            "schema": "salli.scenario/1",
            "horizon_years": years,
            "changes": list(changes),
            **({"label": label} if label else {}),
        }
    )


def _points(baseline, scenario: schema.Scenario) -> list[timelines.MonthPoint]:
    changes = engine.translate(baseline, scenario).changes
    return list(timelines.monthly(baseline, scenario.horizon_years, changes).points)


@_SETTINGS
@given(ledgers(), prices, days_ahead)
def test_an_asset_bought_for_cash_leaves_net_worth_as_it_was(
    books: Ledger, price: Decimal, offset: int
):
    baseline = books.baseline(AS_OF)
    asset = {
        "type": "asset",
        "price": f"{price}",
        "date": _day(offset),
        "real_growth": "0",
        "label": "x",
    }
    base, mine = _points(baseline, _doc()), _points(baseline, _doc(asset))
    month = _day(offset)[:7]
    for a, b in zip(base, mine, strict=True):
        if a.month == month and a.date != AS_OF.isoformat():
            assert b.net_worth.quantize(_CENT) == a.net_worth.quantize(_CENT)
            assert b.other_assets - a.other_assets == price / b.deflator
        if baseline.inflation is None:
            # Nothing deflates: as it was at every month's end.
            assert b.net_worth.quantize(_CENT) == a.net_worth.quantize(_CENT)


@_SETTINGS
@given(ledgers(), prices, days_ahead, growths, growths, selling)
def test_a_higher_growth_never_lowers_net_worth(
    books: Ledger, price: Decimal, offset: int, g1: Decimal, g2: Decimal, costs: str
):
    baseline = books.baseline(AS_OF)
    low, high = sorted((g1, g2))

    def asset(growth: Decimal) -> dict[str, object]:
        return {
            "type": "asset",
            "price": f"{price}",
            "date": _day(offset),
            "real_growth": f"{growth}",
            "selling_costs": costs,
            "label": "x",
        }

    slower, faster = _points(baseline, _doc(asset(low))), _points(baseline, _doc(asset(high)))
    for a, b in zip(slower, faster, strict=True):
        assert b.net_worth >= a.net_worth
        assert b.other_assets_value >= b.other_assets


@settings(max_examples=8, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(ledgers(), prices, st.integers(min_value=0, max_value=60), selling, st.integers(1, 4))
def test_at_the_growth_found_buying_is_level_and_a_basis_point_lower_behind(
    books: Ledger, price: Decimal, offset: int, costs: str, years: int
):
    baseline = books.baseline(AS_OF)
    own = {b.account_id for b in baseline.balances}
    # The rent the ledger shows (an outflow, not a transfer), stopped on buying.
    key = next(
        (r.key for r in baseline.recurring if r.direction == "out" and r.account_id not in own),
        None,
    )
    stop = [{"type": "stop_recurring", "key": key, "from": _day(offset)}] if key else []
    home = {
        "type": "asset",
        "price": f"{price}",
        "date": _day(offset),
        "selling_costs": costs,
        "label": "Home",
    }
    loan = {
        "type": "loan",
        "principal": f"{(price * Decimal('0.8')).quantize(_CENT)}",
        "annual_rate": "0.05",
        "term_months": 300,
        "start": _day(offset),
        "label": "Mortgage",
    }
    rent = _doc(years=years, label="Rent")
    buy = _doc(home, loan, *stop, years=years, label="Buy")
    found = comparison.asset_growth(baseline, ("Buy", buy), 0, ("Rent", rent))
    target = _points(baseline, rent)[-1].net_worth

    def at(growth: Decimal) -> Decimal:
        changes = list(buy.changes)
        changes[0] = buy.changes[0].model_copy(update={"real_growth": growth})
        return _points(baseline, buy.model_copy(update={"changes": changes}))[-1].net_worth

    low, high = comparison.ASSET_GROWTH_RANGE
    if found.status == "found":
        assert found.value is not None
        assert at(found.value) >= target
        assert at(found.value - comparison.RATE_STEP) < target
    elif found.ahead == "Buy":
        assert at(low) >= target
    else:
        assert at(high) < target


@_SETTINGS
@given(
    ledgers(),
    st.decimals(min_value=Decimal("1"), max_value=Decimal("5000"), places=2),
    days_ahead,
    st.sampled_from(["weekly", "monthly", "quarterly", "yearly"]),
)
def test_a_real_growth_of_zero_gives_the_figures_exactly(
    books: Ledger, amount: Decimal, offset: int, cadence: str
):
    baseline = books.baseline(AS_OF)
    rent = {
        "type": "recurring",
        "amount": f"-{amount}",
        "cadence": cadence,
        "start": _day(offset),
        "label": "Rent",
    }
    without = engine.run(baseline, _doc(rent))
    with_zero = engine.run(baseline, _doc({**rent, "real_growth": "0"}))
    assert with_zero.monthly == without.monthly
    assert with_zero.cash == without.cash
    assert with_zero.fi == without.fi
    assert with_zero.debts == without.debts
    assert with_zero.break_evens == without.break_evens
