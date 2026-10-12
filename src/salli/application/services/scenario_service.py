"""
ScenarioService — runs and compares the decision lab's scenarios
(domain/scenarios, docs/scenarios.md) on a user's baseline.

It reads and never writes: a scenario is the baseline plus changes,
evaluated in memory, and nothing about it is stored. The service does what
the pure engine can't:

- **Whose ids.** Every account, debt and holding a change names must be the
  caller's own: an account checked as every write in Salli checks one
  (`ownership.require_own_accounts`), a debt among their active debts, a
  holding among their holdings. Anything else is "not found"
  (AccountNotFound, DebtNotFound, HoldingNotFound), the same for one that
  doesn't exist and one that is someone else's: no security the caller
  doesn't hold gets into a scenario.
- **Whose tax roles.** A change's `tax_role` must be a role one of the
  caller's rule sets declares (any version still in use, active or not), of
  kind income or deduction (a sale's, of kind income: its realised gain):
  anything else is a problem at its path, as a mistyped id is. Whether active rules compute it is the engine's to say.
- **Which day.** The baseline is built as of the scenario's `as_of` (today
  by this service's clock when it has none), never a day after today; the
  options of a comparison share one.
- **The document.** A scenario arrives as the validated model (the API's
  typed body) or as plain data (an MCP tool's); plain data is validated by
  the same model, its problems reported with paths.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from salli.application.ownership import require_own_accounts
from salli.application.ports import DebtNotFound, HoldingNotFound
from salli.application.services.baseline_service import BaselineService
from salli.domain.scenarios import comparison, engine, schema, views
from salli.domain.scenarios.engine import ScenarioError
from salli.domain.taxrules.common import Problem, join_path


def accounts_named(scenarios: Iterable[schema.Scenario]) -> set[str]:
    """Every account id a change names."""
    named: set[str] = set()
    for scenario in scenarios:
        for change in scenario.changes:
            match change:
                case schema.OneOffChange() | schema.RecurringChange():
                    account = change.account
                case schema.LoanChange():
                    account = change.into
                case schema.InvestChange() | schema.AssetChange():
                    account = change.from_
                case schema.SellChange():
                    account = change.into
                case _:
                    account = None
            if account:
                named.add(account)
    return named


def tax_roles_named(scenarios: Sequence[schema.Scenario]) -> list[tuple[int, int, str]]:
    """(option, change, role) for every change tagged with a tax role."""
    return [
        (n, i, change.tax_role)
        for n, scenario in enumerate(scenarios)
        for i, change in enumerate(scenario.changes)
        if isinstance(change, schema.TAGGABLE) and change.tax_role is not None
    ]


def debts_named(scenarios: Iterable[schema.Scenario]) -> set[str]:
    """Every debt id a change names."""
    return {
        change.debt
        for scenario in scenarios
        for change in scenario.changes
        if isinstance(change, schema.ExtraDebtPaymentChange)
    }


def holdings_named(scenarios: Iterable[schema.Scenario]) -> set[str]:
    """Every holding id a change names."""
    return {
        change.holding
        for scenario in scenarios
        for change in scenario.changes
        if isinstance(change, schema.WITH_HOLDING) and change.holding is not None
    }


def load_scenario(
    data: schema.Scenario | Mapping[str, Any], option: int | None = None
) -> schema.Scenario:
    """`data` as a validated scenario, or ScenarioError with each problem's
    path (under `options[n]` for a comparison's option)."""
    if isinstance(data, schema.Scenario):
        return data
    try:
        return schema.load(data)
    except ValidationError as error:
        raise ScenarioError(schema.problems(error, option=option)) from None


class ScenarioService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        baselines: BaselineService | None = None,
        today: Callable[[], dt.date] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._baselines = baselines or BaselineService(uow_factory, today=today or dt.date.today)
        self._today = today or self._baselines.today

    def today(self) -> dt.date:
        return self._today()

    @property
    def baselines(self) -> BaselineService:
        return self._baselines

    @staticmethod
    def schema() -> dict[str, Any]:
        """The scenario document's JSON Schema, for agents writing one."""
        return schema.json_schema()

    async def check_own(self, user_id: str, scenarios: Sequence[schema.Scenario]) -> None:
        """AccountNotFound / DebtNotFound / HoldingNotFound unless every id
        the changes name is the user's own (an active debt, for a debt)."""
        debts = debts_named(scenarios)
        holdings = holdings_named(scenarios)
        tagged = tax_roles_named(scenarios)
        async with self._uow_factory() as uow:
            await require_own_accounts(uow, user_id, accounts_named(scenarios))
            if debts:
                mine = {str(d["id"]) for d in await uow.debts.list(user_id, active_only=True)}
                if debts - mine:
                    raise DebtNotFound(debts - mine)
            if holdings:
                held = {str(h["id"]) for h in await uow.holdings.list(user_id, active_only=False)}
                if holdings - held:
                    raise HoldingNotFound(holdings - held)
            kinds: dict[str, set[str]] = (
                await uow.tax_rule_sets.declared_role_kinds(user_id) if tagged else {}
            )
        problems: list[Problem] = []
        many = len(scenarios) > 1
        for n, i, role in tagged:
            path = join_path(*(["options", n] if many else []), "changes", i, "tax_role")
            declared = kinds.get(role)
            if not declared:
                problems.append(
                    Problem(
                        path,
                        f"{role!r} is not a role any of your tax rule sets declares: "
                        "`salli tax rules list` shows your rule sets, and their roles",
                    )
                )
            elif (
                isinstance(scenarios[n].changes[i], schema.SellChange) and "income" not in declared
            ):
                problems.append(
                    Problem(
                        path,
                        f"{role} is a role of kind {sorted(declared)[0]} in your tax rules: a "
                        "sale's realised gain goes to an income role",
                    )
                )
            elif not declared & {"income", "deduction"}:
                problems.append(
                    Problem(
                        path,
                        f"{role} is a role of kind {sorted(declared)[0]} in your tax rules: "
                        "only income and deduction roles can be tagged",
                    )
                )
        if problems:
            raise ScenarioError(problems)

    def as_of_for(self, scenarios: Sequence[schema.Scenario], *, options: bool = False) -> dt.date:
        """The day the baseline is as of: the scenarios' (one day, for every
        option that gives one), or today; never after today. `options`: the
        scenarios are a request's `options`, so problems are under it."""
        today = self._today()
        given = sorted({s.as_of for s in scenarios if s.as_of is not None})
        problems: list[Problem] = []
        many = len(scenarios) > 1 or options
        for i, s in enumerate(scenarios):
            at = join_path("options", i, "as_of") if many else "as_of"
            if s.as_of is not None and s.as_of > today:
                problems.append(Problem(at, f"can't be after today ({today.isoformat()})"))
            elif s.as_of is not None and given and s.as_of != given[0]:
                problems.append(
                    Problem(
                        at, f"is not the first option's as-of date ({given[0]}): options share one"
                    )
                )
        if problems:
            raise ScenarioError(problems)
        return given[0] if given else today

    async def run(
        self,
        user_id: str,
        data: schema.Scenario | Mapping[str, Any],
        *,
        timeline: bool = False,
    ) -> dict[str, Any]:
        """The scenario on the user's baseline: every figure under the
        baseline and under the scenario, and the delta; with `timeline`, both
        timelines too, for drawing them. Stores nothing."""
        scenario = load_scenario(data)
        as_of = self.as_of_for([scenario])
        await self.check_own(user_id, [scenario])
        baseline = await self._baselines.build(user_id, as_of)
        return views.result_view(engine.run(baseline, scenario, timeline=timeline))

    async def compare(
        self,
        user_id: str,
        options: Sequence[schema.Scenario | Mapping[str, Any]],
        *,
        timeline: bool = False,
    ) -> dict[str, Any]:
        """Two to five scenarios side by side on the user's baseline, the
        trade between each two, their sensitivity to the real return and the
        break-evens (with `timeline`, each option's timelines). Never a
        ranking. Stores nothing."""
        if not comparison.MIN_OPTIONS <= len(options) <= comparison.MAX_OPTIONS:
            raise ScenarioError(
                [
                    Problem(
                        "options",
                        f"compares {comparison.MIN_OPTIONS} to {comparison.MAX_OPTIONS} "
                        f"options, not {len(options)}",
                    )
                ]
            )
        scenarios: list[schema.Scenario] = []
        problems: list[Problem] = []
        for i, data in enumerate(options):
            try:
                scenarios.append(load_scenario(data, option=i))
            except ScenarioError as error:
                problems += error.problems
        if problems:
            raise ScenarioError(problems)
        as_of = self.as_of_for(scenarios)
        await self.check_own(user_id, scenarios)
        baseline = await self._baselines.build(user_id, as_of)
        return views.comparison_view(comparison.compare(baseline, scenarios, timeline=timeline))
