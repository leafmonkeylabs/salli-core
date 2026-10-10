"""
The statement classifier's side of the bargain: what it asks the model and
how it reads the answer. The model is a stand-in; nothing calls Anthropic.
"""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from salli.adapters.parsing.llm_classifier import classify_transactions
from salli.domain.parsing.models import RawRow
from tests.fakes import FakeLLM

CHART = [
    SimpleNamespace(id="checking", code="1000", name="Checking", type="asset"),
    SimpleNamespace(id="food", code="5000", name="Food", type="expense"),
    SimpleNamespace(id="salary", code="4000", name="Salary", type="income"),
]
ROWS = [
    RawRow("2026-10-02", "WHOLE FOODS", Decimal("84.17"), False, "USD"),
    RawRow("2026-10-15", "ACME PAYROLL", Decimal("3250.00"), True, "USD"),
]


@pytest.fixture
def model():
    """Answers every prompt with `model.reply`, and keeps the prompts."""
    return FakeLLM("[]")


async def test_with_the_statements_account_the_model_chooses_only_the_other_side(model):
    model.reply = json.dumps(
        [
            {"index": 0, "account_id": "food", "category": "groceries", "confidence": 0.9},
            {"index": 1, "account_id": "salary", "category": "salary", "confidence": "high"},
        ]
    )

    spent, earned = await classify_transactions(ROWS, CHART, llm=model, money_account=CHART[0])

    assert "never choose checking" in model.prompts[0]
    assert (spent.debit_account_id, spent.credit_account_id) == ("food", "checking")
    assert (earned.debit_account_id, earned.credit_account_id) == ("checking", "salary")
    assert (spent.confidence, earned.confidence) == (0.9, 0.5)  # "high" is no number


async def test_without_it_the_model_chooses_both_and_a_null_is_no_account(model):
    model.reply = json.dumps(
        [{"index": 0, "debit_account_id": "food", "credit_account_id": None, "category": None}]
    )

    spent, earned = await classify_transactions(ROWS, CHART, llm=model)

    assert "debit_account_id" in model.prompts[0]
    assert (spent.debit_account_id, spent.credit_account_id, spent.category) == ("food", "", "")
    # No answer for a row at all: nothing chosen.
    assert (earned.debit_account_id, earned.credit_account_id) == ("", "")


def test_malformed_items_in_the_models_answer_are_left_out():
    # `index: null` and non-object items raised TypeError, failing the whole
    # import after the meter had charged.
    from salli.adapters.parsing.llm_classifier import _parse_response

    answer = '[{"index": null}, "junk", 3, {"index": "x"}, {"index": 1, "account_id": "a"}]'
    assert _parse_response(answer) == {1: {"index": 1, "account_id": "a"}}


async def test_it_asks_the_fast_model_with_the_whole_prompt_as_the_user_turn(model):
    """The request Anthropic always got: no system prompt, the prompt as the
    user's turn, 4096 tokens to answer in. On the OpenAI routes the token
    hint is dropped (the plan route forbids it)."""
    await classify_transactions(ROWS, CHART, llm=model)

    (request,) = model.requests
    assert request["tier"] == "fast"
    assert request["instructions"] == ""
    assert request["max_output_tokens"] == 4096
    assert "WHOLE FOODS" in request["input"]
