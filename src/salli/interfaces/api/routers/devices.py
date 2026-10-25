"""
Devices router — the phones that take push alerts (docs/self-host.md#push-alerts).
A device is registered with its Expo push token, which is sealed at rest and
never shown again; its id is the token's SHA-256 hash. Only Salli's own
clients (the phone app, the console, the CLI) add or remove devices, and each
change is in the audit log.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from salli.application.services.mcp_oauth_service import (
    CLI_CLIENT_ID,
    CONSOLE_CLIENT_ID,
    MOBILE_CLIENT_ID,
)
from salli.application.services.notification_service import PushUnavailable
from salli.interfaces.api.deps import AppServices, CurrentPrincipal, CurrentUser, Principal

router = APIRouter(prefix="/devices", tags=["devices"])

_OWN_CLIENTS = frozenset({MOBILE_CLIENT_ID, CONSOLE_CLIENT_ID, CLI_CLIENT_ID})


def _own_client(principal: Principal) -> str | None:
    """The caller's client id; 403 unless it is one of Salli's own."""
    if principal.method == "dev":
        return None
    if principal.method != "oauth" or principal.client_id not in _OWN_CLIENTS:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Devices are added and removed from Salli's own apps."
        )
    return principal.client_id


class DeviceRequest(BaseModel):
    #: The Expo push token ("ExponentPushToken[...]").
    token: Annotated[str, Field(min_length=1, max_length=255)]
    platform: Literal["ios", "android"]


class Device(BaseModel):
    #: The token's SHA-256 hash: how the device is removed.
    id: str
    platform: Literal["ios", "android"]
    created_at: str


class DeviceList(BaseModel):
    devices: list[Device]
    #: Whether this server sends push alerts at all.
    push_enabled: bool


@router.get("/")
async def list_devices(user_id: CurrentUser, svc: AppServices) -> DeviceList:
    return DeviceList(
        devices=[Device.model_validate(d) for d in await svc.notifications.devices(user_id)],
        push_enabled=svc.notifications.push_enabled,
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_device(
    body: DeviceRequest, user_id: CurrentUser, principal: CurrentPrincipal, svc: AppServices
) -> Device:
    """Take push alerts on this phone: budget lines over their limit, the
    cash forecast below zero, reminders due. Registering the same token again
    replaces it. 403 from a client not Salli's own; 503 when this server
    sends no push alerts."""
    client_id = _own_client(principal)
    try:
        device = await svc.notifications.add_device(
            user_id, body.token, body.platform, client_id=client_id
        )
    except PushUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return Device.model_validate(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(
    device_id: str, user_id: CurrentUser, principal: CurrentPrincipal, svc: AppServices
) -> None:
    """Stop push alerts to a device. 403 from a client not Salli's own."""
    client_id = _own_client(principal)
    if not await svc.notifications.remove_device(user_id, device_id, client_id=client_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such device")
