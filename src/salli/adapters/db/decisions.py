"""
Storage for principles and the decision journal (application/ports.py
`PrincipleRepository`, `DecisionRepository`).

Principles are preferences: edited (each edit counts the version up) and
archived, never deleted. The journal is append-only: `SQLDecisionRepository`
only ever adds rows (an entry, a note, a review) and reads them, and the
database refuses an UPDATE, DELETE or TRUNCATE on its tables (core_0017),
except a DELETE while erasing the user's whole account. Every query names
the owner, and a note or a review can only be added to the caller's own
entry (and a composite foreign key keeps their owner the entry's).
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from salli.adapters.db.models import (
    DecisionNoteORM,
    DecisionORM,
    DecisionReviewORM,
    PrincipleORM,
)
from salli.application.ports import DecisionRepository, PrincipleRepository

_PRINCIPLE_FIELDS = {
    "label": "label",
    "check": "expression",
    "account": "account_id",
    "note": "note",
}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _principle(row: PrincipleORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "label": row.label,
        "check": row.expression,
        "account": row.account_id,
        "note": row.note,
        "version": row.version,
        "author_kind": row.author_kind,
        "author_name": row.author_name,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "archived_at": row.archived_at,
    }


class SQLPrincipleRepository(PrincipleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _row(self, user_id: str, principle_id: str) -> PrincipleORM | None:
        return (
            await self._s.execute(
                select(PrincipleORM).where(
                    PrincipleORM.id == principle_id, PrincipleORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()

    async def list(self, user_id: str, include_archived: bool = False) -> list[dict[str, Any]]:
        stmt = select(PrincipleORM).where(PrincipleORM.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(PrincipleORM.archived_at.is_(None))
        stmt = stmt.order_by(PrincipleORM.created_at, PrincipleORM.id)
        return [_principle(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def get(self, user_id: str, principle_id: str) -> dict[str, Any] | None:
        row = await self._row(user_id, principle_id)
        return None if row is None else _principle(row)

    async def add(self, user_id: str, record: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        row = PrincipleORM(
            id=str(uuid.uuid4()),
            user_id=user_id,
            label=record["label"],
            expression=record["check"],
            account_id=record.get("account"),
            note=record.get("note"),
            version=1,
            author_kind=record.get("author_kind", "user"),
            author_name=record.get("author_name"),
            created_at=now,
            updated_at=now,
        )
        self._s.add(row)
        await self._s.flush()
        return _principle(row)

    async def update(
        self, user_id: str, principle_id: str, changes: dict[str, Any]
    ) -> dict[str, Any] | None:
        row = await self._row(user_id, principle_id)
        if row is None or row.archived_at is not None:
            return None
        for key, column in _PRINCIPLE_FIELDS.items():
            if key in changes:
                setattr(row, column, changes[key])
        row.version += 1
        row.updated_at = _now()
        await self._s.flush()
        return _principle(row)

    async def archive(self, user_id: str, principle_id: str) -> dict[str, Any] | None:
        row = await self._row(user_id, principle_id)
        if row is None:
            return None
        if row.archived_at is None:
            row.archived_at = row.updated_at = _now()
            await self._s.flush()
        return _principle(row)


def _entry(row: DecisionORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "question": row.question,
        "chosen": row.chosen,
        "currency": row.currency,
        "as_of": row.as_of,
        "review_on": row.review_on,
        "recorded_at": row.recorded_at,
        "content": row.content,
        "hash": row.hash,
    }


def _appended(row: DecisionNoteORM | DecisionReviewORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "content": row.content,
        "hash": row.hash,
        "created_at": row.created_at,
    }


class SQLDecisionRepository(DecisionRepository):
    """Append-only: `record`, `add_note` and `add_review` insert; nothing
    here updates or deletes."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _owned(self, user_id: str, decision_id: str) -> DecisionORM | None:
        return (
            await self._s.execute(
                select(DecisionORM).where(
                    DecisionORM.id == decision_id, DecisionORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()

    async def record(self, user_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        row = DecisionORM(
            id=entry["id"],
            user_id=user_id,
            question=entry["question"],
            chosen=entry["chosen"],
            currency=entry["currency"],
            as_of=entry["as_of"],
            review_on=entry["review_on"],
            recorded_at=entry["recorded_at"],
            content=entry["content"],
            hash=entry["hash"],
        )
        self._s.add(row)
        await self._s.flush()
        return _entry(row)

    async def _appendices(
        self, user_id: str, ids: list[str]
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
        notes: dict[str, list[dict[str, Any]]] = defaultdict(list)
        reviews: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if not ids:
            return notes, reviews
        for model, into in ((DecisionNoteORM, notes), (DecisionReviewORM, reviews)):
            stmt = (
                select(model)
                .where(model.user_id == user_id, model.decision_id.in_(ids))
                .order_by(model.created_at, model.id)
            )
            for row in (await self._s.execute(stmt)).scalars().all():
                into[row.decision_id].append(_appended(row))
        return notes, reviews

    async def get(self, user_id: str, decision_id: str) -> dict[str, Any] | None:
        row = await self._owned(user_id, decision_id)
        if row is None:
            return None
        notes, reviews = await self._appendices(user_id, [row.id])
        return {**_entry(row), "notes": notes[row.id], "reviews": reviews[row.id]}

    async def list_full(self, user_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(DecisionORM)
            .where(DecisionORM.user_id == user_id)
            .order_by(DecisionORM.recorded_at, DecisionORM.id)
        )
        rows = list((await self._s.execute(stmt)).scalars().all())
        notes, reviews = await self._appendices(user_id, [r.id for r in rows])
        return [{**_entry(r), "notes": notes[r.id], "reviews": reviews[r.id]} for r in rows]

    async def _summaries(self, user_id: str, rows: list[DecisionORM]) -> list[dict[str, Any]]:
        ids = [r.id for r in rows]
        counts: dict[str, dict[str, Any]] = defaultdict(dict)
        if ids:
            for model, key in ((DecisionNoteORM, "notes"), (DecisionReviewORM, "reviews")):
                stmt = (
                    select(model.decision_id, func.count(), func.max(model.created_at))
                    .where(model.user_id == user_id, model.decision_id.in_(ids))
                    .group_by(model.decision_id)
                )
                for decision_id, count, latest in (await self._s.execute(stmt)).all():
                    counts[decision_id][key] = count
                    if key == "reviews":
                        counts[decision_id]["last_reviewed_at"] = latest
        out: list[dict[str, Any]] = []
        for r in rows:
            found = counts.get(r.id, {})
            summary = {k: v for k, v in _entry(r).items() if k != "content"}
            out.append(
                {
                    **summary,
                    "notes": found.get("notes", 0),
                    "reviews": found.get("reviews", 0),
                    "last_reviewed_at": found.get("last_reviewed_at"),
                }
            )
        return out

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(DecisionORM)
            .where(DecisionORM.user_id == user_id)
            .order_by(DecisionORM.recorded_at.desc(), DecisionORM.id)
        )
        return await self._summaries(user_id, list((await self._s.execute(stmt)).scalars().all()))

    async def due(self, user_id: str, on: dt.date) -> list[dict[str, Any]]:
        reviewed = select(DecisionReviewORM.decision_id).where(DecisionReviewORM.user_id == user_id)
        stmt = (
            select(DecisionORM)
            .where(
                DecisionORM.user_id == user_id,
                DecisionORM.review_on <= on,
                DecisionORM.id.not_in(reviewed),
            )
            .order_by(DecisionORM.review_on, DecisionORM.recorded_at, DecisionORM.id)
        )
        return await self._summaries(user_id, list((await self._s.execute(stmt)).scalars().all()))

    async def add_note(
        self, user_id: str, decision_id: str, note: dict[str, Any]
    ) -> dict[str, Any] | None:
        if await self._owned(user_id, decision_id) is None:
            return None
        row = DecisionNoteORM(
            id=note["id"],
            decision_id=decision_id,
            user_id=user_id,
            content=note["content"],
            hash=note["hash"],
            created_at=note["created_at"],
        )
        self._s.add(row)
        await self._s.flush()
        return _appended(row)

    async def add_review(
        self, user_id: str, decision_id: str, review: dict[str, Any]
    ) -> dict[str, Any] | None:
        if await self._owned(user_id, decision_id) is None:
            return None
        row = DecisionReviewORM(
            id=review["id"],
            decision_id=decision_id,
            user_id=user_id,
            as_of=review["as_of"],
            content=review["content"],
            hash=review["hash"],
            created_at=review["created_at"],
        )
        self._s.add(row)
        await self._s.flush()
        return _appended(row)
