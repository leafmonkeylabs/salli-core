"""
Statement parsing router.

POST /statements/upload     — upload a bank statement (PDF/XLSX/CSV), returns ParseResult
GET  /statements/            — statements uploaded so far, newest first
GET  /statements/{id}       — fetch pending transactions for a statement
POST /statements/{id}/post  — approve and post selected transactions as journal entries
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel

from salli.domain.usage import AIAction
from salli.interfaces.api.deps import AppServices, CurrentEmail, CurrentUser

router = APIRouter(prefix="/statements", tags=["statements"])


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_statement(
    file: UploadFile,
    user_id: CurrentUser,
    email: CurrentEmail,
    svc: AppServices,
    bank: str = "",
):
    """
    Parse a bank statement file. Returns the statement_id and extracted transactions.
    Transactions have LLM-assigned accounts and dedup status; review before posting.
    Passes the deployment's usage meter before any parsing starts.
    """
    if file.filename is None:
        raise HTTPException(status_code=400, detail="filename required")

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:  # 10 MB hard cap
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    await svc.usage.charge(user_id, AIAction.STATEMENT_IMPORT, email=email)

    result = await svc.parsing.parse_statement(
        user_id=user_id,
        filename=file.filename,
        file_bytes=data,
        bank=bank,
    )

    if result.errors and not result.transactions:
        raise HTTPException(status_code=422, detail=result.errors)

    return {
        "statement_id": result.statement_id,
        "bank": result.bank,
        "period_start": result.period_start,
        "period_end": result.period_end,
        "total_rows": len(result.raw_rows),
        "parsed": len(result.transactions),
        "errors": result.errors,
        "transactions": [_txn_dict(t) for t in result.transactions],
    }


@router.get("/")
async def list_statements(user_id: CurrentUser, svc: AppServices, limit: int = 50):
    """
    Statements this user has uploaded, newest first.

    These rows were always persisted — nothing exposed them, so the mobile app
    told users a statement history "isn't tracked by the server yet".
    """
    return {"statements": await svc.parsing.list_statements(user_id, limit)}


@router.get("/{statement_id}")
async def get_pending(statement_id: str, user_id: CurrentUser, svc: AppServices):
    """Return unposted transactions for a statement."""
    txns = await svc.parsing.get_pending(user_id)
    return {"statement_id": statement_id, "transactions": [_txn_dict(t) for t in txns]}


class PostRequest(BaseModel):
    approved_ids: list[str]


@router.post("/{statement_id}/post")
async def post_approved(
    statement_id: str,
    body: PostRequest,
    user_id: CurrentUser,
    svc: AppServices,
):
    """Post approved transactions as journal entries."""
    entry_ids = await svc.parsing.post_approved(user_id, body.approved_ids)
    return {"posted": len(entry_ids), "entry_ids": entry_ids}


def _txn_dict(t: object) -> dict:
    raw = t.raw  # type: ignore[attr-defined]
    return {
        "id": getattr(t, "id", None),
        "date": raw.date,
        "description": raw.description,
        "amount": str(raw.amount),
        "credit_flag": raw.credit_flag,
        "bank_ref": raw.bank_ref,
        "currency": raw.currency,
        "debit_account_id": t.debit_account_id,  # type: ignore[attr-defined]
        "credit_account_id": t.credit_account_id,  # type: ignore[attr-defined]
        "category": t.category,  # type: ignore[attr-defined]
        "confidence": t.confidence,  # type: ignore[attr-defined]
        "dedup_status": t.dedup_status,  # type: ignore[attr-defined]
    }
