"""
Money never a float (docs/design/console.md, decision 12): a request's
amounts and rates are decimal strings, and a JSON number is refused with a
422 that says what to send; and the API document says so, so the generated
SDK refuses a number before it is sent.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from salli.interfaces.api.routers.fi import (
    AllocationRequest,
    GoalRequest,
    GoalUpdateRequest,
)
from salli.interfaces.api.routers.onboarding import (
    IncomeItem,
    OnboardingGoalItem,
    OnboardingRequest,
    OpeningBalanceItem,
)
from tests.unit.api.conftest import AUTH

ROOT = Path(__file__).resolve().parents[3]

#: The request fields that took a number as well as a string, and what else
#: each model needs.
FIELDS: list[tuple[type[BaseModel], str, dict[str, Any]]] = [
    (AllocationRequest, "allocated_amount", {"account_id": "a1"}),
    (GoalRequest, "target_amount", {"name": "Roof"}),
    (GoalUpdateRequest, "target_amount", {}),
    (IncomeItem, "amount", {"code": "4000", "name": "Salary"}),
    (IncomeItem, "fx_rate", {"code": "4000", "name": "Salary", "amount": "10"}),
    (OpeningBalanceItem, "amount", {"code": "1000", "name": "Bank", "type": "asset"}),
    (
        OpeningBalanceItem,
        "fx_rate",
        {"code": "1000", "name": "Bank", "type": "asset", "amount": "10"},
    ),
    (OnboardingRequest, "goal_target_amount", {"name": "Ana"}),
    (OnboardingGoalItem, "target_amount", {"name": "Roof"}),
]


@pytest.mark.parametrize(("model", "field", "rest"), FIELDS)
@pytest.mark.parametrize("number", [1234.5, 1500, 0.1 + 0.2, 9007199254740993])
def test_a_json_number_is_refused(model, field, rest, number):
    with pytest.raises(ValidationError) as refused:
        model.model_validate({**rest, field: number})
    message = str(refused.value)
    assert "decimal string" in message and "JSON number" in message


@pytest.mark.parametrize(("model", "field", "rest"), FIELDS)
def test_a_decimal_string_is_read_exactly(model, field, rest):
    exact = "9007199254740993.01"
    read = model.model_validate({**rest, field: exact})
    assert getattr(read, field) == Decimal(exact)


@pytest.mark.parametrize("text", ["1e3", "NaN", "Infinity", "1,234.50", "", "0x10", " 12 x"])
def test_anything_but_a_plain_decimal_string_is_refused(text):
    with pytest.raises(ValidationError, match="decimal string"):
        GoalRequest.model_validate({"name": "Roof", "target_amount": text})


async def test_over_http_a_number_is_a_422_that_says_what_to_send(client, mock_services):
    r = await client.post(
        "/v1/fi/goals", json={"name": "Roof", "target_amount": 25000.1}, headers=AUTH
    )
    assert r.status_code == 422
    problem = r.json()
    assert problem["type"] == "/problems/validation"
    [error] = problem["detail"]
    assert error["loc"] == ["body", "target_amount"]
    assert "decimal string" in error["msg"] and "JSON number" in error["msg"]
    mock_services.fi.create_goal.assert_not_called()


def test_no_request_body_in_the_api_document_takes_a_number():
    """What the generated SDK's types are made from: a number can't be sent."""
    spec = json.loads((ROOT / "openapi" / "openapi.json").read_text())
    schemas = spec["components"]["schemas"]

    def refs(node: Any):
        if isinstance(node, dict):
            if "$ref" in node:
                yield node["$ref"].rsplit("/", 1)[-1]
            for value in node.values():
                yield from refs(value)
        elif isinstance(node, list):
            for value in node:
                yield from refs(value)

    todo = [
        name
        for operations in spec["paths"].values()
        for operation in operations.values()
        for name in refs(operation.get("requestBody", {}))
    ]
    seen: set[str] = set()
    while todo:
        name = todo.pop()
        if name not in seen:
            seen.add(name)
            todo.extend(refs(schemas[name]))

    def numbers(node: Any, path: str):
        if isinstance(node, dict):
            if node.get("type") in ("number", "integer") and any(
                word in path.lower() for word in ("amount", "rate", "price", "balance", "fee")
            ):
                yield path
            for key, value in node.items():
                yield from numbers(value, f"{path}/{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                yield from numbers(value, f"{path}[{i}]")

    found = [hit for name in sorted(seen) for hit in numbers(schemas[name], name)]
    assert not found, found
    assert {"AllocationRequest", "GoalRequest", "IncomeItem", "OpeningBalanceItem"} <= seen
