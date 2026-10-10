"""LlmCredentialService decides which key a request spends money on, so the
fallbacks and the failure modes matter more than the happy path."""

from __future__ import annotations

import base64
import os
from typing import Any

import pytest

from salli.adapters.crypto.keyring import KeyRing, aad_for
from salli.application.services.llm_credential_service import (
    LlmCredentialService,
    ResolvedCredentials,
)

USER = "u1"
USER_KEY = "sk-ant-api03-USERKEY0123456789"
PLATFORM_ANTHROPIC = "sk-ant-api03-PLATFORM0123456789"

K1 = base64.b64encode(os.urandom(32)).decode()
K2 = base64.b64encode(os.urandom(32)).decode()


class FakeCredentialRepo:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return [dict(v) for (u, _), v in self.rows.items() if u == user_id]

    async def get(self, user_id: str, provider: str) -> dict[str, Any] | None:
        row = self.rows.get((user_id, provider))
        return dict(row) if row else None

    async def upsert(
        self,
        user_id: str,
        provider: str,
        *,
        ciphertext: str,
        last4: str,
        validated_at: Any,
        key_version: int,
    ) -> None:
        self.rows[(user_id, provider)] = {
            "provider": provider,
            "ciphertext": ciphertext,
            "key_version": key_version,
            "last4": last4,
            "validated_at": validated_at.isoformat() if validated_at else None,
        }

    async def delete(self, user_id: str, provider: str) -> bool:
        return self.rows.pop((user_id, provider), None) is not None


class FakeUoW:
    def __init__(self, repo: FakeCredentialRepo) -> None:
        self.llm_credentials = repo

    async def __aenter__(self) -> FakeUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


async def _accepting_validator(provider: str, key: str) -> None:
    return None


def _service(
    repo: FakeCredentialRepo | None = None,
    *,
    spec: str = f"1:{K1}",
    feature_enabled: bool = True,
    validator: Any = _accepting_validator,
) -> tuple[LlmCredentialService, FakeCredentialRepo]:
    repo = repo or FakeCredentialRepo()
    svc = LlmCredentialService(
        lambda: FakeUoW(repo),
        KeyRing(spec),
        platform_anthropic_key=PLATFORM_ANTHROPIC,
        validator=validator,
        feature_enabled=feature_enabled,
    )
    return svc, repo


# ── Availability gating ───────────────────────────────────────────────────────


def test_unavailable_without_an_encryption_key():
    svc, _ = _service(spec="")
    assert svc.available is False


def test_unavailable_when_the_deployment_disables_the_feature():
    """Covers the dev-auth fallback, where any bearer token is accepted as a user
    id — BYOK there would let a caller spend an arbitrary user's key."""
    svc, _ = _service(feature_enabled=False)
    assert svc.available is False


@pytest.mark.asyncio
async def test_saving_is_refused_when_unavailable():
    svc, repo = _service(spec="")
    with pytest.raises(RuntimeError):
        await svc.save(USER, "anthropic", USER_KEY)
    assert repo.rows == {}


@pytest.mark.asyncio
async def test_a_disabled_deployment_ignores_rows_that_already_exist():
    """If the encryption key is removed while rows remain, those users must fall
    back to the platform key rather than half-working."""
    svc, repo = _service()
    await svc.save(USER, "anthropic", USER_KEY)

    disabled, _ = _service(repo, feature_enabled=False)
    creds = await disabled.resolve(USER)
    assert creds.byok is False
    assert creds.anthropic.reveal() == PLATFORM_ANTHROPIC
    assert await disabled.has_byok(USER) is False


# ── Resolution ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_falls_back_to_the_platform_key_with_nothing_stored():
    svc, _ = _service()
    creds = await svc.resolve(USER)
    assert creds.anthropic.reveal() == PLATFORM_ANTHROPIC
    assert creds.byok is False


@pytest.mark.asyncio
async def test_a_stored_key_wins_and_marks_the_request_byok():
    svc, _ = _service()
    await svc.save(USER, "anthropic", USER_KEY)
    creds = await svc.resolve(USER)
    assert creds.anthropic.reveal() == USER_KEY
    assert creds.byok is True


@pytest.mark.asyncio
async def test_one_users_key_is_never_resolved_for_another():
    svc, _ = _service()
    await svc.save(USER, "anthropic", USER_KEY)
    other = await svc.resolve("someone-else")
    assert other.anthropic.reveal() == PLATFORM_ANTHROPIC
    assert other.byok is False


@pytest.mark.asyncio
async def test_an_unreadable_row_falls_back_instead_of_locking_the_user_out():
    """A key rotated away is our storage problem, not the user's. Better to keep
    them working on the platform key than to fail every chat request."""
    svc, repo = _service()
    await svc.save(USER, "anthropic", USER_KEY)

    rotated, _ = _service(repo, spec=f"2:{K2}")  # version 1 no longer configured
    creds = await rotated.resolve(USER)
    assert creds.anthropic.reveal() == PLATFORM_ANTHROPIC
    assert creds.byok is False


@pytest.mark.asyncio
async def test_a_row_moved_to_another_user_does_not_decrypt():
    """The AAD binding, seen from the service: copying a row to another user id
    must not hand that user a working key."""
    svc, repo = _service()
    await svc.save(USER, "anthropic", USER_KEY)
    stolen = dict(repo.rows[(USER, "anthropic")])
    repo.rows[("attacker", "anthropic")] = stolen

    creds = await svc.resolve("attacker")
    assert creds.anthropic.reveal() == PLATFORM_ANTHROPIC
    assert creds.byok is False


@pytest.mark.asyncio
async def test_a_rotated_key_still_opens_rows_sealed_by_the_old_one():
    svc, repo = _service()
    await svc.save(USER, "anthropic", USER_KEY)
    rotated, _ = _service(repo, spec=f"1:{K1},2:{K2}")
    assert (await rotated.resolve(USER)).anthropic.reveal() == USER_KEY


# ── has_byok (what a usage meter sees) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_has_byok_tracks_the_anthropic_key():
    """Anthropic is the only provider now — it powers every AI path, so a user
    key there is exactly what has_byok reports. (This used to also assert
    that an OpenAI key did *not* count; OpenAI is gone, since transcription
    moved on-device.)"""
    svc, _ = _service()
    assert await svc.has_byok(USER) is False
    await svc.save(USER, "anthropic", USER_KEY)
    assert await svc.has_byok(USER) is True


# ── Storage / readback ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_plaintext_is_never_stored():
    svc, repo = _service()
    await svc.save(USER, "anthropic", USER_KEY)
    stored = repo.rows[(USER, "anthropic")]
    assert USER_KEY not in stored["ciphertext"]
    assert USER_KEY not in str(stored)


@pytest.mark.asyncio
async def test_status_exposes_only_last4_and_never_the_key():
    svc, _ = _service()
    await svc.save(USER, "anthropic", USER_KEY)
    rows = await svc.status(USER)
    assert rows == [
        {
            "provider": "anthropic",
            "last4": USER_KEY[-4:],
            "validated_at": rows[0]["validated_at"],
            "readable": True,
        }
    ]
    assert USER_KEY not in str(rows)


@pytest.mark.asyncio
async def test_status_flags_an_unreadable_row_so_the_ui_can_prompt_a_re_entry():
    svc, repo = _service()
    await svc.save(USER, "anthropic", USER_KEY)
    rotated, _ = _service(repo, spec=f"2:{K2}")
    assert (await rotated.status(USER))[0]["readable"] is False


@pytest.mark.asyncio
async def test_resolve_never_leaks_through_the_dataclass_repr():
    svc, _ = _service()
    await svc.save(USER, "anthropic", USER_KEY)
    creds = await svc.resolve(USER)
    assert USER_KEY not in repr(creds)
    assert USER_KEY not in str(creds)


# ── Validation before storing ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_rejected_key_is_not_stored():
    async def _rejecting(provider: str, key: str) -> None:
        raise RuntimeError("nope")

    svc, repo = _service(validator=_rejecting)
    with pytest.raises(RuntimeError):
        await svc.save(USER, "anthropic", USER_KEY)
    assert repo.rows == {}


@pytest.mark.asyncio
async def test_validation_stamps_validated_at():
    svc, _ = _service()
    result = await svc.save(USER, "anthropic", USER_KEY)
    assert result["validated_at"] is not None
    assert result["last4"] == USER_KEY[-4:]


@pytest.mark.asyncio
async def test_whitespace_is_trimmed_so_a_pasted_key_still_works():
    svc, _ = _service()
    await svc.save(USER, "anthropic", f"  {USER_KEY}\n")
    assert (await svc.resolve(USER)).anthropic.reveal() == USER_KEY


@pytest.mark.asyncio
async def test_blank_and_unknown_inputs_are_rejected():
    svc, _ = _service()
    with pytest.raises(ValueError):
        await svc.save(USER, "anthropic", "   ")
    with pytest.raises(ValueError):
        await svc.save(USER, "not-a-provider", USER_KEY)
    with pytest.raises(ValueError):
        await svc.delete(USER, "not-a-provider")


# ── Delete ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_removes_the_key_and_reverts_to_the_platform():
    svc, _ = _service()
    await svc.save(USER, "anthropic", USER_KEY)
    assert await svc.delete(USER, "anthropic") is True

    creds = await svc.resolve(USER)
    assert creds.anthropic.reveal() == PLATFORM_ANTHROPIC
    assert creds.byok is False
    assert await svc.delete(USER, "anthropic") is False  # idempotent


# ── Re-save ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_re_saving_replaces_rather_than_duplicating():
    svc, repo = _service()
    await svc.save(USER, "anthropic", USER_KEY)
    second = "sk-ant-api03-SECONDKEY98765432"
    await svc.save(USER, "anthropic", second)
    assert len(await repo.list_for_user(USER)) == 1
    assert (await svc.resolve(USER)).anthropic.reveal() == second


def test_resolved_credentials_is_immutable():
    """Resolved once per request and passed down — nothing downstream should be
    able to swap the key mid-request."""
    from salli.domain.secrets import Secret

    creds = ResolvedCredentials(
        anthropic=Secret("a"),
        anthropic_is_user_key=False,
    )
    with pytest.raises(Exception):
        creds.anthropic = Secret("b")  # type: ignore[misc]


def test_aad_binds_both_user_and_provider():
    assert aad_for("u1", "anthropic") != aad_for("u2", "anthropic")
    assert aad_for("u1", "anthropic") != aad_for("u2", "anthropic")


# ── The composition-level gates ───────────────────────────────────────────────
#
# These construct Settings with the auth fields set EXPLICITLY. Settings reads
# the repo .env, which sets supabase_url locally, so a test that omitted them
# would silently exercise the wrong branch.


def _built(**overrides: Any):
    from salli.composition import _build_llm_credentials
    from salli.config import Settings

    base = {
        "byok_encryption_keys": f"1:{K1}",
        "supabase_url": "https://project.supabase.co",
        "supabase_jwt_secret": "",
    }
    return _build_llm_credentials(Settings(**{**base, **overrides}), lambda: None)


def test_available_with_an_encryption_key_and_real_auth():
    assert _built().available is True


def test_unavailable_without_an_encryption_key_at_all():
    assert _built(byok_encryption_keys="").available is False


def test_unavailable_when_the_dev_auth_fallback_is_live():
    """deps.get_principal treats the bearer token AS the user id when Supabase
    is entirely unconfigured and the development fallback is on. BYOK there
    would let any caller spend an arbitrary user's key, so it must stay off."""
    live = {"salli_insecure_dev_auth": True, "environment": "development"}
    assert _built(supabase_url="", supabase_jwt_secret="", **live).available is False


def test_available_without_supabase_when_the_dev_fallback_is_off():
    """No Supabase and no fallback: the API takes only Salli's own tokens, which
    are real. The gate is the fallback, the same one get_principal applies."""
    off = {"salli_insecure_dev_auth": False}
    assert _built(supabase_url="", supabase_jwt_secret="", **off).available is True


def test_a_jwt_secret_alone_is_enough_to_count_as_real_auth():
    assert _built(supabase_url="", supabase_jwt_secret="s3cret").available is True
