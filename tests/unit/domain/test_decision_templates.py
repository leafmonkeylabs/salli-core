"""
Decision templates, pure (domain/decisions/templates.py, catalogue.py): the
questions are typed and checked with paths; defaults come only from the
person's own facts or the date, and a question with no honest default must
be answered; the options are scenarios built from the answers alone; and
nothing a template says ranks or recommends.

The facts are written by hand, in yen (no minor unit) for a person in a
made-up place, so nothing here leans on one currency's two decimals.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from salli.domain.decisions import catalogue, templates
from salli.domain.decisions.principles import Principle, compile_check
from salli.domain.decisions.templates import (
    AccountFact,
    CoverPrinciple,
    DebtFact,
    Facts,
    TemplateError,
    UnknownTemplate,
)
from tests.guardrails import assert_never_ranks

AS_OF = dt.date(2026, 10, 11)
CAR = DebtFact("debt-car", "Car loan", Decimal("990000"), Decimal("0.059"))
STUDY = DebtFact("debt-study", "Study loan", Decimal("800000"), Decimal("0.045"))
FACTS = Facts(
    as_of=AS_OF,
    currency="JPY",
    debts=(CAR, STUDY),
    accounts=(AccountFact("acc-main", "Main"), AccountFact("acc-save", "Savings")),
)
ONE_DEBT = Facts(as_of=AS_OF, currency="JPY", debts=(CAR,))


def build(template_id: str, answers: dict[str, Any], facts: Facts = FACTS):
    return templates.build(catalogue.get(template_id), answers, facts)


def problems(template_id: str, answers: Any, facts: Facts = FACTS) -> dict[str, str]:
    with pytest.raises(TemplateError) as error:
        build(template_id, answers, facts)
    return {p.path: p.message for p in error.value.problems}


def changes(option: templates.OptionBuilt) -> list[dict[str, Any]]:
    return option.scenario.model_dump(mode="json", by_alias=True, exclude_none=True)["changes"]


# ── The catalogue ────────────────────────────────────────────────────────────


def test_the_six_templates_of_the_design():
    assert [t.id for t in catalogue.TEMPLATES] == [
        "afford-it",
        "debt-or-invest",
        "windfall",
        "big-change",
        "borrow",
        "emergency-fund",
    ]
    for template in catalogue.TEMPLATES:
        ids = [q.id for q in template.questions]
        assert len(ids) == len(set(ids)), template.id
        for q in template.questions:
            if q.when is not None:
                assert q.when.question in ids[: ids.index(q.id)], (template.id, q.id)
            if q.type == "choice":
                assert q.choices


def test_no_template_ranks_recommends_or_advises():
    """Not in its title, summary, options, questions or notes: a template is
    a convenience, not advice (docs/design/decision-lab.md, decision 1)."""
    for template in catalogue.TEMPLATES:
        assert_never_ranks(templates.template_view(template, FACTS))


def test_an_unknown_template_says_which_there_are():
    with pytest.raises(UnknownTemplate) as error:
        catalogue.get("rent-or-buy")
    assert "afford-it" in str(error.value) and "emergency-fund" in str(error.value)


def test_the_answers_schema_names_every_question_and_the_persons_own_ids():
    template = catalogue.get("debt-or-invest")
    schema = templates.answers_schema(template, FACTS)
    assert schema["additionalProperties"] is False
    assert list(schema["properties"]) == [q.id for q in template.questions]
    assert schema["properties"]["debt"]["enum"] == ["debt-car", "debt-study"]
    assert schema["properties"]["amount"]["type"] == "string"
    assert schema["properties"]["months"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 48,
        "title": "For how many months?",
        "description": "How long you would keep it up.",
    }
    assert schema["properties"]["how"]["enum"] == ["once", "monthly"]


# ── Answers ──────────────────────────────────────────────────────────────────


def test_what_isnt_answered_and_has_no_honest_default_is_required():
    """A price, a rate, a target: never invented."""
    found = problems("afford-it", {"instalment_months": 12})
    assert found == {
        "answers.price": "is required: What does it cost?",
        "answers.instalment_rate": "is required: At what yearly rate?",
    }
    assert problems("emergency-fund", {"set_aside": ["20000"]}) == {
        "answers.target_months": (
            "is required: How many months of spending do you want your cash to cover?"
        )
    }


def test_each_answer_is_typed_and_checked_with_its_path():
    found = problems(
        "afford-it",
        {
            "price": 2400,
            "what": "",
            "date": "2026-10-01",
            "account": "acc-other",
            "instalment_months": 0,
            "wait_months": "6",
            "colour": "red",
        },
    )
    assert found["answers.price"].startswith("write amounts as decimal strings")
    assert found["answers.what"] == "is a few words of text"
    assert found["answers.date"].startswith("is before the as-of date (2026-10-11)")
    assert found["answers.account"].startswith("'acc-other' is not one of your cash accounts")
    assert found["answers.instalment_months"] == "is a whole number from 1 to 600"
    assert found["answers.wait_months"] == "must be a whole number, like 12"
    assert found["answers.colour"].startswith("is not a question of afford-it")


def test_amounts_keep_to_the_currencys_smallest_unit():
    """Yen have none below the yen."""
    found = problems("afford-it", {"price": "2400.50", "wait_months": 3})
    assert found == {"answers.price": "has more decimals than JPY's smallest unit (1)"}


def test_a_question_asked_only_when_another_is_answered():
    found = problems("afford-it", {"price": "240000", "wait_months": 2, "instalment_rate": "0.1"})
    assert found == {"answers.instalment_rate": "is asked only when instalment_months is answered"}
    found = problems(
        "borrow",
        {
            "principal": "100000",
            "debt": "debt-car",
            "loans": [{"annual_rate": "0.05", "term_months": 12}],
        },
    )
    assert found == {"answers.debt": "is asked only when purpose is refinance"}


def test_a_decision_needs_two_options():
    assert problems("afford-it", {"price": "240000"}) == {
        "answers": (
            "say how else you could pay: instalment_months (spread it), wait_months (wait and "
            "save), or both. A decision needs two options to compare"
        )
    }


def test_defaults_say_where_they_come_from():
    answers, _ = build("afford-it", {"price": "240000", "wait_months": 3})
    assert answers.values["date"] == AS_OF and answers.sources["date"] == "as_of"
    assert answers.values["what"] == "The purchase" and answers.sources["what"] == "salli"
    assert answers.values["horizon_years"] == 20
    assert answers.sources["price"] == "given"
    # The only debt someone has is the debt, from their own data; with two,
    # they say which.
    answers, _ = build("debt-or-invest", {"amount": "50000"}, ONE_DEBT)
    assert (answers.values["debt"], answers.sources["debt"]) == ("debt-car", "your_debts")
    assert answers.notes["debt"] == "Car loan, the only debt you have that owes something"
    assert (answers.values["start"], answers.sources["start"]) == (
        dt.date(2026, 11, 1),
        "next_month",
    )
    assert problems("debt-or-invest", {"amount": "50000"}) == {
        "answers.debt": "is required: Which debt?"
    }


def test_refinancing_borrows_what_the_debt_owes_unless_told_otherwise():
    answers, built = build(
        "borrow",
        {"purpose": "refinance", "loans": [{"annual_rate": "0.039", "term_months": 36}]},
        ONE_DEBT,
    )
    assert (answers.values["principal"], answers.sources["principal"]) == (
        Decimal("990000"),
        "your_debts",
    )
    assert answers.notes["principal"] == "what Car loan owes now"
    assert [o.label for o in built.options] == ["3.9% over 36 months", "Keep Car loan"]


def test_a_principle_sets_the_cash_target():
    six = Principle("Six months of essentials in cash", "emergency_months >= 6")
    other = Principle("Debt-free in five years", "debt_free_months <= 60")
    facts = dataclasses.replace(
        FACTS,
        cover_principles=templates.cover_principles(
            [(other, compile_check(other)), (six, compile_check(six))]
        ),
    )
    assert facts.cover_principles == (
        CoverPrinciple("Six months of essentials in cash", Decimal(6)),
    )
    answers, built = build("emergency-fund", {"set_aside": ["20000"]}, facts)
    assert (answers.values["target_months"], answers.sources["target_months"]) == (
        Decimal(6),
        "your_principles",
    )
    assert built.cover_months == Decimal(6)
    # The other way round says the same.
    flipped = Principle("Six months", "6 <= emergency_months")
    assert templates.cover_months_of(compile_check(flipped)) == Decimal(6)
    assert templates.cover_months_of(compile_check(Principle("x", "emergency_months > 6"))) is None


# ── What each template builds ────────────────────────────────────────────────


def test_afford_it_builds_cash_spread_and_wait():
    _, built = build(
        "afford-it",
        {
            "price": "240000",
            "what": "Laptop",
            "date": "2026-11-02",
            "account": "acc-main",
            "instalment_months": 12,
            "instalment_rate": "0.069",
            "wait_months": 6,
            "save_monthly": "40000",
        },
    )
    cash, spread, wait = built.options
    assert [o.label for o in built.options] == [
        "Pay cash",
        "Spread over 12 months",
        "Wait 6 months",
    ]
    buy = {
        "type": "one_off",
        "date": "2026-11-02",
        "amount": "-240000",
        "account": "acc-main",
        "label": "Laptop",
    }
    assert changes(cash) == [buy]
    assert changes(spread) == [
        buy,
        {
            "type": "loan",
            "principal": "240000",
            "annual_rate": "0.069",
            "term_months": 12,
            "start": "2026-11-02",
            "into": "acc-main",
            "label": "Laptop, over 12 months",
        },
    ]
    # Bought six months on; until the end of the month before, 40,000 of
    # each month's surplus is kept in cash.
    assert changes(wait) == [
        {
            "type": "set_aside",
            "monthly": "40000",
            "from": "2026-11-02",
            "to": "2027-04-30",
            "label": "Saving for Laptop",
        },
        {**buy, "date": "2027-05-02"},
    ]
    assert built.question == "Can I afford Laptop (240000 JPY), and how would I pay for it?"


def test_debt_or_invest_moves_the_same_money_each_way():
    _, built = build(
        "debt-or-invest",
        {
            "debt": "debt-study",
            "amount": "20000",
            "how": "monthly",
            "months": 3,
            "start": "2027-01-31",
            "split_on_debt": "5000",
        },
    )
    pay, invest, split = built.options
    assert [o.label for o in built.options] == ["Pay down Study loan", "Invest it", "Split"]
    extra = {
        "type": "extra_debt_payment",
        "debt": "debt-study",
        "monthly": "20000",
        "from": "2027-01-31",
        "to": "2027-03-31",
        "label": "Extra on Study loan",
    }
    assert changes(pay) == [extra]
    # Each month on the start's day, kept to a short month.
    days = ["2027-01-31", "2027-02-28", "2027-03-31"]
    assert changes(invest) == [
        {"type": "invest", "amount": "20000", "date": day, "label": "Invested"} for day in days
    ]
    assert changes(split) == [
        {**extra, "monthly": "5000"},
        *({"type": "invest", "amount": "15000", "date": day, "label": "Invested"} for day in days),
    ]
    # The split is less than the whole.
    found = problems(
        "debt-or-invest",
        {"debt": "debt-study", "amount": "20000", "start": "2026-10-20", "split_on_debt": "20000"},
    )
    assert set(found) == {"answers.split_on_debt"}


def test_debt_or_invest_may_start_in_the_as_of_month():
    # The engine pays an extra payment in the as-of month at its end, before
    # the debt's first scheduled payment: so the start is the person's to
    # choose, this month included.
    _, built = build(
        "debt-or-invest",
        {"debt": "debt-study", "amount": "20000", "start": "2026-10-11"},
    )
    pay, invest = built.options
    assert changes(pay) == [
        {
            "type": "extra_debt_payment",
            "debt": "debt-study",
            "monthly": "20000",
            "from": "2026-10-11",
            "to": "2026-10-31",
            "label": "Extra on Study loan",
        }
    ]
    assert changes(invest) == [
        {"type": "invest", "amount": "20000", "date": "2026-10-11", "label": "Invested"}
    ]
    # Every month for the most months there are, from this one.
    _, built = build(
        "debt-or-invest",
        {
            "debt": "debt-study",
            "amount": "20000",
            "how": "monthly",
            "months": 48,
            "start": "2026-10-11",
        },
    )
    assert (changes(built.options[0])[0]["from"], changes(built.options[0])[0]["to"]) == (
        "2026-10-11",
        "2030-09-30",
    )
    assert "answers.months" in problems(
        "debt-or-invest",
        {"debt": "debt-study", "amount": "20000", "how": "monthly", "months": 49},
    )


def test_a_windfall_is_shared_out_the_ways_proposed():
    _, built = build(
        "windfall",
        {
            "amount": "600000",
            "date": "2026-10-20",
            "account": "acc-save",
            "splits": [
                {"label": "Car first", "debts": [{"debt": "debt-car", "amount": "600000"}]},
                {
                    "label": "Some of each",
                    "debts": [{"debt": "debt-study", "amount": "200000"}],
                    "invest": "300000",
                },
                {"label": "Keep it"},
            ],
        },
    )
    arrives = {
        "type": "one_off",
        "date": "2026-10-20",
        "amount": "600000",
        "account": "acc-save",
        "label": "The windfall",
    }
    car, each, keep = built.options
    # A payment onto a debt lands in the month the money is used, the as-of
    # month included (at its end, before the debt's next payment).
    assert changes(car) == [
        arrives,
        {
            "type": "extra_debt_payment",
            "debt": "debt-car",
            "monthly": "600000",
            "from": "2026-10-20",
            "to": "2026-10-31",
            "label": "Onto Car loan",
        },
    ]
    assert changes(each)[2] == {
        "type": "invest",
        "amount": "300000",
        "date": "2026-10-20",
        "from": "acc-save",
        "label": "Invested",
    }
    assert changes(keep) == [arrives]
    assert each.describes == (
        "Of 600000 JPY: 200000 onto Study loan, 300000 invested; the rest kept in cash."
    )
    assert built.notes == ()
    # Already in cash, nothing arrives; a split can't use more than there is.
    _, built = build(
        "windfall",
        {"amount": "600000", "arrives": "in_cash", "splits": [{"label": "A"}, {"label": "B"}]},
    )
    assert [changes(o) for o in built.options] == [[], []]
    found = problems(
        "windfall",
        {
            "amount": "600000",
            "splits": [
                {
                    "label": "A",
                    "invest": "500000",
                    "debts": [{"debt": "debt-car", "amount": "200000"}],
                },
                {"label": "A"},
            ],
        },
    )
    assert found == {"answers.splits": "has two splits with one label: give each its own"}
    found = problems(
        "windfall",
        {
            "amount": "600000",
            "splits": [
                {
                    "label": "A",
                    "invest": "500000",
                    "debts": [{"debt": "debt-car", "amount": "200000"}],
                },
                {"label": "B"},
            ],
        },
    )
    assert found == {
        "answers.splits[0]": (
            "puts 700000 to work, more than the 600000 there is: what isn't put onto a debt "
            "or invested stays in cash"
        )
    }
    found = problems(
        "windfall",
        {
            "amount": "600000",
            "splits": [
                {"label": "A", "debts": [{"debt": "debt-xyz", "amount": "1"}]},
                {"label": "B"},
            ],
        },
    )
    assert list(found) == ["answers.splits[0].debts[0].debt"]
    assert found["answers.splits[0].debts[0].debt"].startswith(
        "'debt-xyz' is not one of your debts"
    )


def test_a_big_change_against_things_as_they_are():
    _, built = build(
        "big-change",
        {
            "label": "New flat",
            "start": "2027-01-01",
            "monthly_costs": "+45000",
            "monthly_income": "-10000",
            "upfront": "180000",
            "end": "2028-12-31",
        },
    )
    same, flat = built.options
    assert (same.label, changes(same)) == ("As things are", [])
    assert changes(flat) == [
        {
            "type": "one_off",
            "date": "2027-01-01",
            "amount": "-180000",
            "label": "New flat: at the start",
        },
        {
            "type": "recurring",
            "amount": "-45000",
            "cadence": "monthly",
            "start": "2027-01-01",
            "end": "2028-12-31",
            "label": "New flat: costs",
        },
        {
            "type": "income_change",
            "monthly": "-10000",
            "from": "2027-01-01",
            "to": "2028-12-31",
            "label": "New flat: income",
        },
    ]
    assert flat.describes == (
        "180000 JPY once on 2027-01-01; spending +45000 JPY a month; take-home pay -10000 JPY "
        "a month, from 2027-01-01 to 2028-12-31."
    )
    assert problems("big-change", {"label": "Car"}) == {
        "answers": "say what changes: monthly_costs, monthly_income, upfront, or more than one"
    }


def test_borrowing_compares_each_loan_with_not_borrowing():
    _, built = build(
        "borrow",
        {
            "principal": "1800000",
            "what": "A car",
            "fee": "20000",
            "loans": [
                {"annual_rate": "0.069", "term_months": 48},
                {"annual_rate": "0.049", "term_months": 36, "label": "Dealer offer"},
            ],
        },
    )
    assert [o.label for o in built.options] == [
        "6.9% over 48 months",
        "Dealer offer",
        "Don't borrow",
    ]
    assert changes(built.options[1]) == [
        {
            "type": "loan",
            "principal": "1800000",
            "annual_rate": "0.049",
            "term_months": 36,
            "start": "2026-10-11",
            "label": "Dealer offer",
        },
        {"type": "one_off", "date": "2026-10-11", "amount": "-1800000", "label": "A car"},
        {"type": "one_off", "date": "2026-10-11", "amount": "-20000", "label": "Fee"},
    ]
    # Kept in cash, it is only the loan.
    _, built = build(
        "borrow",
        {
            "principal": "1800000",
            "spent": "kept",
            "loans": [{"annual_rate": "0.05", "term_months": 12}],
        },
    )
    assert [c["type"] for c in changes(built.options[0])] == ["loan"]
    found = problems(
        "borrow",
        {
            "principal": "1800000",
            "loans": [
                {"annual_rate": "0.05", "term_months": 12},
                {"annual_rate": "0.05", "term_months": 12},
            ],
        },
    )
    assert found == {"answers.loans": "has two loans that would be called the same: label each"}


def test_refinancing_pays_the_old_debt_off_with_the_new_loan():
    _, built = build(
        "borrow",
        {
            "purpose": "refinance",
            "debt": "debt-car",
            "loans": [{"annual_rate": "0.039", "term_months": 36}],
        },
    )
    new, keep = built.options
    assert changes(new)[1] == {
        "type": "extra_debt_payment",
        "debt": "debt-car",
        "monthly": "990000",
        "from": "2026-11-01",
        "to": "2026-11-30",
        "label": "Pay off Car loan",
    }
    assert (keep.label, changes(keep)) == ("Keep Car loan", [])
    assert built.notes == (
        "The new loan's money pays Car loan off in 2026-11, on top of that month's payment; "
        "whatever it doesn't need stays in cash.",
    )


def test_refinancing_may_start_in_the_as_of_month():
    _, built = build(
        "borrow",
        {
            "purpose": "refinance",
            "debt": "debt-car",
            "start": "2026-10-11",
            "loans": [{"annual_rate": "0.039", "term_months": 36}],
        },
    )
    loan, pay_off = changes(built.options[0])
    assert (loan["type"], loan["start"]) == ("loan", "2026-10-11")
    assert (pay_off["from"], pay_off["to"]) == ("2026-10-11", "2026-10-31")
    assert built.notes == (
        "The new loan's money pays Car loan off at the end of 2026-10, before its next payment; "
        "whatever it doesn't need stays in cash.",
    )


def test_an_emergency_fund_sets_amounts_aside_and_reads_the_time_to_the_target():
    _, built = build(
        "emergency-fund",
        {"target_months": "4.5", "set_aside": ["20000", "50000"], "months": 12},
    )
    assert built.cover_months == Decimal("4.5")
    assert [o.label for o in built.options] == [
        "As things are",
        "Set aside 20000 a month",
        "Set aside 50000 a month",
    ]
    assert changes(built.options[2]) == [
        {
            "type": "set_aside",
            "monthly": "50000",
            "from": "2026-11-01",
            "to": "2027-10-31",
            "label": "Emergency fund",
        }
    ]
    assert problems("emergency-fund", {"target_months": "6", "set_aside": ["1", "1"]}) == {
        "answers.set_aside": "has the same amount twice: give each once"
    }


# ── Tax roles ────────────────────────────────────────────────────────────────

TAXED = dataclasses.replace(
    FACTS,
    tax_roles=(
        templates.TaxRoleFact("pension", "deduction", "Pension contributions"),
        templates.TaxRoleFact("salary", "income", "Salary"),
    ),
)


def test_big_change_pay_may_be_before_tax_in_a_role():
    """The pay change is take-home unless a role is named: then it is
    before tax, in that role, and the engine works out the tax."""
    _, built = build(
        "big-change",
        {
            "label": "New job",
            "start": "2027-01-01",
            "monthly_income": "+90000",
            "income_tax_role": "salary",
        },
        TAXED,
    )
    job = built.options[1]
    assert changes(job) == [
        {
            "type": "income_change",
            "monthly": "90000",
            "from": "2027-01-01",
            "tax_role": "salary",
            "label": "New job: income",
        }
    ]
    assert job.describes == "Pay before tax +90000 JPY a month, as salary, from 2027-01-01."
    assert problems(
        "big-change",
        {"label": "Job", "monthly_income": "+1", "income_tax_role": "bonus"},
        TAXED,
    ) == {
        "answers.income_tax_role": "'bonus' is not an income or deduction role of your active "
        "tax rules; yours: pension (deduction), salary (income)"
    }
    # Without active rules there is no role to name.
    assert "you have no active tax rules" in problems(
        "big-change", {"label": "Job", "monthly_income": "+1", "income_tax_role": "salary"}
    ).get("answers.income_tax_role", "")
    # Asked only about a pay change.
    assert problems(
        "big-change", {"label": "Job", "upfront": "1", "income_tax_role": "salary"}, TAXED
    ) == {"answers.income_tax_role": "is asked only when monthly_income is answered"}


def test_a_windfall_may_be_taxable():
    _, built = build(
        "windfall",
        {
            "amount": "500000",
            "tax_role": "salary",
            "splits": [{"label": "Keep"}, {"label": "Invest", "invest": "100000"}],
        },
        TAXED,
    )
    for option in built.options:
        assert changes(option)[0]["tax_role"] == "salary"
        assert option.describes.endswith("It arrives before tax, as salary.")
    assert problems(
        "windfall",
        {
            "amount": "500000",
            "arrives": "in_cash",
            "tax_role": "salary",
            "splits": [{"label": "A"}, {"label": "B"}],
        },
        TAXED,
    ) == {"answers.tax_role": "is asked only when arrives is new"}


def test_tax_answers_go_in_every_option():
    _, built = templates.build(
        catalogue.get("big-change"),
        {"label": "Job", "monthly_income": "+1", "income_tax_role": "salary"},
        TAXED,
        {"filing_status": "single", "blind": False},
    )
    for option in built.options:
        assert option.scenario.tax is not None
        assert option.scenario.tax.answers == {"filing_status": "single", "blind": False}
    with pytest.raises(TemplateError) as error:
        templates.build(
            catalogue.get("big-change"), {"label": "Job", "upfront": "1"}, TAXED, {"x": 3}
        )
    assert [p.path for p in error.value.problems] == ["tax_answers.x"]


def test_the_tax_role_question_lists_only_the_persons_roles():
    schema = templates.answers_schema(catalogue.get("big-change"), TAXED)
    assert schema["properties"]["income_tax_role"]["enum"] == ["pension", "salary"]
    question = next(q for q in catalogue.get("big-change").questions if q.id == "income_tax_role")
    assert question.default is None and not question.required


# ── Holdings (decision lab 3b, decision 21) ─────────────────────────────────

HELD = dataclasses.replace(
    FACTS,
    holdings=(templates.HoldingFact("h-fund", "FND", "My index fund"),),
)


def test_debt_or_invest_may_invest_into_a_holding_the_person_names():
    _, built = build(
        "debt-or-invest",
        {"debt": "debt-car", "amount": "50000", "start": "2026-10-20", "holding": "h-fund"},
        HELD,
    )
    _, invest = built.options
    assert changes(invest) == [
        {
            "type": "invest",
            "amount": "50000",
            "date": "2026-10-20",
            "holding": "h-fund",
            "label": "Invested",
        }
    ]
    assert "into My index fund" in invest.describes


def test_a_windfall_may_invest_into_a_holding_the_person_names():
    _, built = build(
        "windfall",
        {
            "amount": "600000",
            "date": "2026-10-20",
            "holding": "h-fund",
            "splits": [{"label": "Invest", "invest": "300000"}, {"label": "Keep it"}],
        },
        HELD,
    )
    invest, _ = built.options
    assert changes(invest)[1]["holding"] == "h-fund"
    assert "invested in My index fund" in invest.describes


@pytest.mark.parametrize("template_id", [t.id for t in catalogue.TEMPLATES])
def test_no_template_ever_picks_a_holding(template_id):
    """Even when the person holds exactly one, no question defaults to it,
    and an option names a holding only when the answers did."""
    template = catalogue.get(template_id)
    for question in template.questions:
        if question.type == "holding":
            assert question.default is None and not question.required
            assert templates.question_view(question, HELD)["default"] is None
    if template_id == "debt-or-invest":
        _, built = build(
            template_id, {"debt": "debt-car", "amount": "50000", "start": "2026-10-20"}, HELD
        )
    elif template_id == "windfall":
        _, built = build(
            template_id,
            {
                "amount": "600000",
                "splits": [{"label": "Invest", "invest": "300000"}, {"label": "Keep it"}],
            },
            HELD,
        )
    else:
        return
    for option in built.options:
        assert all("holding" not in c for c in changes(option))


def test_the_holding_question_lists_only_the_persons_own():
    schema = templates.answers_schema(catalogue.get("debt-or-invest"), HELD)
    assert schema["properties"]["holding"]["enum"] == ["h-fund"]
    found = problems(
        "debt-or-invest",
        {"debt": "debt-car", "amount": "50000", "start": "2026-10-20", "holding": "VOO"},
        HELD,
    )
    assert "is not one of your holdings" in found["answers.holding"]
