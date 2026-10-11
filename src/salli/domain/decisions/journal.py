"""
The decision journal: append-only records of how a person decided
(`salli.decision/1`), with later notes and reviews appended. Pure.

An entry is a self-describing JSON document, written once:

- **the question**, in the person's words;
- **the options**, each a snapshot of the scenario Salli ran: the scenario
  document as run, its content hash, the figures a principle reads
  (`figures.FIGURES`), what it projected month by month (`projection.py`),
  and each principle's check against it;
- **the basis** every option shares: the as-of date and currency, the
  baseline's fingerprint, the engine's and the FI assumptions' versions,
  the assumptions with the placeholders flagged, and how fresh the ledger
  was;
- **the principles** as they were, each with its version and content hash;
- **the option chosen**, and **the person's reasons, in their words**;
- **the agent's summary**, if there is one, marked as the agent's;
- **the review date**, and how it was recorded (the API, or an agent over
  MCP with the person's confirmation).

`hash` is the SHA-256 of the entry's canonical JSON (`domain/canonical.py`:
sorted keys, no spaces, ASCII; numbers as decimal strings): anyone holding
the JSON export can recompute it and see the entry is the one recorded.
A note (`salli.decision-note/1`) or a review (`salli.decision-review/1`) is
its own document, with its own hash, naming the entry's hash: appending one
never changes the entry, and each points at exactly what it is about.

Nothing here edits or deletes: the functions build documents, hash them,
check a hash, and render the journal as JSON or Markdown.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from salli.domain import canonical
from salli.domain.decisions import figures as figure_set
from salli.domain.decisions import principles as principle_rules
from salli.domain.decisions.principles import CheckResult, Principle
from salli.domain.scenarios import views
from salli.domain.scenarios.engine import ScenarioResult
from salli.domain.taxrules.common import Problem
from salli.domain.taxrules.expr import Expr

SCHEMA_ID = "salli.decision/1"
NOTE_SCHEMA = "salli.decision-note/1"
REVIEW_SCHEMA = "salli.decision-review/1"
EXPORT_SCHEMA = "salli.decision-journal/1"

MIN_OPTIONS = 1
MAX_OPTIONS = 5
MAX_QUESTION = 500
MAX_TEXT = 5000
#: How far ahead a review may be set.
MAX_REVIEW_YEARS = 50

Author = Literal["user", "agent"]

#: How to check an entry, said in every export.
VERIFY = (
    "Each hash is the SHA-256 of the document's canonical JSON: keys sorted, no "
    "whitespace, ASCII only (non-ASCII as \\u escapes), numbers as decimal strings. "
    "Recompute it over `entry` (or `note`, `review`) and compare."
)


class JournalError(ValueError):
    """A decision, note or review that can't be recorded, with every problem."""

    def __init__(self, problems: Sequence[Problem]) -> None:
        self.problems = tuple(problems)
        shown = "; ".join(str(p) for p in self.problems[:5])
        super().__init__(f"{len(self.problems)} problem(s): {shown}")


@dataclass(frozen=True)
class PrincipleInUse:
    """A principle as it stands when a decision is checked against it."""

    id: str
    version: int
    hash: str
    principle: Principle
    expr: Expr

    def view(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.principle.label,
            "check": self.principle.check,
            "account": self.principle.account,
            "version": self.version,
            "hash": self.hash,
        }

    def check(self, figures: figure_set.Figures) -> CheckResult:
        return principle_rules.check(self.principle, self.expr, figures)


def checks_view(
    in_use: Sequence[PrincipleInUse], figures: figure_set.Figures
) -> list[dict[str, Any]]:
    """Each principle's check against `figures`, in the principles' order."""
    return [
        {
            "principle_id": p.id,
            "label": p.principle.label,
            **principle_rules.result_view(p.check(figures)),
        }
        for p in in_use
    ]


def text_problems(
    path: str, value: str | None, *, required: bool, limit: int = MAX_TEXT
) -> list[Problem]:
    if value is None or not value.strip():
        return [Problem(path, "is required: write it in your own words")] if required else []
    if len(value) > limit:
        return [Problem(path, f"may be at most {limit} characters")]
    return []


def entry_problems(
    *,
    question: str,
    labels: Sequence[str | None],
    chosen: str,
    reasons: str,
    agent_summary: str | None,
    review_on: dt.date,
    as_of: dt.date,
    earliest_review: dt.date,
) -> list[Problem]:
    """What is wrong with a decision before anything is run."""
    problems = [
        *text_problems("question", question, required=True, limit=MAX_QUESTION),
        *text_problems("reasons", reasons, required=True),
        *text_problems("agent_summary", agent_summary, required=False),
    ]
    if not MIN_OPTIONS <= len(labels) <= MAX_OPTIONS:
        problems.append(
            Problem("options", f"records {MIN_OPTIONS} to {MAX_OPTIONS} options, not {len(labels)}")
        )
    seen: set[str] = set()
    for i, label in enumerate(labels):
        if not label or not label.strip():
            problems.append(Problem(f"options[{i}].label", "is required: how the option is named"))
        elif label in seen:
            problems.append(Problem(f"options[{i}].label", f"{label!r} names another option too"))
        else:
            seen.add(label)
    if chosen not in seen:
        problems.append(Problem("chosen", "is not the label of one of the options"))
    if review_on < earliest_review:
        problems.append(
            Problem(
                "review_on",
                f"is before {earliest_review.isoformat()}: a review compares at a month's end, "
                "and the first the projection has is the end of the as-of month",
            )
        )
    elif review_on.year > as_of.year + MAX_REVIEW_YEARS:
        problems.append(Problem("review_on", f"is more than {MAX_REVIEW_YEARS} years ahead"))
    return problems


def basis(result: ScenarioResult) -> dict[str, Any]:
    """What every option of a decision rests on (the same for each: one
    baseline, one engine)."""
    shown = views.result_view(result)
    return {
        "baseline_fingerprint": result.baseline_fingerprint,
        "versions": shown["versions"],
        "assumptions": shown["assumptions"],
        "placeholders": shown["placeholders"],
        "data_as_of": result.data_as_of,
        "is_stale": result.is_stale,
    }


def option_snapshot(
    result: ScenarioResult,
    figures: figure_set.Figures,
    checks: list[dict[str, Any]],
    projection: list[dict[str, str | None]],
) -> dict[str, Any]:
    """One option as recorded."""
    return {
        "label": result.label,
        "scenario": result.scenario.model_dump(mode="json", by_alias=True, exclude_none=True),
        "scenario_hash": result.hash,
        "figures": figure_set.view(figures),
        "unavailable": dict(figures.missing),
        "principles": checks,
        "projection": projection,
        "notes": list(result.notes),
    }


def entry(
    *,
    decision_id: str,
    recorded_at: dt.datetime,
    recorded_via: Mapping[str, Any],
    question: str,
    as_of: dt.date,
    currency: str,
    basis: Mapping[str, Any],
    principles: Sequence[PrincipleInUse],
    baseline: Mapping[str, Any],
    options: Sequence[Mapping[str, Any]],
    chosen: str,
    reasons: str,
    agent_summary: str | None,
    agent: str | None,
    review_on: dt.date,
) -> dict[str, Any]:
    """A decision's entry, as it is recorded and hashed."""
    return {
        "schema": SCHEMA_ID,
        "id": decision_id,
        "recorded_at": recorded_at.isoformat(),
        "recorded_via": dict(recorded_via),
        "question": question.strip(),
        "as_of": as_of.isoformat(),
        "currency": currency,
        "basis": dict(basis),
        "principles": [p.view() for p in principles],
        "baseline": dict(baseline),
        "options": [dict(o) for o in options],
        "chosen": chosen,
        "reasons": reasons.strip(),
        "agent_summary": None
        if not agent_summary or not agent_summary.strip()
        else {"text": agent_summary.strip(), "author": "agent", "agent": agent},
        "review_on": review_on.isoformat(),
    }


def note(
    *,
    note_id: str,
    decision_id: str,
    entry_hash: str,
    at: dt.datetime,
    text: str,
    author: Author,
    agent: str | None = None,
) -> dict[str, Any]:
    """A note appended to an entry."""
    return {
        "schema": NOTE_SCHEMA,
        "id": note_id,
        "decision_id": decision_id,
        "entry_hash": entry_hash,
        "at": at.isoformat(),
        "text": text.strip(),
        "author": author,
        "agent": agent if author == "agent" else None,
    }


def review(
    *,
    review_id: str,
    decision_id: str,
    entry_hash: str,
    at: dt.datetime,
    as_of: dt.date,
    reflection: str,
    comparison: Mapping[str, Any],
    author: Author,
    agent: str | None = None,
) -> dict[str, Any]:
    """A review appended to an entry: the person's reflection, and Salli's
    comparison of what was projected with what happened."""
    return {
        "schema": REVIEW_SCHEMA,
        "id": review_id,
        "decision_id": decision_id,
        "entry_hash": entry_hash,
        "at": at.isoformat(),
        "as_of": as_of.isoformat(),
        "reflection": reflection.strip(),
        "author": author,
        "agent": agent if author == "agent" else None,
        "comparison": dict(comparison),
    }


def digest(document: Mapping[str, Any]) -> str:
    """The content hash of an entry, a note or a review."""
    return canonical.digest(document)


def verify(document: Mapping[str, Any], expected: str) -> bool:
    """Whether `document` is the one `expected` was the hash of."""
    return digest(document) == expected


# ── Export ───────────────────────────────────────────────────────────────────


def export(records: Sequence[Mapping[str, Any]], exported_at: dt.datetime) -> dict[str, Any]:
    """The journal as one JSON document: every entry exactly as recorded,
    with its notes and reviews, each with its hash."""
    return {
        "schema": EXPORT_SCHEMA,
        "exported_at": exported_at.isoformat(),
        "verify": VERIFY,
        "entries": [
            {
                "entry": r["entry"],
                "hash": r["hash"],
                "notes": [{"note": n["note"], "hash": n["hash"]} for n in r["notes"]],
                "reviews": [{"review": v["review"], "hash": v["hash"]} for v in r["reviews"]],
            }
            for r in records
        ],
    }


_KEY_FIGURES = (
    ("lowest_cash", "Lowest cash, next 12 months"),
    ("emergency_months", "Emergency months at the low"),
    ("net_worth_1y", "Net worth in 1 year (today's money)"),
    ("net_worth_5y", "Net worth in 5 years (today's money)"),
    ("net_worth_10y", "Net worth in 10 years (today's money)"),
    ("total_interest", "Interest on debts"),
    ("debt_free_months", "Months to debt-free"),
    ("fi_months", "Months to FI"),
)

_FIGURE_NAMES = {
    "cash": "Cash",
    "investments": "Investments",
    "owed": "Owed",
    "net_worth": "Net worth",
}


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _quote(text: str) -> list[str]:
    return [f"> {line}" if line else ">" for line in text.splitlines() or [""]]


def _line(text: str) -> str:
    return " ".join(text.split())


def _entry_markdown(r: Mapping[str, Any]) -> list[str]:
    e: Mapping[str, Any] = r["entry"]
    currency = e["currency"]
    options: list[Mapping[str, Any]] = e["options"]
    out = [
        f"## {_line(e['question'])}",
        "",
        f"Recorded {e['recorded_at'][:10]}, as of {e['as_of']}, in {currency}. "
        f"Chosen: **{_line(e['chosen'])}**. Review on {e['review_on']}.",
        "",
        "**Reasons, in the person's words**",
        "",
        *_quote(e["reasons"]),
        "",
    ]
    summary = e.get("agent_summary")
    if summary:
        who = f" ({_line(summary['agent'])})" if summary.get("agent") else ""
        out += [f"**The agent's summary**{who}, written by the agent, not the person", ""]
        out += [*_quote(summary["text"]), ""]

    header = ["Figure", "Baseline", *(_cell(o["label"]) for o in options)]
    out += ["### The options", "", "| " + " | ".join(header) + " |"]
    out.append("|" + "---|" * len(header))
    for name, label in _KEY_FIGURES:
        row = [
            label,
            _cell(e["baseline"]["figures"].get(name)),
            *(_cell(o["figures"].get(name)) for o in options),
        ]
        out.append("| " + " | ".join(row) + " |")
    out.append("")
    for o in options:
        changes = o["scenario"].get("changes", [])
        out.append(
            f"- **{_line(o['label'])}**: {len(changes)} change{'s' if len(changes) != 1 else ''}; "
            f"scenario hash `{o['scenario_hash']}`"
        )
    out.append("")

    if e["principles"]:
        header = ["Principle", "Baseline", *(_cell(o["label"]) for o in options)]
        out += ["### Principles", "", "| " + " | ".join(header) + " |"]
        out.append("|" + "---|" * len(header))
        for i, p in enumerate(e["principles"]):
            row = [
                f"{_cell(p['label'])} (`{_cell(p['check'])}`)",
                e["baseline"]["principles"][i]["status"],
                *(o["principles"][i]["status"] for o in options),
            ]
            out.append("| " + " | ".join(row) + " |")
        out.append("")

    b = e["basis"]
    placeholders = ", ".join(b["placeholders"]) or "none"
    out += [
        f"Assumptions that were placeholders: {placeholders}. Engine {b['versions']['engine']}; "
        f"baseline `{b['baseline_fingerprint']}`"
        + (f"; the ledger's newest entry was from {b['data_as_of']}" if b["data_as_of"] else "")
        + ".",
        "",
    ]

    if r["notes"]:
        out += ["### Notes", ""]
        for n in r["notes"]:
            note_doc = n["note"]
            who = "the agent" if note_doc["author"] == "agent" else "the person"
            out.append(f"- {note_doc['at'][:10]} ({who}): {_line(note_doc['text'])}")
        out.append("")

    for v in r["reviews"]:
        doc = v["review"]
        c = doc["comparison"]
        out += [
            f"### Review of {doc['at'][:10]}",
            "",
            f"What {_line(c['option'])} projected for {c['at']}, against what happened "
            f"(in {c['currency']}, each day's own money):",
            "",
            "| | Projected | Actual | Difference |",
            "|---|---|---|---|",
        ]
        for row in c["figures"]:
            out.append(
                f"| {_FIGURE_NAMES.get(row['figure'], row['figure'])} | {row['projected']} | "
                f"{row['actual']} | {row['difference']} |"
            )
        s = c["spending"]
        if s["months"]:
            out.append(
                f"| Spending a month ({s['months'][0]} to {s['months'][-1]}) | {s['projected']} "
                f"| {s['actual']} | {s['difference']} |"
            )
        out += ["", "**Reflection**", "", *_quote(doc["reflection"]), ""]
        out += [f"Review hash `{v['hash']}`", ""]

    out += [f"Entry hash `{r['hash']}`", ""]
    return out


def markdown(records: Sequence[Mapping[str, Any]], exported_at: dt.datetime) -> str:
    """The journal as plain text: each entry, its options' key figures and
    principles, the reasons, notes and reviews, and every hash."""
    out = [
        "# Decision journal",
        "",
        f"Exported {exported_at.isoformat()}. Every figure is Salli's, as recorded; the JSON "
        "export holds each document exactly, and its hash shows it is unchanged. " + VERIFY,
        "",
    ]
    if not records:
        out += ["No decisions recorded yet.", ""]
    for r in records:
        out += _entry_markdown(r)
    return "\n".join(out).rstrip("\n") + "\n"
