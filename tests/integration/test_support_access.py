"""
Support access, end to end over HTTP (docs/security.md, "Support access"):
the operator's session reads only the person's books, for its time, every
read in the audit chain; the person sees it all and may end it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from salli.application import acting
from salli.application.services.support_access_service import (
    SupportAccessService,
    SupportRefused,
)
from salli.config import Settings
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

BASE = "http://test"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
async def salli(db, real_boundaries):
    from salli.composition import build_services
    from salli.interfaces.api.deps import get_services, get_settings
    from salli.interfaces.api.main import create_app

    settings = Settings(
        _env_file=None,
        database_url=db,
        environment="production",
        salli_public_url=BASE,
        mcp_signing_secret="s" * 48,
    )
    services = build_services(settings)
    clock = Clock()
    services.support = SupportAccessService(services.tokens._uow_factory, clock=clock)  # noqa: SLF001
    await services.logins.create_account(
        "owner@example.org", "the owner's long password", owner=True
    )
    await services.logins.create_account("ada@example.org", "ada's long password")
    app = create_app()
    app.dependency_overrides[get_services] = lambda: services
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        client.services, client.clock = services, clock  # type: ignore[attr-defined]
        yield client


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _as_ada(client: AsyncClient) -> dict[str, str]:
    signed_in = await client.post(
        "/v1/auth/sessions", json={"email": "ada@example.org", "password": "ada's long password"}
    )
    return _bearer(signed_in.json()["token"])


async def test_a_session_only_reads_the_books_and_every_read_is_shown(salli):
    services = salli.services
    with pytest.raises(SupportRefused):
        await services.support.open("ada@example.org", "  ")
    with pytest.raises(SupportRefused):
        await services.support.open("ada@example.org", "Ticket 7", minutes=241)
    with pytest.raises(SupportRefused):
        await services.support.open("nobody@example.org", "Ticket 7")

    opened = await services.support.open("ada@example.org", "Ticket 7: import stopped")
    assert opened["expires_at"] - opened["opened_at"] == timedelta(minutes=60)
    support = _bearer(opened["token"])

    assert (await salli.get("/v1/accounts/", headers=support)).status_code == 200
    assert (await salli.get("/v1/ledger/trial-balance", headers=support)).status_code == 200
    for method, path in (
        ("POST", "/v1/accounts/"),
        ("GET", "/v1/auth/me"),
        ("GET", "/v1/tokens"),
        ("GET", "/v1/auth/support-access"),
        ("GET", "/v1/onboarding/export"),
    ):
        refused = await salli.request(method, path, headers=support, json={})
        assert refused.status_code == 403, (method, path, refused.text)
    other = await salli.get("/v1/accounts/", headers={**support, "Salli-Books": "someone-else"})
    assert other.status_code == 403

    ada = await _as_ada(salli)
    [seen] = (await salli.get("/v1/auth/support-access", headers=ada)).json()
    assert (seen["reason"], seen["open"]) == ("Ticket 7: import stopped", True)
    assert [r["path"] for r in seen["reads"]] == ["/accounts/", "/ledger/trial-balance"]

    assert (
        await salli.delete(f"/v1/auth/support-access/{seen['id']}", headers=ada)
    ).status_code == 204
    assert (await salli.get("/v1/accounts/", headers=support)).status_code == 401
    [ended] = (await salli.get("/v1/auth/support-access", headers=ada)).json()
    assert (ended["open"], ended["ended_by"]) == (False, "person")
    assert (
        await salli.delete(f"/v1/auth/support-access/{seen['id']}", headers=ada)
    ).status_code == 404

    check = await services.agent.verify_audit_chain()
    assert check["ok"]
    ada_id = await _ada_id(services)
    with acting.acting_as(ada_id):
        async with services.tokens._uow_factory() as uow:  # noqa: SLF001
            rows = await uow.audit_log.list(ada_id)
    actions = [r["action"] for r in rows if r["action"].startswith("support.")]
    assert sorted(actions) == ["support.end", "support.open", "support.read", "support.read"]


async def _ada_id(services) -> str:
    login = next(x for x in await services.logins.list_logins() if x["email"] == "ada@example.org")
    return str(login["user_id"])


async def test_a_session_ends_with_its_time_and_the_operator_may_end_one(salli):
    services = salli.services
    timed = await services.support.open("ada@example.org", "Ticket 8", minutes=5)
    closed = await services.support.open("ada@example.org", "Ticket 9")
    assert (await salli.get("/v1/accounts/", headers=_bearer(timed["token"]))).status_code == 200

    salli.clock.now += timedelta(minutes=6)
    assert (await salli.get("/v1/accounts/", headers=_bearer(timed["token"]))).status_code == 401
    assert await services.support.close(closed["id"])
    assert not await services.support.close(closed["id"])

    seen = {s["reason"]: s for s in await services.support.list_all()}
    assert seen["Ticket 8"]["ended_by"] == "expiry"
    assert seen["Ticket 8"]["ended_at"] == timed["expires_at"]
    assert seen["Ticket 9"]["ended_by"] == "operator"
