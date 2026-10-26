"""Restoring an export, the pure part (domain/export/restore.py): which
versions it takes, the exported chain checked, and the rows moved to the
person restoring with their entries chained again."""

from __future__ import annotations

from typing import Any

import pytest

from salli.domain.accounting import chain
from salli.domain.export import restore
from salli.domain.export.restore import ExportRefused


def _rows(user: str = "ama") -> dict[str, list[dict[str, Any]]]:
    entries, postings, prev = [], [], None
    for seq in (1, 2):
        legs = [
            {
                "account_id": "bank",
                "direction": 1,
                "amount_minor": 1250,
                "currency": "GHS",
                "fx_rate": "1",
            },
            {
                "account_id": "food",
                "direction": -1,
                "amount_minor": 1250,
                "currency": "GHS",
                "fx_rate": "1",
            },
        ]
        entry = {
            "id": f"e{seq}",
            "user_id": user,
            "seq": seq,
            "prev_hash": prev,
            "entry_date": "2031-02-0" + str(seq),
            "description": "Market",
            "source": "manual",
            "external_ref": None,
            "reverses_id": None,
            "corrects_id": None,
            "created_by": user,
            "created_via": "cli",
        }
        entry["hash"] = prev = chain.entry_hash(
            chain.content(
                seq=seq,
                prev_hash=entry["prev_hash"],
                entry_id=entry["id"],
                user_id=user,
                entry_date=entry["entry_date"],
                description="Market",
                source="manual",
                external_ref=None,
                reverses=None,
                created_by=user,
                created_via="cli",
                postings=legs,
            )
        )
        entries.append(entry)
        postings += [{**leg, "entry_id": entry["id"]} for leg in legs]
    return {
        "journal_entries": entries,
        "postings": postings,
        "agent_documents": [{"id": "d1", "user_id": user, "storage_key": f"{user}/a/receipt.pdf"}],
        "tax_returns": [{"id": "r1", "user_id": user, "chain_head_hash": entries[-1]["hash"]}],
    }


def test_only_known_versions_with_rows_are_taken():
    rows = _rows()
    assert restore.check_version({"export_version": 2, "rows": rows}) == 2
    with pytest.raises(ExportRefused, match="version 1"):
        restore.check_version({"journal_entries": []})
    with pytest.raises(ExportRefused, match="newer than this server knows"):
        restore.check_version({"export_version": 3, "rows": rows})


def test_the_exported_chain_is_checked_and_its_first_break_named():
    rows = _rows()
    assert restore.verify_ledger(rows) == {"ok": True, "checked": 2, "first_break": None}
    rows["postings"][2]["amount_minor"] = 1350
    assert restore.verify_ledger(rows)["first_break"] == {
        "seq": 2,
        "entry_id": "e2",
        "reason": "content",
    }


def test_moved_rows_are_the_persons_chained_again_with_their_files():
    rows = _rows("ama")
    moved, hashes = restore.rehome(rows, "kofi", {"ama/a/receipt.pdf": "kofi/a/receipt.pdf"})

    assert {r["user_id"] for t in moved.values() for r in t if "user_id" in r} == {"kofi"}
    assert moved["agent_documents"][0]["storage_key"] == "kofi/a/receipt.pdf"
    # Who posted them stays as recorded; the chain is theirs now, and verifies.
    assert moved["journal_entries"][0]["created_by"] == "ama"
    assert restore.verify_ledger(moved)["ok"] is True
    old_head = rows["journal_entries"][-1]["hash"]
    assert moved["tax_returns"][0]["chain_head_hash"] == hashes[old_head] != old_head
    assert rows["journal_entries"][0]["user_id"] == "ama"  # the export is left as it was
