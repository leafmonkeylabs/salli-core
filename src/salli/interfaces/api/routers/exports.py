"""
The ledger as plain-text accounting — `/v1/export/beancount`, `/v1/export/hledger`.

Every account and entry, as a Beancount file or an hledger journal: leave
Salli with your whole ledger at any time, or use Fava or hledger alongside it.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/export", tags=["exports"])

_TEXT = {200: {"content": {"text/plain": {}}, "description": "The journal, as a file."}}


def _download(text: str, filename: str) -> PlainTextResponse:
    return PlainTextResponse(
        text, headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/beancount", response_class=PlainTextResponse, responses=_TEXT)  # type: ignore[arg-type]
async def export_beancount(user_id: CurrentUser, svc: AppServices) -> PlainTextResponse:
    """A Beancount file (`bean-check` clean)."""
    return _download(
        await svc.data_portability.export_plaintext(user_id, "beancount"), "salli.beancount"
    )


@router.get("/hledger", response_class=PlainTextResponse, responses=_TEXT)  # type: ignore[arg-type]
async def export_hledger(user_id: CurrentUser, svc: AppServices) -> PlainTextResponse:
    """An hledger journal (Ledger reads it too)."""
    return _download(
        await svc.data_portability.export_plaintext(user_id, "hledger"), "salli.journal"
    )
