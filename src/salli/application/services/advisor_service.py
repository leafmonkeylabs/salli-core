"""
AdvisorService — orchestrates the daily/on-command Wealth Advisor.

Flow: usage meter → gather (deterministic FI score + goals + profile memories +
current rates) → advise (structured LLM) → persist an advisory report. Acting on a
recommendation (create a reminder) happens later, on the user's approval.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from salli.domain.agents import advisor as advisor_llm
from salli.domain.jurisdiction import country_phrase
from salli.domain.usage import AIAction


class AdvisorService:
    def __init__(
        self, uow_factory, fi_service, usage_meter, doc_service=None, credentials=None
    ) -> None:
        self._uow_factory = uow_factory
        self._fi = fi_service
        self._usage = usage_meter
        self._doc = doc_service
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
        context = await self.gather_context(user_id, email)
        llm = await self.llm_for(user_id, api_key)
        advice = await advisor_llm.generate_advice(context, llm=llm)
        return await self.persist_report(user_id, trigger, advice)

    async def gather_context(self, user_id: str, email: str | None = None) -> dict[str, Any]:
        """Metered, deterministic gather step — reused by both run_advisor and
        the briefing workflow's gather node. Never calls the LLM.

        May raise UsageLimitReached (the API returns the meter's response); cron
        and the briefing workflow both catch it and skip/surface gracefully
        rather than propagate.
        """
        # No model_id: `advisor.generate_advice` runs on the default model, and
        # telling the meter otherwise would let it price one model while another
        # runs. Deliberately not the user's chosen model either — this path is
        # also the scheduled 6am cron, and a background job silently running on
        # the most expensive model is not something anyone opted into.
        await self._usage.charge(user_id, AIAction.ADVISOR_RUN, email=email)

        from salli.domain.agents.tools import set_current_user

        set_current_user(user_id)

        score = await self._fi.compute_score(user_id)
        goals = await self._fi.list_goals(user_id)
        profile = await self._gather_profile(user_id)
        residency = await self._tax_residency(user_id)
        rates = await self._research_rates(residency, score.get("currency"))
        fire_strategy = await self._fi.get_strategy(user_id)
        fire_projections = await self._fi.get_projections(user_id)
        surplus = await self._fi.get_surplus_breakdown(user_id)

        context = {
            "currency": score["currency"],
            # Where the user is taxed (ISO 3166-1), or None: advice tailored
            # to a country only when it is known.
            "tax_residency": residency,
            "fi_score": {
                "overall": score.get("overall_score"),
                "grade": score.get("grade"),
                "savings_rate": score.get("savings_rate"),
                "monthly_income": score.get("monthly_income"),
                "monthly_expenses": score.get("monthly_expenses"),
                "monthly_surplus": score.get("monthly_surplus"),
                "emergency_fund_months": score.get("emergency_fund_months"),
                "fi_number": score.get("fi_number"),
                "swr_used": score.get("swr"),
                "net_worth": score.get("net_worth"),
                # The base progress is actually measured against (investable assets
                # net of debt) — net_worth alone would overstate FI readiness.
                "fi_asset_base": score.get("fi_asset_base"),
                "progress_to_fi": score.get("progress_to_fi"),
                "debt_to_asset": score.get("debt_to_asset"),
                "projected_fi_date": score.get("projected_fi_date"),
                "components": score.get("components"),
            },
            "fire_strategy": {
                "fire_style": fire_strategy.get("fire_style"),
                "swr": fire_strategy.get("swr"),
                "return_conservative": fire_strategy.get("return_conservative"),
                "return_base": fire_strategy.get("return_base"),
                "return_growth": fire_strategy.get("return_growth"),
                "target_age": fire_strategy.get("target_age"),
                "target_monthly_expenses": fire_strategy.get("target_monthly_expenses"),
                "buckets": fire_strategy.get("buckets", []),
                "theories_applied": fire_strategy.get("theories_applied", []),
                "version": fire_strategy.get("version"),
                "created_at": fire_strategy.get("created_at"),
            }
            if fire_strategy
            else None,
            "fire_projections": {
                # fi_number deliberately omitted — it is the same figure as
                # fi_score.fi_number above. Sending it twice previously let the two
                # paths disagree and asked the model to reason about two targets.
                "current_portfolio": fire_projections.get("current_portfolio"),
                "fire_year_conservative": fire_projections.get("fire_year_conservative"),
                "fire_year_base": fire_projections.get("fire_year_base"),
                "fire_year_growth": fire_projections.get("fire_year_growth"),
                # Returns here are REAL (inflation-adjusted), unlike the nominal
                # assumptions in fire_strategy — say so, or the model will conflate them.
                "real_returns_used": fire_projections.get("real_returns"),
                "expected_inflation": fire_projections.get("expected_inflation"),
            },
            "surplus_breakdown": {
                "income_by_source": surplus.get("income_by_source", {}),
                "expense_by_category": surplus.get("expense_by_category", {}),
                "monthly_surplus": surplus.get("monthly_surplus"),
                "savings_rate": surplus.get("savings_rate"),
            },
            "goals": goals,
            "profile": profile,  # primary_goal, motivation, risk_appetite, target year/amount
            "current_rates_research": rates,
        }
        return context

    async def persist_report(self, user_id: str, trigger: str, advice: Any) -> dict[str, Any]:
        """Persist structured LLM advice (an Advice model, or anything exposing the
        same summary/fire_tier_assessment/recommendations shape) as an advisory
        report. Shared by run_advisor and the briefing workflow's finalize node."""
        recommendations = [
            {
                "id": str(uuid.uuid4()),
                "title": r.title,
                "rationale": r.rationale,
                "category": r.category,
                "priority": r.priority,
                "bucket_key": r.bucket_key,
                "action_type": r.action.type,
                "action_params": {
                    "label": r.action.label,
                    "due_in_days": r.action.due_in_days,
                },
                "status": "pending",
            }
            for r in advice.recommendations
        ]

        report = {
            "trigger": trigger,
            "fi_score_id": None,
            "summary": advice.summary,
            "fire_tier_assessment": advice.fire_tier_assessment,
            "recommendations": recommendations,
        }
        async with self._uow_factory() as uow:
            report_id = await uow.advisories.save(user_id, report)
        report["id"] = report_id
        return report

    async def _gather_profile(self, user_id: str) -> dict[str, Any]:
        if not self._doc:
            return {}
        keys = (
            "primary_goal",
            "motivation",
            "risk_appetite",
            "goal_target_amount",
            "goal_target_year",
        )
        out: dict[str, Any] = {}
        for k in keys:
            mem = await self._doc.get_memory(user_id, k)
            if mem and mem.get("content"):
                out[k] = mem["content"]
        return out

    async def _tax_residency(self, user_id: str) -> str | None:
        async with self._uow_factory() as uow:
            profile = await uow.user_profiles.get(user_id)
        residency = (profile or {}).get("tax_residency")
        return residency if isinstance(residency, str) and residency else None

    async def _research_rates(self, residency: str | None, currency: str | None) -> str:
        """Best-effort: current deposit and treasury bill rates where the user
        is, by their tax residency, or else for savers in their base currency."""
        if residency:
            where = f"in {country_phrase(residency)}"
        elif currency:
            where = f"for {currency} savings"
        else:
            return ""
        try:
            from langchain_community.tools.tavily_search import TavilySearchResults

            tool = TavilySearchResults(max_results=3)
            results = await tool.ainvoke(
                f"current fixed deposit and treasury bill interest rates {where}"
            )
            if isinstance(results, list):
                return " | ".join(
                    r.get("content", "")[:300] for r in results if isinstance(r, dict)
                )[:1200]
            return str(results)[:1200]
        except Exception:
            return ""

    # ── Reports ─────────────────────────────────────────────────────────────────

    async def list_reports(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return await uow.advisories.list(user_id)

    async def get_latest_report(self, user_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            return await uow.advisories.get_latest(user_id)

    # ── Act on a recommendation (user approval) ──────────────────────────────────

    async def apply_recommendation(
        self, user_id: str, report_id: str, rec_id: str
    ) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            report = await uow.advisories.get(user_id, report_id)
            if not report:
                raise ValueError("Report not found")
            recs = report["recommendations"]
            rec = next((r for r in recs if r["id"] == rec_id), None)
            if not rec:
                raise ValueError("Recommendation not found")

            if rec.get("action_type") == "reminder":
                params = rec.get("action_params") or {}
                due_days = params.get("due_in_days") or 14
                due = (datetime.date.today() + datetime.timedelta(days=int(due_days))).isoformat()
                label = params.get("label") or rec["title"]
                await uow.reminders.create_reminder(user_id, str(uuid.uuid4()), label, due)

            rec["status"] = "applied"
            await uow.advisories.update_recommendations(user_id, report_id, recs)
        return {"id": rec_id, "status": "applied"}

    async def dismiss_recommendation(
        self, user_id: str, report_id: str, rec_id: str
    ) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            report = await uow.advisories.get(user_id, report_id)
            if not report:
                raise ValueError("Report not found")
            recs = report["recommendations"]
            for r in recs:
                if r["id"] == rec_id:
                    r["status"] = "dismissed"
            await uow.advisories.update_recommendations(user_id, report_id, recs)
        return {"id": rec_id, "status": "dismissed"}

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
