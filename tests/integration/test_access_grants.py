"""Read-only access to another member's books, end to end: a grant stored in
a real database, listed on both sides, audited in both logs, and used over
HTTP with personal access tokens: the grantee reads the grantor's books by
naming them (Salli-Books), may change nothing, reads nothing outside the
books, and nothing at all once either of them ends it."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from salli.adapters.auth.passwords import Argon2PasswordHasher
from salli.application.services.access_grant_service import AccessGrantService
from salli.application.services.login_service import LoginService
from salli.application.services.personal_access_token_service import PersonalAccessTokenService
from salli.application.services.reminder_service import ReminderService
from salli.config import Settings
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

PASSWORD = "a long enough password"


async def _members(uow_factory) -> tuple[str, str, str]:
    hasher = Argon2PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    logins = LoginService(uow_factory, hasher, default_currency="CHF")
    ada = await logins.create_account("ada@example.org", PASSWORD, owner=True)
    bo = await logins.create_account("bo@example.org", PASSWORD)
    cy = await logins.create_account("cy@example.org", PASSWORD)
    return ada["user_id"], bo["user_id"], cy["user_id"]


async def _actions(uow_factory, user_id: str) -> list[str]:
    async with uow_factory() as uow:
        rows = await uow._session.execute(  # noqa: SLF001
            text("select action from audit_logs where user_id = :u order by created_at"),
            {"u": user_id},
        )
        return [r[0] for r in rows]


async def test_a_grant_is_listed_both_sides_audited_and_ended_by_either(uow_factory):
    ada, bo, _ = await _members(uow_factory)
    access = AccessGrantService(uow_factory)
    with pytest.raises(LookupError):
        await access.grant(ada, "nobody@example.org")
    with pytest.raises(ValueError):
        await access.grant(ada, "ADA@example.org")

    given = await access.grant(ada, "Bo@Example.org")
    assert (given["member_id"], given["member_email"]) == (bo, "bo@example.org")
    assert (await access.grant(ada, "bo@example.org"))["id"] == given["id"]  # one live grant
    assert [g["member_id"] for g in (await access.list(ada))["given"]] == [bo]
    assert [g["member_id"] for g in (await access.list(bo))["received"]] == [ada]
    assert await access.may_read(bo, ada, "/accounts/")
    assert not await access.may_read(ada, bo, "/accounts/")

    assert await access.revoke(bo, given["id"])  # the grantee may end it too
    assert not await access.may_read(bo, ada, "/accounts/")
    assert await access.list(ada) == {"given": [], "received": []}
    assert not await access.revoke(ada, given["id"])
    assert await _actions(uow_factory, ada) == [
        "access_grant.give",
        "access_grant.give",
        "access_grant.read",
        "access_grant.revoke",
    ]
    assert await _actions(uow_factory, bo) == [
        "access_grant.receive",
        "access_grant.receive",
        "access_grant.revoke",
    ]


async def test_over_http_the_grantee_only_reads_the_grantors_books(uow_factory):
    from salli.interfaces.api.deps import get_services, get_settings
    from salli.interfaces.api.main import create_app

    ada, bo, cy = await _members(uow_factory)
    tokens = PersonalAccessTokenService(uow_factory)
    access = AccessGrantService(uow_factory)
    reminders = ReminderService(uow_factory)
    await reminders.create_reminder(ada, "Ada's renewal", "2026-12-01")

    async def member(*_: object, **__: object) -> bool:
        return True

    app = create_app()
    app.dependency_overrides[get_services] = lambda: SimpleNamespace(
        tokens=tokens,
        access=access,
        reminders=reminders,
        profile=SimpleNamespace(ensure_user=member),
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, environment="production"
    )
    api = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    def as_(user: str, token: str, books: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {token}"}
        return {**headers, "Salli-Books": books} if books else headers

    bo_token = (await tokens.create(bo, "laptop"))["token"]
    cy_token = (await tokens.create(cy, "laptop"))["token"]
    ada_token = (await tokens.create(ada, "laptop"))["token"]

    # No grant: refused.
    assert (await api.get("/v1/reminders/", headers=as_(bo, bo_token, ada))).status_code == 403
    # A token may not give access.
    made = await api.post(
        "/v1/access-grants", json={"email": "bo@example.org"}, headers=as_(ada, ada_token)
    )
    assert made.status_code == 403
    grant = await access.grant(ada, "bo@example.org")

    read = await api.get("/v1/reminders/", headers=as_(bo, bo_token, ada))
    assert read.status_code == 200
    assert [r["kind"] for r in read.json()["reminders"]] == ["Ada's renewal"]
    # Bo's own books, without naming Ada's.
    own = await api.get("/v1/reminders/", headers=as_(bo, bo_token))
    assert own.json()["reminders"] == []
    # Never a change, never outside the books, never someone else's.
    write = await api.post(
        "/v1/reminders/",
        json={"description": "x", "due_date": "2026-12-01"},
        headers=as_(bo, bo_token, ada),
    )
    assert write.status_code == 403
    assert (await api.get("/v1/tokens", headers=as_(bo, bo_token, ada))).status_code == 403
    assert (await api.get("/v1/reminders/", headers=as_(cy, cy_token, ada))).status_code == 403

    listed = await api.get("/v1/access-grants", headers=as_(bo, bo_token))
    assert [g["member_email"] for g in listed.json()["received"]] == ["ada@example.org"]
    ended = await api.delete(f"/v1/access-grants/{grant['id']}", headers=as_(ada, ada_token))
    assert ended.status_code == 204
    assert (await api.get("/v1/reminders/", headers=as_(bo, bo_token, ada))).status_code == 403
