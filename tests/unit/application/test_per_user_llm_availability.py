"""Quick-add parsing used to exist only when a *platform* key was configured,
so it 503'd for exactly the users BYOK is for. These pin the new behaviour: the
service always exists, and which key it runs on — or whether it is usable at
all — is decided per request.

Voice Mode transcription used to be covered here too. It now runs on the phone
via `expo-speech-recognition`, so there is no key to resolve and nothing on the
server to test.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from salli.application.services.entry_parse_service import EntryParseService
from salli.application.services.llm_credential_service import ResolvedCredentials
from salli.domain.llm import LLMNotConfigured
from salli.domain.secrets import Secret
from tests.fakes import FakeLLM

DRAFT = {
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


class FakeCredentials:
    """Resolves to an Anthropic key, as the platform or a user's own would."""

    def __init__(self, anthropic: str = "") -> None:
        self._anthropic = anthropic
        self.resolved_for: list[str] = []

    async def resolve(self, user_id: str) -> ResolvedCredentials:
        self.resolved_for.append(user_id)
        return ResolvedCredentials(
            anthropic=Secret(self._anthropic),
            anthropic_is_user_key=bool(self._anthropic),
        )


class ClientCredentials:
    """Resolves to whatever client the test hands it, of any provider."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    async def resolve(self, user_id: str) -> Any:
        return ResolvedCredentials(anthropic=Secret(""), anthropic_is_user_key=False, llm=self.llm)


# ── Quick-add parsing ─────────────────────────────────────────────────────────


class FakeLedger:
    async def list_accounts(self, user_id: str) -> list[Any]:
        return []

    async def base_currency(self, user_id: str) -> str:
        return "LKR"


@pytest.mark.asyncio
async def test_entry_parse_runs_on_the_resolved_client():
    llm = FakeLLM(json.dumps(DRAFT))
    svc = EntryParseService(FakeLedger(), credentials=ClientCredentials(llm))

    draft = await svc.parse_draft("u1", "spent 500 on lunch")

    assert draft["amount"] == "500"
    (request,) = llm.requests
    assert request["tier"] == "fast"
    assert request["schema"]["title"] == "JournalEntryDraft"
    assert "spent 500 on lunch" in request["input"]


@pytest.mark.asyncio
async def test_a_resolved_anthropic_key_becomes_its_client():
    """Code that only knows about the Anthropic key keeps working: the
    resolved credentials carry a client built on it."""
    creds = await FakeCredentials(anthropic="sk-ant-USER").resolve("u1")
    assert creds.llm is not None
    assert creds.llm.provider == "anthropic"
    assert creds.llm.source == "user"


@pytest.mark.asyncio
async def test_entry_parse_resolves_per_user():
    creds = FakeCredentials(anthropic="sk-ant-X")
    svc = EntryParseService(FakeLedger(), credentials=creds)
    llm = FakeLLM(json.dumps(DRAFT))

    async def resolve(user_id: str) -> Any:
        creds.resolved_for.append(user_id)
        return ResolvedCredentials(anthropic=Secret(""), anthropic_is_user_key=False, llm=llm)

    creds.resolve = resolve  # type: ignore[method-assign]
    await svc.parse_draft("u1", "spent 500 on lunch")
    await svc.parse_draft("u2", "spent 900 on fuel")
    assert creds.resolved_for == ["u1", "u2"]


@pytest.mark.asyncio
async def test_with_nothing_to_run_on_quick_add_says_so():
    svc = EntryParseService(FakeLedger(), credentials=FakeCredentials())
    with pytest.raises(LLMNotConfigured):
        await svc.parse_draft("u1", "spent 500 on lunch")


@pytest.mark.asyncio
async def test_a_numeric_amount_never_passes_through_a_float():
    """The schema asks for a string; a model that answers with a number still
    reaches the form as the digits it wrote, read as Decimal, not a float."""
    llm = FakeLLM(
        '{"entry_type": "expense", "amount": 1234.10, "description": "x", '
        '"currency": "LKR", "confidence": 0.5}'
    )
    svc = EntryParseService(FakeLedger(), credentials=ClientCredentials(llm))

    draft = await svc.parse_draft("u1", "1234.10 on rent")

    assert draft["amount"] == "1234.10"


def test_entry_parse_reports_unavailable_without_a_credential_source():
    assert EntryParseService(FakeLedger()).available is False
    assert EntryParseService(FakeLedger(), credentials=FakeCredentials()).available is True
