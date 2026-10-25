"""Push devices are added and removed only from Salli's own clients."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from .conftest import AUTH

USER = "test-user-1"


def _as(app, client_id: str) -> None:
    from salli.interfaces.api.deps import Principal, get_principal

    app.dependency_overrides[get_principal] = lambda: Principal(
        USER, None, "oauth", client_id=client_id, first_party_client=client_id.startswith("salli-")
    )


@pytest.mark.parametrize("client_id", ["some-ai-client", "salli-elsewhere"])
async def test_another_client_may_not_add_or_remove_devices(app, client, mock_services, client_id):
    _as(app, client_id)
    mock_services.notifications.add_device = AsyncMock()
    mock_services.notifications.remove_device = AsyncMock()
    body = {"token": "ExponentPushToken[x]", "platform": "ios"}
    assert (await client.post("/v1/devices/", json=body, headers=AUTH)).status_code == 403
    assert (await client.delete("/v1/devices/abc", headers=AUTH)).status_code == 403
    mock_services.notifications.add_device.assert_not_awaited()
    mock_services.notifications.remove_device.assert_not_awaited()


async def test_the_app_adds_a_device_and_its_client_is_audited(app, client, mock_services):
    _as(app, "salli-mobile")
    mock_services.notifications.add_device = AsyncMock(
        return_value={"id": "h", "platform": "ios", "created_at": "2026-10-25T00:00:00Z"}
    )
    body = {"token": "ExponentPushToken[x]", "platform": "ios"}
    assert (await client.post("/v1/devices/", json=body, headers=AUTH)).status_code == 201
    mock_services.notifications.add_device.assert_awaited_once_with(
        USER, "ExponentPushToken[x]", "ios", client_id="salli-mobile"
    )
