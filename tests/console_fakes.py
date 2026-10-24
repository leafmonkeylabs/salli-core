"""
In-memory repositories for the console's books, tax and settings fixtures
(tests/console_fixtures.py, C4): the slices of the SQL repositories that the
statement import, the categorisation rules, the tax rule sets and their
computations, personal access tokens, stored model keys and bank
connections use, kept as the SQL ones keep them (adapters/db) and stamped
with a fixed clock, so what the real services answer over them is the same
each time it is written.

Each answers for one user as the SQL repository does: every query names
its owner.
"""

from __future__ import annotations

import copy
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from salli.domain.parsing.models import ParsedTransaction, RawRow

Clock = Callable[[], datetime]


def _fixed(at: datetime) -> Clock:
    return lambda: at


# ── Categorisation rules (SQLRuleRepository) ────────────────────────────────


class FakeRules:
    def __init__(self, now: Clock) -> None:
        self.now = now
        self.rows: dict[str, dict[str, Any]] = {}

    def _view(self, row: dict[str, Any]) -> dict[str, Any]:
        return {k: copy.deepcopy(v) for k, v in row.items() if k != "user_id"}

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        mine = [r for r in self.rows.values() if r["user_id"] == user_id]
        return [self._view(r) for r in sorted(mine, key=lambda r: (r["priority"], r["name"]))]

    async def get(self, user_id: str, rule_id: str) -> dict[str, Any] | None:
        row = self.rows.get(rule_id)
        return self._view(row) if row is not None and row["user_id"] == user_id else None

    async def save(self, user_id: str, rule: dict[str, Any]) -> str:
        now = self.now()
        rule_id = str(uuid.uuid4())
        self.rows[rule_id] = {
            "id": rule_id,
            "user_id": user_id,
            "name": rule["name"],
            "priority": rule["priority"],
            "match_all": rule["match_all"],
            "conditions": copy.deepcopy(rule["conditions"]),
            "actions": copy.deepcopy(rule["actions"]),
            "enabled": rule["enabled"],
            "hits": 0,
            "last_hit_at": None,
            "created_at": now,
            "updated_at": now,
        }
        return rule_id

    async def update(self, user_id: str, rule_id: str, fields: dict[str, Any]) -> bool:
        row = self.rows.get(rule_id)
        if row is None or row["user_id"] != user_id:
            return False
        for key in ("name", "priority", "match_all", "conditions", "actions", "enabled"):
            if key in fields:
                row[key] = copy.deepcopy(fields[key])
        row["updated_at"] = self.now()
        return True

    async def delete(self, user_id: str, rule_id: str) -> bool:
        row = self.rows.get(rule_id)
        if row is None or row["user_id"] != user_id:
            return False
        del self.rows[rule_id]
        return True

    async def record_hits(self, user_id: str, counts: dict[str, int], at: datetime) -> None:
        for rule_id, count in counts.items():
            row = self.rows.get(rule_id)
            if row is not None and row["user_id"] == user_id:
                row["hits"] += count
                row["last_hit_at"] = at


# ── Statements and their transactions (SQLStatementRepository) ──────────────

#: Waiting for no one: posted, discarded or an exact duplicate.
_SETTLED = ("posted", "discarded", "exact_duplicate")


class FakeStatements:
    """Statements and their parsed transactions, each row kept as the SQL
    repository keeps it (its extracted JSON) and read back the same way."""

    def __init__(self, now: Clock) -> None:
        self.now = now
        self.statements: dict[str, dict[str, Any]] = {}
        #: Rows in the order they were saved.
        self.rows: list[dict[str, Any]] = []

    @staticmethod
    def _pending(row: dict[str, Any]) -> bool:
        return row["posted_entry_id"] is None and row["dedup_status"] not in (
            "discarded",
            "exact_duplicate",
        )

    def _parsed(self, row: dict[str, Any]) -> ParsedTransaction:
        j = row["json"]
        statement = self.statements[row["statement_id"]]
        return ParsedTransaction(
            raw=RawRow(
                date=j["date"],
                description=j["description"],
                amount=j["amount"],
                credit_flag=j["credit_flag"],
                bank_ref=j.get("bank_ref", ""),
                currency=j["currency"],
                ref_kind=j.get("ref_kind", "id"),
                ref_source=j.get("ref_source", ""),
                source_account=j.get("source_account", ""),
            ),
            debit_account_id=j.get("debit_account_id", ""),
            credit_account_id=j.get("credit_account_id", ""),
            category=j.get("category", ""),
            need=j.get("need", ""),
            description=j.get("booking_description", ""),
            rule_id=j.get("rule_id", ""),
            duplicate_of=j.get("duplicate_of", ""),
            confidence=row["confidence"],
            dedup_key=row["dedup_key"],
            dedup_status=row["dedup_status"],
            id=row["id"],
            statement_id=row["statement_id"],
            account_id=statement["account_id"] or "",
        )

    def _mine(self, user_id: str) -> list[dict[str, Any]]:
        return [r for r in self.rows if self.statements[r["statement_id"]]["user_id"] == user_id]

    def _view(self, statement: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": statement["id"],
            "bank": statement["bank"],
            "account_id": statement["account_id"],
            "period_start": statement["period_start"],
            "period_end": statement["period_end"],
            "status": statement["status"],
            "created_at": statement["created_at"].isoformat(),
        }

    async def list_statements(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        mine = [s for s in self.statements.values() if s["user_id"] == user_id]
        mine.sort(key=lambda s: s["created_at"], reverse=True)
        return [self._view(s) for s in mine[:limit]]

    async def save_statement(
        self,
        user_id: str,
        statement_id: str,
        bank: str,
        period_start: str,
        period_end: str,
        transactions: list[Any],
        storage_key: str = "",
        account_id: str | None = None,
        kind: str = "import",
    ) -> None:
        self.statements[statement_id] = {
            "id": statement_id,
            "user_id": user_id,
            "bank": (bank or "")[:100],
            "account_id": account_id,
            "kind": kind,
            "period_start": period_start,
            "period_end": period_end,
            "storage_key": storage_key,
            "status": (
                "pending"
                if any(t.dedup_status not in _SETTLED for t in transactions)
                else "reviewed"
            ),
            "created_at": self.now(),
        }
        self._add(statement_id, account_id, transactions)

    async def open_drafts(self, user_id: str, account_id: str) -> str | None:
        batches = [
            s
            for s in self.statements.values()
            if s["user_id"] == user_id
            and s["account_id"] == account_id
            and s.get("kind") == "drafts"
            and any(r["statement_id"] == s["id"] and self._pending(r) for r in self.rows)
        ]
        batches.sort(key=lambda s: s["created_at"], reverse=True)
        return batches[0]["id"] if batches else None

    async def add_rows(
        self,
        user_id: str,
        statement_id: str,
        transactions: list[Any],
        *,
        period_start: str,
        period_end: str,
    ) -> None:
        statement = self.statements[statement_id]
        assert statement["user_id"] == user_id
        statement["period_start"] = min(filter(None, (statement["period_start"], period_start)))
        statement["period_end"] = max(filter(None, (statement["period_end"], period_end)))
        self._add(statement_id, statement["account_id"], transactions)
        if any(t.dedup_status not in _SETTLED for t in transactions):
            statement["status"] = "pending"

    def _add(self, statement_id: str, account_id: str | None, transactions: list[Any]) -> None:
        for txn in transactions:
            raw = txn.raw
            row_id = str(uuid.uuid4())
            self.rows.append(
                {
                    "id": row_id,
                    "statement_id": statement_id,
                    "json": {
                        "date": raw.date,
                        "description": raw.description,
                        "amount": raw.amount,
                        "credit_flag": raw.credit_flag,
                        "bank_ref": raw.bank_ref,
                        "debit_account_id": txn.debit_account_id,
                        "credit_account_id": txn.credit_account_id,
                        "category": txn.category,
                        "currency": raw.currency,
                        "need": txn.need,
                        "booking_description": txn.description,
                        "rule_id": txn.rule_id,
                        "duplicate_of": txn.duplicate_of,
                        "ref_kind": raw.ref_kind,
                        "ref_source": raw.ref_source,
                        "source_account": raw.source_account,
                    },
                    "confidence": txn.confidence,
                    "dedup_key": txn.dedup_key or "",
                    "dedup_status": txn.dedup_status,
                    "posted_entry_id": None,
                }
            )
            txn.id, txn.statement_id, txn.account_id = row_id, statement_id, account_id or ""

    async def imported_between(
        self,
        user_id: str,
        from_date: str,
        to_date: str,
        *,
        account_id: str | None = None,
        excluding_statement: str | None = None,
    ) -> list[Any]:
        found = []
        for row in self._mine(user_id):
            statement = self.statements[row["statement_id"]]
            if not from_date <= row["json"]["date"] <= to_date:
                continue
            if row["dedup_status"] == "exact_duplicate":
                continue
            if account_id is not None and statement["account_id"] not in (account_id, None):
                continue
            if (
                excluding_statement is not None
                and row["statement_id"] == excluding_statement
                and row["posted_entry_id"] is None
            ):
                continue
            found.append(self._parsed(row))
        return found

    async def get_all_pending(self, user_id: str) -> list[Any]:
        return [self._parsed(r) for r in self._mine(user_id) if self._pending(r)]

    async def get_pending(self, user_id: str, statement_id: str) -> list[Any]:
        return [
            self._parsed(r)
            for r in self._mine(user_id)
            if r["statement_id"] == statement_id and self._pending(r)
        ]

    async def discard(self, user_id: str, statement_id: str, ids: list[str] | None = None) -> int:
        rows = [
            r
            for r in self._mine(user_id)
            if r["statement_id"] == statement_id
            and self._pending(r)
            and (ids is None or r["id"] in ids)
        ]
        for row in rows:
            row["dedup_status"] = "discarded"
        self._settle(statement_id)
        return len(rows)

    def _settle(self, statement_id: str) -> None:
        waiting = any(self._pending(r) for r in self.rows if r["statement_id"] == statement_id)
        if statement_id in self.statements:
            self.statements[statement_id]["status"] = "pending" if waiting else "reviewed"

    async def get_by_ids(
        self, user_id: str, ids: list[str], *, for_update: bool = False
    ) -> list[Any]:
        return [self._parsed(r) for r in self._mine(user_id) if r["id"] in ids]

    async def set_choice(self, user_id: str, transaction_id: str, fields: dict[str, Any]) -> None:
        for row in self._mine(user_id):
            if row["id"] == transaction_id:
                row["json"] = {**row["json"], **fields}
                row["confidence"] = 1.0

    async def mark_posted(self, transaction_id: str, entry_id: str) -> None:
        for row in self.rows:
            if row["id"] == transaction_id:
                row["posted_entry_id"] = entry_id
                row["dedup_status"] = "posted"
                self._settle(row["statement_id"])

    async def get_statement(self, user_id: str, statement_id: str) -> dict[str, Any] | None:
        statement = self.statements.get(statement_id)
        if statement is None or statement["user_id"] != user_id:
            return None
        return {**self._view(statement), "storage_key": statement["storage_key"]}


class FakeBankConnections:
    """Bank connections as the SQL repository lists them."""

    def __init__(self) -> None:
        self.connections: list[dict[str, Any]] = []

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        return copy.deepcopy([c for c in self.connections if c.get("user_id", user_id) == user_id])


class ClosedKeyRing:
    """An instance with no encryption key: nothing sealed can be stored."""

    available = False


# ── Tax rule sets and computations (adapters/db/tax_rule_sets.py, …) ────────

_LIFECYCLE_FIELDS = frozenset(
    {"status", "validation", "proposed_at", "activated_at", "superseded_at"}
)


class FakeTaxRuleSets:
    def __init__(self, now: Clock) -> None:
        self.now = now
        self.sets: dict[str, dict[str, Any]] = {}
        self.versions: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _version(row: dict[str, Any], *, content: bool) -> dict[str, Any]:
        out = {
            k: row[k]
            for k in (
                "id",
                "rule_set_id",
                "version",
                "content_hash",
                "status",
                "author_kind",
                "author_name",
                "change_note",
                "created_at",
                "proposed_at",
                "activated_at",
                "superseded_at",
            )
        }
        if content:
            out["content"] = copy.deepcopy(row["content"])
            out["validation"] = copy.deepcopy(row["validation"])
        return out

    def _of(self, user_id: str, rule_set_id: str) -> list[dict[str, Any]]:
        return sorted(
            (
                v
                for v in self.versions.values()
                if v["user_id"] == user_id and v["rule_set_id"] == rule_set_id
            ),
            key=lambda v: v["version"],
        )

    def _set(self, row: dict[str, Any], versions: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            **{k: row[k] for k in ("id", "country", "region", "year_label", "name")},
            "active_version_id": row["active_version_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "versions": [self._version(v, content=False) for v in versions],
        }

    async def list_sets(self, user_id: str) -> list[dict[str, Any]]:
        mine = [s for s in self.sets.values() if s["user_id"] == user_id]
        mine.sort(key=lambda s: (s["country"], s["year_label"], s["created_at"]))
        return [self._set(s, self._of(user_id, s["id"])) for s in mine]

    async def get_set(
        self, user_id: str, rule_set_id: str, *, lock: bool = False
    ) -> dict[str, Any] | None:
        row = self.sets.get(rule_set_id)
        if row is None or row["user_id"] != user_id:
            return None
        return self._set(row, self._of(user_id, rule_set_id))

    async def find_set(
        self, user_id: str, country: str, region: str | None, year_label: str, *, lock: bool = False
    ) -> dict[str, Any] | None:
        for row in self.sets.values():
            if (row["user_id"], row["country"], row["region"] or "", row["year_label"]) == (
                user_id,
                country,
                region or "",
                year_label,
            ):
                return self._set(row, self._of(user_id, row["id"]))
        return None

    async def create_set(
        self, user_id: str, country: str, region: str | None, year_label: str, name: str
    ) -> dict[str, Any]:
        from salli.application.ports import RuleSetExists

        existing = await self.find_set(user_id, country, region, year_label)
        if existing is not None:
            raise RuleSetExists(existing["id"])
        now = self.now()
        row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "country": country,
            "region": region,
            "year_label": year_label,
            "name": name,
            "active_version_id": None,
            "created_at": now,
            "updated_at": now,
        }
        self.sets[row["id"]] = row
        return self._set(row, [])

    async def get_version(self, user_id: str, version_id: str) -> dict[str, Any] | None:
        row = self.versions.get(version_id)
        if row is None or row["user_id"] != user_id:
            return None
        return self._version(row, content=True)

    async def add_version(
        self, user_id: str, rule_set_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        latest = max((v["version"] for v in self._of(user_id, rule_set_id)), default=0)
        row = {
            "id": str(uuid.uuid4()),
            "rule_set_id": rule_set_id,
            "user_id": user_id,
            "version": latest + 1,
            "content": copy.deepcopy(fields["content"]),
            "content_hash": fields.get("content_hash"),
            "status": fields["status"],
            "validation": copy.deepcopy(fields["validation"]),
            "author_kind": fields["author_kind"],
            "author_name": fields.get("author_name"),
            "change_note": fields.get("change_note"),
            "created_at": self.now(),
            "proposed_at": None,
            "activated_at": None,
            "superseded_at": None,
        }
        self.versions[row["id"]] = row
        self._touch(user_id, rule_set_id)
        return self._version(row, content=True)

    async def update_version(self, user_id: str, version_id: str, fields: dict[str, Any]) -> bool:
        unknown = set(fields) - _LIFECYCLE_FIELDS
        if unknown:
            raise ValueError(f"A version's {', '.join(sorted(unknown))} cannot be changed")
        row = self.versions.get(version_id)
        if row is None or row["user_id"] != user_id:
            return False
        row.update(copy.deepcopy(fields))
        self._touch(user_id, row["rule_set_id"])
        return True

    async def set_active(self, user_id: str, rule_set_id: str, version_id: str | None) -> None:
        row = self.sets.get(rule_set_id)
        if row is not None and row["user_id"] == user_id:
            row["active_version_id"] = version_id
            row["updated_at"] = self.now()

    def _touch(self, user_id: str, rule_set_id: str) -> None:
        row = self.sets.get(rule_set_id)
        if row is not None and row["user_id"] == user_id:
            row["updated_at"] = self.now()

    def _live(self, user_id: str) -> list[dict[str, Any]]:
        return [
            v
            for v in self.versions.values()
            if v["user_id"] == user_id
            and v["content_hash"] is not None
            and v["status"] != "superseded"
        ]

    async def declared_roles(self, user_id: str) -> set[str]:
        return {r["key"] for v in self._live(user_id) for r in v["content"].get("roles", [])}

    async def declared_role_kinds(self, user_id: str) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for v in self._live(user_id):
            for role in v["content"].get("roles", []):
                out.setdefault(role["key"], set()).add(role["kind"])
        return out

    async def active_versions(self, user_id: str) -> list[dict[str, Any]]:
        mine = [s for s in self.sets.values() if s["user_id"] == user_id and s["active_version_id"]]
        mine.sort(key=lambda s: (s["country"], s["year_label"], s["region"] or ""))
        return [
            {
                **self._set(s, []),
                "version": self._version(self.versions[s["active_version_id"]], content=True),
            }
            for s in mine
        ]


class FakeTaxComputations:
    _FIELDS = (
        "country",
        "region",
        "year",
        "rule_set_version_id",
        "content_hash",
        "currency",
        "net_minor",
        "tax_payable_minor",
        "refund_due_minor",
        "lines",
        "inputs",
        "warnings",
    )

    def __init__(self, now: Clock, rule_sets: FakeTaxRuleSets) -> None:
        self.now = now
        self.rule_sets = rule_sets
        self.rows: list[dict[str, Any]] = []

    def _view(self, row: dict[str, Any]) -> dict[str, Any]:
        version = self.rule_sets.versions[row["rule_set_version_id"]]
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "country": row["country"],
            "region": row["region"],
            "year": row["year"],
            "rule_set_id": version["rule_set_id"],
            "rule_set_version_id": row["rule_set_version_id"],
            "version": version["version"],
            **{k: copy.deepcopy(row[k]) for k in self._FIELDS[4:]},
            "created_at": row["created_at"],
        }

    async def save(self, user_id: str, record: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            **{f: copy.deepcopy(record[f]) for f in self._FIELDS},
            "created_at": self.now(),
        }
        self.rows.append(row)
        return self._view(row)

    def _mine(self, user_id: str) -> list[dict[str, Any]]:
        # Newest first, as the SQL repository orders them.
        return [r for r in reversed(self.rows) if r["user_id"] == user_id]

    async def get(self, user_id: str, computation_id: str) -> dict[str, Any] | None:
        return next((self._view(r) for r in self._mine(user_id) if r["id"] == computation_id), None)

    async def get_latest(
        self, user_id: str, country: str, region: str | None, year: str
    ) -> dict[str, Any] | None:
        for row in self._mine(user_id):
            if (row["country"], row["region"], row["year"]) == (country, region, year):
                return self._view(row)
        return None

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return [self._view(r) for r in self._mine(user_id)]


class FakeAuditLog:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, dict[str, Any], str]] = []

    async def log(
        self,
        user_id: str,
        action: str,
        params: dict[str, Any],
        decision: str,
        client_id: str | None = None,
    ) -> str:
        self.rows.append((user_id, action, params, decision))
        return str(len(self.rows))


# ── Personal access tokens and stored model keys ────────────────────────────


class FakeTokens:
    """SQLPersonalAccessTokenRepository: only a token's hash is kept."""

    def __init__(self, now: Clock) -> None:
        self.now = now
        self.rows: list[dict[str, Any]] = []

    @staticmethod
    def _view(row: dict[str, Any]) -> dict[str, Any]:
        return {
            k: row[k]
            for k in (
                "id",
                "user_id",
                "name",
                "prefix",
                "permissions",
                "expires_at",
                "last_used_at",
                "created_at",
            )
        }

    async def create(
        self,
        user_id: str,
        name: str,
        token_hash: str,
        prefix: str,
        expires_at: datetime | None,
        permissions: list[str],
    ) -> dict[str, Any]:
        row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "name": name,
            "token_hash": token_hash,
            "prefix": prefix,
            "permissions": sorted(set(permissions)),
            "expires_at": expires_at,
            "last_used_at": None,
            "created_at": self.now(),
            "revoked": False,
        }
        self.rows.append(row)
        return self._view(row)

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        mine = [r for r in self.rows if r["user_id"] == user_id and not r["revoked"]]
        return [self._view(r) for r in sorted(mine, key=lambda r: r["created_at"], reverse=True)]

    async def get_active(self, token_hash: str) -> dict[str, Any] | None:
        return next(
            (
                self._view(r)
                for r in self.rows
                if r["token_hash"] == token_hash and not r["revoked"]
            ),
            None,
        )

    async def revoke(self, user_id: str, token_id: str) -> bool:
        for row in self.rows:
            if row["id"] == token_id and row["user_id"] == user_id and not row["revoked"]:
                row["revoked"] = True
                return True
        return False

    async def touch(self, token_id: str, at: datetime) -> None:
        for row in self.rows:
            if row["id"] == token_id:
                row["last_used_at"] = at


class FakeLlmCredentials:
    """SQLLlmCredentialRepository: a provider's key, sealed, and its last four."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return [dict(v) for (u, _), v in sorted(self.rows.items()) if u == user_id]

    async def get(self, user_id: str, provider: str) -> dict[str, Any] | None:
        row = self.rows.get((user_id, provider))
        return dict(row) if row else None

    async def upsert(
        self,
        user_id: str,
        provider: str,
        *,
        ciphertext: str,
        last4: str,
        validated_at: Any,
        key_version: int,
    ) -> None:
        self.rows[(user_id, provider)] = {
            "provider": provider,
            "ciphertext": ciphertext,
            "key_version": key_version,
            "last4": last4,
            "validated_at": validated_at.isoformat() if validated_at else None,
        }

    async def delete(self, user_id: str, provider: str) -> bool:
        return self.rows.pop((user_id, provider), None) is not None


def at(year: int, month: int, day: int, hour: int = 10, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


__all__ = [
    "ClosedKeyRing",
    "FakeAuditLog",
    "FakeBankConnections",
    "FakeLlmCredentials",
    "FakeRules",
    "FakeStatements",
    "FakeTaxComputations",
    "FakeTaxRuleSets",
    "FakeTokens",
    "at",
    "_fixed",
]
