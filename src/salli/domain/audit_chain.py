"""
The audit trail's hash chain. Pure.

Every `audit_logs` row on the instance is numbered (`seq`, from 1, in the
order stored, everyone's in one chain) and carries the previous row's hash
and its own. Its own covers what was done, when and by which client, and
`body_hash`: a digest of whose row it is and its arguments. Erasing an
account pseudonymises its rows (a keyed hash in place of the user id, no
arguments) without touching `body_hash`, so the chain still verifies; a row
not erased must also still match its `body_hash`.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable, Mapping
from typing import Any

from salli.domain.canonical import digest

SCHEMA = "salli.audit/1"

#: How an erased account's rows name it: this, then a keyed hash of its id.
ERASED = "erased:"


def pseudonym(key: str, user_id: str) -> str:
    """The id an erased account's audit rows keep: the same for each of its
    rows, and not the id without the key."""
    mac = hmac.new(key.encode("utf-8"), user_id.encode("utf-8"), hashlib.sha256)
    return ERASED + mac.hexdigest()[:56]


def body_hash(user_id: str, params: Mapping[str, Any]) -> str:
    # Arguments arrive as JSON, numbers and all.
    return digest({"user_id": user_id, "params": dict(params)}, floats=True)


def row_hash(
    *,
    seq: int,
    prev_hash: str | None,
    row_id: str,
    action: str,
    decision: str,
    client_id: str | None,
    created_at: str,
    body: str,
) -> str:
    return digest(
        {
            "schema": SCHEMA,
            "seq": seq,
            "prev_hash": prev_hash,
            "id": row_id,
            "action": action,
            "decision": decision,
            "client_id": client_id,
            "created_at": created_at,
            "body_hash": body,
        }
    )


def verify(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Walk the rows in `seq` order (each with the columns `row_hash` and
    `body_hash` take, `created_at` as ISO text). `ok` with the number
    checked, or the first break: its `seq`, `id` and why (`missing`, `link`,
    `content`: changed after it was stored)."""
    checked = 0
    prev: str | None = None
    for r in rows:
        reason: str | None = None
        if r["seq"] != checked + 1:
            reason = "missing"
        elif r["prev_hash"] != prev:
            reason = "link"
        elif (
            not str(r["user_id"]).startswith(ERASED)
            and body_hash(r["user_id"], r["params"]) != r["body_hash"]
        ) or row_hash(
            seq=r["seq"],
            prev_hash=r["prev_hash"],
            row_id=r["id"],
            action=r["action"],
            decision=r["decision"],
            client_id=r["client_id"],
            created_at=r["created_at"],
            body=r["body_hash"],
        ) != r["hash"]:
            reason = "content"
        if reason is not None:
            return {
                "ok": False,
                "checked": checked,
                "first_break": {"seq": r["seq"], "id": r["id"], "reason": reason},
            }
        checked += 1
        prev = r["hash"]
    return {"ok": True, "checked": checked, "first_break": None}
