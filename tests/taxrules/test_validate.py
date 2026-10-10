"""
Validation: a broken document is reported with every problem, each with a path
an author (or their agent) can follow, and nothing broken passes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from salli.domain.taxrules.validate import MAX_DOCUMENT_BYTES, validate
from tests.taxrules.documents import minimal


def errors(doc) -> list[tuple[str, str]]:
    report = validate(doc)
    assert not report.ok
    return [(p.path, p.message) for p in report.errors]


def has(problems: list[tuple[str, str]], path: str, fragment: str) -> bool:
    return any(p == path and fragment in m for p, m in problems)


def test_the_minimal_document_is_valid():
    report = validate(minimal())
    assert report.errors == ()
    assert report.warnings == ()
    assert report.ok
    assert report.content_hash is not None


def test_validate_accepts_json_text_too():
    assert validate(json.dumps(minimal())).ok


def test_the_example_document_in_the_docs_is_valid():
    """docs/taxrules.md shows a whole document; it must stay one that works."""
    text = (Path(__file__).parents[2] / "docs" / "taxrules.md").read_text()
    match = re.search(r"```jsonc\n(.*?)```", text, re.DOTALL)
    assert match is not None
    report = validate(match.group(1))
    assert report.ok and report.warnings == ()


# ── the broken documents the suite must catch ──────────────────────────────────


def test_a_cycle_is_reported_with_its_path():
    doc = minimal()
    doc["lines"] += [
        {"key": "a", "label": "A", "expr": "line.b + 1"},
        {"key": "b", "label": "B", "expr": "line.c * 2"},
        {"key": "c", "label": "C", "expr": "line.a"},
    ]
    problems = errors(doc)
    assert has(problems, "lines[1].expr", "cycle: a -> b -> c -> a")
    assert len([m for _, m in problems if "cycle" in m]) == 1


def test_a_block_that_refers_to_itself_is_a_cycle():
    doc = minimal()
    doc["blocks"][0]["of"] = "role.income - line.allowance"
    assert has(errors(doc), "blocks[0]", "cycle: allowance -> allowance")


def test_unknown_references_are_each_reported_where_they_are():
    doc = minimal()
    doc["blocks"][0]["of"] = "role.salary"
    doc["lines"][0]["expr"] = "line.tax - line.withholdings + answer.status"
    doc["result"]["net"] = "line.nope"
    problems = errors(doc)
    assert has(problems, "blocks[0].of", "Unknown role: role.salary")
    assert has(problems, "lines[0].expr", "Unknown line: line.withholdings")
    assert has(problems, "lines[0].expr", "Unknown question: answer.status")
    assert has(problems, "result.net", "Unknown line: line.nope")


def test_an_unknown_band_table_is_reported_for_a_schedule_and_for_bands():
    doc = minimal()
    doc["blocks"][1]["table"] = "general"
    doc["lines"].append({"key": "x", "label": "X", "expr": 'bands(role.income, "other")'})
    problems = errors(doc)
    assert has(problems, "blocks[1].table", "no band table 'general'")
    assert has(problems, "lines[1].expr", "no band table 'other'")


def test_a_band_number_beyond_the_table_is_reported():
    doc = minimal()
    doc["lines"].append({"key": "x", "label": "X", "expr": 'band_amount(role.income, "main", 3)'})
    assert has(errors(doc), "lines[1].expr", "has 2 bands, not 3")


def test_type_errors_are_reported():
    doc = minimal()
    doc["lines"] += [
        {"key": "flag", "label": "A yes/no line", "expr": "role.income > 0"},
        {"key": "sum", "label": "Mixed", "expr": "1 + true"},
    ]
    problems = errors(doc)
    assert has(problems, "lines[1].expr", "must be a number, not a boolean")
    assert has(problems, "lines[2].expr", "must be a number")


def test_float_amounts_are_refused_with_a_reason():
    doc = minimal()
    doc["band_tables"]["main"]["bands"][0]["rate"] = 0.1
    doc["examples"][0]["inputs"]["income"] = 25000
    problems = errors(doc)
    assert has(problems, "band_tables.main.bands[0].rate", "decimal strings")
    assert has(problems, "examples[0].inputs.income", "decimal strings")


def test_float_amounts_in_json_text_are_refused_too():
    text = json.dumps(minimal()).replace('"rate": "0.1"', '"rate": 0.1')
    assert has(errors(text), "band_tables.main.bands[0].rate", "decimal strings")


def test_an_unsorted_band_table_is_refused():
    doc = minimal()
    doc["band_tables"]["main"]["bands"] = [
        {"upto": "20000", "rate": "0.1"},
        {"upto": "10000", "rate": "0.2"},
        {"upto": None, "rate": "0.3"},
    ]
    assert has(errors(doc), "band_tables.main", "ascend")


def test_a_band_table_without_an_open_top_band_is_refused():
    doc = minimal()
    doc["band_tables"]["main"]["bands"] = [{"upto": "10000", "rate": "0.1"}]
    assert has(errors(doc), "band_tables.main", "last band has no ceiling")


def test_a_failing_example_says_which_figure_what_was_expected_and_what_came_out():
    doc = minimal()
    doc["examples"][0]["expected"] = {
        "payable": "2999",
        "lines": {"tax.band_2.tax": "1500", "tax": "3000"},
    }
    report = validate(doc)
    assert report.errors == ()
    assert not report.ok
    (example,) = report.examples
    assert example.name == "Basic" and not example.passed
    mismatches = {m.key: m for m in example.mismatches}
    assert set(mismatches) == {"payable", "tax.band_2.tax"}
    assert str(mismatches["payable"]) == "payable: expected 2999, got 3000 (from line.balance)"
    band = mismatches["tax.band_2.tax"]
    assert (band.expected, band.got) == (1500, 2000)
    assert band.expr == "line.tax.band_2.amount * 0.2"


def test_an_example_expecting_a_line_that_doesnt_exist_fails():
    doc = minimal()
    doc["examples"][0]["expected"] = {"lines": {"taxes": "3000"}}
    report = validate(doc)
    assert any(p.path == "examples[0].expected.lines.taxes" for p in report.errors)
    assert not report.examples[0].passed


def test_an_example_that_cant_run_says_why():
    doc = minimal()
    doc["lines"][0]["expr"] = "line.tax / (role.income - 25000)"
    report = validate(doc)
    (example,) = report.examples
    assert not example.passed
    assert example.error is not None and "Division by zero" in example.error


def test_a_missing_source_id_is_reported():
    doc = minimal()
    doc["blocks"][0]["source"] = "statute"
    doc["examples"][0]["source"] = "worked_examples"
    problems = errors(doc)
    assert has(problems, "blocks[0].source", "No source has the id 'statute'")
    assert has(problems, "examples[0].source", "No source has the id 'worked_examples'")


def test_an_expression_past_the_limits_is_reported():
    doc = minimal()
    doc["lines"][0]["expr"] = "(" * 60 + "line.tax" + ")" * 60
    assert has(errors(doc), "lines[0].expr", "nest at most 50")


def test_an_expression_past_the_length_limit_is_a_schema_error():
    doc = minimal()
    doc["lines"][0]["expr"] = "1 + " * 1000 + "1"
    assert has(errors(doc), "lines[0].expr", "4000")


def test_a_syntax_error_comes_with_a_caret():
    doc = minimal()
    doc["lines"][0]["expr"] = "line.tax -* 2"
    report = validate(doc)
    (problem,) = report.errors
    assert problem.path == "lines[0].expr"
    assert problem.snippet == "line.tax -* 2\n          ^"


# ── more ways to be wrong ──────────────────────────────────────────────────────


def test_every_problem_is_reported_at_once():
    doc = minimal()
    doc["blocks"][0]["source"] = "nope"
    doc["lines"][0]["expr"] = "line.unknown"
    doc["roles"].append({"key": "income", "kind": "income", "label": "Again"})
    problems = errors(doc)
    assert has(problems, "blocks[0].source", "No source")
    assert has(problems, "lines[0].expr", "Unknown line")
    assert has(problems, "roles[2].key", "already used at roles[0].key")


def test_a_block_and_a_line_cant_share_a_key():
    doc = minimal()
    doc["lines"].append({"key": "allowance", "label": "Again", "expr": "1"})
    assert has(errors(doc), "lines[1].key", "Line key 'allowance' is already used at blocks[0].key")


def test_a_question_cant_share_a_roles_key():
    doc = minimal()
    doc["questions"] = [{"key": "income", "label": "Income?", "type": "boolean", "default": False}]
    assert has(errors(doc), "questions[0].key", "also a role's key")


@pytest.mark.parametrize(
    ("change", "path", "fragment"),
    [
        (lambda d: d.update(colour="blue"), "colour", "not a field here"),
        (lambda d: d["jurisdiction"].update(country="UK"), "jurisdiction.country", "ISO 3166-1"),
        (lambda d: d.update(currency="eur"), "currency", "ISO 4217"),
        (lambda d: d.update(currency="ABC"), "currency", "ISO 4217"),
        (lambda d: d["year"].update(start="2032-01-01"), "year", "start before it ends"),
        (lambda d: d["year"].update(end="2031-02-30"), "year.end", "YYYY-MM-DD"),
        (lambda d: d.update(schema="salli.tax/2"), "schema", "salli.tax/1"),
        (lambda d: d.pop("result"), "result", "is required"),
        (lambda d: d["blocks"][0].update(type="allowance"), "blocks[0]", "type"),
        (lambda d: d["blocks"][2].update(refundable="yes"), "blocks[2].refundable", "boolean"),
        (lambda d: d["roles"][0].update(key="Income"), "roles[0].key", "pattern"),
        (
            lambda d: d["band_tables"]["main"]["bands"][1].update(rate="1.5"),
            "band_tables.main.bands[1].rate",
            "between",
        ),
        (
            lambda d: d["band_tables"].update({"Bad Key": d["band_tables"]["main"]}),
            "band_tables.Bad Key",
            "not a valid key",
        ),
    ],
)
def test_schema_problems_point_at_the_field(change, path, fragment):
    doc = minimal()
    change(doc)
    assert has(errors(doc), path, fragment)


def test_a_choice_must_cover_every_choice_and_name_only_real_ones():
    doc = minimal()
    doc["questions"] = [
        {
            "key": "status",
            "label": "Status",
            "type": "choice",
            "choices": ["single", "joint", "widowed"],
        }
    ]
    doc["lines"].append(
        {
            "key": "x",
            "label": "X",
            "expr": 'choice(answer.status, "single", 1, "joint", 2, "married", 3)',
        }
    )
    problems = errors(doc)
    assert has(problems, "lines[1].expr", "'married' is not one of answer.status's choices")
    assert has(problems, "lines[1].expr", "leaves out widowed")


def test_a_question_default_must_fit_the_question():
    doc = minimal()
    doc["questions"] = [{"key": "children", "label": "Children", "type": "number", "default": True}]
    assert has(errors(doc), "questions[0]", "decimal string")


def test_example_inputs_must_be_declared_and_well_typed():
    doc = minimal()
    doc["questions"] = [{"key": "blind", "label": "Blind", "type": "boolean", "default": False}]
    doc["lines"][0]["expr"] = "line.tax - line.withholding + if(answer.blind, 0, 0)"
    doc["examples"][0]["inputs"].update(salary="1", blind="yes")
    problems = errors(doc)
    assert has(problems, "examples[0].inputs.salary", "neither a role nor a question")
    assert has(problems, "examples[0].inputs.blind", "answer true or false")


def test_a_suggested_account_must_carry_a_declared_role():
    doc = minimal()
    doc["suggested_accounts"] = [
        {"code": "1400", "name": "Withheld", "type": "asset", "tax_role": "apit"}
    ]
    assert has(errors(doc), "suggested_accounts[0].tax_role", "not one of the rule set's roles")


def test_a_rule_set_without_examples_is_not_ok():
    doc = minimal()
    doc["examples"] = []
    report = validate(doc)
    assert not report.ok
    assert [p.path for p in report.errors] == ["examples"]


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ('{"schema": "salli.tax/1", "schema": "salli.tax/1"}', "appears twice"),
        ('{"rate": NaN}', "not a number JSON allows"),
        ("{", "Not valid JSON"),
        ("[]", "is a JSON object"),
        ("[" * 100_000 + "]" * 100_000, "Not valid JSON"),
        (" " * (MAX_DOCUMENT_BYTES + 1), "larger than"),
    ],
)
def test_text_that_isnt_a_json_object_is_refused(text, fragment):
    problems = errors(text)
    assert problems[0][0] == "$" and fragment in problems[0][1]


# ── warnings ───────────────────────────────────────────────────────────────────


def test_warnings_flag_what_an_author_probably_got_wrong():
    doc = minimal()
    doc["roles"].append({"key": "gifts", "kind": "other", "label": "Gifts"})
    doc["questions"] = [{"key": "blind", "label": "Blind", "type": "boolean", "default": False}]
    doc["band_tables"]["spare"] = {"bands": [{"upto": None, "rate": "0.5"}]}
    doc["blocks"][0].pop("source")
    doc["blocks"].append(
        {"type": "credit", "key": "foreign", "of": "role.withheld", "refundable": False}
    )
    doc["lines"].append({"key": "levy", "label": "Levy", "expr": "role.income * 0.25"})
    doc["deadlines"] = [{"key": "return", "label": "Return", "date": "2032-04-30"}]
    report = validate(doc)
    assert report.ok, "warnings don't block"
    warnings = {(p.path, p.message.split(";")[0]) for p in report.warnings}
    assert warnings == {
        ("roles[2]", "Role 'gifts' is never used"),
        ("questions[0]", "Question 'blind' is never used"),
        ("band_tables.spare", "Band table 'spare' is never used"),
        ("band_tables.spare", "This table's figures have no source"),
        ("blocks[0]", "This block's figures have no source"),
        (
            "blocks[3]",
            "A non-refundable credit with no cap can reduce the tax below zero and create a refund",
        ),
        ("lines[1]", "This line's figures have no source"),
        ("deadlines[0]", "This deadline has no source"),
    }
