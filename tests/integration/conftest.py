"""Fixtures for tests against a real, freshly migrated Postgres database.

The database is owned by, and Salli connects as, `salli_test_app`: no
superuser and no BYPASSRLS, so row-level security holds in every test as it
does on a server (docs/self-host.md, "The database role"). A service method
called straight from a test acts as a request would: for the person its
first argument naming a person (`user_id`, `actor`, ...) names, else for no one, so a method that reaches
across people must say so itself (application/acting.py). The test's own
setup, outside any service, acts for the system; so do raw connections, by
the role's default `salli.scope`, which Salli's sessions always set over.
"""

from __future__ import annotations

import functools
import importlib
import inspect
import pkgutil
from contextvars import ContextVar
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import salli.application.services as services_package
from salli.adapters.db.session import ActingSession
from salli.application import acting
from salli.application.unit_of_work import UnitOfWork
from salli.migrations.support import CORE_SCRIPT_LOCATION, upgrade
from tests.integration.pg import ADMIN_URL, _sync, scratch_database

#: The role Salli connects as in these tests (cluster-wide, made once).
APP_ROLE = "salli_test_app"


_made = False


def _ensure_role() -> None:
    global _made
    if _made:
        return
    _made = True
    admin = create_engine(_sync(ADMIN_URL), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            # Workers start together: one makes the role, the rest wait.
            conn.execute(text("SELECT pg_advisory_lock(5811)"))
            conn.execute(
                text(
                    "DO $$ BEGIN CREATE ROLE salli_test_app LOGIN NOSUPERUSER NOBYPASSRLS"
                    " PASSWORD 'salli_test_app'; EXCEPTION WHEN duplicate_object THEN NULL;"
                    " END $$"
                )
            )
            conn.execute(text("ALTER ROLE salli_test_app SET salli.scope = 'system'"))
            conn.execute(text("SELECT pg_advisory_unlock(5811)"))
    finally:
        admin.dispose()


def as_app_role(url: str) -> str:
    """`url`, its database owned by and reached as the app's role."""
    _ensure_role()
    name = make_url(url).database
    admin = create_engine(_sync(ADMIN_URL), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'ALTER DATABASE "{name}" OWNER TO {APP_ROLE}'))
    finally:
        admin.dispose()
    return (
        make_url(url)
        .set(username=APP_ROLE, password=APP_ROLE)
        .render_as_string(hide_password=False)
    )


@pytest.fixture
def db(monkeypatch):
    with scratch_database() as url:
        app = as_app_role(url)
        monkeypatch.setenv("DATABASE_URL", app)
        upgrade(CORE_SCRIPT_LOCATION)
        yield app


@pytest.fixture
async def uow_factory(db):
    engine = create_async_engine(db, connect_args={"statement_cache_size": 0})
    sessions = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession, sync_session_class=ActingSession
    )
    yield lambda: UnitOfWork(sessions)
    await engine.dispose()


def _as_its_person(method: Any) -> Any:
    signature = inspect.signature(method)

    @functools.wraps(method)
    async def run(*args: Any, **kwargs: Any) -> Any:
        if acting._acting.get() is not None:
            return await method(*args, **kwargs)
        given = signature.bind_partial(*args, **kwargs).arguments
        # The caller: the first argument naming a person.
        person = next(
            (
                getattr(value, "user_id", value)
                for name, value in given.items()
                if name in ("user_id", "grantor_id", "grantee_id", "actor")
            ),
            None,
        )
        with acting.acting_as(person) if isinstance(person, str) else _no_one():
            return await method(*args, **kwargs)

    return run


class _no_one:
    def __enter__(self) -> None:
        self._token = acting._acting.set(acting.Acting())

    def __exit__(self, *_: object) -> None:
        acting._acting.reset(self._token)


def _service_methods() -> list[tuple[type, str, Any]]:
    found = []
    for info in pkgutil.iter_modules(services_package.__path__):
        module = importlib.import_module(f"{services_package.__name__}.{info.name}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__ or not cls.__name__.endswith("Service"):
                continue
            for name, member in vars(cls).items():
                if not name.startswith("_") and inspect.iscoroutinefunction(member):
                    found.append((cls, name, member))
    return found


_SERVICE_METHODS = _service_methods()


@pytest.fixture
def real_boundaries() -> None:
    """Asked for by a test that drives Salli only through its own
    boundaries (HTTP, MCP, `salli-server`): nothing acts for anyone unless
    Salli says so."""


@pytest.fixture(autouse=True)
def _acting_as_a_request_would(request, monkeypatch):
    # A fresh variable each test: nothing one test (or a request it made in
    # its own task) acted as reaches the next.
    monkeypatch.setattr(acting, "_acting", ContextVar("salli_acting", default=None))
    if "real_boundaries" in request.fixturenames:
        return
    default = acting.Acting(system="tests")
    monkeypatch.setattr(acting, "current", lambda: acting._acting.get() or default)
    for cls, name, method in _SERVICE_METHODS:
        monkeypatch.setattr(cls, name, _as_its_person(method))
