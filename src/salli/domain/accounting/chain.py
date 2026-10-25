"""
The ledger's hash chain. Pure.

Every journal entry a user posts is numbered (`seq`, from 1, in the order
they were stored) and carries two hashes: the previous entry's, and its own
over its canonical content, that link included. Changing, removing or
reordering any stored entry breaks the chain from there on, and `verify`
says where. What is hashed is what the entry says about money and who said
it (`content`); tags are not, as they stay editable outside closed books.

The content is plain text and integers (amounts in minor units, rates as
normalised decimal text), so core_0037's migration hashes the entries
stored before it exactly as this does.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from salli.domain.canonical import decimal_text, digest

SCHEMA = "salli.entry/1"

#: The precision a rate is stored at (postings.fx_rate, Numeric(20, 8)).
_RATE = Decimal("1e-8")


def rate_text(rate: Decimal) -> str:
    """A rate as stored, in normalised decimal text."""
    return decimal_text(rate.quantize(_RATE, rounding=ROUND_HALF_UP))


def content(
    *,
    seq: int,
    prev_hash: str | None,
    entry_id: str,
    user_id: str,
    entry_date: str,
    description: str,
    source: str,
    external_ref: str | None,
    reverses: str | None,
    created_by: str,
    created_via: str,
    postings: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """What an entry's hash covers. Each posting is its `account_id`,
    `direction` (1 or -1), `amount_minor`, `currency` and `fx_rate` (text,
    `rate_text`); their order doesn't matter."""
    legs = [
        {
            "account_id": p["account_id"],
            "direction": int(p["direction"]),
            "amount_minor": int(p["amount_minor"]),
            "currency": p["currency"],
            "fx_rate": p["fx_rate"],
        }
        for p in postings
    ]
    legs.sort(key=lambda leg: json.dumps(leg, sort_keys=True))
    return {
        "schema": SCHEMA,
        "seq": seq,
        "prev_hash": prev_hash,
        "id": entry_id,
        "user_id": user_id,
        "entry_date": entry_date,
        "description": description,
        "source": source,
        "external_ref": external_ref,
        "reverses": reverses,
        "created_by": created_by,
        "created_via": created_via,
        "postings": legs,
    }


def entry_hash(entry_content: Mapping[str, Any]) -> str:
    return digest(entry_content)


@dataclass(frozen=True)
class Link:
    """A stored entry as the chain sees it: its content as stored now, and
    the hash stored with it."""

    content: Mapping[str, Any]
    hash: str | None


def verify(links: Iterable[Link]) -> dict[str, Any]:
    """Walk a user's entries in `seq` order. `ok` with the number of entries
    checked, or the first break: the entry (`seq`, `entry_id`) and why
    (`missing`: an entry before it is gone; `link`: it doesn't name the one
    before it; `content`: it was changed after it was stored)."""
    checked = 0
    prev: str | None = None
    for link in links:
        c = link.content
        expected = checked + 1
        reason: str | None = None
        if c["seq"] != expected:
            reason = "missing"
        elif c["prev_hash"] != prev:
            reason = "link"
        elif link.hash is None or entry_hash(c) != link.hash:
            reason = "content"
        if reason is not None:
            return {
                "ok": False,
                "checked": checked,
                "first_break": {"seq": c["seq"], "entry_id": c["id"], "reason": reason},
            }
        checked += 1
        prev = link.hash
    return {"ok": True, "checked": checked, "first_break": None}
