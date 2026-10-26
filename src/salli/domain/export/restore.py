"""
Restoring a full export into another person's empty books. Pure.

The export (`GET /v1/onboarding/export`) carries, beside its readable
sections, `rows`: the person's stored rows, table by table, exactly as
stored (amounts in minor units, decimals and times as text). A restore reads
only those. It checks the export's version, then the ledger's hash chain as
exported, and only then moves the rows to the person restoring: their id in
place of the exported one, their entries chained again (the chain covers
whose entries they are), and stored files under their own folder.

What each version carries, and which a restore takes, is in
docs/self-host.md ("Moving your books").
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from salli.domain.accounting import chain
from salli.domain.canonical import digest

#: The export's format. 1: exports made before it said (no `rows`); 2 adds
#: `export_version` and `rows`. A restore takes only versions it knows.
EXPORT_VERSION = 2

#: The tables `rows` carries, in the order a restore writes them (each after
#: the ones it refers to). `user_profiles` and `audit_logs` are read apart:
#: the profile updates the person's own, and the audit rows are kept as an
#: imported section (`restores.audit_rows`), outside this server's chain.
TABLES: tuple[str, ...] = (
    "accounts",
    "tags",
    "journal_entries",
    "postings",
    "posting_tags",
    "statements",
    "parsed_transactions",
    "reconciliations",
    "tax_rule_sets",
    "tax_rule_set_versions",
    "tax_computations",
    "tax_returns",
    "tax_return_payments",
    "cma_packs",
    "agent_documents",
    "reminders",
    "budgets",
    "debts",
    "fi_goals",
    "goal_allocations",
    "fi_scores",
    "fire_strategies",
    "advisory_reports",
    "holdings",
    "holding_transactions",
    "holding_prices",
    "investment_policies",
    "recurring_subscriptions",
    "policies",
    "insurance_targets",
    "principles",
    "decisions",
    "decision_notes",
    "decision_reviews",
    "categorization_rules",
    "notification_preferences",
    "restores",
)

#: Profile columns a restore leaves as they are on this server: who the
#: person is here, how they reach its AI, and its switches.
PROFILE_KEPT = frozenset(
    {
        "id",
        "email",
        "mcp_enabled",
        "daily_briefing_enabled",
        "preferred_model",
        "ai_provider",
        "ai_models",
        "created_at",
        "updated_at",
    }
)

#: The rows that hold a stored file's key.
FILE_TABLES = ("agent_documents", "statements")


class ExportRefused(ValueError):
    """The export can't be restored: its version, its shape or its ledger."""


def export_hash(document: Mapping[str, Any]) -> str:
    """The export's content hash, as the restore's audit row names it."""
    return digest(dict(document), floats=True)


def check_version(document: Mapping[str, Any]) -> int:
    version = document.get("export_version")
    if version is None or "rows" not in document:
        raise ExportRefused(
            "This export was made before exports carried what a restore needs "
            "(version 1). Export again from a server that is up to date."
        )
    if not isinstance(version, int) or version < 2:
        raise ExportRefused(f"Unknown export version {version!r}.")
    if version > EXPORT_VERSION:
        raise ExportRefused(
            f"This export is version {version}, newer than this server knows "
            f"({EXPORT_VERSION}). Update this server first."
        )
    return version


def _legs(rows: Mapping[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    legs: dict[str, list[dict[str, Any]]] = {}
    for p in rows.get("postings", []):
        legs.setdefault(p["entry_id"], []).append(
            {
                "account_id": p["account_id"],
                "direction": p["direction"],
                "amount_minor": p["amount_minor"],
                "currency": p["currency"],
                "fx_rate": chain.rate_text(Decimal(str(p["fx_rate"]))),
            }
        )
    return legs


def _content(entry: Mapping[str, Any], legs: list[dict[str, Any]], **over: Any) -> dict[str, Any]:
    e = {**entry, **over}
    return chain.content(
        seq=e["seq"],
        prev_hash=e["prev_hash"],
        entry_id=e["id"],
        user_id=e["user_id"],
        entry_date=e["entry_date"],
        description=e["description"],
        source=e["source"],
        external_ref=e["external_ref"],
        reverses=e["reverses_id"],
        corrects=e["corrects_id"],
        created_by=e["created_by"],
        created_via=e["created_via"],
        postings=legs,
    )


def file_keys(rows: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    """The stored files the rows refer to, by key."""
    return sorted(
        {r["storage_key"] for t in FILE_TABLES for r in rows.get(t, []) if r.get("storage_key")}
    )


def entries(rows: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return sorted(rows.get("journal_entries", []), key=lambda e: e["seq"])


def verify_ledger(rows: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """The exported entries' hash chain, as `GET /v1/ledger/verify` checks a
    stored one: ok, or the first break."""
    legs = _legs(rows)
    return chain.verify(
        chain.Link(_content(e, legs.get(e["id"], [])), e["hash"]) for e in entries(rows)
    )


def rehome(
    rows: Mapping[str, list[dict[str, Any]]],
    user_id: str,
    files: Mapping[str, str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """The rows as `user_id`'s: their id in every `user_id`, each stored
    file's key as `files` maps it (an empty key where it has none), and the
    entries chained again under them, a return's `chain_head_hash` with
    them. Returns the rows and each exported entry hash's new one."""
    moved: dict[str, list[dict[str, Any]]] = {
        table: [{**r, "user_id": user_id} if "user_id" in r else dict(r) for r in rows[table]]
        for table in TABLES
        if table in rows
    }
    for table in FILE_TABLES:
        for r in moved.get(table, []):
            if r.get("storage_key"):
                r["storage_key"] = files.get(r["storage_key"], "")
    legs = _legs(moved)
    hashes: dict[str, str] = {}
    prev: str | None = None
    for e in sorted(moved.get("journal_entries", []), key=lambda e: e["seq"]):
        own = chain.entry_hash(_content(e, legs.get(e["id"], []), prev_hash=prev))
        hashes[e["hash"]] = own
        e["prev_hash"], e["hash"] = prev, own
        prev = own
    for r in moved.get("tax_returns", []):
        if r.get("chain_head_hash"):
            r["chain_head_hash"] = hashes.get(r["chain_head_hash"], r["chain_head_hash"])
    return moved, hashes
