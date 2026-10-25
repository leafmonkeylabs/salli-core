"""
FiService — runs the deterministic FI engine on the baseline (domain/baseline),
records score snapshots when asked to, and manages goals. No model is used:
every figure is the engine's, on the user's own assumptions or labelled
placeholders.

Every figure starts from the baseline as of a day (today by this service's
clock, which is injectable, or the `as_of` a caller gives): its monthly
income and expenses (one definition, the same insights shows), its asset
split by account role (cash, investments; never by an account's name), its
balances at the published rates for that day, and its debts counted once.

When FI is reached comes from the baseline's monthly timeline
(domain/baseline/fi.py), where cash, investments and debts are kept apart:
the score's month, the projections under each return scenario, and every
scenario of the decision lab read it the same way. What a purchase costs is
a scenario (`ScenarioService.compare`), not a separate costing.

Reading never writes. A score is stored in the history only by `record_score`
(`POST /v1/fi/score/recompute`, and the advisor's run, which records the
score it advised on).
"""

from __future__ import annotations

import datetime
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from salli.application.ports import ProfileMissing
from salli.application.services.baseline_service import BaselineService
from salli.domain.baseline import Baseline
from salli.domain.baseline import fi as fi_timeline
from salli.domain.currency import quantize
from salli.domain.debt.engine import month_after
from salli.domain.fi import engine
from salli.domain.fi.allocation import Claim, GoalFunding, compute_goal_funding
from salli.domain.fi.assumptions import (
    NAMES,
    PLACEHOLDERS,
    SCENARIO_SPREAD,
    FiAssumptions,
    OwnAssumptions,
    OwnFigure,
    assumptions_dict,
    own_figure,
    rate_text,
    resolve,
)
from salli.domain.fi.assumptions import scenarios_dict as _scenarios_dict
from salli.domain.fi.models import FinancialSnapshot, FiPack, FiScore
from salli.domain.fi.packs import registry
from salli.domain.money import from_minor, to_minor

__all__ = ["FiService", "assumptions_dict"]


def decimal_arg(value: object, what: str) -> Decimal:
    """`value` as a Decimal, or a ValueError naming `what`."""
    if isinstance(value, float | bool):
        raise ValueError(f"{what} is a decimal string, such as '1200.50'")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f"Could not read {value!r} as {what}") from None
    if not number.is_finite():
        raise ValueError(f"Could not read {value!r} as {what}")
    return number


def _month_of(as_of: datetime.date, months: int | None) -> str | None:
    """The calendar month ("YYYY-MM") `months` after the as-of date's."""
    return None if months is None else month_after(as_of.isoformat()[:7], months)


def _fi_by(as_of: datetime.date, months: int | None) -> dict[str, Any]:
    return {"months": months, "month": _month_of(as_of, months)}


def _score_to_dict(score: FiScore, as_of: datetime.date) -> dict[str, Any]:
    d = asdict(score)
    # JSONB can't hold Decimal — stringify money/ratio fields (frontend formats)
    for k, v in list(d.items()):
        if isinstance(v, Decimal):
            d[k] = str(v)
    d["components"] = [
        {**c, "score": str(c["score"]), "weight": str(c["weight"])} for c in d["components"]
    ]
    # The FI date to the month, from the baseline's monthly timeline.
    d["projected_fi_month"] = _month_of(as_of, score.projected_fi_months)
    d["as_of"] = as_of.isoformat()
    return d


def _money(value: Decimal, currency: str) -> str:
    """Money as a string with exactly the currency's decimals.

    Apportioned amounts are rounded while exact ones are not, so without this a
    goal could report "500000.00" alongside a bare "0".
    """
    return str(quantize(value, currency))


def _own(profile: dict[str, Any] | None) -> OwnAssumptions:
    """The FI assumptions the user set, from their stored profile row."""
    return OwnAssumptions.from_stored((profile or {}).get("fi_assumptions"))


def _own_dict(figure: OwnFigure | None) -> dict[str, Any] | None:
    if figure is None:
        return None
    return {
        "value": rate_text(figure.value),
        "source": figure.source,
        "note": figure.note,
        "set_at": figure.set_at,
    }


def snapshot_of(baseline: Baseline, goal_progress: Decimal | None) -> FinancialSnapshot:
    """The FI engine's inputs, from the baseline: its monthly income and
    expenses; cash accounts as liquid savings and investment accounts as
    investments (what each owns); everything owned and owed, the debts the
    ledger doesn't hold among it."""
    return FinancialSnapshot(
        monthly_income=baseline.flows.income,
        monthly_expenses=baseline.flows.expenses,
        liquid_savings=baseline.liquid,
        investments=sum((b.owned for b in baseline.balances if b.role == "investment"), Decimal(0)),
        total_assets=baseline.total_assets,
        total_liabilities=baseline.total_liabilities,
        goal_progress=goal_progress,
        currency=baseline.currency,
        debt_rates=tuple((d.apr, d.balance) for d in baseline.debts if d.source != "scenario"),
        full_months=len(baseline.flows.months),
    )


class FiService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        baselines: BaselineService | None = None,
        today: Callable[[], datetime.date] = datetime.date.today,
    ) -> None:
        self._uow_factory = uow_factory
        self._today = today
        self._baselines = baselines or BaselineService(uow_factory, today=today)

    async def _baseline(self, user_id: str, as_of: datetime.date | None) -> Baseline:
        return await self._baselines.build(user_id, as_of or self._today())

    async def _goal_progress(self, user_id: str, baseline: Baseline) -> Decimal | None:
        """Weighted goal progress, from what the goals' accounts hold.

        Goals with nothing allocated are excluded rather than scored zero.
        Goal progress carries 15% of the Freedom Score, so scoring an
        unearmarked goal as 0% would mean merely *creating* a goal cost up to
        15 points — punishing someone for setting a goal, which is backwards.

        `engine.compute` drops the goals component and renormalises the
        remaining weights when `goal_progress` is None, so a set of goals with
        no allocations scores exactly as having no goals at all.
        """
        async with self._uow_factory() as uow:
            goals = await uow.goals.list(user_id, active_only=True)
            funding = await self._goal_funding(uow, user_id, baseline)
        currency = baseline.currency
        prog = [
            min(
                Decimal(1), funding[g["id"]].funded / from_minor(g["target_amount_minor"], currency)
            )
            for g in goals
            if g.get("target_amount_minor", 0) > 0
            and g["id"] in funding
            and funding[g["id"]].funded > 0
        ]
        return sum(prog, Decimal(0)) / Decimal(len(prog)) if prog else None

    async def build_snapshot(
        self, user_id: str, as_of: datetime.date | None = None
    ) -> FinancialSnapshot:
        baseline = await self._baseline(user_id, as_of)
        return snapshot_of(baseline, await self._goal_progress(user_id, baseline))

    # ── Assumptions ──────────────────────────────────────────────────────────

    async def _applied(self, user_id: str) -> FiAssumptions:
        """The assumptions that apply: the user's own, then the placeholders."""
        async with self._uow_factory() as uow:
            profile = await uow.user_profiles.get(user_id)
        return resolve(_own(profile))

    async def _inputs(
        self, user_id: str, as_of: datetime.date | None
    ) -> tuple[Baseline, FinancialSnapshot, FiAssumptions, FiPack]:
        """Everything a figure is computed from, read once: the baseline, the
        snapshot from it, the assumptions (the baseline's own), and the pack."""
        baseline = await self._baseline(user_id, as_of)
        snapshot = snapshot_of(baseline, await self._goal_progress(user_id, baseline))
        return baseline, snapshot, baseline.assumptions, registry.get_pack()

    async def assumptions(self, user_id: str) -> dict[str, Any]:
        """The planning assumptions behind the user's FI figures, what they
        set themselves (with sources), and the placeholders that stand in for
        what they have not."""
        applied = await self._applied(user_id)
        async with self._uow_factory() as uow:
            profile = await uow.user_profiles.get(user_id)
        own = _own(profile)
        return {
            "applied": assumptions_dict(applied),
            "own": {name: _own_dict(own.get(name)) for name in NAMES},
            "placeholder_values": {
                name: {"value": rate_text(p.value), "source": p.source}
                for name, p in PLACEHOLDERS.items()
            },
            "scenario_spread": rate_text(SCENARIO_SPREAD),
        }

    async def set_assumptions(
        self, user_id: str, changes: Mapping[str, Mapping[str, Any] | None]
    ) -> dict[str, Any]:
        """Set (or, with None, clear) the user's own planning assumptions
        named in `changes`, each `{"value", "source", "note"}`; the others
        stay as they are. A ValueError, before anything is written, for a
        figure out of range or a set that can't be used together (a real and
        a nominal return; a nominal return without inflation). Answers what
        `assumptions` does, afterwards."""
        now = datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat()
        figures: dict[str, OwnFigure | None] = {}
        for name, given in changes.items():
            if name not in NAMES:
                raise ValueError(f"Not an FI assumption: {name!r}. They are: {', '.join(NAMES)}")
            figures[name] = (
                None
                if given is None
                else own_figure(
                    name, given.get("value"), given.get("source"), given.get("note"), now
                )
            )
        async with self._uow_factory() as uow:
            profile = await uow.user_profiles.get(user_id)
            if profile is None:
                raise ProfileMissing(user_id)
            updated = _own(profile).changed(figures)
            await uow.user_profiles.set_fi_assumptions(user_id, updated.as_stored())
        return await self.assumptions(user_id)

    @staticmethod
    def _inputs_hash(
        snapshot: FinancialSnapshot,
        applied: FiAssumptions,
        pack: FiPack,
        fi_month: str | None = None,
    ) -> str:
        """
        Fingerprint of everything the score depends on, and everything it
        reports about its assumptions.

        Includes the assumptions, not just the ledger snapshot: setting one's
        own return or withdrawal rate changes the figures, and setting a source or an inflation figure
        changes what the score says about them, so a score computed under the
        old ones is stale even when the ledger has not moved. And the month FI
        is reached, which the whole baseline (its debts' schedules among it)
        decides, not the snapshot alone.
        """
        payload = {
            "snapshot": asdict(snapshot),
            "assumptions": assumptions_dict(applied),
            "pack": pack.version,
            "fi_month": fi_month,
        }
        return hashlib.sha256(json.dumps(payload, default=str, sort_keys=True).encode()).hexdigest()

    # ── Score ─────────────────────────────────────────────────────────────────

    async def compute_score(
        self, user_id: str, as_of: datetime.date | None = None
    ) -> dict[str, Any]:
        """The Freedom Score as of `as_of` (today when None). Reads only: the
        score history is written by `record_score` alone."""
        baseline, snapshot, applied, pack = await self._inputs(user_id, as_of)
        # When FI is reached: the baseline's monthly timeline, at the base
        # return, against the FI number the score computes from the same
        # withdrawal rate and target, so the card and the chart say one month.
        outlook = fi_timeline.outlook(baseline, fi_timeline.full_timeline(baseline))
        score = engine.compute(
            snapshot,
            pack,
            swr=applied.safe_withdrawal_rate.value,
            projected_fi_months=outlook.months,
        )
        result = _score_to_dict(score, baseline.as_of)
        # Under two full months of income and spending the engine grades it
        # "Not enough data"; `status` says the same for clients.
        result["months_observed"] = len(baseline.flows.months)
        result["status"] = "not_enough_data" if score.grade == engine.NOT_ENOUGH_DATA else "ok"
        result["assumptions"] = assumptions_dict(applied)
        result["inputs_hash"] = self._inputs_hash(snapshot, applied, pack, outlook.month)
        return result

    async def record_score(self, user_id: str) -> dict[str, Any]:
        """Compute today's score and store it in the score history: the one
        path that writes a score. A score whose inputs match the latest
        stored one is not stored twice."""
        result = await self.compute_score(user_id)
        async with self._uow_factory() as uow:
            latest = await uow.fi_scores.get_latest(user_id)
            if latest is None or latest.get("inputs_hash") != result["inputs_hash"]:
                await uow.fi_scores.save(user_id, result)
        return result

    async def get_latest_score(self, user_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            return await uow.fi_scores.get_latest(user_id)

    async def get_score_history(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return await uow.fi_scores.history(user_id)

    # ── Goals ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _goal_view(g: dict[str, Any], funding: GoalFunding | None, currency: str) -> dict[str, Any]:
        """One goal, with progress derived from what its accounts actually hold.

        `current_amount` is no longer the stored number. It is the sum of the
        live balances earmarked to this goal, apportioned by priority where an
        account is over-claimed — so it moves when money moves and only then.
        """
        target = g.get("target_amount_minor", 0)
        current = funding.funded if funding else Decimal(0)
        claimed = funding.claimed if funding else Decimal(0)
        # Computed in Decimal (the score path already did); float only at the
        # JSON boundary, where this is a display ratio and not money.
        progress = (
            min(Decimal(1), current / from_minor(target, currency)) if target > 0 else Decimal(0)
        )
        return {
            "id": g["id"],
            "name": g["name"],
            "kind": g["kind"],
            "currency": currency,
            "target_amount": _money(from_minor(g["target_amount_minor"], currency), currency),
            "current_amount": _money(current, currency),
            # What the user earmarked, vs what is actually behind it. A gap
            # means the accounts backing this goal do not hold what was claimed
            # — a normal unfunded plan, and something to show rather than hide.
            "allocated_amount": _money(claimed, currency),
            "shortfall": _money(funding.shortfall if funding else Decimal(0), currency),
            "target_date": g.get("target_date"),
            "priority": g["priority"],
            "progress": float(progress.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "created_at": g.get("created_at"),
        }

    async def _goal_funding(
        self, uow: Any, user_id: str, baseline: Baseline
    ) -> dict[str, GoalFunding]:
        """Apportion account balances across the claims made on them: each
        account's value in the baseline (at the published rate for its day),
        as every other figure counts it."""
        goals = await uow.goals.list(user_id, active_only=True)
        allocations = await uow.goals.list_allocations(user_id)
        if not allocations:
            return {}
        currency = baseline.currency
        balances = {b.account_id: b.value for b in baseline.balances if b.value is not None}
        priority = {g["id"]: int(g.get("priority", 2)) for g in goals}
        targets = {
            g["id"]: from_minor(g.get("target_amount_minor", 0), currency)
            for g in goals
            if g.get("target_amount_minor", 0) > 0
        }
        claims = [
            Claim(
                goal_id=a["goal_id"],
                account_id=a["account_id"],
                allocated=from_minor(a["allocated_minor"], currency),
                priority=priority.get(a["goal_id"], 2),
            )
            for a in allocations
            # A claim from a goal that is gone or archived should not consume
            # balance that an active goal could be using.
            if a["goal_id"] in priority
        ]
        return compute_goal_funding(claims, balances, targets)

    async def list_goals(self, user_id: str) -> list[dict[str, Any]]:
        baseline = await self._baseline(user_id, None)
        async with self._uow_factory() as uow:
            goals = await uow.goals.list(user_id, active_only=True)
            funding = await self._goal_funding(uow, user_id, baseline)
        return [self._goal_view(g, funding.get(g["id"]), baseline.currency) for g in goals]

    async def list_allocations(
        self, user_id: str, goal_id: str | None = None
    ) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            rows = await uow.goals.list_allocations(user_id, goal_id)
        return [
            {
                "goal_id": r["goal_id"],
                "account_id": r["account_id"],
                "currency": currency,
                "allocated_amount": _money(from_minor(r["allocated_minor"], currency), currency),
            }
            for r in rows
        ]

    async def set_allocation(
        self, user_id: str, goal_id: str, account_id: str, allocated_amount: Decimal
    ) -> None:
        """Earmark part of an account for a goal. Zero clears the claim."""
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            await uow.goals.set_allocation(
                user_id, goal_id, account_id, to_minor(allocated_amount, currency)
            )

    async def create_goal(self, user_id: str, data: dict[str, Any]) -> str:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            goal = {
                "name": data["name"],
                "kind": data.get("kind", "custom"),
                "target_amount_minor": to_minor(
                    Decimal(str(data.get("target_amount", 0))), currency
                ),
                # Progress is derived from allocations against real accounts, never
                # typed in. The column stays at zero and is no longer read.
                "current_amount_minor": 0,
                "target_date": data.get("target_date"),
                "priority": int(data.get("priority", 2)),
            }
            return await uow.goals.save(user_id, goal)

    async def update_goal(self, user_id: str, goal_id: str, data: dict[str, Any]) -> None:
        updates: dict[str, Any] = {}
        for k in ("name", "kind", "target_date", "priority", "is_active"):
            if k in data:
                updates[k] = data[k]
        async with self._uow_factory() as uow:
            if "target_amount" in data:
                currency = await uow.user_profiles.base_currency(user_id)
                updates["target_amount_minor"] = to_minor(
                    Decimal(str(data["target_amount"])), currency
                )
            await uow.goals.update(user_id, goal_id, updates)

    async def delete_goal(self, user_id: str, goal_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.goals.delete(user_id, goal_id)

    # ── Projections ──────────────────────────────────────────────────────────────

    async def get_projections(
        self, user_id: str, as_of: datetime.date | None = None
    ) -> dict[str, Any]:
        """The FI asset base projected under three real-return scenarios, in
        today's money; and in each year's own money too when the user set
        their inflation. Never waits for assumptions: placeholders stand in,
        and `assumptions` says which.

        Each scenario is the baseline's monthly timeline with its
        investments, the share of each month's surplus the user invests
        among them, at that real return (cash earns nothing, debts follow
        their schedules), and the month FI is reached is read from the same
        timeline, so the chart and the month always agree."""
        baseline, _, applied, _ = await self._inputs(user_id, as_of)
        rates = applied.real_returns.as_dict()
        inflation = applied.inflation.value if applied.inflation is not None else None
        currency = baseline.currency
        fi_number = fi_timeline.fi_number(baseline)
        runs = {
            key: fi_timeline.full_timeline(baseline, real_return=rate)
            for key, rate in rates.items()
        }
        months = {
            key: fi_timeline.months_to_fi(timeline.points, fi_number)
            for key, timeline in runs.items()
        }

        # Stretch the chart far enough to show the crossing when there is
        # one, so the plotted line and the month tell the same story.
        reachable = [-(-m // 12) for m in months.values() if m]
        horizon = min(40, max(15, (max(reachable) + 2) if reachable else 15))
        by_year = {key: fi_timeline.year_points(t.points, horizon) for key, t in runs.items()}

        def money(value: Decimal) -> str:
            return str(quantize(value, currency, strict=False))

        def point(year: int) -> dict[str, Any]:
            at = {key: points[year] for key, points in by_year.items()}
            row: dict[str, Any] = {
                "year": year,
                **{key: money(fi_timeline.asset_base(p)) for key, p in at.items()},
            }
            if inflation is not None:
                # In that year's own money: the same values grown by the
                # timeline's own deflator, never walked separately.
                level = at["base"].deflator
                row["nominal"] = {
                    **{key: money(fi_timeline.asset_base(p) * p.deflator) for key, p in at.items()},
                    # The FI number in that year's money: where the line it
                    # must cross has moved to by then.
                    "fi_number": money(fi_number * level),
                }
            return row

        return {
            "currency": currency,
            "as_of": baseline.as_of.isoformat(),
            # "real": every amount in today's money; "real_and_nominal": each
            # point also in its year's own money, from the user's inflation.
            "terms": "real" if inflation is None else "real_and_nominal",
            "points": [point(year) for year in range(len(by_year["base"]))],
            "fi_number": str(fi_number),
            "swr": rate_text(applied.safe_withdrawal_rate.value),
            # The month FI is reached in each scenario, and how many months
            # from the as-of month that is.
            "fi_by": {key: _fi_by(baseline.as_of, m) for key, m in months.items()},
            "current_portfolio": money(fi_timeline.asset_base(runs["base"].points[0])),
            # The real (after-inflation) rates the scenarios use.
            "real_returns": _scenarios_dict(applied.real_returns),
            # Their nominal equivalents and the inflation behind them: only
            # with the user's own inflation figure, never a guessed one.
            "inflation": None if inflation is None else rate_text(inflation),
            "nominal_returns": _scenarios_dict(applied.nominal_returns),
            # Which assumptions these are, where each came from, and whether
            # any is a placeholder.
            "assumptions": assumptions_dict(applied),
        }

    # ── Surplus Breakdown ────────────────────────────────────────────────────────

    async def _breakdown(self, user_id: str, baseline: Baseline) -> Any:
        """Income by source and spending by category, over the baseline's
        months observed: its totals are the baseline's own."""
        months = baseline.flows.months
        if not months:
            return engine.compute_surplus_breakdown([], [], 0)
        last = baseline.flows.by_month[-1].month
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(
                user_id, from_date=f"{months[0]}-01", to_date=f"{last}-31"
            )
        return engine.compute_surplus_breakdown(entries, accounts, len(months))

    async def get_surplus_breakdown(
        self, user_id: str, as_of: datetime.date | None = None
    ) -> dict[str, Any]:
        baseline = await self._baseline(user_id, as_of)
        breakdown = await self._breakdown(user_id, baseline)
        return {
            "currency": baseline.currency,
            "as_of": baseline.as_of.isoformat(),
            # The full calendar months these are monthly averages over.
            "months_observed": list(baseline.flows.months),
            "income_by_source": {k: str(v) for k, v in breakdown.income_by_source.items()},
            "expense_by_category": {k: str(v) for k, v in breakdown.expense_by_category.items()},
            # The needs/wants/savings split. Empty until spending carries `need`
            # tags, so clients must treat an empty object as "not classified
            # yet" rather than "nothing spent".
            "expense_by_need": {k: str(v) for k, v in breakdown.expense_by_need.items()},
            "gross_monthly_income": str(breakdown.gross_monthly_income),
            "gross_monthly_expenses": str(breakdown.gross_monthly_expenses),
            "monthly_surplus": str(breakdown.monthly_surplus),
            "savings_rate": str(breakdown.savings_rate),
        }
