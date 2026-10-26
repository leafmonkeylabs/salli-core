"""
A person's stored rows, table by table, as the export carries them
(`rows`) and a restore writes them back (domain/export/restore.py).

A value is stored text, an integer, a boolean or JSON as it is; a decimal,
a day or a time is its text, read back by its column's type. Nothing here
decides what a restore takes: the tables, and how their rows move to the
person restoring, are the domain's.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Numeric, Table, delete, exists, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from salli.adapters.db.models import Base
from salli.domain.export import restore

_TABLES = Base.metadata.tables

#: Rows reached through another table, not by a `user_id` of their own.
_THROUGH = {
    "postings": ("entry_id", "journal_entries"),
    "posting_tags": ("posting_id", "postings"),
    "parsed_transactions": ("statement_id", "statements"),
}

#: What a person's books may hold and still take a restore: the starter
#: chart and the seeded tags (replaced: nothing points at them without
#: entries), the digest's preferences (replaced), and rows that come only
#: with something that blocks it anyway.
#: Rows that point at earlier ones of the same table go after them.
_ORDER = {"journal_entries": "seq", "tax_returns": "version"}

_REPLACED = {"accounts", "tags", "notification_preferences", *_THROUGH}


def _owned(table: Table, user_id: str) -> ColumnElement[bool]:
    if table.name == "user_profiles":
        return table.c.id == user_id
    if table.name in _THROUGH:
        column, parent = _THROUGH[table.name]
        return table.c[column].in_(
            select(_TABLES[parent].c.id).where(_owned(_TABLES[parent], user_id))
        )
    return table.c.user_id == user_id


def _encode(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def _decode(table: Table, row: Mapping[str, Any]) -> dict[str, Any]:
    """A row as the table takes it: only its own columns, each decimal, day
    and time read back from its text."""
    out: dict[str, Any] = {}
    for name, value in row.items():
        if name not in table.c:
            continue
        kind = table.c[name].type
        if value is not None and isinstance(kind, DateTime):
            value = datetime.fromisoformat(value)
        elif value is not None and isinstance(kind, Date):
            value = date.fromisoformat(value)
        elif value is not None and isinstance(kind, Numeric):
            value = Decimal(str(value))
        out[name] = value
    return out


async def stored_rows(session: AsyncSession, user_id: str) -> dict[str, list[dict[str, Any]]]:
    """Every row a restore takes, and the profile and audit rows, by table."""
    rows: dict[str, list[dict[str, Any]]] = {}
    for name in (*restore.TABLES, "user_profiles", "audit_logs"):
        table = _TABLES[name]
        order = [table.c.seq] if "seq" in table.c else list(table.primary_key.columns)
        result = await session.execute(select(table).where(_owned(table, user_id)).order_by(*order))
        rows[name] = [{k: _encode(v) for k, v in r.items()} for r in result.mappings()]
    return rows


async def occupied(session: AsyncSession, user_id: str) -> list[str]:
    """What in the person's books stops a restore: each table holding a row
    of theirs (an agent's memories aside, which a restore keeps or
    replaces), and a lock date."""
    found: list[str] = []
    for name in restore.TABLES:
        if name in _REPLACED:
            continue
        table = _TABLES[name]
        where = _owned(table, user_id)
        if name == "agent_documents":
            where = where & (table.c.namespace != "memories")
        if (await session.execute(select(exists().where(where)))).scalar():
            found.append(name)
    profiles = _TABLES["user_profiles"]
    locked = await session.execute(select(profiles.c.lock_date).where(profiles.c.id == user_id))
    if locked.scalar() is not None:
        found.append("lock_date")
    return found


def _parents_first(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    placed: set[str] = set()
    ordered: list[dict[str, Any]] = []
    waiting = list(rows)
    while waiting:
        ready = [r for r in waiting if r.get("parent_id") in (None, *placed)]
        if not ready:  # a parent the export doesn't hold: the insert says so
            ready = waiting
        ordered += ready
        placed |= {r["id"] for r in ready}
        waiting = [r for r in waiting if r not in ready]
    return ordered


def strays(rows: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    """Each row that points at another the export doesn't hold (by a
    foreign key to a table it carries): a restore writes the person's own
    books only, and a reference elsewhere would reach past them."""
    ids = {name: {r["id"] for r in rows.get(name, []) if "id" in r} for name in restore.TABLES}
    found: list[str] = []
    for name in restore.TABLES:
        for key in _TABLES[name].foreign_keys:
            target, column = key.column.table.name, key.parent.name
            if target not in ids or key.column.name != "id":
                continue
            found += [
                f"{name}.{column}"
                for r in rows.get(name, [])
                if r.get(column) is not None and r[column] not in ids[target]
            ][:1]
    return found


async def write_rows(
    session: AsyncSession,
    user_id: str,
    rows: Mapping[str, list[dict[str, Any]]],
    profile: Mapping[str, Any],
) -> dict[str, int]:
    """Writes the rows (already the person's) into their books, which hold
    nothing `occupied` names: the starter chart, the seeded tags, the
    digest's preferences and any memory the export has too are replaced,
    and the profile takes the export's, the lock date last, once every entry
    it closes is in."""
    for name in ("tags", "accounts", "notification_preferences"):
        await session.execute(delete(_TABLES[name]).where(_owned(_TABLES[name], user_id)))
    documents = _TABLES["agent_documents"]
    memories = [
        r["slug"] for r in rows.get("agent_documents", []) if r.get("namespace") == "memories"
    ]
    if memories:
        await session.execute(
            delete(documents).where(
                _owned(documents, user_id),
                documents.c.namespace == "memories",
                documents.c.slug.in_(memories),
            )
        )

    profiles = _TABLES["user_profiles"]
    settings = {
        k: v
        for k, v in _decode(profiles, profile).items()
        if k not in restore.PROFILE_KEPT and k != "lock_date"
    }
    await session.execute(
        pg_insert(profiles)
        .values(id=user_id, **settings)
        .on_conflict_do_update(index_elements=[profiles.c.id], set_=settings)
    )

    counts: dict[str, int] = {}
    for name in restore.TABLES:
        table = _TABLES[name]
        given = list(rows.get(name, []))
        if name == "accounts":
            given = _parents_first(given)
        if name in _ORDER:
            given.sort(key=lambda r: r[_ORDER[name]])
        if name == "tax_rule_sets":
            # Its active version points back at it: set once the versions are in.
            given = [{**r, "active_version_id": None} for r in given]
        if given:
            await session.execute(insert(table), [_decode(table, r) for r in given])
        counts[name] = len(given)
    sets = _TABLES["tax_rule_sets"]
    for r in rows.get("tax_rule_sets", []):
        if r.get("active_version_id"):
            await session.execute(
                update(sets)
                .where(sets.c.id == r["id"])
                .values(
                    active_version_id=r["active_version_id"],
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
            )
    if profile.get("lock_date"):
        await session.execute(
            update(profiles)
            .where(profiles.c.id == user_id)
            .values(lock_date=date.fromisoformat(profile["lock_date"]))
        )
    return counts
