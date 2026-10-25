"""
FiService computes with the assumptions that apply to the user, in real terms,
and says so: every score, projection and purchase costing carries them, with
their origin, and flags any placeholder. The user (or their agent) sets their
own, each with a source, and nominal figures appear only once they set an
inflation figure.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

import pytest

from salli.application.services.fi_service import FiService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from tests.fakes import FakeUoW

USER = "u1"

pytestmark = pytest.mark.asyncio


# The day these tests stand on: the golden households' as-of date. Every
# figure here depends on it (the months averaged, each month's own money and
# where its rounding falls), so it is fixed rather than read from the clock:
# a real-against-nominal check that rounds each month's own money to the cent
# drifted from 0.04 to 0.11 across the days of a quarter, and failed on some.
TODAY = datetime.date(2026, 10, 11)


def _last_month(day: int) -> datetime.date:
    # Pinned to last month rather than "N days ago": the service averages over
    # the calendar months from the earliest entry to today, so a fixed number
    # of days back spans two months on some dates and three on others.
    first_of_this_month = TODAY.replace(day=1)
    return (first_of_this_month - datetime.timedelta(days=1)).replace(day=day)


def _entry(n: int, day: datetime.date, debit: str, credit: str, amount: str) -> StoredJournalEntry:
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


ACCOUNTS = [
    Account(id="salary", user_id=USER, code="4000", name="Salary", type="income", currency="USD"),
    Account(id="cash", user_id=USER, code="1000", name="Savings", type="asset", currency="USD"),
    Account(id="rent", user_id=USER, code="5000", name="Rent", type="expense", currency="USD"),
]
ENTRIES = [
    _entry(1, _last_month(1), "cash", "salary", "5000"),
    _entry(2, _last_month(2), "rent", "cash", "2000"),
]


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

    async def export(self, user_id):
        return [self.strategy] if self.strategy else []


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
    uow = FakeUoW(base)
    uow.ledger.accounts = list(ACCOUNTS)
    uow.ledger.entries = list(ENTRIES)
    uow.fi_scores = scores  # type: ignore[assignment]
    uow.fire_strategies = _Strategies(strategy)  # type: ignore[assignment]
    uow.user_profiles = profiles  # type: ignore[assignment]
    factory = uow.factory()
    return FiService(factory, today=lambda: TODAY), profiles, scores, factory


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
    assert assumptions["placeholders"] == [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "drawdown_horizon",
    ]
    assert assumptions["real_return"]["origin"] == "placeholder"
    assert assumptions["real_return"]["value"] == "0.04"
    assert assumptions["real_return"]["source"].startswith("Placeholder:")
    # The rate the placeholder pack's returns sustain.
    assert assumptions["safe_withdrawal_rate"]["value"] == "0.0314"
    assert assumptions["surplus_invested"]["value"] == "1"
    assert assumptions["surplus_invested"]["source"].startswith(
        "Placeholder: all of your monthly surplus is assumed invested"
    )
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
    assert projections["swr"] == "0.0314"


async def test_projections_never_block_on_missing_assumptions():
    svc, *_ = _service("USD")
    projections = await svc.get_projections(USER)
    # 2,000 of rent over the one full month the ledger covers (last month;
    # this one isn't over, so it isn't averaged in) is 2,000 a month: 24,000
    # a year, at the placeholder rate (the one the placeholder pack's
    # returns sustain, 3.14%), is 764,331.21. It was 600,000 at a round 4%,
    # and 300,000 when this month counted as a month of no rent.
    assert Decimal(projections["fi_number"]).quantize(Decimal("0.01")) == Decimal("764331.21")
    assert projections["points"][0]["year"] == 0
    assert len(projections["points"]) >= 16


async def test_every_fi_figure_carries_the_flag():
    svc, *_ = _service("USD")
    score = await svc.compute_score(USER)
    projections = await svc.get_projections(USER)
    for result in (score, projections):
        assert result["assumptions"]["status"] == "placeholder"
        assert result["assumptions"]["placeholders"] == [
            "real_return",
            "safe_withdrawal_rate",
            "surplus_invested",
            "drawdown_horizon",
        ]
    assert projections["real_returns"]["base"] == "0.04"


# ── The user's own ───────────────────────────────────────────────────────────


async def test_the_users_own_figures_apply_with_their_sources_and_say_so():
    svc, *_ = _service(
        "USD",
        fi_assumptions=_own(
            real_return={"value": "0.05", "source": "https://example.org/returns"},
            safe_withdrawal_rate={"value": "0.035", "note": "a cautious rate"},
            surplus_invested={"value": "0.6", "source": "my standing orders"},
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
    assert assumptions["surplus_invested"] == {
        "value": "0.6",
        "origin": "user",
        "source": "my standing orders",
        "note": None,
    }
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
    # 1b: was "the real projection is the same as without inflation"; then,
    # the surplus kept in cash, which loses real value with inflation, "the
    # real line can only be lower". Surplus invested at the placeholder
    # 100%, it keeps its real value in the investments whatever inflation
    # does, and only cash loses it. This ledger's baseline holds no cash, so
    # the real line is the one without inflation, to the cents each month's
    # own money is rounded to. Each point adds its year's own money, grown by
    # the timeline's own deflator (a twelfth of 2% a month), and the FI
    # number grows with it.
    plain, *_ = _service("EUR")
    real = (await plain.get_projections(USER))["points"]
    # (Inflation could move FI later, so the chart may run longer: the years
    # both show.)
    for point, without in zip(projections["points"], real, strict=False):
        # A cent a month at most, over the longer chart a larger number brings.
        assert abs(Decimal(point["base"]) - Decimal(without["base"])) <= Decimal("0.10")
    # With the surplus kept in cash instead, inflation takes from it, and the
    # real line is lower from the first year on.
    kept_in_cash = {"surplus_invested": {"value": "0"}}
    deflating, *_ = _service(
        "EUR",
        fi_assumptions=_own(inflation={"value": "0.02"}, **kept_in_cash),
    )
    level, *_ = _service("EUR", fi_assumptions=_own(**kept_in_cash))
    lower = (await deflating.get_projections(USER))["points"]
    flat = (await level.get_projections(USER))["points"]
    for point, without in list(zip(lower, flat, strict=False))[1:]:
        assert Decimal(point["base"]) < Decimal(without["base"])
    year_two = projections["points"][2]
    level = Decimal(year_two["nominal"]["fi_number"]) / Decimal(projections["fi_number"])
    assert Decimal("1.0404") < level < Decimal("1.0420")
    nominal = Decimal(year_two["nominal"]["base"])
    assert abs(nominal - Decimal(year_two["base"]) * level) <= Decimal("0.02")
    assert projections["points"][0]["nominal"]["base"] == projections["points"][0]["base"]
    # Still placeholders for the return, the rate and the share: inflation is
    # not one of them.
    assert projections["assumptions"]["placeholders"] == [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "drawdown_horizon",
    ]


async def test_a_strategy_an_earlier_salli_stored_moves_no_figure():
    """FI figures come from the user's own assumptions or the labelled
    placeholders, never from a model's choice."""
    strategy = {
        "version": 2,
        "swr": 0.045,
        "real_return_conservative": 0.01,
        "real_return_base": 0.03,
        "real_return_growth": 0.05,
        "target_monthly_expenses": 900,
    }
    svc, *_ = _service("USD", strategy=strategy)
    projections = await svc.get_projections(USER)
    assert projections["assumptions"]["placeholders"] == [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "drawdown_horizon",
    ]
    assert projections["swr"] == "0.0314"
    without, *_ = _service("USD")
    assert (await svc.compute_score(USER))["fi_number"] == (await without.compute_score(USER))[
        "fi_number"
    ]


async def test_a_score_is_recorded_when_its_inputs_change_and_never_by_reading():
    svc, profiles, scores, _ = _service("USD")
    first = await svc.compute_score(USER)
    assert scores.rows == []  # reading stores nothing
    await svc.record_score(USER)
    await svc.record_score(USER)  # nothing moved: not stored twice
    assert [r["inputs_hash"] for r in scores.rows] == [first["inputs_hash"]]

    # Even a figure the score does not use (inflation) changes what it reports.
    profiles.row["fi_assumptions"] = _own(inflation="0.04")
    second = await svc.record_score(USER)
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
        "volatility": None,
        "safe_withdrawal_rate": None,
        "surplus_invested": None,
    }
    assert report["placeholder_values"]["real_return"]["value"] == "0.04"
    assert report["placeholder_values"]["surplus_invested"]["value"] == "1"
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


async def test_the_share_of_the_surplus_invested_is_set_with_its_source_and_bounded():
    svc, profiles, *_ = _service("USD")
    report = await svc.set_assumptions(
        USER, {"surplus_invested": {"value": "0.8", "source": "my standing orders"}}
    )
    stored = profiles.row["fi_assumptions"]["surplus_invested"]
    assert (stored["value"], stored["source"]) == ("0.8", "my standing orders")
    assert report["own"]["surplus_invested"]["value"] == "0.8"
    assert report["applied"]["surplus_invested"]["origin"] == "user"
    assert "surplus_invested" not in report["applied"]["placeholders"]
    # The projections use it: the FI month moves with what is invested.
    invested = await svc.get_projections(USER)
    assert invested["assumptions"]["surplus_invested"]["value"] == "0.8"
    await svc.set_assumptions(USER, {"surplus_invested": {"value": "0"}})
    kept = await svc.get_projections(USER)
    # Kept in cash, which earns nothing, the surplus reaches FI later.
    sooner, later = invested["fi_by"]["base"]["months"], kept["fi_by"]["base"]["months"]
    assert sooner is not None and later is not None and later > sooner
    # A share is from 0 to 1: 80 typed for 80% is refused, and nothing changes.
    for value in ("80", "1.5", "-0.2"):
        with pytest.raises(ValueError, match="a share from 0 to 1"):
            await svc.set_assumptions(USER, {"surplus_invested": {"value": value}})
    assert profiles.row["fi_assumptions"]["surplus_invested"]["value"] == "0"
    # Cleared, the placeholder stands in again.
    report = await svc.set_assumptions(USER, {"surplus_invested": None})
    assert "surplus_invested" in report["applied"]["placeholders"]


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
