"""Unit tests for McpOAuthService's per-user toggle using in-memory fakes.

Only the toggle is covered here (is_mcp_enabled / set_mcp_enabled) — the
OAuth flow itself (DCR, PKCE, token exchange) is exercised by the
standalone integration script used when that feature was built, not by these
unit tests.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from salli.application.services.mcp_oauth_service import McpOAuthService

# ── In-memory fakes ────────────────────────────────────────────────────────────


class FakeUserProfileRepo:
    def __init__(self, mcp_enabled_by_user=None):
        self._profiles: dict[str, dict] = {
            uid: {"id": uid, "mcp_enabled": enabled}
            for uid, enabled in (mcp_enabled_by_user or {}).items()
        }

    async def get(self, user_id):
        return self._profiles.get(user_id)

    async def upsert(self, user_id, fields):
        row = self._profiles.setdefault(user_id, {"id": user_id})
        row.update(fields)


class FakeUoW:
    def __init__(self, user_profiles):
        self.user_profiles = user_profiles

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


def _make_service(mcp_enabled_by_user=None):
    user_profiles = FakeUserProfileRepo(mcp_enabled_by_user)

    @asynccontextmanager
    async def uow_factory():
        yield FakeUoW(user_profiles)

    return McpOAuthService(
        uow_factory,
        signing_secret="test-secret",
        mcp_resource_url="https://api.test/mcp",
        consent_url="https://app.test/oauth/consent",
        auth_code_ttl_seconds=120,
        access_token_ttl_seconds=3600,
        refresh_token_ttl_seconds=2592000,
    )


# ── is_mcp_enabled / set_mcp_enabled ─────────────────────────────────────────────
#
# The user's own toggle is the whole decision: nothing about who they are or
# what they pay is consulted.


@pytest.mark.asyncio
async def test_is_mcp_enabled_false_when_never_enabled():
    svc = _make_service()
    assert await svc.is_mcp_enabled("user-1") is False


@pytest.mark.asyncio
async def test_is_mcp_enabled_true_with_the_flag_set():
    svc = _make_service(mcp_enabled_by_user={"user-1": True})
    assert await svc.is_mcp_enabled("user-1") is True


@pytest.mark.asyncio
async def test_set_mcp_enabled_switches_it_on():
    svc = _make_service()
    await svc.set_mcp_enabled("user-1", True)
    assert await svc.is_mcp_enabled("user-1") is True


@pytest.mark.asyncio
async def test_the_toggle_revokes_immediately_when_switched_off():
    """The live check is what makes disabling take effect on already-issued
    tokens, rather than only on future grants."""
    svc = _make_service(mcp_enabled_by_user={"user-1": True})
    await svc.set_mcp_enabled("user-1", False)
    assert await svc.is_mcp_enabled("user-1") is False
