"""
The statement classifier's side of the bargain: what it asks the model and
how it reads the answer. The model is a stand-in; nothing calls Anthropic.
"""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import anthropic
import pytest

from salli.adapters.parsing.llm_classifier import classify_transactions
from salli.domain.parsing.models import RawRow

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
def model(monkeypatch):
    """Answers every prompt with `model.reply`, and keeps the prompts."""
    seen = SimpleNamespace(reply="[]", prompts=[])

    class Client:
        def __init__(self, api_key: str) -> None:
            self.messages = self

        async def create(self, **request: Any) -> Any:
            seen.prompts.append(request["messages"][0]["content"])
            return SimpleNamespace(content=[SimpleNamespace(text=seen.reply)])

    monkeypatch.setattr(anthropic, "AsyncAnthropic", Client)
    return seen


async def test_with_the_statements_account_the_model_chooses_only_the_other_side(model):
    model.reply = json.dumps(
        [
            {"index": 0, "account_id": "food", "category": "groceries", "confidence": 0.9},
            {"index": 1, "account_id": "salary", "category": "salary", "confidence": "high"},
        ]
    )

    spent, earned = await classify_transactions(ROWS, CHART, api_key="k", money_account=CHART[0])

    assert "never choose checking" in model.prompts[0]
    assert (spent.debit_account_id, spent.credit_account_id) == ("food", "checking")
    assert (earned.debit_account_id, earned.credit_account_id) == ("checking", "salary")
    assert (spent.confidence, earned.confidence) == (0.9, 0.5)  # "high" is no number


async def test_without_it_the_model_chooses_both_and_a_null_is_no_account(model):
    model.reply = json.dumps(
        [{"index": 0, "debit_account_id": "food", "credit_account_id": None, "category": None}]
    )

    spent, earned = await classify_transactions(ROWS, CHART, api_key="k")

    assert "debit_account_id" in model.prompts[0]
    assert (spent.debit_account_id, spent.credit_account_id, spent.category) == ("food", "", "")
    # No answer for a row at all: nothing chosen.
    assert (earned.debit_account_id, earned.credit_account_id) == ("", "")
