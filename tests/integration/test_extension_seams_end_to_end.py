"""The generic extension seams, end to end against Postgres: an extension
(seams_extension.py) refuses capabilities with an offer, a usage limit under its
own problem type, shows panels (an invalid one never leaks), serves a page at
the root and acts under a system path it registered."""

from __future__ import annotations

from importlib.metadata import EntryPoint
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from salli.adapters.auth.passwords import Argon2PasswordHasher
from salli.application import acting
from salli.application.services.access_grant_service import AccessGrantService
from salli.application.services.login_service import LoginService
from salli.application.services.personal_access_token_service import PersonalAccessTokenService
from salli.config import Settings
from salli.extensions import ExtensionContext, build_extensions, combine, load_specs
from tests.integration import seams_extension
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

PASSWORD = "a long enough password"


def _specs(_settings=None):
    ep = EntryPoint("seams", "tests.integration.seams_extension:spec", "salli.extensions")
    return load_specs(["seams"], discover=lambda: [ep])


@pytest.fixture
async def api(uow_factory, monkeypatch):
    from salli.interfaces.api import main
    from salli.interfaces.api.deps import get_services, get_settings
    from salli.interfaces.api.routers import meta

    monkeypatch.setattr(acting, "SYSTEM_PATHS", dict(acting.SYSTEM_PATHS))
    monkeypatch.setattr(main, "enabled_specs", _specs)
    monkeypatch.setattr(meta, "enabled_specs", _specs)
    specs = _specs()
    contributions = combine(
        build_extensions(
            specs,
            ExtensionContext(
                settings=None, session_factory=None, uow_factory=uow_factory, llm_credentials=None
            ),
        )
    )
    hasher = Argon2PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    logins = LoginService(uow_factory, hasher, default_currency="CHF")
    ada = (await logins.create_account("ada@example.org", PASSWORD, owner=True))["user_id"]
    await logins.create_account("bo@example.org", PASSWORD)
    tokens = PersonalAccessTokenService(uow_factory)

    async def member(*_: object, **__: object) -> bool:
        return True

    app = main.create_app()
    app.dependency_overrides[get_services] = lambda: SimpleNamespace(
        tokens=tokens,
        access=AccessGrantService(uow_factory),
        entitlements=contributions.entitlements,
        usage=contributions.usage_meter,
        extensions=contributions,
        profile=SimpleNamespace(ensure_user=member),
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, environment="production"
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    token = (await tokens.create(ada, "laptop"))["token"]
    return SimpleNamespace(
        client=client, headers={"Authorization": f"Bearer {token}"}, app=app, ada=ada
    )


async def test_a_usage_refusal_carries_its_offer_under_the_extensions_problem_type(api):
    r = await api.client.get("/v1/seams/charge", headers=api.headers)
    assert r.status_code == 402
    body = r.json()
    assert body["type"] == "/problems/over-the-line"
    assert body["offer"] == {
        "title": "More room",
        "detail": "Ask for more.",
        "label": "See options",
        "panel": "options",
    }


async def test_a_refused_capability_is_a_403_with_the_offer(api):
    r = await api.client.get("/v1/seams/capability", headers=api.headers)
    body = r.json()
    assert (r.status_code, body["type"], body["capability"]) == (
        403,
        "/problems/capability-refused",
        "x-custom",
    )
    assert body["offer"]["panel"] == "options"


async def test_sharing_and_bank_formats_are_refused_before_anything_happens(api):
    from salli.interfaces.api.deps import Principal, get_principal

    api.app.dependency_overrides[get_principal] = lambda: Principal(
        user_id=api.ada, email="ada@example.org", method="session"
    )
    shared = await api.client.post(
        "/v1/access-grants", json={"email": "bo@example.org"}, headers=api.headers
    )
    assert shared.status_code == 403
    assert shared.json()["type"] == "/problems/capability-refused"
    assert shared.json()["capability"] == "member-sharing"
    listed = await api.client.get("/v1/access-grants", headers=api.headers)
    assert listed.json()["given"] == []

    formats = await api.client.post(
        "/v1/statements/check",
        files={"file": ("s.csv", b"date,amount\n2026-01-01,1\n")},
        data={"formats": '[{"schema": "salli.bankformat/1"}]'},
        headers=api.headers,
    )
    assert formats.status_code == 403
    assert formats.json()["capability"] == "bank-formats"


async def test_panels_are_listed_and_built_and_an_invalid_one_never_leaks(api):
    meta = await api.client.get("/v1/meta")
    assert meta.json()["panels"] is True

    listed = (await api.client.get("/v1/panels", headers=api.headers)).json()["panels"]
    assert {(p["id"], p["entry"]) for p in listed} == {
        ("options", "more"),
        ("leaky", None),
        ("broken", "settings"),
    }
    built = await api.client.get("/v1/panels/options", headers=api.headers)
    assert built.status_code == 200
    assert built.headers["cache-control"] == "no-store"
    assert built.json()["schema"] == "salli.panel/1"
    assert built.json()["sections"][0]["rows"][0]["value"] == "3.50"

    for bad in ("leaky", "broken"):
        r = await api.client.get(f"/v1/panels/{bad}", headers=api.headers)
        assert r.status_code == 500
        assert "elsewhere" not in r.text and "secret" not in r.text
    assert (await api.client.get("/v1/panels/nope", headers=api.headers)).status_code == 404
    # The list still works with panels that fail.
    assert (await api.client.get("/v1/panels", headers=api.headers)).status_code == 200


async def test_the_root_router_is_mounted_where_declared_and_api_routers_only_under_v1(api):
    assert (await api.client.get("/hello")).json() == {"hello": "root"}
    assert (await api.client.get("/v1/hello")).status_code == 404
    assert (await api.client.get("/seams/charge", headers=api.headers)).status_code == 404


async def test_an_extensions_system_path_works_and_unknown_ones_are_still_refused(api):
    seams_extension.own_system_path()
    assert "seams-sweep" in acting.SYSTEM_PATHS
    with pytest.raises(ValueError), acting.as_system("never-registered"):
        pass


async def test_an_account_can_be_made_with_a_password_hash_already_made(uow_factory):
    hasher = Argon2PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    logins = LoginService(uow_factory, hasher, default_currency="CHF")
    made = await logins.create_account(
        "cy@example.org", None, password_hash=await hasher.hash(PASSWORD)
    )
    assert made["email"] == "cy@example.org"
    assert (await logins.authenticate("cy@example.org", PASSWORD)) is not None
    with pytest.raises(ValueError):
        await logins.create_account("di@example.org", PASSWORD, password_hash="x")
    with pytest.raises(ValueError):
        await logins.create_account("di@example.org", None)
