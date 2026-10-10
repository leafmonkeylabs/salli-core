"""
The engine: compiling into an ordered line graph, evaluating it for one
taxpayer, and the content hash that pins which rules produced a result.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from salli.domain.taxrules.common import RuleSetError
from salli.domain.taxrules.engine import (
    RuleSetEvaluationError,
    canonical_json,
    compile_rule_set,
    content_hash,
    evaluate,
)
from salli.domain.taxrules.schema import RuleSet
from tests.taxrules.documents import minimal

D = Decimal


def with_question(doc: dict, **question) -> dict:
    doc["questions"] = [{"key": "status", "label": "Filing status", **question}]
    return doc


# ── compiling ──────────────────────────────────────────────────────────────────


def test_compile_accepts_a_parsed_document_or_plain_json():
    from_json = compile_rule_set(minimal())
    from_model = compile_rule_set(RuleSet.model_validate(minimal()))
    assert [line.key for line in from_json.lines] == [line.key for line in from_model.lines]


def test_compile_reports_schema_problems_with_paths():
    doc = minimal()
    doc["blocks"][0]["amount"] = 5000
    with pytest.raises(RuleSetError) as caught:
        compile_rule_set(doc)
    assert [p.path for p in caught.value.problems] == ["blocks[0].amount"]


def test_lines_come_after_everything_they_use_and_otherwise_keep_their_order():
    doc = minimal()
    doc["lines"] = [
        {"key": "last", "label": "Uses later lines", "expr": "line.balance + line.first"},
        {"key": "first", "label": "Nothing", "expr": "1"},
        {"key": "balance", "label": "Tax less withholding", "expr": "line.tax - line.withholding"},
    ]
    keys = [line.key for line in compile_rule_set(doc).lines]
    for key, dependency in [
        ("last", "balance"),
        ("last", "first"),
        ("balance", "tax"),
        ("tax", "tax.band_2.tax"),
    ]:
        assert keys.index(dependency) < keys.index(key)
    assert keys.index("allowance") < keys.index("withholding")  # the declared order where free
    assert len(keys) == len(set(keys))


def test_a_long_chain_of_lines_compiles_without_exhausting_the_stack():
    doc = minimal()
    doc["lines"] = [{"key": "l0", "label": "L", "expr": "line.tax"}] + [
        {"key": f"l{n}", "label": "L", "expr": f"line.l{n - 1} + 1"} for n in range(1, 999)
    ]
    doc["result"]["net"] = "line.l998"
    doc["examples"][0]["expected"] = {"payable": "3998"}
    compiled = compile_rule_set(doc)
    assert evaluate(compiled, {"income": D("25000")}).tax_payable == D("3998")


def test_a_long_cycle_is_named_from_its_first_line():
    doc = minimal()
    doc["lines"] = [
        {"key": f"c{n}", "label": "C", "expr": f"line.c{(n + 1) % 600}"} for n in range(600)
    ]
    with pytest.raises(RuleSetError) as caught:
        compile_rule_set(doc)
    (problem,) = [p for p in caught.value.problems if "cycle" in p.message]
    assert problem.path == "lines[0].expr"
    assert problem.message.endswith("c598 -> c599 -> c0")


# ── evaluating ─────────────────────────────────────────────────────────────────


def test_a_result_lists_every_line_with_the_expression_behind_it():
    result = evaluate(compile_rule_set(minimal()), {"income": D("25000"), "withheld": D("500")})
    assert result.tax_payable == D("2500") and result.refund_due == 0
    assert (result.country, result.year, result.currency) == ("XZ", "2031", "EUR")
    line = result.line("withholding")
    assert (line.amount, line.expr, line.refundable, line.source) == (
        D("500"),
        "role.withheld",
        True,
        None,
    )
    assert result.line("allowance").source == "law"
    assert result.net_expr == "line.balance"


def test_a_role_with_no_total_is_zero():
    result = evaluate(compile_rule_set(minimal()), {})
    assert result.amount("allowance") == 0
    assert result.tax_payable == 0 and result.refund_due == 0


def test_a_negative_net_is_a_refund():
    result = evaluate(compile_rule_set(minimal()), {"income": D("25000"), "withheld": D("3500.50")})
    assert (result.net, result.tax_payable, result.refund_due) == (D("-500.50"), D(0), D("500.50"))


def test_the_net_is_rounded_before_it_is_split():
    doc = minimal()
    doc["result"] = {"net": "line.balance", "round": {"mode": "nearest", "unit": "1"}}
    result = evaluate(compile_rule_set(doc), {"income": D("25000"), "withheld": D("3000.40")})
    assert (result.net, result.tax_payable, result.refund_due) == (D(0), D(0), D(0))
    assert str(result.net) == "0"


def test_answers_take_defaults_and_are_checked_against_their_question():
    doc = with_question(minimal(), type="choice", choices=["single", "joint"], default="single")
    doc["lines"][0]["expr"] = (
        'line.tax - line.withholding + choice(answer.status, "single", 0, "joint", 100)'
    )
    compiled = compile_rule_set(doc)
    assert evaluate(compiled, {"income": D("25000")}).tax_payable == D("3000")
    assert evaluate(compiled, {"income": D("25000")}, {"status": "joint"}).tax_payable == D("3100")
    with pytest.raises(RuleSetEvaluationError, match="single, joint"):
        evaluate(compiled, {}, {"status": "widowed"})


def test_a_question_without_an_answer_or_default_is_an_error():
    doc = with_question(minimal(), type="boolean")
    doc["lines"][0]["expr"] = "line.tax - if(answer.status, line.withholding, 0)"
    with pytest.raises(RuleSetEvaluationError) as caught:
        evaluate(compile_rule_set(doc), {"income": D("1")})
    assert [p.path for p in caught.value.problems] == ["answers.status"]


@pytest.mark.parametrize(
    ("roles", "answers", "path"),
    [
        ({"salary": D(1)}, {}, "roles.salary"),
        ({"income": 25000.0}, {}, "roles.income"),
        ({"income": D("NaN")}, {}, "roles.income"),
        ({"income": D("1." + "1" * 30)}, {}, "roles.income"),
        ({}, {"status": "single"}, "answers.status"),
    ],
)
def test_inputs_the_rule_set_doesnt_declare_or_cant_use_are_refused(roles, answers, path):
    with pytest.raises(RuleSetEvaluationError) as caught:
        evaluate(compile_rule_set(minimal()), roles, answers)
    assert path in [p.path for p in caught.value.problems]


def test_arithmetic_that_fails_names_the_line_and_where_in_it():
    doc = minimal()
    doc["lines"].append({"key": "ratio", "label": "Ratio", "expr": "line.tax / role.withheld"})
    with pytest.raises(RuleSetEvaluationError) as caught:
        evaluate(compile_rule_set(doc), {"income": D("25000")})
    (problem,) = caught.value.problems
    assert problem.path == "lines[1].expr"
    assert problem.message.startswith("line ratio: Division by zero")
    assert problem.snippet == "line.tax / role.withheld\n         ^"


def test_form_fields_are_filled_from_the_lines():
    doc = minimal()
    doc["forms"] = [
        {
            "key": "return",
            "label": "Return",
            "fields": [
                {"id": "tax", "label": "Tax", "value": "line.tax"},
                {"id": "owes", "label": "Owes tax", "value": "line.balance > 0"},
            ],
        }
    ]
    result = evaluate(compile_rule_set(doc), {"income": D("25000")})
    assert result.forms == {"return": {"tax": D("3000.0"), "owes": True}}


def test_evaluation_is_deterministic():
    compiled = compile_rule_set(minimal())
    first = evaluate(compiled, {"income": D("123456.78"), "withheld": D("9.99")})
    second = evaluate(compiled, {"income": D("123456.78"), "withheld": D("9.99")})
    assert first == second


# ── content hash ───────────────────────────────────────────────────────────────


def test_the_content_hash_ignores_key_order_and_formatting():
    doc = minimal()
    shuffled = json.loads(json.dumps(doc, sort_keys=True))
    reordered = dict(reversed(list(doc.items())))
    respelled = minimal()
    respelled["band_tables"]["main"]["bands"][0]["rate"] = "0.100"
    respelled["examples"][0]["expected"]["payable"] = "3000.00"
    explicit = minimal()
    explicit["jurisdiction"]["region"] = None
    assert (
        content_hash(doc)
        == content_hash(shuffled)
        == content_hash(reordered)
        == content_hash(respelled)
        == content_hash(explicit)
        == content_hash(RuleSet.model_validate(doc))
    )
    assert len(content_hash(doc)) == 64


def test_the_content_hash_changes_with_the_rules():
    changed = minimal()
    changed["band_tables"]["main"]["bands"][0]["rate"] = "0.11"
    assert content_hash(changed) != content_hash(minimal())


def test_the_canonical_json_is_what_the_content_hash_is_of():
    import hashlib

    text = canonical_json(minimal())
    assert hashlib.sha256(text.encode()).hexdigest() == content_hash(minimal())
    assert json.loads(text)["jurisdiction"] == {"country": "XZ", "region": None}
    # Sorted, compact: writing it out again changes nothing.
    assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))


def test_a_result_carries_its_rule_sets_content_hash():
    compiled = compile_rule_set(minimal())
    assert compiled.content_hash == content_hash(minimal())
    assert evaluate(compiled, {}).content_hash == compiled.content_hash
