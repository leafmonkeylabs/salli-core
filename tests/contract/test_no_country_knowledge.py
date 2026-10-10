"""
salli-core keeps no country's tax or financial knowledge.

A country's tax rules, planning assumptions, tax-id schemes and market notes
are user data, written by the user or their agent with sources
(docs/design/country-neutral-core.md). This keeps them from creeping back into
the code, the CLI, the SDK, the API document, the skills or the docs: it fails
on any term below outside the allowlist.

The terms are the ones the last country's built-in knowledge used: its name,
its currency (outside the ISO 4217 table), its revenue authority and filing
portal, its withholding taxes, its tax-id schemes and its stock exchange and
index. If you need to name a country or a currency in an example, vary them;
if you need one of these terms for a reason that isn't country knowledge, add
it to ALLOWED with that reason.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Code: what Salli runs, and what it ships to clients.
CODE = [
    ROOT / "src",
    ROOT / "packages" / "cli" / "src",
    ROOT / "packages" / "sdk" / "src",
    ROOT / "openapi",
]
#: Words people and agents read: the skills and the docs.
PROSE = [
    ROOT / "packages" / "cli" / "skills",
    ROOT / "packages" / "cli" / "README.md",
    ROOT / "docs",
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "CLAUDE.md",
    ROOT / ".env.example",
]
SUFFIXES = {".py", ".ts", ".mjs", ".json", ".md", ".mako", ".toml", ".example"}

#: Matched case-sensitively, as whole words: acronyms that are ordinary
#: letters in lower case ("ait", "cse").
ACRONYMS = re.compile(r"\b(?:LKR|IRD|RAMIS|APIT|AIT|CSE|ASPI|CBSL)\b|LK-TIN|LK-NIC|LK_TIN|LK_NIC")
#: Matched in any case.
WORDS = re.compile(r"sri\s+lanka|rupee|ird_number|\blk_\d", re.IGNORECASE)

#: (path, the stripped line) pairs where a term is data about every country
#: alike, or history; each says why. A stale entry fails the test.
ALLOWED: dict[tuple[str, str], str] = {
    # The ISO 3166-1 table: every country's code and name, this one included.
    ("src/salli/domain/jurisdiction.py", '"LK": "Sri Lanka",'): "ISO 3166-1 country names",
    # The ISO 4217 table: every currency's code, this one included.
    ("src/salli/domain/currency.py", '"LKR",'): "ISO 4217 currency codes",
    # Where the project began, as history; it claims no support for anywhere.
    (
        "README.md",
        "Salli is for anyone, anywhere. It started in Sri Lanka, but its code knows no",
    ): "the project's history",
}

#: Whole directories that are history: an applied migration is never edited,
#: so the ones that once moved one country's data keep saying so.
HISTORICAL = ("src/salli/migrations/versions/",)


def _files(bases: list[Path]) -> list[Path]:
    found: list[Path] = []
    for base in bases:
        if base.is_file():
            found.append(base)
            continue
        for path in base.rglob("*"):
            if path.is_file() and (path.suffix in SUFFIXES or path.name.endswith(".example")):
                if "node_modules" not in path.parts and "__pycache__" not in path.parts:
                    found.append(path)
    return found


def _hits(bases: list[Path]) -> tuple[list[str], set[tuple[str, str]]]:
    hits: list[str] = []
    used: set[tuple[str, str]] = set()
    for path in _files(bases):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(HISTORICAL):
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            terms = [m.group(0) for m in (*ACRONYMS.finditer(line), *WORDS.finditer(line))]
            if not terms:
                continue
            key = (rel, line.strip())
            if key in ALLOWED:
                used.add(key)
                continue
            hits.append(f"{rel}:{n}: {', '.join(terms)} in {line.strip()[:100]}")
    return hits, used


def test_the_code_keeps_no_country_s_knowledge():
    hits, _ = _hits(CODE)
    assert not hits, "Country-specific knowledge in salli-core's code:\n" + "\n".join(hits)


def test_the_skills_and_docs_keep_no_country_s_knowledge():
    hits, _ = _hits(PROSE)
    assert not hits, "Country-specific knowledge in the skills or docs:\n" + "\n".join(hits)


def test_every_allowed_line_is_still_there():
    """An entry whose line has gone is an exception nobody needs: remove it."""
    _, used = _hits(CODE + PROSE)
    assert set(ALLOWED) == used, f"Stale ALLOWED entries: {sorted(set(ALLOWED) - used)}"


def test_the_guard_catches_what_it_is_for():
    """The patterns themselves: each term is caught, ordinary words are not."""
    for text in (
        "Sri Lanka",
        "a SRI LANKAN figure",
        "LKR 1,000",
        "the IRD portal",
        "APIT withheld",
        "AIT",
        "RAMIS",
        "LK-TIN",
        "LK_NIC",
        "CSE index funds",
        "the ASPI",
        "in rupees",
        "ird_number",
        "lk_2025_26",
        "CBSL",
    ):
        assert ACRONYMS.search(text) or WORDS.search(text), text
    for text in ("third", "wait", "aspiration", "useless", "blk_1", "Kirdi", "LKRS2"):
        assert not (ACRONYMS.search(text) or WORDS.search(text)), text
