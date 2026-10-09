"""
Statement parsing router.

POST /statements/upload        — upload a bank statement (PDF, XLSX, CSV, OFX/QFX, QIF,
                                 camt.053, MT940), returns ParseResult
GET  /statements/               — statements uploaded so far, newest first
GET  /statements/{id}           — a statement's transactions still to review
POST /statements/{id}/post      — approve and post selected transactions as journal entries
POST /statements/{id}/discard   — discard pending transactions: they are never posted
"""

from __future__ import annotations

from typing import Annotated, Literal

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
    #: The account the statement is for: the money side, debited for money in
    #: and credited for money out. Null when the statement does not say.
    account_id: str | None
    #: The accounts to post to, from the statement's account, a rule or the
    #: classifier; empty or null while one is still to be chosen.
    debit_account_id: str | None
    credit_account_id: str | None
    #: The category ("salary", "groceries") from a rule or the classifier;
    #: posting tags the other side with it.
    category: str | None
    #: essential, discretionary or savings, from a rule; posting tags it too.
    need: str | None
    #: The rule that decided it, if one did.
    rule_id: str | None
    #: What the entry is booked as when that is not `description` (a rule's
    #: tidy name for the bank's text). Null: `description`.
    description_override: str | None
    #: 1 when the statement's account and a rule decided it, the classifier's
    #: confidence when it did, 0 while an account is still to be chosen.
    confidence: float
    #: "pending" until posted; "fuzzy_match" looks like an entry already
    #: booked, so check it; "exact_duplicate" repeats an earlier import and is
    #: never posted; "posted"; "discarded".
    dedup_status: str
    #: What it repeats: the earlier import's transaction (exact_duplicate) or
    #: the journal entry (fuzzy_match).
    duplicate_of: str | None


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
    #: The account the statement is for: the money side of its transactions.
    account_id: str | None = None
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


class DiscardRequest(BaseModel):
    #: The transactions to discard; every pending one of the statement when omitted.
    ids: list[str] | None = None


class DiscardedStatementTransactions(BaseModel):
    #: How many pending transactions were discarded.
    discarded: int


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_statement(
    form: Annotated[FileUpload, Form(media_type="multipart/form-data")],
    user_id: CurrentUser,
    email: CurrentEmail,
    svc: AppServices,
    bank: str = "",
    currency: str | None = None,
    account_id: str | None = None,
    date_order: Literal["DMY", "MDY", "YMD"] | None = None,
) -> StatementUpload:
    """
    Parse a bank statement file. Returns the statement_id and extracted transactions.
    Transactions have LLM-assigned accounts and dedup status; review before posting.
    Passes the deployment's usage meter before any parsing starts.

    `account_id` is the account the statement is for (an active asset or
    liability account): the money side of every transaction in it. `currency`
    is the statement's ISO 4217 code, for files that do not name their own
    (OFX, camt.053 and MT940 always do, and a CSV may); it defaults to the
    account's currency, else the user's base currency, and a transaction in
    another currency than the account's is skipped. Posting a statement in
    another currency than the base converts each transaction at the published
    rate for its date. `date_order` settles dates a CSV or QIF file leaves
    ambiguous (01/02/2026). Rows that could not be read, and any guess the
    importer made, come back in `errors`.
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
        account_id=account_id,
        date_order=date_order,
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
    """A statement's transactions still to review: neither posted nor discarded."""
    if await svc.parsing.get_statement(user_id, statement_id) is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    txns = await svc.parsing.get_pending(user_id, statement_id)
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


@router.post("/{statement_id}/discard")
async def discard(
    statement_id: str,
    user_id: CurrentUser,
    svc: AppServices,
    body: DiscardRequest | None = None,
) -> DiscardedStatementTransactions:
    """Discard a statement's pending transactions — those named in `ids`, or
    every one. A discarded transaction is never posted, leaves review, and is
    no duplicate of anything imported later."""
    count = await svc.parsing.discard(user_id, statement_id, body.ids if body else None)
    if count is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    return DiscardedStatementTransactions(discarded=count)


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
        account_id=t.account_id or None,
        debit_account_id=t.debit_account_id,
        credit_account_id=t.credit_account_id,
        category=t.category,
        need=t.need or None,
        rule_id=t.rule_id or None,
        description_override=t.description or None,
        confidence=t.confidence,
        dedup_status=t.dedup_status,
        duplicate_of=t.duplicate_of or None,
    )
