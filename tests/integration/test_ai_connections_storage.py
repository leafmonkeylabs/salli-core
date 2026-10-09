"""A ChatGPT connection against a real Postgres: sealed storage, renewals that
race for one rotating refresh token, and account deletion."""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import os

import pytest

from salli.adapters.crypto.keyring import KeyRing
from salli.application.services.chatgpt_connection_service import (
    ChatGPTConnectionService,
    ChatGPTRecord,
)
from tests.integration.pg import requires_postgres, scalar
from tests.openai_fakes import FakeAuthServer

pytestmark = requires_postgres

KEYS = "1:" + base64.b64encode(os.urandom(32)).decode()
USER = "u1"


def _record(expires_in: dt.timedelta) -> ChatGPTRecord:
    return ChatGPTRecord(
        sub="sub-1",
        client_id="oaiapp_test",
        email="me@example.com",
        access_token="access-1",
        refresh_token="refresh-1",
        id_token="id-token-1",
        scopes=("chatgpt.tokens.use.direct", "offline_access"),
        expires_at=dt.datetime.now(dt.UTC) + expires_in,
    )


@pytest.fixture
def auth():
    # Slow enough that two renewals overlap if nothing holds them apart.
    return FakeAuthServer(delay=0.3)


@pytest.fixture
def service(uow_factory, auth):
    return ChatGPTConnectionService(uow_factory, KeyRing(KEYS), auth.oauth())


async def test_a_connection_is_stored_sealed_and_read_back(service, db):
    await service.save_record(USER, _record(dt.timedelta(hours=1)))

    sealed = scalar(db, "select sealed from ai_connections")
    assert "access-1" not in sealed and "refresh-1" not in sealed
    assert scalar(db, "select status from ai_connections") == "active"
    assert (await service.status(USER))["email"] == "me@example.com"
    assert await service.access_token(USER) == "access-1"


async def test_two_requests_renewing_at_once_spend_the_refresh_token_once(service, auth):
    """Both see a token about to expire. The first renews while holding the
    row; the second waits for it, then uses the new pair. Without the lock
    both would send refresh-1, and OpenAI refuses a refresh token used twice."""
    await service.save_record(USER, _record(dt.timedelta(minutes=2)))

    first, second = await asyncio.gather(service.access_token(USER), service.access_token(USER))

    assert first == second == "access-2"
    assert [r["refresh_token"] for r in auth.refreshes] == ["refresh-1"]
    stored = await service.record(USER)
    assert (stored.access_token, stored.refresh_token) == ("access-2", "refresh-2")


async def test_two_rejected_requests_renew_once(service, auth):
    """OpenAI rejected both with the same token; one renewal serves both."""
    await service.save_record(USER, _record(dt.timedelta(hours=1)))

    tokens = await asyncio.gather(
        service.access_token(USER, rejected="access-1"),
        service.access_token(USER, rejected="access-1"),
    )

    assert tokens == ["access-2", "access-2"]
    assert len(auth.refreshes) == 1


async def test_a_refused_renewal_is_stored_as_needing_sign_in(service, auth, db):
    from salli.domain.llm import LLMSignInRequired

    await service.save_record(USER, _record(dt.timedelta(minutes=1)))
    auth.refuse_with = "refresh_token_reused"

    with pytest.raises(LLMSignInRequired):
        await service.access_token(USER)

    assert scalar(db, "select status from ai_connections") == "needs_sign_in"
    assert scalar(db, "select status_detail from ai_connections").startswith("ChatGPT ended")


async def test_deleting_the_account_deletes_the_connection(service, uow_factory, db):
    await service.save_record(USER, _record(dt.timedelta(hours=1)))
    await service.save_record("someone-else", _record(dt.timedelta(hours=1)))

    async with uow_factory() as uow:
        counts = await uow.data_portability.delete_all(USER)

    assert counts["ai_connections"] == 1
    assert scalar(db, f"select count(*) from ai_connections where user_id = '{USER}'") == 0
    assert scalar(db, "select count(*) from ai_connections") == 1


async def test_one_connection_per_user_and_provider(service, db):
    await service.save_record(USER, _record(dt.timedelta(hours=1)))
    await service.save_record(USER, _record(dt.timedelta(hours=2)))
    assert scalar(db, "select count(*) from ai_connections") == 1
