"""The audit trail's hash chain (domain/audit_chain.py)."""

from __future__ import annotations

from typing import Any

from salli.domain import audit_chain


def _chain(n: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prev = None
    for seq in range(1, n + 1):
        row = {
            "seq": seq,
            "prev_hash": prev,
            "id": f"r{seq}",
            "user_id": "ana",
            "params": {"n": seq, "rate": 0.5},
            "action": "create_rule",
            "decision": "succeeded",
            "client_id": None,
            "created_at": f"2026-10-0{seq}T00:00:00+00:00",
        }
        row["body_hash"] = audit_chain.body_hash(row["user_id"], row["params"])
        row["hash"] = audit_chain.row_hash(
            seq=seq,
            prev_hash=prev,
            row_id=row["id"],
            action=row["action"],
            decision=row["decision"],
            client_id=None,
            created_at=row["created_at"],
            body=row["body_hash"],
        )
        rows.append(row)
        prev = row["hash"]
    return rows


def test_an_intact_chain_verifies():
    assert audit_chain.verify(_chain(3)) == {"ok": True, "checked": 3, "first_break": None}


def test_a_changed_argument_a_gap_and_a_bad_link_are_named():
    rows = _chain(3)
    rows[1]["params"] = {"n": 9}
    assert audit_chain.verify(rows)["first_break"] == {"seq": 2, "id": "r2", "reason": "content"}
    rows = _chain(3)
    del rows[1]
    assert audit_chain.verify(rows)["first_break"]["reason"] == "missing"
    rows = _chain(3)
    rows[2]["prev_hash"] = "sha256:x"
    assert audit_chain.verify(rows)["first_break"]["reason"] == "link"


def test_a_pseudonymised_row_still_verifies_but_its_action_cannot_change():
    rows = _chain(2)
    rows[0]["user_id"] = audit_chain.pseudonym("key", "ana")
    rows[0]["params"] = {}
    assert audit_chain.verify(rows)["ok"]
    rows[0]["action"] = "other"
    assert audit_chain.verify(rows)["first_break"]["reason"] == "content"


def test_the_pseudonym_is_keyed_and_stable():
    one = audit_chain.pseudonym("key", "ana")
    assert one == audit_chain.pseudonym("key", "ana")
    assert one != audit_chain.pseudonym("other", "ana")
    assert one.startswith("erased:") and "ana" not in one and len(one) <= 64
