"""
Canonical JSON and content hashes. Pure.

A content hash says "these are the same inputs" whatever order their keys
came in, however their numbers were written, and whichever container held
them. So `canonical` turns a value into plain JSON data, one way only:

- a mapping's keys sorted (as text);
- a Decimal as its exact value, normalised: "2400", "2400.0" and "2400.00"
  are one number, written "2400"; minus zero is "0";
- a date or a datetime in ISO 8601;
- a dataclass or a pydantic model as its fields (a model by its aliases, as
  it is written in JSON);
- a set as a sorted list; any other sequence as a list, in its order;
- a float refused, unless the caller says floats may come (a row as a
  database driver returned it): then it is the decimal its shortest repr
  writes.

`digest` is the SHA-256 of the canonical JSON, compact and ASCII-only.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
from collections.abc import Mapping, Set
from decimal import Decimal
from enum import Enum
from typing import Any, cast

from pydantic import BaseModel


def decimal_text(value: Decimal) -> str:
    """A Decimal's exact value, normalised, never in exponent form."""
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def canonical(value: Any, *, floats: bool = False) -> Any:
    """`value` as plain JSON data, written one way only (see the module).
    `floats`: a float is read as the decimal its repr writes, rather than
    refused."""

    def walk(v: Any) -> Any:
        if v is None or isinstance(v, bool | str):
            return v
        if isinstance(v, Enum):
            return walk(v.value)
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            if not floats:
                raise TypeError("A float has no canonical form here: use a Decimal")
            return decimal_text(Decimal(repr(v)))
        if isinstance(v, Decimal):
            return decimal_text(v)
        if isinstance(v, dt.datetime | dt.date):
            return v.isoformat()
        if isinstance(v, BaseModel):
            return walk(v.model_dump(mode="python", by_alias=True))
        if dataclasses.is_dataclass(v) and not isinstance(v, type):
            return walk({f.name: getattr(v, f.name) for f in dataclasses.fields(v)})
        if isinstance(v, Mapping):
            items = cast("Mapping[Any, Any]", v)
            return {str(k): walk(x) for k, x in sorted(items.items(), key=lambda kv: str(kv[0]))}
        if isinstance(v, Set):
            members = [walk(x) for x in cast("Set[Any]", v)]
            return sorted(members, key=lambda m: json.dumps(m, sort_keys=True))
        if isinstance(v, list | tuple):
            return [walk(x) for x in cast("list[Any]", v)]
        raise TypeError(f"No canonical form for {type(v).__name__}")

    return walk(value)


def dumps(value: Any, *, floats: bool = False) -> str:
    """The canonical JSON text of `value`: sorted keys, no spaces, ASCII."""
    return json.dumps(
        canonical(value, floats=floats), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def digest(value: Any, *, floats: bool = False) -> str:
    """ "sha256:" and the hex digest of `value`'s canonical JSON."""
    return "sha256:" + hashlib.sha256(dumps(value, floats=floats).encode("ascii")).hexdigest()
