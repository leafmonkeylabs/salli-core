"""
What a scenario document may hold (`salli.scenario/1`), and what the engine
refuses once it sees the user's money: each problem with its path, every one
of them at once.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from salli.application.services.baseline_service import BaselineService
from salli.domain.baseline import Baseline
from salli.domain.scenarios import engine, schema
from tests.golden import household as h


def _problems(doc: dict[str, Any]) -> dict[str, str]:
    with pytest.raises(ValidationError) as caught:
        schema.load(doc)
    return {p.path: p.message for p in schema.problems(caught.value)}


def _doc(*changes: dict[str, Any], **more: Any) -> dict[str, Any]:
    return {"schema": "salli.scenario/1", "changes": list(changes), **more}


ONE_OFF = {"type": "one_off", "date": "2026-11-02", "amount": "-2400.00", "label": "Laptop"}


def test_a_minimal_scenario_takes_its_defaults():
    doc = schema.load({"schema": "salli.scenario/1"})
    assert (doc.as_of, doc.horizon_years, doc.changes, doc.label) == (None, 20, [], None)
    assert schema.load(_doc(ONE_OFF)).changes[0].amount == Decimal("-2400.00")
    # A leading + is money in.
    income = {"type": "income_change", "monthly": "+600", "from": "2027-01-01", "label": "Job"}
    assert schema.load(_doc(income)).changes[0].monthly == Decimal("600")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount", -2400),
        ("amount", -2400.5),
        ("amount", True),
        ("amount", "1e3"),
        ("amount", "1,000"),
    ],
)
def test_amounts_are_decimal_strings_never_json_numbers(field, value):
    problems = _problems(_doc({**ONE_OFF, field: value}))
    assert list(problems) == [f"changes[0].{field}"]


def test_rates_are_decimal_strings_from_0_to_1():
    loan = {
        "type": "loan",
        "principal": "18000",
        "annual_rate": 0.069,
        "term_months": 48,
        "start": "2026-12-01",
        "label": "Car",
    }
    assert "decimal strings" in _problems(_doc(loan))["changes[0].annual_rate"]
    assert "between" in _problems(_doc({**loan, "annual_rate": "6.9"}))["changes[0].annual_rate"]
    assert (
        "greater than zero"
        in _problems(_doc({**loan, "annual_rate": "0.069", "principal": "0"}))[
            "changes[0].principal"
        ]
    )
    for term in (0, 601, 12.0, "12"):
        assert (
            "months from 1 to 600"
            in _problems(_doc({**loan, "annual_rate": "0.069", "term_months": term}))[
                "changes[0].term_months"
            ]
        )


@pytest.mark.parametrize(
    "day", ["2026-13-01", "2026-02-30", "01/11/2026", "2026-11-01T00:00:00", 20261101]
)
def test_dates_are_iso_days(day):
    assert "YYYY-MM-DD" in _problems(_doc({**ONE_OFF, "date": day}))["changes[0].date"]


def test_a_range_ends_after_it_starts():
    rent = {
        "type": "recurring",
        "amount": "-450",
        "cadence": "monthly",
        "start": "2027-01-01",
        "end": "2026-12-31",
        "label": "Flat",
    }
    assert _problems(_doc(rent))["changes[0]"] == "end is before start"


@pytest.mark.parametrize("years", [0, 51, -1, 20.0, "20", True])
def test_the_horizon_is_1_to_50_whole_years(years):
    assert "from 1 to 50" in _problems(_doc(horizon_years=years))["horizon_years"]


def test_at_most_50_changes():
    assert _problems(_doc(*[ONE_OFF] * 51)) == {"changes": "has more than 50 changes"}
    assert len(schema.load(_doc(*[ONE_OFF] * 50)).changes) == 50


def test_unknown_fields_types_and_versions_are_refused_with_their_paths():
    problems = _problems(
        {
            "schema": "salli.scenario/2",
            "changes": [{**ONE_OFF, "currency": "USD"}, {"type": "lottery"}, {"amount": "1"}],
            "extra": True,
        }
    )
    assert problems == {
        "schema": "Input should be 'salli.scenario/1'",
        "changes[0].currency": "is not a field here",
        "changes[1]": (
            "is not a change type; the types are: one_off, recurring, income_change, loan, "
            "extra_debt_payment, invest, stop_recurring, set_aside, sell, asset"
        ),
        "changes[2]": (
            "needs a type: one of one_off, recurring, income_change, loan, "
            "extra_debt_payment, invest, stop_recurring, set_aside, sell, asset"
        ),
        "extra": "is not a field here",
    }


def test_every_change_type_reads():
    doc = schema.load(
        _doc(
            ONE_OFF,
            {
                "type": "recurring",
                "amount": "-450",
                "cadence": "weekly",
                "start": "2027-01-01",
                "label": "x",
            },
            {
                "type": "income_change",
                "monthly": "600",
                "from": "2027-01-01",
                "to": "2027-12-31",
                "label": "x",
            },
            {
                "type": "loan",
                "principal": "1",
                "annual_rate": "0",
                "term_months": 1,
                "start": "2027-01-01",
                "into": "chk",
                "label": "x",
            },
            {
                "type": "extra_debt_payment",
                "debt": "debt-car",
                "monthly": "200",
                "from": "2026-11-01",
            },
            {"type": "invest", "amount": "5000", "date": "2026-12-15", "from": "sav", "label": "x"},
            {"type": "stop_recurring", "key": "streamflix", "from": "2026-11-01"},
            {"type": "set_aside", "monthly": "200", "from": "2026-11-01", "to": "2027-10-31"},
            {"type": "sell", "holding": "h-1", "quantity": "4", "date": "2026-12-15"},
            {
                "type": "asset",
                "price": "250000",
                "date": "2026-12-01",
                "from": "chk",
                "real_growth": "-0.01",
                "selling_costs": "0.03",
                "label": "x",
            },
        )
    )
    assert [c.type for c in doc.changes] == list(schema.CHANGE_TYPES)


SALE = {"type": "sell", "holding": "h-1", "date": "2026-12-15"}


@pytest.mark.parametrize(
    ("change", "path", "says"),
    [
        (SALE, "changes[0]", "give the units to sell (quantity) or the value to sell (amount)"),
        ({**SALE, "quantity": "1", "amount": "100"}, "changes[0]", "not both"),
        ({**SALE, "quantity": 4}, "changes[0].quantity", "not as JSON numbers"),
        ({**SALE, "quantity": "0"}, "changes[0].quantity", "greater than zero"),
        ({**SALE, "quantity": "1.0000000000000000001"}, "changes[0].quantity", "18 decimal"),
        ({**SALE, "quantity": "1", "fees": "-2"}, "changes[0].fees", "can't be negative"),
        (
            {**SALE, "quantity": "3", "lots": [{"lot": "a", "quantity": "2"}]},
            "changes[0]",
            "the lots named add up to 2 units, not the 3 sold",
        ),
        (
            {**SALE, "lots": [{"lot": "a", "quantity": "1"}, {"lot": "a", "quantity": "1"}]},
            "changes[0]",
            "names each lot once",
        ),
        (
            {**SALE, "amount": "100", "lots": [{"lot": "a", "quantity": "1"}]},
            "changes[0]",
            "not an amount",
        ),
        (
            {"type": "invest", "amount": "100", "date": "2026-12-15", "fees": "100", "label": "x"},
            "changes[0]",
            "must be less than it",
        ),
    ],
)
def test_a_sale_or_an_invest_that_cant_be_read_is_refused_at_its_path(change, path, says):
    assert says in _problems(_doc(change))[path]


def test_a_sale_of_named_lots_needs_no_quantity():
    doc = schema.load(
        _doc({**SALE, "lots": [{"lot": "a", "quantity": "1.5"}, {"lot": "b", "quantity": "2"}]})
    )
    (sale,) = doc.changes
    assert isinstance(sale, schema.SellChange) and str(sale.units) == "3.5"


@pytest.mark.parametrize(
    ("change", "path", "message"),
    [
        (
            {"type": "asset", "price": "0", "date": "2026-12-01", "label": "x"},
            "changes[0].price",
            "must be greater than zero",
        ),
        (
            {
                "type": "asset",
                "price": "1",
                "date": "2026-12-01",
                "selling_costs": "1.5",
                "label": "x",
            },
            "changes[0].selling_costs",
            'a rate is a fraction between "0" and "1" ("0.15" is 15%)',
        ),
        (
            {
                "type": "asset",
                "price": "1",
                "date": "2026-12-01",
                "real_growth": "-2",
                "label": "x",
            },
            "changes[0].real_growth",
            'a growth is a yearly fraction from "-1" to "1" ("0.01" is 1%)',
        ),
        (
            {
                "type": "recurring",
                "amount": "-450",
                "cadence": "monthly",
                "start": "2027-01-01",
                "real_growth": 0.01,
                "label": "x",
            },
            "changes[0].real_growth",
            "write amounts as decimal strings",
        ),
    ],
)
def test_an_assets_and_a_growths_fields_are_checked(change, path, message):
    assert message in _problems(_doc(change))[path]


def test_a_recurring_change_without_a_growth_hashes_as_before():
    """`real_growth` left out is no part of the content hash, so a scenario
    written before it existed keeps its hash."""
    rent = {
        "type": "recurring",
        "amount": "-450",
        "cadence": "monthly",
        "start": "2027-01-01",
        "label": "x",
    }
    hashed = schema.hashable(schema.load(_doc(rent)))
    assert "real_growth" not in hashed["changes"][0]
    with_growth = schema.hashable(schema.load(_doc({**rent, "real_growth": "0.01"})))
    assert with_growth["changes"][0]["real_growth"] == Decimal("0.01")


def test_the_json_schema_describes_the_document_for_agents():
    described = schema.json_schema()
    assert described["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert described["properties"]["schema"]["const"] == "salli.scenario/1"
    assert described["properties"]["horizon_years"]["maximum"] == 50
    assert described["properties"]["changes"]["maxItems"] == 50
    one_off = described["$defs"]["OneOffChange"]
    assert one_off["properties"]["amount"]["type"] == "string"
    assert one_off["additionalProperties"] is False
    # Written out in place for a tool's input schema: no $ref left.
    assert "$ref" not in str(schema.inline_json_schema())


# ── What the engine refuses, seeing the user's money ─────────────────────────


@pytest.fixture(scope="module")
def baseline() -> Baseline:
    uow = h.uow()
    service = BaselineService(uow.factory(), fx=h.fx(), today=lambda: h.AS_OF)
    return asyncio.run(service.build(h.USER))


def _refused(baseline: Baseline, *changes: dict[str, Any], **more: Any) -> dict[str, str]:
    with pytest.raises(engine.ScenarioError) as caught:
        engine.run(baseline, schema.load(_doc(*changes, **more)))
    return {p.path: p.message for p in caught.value.problems}


def test_the_engine_says_every_problem_at_once(baseline):
    problems = _refused(
        baseline,
        {**ONE_OFF, "date": "2026-10-10"},
        {**ONE_OFF, "amount": "-2400.005"},
        {**ONE_OFF, "account": "brk"},
        {**ONE_OFF, "account": "usd"},
        {**ONE_OFF, "account": "card"},
        {**ONE_OFF, "account": "nobody"},
        {"type": "extra_debt_payment", "debt": "nobody", "monthly": "200", "from": "2026-11-01"},
        {"type": "stop_recurring", "key": "nothing", "from": "2026-11-01"},
        {"type": "stop_recurring", "key": "savings", "from": "2026-11-01"},
        as_of="2026-10-01",
    )
    assert problems["as_of"] == "is not the baseline's as-of date (2026-10-11)"
    assert problems["changes[0].date"].startswith("is before the as-of date (2026-10-11)")
    assert problems["changes[1].amount"] == "has more decimals than EUR's smallest unit (0.01)"
    assert problems["changes[2].account"].startswith("Brokerage is not one of your cash accounts")
    assert problems["changes[3].account"].startswith("Dollar account is held in USD")
    assert problems["changes[4].account"].startswith("Credit card is not one of your cash accounts")
    assert problems["changes[5].account"] == "'nobody' is not one of your accounts"
    assert problems["changes[6].debt"] == "'nobody' is not one of your debts"
    assert problems["changes[7].key"].startswith("No recurring flow has the key 'nothing'")
    assert problems["changes[8].key"].startswith("Savings moves money between your own accounts")
    assert len(problems) == 10


def test_trailing_zeros_fit_the_smallest_unit(baseline):
    result = engine.run(baseline, schema.load(_doc({**ONE_OFF, "amount": "-2400.000"})))
    assert result.cash.at_end.delta == Decimal("-2400.00")
