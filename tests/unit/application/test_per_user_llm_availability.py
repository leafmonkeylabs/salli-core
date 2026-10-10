"""Quick-add parsing used to exist only when a *platform* key was configured,
so it 503'd for exactly the users BYOK is for. These pin the new behaviour: the
service always exists, and which key it runs on — or whether it is usable at
all — is decided per request.

Voice Mode transcription used to be covered here too. It now runs on the phone
via `expo-speech-recognition`, so there is no key to resolve and nothing on the
server to test.
"""

from __future__ import annotations

from typing import Any

import pytest

from salli.application.services.entry_parse_service import EntryParseService
from salli.application.services.llm_credential_service import ResolvedCredentials
from salli.domain.secrets import Secret


class FakeCredentials:
    def __init__(self, anthropic: str = "") -> None:
        self._anthropic = anthropic
        self.resolved_for: list[str] = []

    async def resolve(self, user_id: str) -> ResolvedCredentials:
        self.resolved_for.append(user_id)
        return ResolvedCredentials(
            anthropic=Secret(self._anthropic),
            anthropic_is_user_key=bool(self._anthropic),
        )


# ── Quick-add parsing ─────────────────────────────────────────────────────────


class FakeLedger:
    async def list_accounts(self, user_id: str) -> list[Any]:
        return []

    async def base_currency(self, user_id: str) -> str:
        return "LKR"


class FakeLLM:
    def __init__(self, api_key: Any) -> None:
        self.api_key = api_key

    async def extract_structured(self, prompt: str, schema: Any, *, model_tier: str) -> dict:
        return {
            "entry_type": "expense",
            "amount": "500",
            "description": "lunch",
            "debit_account_id": None,
            "credit_account_id": None,
            "debit_account_hint": None,
            "credit_account_hint": None,
            "currency": "LKR",
            "confidence": 0.9,
        }


@pytest.mark.asyncio
async def test_entry_parse_builds_the_adapter_against_the_resolved_key():
    creds = FakeCredentials(anthropic="sk-ant-USER")
    built: list[FakeLLM] = []

    def factory(key: Any) -> FakeLLM:
        llm = FakeLLM(key)
        built.append(llm)
        return llm

    svc = EntryParseService(FakeLedger(), factory, credentials=creds)
    draft = await svc.parse_draft("u1", "spent 500 on lunch")
    assert draft["amount"] == "500"
    assert built[0].api_key.reveal() == "sk-ant-USER"


@pytest.mark.asyncio
async def test_entry_parse_resolves_per_user():
    creds = FakeCredentials(anthropic="sk-ant-X")
    svc = EntryParseService(FakeLedger(), FakeLLM, credentials=creds)
    await svc.parse_draft("u1", "spent 500 on lunch")
    await svc.parse_draft("u2", "spent 900 on fuel")
    assert creds.resolved_for == ["u1", "u2"]


def test_entry_parse_reports_unavailable_without_a_credential_source():
    assert EntryParseService(FakeLedger(), FakeLLM).available is False
    assert EntryParseService(FakeLedger(), FakeLLM, credentials=FakeCredentials()).available is True
