"""
The paths that act across people are the ones `acting.SYSTEM_PATHS` lists,
each with its reason: every name used in the code is listed, and every one
listed is used (docs/security.md, "Row-level security").
"""

from __future__ import annotations

import re
from pathlib import Path

from salli.application.acting import SYSTEM_PATHS

SRC = Path(__file__).resolve().parents[3] / "src" / "salli"

#: as_system("…"), @system_path("…"), uow.across_people("…"),
#: system_scope(session, "…").
_USE = re.compile(
    r"""(?:as_system|system_path|across_people)\(\s*"([^"]+)"|system_scope\([^,]+,\s*"([^"]+)\""""
)


def _used() -> dict[str, set[str]]:
    used: dict[str, set[str]] = {}
    for path in SRC.rglob("*.py"):
        for match in _USE.finditer(path.read_text()):
            used.setdefault(match.group(1) or match.group(2), set()).add(str(path.relative_to(SRC)))
    return used


def test_every_path_used_is_listed_with_a_reason():
    used = _used()
    assert set(used) <= set(SYSTEM_PATHS), sorted(set(used) - set(SYSTEM_PATHS))
    assert all(reason.strip() for reason in SYSTEM_PATHS.values())


def test_every_path_listed_is_used():
    used = _used()
    # Migrations set the scope in SQL (migrations/support.py), not by name.
    unused = set(SYSTEM_PATHS) - set(used) - {"migrations"}
    assert unused == set()
    assert "salli.scope', 'system'" in (SRC / "migrations" / "support.py").read_text()
