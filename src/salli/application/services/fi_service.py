"""
FiService — builds a FinancialSnapshot from the ledger, runs the deterministic FI
engine, persists score snapshots, and manages goals. The LLM is only used in
generate_strategy() to create the AI-generated FireStrategy.
"""

from __future__ import annotations

import calendar
import datetime
import hashlib
import json
import re
from collections.abc import AsyncGenerator, Callable, Mapping
from dataclasses import asdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from salli.application.ports import ProfileMissing
from salli.domain.accounting import ledger as ledger_ops
from salli.domain.accounting.models import Account, Direction, StoredJournalEntry
from salli.domain.currency import quantize
from salli.domain.fi import engine
from salli.domain.fi.allocation import Claim, GoalFunding, compute_goal_funding
from salli.domain.fi.assumptions import (
    NAMES,
    PLACEHOLDERS,
    SCENARIO_SPREAD,
    Applied,
    FiAssumptions,
    OwnAssumptions,
    OwnFigure,
    Scenarios,
    StrategyFigures,
    own_figure,
    resolve,
)
from salli.domain.fi.models import (
    AllocationBucket,
    FinancialSnapshot,
    FiPack,
    FireStrategy,
    FiScore,
)
from salli.domain.fi.packs import registry
from salli.domain.llm import LLMError
from salli.domain.money import from_minor, to_minor

# Account-name patterns that mark an asset account as an *investment* rather than
# emergency-fund-eligible liquid savings.
#
# Anchored on word boundaries deliberately: an earlier unanchored substring list
# matched "fd" inside "Refund" and "share" inside "Sharepoint", quietly moving
# cash out of liquid savings and corrupting the emergency-fund component (15% of
# the score). Stems that need to match plurals/derivatives spell that out.
_INVESTMENT_PATTERN = re.compile(
    r"\b(?:"
    r"fixed deposits?"
    r"|fd"
    r"|invest\w*"
    r"|stocks?"
    r"|shares?"
    r"|mutual"
    r"|unit trusts?"
    r"|bonds?"
    r"|treasury"
    r"|t-?bills?"
    r"|crypto\w*"
    r"|etfs?"
    r"|pensions?"
    r"|provident"
    r"|portfolios?"
    r")\b"
)


def _is_investment(acc: Account) -> bool:
    return bool(_INVESTMENT_PATTERN.search(acc.name.lower()))


def _months_ago_iso(months: int) -> str:
    """
    First day of the trailing window, on calendar months.

    Previously approximated as 30-day steps, which made a "12 month" window 360
    days while still dividing the total by 12 — understating monthly income and
    expenses by ~1.4%.
    """
    today = datetime.date.today()
    month_index = today.month - 1 - months
    year = today.year + month_index // 12
    month = month_index % 12 + 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day).isoformat()


def _months_observed(entries: list[StoredJournalEntry], cap: int = 12) -> Decimal:
    """
    Months of history the trailing window actually covers, clamped to 1..cap.

    Measured as the span from the earliest entry to today, so a steady earner with
    only four months of records is averaged over four months rather than twelve.
    """
    if not entries:
        return Decimal(cap)
    earliest = min(str(e.entry_date)[:10] for e in entries)
    try:
        start = datetime.date.fromisoformat(earliest)
    except ValueError:
        return Decimal(cap)
    today = datetime.date.today()
    months = (today.year - start.year) * 12 + (today.month - start.month)
    # A partial current month still counts as one month of observation.
    months += 1
    return Decimal(max(1, min(cap, months)))


# A balance sheet older than this is treated as too stale to advise a purchase
# against. Chosen to be forgiving of a user who books a month late, while still
# refusing to answer from a quarter-old picture: a confident "yes, you can
# afford it" derived from stale data is worse than declining to answer, because
# the user acts on it and cannot un-spend the money.
STALE_AFTER_DAYS = 45


def _latest_entry_date(entries: list[StoredJournalEntry]) -> str | None:
    """Newest entry date in the ledger, ISO — the age of the picture we advise on."""
    if not entries:
        return None
    return max(str(e.entry_date)[:10] for e in entries)


def _is_stale(latest_iso: str | None, *, threshold_days: int = STALE_AFTER_DAYS) -> bool:
    """
    True when the ledger is too old to answer a purchase question from.

    An empty ledger counts as stale: there is nothing to advise on, and that is a
    far more honest response than costing a purchase against a zero balance sheet.
    """
    if latest_iso is None:
        return True
    try:
        latest = datetime.date.fromisoformat(latest_iso)
    except ValueError:
        return True
    return (datetime.date.today() - latest).days > threshold_days


def _plus_years_iso(years: int) -> str:
    """Calendar-correct year arithmetic (365-day years drift on leap years)."""
    today = datetime.date.today()
    try:
        return today.replace(year=today.year + years).isoformat()
    except ValueError:  # 29 Feb → 28 Feb in a non-leap target year
        return today.replace(year=today.year + years, day=28).isoformat()


def _dec(v: Decimal) -> str:
    return str(v)


def _score_to_dict(score: FiScore, projected_fi_date: str | None) -> dict[str, Any]:
    d = asdict(score)
    # JSONB can't hold Decimal — stringify money/ratio fields (frontend formats)
    for k, v in list(d.items()):
        if isinstance(v, Decimal):
            d[k] = str(v)
    d["components"] = [
        {**c, "score": str(c["score"]), "weight": str(c["weight"])} for c in d["components"]
    ]
    d["projected_fi_date"] = projected_fi_date
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


def _strategy_figures(strategy_data: dict[str, Any] | None) -> StrategyFigures | None:
    """The real returns and withdrawal rate a stored FIRE strategy chose. The
    model writes floats; they become Decimals here, once. A strategy stored
    without real returns contributes only its withdrawal rate, and one without
    a withdrawal rate contributes nothing."""
    if strategy_data is None or strategy_data.get("swr") is None:
        return None

    def rate(key: str) -> Decimal:
        return Decimal(str(strategy_data[key]))

    keys = ("real_return_conservative", "real_return_base", "real_return_growth")
    returns = (
        Scenarios(*(rate(k) for k in keys))
        if all(strategy_data.get(k) is not None for k in keys)
        else None
    )
    version = strategy_data.get("version")
    return StrategyFigures(
        safe_withdrawal_rate=rate("swr"),
        real_returns=returns,
        version=version if isinstance(version, int) else None,
    )


def _rate(value: Decimal) -> str:
    """A yearly fraction as a plain decimal string, never in exponent form,
    without the trailing zeros a computed rate carries ("0.09", not
    "0.0900000000000000000000000000")."""
    return f"{value.normalize():f}"


def _applied_dict(applied: Applied | None) -> dict[str, Any] | None:
    if applied is None:
        return None
    return {
        "value": _rate(applied.value),
        "origin": applied.origin,
        "source": applied.source,
        "note": applied.note,
    }


def _scenarios_dict(scenarios: Scenarios | None) -> dict[str, str] | None:
    if scenarios is None:
        return None
    return {k: _rate(v) for k, v in scenarios.as_dict().items()}


def assumptions_dict(applied: FiAssumptions) -> dict[str, Any]:
    """The assumptions behind a figure, as every FI response carries them:
    whether any is a placeholder (and which), each figure with its origin and
    source, and the scenarios' returns, real and (with the user's inflation)
    nominal."""
    return {
        "status": applied.status,
        "placeholders": list(applied.placeholders),
        "message": applied.message,
        "real_return": _applied_dict(applied.real_return),
        "safe_withdrawal_rate": _applied_dict(applied.safe_withdrawal_rate),
        "inflation": _applied_dict(applied.inflation),
        "nominal_return": _applied_dict(applied.nominal_return),
        "real_returns": _scenarios_dict(applied.real_returns),
        "nominal_returns": _scenarios_dict(applied.nominal_returns),
    }


def _own_dict(figure: OwnFigure | None) -> dict[str, Any] | None:
    if figure is None:
        return None
    return {
        "value": _rate(figure.value),
        "source": figure.source,
        "note": figure.note,
        "set_at": figure.set_at,
    }


class FiService:
    def __init__(self, uow_factory: Callable[[], Any], credentials: Any = None) -> None:
        self._uow_factory = uow_factory
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

    # ── Snapshot ────────────────────────────────────────────────────────────────

    async def build_snapshot(self, user_id: str) -> FinancialSnapshot:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            # Closed accounts too: a deactivated account with a balance is
            # still owned or owed (as net worth over time counts it).
            accounts: list[Account] = await uow.ledger.get_accounts(user_id, include_inactive=True)
            all_entries: list[StoredJournalEntry] = await uow.ledger.get_entries(user_id)
            recent: list[StoredJournalEntry] = await uow.ledger.get_entries(
                user_id, from_date=_months_ago_iso(12)
            )
            goals = await uow.goals.list(user_id, active_only=True)
            funding = await self._goal_funding(uow, user_id, currency)

        acc_map = {a.id: a for a in accounts}
        balances = ledger_ops.trial_balance(all_entries)  # {account_id: signed}

        total_assets = Decimal(0)
        total_liabilities = Decimal(0)
        liquid = Decimal(0)
        investments = Decimal(0)
        # Classify per account on its actual sign, rather than summing signed
        # balances and clamping the aggregate at zero. Clamping let an overdrawn
        # current account net silently against other assets (inflating net worth)
        # instead of being recognised as the borrowing it is.
        for a in accounts:
            # An overdraft is debt, an overpaid card a receivable (ledger_ops).
            owned, owed = ledger_ops.owned_and_owed(a.type, balances.get(a.id, Decimal(0)))
            total_assets += owned
            total_liabilities += owed
            if a.type == "asset" and _is_investment(a):
                investments += owned
            else:
                liquid += owned

        # Trailing-12-month income & expenses (separately)
        income = Decimal(0)
        expenses = Decimal(0)
        for e in recent:
            for p in e.postings:
                acc = acc_map.get(p.account_id)
                if acc is None:
                    continue
                if acc.type == "income" and p.direction == Direction.CREDIT:
                    income += abs(p.base_signed)
                elif acc.type == "expense" and p.direction == Direction.DEBIT:
                    expenses += abs(p.base_signed)
        # Annualise over the period actually observed, not a blind 12 months.
        # Dividing a new user's 3 months of income by 12 understates their monthly
        # figure ~4x, which then propagates into savings_rate, the FI number and
        # every projection built on them.
        months_observed = _months_observed(recent)
        monthly_income = income / months_observed
        monthly_expenses = expenses / months_observed

        # Weighted goal progress, from what the goal's accounts actually hold.
        #
        # Goals with nothing allocated are excluded rather than scored zero.
        # Goal progress carries 15% of the Freedom Score, so scoring an
        # unearmarked goal as 0% would mean merely *creating* a goal cost up to
        # 15 points — punishing someone for setting a goal, which is backwards.
        #
        # `engine.compute` drops the goals component and renormalises the
        # remaining weights when `goal_progress` is None, so a set of goals with
        # no allocations scores exactly as having no goals at all.
        goal_progress: Decimal | None = None
        prog = [
            min(
                Decimal(1), funding[g["id"]].funded / from_minor(g["target_amount_minor"], currency)
            )
            for g in goals
            if g.get("target_amount_minor", 0) > 0
            and g["id"] in funding
            and funding[g["id"]].funded > 0
        ]
        if prog:
            goal_progress = sum(prog, Decimal(0)) / Decimal(len(prog))

        # No aggregate clamping needed — every branch above contributes a
        # non-negative amount to the bucket it actually belongs in.
        return FinancialSnapshot(
            monthly_income=monthly_income,
            monthly_expenses=monthly_expenses,
            liquid_savings=liquid,
            investments=investments,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            goal_progress=goal_progress,
            currency=currency,
        )

    # ── Resolved strategy ──────────────────────────────────────────────────────

    @staticmethod
    def _resolve_strategy(
        strategy_data: dict[str, Any] | None, applied: FiAssumptions
    ) -> FireStrategy:
        """
        The single place raw strategy JSON becomes a typed, Decimal FireStrategy.

        Its withdrawal rate and real returns are the ones that apply
        (`applied`): the user's own where they set them, then the strategy's,
        then the labelled placeholders. So callers always get a usable
        strategy, never have to branch, and every figure on the page is
        computed from one set of assumptions.
        """
        data = strategy_data or {}
        return FireStrategy(
            version=data.get("version", 1) if strategy_data is not None else 0,
            fire_style=data.get("fire_style", "standard"),
            swr=applied.safe_withdrawal_rate.value,
            real_return_conservative=applied.real_returns.conservative,
            real_return_base=applied.real_returns.base,
            real_return_growth=applied.real_returns.growth,
            target_monthly_expenses=(
                Decimal(str(data["target_monthly_expenses"]))
                if data.get("target_monthly_expenses")
                else None
            ),
            target_age=data.get("target_age"),
            buckets=[
                AllocationBucket(
                    key=b["key"],
                    name=b["name"],
                    target_pct=Decimal(str(b["target_pct"])),
                    description=b["description"],
                    color=b["color"],
                )
                for b in data.get("buckets", [])
            ],
            ai_rationale=data.get("ai_rationale", ""),
            theories_applied=data.get("theories_applied", []),
            created_at=data.get("created_at", ""),
            is_initial=data.get("is_initial", True),
        )

    async def _plan(
        self, user_id: str, *, with_strategy: bool = True
    ) -> tuple[FireStrategy, FiAssumptions, FiPack]:
        """The strategy, the assumptions that apply, and the FI pack: what
        every score, projection and purchase costing is computed from.
        `with_strategy=False` leaves the stored strategy out of the
        assumptions (to generate a new one)."""
        strategy_data = await self.get_strategy(user_id) if with_strategy else None
        async with self._uow_factory() as uow:
            profile = await uow.user_profiles.get(user_id)
        applied = resolve(_own(profile), _strategy_figures(strategy_data))
        return self._resolve_strategy(strategy_data, applied), applied, registry.get_pack()

    async def assumptions(self, user_id: str) -> dict[str, Any]:
        """The planning assumptions behind the user's FI figures, what they
        set themselves (with sources), and the placeholders that stand in for
        what they have not."""
        _, applied, _ = await self._plan(user_id)
        async with self._uow_factory() as uow:
            profile = await uow.user_profiles.get(user_id)
        own = _own(profile)
        return {
            "applied": assumptions_dict(applied),
            "own": {name: _own_dict(own.get(name)) for name in NAMES},
            "placeholder_values": {
                name: {"value": _rate(p.value), "source": p.source}
                for name, p in PLACEHOLDERS.items()
            },
            "scenario_spread": _rate(SCENARIO_SPREAD),
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
        strategy: FireStrategy,
        applied: FiAssumptions,
        pack: FiPack,
    ) -> str:
        """
        Fingerprint of everything the score depends on, and everything it
        reports about its assumptions.

        Includes the strategy and the assumptions, not just the ledger snapshot:
        regenerating a strategy with a different SWR, or setting one's own
        return, changes the figures, and setting a source or an inflation figure
        changes what the score says about them, so a score computed under the
        old ones is stale even when the ledger has not moved.
        """
        payload = {
            "snapshot": asdict(snapshot),
            "target_monthly_expenses": str(strategy.target_monthly_expenses),
            "assumptions": assumptions_dict(applied),
            "pack": pack.version,
        }
        return hashlib.sha256(json.dumps(payload, default=str, sort_keys=True).encode()).hexdigest()

    # ── Score ─────────────────────────────────────────────────────────────────

    async def compute_score(self, user_id: str) -> dict[str, Any]:
        snapshot = await self.build_snapshot(user_id)
        strategy, applied, pack = await self._plan(user_id)

        # Same swr / target / real return the projection uses, so the Freedom
        # Number on the card and the target on the chart are one number.
        score = engine.compute(
            snapshot,
            pack,
            swr=strategy.swr,
            target_monthly_expenses=strategy.target_monthly_expenses,
            annual_real_return=strategy.real_return_base,
        )

        projected_date = None
        if score.projected_fi_years is not None:
            projected_date = _plus_years_iso(int(score.projected_fi_years))

        result = _score_to_dict(score, projected_date)
        result["assumptions"] = assumptions_dict(applied)
        result["inputs_hash"] = self._inputs_hash(snapshot, strategy, applied, pack)

        async with self._uow_factory() as uow:
            await uow.fi_scores.save(user_id, result)
        return result

    async def get_latest_score(self, user_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            return await uow.fi_scores.get_latest(user_id)

    async def get_or_compute_score(self, user_id: str) -> dict[str, Any]:
        """
        Latest score, recomputed whenever its inputs have moved.

        `inputs_hash` was previously written and never read, so the score card
        served the first-ever snapshot indefinitely while the projection chart was
        computed live — the two drifted apart with every posted entry.
        """
        latest = await self.get_latest_score(user_id)
        if latest is None:
            return await self.compute_score(user_id)

        snapshot = await self.build_snapshot(user_id)
        strategy, applied, pack = await self._plan(user_id)
        if latest.get("inputs_hash") != self._inputs_hash(snapshot, strategy, applied, pack):
            return await self.compute_score(user_id)
        return latest

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

    async def _goal_funding(self, uow: Any, user_id: str, currency: str) -> dict[str, GoalFunding]:
        """Apportion live account balances across the claims made on them."""
        goals = await uow.goals.list(user_id, active_only=True)
        allocations = await uow.goals.list_allocations(user_id)
        if not allocations:
            return {}

        entries = await uow.ledger.get_entries(user_id)
        balances = ledger_ops.trial_balance(entries)
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
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            goals = await uow.goals.list(user_id, active_only=True)
            funding = await self._goal_funding(uow, user_id, currency)
        return [self._goal_view(g, funding.get(g["id"]), currency) for g in goals]

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

    # ── FIRE Strategy ────────────────────────────────────────────────────────────

    async def get_strategy(self, user_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            return await uow.fire_strategies.get_latest(user_id)

    async def get_strategy_history(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return await uow.fire_strategies.get_history(user_id)

    async def generate_strategy(
        self,
        user_id: str,
        email: str | None = None,
        *,
        api_key: Any = None,
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """SSE generator: streams status events, then persists and yields the result."""
        from salli.domain.agents import fire_strategy as fs_llm

        yield _sse({"type": "status", "message": "Gathering your financial profile..."})

        snapshot = await self.build_snapshot(user_id)
        goals = await self.list_goals(user_id)
        previous = await self.get_strategy(user_id)

        # Build raw account detail for LLM context (type, currency, name)
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id)
            recent_entries = await uow.ledger.get_entries(user_id, from_date=_months_ago_iso(12))
            profile = await uow.user_profiles.get(user_id) or {}

        account_summary = [
            {"name": a.name, "type": a.type, "currency": a.currency} for a in accounts
        ]

        surplus_data = engine.compute_surplus_breakdown(recent_entries, accounts, months=12)

        yield _sse({"type": "status", "message": "Applying FIRE theories to your data..."})

        context: dict[str, Any] = {
            "monthly_income": str(snapshot.monthly_income),
            "monthly_expenses": str(snapshot.monthly_expenses),
            "monthly_surplus": str(snapshot.monthly_income - snapshot.monthly_expenses),
            "savings_rate": str(
                (snapshot.monthly_income - snapshot.monthly_expenses) / snapshot.monthly_income
                if snapshot.monthly_income > 0
                else Decimal(0)
            ),
            "liquid_savings": str(snapshot.liquid_savings),
            "investments": str(snapshot.investments),
            "total_assets": str(snapshot.total_assets),
            "total_liabilities": str(snapshot.total_liabilities),
            "net_worth": str(snapshot.total_assets - snapshot.total_liabilities),
            "currency": snapshot.currency,
            # Where the user is taxed, or None: the strategy suggests what is
            # available there, and assumes no country when it is not known.
            "tax_residency": profile.get("tax_residency"),
            # The user's own assumptions, or the labelled placeholders, with
            # where each came from: not the previous strategy's, which follows.
            "assumptions": assumptions_dict((await self._plan(user_id, with_strategy=False))[1]),
            "income_by_source": {k: str(v) for k, v in surplus_data.income_by_source.items()},
            "expense_by_category": {k: str(v) for k, v in surplus_data.expense_by_category.items()},
            "accounts": account_summary,
            "goals": goals,
            "previous_strategy": previous,
        }

        yield _sse({"type": "status", "message": "Generating personalised FIRE configuration..."})

        try:
            result = await fs_llm.generate_strategy(
                context,
                llm=await self.llm_for(user_id, api_key),
                # The model the usage meter was told about. Metering Opus and
                # then running Sonnet would charge for an answer the user never got.
                model=model,
            )
        except LLMError as exc:
            # The stream is already open, so the failure is its last event: our
            # own sentence, a code to branch on, and where to fix it (ChatGPT's
            # usage settings, when a plan's limit was reached).
            yield _sse({"type": "error", **exc.detail()})
            return

        yield _sse({"type": "status", "message": "Saving your FIRE strategy..."})

        strategy_dict = {
            "fire_style": result.fire_style,
            "swr": result.swr,
            "real_return_conservative": result.real_return_conservative,
            "real_return_base": result.real_return_base,
            "real_return_growth": result.real_return_growth,
            "target_monthly_expenses": result.target_monthly_expenses,
            "target_age": result.target_age,
            "buckets": [b.model_dump() for b in result.buckets],
            "ai_rationale": result.ai_rationale,
            "theories_applied": result.theories_applied,
            "is_initial": previous is None,
        }

        async with self._uow_factory() as uow:
            version = await uow.fire_strategies.save(user_id, strategy_dict)

        strategy_dict["version"] = version
        yield _sse({"type": "done", "strategy": strategy_dict})

    # ── Projections ──────────────────────────────────────────────────────────────

    async def get_projections(self, user_id: str) -> dict[str, Any]:
        """The FI asset base projected under three real-return scenarios, in
        today's money; and in each year's own money too when the user set
        their inflation. Never waits for assumptions: placeholders stand in,
        and `assumptions` says which."""
        snapshot = await self.build_snapshot(user_id)
        strategy, applied, pack = await self._plan(user_id)
        rates = applied.real_returns.as_dict()
        inflation = applied.inflation.value if applied.inflation is not None else None

        # The score's own FI number, from the same swr/target — not a second
        # formula. These two used to disagree whenever the strategy SWR was not 4%.
        score = engine.compute(
            snapshot,
            pack,
            swr=strategy.swr,
            annual_real_return=rates["base"],
            target_monthly_expenses=strategy.target_monthly_expenses,
        )
        fi_number = score.fi_number
        base = engine.fi_asset_base(snapshot)
        surplus = snapshot.monthly_income - snapshot.monthly_expenses

        # Years come from the shared solver, NOT from scanning the plotted series:
        # a 15-year chart cannot express an 18-year answer, and scanning one
        # returned None (which the UI rendered as a fallback ISO date).
        years = {
            key: engine.years_to_target(base, surplus, rate, fi_number)
            for key, rate in rates.items()
        }

        # Stretch the chart far enough to actually show the crossing when there is
        # one, so the plotted line and the headline number tell the same story.
        reachable = [int(v) for v in years.values() if v is not None and v > 0]
        horizon = min(40, max(15, (max(reachable) + 2) if reachable else 15))
        points = engine.project_portfolio(
            snapshot, rates, horizon_years=horizon, inflation=inflation
        )

        def point(p: Any) -> dict[str, Any]:
            row: dict[str, Any] = {
                "year": p.year,
                "conservative": str(p.conservative),
                "base": str(p.base),
                "growth": str(p.growth),
            }
            if p.nominal is not None and inflation is not None:
                row["nominal"] = {
                    "conservative": str(p.nominal.conservative),
                    "base": str(p.nominal.base),
                    "growth": str(p.nominal.growth),
                    # The FI number in that year's money: where the line it
                    # must cross has moved to by then.
                    "fi_number": str(engine.in_future_money(fi_number, inflation, p.year)),
                }
            return row

        return {
            "currency": snapshot.currency,
            # "real": every amount in today's money; "real_and_nominal": each
            # point also in its year's own money, from the user's inflation.
            "terms": "real" if inflation is None else "real_and_nominal",
            "points": [point(p) for p in points],
            "fi_number": str(fi_number),
            "swr": _rate(strategy.swr),
            "fire_year_conservative": (
                int(years["conservative"]) if years["conservative"] is not None else None
            ),
            "fire_year_base": int(years["base"]) if years["base"] is not None else None,
            "fire_year_growth": int(years["growth"]) if years["growth"] is not None else None,
            "current_portfolio": str(base),
            # The real (after-inflation) rates the scenarios use.
            "real_returns": _scenarios_dict(applied.real_returns),
            # Their nominal equivalents and the inflation behind them: only
            # with the user's own inflation figure, never a guessed one.
            "inflation": None if inflation is None else _rate(inflation),
            "nominal_returns": _scenarios_dict(applied.nominal_returns),
            # Which assumptions these are, where each came from, and whether
            # any is a placeholder.
            "assumptions": assumptions_dict(applied),
        }

    # ── Purchase simulation ("can I afford this?") ────────────────────────────────

    async def simulate_purchase(
        self,
        user_id: str,
        amount: Decimal,
        *,
        term_months: int | None = None,
        annual_interest_rate: Decimal = Decimal(0),
    ) -> dict[str, Any]:
        """
        Cost a prospective purchase in months of freedom.

        Uses the SAME swr / target-expenses / real-return values as
        `get_projections`, so the answer here can never contradict the user's
        Freedom page. Every figure is engine-computed; the caller (and the agent
        above it) may present them but must not derive new ones.
        """
        snapshot = await self.build_snapshot(user_id)
        strategy, applied, pack = await self._plan(user_id)

        async with self._uow_factory() as uow:
            entries = await uow.ledger.get_entries(user_id)
        as_of = _latest_entry_date(entries)
        stale = _is_stale(as_of)

        # The base scenario's real return — the same rate `get_projections`
        # reports as `real_returns.base` and draws the base line with.
        rate = applied.real_returns.base

        impact = engine.simulate_purchase(
            snapshot,
            pack,
            amount,
            swr=strategy.swr,
            target_monthly_expenses=strategy.target_monthly_expenses,
            annual_real_return=rate,
            term_months=term_months,
            annual_interest_rate=annual_interest_rate,
            data_as_of=as_of,
            is_stale=stale,
        )

        return {
            "amount": str(impact.amount),
            "currency": impact.currency,
            "fi_number": str(impact.fi_number),
            "fi_asset_base_before": str(impact.fi_asset_base_before),
            "monthly_surplus": str(impact.monthly_surplus),
            "baseline_months_to_fi": impact.baseline_months_to_fi,
            "payable_from_liquid": impact.payable_from_liquid,
            "emergency_months_before": str(impact.emergency_months_before),
            "emergency_months_after_cash": str(impact.emergency_months_after_cash),
            "emergency_fund_target_months": impact.emergency_fund_target_months,
            "options": [
                {
                    "key": o.key,
                    "label": o.label,
                    "total_cost": str(o.total_cost),
                    "interest_cost": str(o.interest_cost),
                    "monthly_payment": str(o.monthly_payment) if o.monthly_payment else None,
                    "term_months": o.term_months,
                    "months_to_fi": o.months_to_fi,
                    "months_delay": o.months_delay,
                    "exceeds_monthly_surplus": o.exceeds_monthly_surplus,
                }
                for o in impact.options
            ],
            "cheapest_option_key": impact.cheapest_option_key,
            "data_as_of": impact.data_as_of,
            "is_stale": impact.is_stale,
            "stale_after_days": STALE_AFTER_DAYS,
            "real_return_used": _rate(rate),
            "swr": _rate(strategy.swr),
            "assumptions": assumptions_dict(applied),
        }

    # ── Surplus Breakdown ────────────────────────────────────────────────────────

    async def get_surplus_breakdown(self, user_id: str) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            accounts = await uow.ledger.get_accounts(user_id)
            entries = await uow.ledger.get_entries(user_id, from_date=_months_ago_iso(12))

        breakdown = engine.compute_surplus_breakdown(entries, accounts, months=12)
        return {
            "currency": currency,
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


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"
