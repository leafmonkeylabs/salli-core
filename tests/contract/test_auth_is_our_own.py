"""
Salli runs its own sign-in and keeps files on its own disk (decision D13,
docs/self-host.md): nothing in the code, tests, packages or docs depends on,
configures or mentions Supabase.

Allowed: the historical migrations (they record what an instance once had)
and docs/design/ (design history). Everything else is checked, by text, so a
mention in a comment counts too: it would describe something that is no
longer true.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALLOWED = (
    "src/salli/migrations/versions/",
    "docs/design/",
    # This guard names what it looks for.
    "tests/contract/test_auth_is_our_own.py",
)

PATTERN = re.compile(r"supabase", re.IGNORECASE)


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def test_nothing_mentions_supabase():
    found: list[str] = []
    for name in _tracked_files():
        if name.startswith(ALLOWED) or "node_modules/" in name:
            continue
        path = ROOT / name
        if not path.is_file():
            continue
        if PATTERN.search(name):
            found.append(name)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line):
                found.append(f"{name}:{number}")
    assert found == [], f"Supabase is gone; these still mention it: {found}"


def test_nothing_imports_a_supabase_client():
    for name in _tracked_files():
        if name.endswith((".py", ".ts", ".mjs", ".js")) and not name.startswith(ALLOWED):
            text = (ROOT / name).read_text(encoding="utf-8", errors="ignore")
            assert "@supabase/" not in text and "import supabase" not in text, name
