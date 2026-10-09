"""
Categorisation rules — `/v1/rules`.

"When a transaction looks like this, it goes there": deterministic rules that
book imported transactions before any model is asked, so the same payee is
booked the same way every time. `/rules/test` shows what a rule would decide
among what is already booked; `/rules/suggestions` offers the rules the user's
own bookkeeping implies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from salli.domain.rules.engine import InvalidRule
from salli.interfaces.api.contract import Amount, CurrencyCode, Ref
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleCondition(BaseModel):
    field: Literal["description", "amount", "direction", "currency"]
    operator: Literal[
        "contains",
        "not_contains",
        "equals",
        "starts_with",
        "ends_with",
        "matches",
        "gt",
        "gte",
        "lt",
        "lte",
        "between",
    ]
    #: Text, a pattern (`matches`), an amount as a decimal string, "in"/"out",
    #: or an ISO 4217 code — by field.
    value: str
    #: The upper bound, for `between`.
    value2: str | None = None


class RuleActions(BaseModel):
    #: Where the other side of the entry goes.
    account_id: str | None = None
    category: str | None = None
    need: Literal["essential", "discretionary", "savings"] | None = None
    #: Replaces the bank's description.
    description: str | None = None


class RuleDraft(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    conditions: list[RuleCondition] = Field(min_length=1)
    actions: RuleActions
    #: Lower runs first; the first rule that matches decides.
    priority: int = 100
    #: All conditions (AND) or any one of them (OR).
    match_all: bool = True
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    conditions: list[RuleCondition] | None = None
    actions: RuleActions | None = None
    priority: int | None = None
    match_all: bool | None = None
    enabled: bool | None = None


class CategorizationRule(RuleDraft):
    id: str
    #: How many transactions it has decided.
    hits: int
    last_hit_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RuleMatch(BaseModel):
    entry_id: str
    entry_date: str
    description: str
    amount: Amount
    currency: CurrencyCode
    direction: Literal["in", "out"]
    #: Where it was booked: compare with the rule's `account_id`.
    account_id: str


class RuleTestResult(BaseModel):
    total: int
    #: Of those, how many were booked to the rule's account already.
    agreeing: int
    matches: list[RuleMatch]


class RuleSuggestion(RuleDraft):
    #: How many booked transactions it would have decided...
    support: int
    #: ...and how many of those went to its account.
    agreement: int
    examples: list[str]


def _invalid(exc: InvalidRule) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


@router.get("")
async def list_rules(user_id: CurrentUser, svc: AppServices) -> list[CategorizationRule]:
    return [CategorizationRule.model_validate(r) for r in await svc.rules.list(user_id)]


@router.post("", status_code=201)
async def create_rule(body: RuleDraft, user_id: CurrentUser, svc: AppServices) -> Ref:
    try:
        return Ref(id=await svc.rules.create(user_id, body.model_dump()))
    except InvalidRule as exc:
        raise _invalid(exc) from exc


@router.post("/test")
async def test_rule(body: RuleDraft, user_id: CurrentUser, svc: AppServices) -> RuleTestResult:
    try:
        return RuleTestResult.model_validate(await svc.rules.test(user_id, body.model_dump()))
    except InvalidRule as exc:
        raise _invalid(exc) from exc


@router.get("/suggestions")
async def rule_suggestions(user_id: CurrentUser, svc: AppServices) -> list[RuleSuggestion]:
    return [RuleSuggestion.model_validate(s) for s in await svc.rules.suggestions(user_id)]


@router.get("/{rule_id}")
async def get_rule(rule_id: str, user_id: CurrentUser, svc: AppServices) -> CategorizationRule:
    rule = await svc.rules.get(user_id, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such rule")
    return CategorizationRule.model_validate(rule)


@router.patch("/{rule_id}")
async def update_rule(
    rule_id: str, body: RuleUpdate, user_id: CurrentUser, svc: AppServices
) -> Ref:
    try:
        found = await svc.rules.update(user_id, rule_id, body.model_dump(exclude_none=True))
    except InvalidRule as exc:
        raise _invalid(exc) from exc
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such rule")
    return Ref(id=rule_id)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    if not await svc.rules.delete(user_id, rule_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such rule")
