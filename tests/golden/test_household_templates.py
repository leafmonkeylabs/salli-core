"""
Hand-worked decision templates on the household ledger
(tests/golden/household.py): each template's answers, the options it
builds, and what Salli's engine makes of them, with the arithmetic shown.

The household as of Sunday 2026-10-11, in euros (where each figure comes
from: tests/golden/test_household_scenarios.py): 15,801.47 of cash, its
lowest 13,998.91 on 2027-02-24; 1,898.32 of essential spending a month; a
car loan (9,900.00 at 5.9%, 350.00 a month) and a student loan (8,000.00
at 4.5%, 120.00 a month); FI in 2042-05 on an FI number of 611,127.00. All
of the surplus is invested (the placeholder), so cash ends each month where
it started unless a change says otherwise, and the real return is the
placeholder 4%.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.domain.baseline import Baseline
from salli.domain.decisions import catalogue, start, templates
from salli.domain.decisions.journal import PrincipleInUse
from salli.domain.decisions.principles import Principle, compile_check, content_hash
from tests.golden import household as h
from tests.guardrails import assert_never_ranks

pytestmark = pytest.mark.asyncio

D = Decimal
#: The placeholder real return, a twelfth of it a month.
MONTHLY = D("0.04") / 12


async def _baseline(**profile: object) -> Baseline:
    uow = h.uow(**profile)
    return await BaselineService(uow.factory(), fx=h.fx(), today=lambda: h.AS_OF).build(h.USER)


@pytest.fixture
async def baseline() -> Baseline:
    return await _baseline()


def _principle(label: str, check: str) -> PrincipleInUse:
    principle = Principle(label, check)
    return PrincipleInUse(
        f"p-{label}", 1, content_hash(principle), principle, compile_check(principle)
    )


def run(
    baseline: Baseline,
    template_id: str,
    answers: dict[str, Any],
    principles: tuple[PrincipleInUse, ...] = (),
) -> dict[str, Any]:
    template = catalogue.get(template_id)
    facts = templates.facts_of(baseline, [(p.principle, p.expr) for p in principles])
    read, built = templates.build(template, answers, facts)
    return start.start(baseline, template, read, built, principles)


def by_label(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Each option's run (the comparison's), by label."""
    return {o["label"]: o for o in result["comparison"]["options"]}


def figures(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Each option's principle figures, by label."""
    return {o["label"]: o["figures"] for o in result["principles"]["options"]}


def grown(amount: Decimal, months: int) -> Decimal:
    return amount * (1 + MONTHLY) ** months


def cents(value: Decimal) -> Decimal:
    return value.quantize(D("0.01"))


async def test_afford_it(baseline):
    result = run(
        baseline,
        "afford-it",
        {
            "price": "2400.00",
            "what": "Laptop",
            "date": "2026-11-02",
            "account": "chk",
            "instalment_months": 12,
            "instalment_rate": "0.069",
            "wait_months": 6,
            "save_monthly": "400.00",
        },
    )
    runs, values = by_label(result), figures(result)
    assert list(runs) == ["Pay cash", "Spread over 12 months", "Wait 6 months"]

    # Paying cash takes the price out for good: the low is 2,400.00 lower.
    assert runs["Pay cash"]["cash"]["lowest"]["scenario"] == "11598.91"  # 13,998.91 - 2,400.00
    assert values["Pay cash"]["cash_1y"] == "13401.47"  # 15,801.47 - 2,400.00

    # Spread: eleven payments of 207.55 and a last of 207.63, 90.68 of
    # interest on top of the household's 2,009.25.
    spread = runs["Spread over 12 months"]
    loan = next(c for c in spread["changes"] if c["type"] == "loan")
    assert (loan["payment"], loan["first_payment"]) == ("207.55", "2026-12")
    assert spread["debts"]["total_interest"]["scenario"] == "2099.93"
    assert spread["cash"]["lowest"]["scenario"] == "13821.01"

    # Wait: 400.00 of each month's surplus kept in cash from November to
    # April (six months, 2,400.00), then the laptop bought on 2027-05-02,
    # so cash is back where it started by the year's end.
    assert values["Wait 6 months"]["cash_1y"] == "15801.47"  # + 6 × 400.00 - 2,400.00
    # What wasn't invested: 400.00 at the end of each of November to April,
    # 11 down to 6 month-ends before the year's end at the 4% placeholder.
    kept = sum((grown(D(400), k) for k in range(6, 12)), D(0))
    assert cents(kept) == D("2468.90")
    assert values["Wait 6 months"]["investments_1y"] == "61077.92"
    # 63,546.81 - 61,077.92 = 2,468.89: the same, but for the cent the two
    # figures were each rounded to.
    assert abs(D("63546.81") - D("61077.92") - kept) < D("0.01")
    # Its low is November's, before the first 400.00 is kept: the baseline's
    # own low that month.
    wait = runs["Wait 6 months"]["cash"]
    assert (wait["lowest"]["scenario"], wait["lowest_date"]["scenario"]) == (
        "14013.25",
        "2026-11-24",
    )

    # Paying cash ends ahead of spreading at every loan rate: what the
    # payments would have earned invested outweighs the interest.
    says = [b["says"] for b in result["comparison"]["break_evens"]]
    assert (
        "Pay cash ends the horizon with more net worth than Spread over 12 months at every "
        "loan rate from 0% to 100%."
    ) in says


async def test_debt_or_invest_once(baseline):
    """The bonus of docs/scenarios.md: 5,000.00 in December onto the student
    loan at 4.5% or invested, over ten years; and a split."""
    result = run(
        baseline,
        "debt-or-invest",
        {
            "debt": "debt-student",
            "amount": "5000.00",
            "start": "2026-12-01",
            "split_on_debt": "2000.00",
            "horizon_years": 10,
        },
    )
    runs = by_label(result)
    assert list(runs) == ["Pay down Student loan", "Invest it", "Split"]

    def student(label: str) -> tuple[str, str]:
        debt = next(d for d in runs[label]["debts"]["items"] if d["debt_id"] == "debt-student")
        return debt["paid_off"]["scenario"], debt["total_interest"]["scenario"]

    # Paying 5,000.00 off clears it in 2029-01 rather than 2033-03, its
    # interest 197.29 rather than 1,223.12; 2,000.00 clears it in 2031-06.
    assert student("Pay down Student loan") == ("2029-01", "197.29")
    assert student("Invest it") == ("2033-03", "1223.12")
    assert student("Split") == ("2031-06", "675.36")
    # Net worth in ten years against the baseline: the 5,000.00 grown 118
    # months (7,404.72) less what left cash, or the freed payments grown
    # from 2029 (7,558.51) less the same.
    assert cents(grown(D(5000), 118)) == D("7404.72")
    assert runs["Invest it"]["monthly"][-1]["net_worth"]["delta"] == "2404.72"
    assert runs["Pay down Student loan"]["monthly"][-1]["net_worth"]["delta"] == "2558.51"

    # Both sides treated alike, investing comes out level at the loan's own
    # rate, to the basis point above it; so does any split against either.
    evens = {
        (tuple(b["options"]), b["option"]): b["value"] for b in result["comparison"]["break_evens"]
    }
    assert evens == {
        (("Invest it", "Pay down Student loan"), "Invest it"): "0.0451",
        (("Invest it", "Split"), "Invest it"): "0.0451",
        (("Pay down Student loan", "Split"), "Split"): "0.045",
    }
    # The loan's 4.5% is certain; the placeholder 4% return isn't. Over ten
    # years, the share of 1,000 seeded paths on which investing grows more.
    odds = result["odds"]
    assert (odds["debt"], odds["debt_real_rate"], odds["months"]) == ("debt-student", "0.045", 120)
    assert D(0) < D(odds["invest_beats_paying_down"]) < D("0.5")


async def test_debt_or_invest_every_month(baseline):
    result = run(
        baseline,
        "debt-or-invest",
        {
            "debt": "debt-student",
            "amount": "200.00",
            "how": "monthly",
            "months": 12,
            "start": "2026-12-01",
            "horizon_years": 10,
        },
    )
    runs, values = by_label(result), figures(result)
    # Both take 200.00 out of cash each month from December: eleven by the
    # end of October 2027.
    for label in ("Pay down Student loan", "Invest it"):
        assert values[label]["cash_1y"] == "13601.47"  # 15,801.47 - 11 × 200.00
    debt = next(
        d for d in runs["Pay down Student loan"]["debts"]["items"] if d["debt_id"] == "debt-student"
    )
    assert (debt["paid_off"]["scenario"], debt["total_interest"]["scenario"]) == (
        "2031-03",
        "647.98",
    )
    [even] = result["comparison"]["break_evens"]
    assert (even["kind"], even["value"]) == ("invest_vs_debt_return", "0.0451")


async def test_a_windfall(baseline):
    result = run(
        baseline,
        "windfall",
        {
            "amount": "6000.00",
            "date": "2026-12-01",
            "splits": [
                {"label": "Car first", "debts": [{"debt": "debt-car", "amount": "6000.00"}]},
                {
                    "label": "Half and half",
                    "debts": [{"debt": "debt-student", "amount": "3000.00"}],
                    "invest": "3000.00",
                },
                {"label": "Keep it"},
            ],
        },
    )
    runs, values = by_label(result), figures(result)
    # Kept, it is all in cash; put to work, it leaves as it came.
    assert values["Keep it"]["cash_1y"] == "21801.47"  # 15,801.47 + 6,000.00
    assert values["Car first"]["cash_1y"] == values["Half and half"]["cash_1y"] == "15801.47"
    # The car loan owes 9,598.68 after November's payment; December's
    # interest is 47.19, and 350.00 + 6,000.00 leaves 3,295.87, cleared by
    # ten more payments: in 2027-10, at 183.09 of interest in all.
    car = next(d for d in runs["Car first"]["debts"]["items"] if d["debt_id"] == "debt-car")
    assert (car["paid_off"]["scenario"], car["total_interest"]["scenario"]) == (
        "2027-10",
        "183.09",
    )
    assert cents(D("9598.68") * D("0.059") / 12) == D("47.19")
    # FI comes sooner each way: 187 months for the baseline.
    assert [values[k]["fi_months"] for k in runs] == [185, 185, 186]


async def test_a_windfall_used_in_the_as_of_month(baseline):
    """Used on the day it arrives, in the as-of month: the payment onto the
    car loan is paid at October's end, before November's payment."""
    result = run(
        baseline,
        "windfall",
        {
            "amount": "6000.00",
            "splits": [
                {"label": "Car first", "debts": [{"debt": "debt-car", "amount": "6000.00"}]},
                {"label": "Keep it"},
            ],
        },
    )
    assert result["notes"] == []
    runs, values = by_label(result), figures(result)
    # The car loan owes 9,900.00 - 6,000.00 = 3,900.00 at October's end;
    # November's interest is on that, 19.18, and 350.00 leaves 3,569.18.
    # Eleven payments of 350.00 and a last of 170.96 clear it in 2027-10:
    # 4,020.96 paid, 120.96 of it interest.
    assert cents(D("3900") * D("0.059") / 12) == D("19.18")
    assert 11 * D("350.00") + D("170.96") == D("3900.00") + D("120.96")
    car = next(d for d in runs["Car first"]["debts"]["items"] if d["debt_id"] == "debt-car")
    assert (car["paid_off"]["scenario"], car["total_interest"]["scenario"]) == (
        "2027-10",
        "120.96",
    )
    # It arrives and leaves within October, so cash is where it was.
    assert values["Car first"]["cash_1y"] == "15801.47"
    assert values["Keep it"]["cash_1y"] == "21801.47"
    assert values["Car first"]["fi_months"] == 185


async def test_a_big_recurring_change(baseline):
    result = run(
        baseline,
        "big-change",
        {
            "label": "New flat",
            "start": "2027-01-01",
            "monthly_costs": "+450.00",
            "upfront": "1800.00",
        },
    )
    runs, values = by_label(result), figures(result)
    assert list(runs) == ["As things are", "New flat"]
    flat = runs["New flat"]
    # The deposit leaves cash for good; the rent's extra 450.00 leaves it on
    # each month's first day and comes out of what is invested at its end,
    # so the low on 2027-02-24 is both lower.
    assert flat["cash"]["lowest"]["scenario"] == "11748.91"  # 13,998.91 - 1,800.00 - 450.00
    assert values["New flat"]["cash_1y"] == "14001.47"  # 15,801.47 - 1,800.00
    # Spending for good: the FI number rises by 450.00 × 12 / 4%.
    assert flat["fi"]["fi_number"]["delta"] == "135000.00"
    assert (flat["fi"]["fi_month"]["scenario"], flat["fi"]["fi_month"]["delta_months"]) == (
        "2048-02",
        69,
    )
    assert runs["As things are"]["fi"]["fi_month"]["delta_months"] == 0


async def test_refinancing_the_car_loan(baseline):
    result = run(
        baseline,
        "borrow",
        {
            "purpose": "refinance",
            "debt": "debt-car",
            "loans": [{"annual_rate": "0.039", "term_months": 36}],
        },
    )
    answers = {a["id"]: a for a in result["answers"]}
    # What the car loan owes, from the household's own debts.
    assert (answers["principal"]["value"], answers["principal"]["source"]) == (
        "9900.00",
        "your_debts",
    )
    assert answers["start"]["value"] == "2026-11-01"
    runs, values = by_label(result), figures(result)
    new = runs["3.9% over 36 months"]
    # 9,900.00 at 3.9% over 36 months: 9,900.00 × r / (1 - (1 + r)^-36), r
    # = 0.325% a month.
    r = D("0.039") / 12
    assert cents(D("9900") * r / (1 - (1 + r) ** -36)) == D("291.85")
    assert next(c for c in new["changes"] if c["type"] == "loan")["payment"] == "291.85"
    # November: the car loan's 350.00 (48.68 of it interest) leaves
    # 9,598.68, which the new loan's money pays off; 301.32 of it stays.
    car = next(d for d in new["debts"]["items"] if d["debt_id"] == "debt-car")
    assert (car["paid_off"]["scenario"], car["total_interest"]["scenario"]) == ("2026-11", "48.68")
    assert values["3.9% over 36 months"]["cash_1y"] == "16102.79"  # 15,801.47 + 301.32
    # 48.68 + the student loan's 1,223.12 + the new loan's 606.49.
    assert new["debts"]["total_interest"]["scenario"] == "1878.29"
    [even] = result["comparison"]["break_evens"]
    assert (even["kind"], even["option"], even["value"]) == (
        "loan_rate",
        "3.9% over 36 months",
        "0.0442",
    )


async def test_refinancing_the_car_loan_in_the_as_of_month(baseline):
    """Taken out on the as-of date: the new loan's money pays the car loan
    off at October's end, before its first payment, so it costs no more
    interest."""
    result = run(
        baseline,
        "borrow",
        {
            "purpose": "refinance",
            "debt": "debt-car",
            "start": "2026-10-11",
            "loans": [{"annual_rate": "0.039", "term_months": 36}],
        },
    )
    runs, values = by_label(result), figures(result)
    new = runs["3.9% over 36 months"]
    car = next(d for d in new["debts"]["items"] if d["debt_id"] == "debt-car")
    assert (car["paid_off"]["scenario"], car["total_interest"]["scenario"]) == ("2026-10", "0.00")
    # The new loan's payments start in November, as from 2026-11-01 (291.85
    # a month, 606.49 of interest); with the student loan's 1,223.12.
    loan = next(d for d in new["debts"]["items"] if d["source"] == "scenario")
    assert loan["total_interest"]["scenario"] == "606.49"
    assert new["debts"]["total_interest"]["scenario"] == "1829.61"  # 1,223.12 + 606.49
    # 9,900.00 in and 9,900.00 out in October.
    assert values["3.9% over 36 months"]["cash_1y"] == "15801.47"
    assert values["3.9% over 36 months"]["debt_free_months"] == 77  # the student loan's 2033-03


async def test_borrowing_for_a_car(baseline):
    result = run(
        baseline,
        "borrow",
        {
            "principal": "18000.00",
            "what": "A car",
            "into": "chk",
            "loans": [
                {"annual_rate": "0.069", "term_months": 48},
                {"annual_rate": "0.049", "term_months": 36, "label": "Dealer offer"},
            ],
        },
    )
    runs = by_label(result)
    assert list(runs) == ["6.9% over 48 months", "Dealer offer", "Don't borrow"]

    def loan(label: str) -> tuple[str, str]:
        found = next(c for c in runs[label]["changes"] if c["type"] == "loan")
        return found["payment"], next(
            d["total_interest"]["scenario"]
            for d in runs[label]["debts"]["items"]
            if d["source"] == "scenario"
        )

    assert loan("6.9% over 48 months") == ("430.20", "2649.46")
    assert loan("Dealer offer") == ("538.67", "1392.04")
    # The money is spent on the day it arrives: cash a year on is unchanged.
    assert {f["cash_1y"] for f in figures(result).values()} == {"15801.47"}


async def test_an_emergency_fund(baseline):
    nine = _principle("Nine months of essentials", "emergency_months >= 9")
    result = run(baseline, "emergency-fund", {"set_aside": ["200.00", "500.00"]}, (nine,))
    answers = {a["id"]: a for a in result["answers"]}
    assert (answers["target_months"]["value"], answers["target_months"]["source"]) == (
        "9",
        "your_principles",
    )
    cover = result["cover"]
    # 9 × 1,898.32 of essential spending; cash covers 15,801.47 / 1,898.32
    # = 8.32 months today.
    assert (cover["monthly_spending"], cover["target"], cover["now"]) == (
        "1898.32",
        "17084.88",
        "8.32",
    )
    # All of the surplus is invested, so as things are cash never grows.
    assert cover["baseline"] == {"month": None, "months": None}
    # 200.00 a month from November: 15,801.47 + 6 × 200.00 = 17,001.47 by
    # April's end, short; + 7 × 200.00 = 17,201.47 by May's. 500.00: 3 ×
    # 500.00 = 1,500.00 by January's end (2 × 500.00 falls short).
    assert [(o["option"], o["month"], o["months"]) for o in cover["options"]] == [
        ("As things are", None, None),
        ("Set aside 200.00 a month", "2027-05", 7),
        ("Set aside 500.00 a month", "2027-01", 3),
    ]
    values = figures(result)
    assert values["Set aside 200.00 a month"]["cash_1y"] == "18201.47"  # + 12 × 200.00
    # What is kept in cash isn't invested: FI comes later, 191 and 197 months
    # against 187.
    assert [values[k]["fi_months"] for k in values] == [187, 191, 197]
    # The principle reads the low over the next thirteen months: still 7.38
    # months at most, so it isn't kept, whichever amount; Salli says so and
    # counts nothing.
    statuses = [o["results"][0]["status"] for o in result["principles"]["options"]]
    assert statuses == ["breaks", "breaks", "breaks"]


async def test_with_none_of_the_surplus_invested_cash_covers_the_target_by_the_months_end():
    """Kept in cash, October's salary still to come takes cash to 19,261.13
    by the as-of month's end: the target is reached at once, as things are."""
    kept = await _baseline(
        fi_assumptions={"surplus_invested": {"value": "0", "source": "kept in cash"}}
    )
    result = run(kept, "emergency-fund", {"target_months": "9", "set_aside": ["200.00"]})
    assert result["cover"]["baseline"] == {"month": "2026-10", "months": 0}


#: An answer to every template, for what holds of them all.
EVERY = {
    "afford-it": {"price": "2400.00", "instalment_months": 12, "instalment_rate": "0.069"},
    "debt-or-invest": {"debt": "debt-car", "amount": "1000.00"},
    "windfall": {
        "amount": "3000.00",
        "splits": [{"label": "Invest", "invest": "3000.00"}, {"label": "Keep"}],
    },
    "big-change": {"label": "New job", "monthly_income": "+600.00"},
    "borrow": {"principal": "5000.00", "loans": [{"annual_rate": "0.08", "term_months": 24}]},
    "emergency-fund": {"target_months": "6", "set_aside": ["300.00"]},
    "rent-or-buy": {
        "price": "350000.00",
        "deposit": "70000.00",
        "mortgages": [{"annual_rate": "0.042", "term_months": 300}],
        "buying_costs": "9000.00",
        "owning_costs": "250.00",
        "rent": "city",
        "selling_costs": "0.03",
    },
}


async def test_no_start_ranks_and_each_carries_what_recording_needs(baseline):
    """Whatever the template, the result names no option best, recommended or
    preferred, has no field that ranks or scores, and holds what
    record_decision takes: the question, each option as run (its as-of date
    filled in, so recording runs it on the same baseline), and the labels."""
    assert set(EVERY) == {t.id for t in catalogue.TEMPLATES}
    for template_id, answers in EVERY.items():
        result = run(baseline, template_id, answers)
        assert_never_ranks(result)
        record = result["record"]
        assert record["labels"] == [o["label"] for o in result["options"]]
        assert [s["label"] for s in record["options"]] == record["labels"]
        assert {s["as_of"] for s in record["options"]} == {"2026-10-11"}
        assert record["earliest_review"] == "2026-10-31"
        assert [o["scenario_hash"] for o in result["options"]] == [
            o["hash"] for o in result["comparison"]["options"]
        ]
