"""A key is checked with its provider before it is stored, on the free model
list. Nothing leaves the process: httpx is pointed at a MockTransport."""

from __future__ import annotations

import httpx
import pytest

from salli.adapters.llm import key_check
from salli.adapters.llm.key_check import (
    InvalidProviderKey,
    KeyValidationUnavailable,
    validate_provider_key,
)


@pytest.fixture
def provider(monkeypatch):
    seen: list[httpx.Request] = []
    answer = {"status": 200}
    real = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(answer["status"], json={"data": []})

    def client(**kwargs):
        return real(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(key_check.httpx, "AsyncClient", client)
    return seen, answer


async def test_an_openai_key_is_checked_on_openais_model_list(provider):
    seen, _ = provider
    await validate_provider_key("openai", "sk-test-openai")
    (request,) = seen
    assert str(request.url) == "https://api.openai.com/v1/models"
    assert request.headers["authorization"] == "Bearer sk-test-openai"


async def test_an_anthropic_key_is_still_checked_as_before(provider):
    seen, _ = provider
    await validate_provider_key("anthropic", "sk-ant-test")
    assert seen[0].headers["x-api-key"] == "sk-ant-test"


@pytest.mark.parametrize(
    ("status", "error"), [(401, InvalidProviderKey), (503, KeyValidationUnavailable)]
)
async def test_a_rejection_and_an_outage_are_told_apart(provider, status, error):
    _, answer = provider
    answer["status"] = status
    with pytest.raises(error):
        await validate_provider_key("openai", "sk-test-openai")
