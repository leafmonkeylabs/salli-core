"""
Tags — a second classification axis, orthogonal to the chart of accounts.

The account tree answers "which ledger account did this hit". It cannot also
answer "was this essential" without duplicating the whole tree beneath every
answer, so classification lives on its own dimension.

Two axes exist:
  - `category` — what the money was for (groceries, rent, transport). Open set,
    created on demand as people tag things.
  - `need` — how necessary it was, i.e. the 50/30/20 split. Closed, seeded set;
    reports reference these by slug, so they can be renamed but not removed.

A posting carries at most one tag per axis, which is what lets a breakdown along
any single axis sum to the total without double counting.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from salli.domain.accounting.models import TagKind
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/tags", tags=["tags"])


class Tag(BaseModel):
    id: str
    slug: str
    name: str
    kind: TagKind
    #: A display colour; empty when none was chosen.
    color: str
    #: Seeded by Salli (the `need` axis): can be renamed, not deleted.
    is_system: bool


class TagList(BaseModel):
    tags: list[Tag]


@router.get("/")
async def list_tags(
    user_id: CurrentUser,
    svc: AppServices,
    kind: Literal["category", "need"] | None = Query(default=None),
) -> TagList:
    tags = await svc.ledger.list_tags(user_id, kind)
    return TagList(
        tags=[
            Tag(
                id=t.id,
                slug=t.slug,
                name=t.name,
                kind=t.kind,
                color=t.color,
                is_system=t.is_system,
            )
            for t in tags
        ]
    )
