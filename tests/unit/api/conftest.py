"""
API test fixtures.

Uses httpx.AsyncClient with the FastAPI test transport so no real DB or LLM
is needed. All services are replaced with async mocks.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException, Request, status
from httpx import ASGITransport, AsyncClient

from salli.application.defaults import FullAccess
from salli.domain.accounting.models import Direction
from salli.domain.ai_models import DEFAULT_MODEL


@pytest.fixture
def mock_services():
    svc = MagicMock()
    svc.ledger = AsyncMock()
    # Routers that report amounts say which currency they are in.
    svc.ledger.base_currency.return_value = "LKR"
    # tax.list_packs is sync (reads in-memory registry); others are async
    svc.tax = AsyncMock()
    svc.tax.list_packs = MagicMock()
    svc.agent = AsyncMock()
    svc.fi = AsyncMock()
    svc.advisor = AsyncMock()
    # Salli's own seams as shipped: an AsyncMock meter (allows everything, and
    # records what it was asked) and the real full-access policy.
    svc.usage = AsyncMock()
    svc.entitlements = FullAccess()
    # Metered routers ask for the caller's chosen model first, so this has to
    # be awaitable and return a real id — a MagicMock model would reach the
    # meter as an object rather than a model id.
    # Named `profile` to match composition.Services. A MagicMock would happily
    # answer to any attribute, which is exactly how a wrong name reached the
    # routers with a green suite behind it.
    svc.profile = AsyncMock()
    svc.profile.get_preferred_model.return_value = DEFAULT_MODEL
    return svc


def _fake_current_user(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return auth.removeprefix("Bearer ").strip()


def _fake_current_email(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return None


@pytest.fixture
def app(mock_services):
    from salli.interfaces.api.deps import get_current_email, get_current_user, get_services
    from salli.interfaces.api.main import create_app

    application = create_app()
    application.dependency_overrides[get_services] = lambda: mock_services
    application.dependency_overrides[get_current_user] = _fake_current_user
    application.dependency_overrides[get_current_email] = _fake_current_email
    return application


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


AUTH = {"Authorization": "Bearer test-user-1"}


def make_account(
    id: str = "acc-1", code: str = "1000", name: str = "Cash", tax_role: str | None = None
):
    a = MagicMock()
    a.id = id
    a.code = code
    a.name = name
    a.type = "asset"
    a.currency = "LKR"
    a.parent_id = None
    a.is_active = True
    a.tax_role = tax_role
    return a


def make_entry():
    e = MagicMock()
    e.id = "entry-1"
    e.entry_date = "2025-01-15"
    e.description = "Salary"
    e.source = "manual"
    e.external_ref = None
    e.reversed_by = None
    p = MagicMock()
    p.id = "posting-1"
    p.tags = {}
    p.account_id = "acc-1"
    p.direction = Direction.DEBIT
    p.amount = Decimal("100000")
    p.currency = "LKR"
    p.fx_rate = Decimal("1")
    e.postings = [p]
    return e
