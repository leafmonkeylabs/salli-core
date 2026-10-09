"""
What a user's AI runs on, and who pays: the setting (auto, anthropic, openai,
chatgpt), the order auto goes in, the models picked from the account's own
catalogue, and that a chosen provider which cannot run says so instead of
quietly running on the platform's key.
"""

from __future__ import annotations

import base64
import datetime as dt
import os
from typing import Any

import httpx
import pytest

from salli.adapters.crypto.keyring import KeyRing
from salli.application.services.chatgpt_connection_service import (
    ChatGPTConnectionService,
    ChatGPTRecord,
)
from salli.application.services.llm_credential_service import LlmCredentialService
from salli.domain.llm import LLMNotConfigured, LLMNotEligible, LLMSignInRequired
from tests.openai_fakes import FakeAuthServer, FakeOpenAI
from tests.unit.application.test_chatgpt_connection_service import (
    FakeConnections,
    FakeInstanceSettings,
)
from tests.unit.application.test_llm_credential_service import FakeAiSettings, FakeCredentialRepo

USER = "u1"
KEYS = "1:" + base64.b64encode(os.urandom(32)).decode()
API_MODELS = {
    "object": "list",
    "data": [
        {"id": "gpt-test-best", "created": 20},
        {"id": "gpt-test-mini", "created": 30},
        {"id": "text-embedding-3-small", "created": 40},
    ],
}


class World:
    def __init__(self, *, platform: str = "sk-ant-test-platform") -> None:
        self.keys = FakeCredentialRepo()
        self.profiles = FakeAiSettings()
        self.connections = FakeConnections()
        self.instance = FakeInstanceSettings()
        self.auth = FakeAuthServer()
        self.openai = FakeOpenAI()
        self.allowed = True
        ring = KeyRing(KEYS)
        self.chatgpt = ChatGPTConnectionService(self.uow, ring, self.auth.oauth())

        async def plan_allowed(user_id: str) -> bool:
            return self.allowed

        self.service = LlmCredentialService(
            self.uow,
            ring,
            platform_anthropic_key=platform,
            validator=None,
            chatgpt=self.chatgpt,
            http_factory=self.http,
            plan_allowed=plan_allowed,
        )

    def uow(self) -> Any:
        world = self

        class UoW:
            llm_credentials = world.keys
            user_profiles = world.profiles
            ai_connections = world.connections
            instance_settings = world.instance

            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: object) -> None:
                return None

        return UoW()

    def http(self) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/v1/models" and request.headers["authorization"].startswith(
                "Bearer sk-"
            ):
                self.openai.requests.append(request)
                return httpx.Response(200, json=API_MODELS)
            return self.openai.handler(request)

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def connect_plan(self, status: str = "active") -> None:
        await self.chatgpt.save_record(
            USER,
            ChatGPTRecord(
                sub="user-sub-1",
                client_id="oaiapp_test",
                email="me@example.com",
                access_token="access-1",
                refresh_token="refresh-1",
                scopes=("chatgpt.tokens.use.direct",),
                expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
            ),
        )
        if status != "active":
            await self.connections.update(USER, "chatgpt", {"status": status})

    @property
    def catalogue_requests(self) -> int:
        return sum(1 for r in self.openai.requests if r.url.path == "/v1/models")


@pytest.fixture
def world() -> World:
    return World()


# ── Auto ──────────────────────────────────────────────────────────────────────


async def test_with_nothing_of_the_users_own_the_platform_key_runs(world):
    creds = await world.service.resolve(USER)
    assert (creds.provider, creds.source, creds.byok) == ("anthropic", "platform", False)
    assert creds.llm.provider == "anthropic"
    assert await world.service.has_byok(USER) is False


async def test_with_nothing_at_all_there_is_nothing_to_run_on():
    world = World(platform="")
    creds = await world.service.resolve(USER)
    assert (creds.provider, creds.source, creds.llm) == ("anthropic", "none", None)


async def test_auto_prefers_the_users_own_anthropic_key_over_the_platforms(world):
    await world.service.save(USER, "anthropic", "sk-ant-test-userkey")
    creds = await world.service.resolve(USER)
    assert (creds.provider, creds.source) == ("anthropic", "user")
    assert creds.anthropic.reveal() == "sk-ant-test-userkey"


async def test_auto_uses_an_openai_key_when_that_is_all_the_user_brought(world):
    await world.service.save(USER, "openai", "sk-test-openai-user")

    creds = await world.service.resolve(USER)

    assert (creds.provider, creds.source, creds.byok) == ("openai", "user", True)
    assert creds.llm.model_for("best") == "gpt-test-best"
    assert creds.llm.model_for("fast") == "gpt-test-mini"
    assert await world.service.has_byok(USER) is True


async def test_auto_prefers_the_anthropic_key_to_the_openai_key(world):
    await world.service.save(USER, "openai", "sk-test-openai-user")
    await world.service.save(USER, "anthropic", "sk-ant-test-userkey")
    assert (await world.service.resolve(USER)).provider == "anthropic"


async def test_auto_prefers_a_connected_chatgpt_plan_to_any_key(world):
    await world.service.save(USER, "anthropic", "sk-ant-test-userkey")
    await world.connect_plan()

    creds = await world.service.resolve(USER)

    assert (creds.provider, creds.source, creds.byok) == ("chatgpt", "user", True)
    # Picked from the plan's own catalogue, in its server's order.
    assert creds.llm.model_for("best") == "gpt-test-best"
    assert creds.llm.model_for("fast") == "gpt-test-mini"


async def test_a_plan_signed_in_to_without_plan_use_is_not_picked(world):
    await world.connect_plan(status="needs_consent")
    assert (await world.service.resolve(USER)).provider == "anthropic"


async def test_a_plan_that_needs_signing_in_again_never_falls_back_to_the_platform(world):
    await world.connect_plan(status="needs_sign_in")

    with pytest.raises(LLMSignInRequired):
        await world.service.resolve(USER)
    # The meter still knows the user's own plan is what would pay.
    assert await world.service.has_byok(USER) is True


# ── Choosing ──────────────────────────────────────────────────────────────────


async def test_choosing_openai_without_a_key_says_so(world):
    await world.service.set_provider(USER, "openai")
    with pytest.raises(LLMNotConfigured, match="salli llm-keys set openai"):
        await world.service.resolve(USER)


async def test_choosing_chatgpt_without_a_connection_says_so(world):
    await world.service.set_provider(USER, "chatgpt")
    with pytest.raises(LLMSignInRequired, match="salli ai connect chatgpt"):
        await world.service.resolve(USER)


async def test_choosing_anthropic_with_a_plan_connected_uses_anthropic(world):
    await world.connect_plan()
    await world.service.set_provider(USER, "anthropic")
    creds = await world.service.resolve(USER)
    assert (creds.provider, creds.source) == ("anthropic", "platform")


async def test_a_deployment_that_switched_plan_use_off_says_so(world):
    await world.connect_plan()
    world.allowed = False
    with pytest.raises(LLMNotEligible, match="switched off on this Salli server"):
        await world.service.resolve(USER)
    assert (await world.service.settings(USER))["chatgpt_available"] is False


async def test_an_unknown_choice_is_refused(world):
    with pytest.raises(ValueError):
        await world.service.set_provider(USER, "gemini")


async def test_settings_say_what_the_choice_resolves_to(world):
    await world.service.save(USER, "openai", "sk-test-openai-user")
    settings = await world.service.settings(USER)
    assert settings["provider"] == "auto"
    assert settings["active"] == {"provider": "openai", "source": "user"}
    assert settings["keys"] == ["openai"]
    assert "sk-test" not in str(settings)


# ── Models ────────────────────────────────────────────────────────────────────


async def test_the_catalogue_is_fetched_once_for_a_while(world):
    await world.connect_plan()
    await world.service.resolve(USER)
    await world.service.resolve(USER)
    assert world.catalogue_requests == 1


async def test_a_stale_catalogue_beats_none_when_openai_is_down(world, monkeypatch):
    await world.connect_plan()
    await world.service.resolve(USER)
    world.service._clock = lambda: 10**9  # long after it went stale

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    world.service._http_factory = lambda: httpx.AsyncClient(transport=httpx.MockTransport(down))
    creds = await world.service.resolve(USER)
    assert creds.llm.model_for("best") == "gpt-test-best"


async def test_a_chosen_model_is_checked_and_then_runs(world):
    await world.connect_plan()

    with pytest.raises(ValueError, match="isn't one of the models"):
        await world.service.set_models(USER, "chatgpt", fast=None, best="gpt-made-up")
    listed = await world.service.set_models(USER, "chatgpt", fast="gpt-test-best", best=None)

    assert listed["fast"] == "gpt-test-best"
    assert listed["chosen"] == {"fast": "gpt-test-best"}
    creds = await world.service.resolve(USER)
    assert creds.llm.model_for("fast") == "gpt-test-best"
    # Neither: Salli picks again.
    assert (await world.service.set_models(USER, "chatgpt", fast=None, best=None))["chosen"] == {}


async def test_claudes_models_are_not_chosen(world):
    with pytest.raises(ValueError, match="fixed"):
        await world.service.set_models(USER, "anthropic", fast="x", best=None)
    listed = await world.service.models(USER, "anthropic")
    assert listed["best"] and listed["fast"]
