"""
The monthly briefing: Salli's own figures and signals, narrated. Pure apart
from the one model call in `narrate`.

The model never writes a number. It writes sentences with slots, `{spending}`,
and Salli fills each slot with its own figure (`fill`), so every amount, rate
and month in a briefing is the engine's. It says where things stand and what
Salli's signals point at, and gives no advice: no recommendation, no
priority, no product, no rate it looked up.

`check` refuses a draft that writes a digit, names a slot Salli has not, or
uses a word that advises, ranks, presses or names a kind of product. The model
is asked once more with the reason; a second refusal is an unreadable answer.
"""

from __future__ import annotations

import calendar
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field

from salli.domain.agents.style import WRITING_STYLE
from salli.domain.currency import format_amount

Topic = Literal["cash", "spending", "saving", "debt", "independence", "goals", "assumptions"]

#: Who wrote a briefing's words, on every briefing the API shows.
WRITTEN_BY = "ai"
#: Shown under every briefing, wherever it is read.
NOTICE = "Written by an AI from Salli's own figures. Not financial advice."

BRIEFING_PROMPT = (
    """You write a person's monthly money briefing for Salli. You describe; you never advise.

You are given:
- `figures`: Salli's own figures, each under a slot name, with a label and its value.
- `signals`: what Salli's own checks noticed, in Salli's words.
- `assumptions`: whether the independence figures rest on the person's own planning
  assumptions or on placeholders (round stand-ins, not forecasts).

Write:
- `summary`: two or three sentences on where things stand this month.
- `notes`: up to six, each one or two sentences on one topic: cash, spending, saving, debt,
  independence, goals or assumptions. Leave out a topic with nothing to say.

Rules:
- Never write a digit. Every amount, rate, month or count goes in as its slot, in braces,
  exactly as named: "You spent {spending} a month on average." Use only the slots given.
- Describe only what the figures and signals show. No recommendation, no next step, no
  priority, nothing the person should, must or could do, and no kind of investment, product,
  account or rate. Salli does not give financial advice.
- Do not judge: no best, better, worse, good or bad, and nothing about a score.
- When `assumptions.status` is `placeholder`, say once that the independence figures rest on
  placeholders, not forecasts.
- A signal's words are Salli's: refer to what it noticed, without repeating any number in it.
- Plain and calm. No exclamation marks.

"""
    + WRITING_STYLE
)


class Note(BaseModel):
    topic: Topic
    text: str = Field(description="One or two sentences, every figure as a {slot}")


class Draft(BaseModel):
    """What the model writes: sentences with slots, never numbers."""

    summary: str = Field(description="Two or three sentences, every figure as a {slot}")
    notes: list[Note] = Field(default_factory=list[Note], max_length=6)


#: A figure a briefing may name: its label and its value as a person reads it.
Figure = Mapping[str, str]


@dataclass(frozen=True)
class Briefing:
    """A briefing with Salli's figures in it: what a person reads."""

    summary: str
    notes: tuple[tuple[Topic, str], ...]


# ── Salli's figures ──────────────────────────────────────────────────────────


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _percent(value: object) -> str | None:
    """A fraction as a percentage to one place: "0.4907" is "49.1%"."""
    number = _decimal(value)
    if number is None:
        return None
    shown = (number * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{shown.normalize():f}%" if shown == shown.to_integral() else f"{shown}%"


def _month(value: object) -> str | None:
    """ "2042-05" as "May 2042"."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}", value):
        return None
    year, month = value.split("-")
    if not 1 <= int(month) <= 12:
        return None
    return f"{calendar.month_name[int(month)]} {year}"


def figures_of(
    score: Mapping[str, Any],
    projections: Mapping[str, Any],
    goals: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, str]]:
    """The figures a briefing may name, from what the FI service computed:
    each under its slot, with a label and its value as a person reads it."""
    currency = str(score.get("currency") or projections.get("currency") or "")
    out: dict[str, dict[str, str]] = {}

    def amount(slot: str, label: str, value: object) -> None:
        number = _decimal(value)
        if number is not None and currency:
            out[slot] = {"label": label, "value": format_amount(number, currency, strict=False)}

    def put(slot: str, label: str, value: str | None) -> None:
        if value is not None:
            out[slot] = {"label": label, "value": value}

    amount("income", "Income a month, on average", score.get("monthly_income"))
    amount("spending", "Spending a month, on average", score.get("monthly_expenses"))
    amount("surplus", "Left over a month, on average", score.get("monthly_surplus"))
    put("savings_rate", "Share of income left over", _percent(score.get("savings_rate")))
    cover = _decimal(score.get("emergency_fund_months"))
    if cover is not None:
        months = cover.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        put("cash_cover", "Months of spending your cash covers", f"{months} months")
    amount("net_worth", "Net worth", score.get("net_worth"))
    amount("invested", "Cash and investments, less debts", score.get("fi_asset_base"))
    amount("fi_number", "FI number", score.get("fi_number"))
    put("fi_progress", "Of the way to the FI number", _percent(score.get("progress_to_fi")))
    put("fi_month", "When FI is reached at this pace", _month(score.get("projected_fi_month")))
    fi_by = projections.get("fi_by") or {}
    for key, slot, label in (
        ("conservative", "fi_month_cautious", "When FI is reached at the cautious return"),
        ("growth", "fi_month_growth", "When FI is reached at the growth return"),
    ):
        reached = fi_by.get(key) if isinstance(fi_by, Mapping) else None
        if isinstance(reached, Mapping):
            put(slot, label, _month(reached.get("month")))
    for n, goal in enumerate(goals, start=1):
        name = str(goal.get("name") or "")
        put(f"goal_{n}", "A goal's name", name or None)
        amount(f"goal_{n}_saved", f"Held for {name}", goal.get("current_amount"))
        amount(f"goal_{n}_target", f"Target for {name}", goal.get("target_amount"))
        put(f"goal_{n}_progress", f"Of the way to {name}", _percent(goal.get("progress")))
    return out


# ── Checking and filling a draft ─────────────────────────────────────────────

SLOT = re.compile(r"\{([a-z0-9_]+)\}")
#: Words that advise, rank, judge or press. The briefing describes.
ADVICE = re.compile(
    r"\b(should|ought|must|need to|needs to|recommend\w*|suggest\w*|consider\w*|advis\w*|"
    r"best|better|worse|worst|optimal|ideal|good|bad|great|poor|excellent|healthy|"
    r"unhealthy|worrying|concerning|impressive|well done|priorit\w*|rank\w*|scor\w*|"
    r"urgent\w*|pressing|make sure|try to|aim to|focus on|time to|(?<!net )worth|you could|"
    r"you may want|you might|it would help|it may help|it might help|wise|smart|opportunit\w*)\b",
    re.IGNORECASE,
)
#: A sentence that starts with an instruction ("Pay down the card.").
INSTRUCTION = re.compile(
    r"(?:^|[.;:]\s+)(pay|move|cut|save|invest|put|open|close|switch|reduce|increase|raise|"
    r"lower|start|stop|avoid|keep|build|set|try|look|think|plan|shift|transfer|spend|"
    r"sell|buy|use|boost|trim|redirect|review|check)\b",
    re.IGNORECASE,
)
#: Numbers written as words: a figure is a slot, however it is spelled.
NUMBER_WORDS = re.compile(
    r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|"
    r"fifty|sixty|seventy|eighty|ninety|hundred\w*|thousand\w*|million\w*|billion\w*|"
    r"half|halves|quarters?|third|double|doubled|twice|triple|percent|per cent)\b",
    re.IGNORECASE,
)
#: Kinds of product: a briefing names none ("emergency fund" is not one).
PRODUCTS = re.compile(
    r"\b(index funds?|mutual funds?|etfs?|stocks?|shares|equities|bonds?|gilts?|"
    r"fixed deposits?|term deposits?|certificates? of deposit|savings accounts?|"
    r"t-?bills?|treasur\w*|annuit\w*|pensions?|crypto\w*|bitcoin|gold|property|"
    r"real estate|high[- ]yield|money market|(?<!emergency )funds?)\b",
    re.IGNORECASE,
)


def _texts(draft: Draft) -> list[str]:
    return [draft.summary, *(n.text for n in draft.notes)]


def check(draft: Draft, figures: Mapping[str, object]) -> str | None:
    """Why `draft` breaks the briefing's rules, or None when it keeps them."""
    for text in _texts(draft):
        unknown = [s for s in SLOT.findall(text) if s not in figures]
        if unknown:
            return f"It names slots Salli has not: {', '.join(sorted(set(unknown)))}."
        words = SLOT.sub("", text)
        if re.search(r"\d", words):
            return "It writes a number itself instead of using a slot."
        # The reason never repeats the word it caught: echoed back, it
        # teaches the model what to spell around.
        if ADVICE.search(words) or INSTRUCTION.search(words):
            return "It advises, instructs or judges: describe only."
        if NUMBER_WORDS.search(words):
            return "It writes a number in words instead of using a slot."
        if PRODUCTS.search(words):
            return "It names a kind of product or account: name none."
        if "!" in words:
            return "It uses an exclamation mark."
    return None


def fill(text: str, figures: Mapping[str, Figure]) -> str:
    """`text` with each slot replaced by Salli's figure."""
    return SLOT.sub(lambda m: figures[m.group(1)]["value"], text)


def briefing_of(draft: Draft, figures: Mapping[str, Figure]) -> Briefing:
    return Briefing(
        summary=fill(draft.summary, figures),
        notes=tuple((n.topic, fill(n.text, figures)) for n in draft.notes),
    )


def view(draft: Draft, context: Mapping[str, Any]) -> dict[str, Any]:
    """A draft as it is stored and shown: the summary and notes with Salli's
    figures in them, and the figures, signals and assumptions it was written
    from."""
    figures: Mapping[str, Figure] = context.get("figures") or {}
    filled = briefing_of(draft, figures)
    return {
        "summary": filled.summary,
        "briefing": {
            "notes": [{"topic": topic, "text": text} for topic, text in filled.notes],
            "figures": dict(figures),
            "signals": list(context.get("signals") or []),
            "assumptions": dict(context.get("assumptions") or {}),
        },
    }


# ── The model call ───────────────────────────────────────────────────────────


async def narrate(context: Mapping[str, Any], *, llm: Any) -> Draft:
    """The model's draft for `context` (its `figures`, `signals` and
    `assumptions`), checked: asked once more, with the reason, when the first
    breaks the rules. `llm` is the user's resolved LLMClient
    (application/ports.py)."""
    from pydantic import ValidationError

    from salli.domain.llm import LLMUnreadableAnswer, parse_json_answer

    figures: Mapping[str, Figure] = context.get("figures") or {}
    payload = json.dumps(context, indent=2, default=str)
    ask = f"Here is this month's picture:\n\n{payload}\n\nWrite the briefing."
    reason: str | None = None
    for _ in range(2):
        text = await llm.generate(
            instructions=BRIEFING_PROMPT,
            input=ask if reason is None else f"{ask}\n\nYour last draft was refused: {reason}",
            tier="best",
            schema=Draft,
            temperature=0.2,
            max_output_tokens=1200,
        )
        try:
            draft = Draft.model_validate(parse_json_answer(text))
        except ValidationError as exc:
            raise LLMUnreadableAnswer(
                "The briefing the AI wrote could not be read. Please try again."
            ) from exc
        reason = check(draft, figures)
        if reason is None:
            return draft
    raise LLMUnreadableAnswer(
        "The briefing the AI wrote gave advice or wrote its own figures, which Salli "
        "doesn't allow. Please try again."
    )
