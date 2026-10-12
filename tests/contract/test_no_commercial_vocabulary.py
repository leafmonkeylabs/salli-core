"""
salli-core knows nothing about plans, payments or credits.

Metering and gating belong to whoever deploys Salli and live in an extension
(salli/extensions.py). This keeps the vocabulary out too, so the seam stays a
seam: a comment that says "free users get…" is how an `if plan == "free"`
starts. Tax credits (whatever a user's tax rules define) and the ledger's
debit/credit are Salli's own domain and are not what this looks for.

It scans the server (`src/salli`) and the TypeScript packages' sources
(`packages/*/src`: the SDK, the CLI and, from C1, the console), so no page
of the console says what a plan includes either (docs/design/console.md,
decision 22).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = [ROOT / "src" / "salli", *sorted((ROOT / "packages").glob("*/src"))]
SUFFIXES = {".py", ".md", ".mako", ".toml", ".ts", ".tsx", ".css"}

BANNED = re.compile(
    r"paddle|revenuecat|jira|\bquotas?\b|ai[_ ]credits?|spend_credits|grant_credits"
    r"|credit[_ ](pack|purchase|multiplier|charge)|plan_key|top[- ]?ups?\b"
    r"|upgrad(e|ing)\s+(to|your|their|the)\s+(plan|pro|tier)|subscriber|billing"
    r"|\bpaid\s+(plan|tier|user)|\bfree\s+(plan|tier|users?)\b|\bpro\s+(plan|tier)"
    r"|every\s+(plan|tier)\b|\bfree\s+included\b|plan[- ]gat(e|ed|ing)\b"
    r"|price[_ ]id|monetis|monetiz",
    re.IGNORECASE,
)

#: (file, phrase) pairs that use one of these words about something other
#: than Salli's own commerce. Each needs a reason. `file` is relative to the
#: scanned directory.
ALLOWED = {
    # Recognising the LLM provider's own "quota exceeded" error for a user's key.
    ("application/services/agent_service.py", "quota"),
    # A recorded price of one of the person's holdings, by its id.
    ("commands/investments.ts", "price id"),
}


def _sources() -> list[tuple[Path, Path]]:
    found: list[tuple[Path, Path]] = []
    for base in SCANNED:
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in SUFFIXES:
                continue
            if "migrations/versions" in path.as_posix() or "node_modules" in path.parts:
                continue
            found.append((base, path))
    return found


def find_commercial_vocabulary(text: str) -> list[str]:
    """The banned phrases in `text`, as written."""
    return [m.group(0) for m in BANNED.finditer(text)]


def test_core_has_no_commercial_vocabulary():
    hits = []
    for base, path in _sources():
        rel = path.relative_to(base).as_posix()
        for n, line in enumerate(path.read_text().splitlines(), 1):
            for phrase in find_commercial_vocabulary(line):
                if (rel, phrase.lower()) not in ALLOWED:
                    hits.append(f"{path.relative_to(ROOT)}:{n}: {phrase!r} in {line.strip()[:90]}")
    assert not hits, "Commercial vocabulary in salli-core:\n" + "\n".join(hits)


def test_the_packages_are_scanned():
    scanned = {base.relative_to(ROOT).as_posix() for base in SCANNED}
    assert {"src/salli", "packages/cli/src", "packages/sdk/src"} <= scanned
    suffixes = {path.suffix for _, path in _sources()}
    assert {".py", ".ts"} <= suffixes


def test_it_catches_plan_words_in_any_scanned_language():
    assert find_commercial_vocabulary("// MCP is available on every tier, Free included.")
    assert find_commercial_vocabulary("/* Upgrade to Pro */ .billing-banner {}")
    assert find_commercial_vocabulary("No plan gate here")
    assert not find_commercial_vocabulary("the fast tier of a model; a tax credit")
