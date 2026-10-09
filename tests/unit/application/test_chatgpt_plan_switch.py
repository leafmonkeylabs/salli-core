"""
Using a ChatGPT plan can be switched off. OpenAI offers plan usage to
open-source and self-hosted apps; a paid or remotely hosted product needs its
approval first. So it is on for self-hosting, and a hosted deployment turns it
off, by setting or through its extension, until it is approved.
"""

from __future__ import annotations

import base64
import datetime as dt
import os
from typing import Any

import pytest

from salli.adapters.crypto.keyring import KeyRing
from salli.application.defaults import ChatGPTPlanAllowed
from salli.application.ports import ChatGPTPlanPolicy
from salli.application.services.chatgpt_connection_service import (
    ChatGPTConnectionService,
    ChatGPTRecord,
    ChatGPTUnavailable,
)
from salli.domain.llm import LLMNotEligible
from salli.extensions import Extension, ExtensionError, combine
from tests.openai_fakes import FakeAuthServer
from tests.unit.application.test_chatgpt_connection_service import FakeConnections, FakeUoW

KEYS = "1:" + base64.b64encode(os.urandom(32)).decode()


class OnlyReviewers(ChatGPTPlanPolicy):
    """What a hosted product might do while OpenAI reviews it."""

    async def allows(self, user_id: str) -> bool:
        return user_id == "reviewer"


def _service(policy: ChatGPTPlanPolicy) -> tuple[ChatGPTConnectionService, FakeConnections]:
    repo = FakeConnections()
    return (
        ChatGPTConnectionService(
            lambda: FakeUoW(repo),
            KeyRing(KEYS),
            FakeAuthServer().oauth(),
            plan_allowed=policy.allows,
        ),
        repo,
    )


def _record() -> ChatGPTRecord:
    return ChatGPTRecord(
        sub="s",
        client_id="oaiapp_test",
        access_token="access-1",
        refresh_token="refresh-1",
        scopes=("chatgpt.tokens.use.direct",),
        expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
    )


async def test_salli_as_shipped_allows_it():
    assert await ChatGPTPlanAllowed().allows("anyone") is True
    assert isinstance(combine([]).chatgpt_plan, ChatGPTPlanAllowed)


async def test_switched_off_a_user_cannot_connect_or_use_it():
    service, _ = _service(OnlyReviewers())

    assert (await service.status("u1"))["available"] is False
    with pytest.raises(ChatGPTUnavailable, match="switched off"):
        await service.sign_in_context("u1")

    # A connection kept before it was switched off is refused, never used.
    await service.save_record("u1", _record())
    with pytest.raises(LLMNotEligible, match="switched off"):
        await service.access_token("u1")
    status = await service.status("u1")
    assert status["available"] is False and "switched off" in status["detail"]


async def test_an_extension_can_allow_it_for_some_users():
    service, _ = _service(OnlyReviewers())
    await service.save_record("reviewer", _record())
    assert await service.access_token("reviewer") == "access-1"
    assert (await service.status("reviewer"))["available"] is True


def test_an_extensions_policy_is_the_one_in_force():
    policy = OnlyReviewers()
    assert combine([Extension(name="cloud", chatgpt_plan=policy)]).chatgpt_plan is policy


def test_two_extensions_cannot_both_decide():
    with pytest.raises(ExtensionError, match="ChatGPT plan"):
        combine(
            [
                Extension(name="a", chatgpt_plan=OnlyReviewers()),
                Extension(name="b", chatgpt_plan=OnlyReviewers()),
            ]
        )


async def test_the_setting_switches_it_off_for_everyone(monkeypatch):
    from salli.composition import build_services
    from salli.config import Settings

    def built(**overrides: Any):
        return build_services(
            Settings(
                byok_encryption_keys=KEYS,
                supabase_url="https://project.supabase.co",
                salli_extensions="",
                **overrides,
            )
        )

    assert await built().chatgpt.allowed("u1") is True
    off = built(salli_chatgpt_plan_usage=False)
    assert await off.chatgpt.allowed("u1") is False
    # The same switch reaches what decides a request's provider (no database
    # needed to ask it).
    assert await off.llm_credentials._plan_allowed("u1") is False
