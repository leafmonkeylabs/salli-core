"""/v1/export/* — the ledger as a downloadable plain-text journal."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("fmt", "filename"), [("beancount", "salli.beancount"), ("hledger", "salli.journal")]
)
async def test_the_journal_downloads_as_text(client, mock_services, fmt, filename):
    mock_services.data_portability = AsyncMock()
    mock_services.data_portability.export_plaintext.return_value = "; journal\n"
    r = await client.get(f"/v1/export/{fmt}", headers=AUTH)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert r.headers["content-disposition"] == f'attachment; filename="{filename}"'
    assert r.text == "; journal\n"
    mock_services.data_portability.export_plaintext.assert_awaited_once_with("test-user-1", fmt)
