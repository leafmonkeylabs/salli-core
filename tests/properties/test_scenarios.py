"""
Properties of scenarios (domain/scenarios), over random ledgers (the
baseline's own, tests/properties/test_baseline.py):

- a scenario with no changes is the baseline, exactly: every delta is zero,
  and its FI is the FI service's;
- adding a cost never improves a cash figure, and adding income never
  worsens one;
- an extra payment on a debt never adds interest;
- a comparison doesn't depend on the order of its options;
- a result is deterministic, and its hash doesn't depend on key order or on
  how an amount was written.
"""

from __future__ import annotations

import json
import random
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salli.domain.baseline import fi
from salli.domain.scenarios import comparison, engine, schema, views
from tests.baseline_ledger import Ledger
from tests.properties.test_baseline import AS_OF, ledgers

_SETTINGS = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])

amounts = st.decimals(min_value=Decimal("1"), max_value=Decimal("20000"), places=2)
days_ahead = st.integers(min_value=0, max_value=400)
cadences = st.sampled_from(["weekly", "monthly", "quarterly", "yearly"])


def _day(offset: int) -> str:
    from datetime import timedelta

    return (AS_OF + timedelta(days=offset)).isoformat()


def _doc(changes: list[dict], **more: object) -> schema.Scenario:
    return schema.load({"schema": "salli.scenario/1", "changes": changes, **more})


@st.composite
def money_changes(draw: st.DrawFn, sign: int) -> dict:
    """A change that only takes money out (sign -1) or only brings it in."""
    amount = draw(amounts) * sign
    kind = draw(st.sampled_from(["one_off", "recurring", "income"]))
    account = draw(st.sampled_from([None, "bank", "savings"]))
    if kind == "one_off":
        return {
            "type": "one_off",
            "date": _day(draw(days_ahead)),
            "amount": f"{amount}",
            "account": account,
            "label": "Once",
        }
    if kind == "recurring":
        return {
            "type": "recurring",
            "amount": f"{amount}",
            "cadence": draw(cadences),
            "start": _day(draw(days_ahead)),
            "account": account,
            "label": "Again",
        }
    return {
        "type": "income_change",
        "monthly_net": f"{amount}",
        "from": _day(draw(days_ahead)),
        "label": "Income",
    }


def _cash_deltas(result: engine.ScenarioResult) -> list[Decimal]:
    out = [
        result.cash.lowest.delta,
        result.cash.at_end.delta,
        result.cash.safe_to_spend.delta,
        *(a.lowest.delta for a in result.cash.accounts),
        *(p.cash.delta for p in result.monthly),
    ]
    return [d for d in out if d is not None]


@_SETTINGS
@given(ledgers())
def test_a_scenario_with_no_changes_is_the_baseline_exactly(books: Ledger):
    baseline = books.baseline(AS_OF)
    result = engine.run(baseline, _doc([]))

    figures = [
        result.cash.lowest,
        result.cash.at_end,
        result.cash.safe_to_spend,
        result.debts.total_interest,
        result.fi.fi_number,
        *(a.lowest for a in result.cash.accounts),
        *(f for p in result.monthly for f in (p.net_worth, p.cash, p.investments, p.debts)),
        *(d.total_interest for d in result.debts.items),
    ]
    assert all(f.baseline == f.scenario for f in figures)
    assert all(f.delta in (0, None) for f in figures)
    assert result.cash.lowest_date.delta == 0
    months = [result.fi.fi_month, result.debts.debt_free, *(d.paid_off for d in result.debts.items)]
    assert all(m.baseline == m.scenario for m in months)
    assert result.fi.months_gained in (0, None)
    # And its FI is the baseline's own, as the FI service computes it.
    own = fi.outlook(baseline, fi.full_timeline(baseline))
    assert (result.fi.fi_month.scenario, result.fi.fi_number.scenario) == (
        own.month,
        own.fi_number,
    )


@_SETTINGS
@given(ledgers(), st.lists(money_changes(-1), min_size=1, max_size=3))
def test_a_cost_never_improves_a_cash_figure(books: Ledger, costs: list[dict]):
    baseline = books.baseline(AS_OF)
    result = engine.run(baseline, _doc(costs))
    assert all(d <= 0 for d in _cash_deltas(result))


@_SETTINGS
@given(ledgers(), st.lists(money_changes(+1), min_size=1, max_size=3))
def test_income_never_worsens_a_cash_figure(books: Ledger, income: list[dict]):
    baseline = books.baseline(AS_OF)
    result = engine.run(baseline, _doc(income))
    assert all(d >= 0 for d in _cash_deltas(result))


@_SETTINGS
@given(ledgers(), amounts, days_ahead, st.one_of(st.none(), st.integers(0, 600)))
def test_an_extra_payment_never_adds_interest(
    books: Ledger, monthly: Decimal, start: int, length: int | None
):
    baseline = books.baseline(AS_OF)
    for debt in baseline.debts:
        change = {
            "type": "extra_debt_payment",
            "debt": debt.debt_id,
            "monthly": f"{monthly}",
            "from": _day(start),
            "to": None if length is None else _day(start + length),
        }
        result = engine.run(baseline, _doc([change]))
        paid = next(d for d in result.debts.items if d.debt_id == debt.debt_id)
        assert paid.total_interest.scenario is not None and paid.total_interest.baseline is not None
        assert paid.total_interest.scenario <= paid.total_interest.baseline
        total = result.debts.total_interest
        assert total.scenario is not None and total.baseline is not None
        assert total.scenario <= total.baseline


@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(ledgers(), st.lists(money_changes(-1), min_size=3, max_size=3), st.randoms())
def test_a_comparison_does_not_depend_on_the_order_of_its_options(
    books: Ledger, costs: list[dict], shuffle: random.Random
):
    baseline = books.baseline(AS_OF)
    options = [
        _doc([costs[0]], label="A"),
        _doc([costs[1]], label="B"),
        _doc([costs[0], costs[2]], label="C"),
    ]
    reordered = list(options)
    shuffle.shuffle(reordered)
    first = views.comparison_view(comparison.compare(baseline, options))
    again = views.comparison_view(comparison.compare(baseline, reordered))

    def by_label(view: dict) -> dict:
        return {
            "options": {o["label"]: o for o in view["options"]},
            "trade": {(t["option"], t["against"]): t for t in view["trade"]},
            "sensitivity": {o["option"]: o for o in view["sensitivity"]["options"]},
            "break_evens": sorted(json.dumps(b, sort_keys=True) for b in view["break_evens"]),
        }

    assert by_label(first) == by_label(again)


@_SETTINGS
@given(ledgers(), st.lists(money_changes(-1), min_size=1, max_size=3), st.randoms())
def test_a_result_is_deterministic_and_its_hash_ignores_key_order_and_formatting(
    books: Ledger, changes: list[dict], shuffle: random.Random
):
    baseline = books.baseline(AS_OF)
    doc = {"schema": "salli.scenario/1", "horizon_years": 7, "changes": changes}
    first = views.result_view(engine.run(baseline, schema.load(doc)))
    assert views.result_view(engine.run(baseline, schema.load(doc))) == first

    def reshape(value: object) -> object:
        """The same document, its keys in another order and its amounts
        written another way ("12.50" as "+12.500", "0.069" left alone)."""
        if isinstance(value, dict):
            items = list(value.items())
            shuffle.shuffle(items)
            out = {}
            for key, v in items:
                if key in ("amount", "monthly_net") and isinstance(v, str):
                    number = Decimal(v)
                    v = f"+{number:.3f}" if number > 0 else f"{number:.4f}"
                out[key] = reshape(v)
            return out
        if isinstance(value, list):
            return [reshape(v) for v in value]
        return value

    text = json.dumps(reshape(doc), indent=shuffle.choice([None, 2]))
    again = views.result_view(engine.run(baseline, schema.load(json.loads(text))))
    assert again["hash"] == first["hash"]
    # With as_of given as the baseline's own, the hash is the same too.
    dated = views.result_view(
        engine.run(baseline, schema.load({**doc, "as_of": AS_OF.isoformat()}))
    )
    assert dated["hash"] == first["hash"]
