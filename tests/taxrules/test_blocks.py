"""
Building blocks compile to plain lines with predictable keys, and the lines
are inspectable: each says exactly what the block became.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.domain.taxrules.blocks import derived_keys, expand, expression_fields
from salli.domain.taxrules.engine import compile_rule_set, evaluate
from salli.domain.taxrules.expr import parse
from salli.domain.taxrules.schema import RuleSet
from tests.taxrules.documents import minimal


def compiled_lines(*blocks: dict) -> dict[str, tuple[str, str]]:
    """Each line a document with these blocks compiles to: key → (label, expression)."""
    doc = minimal()
    doc["blocks"] = list(blocks)
    doc["lines"] = []
    doc["result"]["net"] = "0"
    doc["examples"] = []
    compiled = compile_rule_set(doc)
    return {line.key: (line.label, str(line.expr)) for line in compiled.lines}


def test_a_relief_gives_the_amount_applied_and_what_remains():
    lines = compiled_lines(
        {
            "type": "relief",
            "key": "allowance",
            "label": "Allowance",
            "of": "role.income",
            "amount": "5000",
        }
    )
    assert lines == {
        "allowance": ("Allowance", "min(5000, max(0, role.income))"),
        "allowance.remaining": ("Allowance: remaining", "max(0, role.income - line.allowance)"),
    }


def test_a_deduction_compiles_exactly_like_a_relief():
    relief = compiled_lines({"type": "relief", "key": "k", "of": "role.income", "amount": "5"})
    deduction = compiled_lines(
        {"type": "deduction", "key": "k", "of": "role.income", "amount": "5"}
    )
    assert relief == deduction


def test_a_compound_of_stays_one_operand():
    lines = compiled_lines(
        {"type": "final_rate", "key": "levy", "of": "role.income + role.withheld", "rate": "0.02"}
    )
    assert lines["levy"][1] == "(role.income + role.withheld) * 0.02"


def test_a_capped_share_gives_the_limit_the_amount_allowed_and_what_remains():
    lines = compiled_lines(
        {
            "type": "capped_share",
            "key": "gifts",
            "of": "role.income",
            "claimed": "role.withheld",
            "fraction": "0.25",
            "cap": "750",
        }
    )
    assert lines == {
        "gifts.limit": ("Gifts: limit", "min(role.income * 0.25, 750)"),
        "gifts": ("Gifts", "min(role.withheld, line.gifts.limit)"),
        "gifts.remaining": ("Gifts: remaining", "max(0, role.income - line.gifts)"),
    }


def test_a_capped_share_without_a_cap_is_limited_by_the_fraction_alone():
    lines = compiled_lines(
        {
            "type": "capped_share",
            "key": "gifts",
            "of": "role.income",
            "claimed": "role.withheld",
            "fraction": "0.25",
        }
    )
    assert lines["gifts.limit"][1] == "role.income * 0.25"


def test_a_schedule_gives_each_bands_amount_and_tax_then_the_total():
    lines = compiled_lines({"type": "schedule", "key": "tax", "of": "role.income", "table": "main"})
    assert lines == {
        "tax.band_1.amount": ("Tax: band 1 amount", 'band_amount(role.income, "main", 1)'),
        "tax.band_1.tax": ("Tax: band 1 tax", "line.tax.band_1.amount * 0.1"),
        "tax.band_2.amount": ("Tax: band 2 amount", 'band_amount(role.income, "main", 2)'),
        "tax.band_2.tax": ("Tax: band 2 tax", "line.tax.band_2.amount * 0.2"),
        "tax": ("Tax", "line.tax.band_1.tax + line.tax.band_2.tax"),
    }


def test_a_schedule_over_a_rounding_table_rounds_each_band():
    doc = minimal()
    doc["band_tables"]["main"]["round"] = {"mode": "nearest", "unit": "1"}
    compiled = compile_rule_set(doc)
    assert (
        str(compiled.line("tax.band_2.tax").expr)
        == 'round(line.tax.band_2.amount * 0.2, "nearest", 1)'
    )


def test_a_final_rate_rounds_when_asked():
    lines = compiled_lines(
        {
            "type": "final_rate",
            "key": "flat",
            "of": "role.income",
            "rate": "0.15",
            "round": {"mode": "down", "unit": "0.01"},
        }
    )
    assert lines == {"flat": ("Flat", 'round(role.income * 0.15, "down", 0.01)')}


def test_a_credit_is_its_amount_or_capped_and_records_refundability():
    doc = minimal()
    doc["blocks"] += [
        {
            "type": "credit",
            "key": "foreign",
            "of": "role.withheld",
            "refundable": False,
            "cap": "line.tax",
        },
    ]
    compiled = compile_rule_set(doc)
    assert str(compiled.line("foreign").expr) == "min(role.withheld, line.tax)"
    assert compiled.line("foreign").refundable is False
    assert compiled.line("withholding").refundable is True
    assert str(compiled.line("withholding").expr) == "role.withheld"
    assert compiled.line("tax").refundable is None


def test_a_blocks_lines_carry_its_source_and_where_it_came_from():
    compiled = compile_rule_set(minimal())
    line = compiled.line("allowance.remaining")
    assert (line.source, line.path, line.block) == ("law", "blocks[0]", "relief")
    assert (
        compiled.line("balance").path == "lines[0].expr" and compiled.line("balance").block is None
    )


@pytest.mark.parametrize("index", range(len(minimal()["blocks"])))
def test_derived_keys_match_what_expand_produces(index):
    doc = RuleSet.model_validate(minimal())
    block = doc.blocks[index]
    table = doc.band_tables["main"].to_table()
    parsed = {name: parse(text) for name, text in expression_fields(block).items()}
    assert [d.key for d in expand(block, parsed, table)] == derived_keys(block, table)


def test_the_compiled_lines_compute_what_the_block_describes():
    """Income 25,000: allowance 5,000, then 10,000 at 10% and 10,000 at 20%."""
    result = evaluate(compile_rule_set(minimal()), {"income": Decimal("25000")})
    assert result.amount("allowance") == 5000
    assert result.amount("allowance.remaining") == 20000
    assert result.amount("tax.band_1.amount") == 10000
    assert result.amount("tax.band_2.amount") == 10000
    assert result.amount("tax") == 3000
