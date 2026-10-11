"""
PrincipleService — the user's own rules of thumb (domain/decisions,
docs/decisions.md): kept, edited, archived, and checked against options.

A principle is a preference, not a record: it can be edited (its version
counts up) and archived, never deleted, and a decision records each one as
it stood. Every write is validated first (`principles.validate`): an
unknown figure, a check that isn't true or false, an account it needs and
lacks are each a problem with its path. An account a principle names must
be one of the caller's own cash accounts (anyone else's is not found, as
one that doesn't exist is).

Checking runs each option (a `salli.scenario/1` document) on the user's
baseline, as `ScenarioService` does, and reports for the baseline and each
option which principles it keeps, breaks, or can't tell, with the figures
each check read. Never a ranking, and nothing is stored.

An agent may suggest a principle; only the user's confirmation stores one
(the MCP tool requires it, docs/decisions.md).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from salli.application.ownership import require_own_accounts
from salli.application.ports import PrincipleNotFound
from salli.application.services.scenario_service import ScenarioService, load_scenario
from salli.domain.baseline.models import Baseline
from salli.domain.decisions import figures as figure_set
from salli.domain.decisions import journal
from salli.domain.decisions.principles import (
    MAX_ACTIVE,
    SCHEMA_ID,
    Principle,
    PrincipleError,
    content_hash,
    validate,
)
from salli.domain.scenarios import engine, schema
from salli.domain.scenarios.engine import Evaluated, Outlook, ScenarioError
from salli.domain.taxrules.common import Problem, join_path

#: At most this many options are checked at once.
MAX_OPTIONS = 5


def _when(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, dt.datetime | dt.date) else str(value)


def principle_of(row: Mapping[str, Any]) -> Principle:
    return Principle(row["label"], row["check"], row.get("account"), row.get("note"))


def principle_view(row: Mapping[str, Any]) -> dict[str, Any]:
    """A stored principle as JSON-ready data."""
    principle = principle_of(row)
    return {
        "schema": SCHEMA_ID,
        "id": row["id"],
        "label": principle.label,
        "check": principle.check,
        "account": principle.account,
        "note": principle.note,
        "version": row["version"],
        "hash": content_hash(principle),
        "author": row["author_kind"],
        "agent": row.get("author_name"),
        "status": "archived" if row.get("archived_at") else "active",
        "created_at": _when(row["created_at"]),
        "updated_at": _when(row["updated_at"]),
        "archived_at": _when(row.get("archived_at")),
    }


@dataclass(frozen=True)
class OptionsOutlook:
    """A baseline and a set of options run on it: the baseline's outlook
    and figures, and each option's result, outlook and figures."""

    baseline: Baseline
    base: Outlook
    base_figures: figure_set.Figures
    options: tuple[tuple[Evaluated, figure_set.Figures], ...]


def evaluate_options(baseline: Baseline, scenarios: Sequence[schema.Scenario]) -> OptionsOutlook:
    """Each scenario on `baseline`, and the figures principles read, for it
    and for the baseline itself."""
    base = engine.baseline_outlook(baseline)
    out: list[tuple[Evaluated, figure_set.Figures]] = []
    for i, scenario in enumerate(scenarios):
        try:
            _, evaluated = engine.run_with_outlook(baseline, scenario, base=base)
        except ScenarioError as error:
            raise ScenarioError(
                [
                    Problem(join_path("options", i) + "." + p.path, p.message, p.snippet)
                    for p in error.problems
                ]
            ) from None
        loans = evaluated.translation.changes.loans
        out.append((evaluated, figure_set.compute(baseline, evaluated.outlook, base, loans)))
    return OptionsOutlook(baseline, base, figure_set.compute(baseline, base, base), tuple(out))


def load_options(options: Sequence[schema.Scenario | Mapping[str, Any]]) -> list[schema.Scenario]:
    """Each option as a validated scenario, or ScenarioError with every
    problem under `options[n]`."""
    scenarios: list[schema.Scenario] = []
    problems: list[Problem] = []
    for i, data in enumerate(options):
        try:
            scenarios.append(load_scenario(data, option=i))
        except ScenarioError as error:
            problems += error.problems
    if problems:
        raise ScenarioError(problems)
    return scenarios


class PrincipleService:
    def __init__(self, uow_factory: Callable[[], Any], scenarios: ScenarioService) -> None:
        self._uow_factory = uow_factory
        self._scenarios = scenarios

    @staticmethod
    def figures() -> dict[str, Any]:
        """The figures a check may read, each with its unit and terms."""
        return {"figures": figure_set.specs_view()}

    async def list(self, user_id: str, include_archived: bool = False) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            rows = await uow.principles.list(user_id, include_archived)
        return {"principles": [principle_view(r) for r in rows]}

    async def get(self, user_id: str, principle_id: str) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            row = await uow.principles.get(user_id, principle_id)
        if row is None:
            raise PrincipleNotFound(principle_id)
        return principle_view(row)

    async def _check_account(self, uow: Any, user_id: str, account: str | None) -> None:
        """AccountNotFound unless it is the user's; PrincipleError unless it
        is a cash account (what `account_lowest` reads)."""
        if not account:
            return
        await require_own_accounts(uow, user_id, [account])
        found = await uow.ledger.get_account(user_id, account)
        if found is None or found.type != "asset" or getattr(found, "asset_role", None) != "cash":
            name = found.name if found is not None else account
            raise PrincipleError([Problem("account", f"{name} is not one of your cash accounts")])

    async def add(
        self,
        user_id: str,
        data: Mapping[str, Any],
        *,
        author: journal.Author = "user",
        agent: str | None = None,
    ) -> dict[str, Any]:
        """Store a principle the user wrote (or confirmed: `author` "agent"
        when their agent wrote it)."""
        principle = Principle(
            label=str(data.get("label") or "").strip(),
            check=str(data.get("check") or ""),
            account=data.get("account") or None,
            note=(str(data["note"]).strip() or None) if data.get("note") else None,
        )
        validate(principle)
        async with self._uow_factory() as uow:
            await self._check_account(uow, user_id, principle.account)
            if len(await uow.principles.list(user_id)) >= MAX_ACTIVE:
                raise PrincipleError(
                    [
                        Problem(
                            "$",
                            f"You have {MAX_ACTIVE} principles in use, the most there can be: "
                            "archive one first",
                        )
                    ]
                )
            row = await uow.principles.add(
                user_id,
                {
                    "label": principle.label,
                    "check": principle.check,
                    "account": principle.account,
                    "note": principle.note,
                    "author_kind": author,
                    "author_name": agent if author == "agent" else None,
                },
            )
        return principle_view(row)

    async def update(
        self, user_id: str, principle_id: str, changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Edit a principle in use: its label, check, account or note (those
        `changes` names; a null account or note removes it)."""
        unknown = set(changes) - {"label", "check", "account", "note"}
        if unknown:
            raise PrincipleError(
                [Problem(k, "is not a field of a principle") for k in sorted(unknown)]
            )
        async with self._uow_factory() as uow:
            row = await uow.principles.get(user_id, principle_id)
            if row is None:
                raise PrincipleNotFound(principle_id)
            if row.get("archived_at"):
                raise PrincipleError(
                    [Problem("$", "is archived: add it again to use it, rather than edit it")]
                )
            current = principle_of(row)
            note = current.note
            if "note" in changes:
                note = str(changes["note"] or "").strip() or None
            edited = Principle(
                label=str(changes["label"] or "").strip() if "label" in changes else current.label,
                check=str(changes["check"] or "") if "check" in changes else current.check,
                account=(changes["account"] or None) if "account" in changes else current.account,
                note=note,
            )
            validate(edited)
            await self._check_account(uow, user_id, edited.account)
            updated = await uow.principles.update(
                user_id,
                principle_id,
                {
                    "label": edited.label,
                    "check": edited.check,
                    "account": edited.account,
                    "note": edited.note,
                },
            )
        if updated is None:
            raise PrincipleNotFound(principle_id)
        return principle_view(updated)

    async def archive(self, user_id: str, principle_id: str) -> dict[str, Any]:
        """Stop checking against a principle. It stays, archived."""
        async with self._uow_factory() as uow:
            row = await uow.principles.archive(user_id, principle_id)
        if row is None:
            raise PrincipleNotFound(principle_id)
        return principle_view(row)

    async def in_use(self, user_id: str) -> list[journal.PrincipleInUse]:
        """The principles in use, compiled, oldest first. A stored principle
        whose check no longer compiles (the figure set never shrinks, so it
        shouldn't happen) is left out rather than failing every check."""
        async with self._uow_factory() as uow:
            rows = await uow.principles.list(user_id)
        out: list[journal.PrincipleInUse] = []
        for row in rows:
            principle = principle_of(row)
            try:
                expr = validate(principle)
            except PrincipleError:
                continue
            out.append(
                journal.PrincipleInUse(
                    row["id"], int(row["version"]), content_hash(principle), principle, expr
                )
            )
        return out

    async def check(
        self, user_id: str, options: Sequence[schema.Scenario | Mapping[str, Any]] = ()
    ) -> dict[str, Any]:
        """The user's principles against the baseline and each option (none
        to five scenarios): which each keeps, breaks or can't tell, with the
        figures it read. Never a ranking; stores nothing."""
        if len(options) > MAX_OPTIONS:
            raise ScenarioError(
                [Problem("options", f"checks at most {MAX_OPTIONS} options, not {len(options)}")]
            )
        scenarios = load_options(options)
        as_of = self._scenarios.as_of_for(scenarios, options=True)
        await self._scenarios.check_own(user_id, scenarios)
        in_use = await self.in_use(user_id)
        baseline = await self._scenarios.baselines.build(user_id, as_of)
        run = evaluate_options(baseline, scenarios)

        def block(figures: figure_set.Figures) -> dict[str, Any]:
            return {
                "figures": figure_set.view(figures),
                "unavailable": dict(figures.missing),
                "results": journal.checks_view(in_use, figures),
            }

        return {
            "as_of": baseline.as_of.isoformat(),
            "currency": baseline.currency,
            "principles": [p.view() for p in in_use],
            "baseline": block(run.base_figures),
            "options": [
                {
                    "label": evaluated.result.label or f"Option {i + 1}",
                    "scenario_hash": evaluated.result.hash,
                    **block(figures),
                }
                for i, (evaluated, figures) in enumerate(run.options)
            ],
            "placeholders": list(baseline.placeholders),
            "data_as_of": baseline.latest_entry,
        }
