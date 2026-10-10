"""The first-run flow every surface shares (API, `salli onboarding`, `salli setup`)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from salli.application.services.onboarding_service import (
    BASE_ACCOUNTS,
    SYSTEM_NEED_TAGS,
    OnboardingService,
    starter_chart,
)

EVERY_SOURCE = ["employment", "freelance", "rental", "interest", "foreign", "dividends"]

#: The chart a Sri Lankan resident got before charts followed the residency,
#: with every income source, in the order it was opened. It must not change.
SRI_LANKAN_CHART = [
    ("1100", "Cash", "asset", None),
    ("1200", "Bank Account", "asset", None),
    ("3000", "Opening Equity", "equity", None),
    ("5000", "General Expenses", "expense", None),
    ("5900", "Donations & Qualifying Payments", "expense", "qualifying_payment"),
    ("4100", "Employment Income", "income", None),
    ("4110", "APIT Receivable", "asset", "apit_credit"),
    ("4200", "Freelance / Business Income", "income", None),
    ("5100", "Business Expenses", "expense", None),
    ("4300", "Rental Income", "income", None),
    ("5200", "Property & Maintenance Expenses", "expense", None),
    ("4400", "Interest Income", "income", None),
    ("4410", "AIT Receivable", "asset", "ait_credit"),
    ("1300", "Foreign Currency Account", "asset", None),
    ("4500", "Foreign Service Income (FSI)", "income", "fsi_income"),
    ("4510", "Foreign Tax Credit Receivable", "asset", "foreign_tax_credit"),
    ("4600", "Dividend Income", "income", None),
]

#: Everyone else's: their income sources, and nothing about anyone's tax.
NEUTRAL_CHART = [
    ("1100", "Cash", "asset", None),
    ("1200", "Bank Account", "asset", None),
    ("3000", "Opening Equity", "equity", None),
    ("5000", "General Expenses", "expense", None),
    ("4100", "Employment Income", "income", None),
    ("4200", "Freelance / Business Income", "income", None),
    ("5100", "Business Expenses", "expense", None),
    ("4300", "Rental Income", "income", None),
    ("5200", "Property & Maintenance Expenses", "expense", None),
    ("4400", "Interest Income", "income", None),
    ("1300", "Foreign Currency Account", "asset", None),
    ("4500", "Foreign Income", "income", None),
    ("4600", "Dividend Income", "income", None),
]


def _service(existing_codes=(), residency: str | None = None):
    documents, fi, ledger, profile = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    ledger.list_accounts.return_value = [SimpleNamespace(code=c) for c in existing_codes]
    profile.get_tax_residency.return_value = residency
    return OnboardingService(documents, fi, ledger, profile), documents, fi, ledger


def _opened(ledger) -> list[tuple]:
    return [
        (c.kwargs["code"], c.kwargs["name"], c.kwargs["type"], c.kwargs["tax_role"])
        for c in ledger.add_account.await_args_list
    ]


async def test_a_name_alone_gets_the_base_ledger_and_need_tags():
    svc, documents, fi, ledger = _service()

    result = await svc.complete("u1", {"name": "Asha"})

    assert _opened(ledger) == [tuple(seed) for seed in BASE_ACCOUNTS]
    ledger.ensure_system_tags.assert_awaited_once_with("u1", SYSTEM_NEED_TAGS)
    fi.create_goal.assert_not_awaited()
    assert result["memories_saved"] == ["onboarding_complete", "user_name", "residency_status"]


async def test_a_sri_lankan_resident_gets_the_chart_they_always_got():
    svc, _, _, ledger = _service(residency="LK")

    await svc.complete("u1", {"name": "Asha", "income_sources": EVERY_SOURCE})

    assert _opened(ledger) == SRI_LANKAN_CHART


async def test_without_a_residency_the_chart_has_nothing_tax_specific():
    """`salli onboarding complete --base-currency USD` used to open an "APIT
    Receivable" for everyone."""
    svc, _, _, ledger = _service(residency=None)

    await svc.complete("u1", {"name": "Asha", "income_sources": EVERY_SOURCE})

    assert _opened(ledger) == NEUTRAL_CHART


async def test_a_country_without_a_tax_pack_gets_the_neutral_chart():
    svc, _, _, ledger = _service(residency="US")

    await svc.complete("u1", {"name": "Asha", "income_sources": EVERY_SOURCE})

    assert _opened(ledger) == NEUTRAL_CHART


async def test_the_chart_follows_the_residency_onboarding_itself_records():
    """The residency is read after the numbers are saved: a Sri Lankan NIC
    given to this flow makes the chart Sri Lankan."""
    svc, _, _, ledger = _service()
    profile = svc._profile
    profile.get_tax_residency.return_value = "LK"

    await svc.complete(
        "u1", {"name": "Asha", "nic": "200012345678", "income_sources": ["interest"]}
    )

    order = [c[0] for c in profile.method_calls]
    assert order.index("update_identity") < order.index("get_tax_residency")
    assert ("4410", "AIT Receivable", "asset", "ait_credit") in _opened(ledger)


async def test_rerunning_skips_accounts_that_exist():
    svc, _, _, ledger = _service(existing_codes=[code for code, *_ in BASE_ACCOUNTS])

    result = await svc.complete("u1", {"name": "Asha"})

    ledger.add_account.assert_not_awaited()
    assert result["accounts_created"] == []


async def test_a_concrete_target_seeds_a_first_goal():
    svc, _, fi, _ = _service()

    await svc.complete(
        "u1",
        {
            "name": "Asha",
            "primary_goal": "home",
            "goal_target_amount": 25_000_000,
            "goal_target_year": "2030",
        },
    )

    goal = fi.create_goal.await_args.args[1]
    assert goal["name"] == "Buy a home"
    assert goal["target_date"] == "2030-12-31"


async def test_status_reads_the_completion_memory():
    svc, documents, _, _ = _service()
    documents.get_memory.return_value = None
    assert not await svc.is_complete("u1")
    documents.get_memory.return_value = {"value": "true"}
    assert await svc.is_complete("u1")


def test_a_pack_account_takes_the_place_of_the_neutral_one_with_its_code():
    chart = starter_chart("LK", ["foreign"])
    assert [seed.code for seed in chart].count("4500") == 1
    assert ("4500", "Foreign Service Income (FSI)", "income", "fsi_income") in chart


async def test_a_source_given_twice_opens_its_accounts_once():
    svc, _, _, ledger = _service(residency="LK")

    await svc.complete("u1", {"name": "Asha", "income_sources": ["employment", "employment"]})

    assert [opened[0] for opened in _opened(ledger)].count("4110") == 1
