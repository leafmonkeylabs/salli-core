"""
Principles — `/v1/principles`: the user's own rules of thumb.

A principle (`salli.principle/1`, docs/decisions.md) is a label and a check
written in Salli's safe expression language over a fixed set of figures
(`GET /v1/principles/figures`): `emergency_months >= 6`,
`max_debt_rate_while_investing <= 0.07`, `account_lowest >= 2000` with the
principle naming the account. Principles are preferences: added, edited
(their version counts up) and archived, never deleted.

`POST /v1/principles/check` runs none to five options (`salli.scenario/1`
documents) on the user's baseline and says, for the baseline and each
option, which principles it keeps, breaks or can't tell, with the figures
each check read. Never a ranking; stores nothing.

A principle Salli can't store is a 422 whose `detail` lists each problem
with its path (`check`, `account`); an account that isn't the caller's is
404, the same as one that doesn't exist.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict, Field

from salli.domain.decisions.principles import MAX_CHECK, MAX_LABEL, MAX_NOTE
from salli.domain.scenarios.schema import Scenario
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/principles", tags=["principles"])

_NOT_FOUND = {404: {"description": "Not one of your principles, or not one of your accounts"}}

#: A figure's value: an amount, months or a rate as a decimal string, a count
#: of months as a whole number, true or false, or null when Salli can't give it.
FigureValue = str | int | bool | None


class PrincipleIn(BaseModel):
    """A principle to keep: what it is called and the check that says
    whether an option keeps it."""

    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, Field(min_length=1, max_length=MAX_LABEL)]
    #: True or false over the figures (`GET /v1/principles/figures`):
    #: "emergency_months >= 6".
    check: Annotated[str, Field(min_length=1, max_length=MAX_CHECK)]
    #: The cash account `account_lowest` reads, by id.
    account: str | None = None
    #: Why it matters, in your words.
    note: Annotated[str | None, Field(max_length=MAX_NOTE)] = None


class PrincipleChanges(BaseModel):
    """What to change; a field left out stays as it is, and a null account or
    note removes it."""

    model_config = ConfigDict(extra="forbid")

    label: Annotated[str | None, Field(min_length=1, max_length=MAX_LABEL)] = None
    check: Annotated[str | None, Field(min_length=1, max_length=MAX_CHECK)] = None
    account: str | None = None
    note: Annotated[str | None, Field(max_length=MAX_NOTE)] = None


class Principle(BaseModel):
    schema_: Literal["salli.principle/1"] = Field(alias="schema")
    id: str
    label: str
    check: str
    account: str | None
    note: str | None
    #: Counts up with each edit.
    version: int
    #: A content hash of the label, the check (in its canonical text) and the account.
    hash: str
    #: "agent" when the user's agent wrote it and the user confirmed it.
    author: Literal["user", "agent"]
    agent: str | None
    status: Literal["active", "archived"]
    created_at: str
    updated_at: str
    archived_at: str | None


class PrincipleList(BaseModel):
    principles: list[Principle]


class DecisionFigure(BaseModel):
    """A figure a check may read."""

    name: str
    kind: Literal["amount", "months", "rate", "count", "boolean"]
    unit: str
    #: "nominal": each day's or month's own money; "real": today's money.
    terms: Literal["nominal", "real", "none"]
    group: Literal["cash", "resilience", "monthly", "debts", "fi", "tax"]
    description: str


class DecisionFigures(BaseModel):
    figures: list[DecisionFigure]


class PrincipleRef(BaseModel):
    """A principle as it stood when it was checked."""

    id: str
    label: str
    check: str
    account: str | None
    version: int
    hash: str


class PrincipleCheckResult(BaseModel):
    """Whether an option keeps a principle, breaks it, or can't tell (a
    figure it reads is missing, or the arithmetic failed); why; and the
    figures the check read."""

    principle_id: str
    label: str
    status: Literal["keeps", "breaks", "unknown"]
    reason: str
    figures: dict[str, FigureValue]


class CheckedFigures(BaseModel):
    #: Every figure (`GET /v1/principles/figures`), null where Salli can't give it.
    figures: dict[str, FigureValue]
    #: Why each null figure is missing.
    unavailable: dict[str, str]
    results: list[PrincipleCheckResult]


class CheckedOption(CheckedFigures):
    label: str
    #: The scenario's content hash, as `POST /v1/scenarios/run` gives it.
    scenario_hash: str


class PrinciplesCheck(BaseModel):
    """Your principles against the baseline and each option. Not a ranking."""

    as_of: str
    currency: str
    principles: list[PrincipleRef]
    baseline: CheckedFigures
    options: list[CheckedOption]
    placeholders: list[str]
    #: The newest ledger entry on or before the as-of date.
    data_as_of: str | None


class CheckOptions(BaseModel):
    """None to five scenarios, with one as-of date between them."""

    options: Annotated[list[Scenario], Field(max_length=5)] = Field(default_factory=list[Scenario])


@router.get("")
async def list_principles(
    user_id: CurrentUser,
    svc: AppServices,
    include_archived: Annotated[bool, Query()] = False,
) -> PrincipleList:
    """Your principles, oldest first: those in use, or every one with
    include_archived."""
    return PrincipleList.model_validate(await svc.principles.list(user_id, include_archived))


@router.post("", status_code=status.HTTP_201_CREATED, responses=_NOT_FOUND)  # type: ignore[arg-type]
async def add_principle(body: PrincipleIn, user_id: CurrentUser, svc: AppServices) -> Principle:
    """Keep a principle. Its check is validated first: a figure that doesn't
    exist, a check that isn't true or false, or account_lowest without an
    account is a 422 with each problem's path."""
    return Principle.model_validate(await svc.principles.add(user_id, body.model_dump()))


@router.get("/figures")
async def principle_figures(svc: AppServices) -> DecisionFigures:
    """The figures a check may read, each with its unit and whether it is in
    today's money (real) or each day's own (nominal)."""
    return DecisionFigures.model_validate(svc.principles.figures())


@router.post("/check", responses=_NOT_FOUND)  # type: ignore[arg-type]
async def check_principles(
    body: CheckOptions, user_id: CurrentUser, svc: AppServices
) -> PrinciplesCheck:
    """Check your principles against your baseline and each option: which
    each keeps, breaks or can't tell, with the figures each check read.
    Never a ranking. Stores nothing."""
    return PrinciplesCheck.model_validate(await svc.principles.check(user_id, body.options))


@router.patch("/{principle_id}", responses=_NOT_FOUND)  # type: ignore[arg-type]
async def update_principle(
    principle_id: str, body: PrincipleChanges, user_id: CurrentUser, svc: AppServices
) -> Principle:
    """Edit a principle in use; its version counts up. Decisions already
    recorded keep the principle as it stood."""
    changes: dict[str, Any] = body.model_dump(include=body.model_fields_set)
    return Principle.model_validate(await svc.principles.update(user_id, principle_id, changes))


@router.post("/{principle_id}/archive", responses=_NOT_FOUND)  # type: ignore[arg-type]
async def archive_principle(principle_id: str, user_id: CurrentUser, svc: AppServices) -> Principle:
    """Stop checking against a principle. It stays, archived: nothing is deleted."""
    return Principle.model_validate(await svc.principles.archive(user_id, principle_id))
