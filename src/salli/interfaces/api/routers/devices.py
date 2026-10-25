"""
Devices router — the phones that take push alerts (docs/self-host.md#push-alerts).
A device is registered with its Expo push token, which is sealed at rest and
never shown again; its id is the token's SHA-256 hash.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from salli.application.services.notification_service import PushUnavailable
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/devices", tags=["devices"])


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
async def add_device(body: DeviceRequest, user_id: CurrentUser, svc: AppServices) -> Device:
    """Take push alerts on this phone: budget lines over their limit, the
    cash forecast below zero, reminders due. Registering the same token again
    replaces it. 503 when this server sends no push alerts."""
    try:
        device = await svc.notifications.add_device(user_id, body.token, body.platform)
    except PushUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return Device.model_validate(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(device_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    """Stop push alerts to a device."""
    if not await svc.notifications.remove_device(user_id, device_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such device")
