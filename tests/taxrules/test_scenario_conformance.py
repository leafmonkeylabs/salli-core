"""
Tax-aware scenarios over every fictional jurisdiction in the conformance
suite (tests/taxrules/conformance/): a taper, a filing-status question,
stacked gains, a capped contribution, a formula tariff, a rebate and
final-rate income, with years that start on 1 January, 1 April and 1 July.
No shape of rule breaks the projection.

For each: the person's books are in the rules' currency, their residency is
the rules' country, and their pay of S a month is booked in the rules'
first income role from the year's start. As of the end of the sixth month,
the year's projected total is 12 × S (six months actual, six at the
average), and a raise of R a month tagged with that role from the next
month adds 6 × R. The change in the year's tax is the rules' own `net` on
those totals, less on the baseline's, and its six parts add up to it.
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from salli.domain.scenarios import engine, schema
from salli.domain.taxrules.engine import compile_rule_set, evaluate
from tests.baseline_ledger import USER, Ledger
from tests.golden.taxed import rules_row

CONFORMANCE = Path(__file__).parent / "conformance"
#: A month's pay in each currency's own scale.
PAY = {"JPY": Decimal("400000"), "KWD": Decimal("1500.000")}
#: Answers a jurisdiction's questions need.
ANSWERS: dict[str, dict[str, str | bool]] = {"jointland": {"filing_status": "single"}}


def _month_end(day: dt.date, months: int) -> dt.date:
    index = day.year * 12 + day.month - 1 + months
    year, month = index // 12, index % 12 + 1
    return dt.date(year, month, calendar.monthrange(year, month)[1])


def _books(doc: dict[str, Any], pay: Decimal) -> tuple[Ledger, str, dt.date]:
    currency = doc["currency"]
    books = Ledger(currency)
    role = next(r["key"] for r in doc["roles"] if r["kind"] == "income")
    books.account("chk", "asset")
    books.account("pay", "income", tax_role=role)
    books.account("eq", "equity")
    start = dt.date.fromisoformat(doc["year"]["start"])
    books.book((start - dt.timedelta(days=1)).isoformat(), "chk", "eq", str(pay))
    for k in range(6):
        books.book(_month_end(start, k).replace(day=20).isoformat(), "chk", "pay", str(pay))
    books.uow.user_profiles.rows.setdefault(USER, {})["tax_residency"] = doc["jurisdiction"][
        "country"
    ]
    books.uow.tax_rule_sets.active.append(rules_row(doc, rule_set_id=f"rs-{doc['currency']}"))
    return books, role, _month_end(start, 5)


@pytest.mark.parametrize("path", sorted(CONFORMANCE.glob("*.json")), ids=lambda p: p.stem)
def test_a_raise_through_each_jurisdiction(path: Path):
    doc = json.loads(path.read_text())
    pay = PAY.get(doc["currency"], Decimal("3000.00"))
    rise = pay / 5
    books, role, as_of = _books(doc, pay)
    answers = ANSWERS.get(path.stem, {})
    scenario = schema.load(
        {
            "schema": "salli.scenario/1",
            "changes": [
                {
                    "type": "income_change",
                    "monthly": str(rise),
                    "from": (as_of + dt.timedelta(days=1)).isoformat(),
                    "tax_role": role,
                    "label": "Raise",
                }
            ],
            **({"tax": {"answers": answers}} if answers else {}),
        }
    )
    result = engine.run(books.baseline(as_of), scenario)
    assert result.tax.status == "computed", result.tax.outcome.reason
    first, second = result.tax.outcome.years[:2]
    (total,) = first.roles
    assert (total.actual, total.projected, total.scenario) == (
        6 * pay,
        12 * pay,
        12 * pay + 6 * rise,
    )

    compiled = compile_rule_set(doc)
    net_b = evaluate(compiled, {role: 12 * pay}, answers).net
    net_s = evaluate(compiled, {role: 12 * pay + 6 * rise}, answers).net
    assert (first.net_baseline, first.net_scenario) == (net_b, net_s)
    assert first.change == net_s - net_b
    assert len(first.parts) == 6
    assert sum((p for _, p in first.parts), Decimal(0)) == first.change

    # The next year carries the rules forward, from the day after this
    # year's last, a year long.
    start = dt.date.fromisoformat(doc["year"]["start"])
    assert second.carried_forward and second.start == start.replace(year=start.year + 1)
    assert second.status == "computed"
