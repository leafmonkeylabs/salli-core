"""
salli-core is for one person keeping their own books: no firm words.

Organisations, adviser seats, client consent, SSO, SCIM, RBAC and
white-labelling are the closed edition's (docs/design/console.md, section 7
and decision 22). A test for which side something falls: if it exists
because one person keeps their own books, it is open; if it exists because
one party acts for another, or an organisation governs people, it is closed.
This keeps the words out of open code, so the line doesn't blur one comment
at a time.

It scans what the commercial-vocabulary guard scans: the server
(`src/salli`) and the TypeScript packages' sources (`packages/*/src`). Design
records under `docs/design/` are not code and are not scanned. Two words are
left alone on purpose: `advisor` (the Wealth Advisor is Salli's own) and
`OIDC` (the `IdentityProvider` seam names it as an example).
"""

from __future__ import annotations

import re

from tests.contract.test_no_commercial_vocabulary import ROOT, SCANNED, SUFFIXES

BANNED = re.compile(
    r"\bfirms?\b|\btenant(s|cy)?\b|\bmulti[- ]?tenan\w*|\borgani[sz]ations?\b|\badvisers?\b"
    r"|\bseats?\b|\bSAML\b|\bSCIM\b|\bSSO\b|white[- ]?label\w*|\bRBAC\b",
    re.IGNORECASE,
)

#: (path relative to the repository, phrase) pairs that use one of these
#: words for something else. Each needs a reason; none so far.
ALLOWED: dict[tuple[str, str], str] = {}


def find_firm_vocabulary(text: str) -> list[str]:
    """The banned words in `text`, as written."""
    return [m.group(0) for m in BANNED.finditer(text)]


def test_open_code_has_no_firm_vocabulary():
    hits = []
    for base in SCANNED:
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in SUFFIXES:
                continue
            if "migrations/versions" in path.as_posix() or "node_modules" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            for n, line in enumerate(path.read_text().splitlines(), 1):
                for word in find_firm_vocabulary(line):
                    if (rel, word.lower()) not in ALLOWED:
                        hits.append(f"{rel}:{n}: {word!r} in {line.strip()[:90]}")
    assert not hits, "Firm vocabulary in open code:\n" + "\n".join(hits)


def test_it_catches_each_word_and_leaves_salli_s_own_alone():
    for text in (
        "a firm's books",
        "tenant isolation",
        "multi-tenant",
        "the organisation",
        "an organization",
        "an adviser",
        "five seats",
        "SAML",
        "SCIM provisioning",
        "SSO",
        "white-label",
        "whitelabelled",
        "RBAC",
    ):
        assert find_firm_vocabulary(text), text
    for text in (
        "the Wealth Advisor",
        "an OIDC IdentityProvider",
        "confirm the amount",
        "the console's settings",
        "research the season",
    ):
        assert not find_firm_vocabulary(text), text
