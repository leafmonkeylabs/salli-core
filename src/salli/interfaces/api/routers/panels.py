"""
Panels — `/v1/panels`: screens an extension adds to the phone app and the
console, as a document (`salli.panel/1`, docs/design/panels.md).

Salli's own clients only: an agent connection or another application is
refused, as a panel's actions act for the person. An extension's builder may
fail or return something invalid; that is a logged 500 for that panel alone,
never a half-built screen and never a crash of the page that lists them.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from salli.application.permissions import is_first_party
from salli.domain.panels import Panel, check_panel
from salli.interfaces.api.deps import AppServices, CurrentPrincipal, CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/panels", tags=["panels"])


class PanelEntry(BaseModel):
    id: str
    title: str
    #: Where the clients list it: "more", "settings", or null (reached only
    #: from an offer or another panel).
    entry: Literal["more", "settings"] | None


class PanelList(BaseModel):
    panels: list[PanelEntry]


def _first_party_only(principal: CurrentPrincipal) -> None:
    if not is_first_party(principal.method, first_party_client=principal.first_party_client):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only your own sign-in in a Salli client can show these screens.",
        )


@router.get("")
async def list_panels(
    principal: CurrentPrincipal, _user: CurrentUser, svc: AppServices
) -> PanelList:
    """The screens this deployment adds, for the clients' "more" and settings lists."""
    _first_party_only(principal)
    return PanelList(
        panels=[PanelEntry(id=p.id, title=p.title, entry=p.entry) for p in svc.extensions.panels]
    )


@router.get(
    "/{panel_id}",
    responses={
        404: {"description": "No such panel"},
        500: {"description": "It could not be built"},
    },
)
async def get_panel(
    panel_id: str, principal: CurrentPrincipal, user_id: CurrentUser, svc: AppServices
) -> Panel:
    """One screen, built for you now, and checked against `salli.panel/1`
    before it is sent."""
    _first_party_only(principal)
    spec = next((p for p in svc.extensions.panels if p.id == panel_id), None)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such panel.")
    try:
        document = check_panel(await spec.builder(user_id))
        if document["id"] != spec.id:
            raise ValueError("the panel's id is not the one registered")
    except Exception:
        logger.exception("panel %s could not be built", spec.id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="This screen could not be built."
        ) from None
    return Panel.model_validate(document)
