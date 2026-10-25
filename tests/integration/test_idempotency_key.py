"""
A POST sent again with the same Idempotency-Key is not made twice: the
first answer comes back (marked `Idempotent-Replayed`), kept in the same
table as MCP's client_refs; a failed one is released for a retry.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from tests.integration.pg import requires_postgres
from tests.integration.test_console_sign_in import API, BASE, OWNER, OWNER_PASSWORD, _app

pytestmark = requires_postgres


@pytest.fixture
async def salli(db, monkeypatch):
    app, services = await _app(db, monkeypatch)
    await services.logins.create_account(OWNER, OWNER_PASSWORD, owner=True, base_currency="EUR")
    token = (await services.logins.sign_in(OWNER, OWNER_PASSWORD)).token
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


async def test_the_same_key_writes_once(salli):
    body = {"kind": "custom", "due_date": "2031-03-01"}
    headers = {"Idempotency-Key": "remind-1"}
    first = await salli.post(f"{API}/reminders/", json=body, headers=headers)
    again = await salli.post(f"{API}/reminders/", json=body, headers=headers)
    other = await salli.post(
        f"{API}/reminders/", json=body, headers={"Idempotency-Key": "remind-2"}
    )
    assert first.status_code == again.status_code == 201
    assert again.json() == first.json()
    assert again.headers["Idempotent-Replayed"] == "true"
    assert other.json() != first.json()


async def test_a_failed_write_is_released(salli):
    headers = {"Idempotency-Key": "bad-1"}
    bad = await salli.post(f"{API}/reminders/", json={"kind": "custom"}, headers=headers)
    good = await salli.post(
        f"{API}/reminders/", json={"kind": "custom", "due_date": "2031-03-01"}, headers=headers
    )
    assert bad.status_code == 422
    assert good.status_code == 201
    assert "Idempotent-Replayed" not in good.headers


async def test_a_key_too_long_is_refused(salli):
    long = {"Idempotency-Key": "k" * 181}
    sent = await salli.post(
        f"{API}/reminders/", json={"kind": "custom", "due_date": "2031-03-01"}, headers=long
    )
    assert sent.status_code == 422
