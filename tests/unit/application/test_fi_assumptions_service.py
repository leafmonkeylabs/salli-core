"""
FiService computes with the assumptions that apply to the user, in real terms,
and says so: every score, projection and purchase costing carries them, with
their origin, and flags any placeholder. The user (or their agent) sets their
own, each with a source, and nominal figures appear only once they set an
inflation figure.
"""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest

from salli.application.services.fi_service import FiService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry

USER = "u1"

pytestmark = pytest.mark.asyncio


def _entry(n: int, days_ago: int, debit: str, credit: str, amount: str) -> StoredJournalEntry:
    day = datetime.date.today() - datetime.timedelta(days=days_ago)
    return StoredJournalEntry(
        id=f"e{n}",
        user_id=USER,
        entry_date=day.isoformat(),
        description="",
        source="manual",
        postings=[
            Posting(
                account_id=debit, direction=Direction.DEBIT, amount=Decimal(amount), currency="USD"
            ),
            Posting(
                account_id=credit,
                direction=Direction.CREDIT,
                amount=Decimal(amount),
                currency="USD",
            ),
        ],
    )


class _Ledger:
    accounts = [
        Account(
            id="salary", user_id=USER, code="4000", name="Salary", type="income", currency="USD"
        ),
        Account(id="cash", user_id=USER, code="1000", name="Savings", type="asset", currency="USD"),
        Account(id="rent", user_id=USER, code="5000", name="Rent", type="expense", currency="USD"),
    ]
    entries = [
        _entry(1, 40, "cash", "salary", "5000"),
        _entry(2, 30, "rent", "cash", "2000"),
    ]

    async def get_accounts(self, user_id, include_inactive=False):
        return self.accounts

    async def get_entries(self, user_id, from_date=None, to_date=None):
        return [e for e in self.entries if from_date is None or e.entry_date >= from_date]


class _Goals:
    async def list(self, user_id, active_only=True):
        return []

    async def list_allocations(self, user_id, goal_id=None):
        return []


class _Scores:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def save(self, user_id, score):
        self.rows.append(score)
        return str(len(self.rows))

    async def get_latest(self, user_id):
        return self.rows[-1] if self.rows else None


class _Strategies:
    def __init__(self, strategy: dict[str, Any] | None = None) -> None:
        self.strategy = strategy

    async def get_latest(self, user_id):
        return self.strategy


class _Profiles:
    def __init__(self, base: str, **row: Any) -> None:
        self.row: dict[str, Any] = {"id": USER, "base_currency": base, "fi_assumptions": {}, **row}

    async def get(self, user_id):
        return dict(self.row)

    async def base_currency(self, user_id):
        return self.row["base_currency"]

    async def upsert(self, user_id, fields):
        self.row.update({k: v for k, v in fields.items() if v is not None})

    async def set_fi_assumptions(self, user_id, stored):
        self.row["fi_assumptions"] = stored


def _service(base: str = "USD", strategy: dict[str, Any] | None = None, **row: Any):
    profiles = _Profiles(base, **row)
    scores = _Scores()

    class _UoW:
        ledger = _Ledger()
        goals = _Goals()
        fi_scores = scores
        fire_strategies = _Strategies(strategy)
        user_profiles = profiles

    @asynccontextmanager
    async def factory():
        yield _UoW()

    return FiService(factory), profiles, scores, factory


def _own(**figures: Any) -> dict[str, Any]:
    """Stored figures, as OwnAssumptions.as_stored() writes them."""
    return {
        name: value if isinstance(value, dict) else {"value": value}
        for name, value in figures.items()
    }


# ── Placeholders, never a currency's or a country's figures ─────────────────


@pytest.mark.parametrize("base", ["USD", "BRL", "JPY", "KES"])
async def test_with_nothing_set_every_currency_gets_the_same_labelled_placeholders(base):
    svc, *_ = _service(base, tax_residency="BR" if base == "BRL" else None)
    projections = await svc.get_projections(USER)
    assumptions = projections["assumptions"]
    assert assumptions["status"] == "placeholder"
    assert assumptions["placeholders"] == ["real_return", "safe_withdrawal_rate"]
    assert assumptions["real_return"]["origin"] == "placeholder"
    assert assumptions["real_return"]["value"] == "0.04"
    assert assumptions["real_return"]["source"].startswith("Placeholder:")
    assert assumptions["safe_withdrawal_rate"]["value"] == "0.04"
    assert "placeholder assumptions" in assumptions["message"]
    # No inflation is assumed, so no nominal figure appears anywhere.
    assert assumptions["inflation"] is None
    assert assumptions["nominal_returns"] is None
    assert projections["terms"] == "real"
    assert projections["inflation"] is None
    assert projections["nominal_returns"] is None
    assert all("nominal" not in point for point in projections["points"])
    # The figures are the ones computed with them.
    assert projections["real_returns"] == {"conservative": "0.02", "base": "0.04", "growth": "0.06"}
    assert projections["swr"] == "0.04"


async def test_projections_never_block_on_missing_assumptions():
    svc, *_ = _service("USD")
    projections = await svc.get_projections(USER)
    # 2,000 of rent over the two months the ledger covers is 1,000 a month:
    # 12,000 a year, at the 4% placeholder rate, is 300,000.
    assert Decimal(projections["fi_number"]) == Decimal("300000")
    assert projections["points"][0]["year"] == 0
    assert len(projections["points"]) >= 16


async def test_every_fi_figure_carries_the_flag():
    svc, *_ = _service("USD")
    score = await svc.compute_score(USER)
    impact = await svc.simulate_purchase(USER, Decimal("1000"))
    for result in (score, impact):
        assert result["assumptions"]["status"] == "placeholder"
        assert result["assumptions"]["placeholders"] == ["real_return", "safe_withdrawal_rate"]
    assert impact["real_return_used"] == "0.04"


# ── The user's own ───────────────────────────────────────────────────────────


async def test_the_users_own_figures_apply_with_their_sources_and_say_so():
    svc, *_ = _service(
        "USD",
        fi_assumptions=_own(
            real_return={"value": "0.05", "source": "https://example.org/returns"},
            safe_withdrawal_rate={"value": "0.035", "note": "a cautious rate"},
        ),
    )
    score = await svc.compute_score(USER)
    assumptions = score["assumptions"]
    assert assumptions["status"] == "user"
    assert assumptions["placeholders"] == []
    assert assumptions["real_return"] == {
        "value": "0.05",
        "origin": "user",
        "source": "https://example.org/returns",
        "note": None,
    }
    assert assumptions["safe_withdrawal_rate"]["note"] == "a cautious rate"
    assert assumptions["safe_withdrawal_rate"]["source"] == "Set by you; no source given."
    assert score["swr"] == "0.035"


async def test_nominal_figures_appear_only_with_the_users_inflation():
    svc, *_ = _service(
        "EUR",
        fi_assumptions=_own(inflation={"value": "0.02", "source": "https://example.org/cpi"}),
    )
    projections = await svc.get_projections(USER)
    assert projections["terms"] == "real_and_nominal"
    assert projections["inflation"] == "0.02"
    # (1.04 × 1.02) − 1 = 0.0608.
    assert projections["nominal_returns"]["base"] == "0.0608"
    # The real projection is the same as without inflation; each point adds
    # its year's own money, and the FI number grows with it.
    plain, *_ = _service("EUR")
    real = (await plain.get_projections(USER))["points"]
    for point, same in zip(projections["points"], real, strict=True):
        assert {k: point[k] for k in ("year", "conservative", "base", "growth")} == same
    year_two = projections["points"][2]
    assert Decimal(year_two["nominal"]["base"]) == (
        Decimal(year_two["base"]) * Decimal("1.02") ** 2
    ).quantize(Decimal("0.01"))
    assert Decimal(year_two["nominal"]["fi_number"]) == (
        Decimal(projections["fi_number"]) * Decimal("1.0404")
    ).quantize(Decimal("0.01"))
    assert projections["points"][0]["nominal"]["base"] == projections["points"][0]["base"]
    # Still a placeholder for the return and the rate: inflation is not one of them.
    assert projections["assumptions"]["placeholders"] == ["real_return", "safe_withdrawal_rate"]


async def test_a_strategy_s_real_returns_apply_unless_the_user_set_their_own():
    strategy = {
        "version": 2,
        "swr": 0.045,
        "real_return_conservative": 0.01,
        "real_return_base": 0.03,
        "real_return_growth": 0.05,
    }
    svc, *_ = _service("USD", strategy=strategy)
    impact = await svc.simulate_purchase(USER, Decimal("1000"))
    assert impact["assumptions"]["safe_withdrawal_rate"]["origin"] == "strategy"
    assert impact["assumptions"]["real_return"]["origin"] == "strategy"
    assert impact["assumptions"]["status"] == "user"
    assert impact["swr"] == "0.045"
    assert impact["real_return_used"] == "0.03"

    svc, *_ = _service("USD", strategy=strategy, fi_assumptions=_own(safe_withdrawal_rate="0.03"))
    impact = await svc.simulate_purchase(USER, Decimal("1000"))
    assert impact["assumptions"]["safe_withdrawal_rate"]["origin"] == "user"
    assert impact["swr"] == "0.03"


async def test_a_strategy_stored_with_nominal_returns_contributes_only_its_rate():
    """Strategies once chose nominal returns; with no inflation to convert them
    at, they are not used, and the placeholder says so."""
    strategy = {"swr": 0.045, "return_conservative": 0.06, "return_base": 0.1}
    svc, *_ = _service("USD", strategy=strategy)
    projections = await svc.get_projections(USER)
    assert projections["assumptions"]["placeholders"] == ["real_return"]
    assert projections["swr"] == "0.045"


async def test_changing_ones_own_figure_recomputes_the_stored_score():
    svc, profiles, scores, _ = _service("USD")
    first = await svc.get_or_compute_score(USER)
    assert len(scores.rows) == 1
    assert await svc.get_or_compute_score(USER) is first  # nothing moved

    # Even a figure the score does not use (inflation) changes what it reports.
    profiles.row["fi_assumptions"] = _own(inflation="0.04")
    second = await svc.get_or_compute_score(USER)
    assert len(scores.rows) == 2
    assert second["assumptions"]["inflation"]["origin"] == "user"


async def test_the_report_has_what_applies_the_users_own_and_the_placeholders():
    svc, *_ = _service(
        "EUR", fi_assumptions=_own(real_return={"value": "0.03", "source": "my notes"})
    )
    report = await svc.assumptions(USER)
    assert report["applied"]["real_return"]["origin"] == "user"
    assert report["own"] == {
        "real_return": {"value": "0.03", "source": "my notes", "note": None, "set_at": None},
        "nominal_return": None,
        "inflation": None,
        "safe_withdrawal_rate": None,
    }
    assert report["placeholder_values"]["real_return"]["value"] == "0.04"
    assert report["placeholder_values"]["safe_withdrawal_rate"]["source"].startswith("Placeholder:")
    assert report["scenario_spread"] == "0.02"


async def test_the_users_own_figures_are_set_with_sources_and_cleared():
    svc, profiles, *_ = _service("USD")
    report = await svc.set_assumptions(
        USER,
        {
            "inflation": {"value": "0.025", "source": "https://example.org/cpi", "note": "  "},
            "nominal_return": {"value": "0.07", "source": "https://example.org/returns"},
        },
    )
    stored = profiles.row["fi_assumptions"]
    assert stored["inflation"]["value"] == "0.025"
    assert stored["inflation"]["source"] == "https://example.org/cpi"
    assert "note" not in stored["inflation"]
    assert stored["inflation"]["set_at"].endswith("+00:00")
    assert report["applied"]["real_return"]["origin"] == "user"
    assert report["applied"]["nominal_return"]["value"] == "0.07"

    # Clearing both the nominal return and the inflation it needs.
    report = await svc.set_assumptions(USER, {"nominal_return": None, "inflation": None})
    assert profiles.row["fi_assumptions"] == {}
    assert report["applied"]["status"] == "placeholder"


async def test_a_figure_that_cannot_be_used_is_refused_and_nothing_changes():
    svc, profiles, *_ = _service("USD", fi_assumptions=_own(inflation="0.02"))
    before = dict(profiles.row["fi_assumptions"])
    for changes, match in (
        ({"inflation": {"value": "3"}}, "yearly fraction"),
        ({"growth": {"value": "0.1"}}, "Not an FI assumption"),
        ({"real_return": {"value": "0.04"}, "nominal_return": {"value": "0.06"}}, "not both"),
        ({"inflation": None, "nominal_return": {"value": "0.06"}}, "needs your inflation"),
        ({"inflation": {"value": "0.02", "source": "x" * 501}}, "source"),
    ):
        with pytest.raises(ValueError, match=match):
            await svc.set_assumptions(USER, changes)
    assert profiles.row["fi_assumptions"] == before


async def test_the_strategy_is_asked_to_build_on_the_users_assumptions(monkeypatch):
    """Not the previous strategy's: those come separately, as the strategy."""
    from salli.domain.agents import fire_strategy

    seen: dict[str, Any] = {}

    async def generate(context, *, llm, model=None):
        seen.update(context)
        raise RuntimeError("stop here")

    monkeypatch.setattr(fire_strategy, "generate_strategy", generate)
    svc, *_ = _service("GBP", strategy={"swr": 0.05}, tax_residency="GB")
    stream = svc.generate_strategy(USER, api_key="k")
    try:
        async for _ in stream:
            pass
    except RuntimeError:
        pass

    assert seen["tax_residency"] == "GB"
    assert seen["assumptions"]["status"] == "placeholder"
    assert seen["assumptions"]["safe_withdrawal_rate"]["origin"] == "placeholder"
    assert "region" not in seen["assumptions"]
