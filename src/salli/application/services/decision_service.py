"""
DecisionService — the decision journal and its reviews (domain/decisions,
docs/decisions.md).

**Recording.** A decision arrives as the question, the options (one to five
`salli.scenario/1` documents, each with its own label), the option chosen,
the person's reasons in their words, an optional summary by their agent,
and a review date. Salli runs every option itself, on the user's baseline as
`ScenarioService` does (their own accounts and debts only; one as-of date,
never after today), checks it against their principles, and records the
entry with every figure, the projection a review will compare against, and
the content hash of the whole. The client never supplies a figure. A review
reminder is set for the review date (`source_domain` "decision").

**Append-only.** There is no way to edit or delete an entry, a note or a
review: not in this service, the repository or the database (core_0017).
A note or a review is a new document beside the entry, naming its hash.
Reading an entry hashes it again and says whether it still matches.

**Reviews.** From the review date on, a review compares what the chosen
option projected at the last month's end with the baseline as of that day
(`review.compare`): cash, investments, what is owed, net worth and the
average spending a month since. The person adds their reflection, and the
review is appended; the reminder is done. A decision whose review date has
come and that has no review is due (`due`), which the signals and the
reminders show too.

Every date the service needs is its clock's (injectable): today for the
baseline and what is due, now for when something was recorded.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable, Mapping
from typing import Any, Literal, cast

from salli.application.ports import DecisionNotFound
from salli.application.services.principle_service import (
    PrincipleService,
    evaluate_options,
    load_options,
)
from salli.application.services.scenario_service import ScenarioService
from salli.domain.decisions import figures as figure_set
from salli.domain.decisions import journal, projection, review
from salli.domain.decisions.journal import JournalError
from salli.domain.taxrules.common import Problem

#: `reminders.source_domain` and `alert_type` of a review reminder.
REVIEW_SOURCE = "decision"
REVIEW_ALERT = "decision_review"

Format = Literal["json", "markdown"]


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(microsecond=0)


def _day(value: Any, path: str) -> dt.date:
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise JournalError([Problem(path, "is not a date (YYYY-MM-DD)")]) from None


def _when(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, dt.date | dt.datetime) else str(value)


def _reminder_kind(question: str) -> str:
    text = " ".join(question.split())
    kind = f"Review your decision: {text}"
    return kind if len(kind) <= 500 else kind[:499] + "…"


class DecisionService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        scenarios: ScenarioService,
        principles: PrincipleService,
        now: Callable[[], dt.datetime] = _utc_now,
    ) -> None:
        self._uow_factory = uow_factory
        self._scenarios = scenarios
        self._principles = principles
        self._now = now

    def today(self) -> dt.date:
        return self._scenarios.today()

    # ── Recording ────────────────────────────────────────────────────────

    async def record(
        self,
        user_id: str,
        data: Mapping[str, Any],
        *,
        via: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Run every option, check the principles, and record the entry.
        `via` says how it was recorded (`{"channel": "api"}`, or MCP with the
        client's name and the person's confirmation)."""
        options: object = data.get("options") or []
        if not isinstance(options, list | tuple):
            raise JournalError([Problem("options", "is a list of scenarios")])
        scenarios = load_options(cast("list[Any]", options))
        as_of = self._scenarios.as_of_for(scenarios, options=True)
        review_on = _day(data.get("review_on"), "review_on")
        question = str(data.get("question") or "")
        chosen = str(data.get("chosen") or "")
        reasons = str(data.get("reasons") or "")
        summary = data.get("agent_summary")
        summary_text = str(summary) if summary is not None else None
        problems = journal.entry_problems(
            question=question,
            labels=[s.label for s in scenarios],
            chosen=chosen,
            reasons=reasons,
            agent_summary=summary_text,
            review_on=review_on,
            as_of=as_of,
            earliest_review=review.earliest_review(as_of),
        )
        if problems:
            raise JournalError(problems)
        await self._scenarios.check_own(user_id, scenarios)
        in_use = await self._principles.in_use(user_id)
        baseline = await self._scenarios.baselines.build(user_id, as_of)
        run = evaluate_options(baseline, scenarios)

        months = min(
            projection.months_to(as_of.isoformat(), review_on.isoformat())
            + 1
            + projection.AFTER_REVIEW_MONTHS,
            len(run.base.monthly.points) - 1,
        )
        snapshots = [
            journal.option_snapshot(
                evaluated.result,
                figures,
                journal.checks_view(in_use, figures),
                projection.projection(baseline, scenario, evaluated.outlook, months),
            )
            for scenario, (evaluated, figures) in zip(scenarios, run.options, strict=True)
        ]
        decision_id = str(uuid.uuid4())
        recorded_at = self._now()
        # Whose summary it is: the MCP client's own name, or as given.
        agent = via.get("client") if via.get("channel") == "mcp" else None
        if agent is None and isinstance(data.get("agent"), str):
            agent = str(data["agent"]).strip() or None
        content = journal.entry(
            decision_id=decision_id,
            recorded_at=recorded_at,
            recorded_via=via,
            question=question,
            as_of=as_of,
            currency=baseline.currency,
            basis=journal.basis(run.options[0][0].result),
            principles=in_use,
            baseline={
                "figures": figure_set.view(run.base_figures),
                "unavailable": dict(run.base_figures.missing),
                "principles": journal.checks_view(in_use, run.base_figures),
            },
            options=snapshots,
            chosen=chosen,
            reasons=reasons,
            agent_summary=summary_text,
            agent=agent,
            review_on=review_on,
        )
        digest = journal.digest(content)
        async with self._uow_factory() as uow:
            await uow.decisions.record(
                user_id,
                {
                    "id": decision_id,
                    "question": content["question"],
                    "chosen": chosen,
                    "currency": baseline.currency,
                    "as_of": as_of,
                    "review_on": review_on,
                    "recorded_at": recorded_at,
                    "content": content,
                    "hash": digest,
                },
            )
            await uow.reminders.upsert_alert(
                user_id,
                REVIEW_ALERT,
                REVIEW_SOURCE,
                decision_id,
                _reminder_kind(content["question"]),
                review_on.isoformat(),
                "info",
            )
        return self._entry_view(
            {
                "id": decision_id,
                "content": content,
                "hash": digest,
                "review_on": review_on,
                "notes": [],
                "reviews": [],
            }
        )

    # ── Reading ──────────────────────────────────────────────────────────

    def _entry_view(self, row: Mapping[str, Any]) -> dict[str, Any]:
        content: dict[str, Any] = row["content"]
        review_on = _day(row["review_on"], "review_on")
        return {
            "id": row["id"],
            "hash": row["hash"],
            "verified": journal.verify(content, row["hash"]),
            "status": self._status(review_on, len(row["reviews"])),
            "entry": content,
            "notes": [
                {
                    "note": n["content"],
                    "hash": n["hash"],
                    "verified": journal.verify(n["content"], n["hash"]),
                }
                for n in row["notes"]
            ],
            "reviews": [
                {
                    "review": v["content"],
                    "hash": v["hash"],
                    "verified": journal.verify(v["content"], v["hash"]),
                }
                for v in row["reviews"]
            ],
        }

    def _status(self, review_on: dt.date, reviews: int) -> str:
        if reviews:
            return "reviewed"
        return "review_due" if review_on <= self.today() else "awaiting_review"

    def _summary(self, row: Mapping[str, Any]) -> dict[str, Any]:
        review_on = _day(row["review_on"], "review_on")
        return {
            "id": row["id"],
            "question": row["question"],
            "chosen": row["chosen"],
            "currency": row["currency"],
            "as_of": _when(row["as_of"]),
            "review_on": review_on.isoformat(),
            "recorded_at": _when(row["recorded_at"]),
            "hash": row["hash"],
            "notes": row["notes"],
            "reviews": row["reviews"],
            "last_reviewed_at": _when(row.get("last_reviewed_at")),
            "status": self._status(review_on, int(row["reviews"])),
        }

    async def list(self, user_id: str) -> dict[str, Any]:
        """Every entry, newest first, without its documents."""
        async with self._uow_factory() as uow:
            rows = await uow.decisions.list(user_id)
        return {"decisions": [self._summary(r) for r in rows]}

    async def _row(self, user_id: str, decision_id: str) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            row = await uow.decisions.get(user_id, decision_id)
        if row is None:
            raise DecisionNotFound(decision_id)
        return row

    async def get(self, user_id: str, decision_id: str) -> dict[str, Any]:
        """An entry with its notes and reviews, each hashed again to show it
        is unchanged (`verified`)."""
        return self._entry_view(await self._row(user_id, decision_id))

    # ── Appending ────────────────────────────────────────────────────────

    async def add_note(
        self,
        user_id: str,
        decision_id: str,
        text: str,
        *,
        author: journal.Author = "user",
        agent: str | None = None,
    ) -> dict[str, Any]:
        """Append a note to an entry. The entry doesn't change."""
        problems = journal.text_problems("text", text, required=True)
        if problems:
            raise JournalError(problems)
        row = await self._row(user_id, decision_id)
        note_id = str(uuid.uuid4())
        at = self._now()
        content = journal.note(
            note_id=note_id,
            decision_id=decision_id,
            entry_hash=row["hash"],
            at=at,
            text=text,
            author=author,
            agent=agent,
        )
        digest = journal.digest(content)
        async with self._uow_factory() as uow:
            added = await uow.decisions.add_note(
                user_id,
                decision_id,
                {"id": note_id, "content": content, "hash": digest, "created_at": at},
            )
        if added is None:
            raise DecisionNotFound(decision_id)
        return {"note": content, "hash": digest, "verified": True}

    # ── Reviews ──────────────────────────────────────────────────────────

    async def _comparison(
        self, user_id: str, content: Mapping[str, Any], review_as_of: dt.date
    ) -> dict[str, Any]:
        """What the chosen option projected, against the baseline at the
        month's end the review compares at."""
        at, notes = review.compared_at(content, review_as_of)
        baselines = self._scenarios.baselines
        actual = await baselines.build(user_id, at)
        # The months spent through `at`'s own: a baseline as of the next day
        # has them all among its full months.
        spent = await baselines.build(user_id, at + dt.timedelta(days=1))
        compared = review.compare(content, at=at, actual=actual, spent=spent.flows.by_month)
        compared["notes"] = list(dict.fromkeys([*notes, *compared["notes"]]))
        return compared

    async def due(self, user_id: str, on: dt.date | None = None) -> dict[str, Any]:
        """The decisions due for review (their review date has come, and
        there is no review yet), soonest first, each with what its chosen
        option projected against what happened, for the person and their
        agent to go through. Stores nothing."""
        on = on or self.today()
        async with self._uow_factory() as uow:
            rows = await uow.decisions.due(user_id, on)
        out: list[dict[str, Any]] = []
        for summary in rows:
            row = await self._row(user_id, summary["id"])
            out.append(
                {
                    **self._summary(summary),
                    "reasons": row["content"]["reasons"],
                    "comparison": await self._comparison(user_id, row["content"], on),
                }
            )
        return {"as_of": on.isoformat(), "reviews": out}

    async def review(
        self,
        user_id: str,
        decision_id: str,
        reflection: str,
        *,
        as_of: dt.date | None = None,
        author: journal.Author = "user",
        agent: str | None = None,
    ) -> dict[str, Any]:
        """Append a review: the person's reflection, and Salli's comparison
        as of `as_of` (today when None; from the review date, never after
        today). The entry doesn't change; the reminder is done."""
        today = self.today()
        on = as_of or today
        problems = journal.text_problems("reflection", reflection, required=True)
        if on > today:
            problems.append(Problem("as_of", f"can't be after today ({today.isoformat()})"))
        row = await self._row(user_id, decision_id)
        content: dict[str, Any] = row["content"]
        review_on = _day(content["review_on"], "review_on")
        if on < review_on:
            problems.append(
                Problem(
                    "as_of",
                    f"is before the review date ({review_on.isoformat()}): the decision can be "
                    "reviewed from then on",
                )
            )
        if problems:
            raise JournalError(problems)
        comparison = await self._comparison(user_id, content, on)
        review_id = str(uuid.uuid4())
        at = self._now()
        document = journal.review(
            review_id=review_id,
            decision_id=decision_id,
            entry_hash=row["hash"],
            at=at,
            as_of=on,
            reflection=reflection,
            comparison=comparison,
            author=author,
            agent=agent,
        )
        digest = journal.digest(document)
        async with self._uow_factory() as uow:
            added = await uow.decisions.add_review(
                user_id,
                decision_id,
                {
                    "id": review_id,
                    "as_of": on,
                    "content": document,
                    "hash": digest,
                    "created_at": at,
                },
            )
            if added is None:
                raise DecisionNotFound(decision_id)
            reminder = await uow.reminders.upsert_alert(
                user_id,
                REVIEW_ALERT,
                REVIEW_SOURCE,
                decision_id,
                _reminder_kind(content["question"]),
                review_on.isoformat(),
                "info",
            )
            await uow.reminders.mark_done(user_id, reminder)
        return {"review": document, "hash": digest, "verified": True}

    # ── Export ───────────────────────────────────────────────────────────

    async def export(
        self, user_id: str, fmt: Format = "json", decision_id: str | None = None
    ) -> dict[str, Any] | str:
        """The journal (or one entry) as JSON, every document exactly as
        recorded with its hash, or as Markdown to read."""
        if decision_id is not None:
            rows = [await self._row(user_id, decision_id)]
        else:
            async with self._uow_factory() as uow:
                rows = await uow.decisions.list_full(user_id)
        records = [
            {
                "entry": r["content"],
                "hash": r["hash"],
                "notes": [{"note": n["content"], "hash": n["hash"]} for n in r["notes"]],
                "reviews": [{"review": v["content"], "hash": v["hash"]} for v in r["reviews"]],
            }
            for r in rows
        ]
        now = self._now()
        if fmt == "markdown":
            return journal.markdown(records, now)
        return journal.export(records, now)
