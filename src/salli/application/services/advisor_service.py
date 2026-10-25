"""
AdvisorService: the monthly briefing (domain/agents/briefing.py).

Flow: usage meter → gather (Salli's own figures, signals and what the planning
assumptions rest on; deterministic) → narrate (the model writes sentences with
slots; Salli fills in its figures) → store the briefing. It describes and
never advises: no recommendation, priority, product or rate research. Reports
the advisor stored before keep their place in the export, and the reads show
briefings only.
"""

from __future__ import annotations

import datetime
from typing import Any

from salli.domain.agents import briefing as briefing_llm
from salli.domain.usage import AIAction


class AdvisorService:
    def __init__(
        self, uow_factory, fi_service, usage_meter, insights=None, credentials=None
    ) -> None:
        self._uow_factory = uow_factory
        self._fi = fi_service
        self._usage = usage_meter
        self._insights = insights
        self._credentials = credentials

    async def llm_for(self, user_id: str, api_key: Any = None) -> Any:
        """The model access to run on: the caller's already-resolved credential
        (an LLMClient, or an Anthropic key as it always was), else this user's,
        resolved now. LLMNotConfigured when there is nothing to run on.

        The HTTP routes resolve once at the boundary and pass it down, so the hot
        path does one lookup. The MCP server, the agent's own tools, and the CLI
        have no such boundary, so they omit it and this resolves on their behalf
        — which keeps every surface on the same credential rather than leaving
        some of them on the platform's.
        """
        from salli.application.services.llm_credential_service import as_llm
        from salli.domain.llm import LLMNotConfigured

        if api_key is not None:
            llm = as_llm(api_key)
        elif self._credentials is None:
            raise RuntimeError("No LLM credential source configured")
        else:
            llm = (await self._credentials.resolve(user_id)).llm
        if llm is None:
            raise LLMNotConfigured(
                "This needs an AI model: add your own API key or connect your ChatGPT "
                "plan in Settings."
            )
        return llm

    # ── Run ─────────────────────────────────────────────────────────────────────

    async def run_advisor(
        self,
        user_id: str,
        email: str | None = None,
        trigger: str = "manual",
        *,
        api_key: Any = None,
    ) -> dict[str, Any]:
        """Gather, narrate and store a briefing now."""
        context = await self.gather_context(user_id, email)
        llm = await self.llm_for(user_id, api_key)
        draft = await briefing_llm.narrate(context, llm=llm)
        report = await self.persist_report(user_id, trigger, draft, context)
        # The run writes (its report), so it also records the score it
        # described in the score history: gathering only reads.
        await self._fi.record_score(user_id)
        return report

    async def gather_context(self, user_id: str, email: str | None = None) -> dict[str, Any]:
        """Metered, deterministic gather step, reused by run_advisor and the
        briefing workflow's gather node: Salli's figures (`briefing.figures_of`),
        its signals in its own words, and whether the FI figures rest on
        placeholders. Never calls the model, and never writes.

        May raise UsageLimitReached (the API returns the meter's response); cron
        and the briefing workflow both catch it and skip/surface gracefully
        rather than propagate.
        """
        # No model_id: the briefing runs on the default model, and telling the
        # meter otherwise would let it price one model while another runs.
        # Deliberately not the user's chosen model either: this path is also
        # the scheduled run, and a background job silently running on the most
        # expensive model is not something anyone opted into.
        await self._usage.charge(user_id, AIAction.ADVISOR_RUN, email=email)

        score = await self._fi.compute_score(user_id)
        projections = await self._fi.get_projections(user_id)
        goals = await self._fi.list_goals(user_id)
        assumptions = projections.get("assumptions") or score.get("assumptions") or {}
        return {
            "figures": briefing_llm.figures_of(score, projections, goals),
            "signals": await self._signals(user_id),
            "assumptions": {
                "status": assumptions.get("status"),
                "placeholders": list(assumptions.get("placeholders") or []),
            },
        }

    async def _signals(self, user_id: str) -> list[dict[str, Any]]:
        """Salli's signals, in its own words: what kind, and its title and
        detail. Never how pressing it is (the briefing doesn't rank or press)
        nor its references."""
        if self._insights is None:
            return []
        found = await self._insights.signals(user_id)
        return [
            {k: s.get(k) for k in ("kind", "title", "detail")} for s in found.get("signals", [])
        ]

    async def persist_report(
        self, user_id: str, trigger: str, draft: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Store a briefing: the model's draft with Salli's figures filled in,
        and the figures, signals and assumptions it was written from. Shared by
        run_advisor and the briefing workflow's finalize node. Answers it as the
        reads show it."""
        report = {"trigger": trigger, **briefing_llm.view(draft, context)}
        async with self._uow_factory() as uow:
            report_id = await uow.advisories.save(user_id, report)
        return _shown({**report, "id": report_id})

    # ── Reports ─────────────────────────────────────────────────────────────────

    async def list_reports(self, user_id: str) -> list[dict[str, Any]]:
        """Briefings, newest first. The advisor's earlier reports are only in
        the export."""
        async with self._uow_factory() as uow:
            reports = await uow.advisories.list(user_id)
        return [_shown(r) for r in reports if r.get("briefing") is not None]

    async def get_latest_report(self, user_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            report = await uow.advisories.get_latest(user_id)
        return _shown(report) if report and report.get("briefing") is not None else None

    async def export_reports(self, user_id: str) -> list[dict[str, Any]]:
        """Every report as stored, the advisor's earlier ones included."""
        async with self._uow_factory() as uow:
            return list(await uow.advisories.export(user_id))

    # ── Scheduling helper ────────────────────────────────────────────────────────

    async def due_users(self) -> list[dict[str, str]]:
        """Opted-in users who have not had an advisory report today.

        Opt-in rather than automatic: each run is a model call made on the
        user's behalf, so it has to be something they asked for.
        """
        today = datetime.date.today().isoformat()
        async with self._uow_factory() as uow:
            candidates = await uow.user_profiles.list_daily_briefing_optins()
            due = []
            for c in candidates:
                if not await uow.advisories.ran_today(c["user_id"], today):
                    due.append(c)
        return due

    async def get_daily_briefing_enabled(self, user_id: str) -> bool:
        async with self._uow_factory() as uow:
            profile = await uow.user_profiles.get(user_id)
        return bool((profile or {}).get("daily_briefing_enabled"))

    async def set_daily_briefing_enabled(self, user_id: str, enabled: bool) -> None:
        """Uses set_flag, not upsert: upsert skips falsy-as-None values, so a
        toggle routed through it could be switched on but never off."""
        async with self._uow_factory() as uow:
            await uow.user_profiles.set_flag(user_id, "daily_briefing_enabled", enabled)


def _shown(report: dict[str, Any]) -> dict[str, Any]:
    """A stored briefing as the API shows it: its stored parts at the top,
    labelled as the AI's words."""
    body = report.get("briefing") or {}
    return (
        {k: report[k] for k in ("id", "user_id", "trigger", "summary", "created_at") if k in report}
        | {k: body.get(k) for k in ("notes", "figures", "signals", "assumptions")}
        | {"written_by": briefing_llm.WRITTEN_BY, "notice": briefing_llm.NOTICE}
    )
