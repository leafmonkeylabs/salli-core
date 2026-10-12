"""
TemplateService — decision templates (domain/decisions/templates.py,
catalogue.py; docs/templates.md) and starting a decision from one.

A template is a common decision as a few typed questions and the options
the answers build. The service does what the pure templates can't:

- **The person's facts.** Defaults come from their own money (their debts,
  their cash accounts) and their principles (a cash target one asks for),
  read from their baseline as of the day and their principles in use.
- **Starting a decision** (`start`): the answers checked (each problem with
  its path under `answers`), the options built, and every option run on
  their baseline (`domain/decisions/start.py`): the comparison, the
  principles' checks and, for a cash target, when cash reaches it. Every
  account and debt an option names is checked as the caller's own, as
  every scenario is.

It records nothing. Recording stays `DecisionService.record`, with the
person's choice, their reasons and their confirmation; the result carries
what that needs.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Any

from salli.application.services.principle_service import PrincipleService
from salli.application.services.scenario_service import ScenarioService
from salli.domain.decisions import catalogue, start, templates
from salli.domain.decisions.templates import Facts, TemplateError
from salli.domain.taxrules.common import Problem


class TemplateService:
    def __init__(self, scenarios: ScenarioService, principles: PrincipleService) -> None:
        self._scenarios = scenarios
        self._principles = principles

    @staticmethod
    def list() -> dict[str, Any]:
        """Every template, in brief: what it is and the options it builds."""
        return {"templates": [templates.summary_view(t) for t in catalogue.TEMPLATES]}

    def _as_of(self, value: Any) -> dt.date:
        today = self._scenarios.today()
        if value is None:
            return today
        if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
            day = value
        else:
            try:
                day = dt.date.fromisoformat(str(value))
            except ValueError:
                raise TemplateError([Problem("as_of", "is not a date (YYYY-MM-DD)")]) from None
        if day > today:
            raise TemplateError([Problem("as_of", f"can't be after today ({today.isoformat()})")])
        return day

    async def facts(self, user_id: str, as_of: dt.date | None = None) -> Facts:
        """What the templates read of the user's money and principles."""
        in_use = await self._principles.in_use(user_id)
        baseline = await self._scenarios.baselines.build(user_id, as_of or self._scenarios.today())
        return templates.facts_of(baseline, [(p.principle, p.expr) for p in in_use])

    async def get(self, user_id: str, template_id: str) -> dict[str, Any]:
        """One template with its questions, each default as it stands for
        the user, and the answers' JSON Schema. UnknownTemplate otherwise."""
        template = catalogue.get(template_id)
        return templates.template_view(template, await self.facts(user_id))

    async def every(self, user_id: str) -> dict[str, Any]:
        """Every template with its questions, as `get` gives each."""
        facts = await self.facts(user_id)
        return {"templates": [templates.template_view(t, facts) for t in catalogue.TEMPLATES]}

    async def start(self, user_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        """A template's options from the answers, compared and checked
        against the user's principles on their baseline (see
        domain/decisions/start.py). Stores nothing."""
        template = catalogue.get(str(data.get("template") or ""))
        as_of = self._as_of(data.get("as_of"))
        in_use = await self._principles.in_use(user_id)
        baseline = await self._scenarios.baselines.build(user_id, as_of)
        facts = templates.facts_of(baseline, [(p.principle, p.expr) for p in in_use])
        answers, built = templates.build(template, data.get("answers"), facts)
        await self._scenarios.check_own(user_id, [o.scenario for o in built.options])
        return start.start(baseline, template, answers, built, in_use)
