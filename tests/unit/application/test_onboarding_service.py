"""The first-run flow every surface shares (API, `salli onboarding`, `salli setup`)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from salli.application.services.onboarding_service import (
    BASE_ACCOUNTS,
    SOURCE_ACCOUNTS,
    SYSTEM_NEED_TAGS,
    OnboardingService,
)

pytestmark = pytest.mark.asyncio


def _service(existing_codes=()):
    documents, fi, ledger = AsyncMock(), AsyncMock(), AsyncMock()
    ledger.list_accounts.return_value = [SimpleNamespace(code=c) for c in existing_codes]
    return OnboardingService(documents, fi, ledger), documents, fi, ledger


async def test_a_name_alone_gets_the_base_ledger_and_need_tags():
    svc, documents, fi, ledger = _service()

    result = await svc.complete("u1", {"name": "Asha"})

    codes = [c.kwargs["code"] for c in ledger.add_account.await_args_list]
    assert codes == [code for code, *_ in BASE_ACCOUNTS]
    ledger.ensure_system_tags.assert_awaited_once_with("u1", SYSTEM_NEED_TAGS)
    fi.create_goal.assert_not_awaited()
    assert result["memories_saved"] == ["onboarding_complete", "user_name", "residency_status"]


async def test_income_sources_add_their_accounts_with_tax_roles():
    svc, _, _, ledger = _service()

    await svc.complete("u1", {"name": "Asha", "income_sources": ["employment", "foreign"]})

    roles = {c.kwargs["code"]: c.kwargs["tax_role"] for c in ledger.add_account.await_args_list}
    for code, _, _, role in SOURCE_ACCOUNTS["employment"] + SOURCE_ACCOUNTS["foreign"]:
        assert roles[code] == role


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
