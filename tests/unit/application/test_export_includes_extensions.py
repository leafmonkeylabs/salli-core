"""
"Export my data" includes what extensions hold about the user, after Salli's
own keys — and is complete without any extension at all.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from salli.application.services.data_portability_service import DataPortabilityService

pytestmark = pytest.mark.asyncio


def _service(exporters=()):
    # profile, ledger, tax, budget, debt, portfolio, subscription, insurance,
    # fi, advisor, documents, reminders
    svcs = [AsyncMock() for _ in range(12)]
    svcs[1].get_entries.return_value = []
    svcs[2].get_latest_computation.return_value = None
    return DataPortabilityService(MagicMock(), *svcs, exporters=exporters)


async def test_without_extensions_the_export_is_salli_only():
    data = await _service().export_all("u1")
    assert data["user_id"] == "u1"
    assert "bug_reports" not in data


async def test_extension_data_is_appended_after_salli_keys():
    async def export(user_id):
        return {"extension_rows": [user_id]}

    data = await _service([export]).export_all("u1")

    assert data["extension_rows"] == ["u1"]
    assert list(data)[-1] == "extension_rows"
