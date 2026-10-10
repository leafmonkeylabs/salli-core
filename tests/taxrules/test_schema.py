"""
The rule-set document: its field types, and the JSON Schema agents write
against.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaError
from pydantic import ValidationError

from salli.domain.taxrules.common import is_user_assigned_country
from salli.domain.taxrules.schema import Question, RuleSet, rule_set_json_schema
from tests.taxrules.documents import minimal


def test_the_json_schema_is_a_valid_draft_2020_12_schema():
    schema = rule_set_json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)


def test_a_valid_document_passes_the_json_schema():
    Draft202012Validator(rule_set_json_schema()).validate(minimal())


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["band_tables"]["main"]["bands"][0].update(rate=0.1),  # a JSON number
        lambda d: d["band_tables"]["main"]["bands"][0].update(rate="1e-1"),
        lambda d: d.update(extra=True),
        lambda d: d["blocks"][0].update(type="unknown"),
        lambda d: d["year"].update(start=20310101),
        lambda d: d["roles"][0].update(key="Not a key"),
    ],
)
def test_the_json_schema_rejects_what_the_validator_rejects(change):
    doc = minimal()
    change(doc)
    with pytest.raises(JsonSchemaError):
        Draft202012Validator(rule_set_json_schema()).validate(doc)
    with pytest.raises(ValidationError):
        RuleSet.model_validate(doc)


def test_amounts_come_back_as_decimals_and_go_out_as_strings():
    doc = RuleSet.model_validate(minimal())
    rate = doc.band_tables["main"].bands[0].rate
    assert rate == Decimal("0.1") and isinstance(rate, Decimal)
    dumped = doc.model_dump(mode="json", by_alias=True)
    assert dumped["band_tables"]["main"]["bands"][0]["rate"] == "0.1"
    assert dumped["year"]["start"] == "2031-01-01"
    assert dumped["schema"] == "salli.tax/1"


@pytest.mark.parametrize(
    "value",
    [
        0.1,
        1,
        True,
        "1e5",
        "1,000",
        " 1",
        "1 ",
        "+1",
        ".5",
        "1.",
        "0x10",
        "NaN",
        "Infinity",
        "",
        "1." + "1" * 28,
    ],
)
def test_a_figure_must_be_a_plain_decimal_string(value):
    doc = minimal()
    doc["band_tables"]["main"]["bands"][0]["upto"] = value
    with pytest.raises(ValidationError):
        RuleSet.model_validate(doc)


@pytest.mark.parametrize(
    "value", ["2031-1-1", "2031-02-30", 20310101, "2031-01-01T00:00:00", "31/01/2031"]
)
def test_a_date_must_be_an_iso_date(value):
    doc = minimal()
    doc["year"]["end"] = value
    with pytest.raises(ValidationError):
        RuleSet.model_validate(doc)


def test_dates_are_parsed_as_dates():
    assert RuleSet.model_validate(minimal()).year.end == datetime.date(2031, 12, 31)


@pytest.mark.parametrize(
    ("code", "ok"),
    [
        ("XA", True),
        ("XZ", True),
        ("AA", True),
        ("QM", True),
        ("QZ", True),
        ("ZZ", True),
        ("QL", False),
        ("XX", True),
        ("LK", False),
        ("GB", False),
    ],
)
def test_user_assigned_country_codes_are_recognised(code, ok):
    assert is_user_assigned_country(code) is ok


@pytest.mark.parametrize("code", ["GB", "LK", "XA", "ZZ"])
def test_real_and_user_assigned_countries_both_validate(code):
    doc = minimal()
    doc["jurisdiction"]["country"] = code
    RuleSet.model_validate(doc)


@pytest.mark.parametrize(
    ("question", "ok"),
    [
        ({"type": "number", "default": "2"}, True),
        ({"type": "number", "default": 2}, False),
        ({"type": "boolean", "default": False}, True),
        ({"type": "boolean", "default": "false"}, False),
        ({"type": "choice", "choices": ["a", "b"], "default": "a"}, True),
        ({"type": "choice", "choices": ["a", "b"], "default": "c"}, False),
        ({"type": "choice"}, False),
        ({"type": "choice", "choices": ["a", "a"]}, False),
        ({"type": "number", "choices": ["a"]}, False),
    ],
)
def test_a_questions_default_and_choices_must_fit_its_type(question, ok):
    data = {"key": "q", "label": "Q", **question}
    if ok:
        Question.model_validate(data)
    else:
        with pytest.raises(ValidationError):
            Question.model_validate(data)
