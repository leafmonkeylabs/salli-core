"""
salli-core knows nothing about plans, payments or credits.

Metering and gating belong to whoever deploys Salli and live in an extension
(salli/extensions.py). This keeps the vocabulary out too, so the seam stays a
seam: a comment that says "free users get…" is how an `if plan == "free"`
starts. Tax credits (whatever a user's tax rules define) and the ledger's
debit/credit are Salli's own domain and are not what this looks for.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = [ROOT / "src" / "salli"]
SUFFIXES = {".py", ".md", ".mako", ".toml"}

BANNED = re.compile(
    r"paddle|revenuecat|jira|\bquotas?\b|ai[_ ]credits?|spend_credits|grant_credits"
    r"|credit[_ ](pack|purchase|multiplier|charge)|plan_key|top[- ]?ups?\b"
    r"|upgrad(e|ing)\s+(to|your|their|the)\s+(plan|pro|tier)|subscriber|billing"
    r"|\bpaid\s+(plan|tier|user)|\bfree\s+(plan|tier|users?)\b|\bpro\s+(plan|tier)"
    r"|price[_ ]id|monetis|monetiz",
    re.IGNORECASE,
)

#: (file, phrase) pairs that use one of these words about something other
#: than Salli's own commerce. Each needs a reason.
ALLOWED = {
    # Recognising the LLM provider's own "quota exceeded" error for a user's key.
    ("application/services/agent_service.py", "quota"),
}


def test_core_has_no_commercial_vocabulary():
    hits = []
    for base in SCANNED:
        for path in base.rglob("*"):
            if path.suffix not in SUFFIXES or "migrations/versions" in path.as_posix():
                continue
            rel = path.relative_to(base).as_posix()
            for n, line in enumerate(path.read_text().splitlines(), 1):
                for m in BANNED.finditer(line):
                    if (rel, m.group(0).lower()) not in ALLOWED:
                        hits.append(f"{rel}:{n}: {m.group(0)!r} in {line.strip()[:90]}")
    assert not hits, "Commercial vocabulary in salli-core:\n" + "\n".join(hits)
