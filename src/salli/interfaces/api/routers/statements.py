"""
Statement parsing router.

POST /statements/upload     — upload a bank statement (PDF/XLSX/CSV), returns ParseResult
GET  /statements/            — statements uploaded so far, newest first
GET  /statements/{id}       — fetch pending transactions for a statement
POST /statements/{id}/post  — approve and post selected transactions as journal entries
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, status
from pydantic import BaseModel

from salli.domain.currency import quantize
from salli.domain.parsing.models import ParsedTransaction
from salli.domain.usage import AIAction
from salli.interfaces.api.contract import Amount, CurrencyCode, FileUpload
from salli.interfaces.api.deps import AppServices, CurrentEmail, CurrentUser

router = APIRouter(prefix="/statements", tags=["statements"])


class StatementTransaction(BaseModel):
    """A transaction read from a statement and classified, awaiting review."""

    #: What to approve it by (POST /statements/{statement_id}/post).
    id: str
    date: str
    description: str
    #: Always positive: `credit_flag` says which way the money moved.
    amount: Amount
    #: True when money came in.
    credit_flag: bool
    bank_ref: str
    #: The statement's currency.
    currency: CurrencyCode
    #: The accounts the classifier chose; empty or null when it could not.
    debit_account_id: str | None
    credit_account_id: str | None
    #: The classifier's label ("salary", "bank_charge"); posting tags it.
    category: str | None
    #: The classifier's confidence, from 0 to 1.
    confidence: float
    #: "pending" until posted; "exact_duplicate" ones are never posted.
    dedup_status: str


class StatementUpload(BaseModel):
    statement_id: str
    bank: str
    period_start: str
    period_end: str
    #: Rows read from the file.
    total_rows: int
    #: Transactions classified and kept for review.
    parsed: int
    errors: list[str]
    transactions: list[StatementTransaction]


class BankStatement(BaseModel):
    id: str
    bank: str | None
    period_start: str | None
    period_end: str | None
    status: str
    created_at: str


class BankStatementList(BaseModel):
    statements: list[BankStatement]


class PendingStatementTransactions(BaseModel):
    statement_id: str
    transactions: list[StatementTransaction]


class PostedStatementTransactions(BaseModel):
    #: How many transactions became journal entries.
    posted: int
    entry_ids: list[str]


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_statement(
    form: Annotated[FileUpload, Form(media_type="multipart/form-data")],
    user_id: CurrentUser,
    email: CurrentEmail,
    svc: AppServices,
    bank: str = "",
    currency: str | None = None,
) -> StatementUpload:
    """
    Parse a bank statement file. Returns the statement_id and extracted transactions.
    Transactions have LLM-assigned accounts and dedup status; review before posting.
    Passes the deployment's usage meter before any parsing starts.

    `currency` is the statement's ISO 4217 code (default: the user's base
    currency). Posting a statement in another currency converts each
    transaction at the published rate for its date.
    """
    file = form.file
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
        currency=currency,
    )

    if result.errors and not result.transactions:
        raise HTTPException(status_code=422, detail=result.errors)

    return StatementUpload(
        statement_id=result.statement_id,
        bank=result.bank,
        period_start=result.period_start,
        period_end=result.period_end,
        total_rows=len(result.raw_rows),
        parsed=len(result.transactions),
        errors=result.errors,
        transactions=[_transaction(t) for t in result.transactions],
    )


@router.get("/")
async def list_statements(
    user_id: CurrentUser, svc: AppServices, limit: int = 50
) -> BankStatementList:
    """
    Statements this user has uploaded, newest first.

    These rows were always persisted — nothing exposed them, so the mobile app
    told users a statement history "isn't tracked by the server yet".
    """
    return BankStatementList.model_validate(
        {"statements": await svc.parsing.list_statements(user_id, limit)}
    )


@router.get("/{statement_id}")
async def get_pending(
    statement_id: str, user_id: CurrentUser, svc: AppServices
) -> PendingStatementTransactions:
    """Return unposted transactions for a statement."""
    txns = await svc.parsing.get_pending(user_id)
    return PendingStatementTransactions(
        statement_id=statement_id, transactions=[_transaction(t) for t in txns]
    )


class PostRequest(BaseModel):
    approved_ids: list[str]


@router.post("/{statement_id}/post")
async def post_approved(
    statement_id: str,
    body: PostRequest,
    user_id: CurrentUser,
    svc: AppServices,
) -> PostedStatementTransactions:
    """Post approved transactions as journal entries."""
    entry_ids = await svc.parsing.post_approved(user_id, body.approved_ids)
    return PostedStatementTransactions(posted=len(entry_ids), entry_ids=entry_ids)


def _transaction(t: ParsedTransaction) -> StatementTransaction:
    raw = t.raw
    return StatementTransaction(
        id=t.id,
        date=raw.date,
        description=raw.description,
        # As the extractor read it, which can carry more or fewer decimals
        # than the currency has; posting stores it at the currency's.
        amount=str(quantize(raw.amount, raw.currency, strict=False)),
        credit_flag=raw.credit_flag,
        bank_ref=raw.bank_ref,
        currency=raw.currency,
        debit_account_id=t.debit_account_id,
        credit_account_id=t.credit_account_id,
        category=t.category,
        confidence=t.confidence,
        dedup_status=t.dedup_status,
    )
