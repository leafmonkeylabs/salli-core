"""
Statement parsing router.

POST /statements/upload        — upload a bank statement (PDF, XLSX, CSV, OFX/QFX, QIF,
                                 camt.053, MT940), returns ParseResult
POST /statements/drafts        — transactions the person's own automation drafted (a
                                 bank's text message, an email), for review
GET  /statements/               — statements uploaded so far, newest first
GET  /statements/{id}           — a statement's transactions still to review
POST /statements/{id}/post      — approve and post selected transactions as journal entries
POST /statements/{id}/discard   — discard pending transactions: they are never posted
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from salli.application.services.parsing_service import load_bank_formats, transaction_view
from salli.domain.parsing.models import ParsedTransaction, RawRow
from salli.interfaces.api.contract import Amount, AmountIn, CurrencyCode, FileUpload
from salli.interfaces.api.deps import AppServices, CurrentEmail, CurrentUser

router = APIRouter(prefix="/statements", tags=["statements"])


class SplitPart(BaseModel):
    """One part of a transaction that was for several things."""

    account_id: str
    #: In the transaction's currency; the parts add up to its amount.
    amount: AmountIn
    category: str = ""
    need: Literal["essential", "discretionary", "savings", ""] = ""


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
    #: The amount in the base currency as the bank gave it: the rate posted
    #: is derived from it. Null when the bank gave none.
    base_amount: Amount | None = None
    #: The other side split across accounts (`categorize`); empty for one.
    splits: list[SplitPart] = Field(default_factory=list["SplitPart"])


class StatementFileUpload(FileUpload):
    """A statement file, and the bank formats to read it with."""

    #: A JSON array of `salli.bankformat/1` documents stating the layout of a
    #: CSV file or of a PDF's or workbook's tables. Each is tried, and the one
    #: that reads the most rows is taken. Omitted: the layout is detected.
    formats: str | None = None


class FormatOutcomeView(BaseModel):
    #: The format's name.
    name: str
    #: Rows it read.
    parsed: int
    #: Rows or tables it could not read.
    failed: int
    #: Whether it was the one taken.
    chosen: bool


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
    #: Each bank format given, with what it read: empty when none was.
    formats: list[FormatOutcomeView] = []


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
    form: Annotated[StatementFileUpload, Form(media_type="multipart/form-data")],
    user_id: CurrentUser,
    email: CurrentEmail,
    svc: AppServices,
    bank: str = "",
    currency: str | None = None,
    account_id: str | None = None,
    source_account: str | None = None,
    replaces: str | None = None,
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

    A file holding several accounts (a QIF with a card register, an OFX with
    two statements) is imported one account at a time: `source_account`
    names the file's account to import when the statement's account does not
    match one by name or code. `replaces` is an earlier upload of the same
    statement, imported again on purpose: its rows are not taken for
    duplicates, and those still in review are discarded. `formats` (a form
    field) states the bank's layout as `salli.bankformat/1` documents; the
    result counts what each read and could not.
    """
    file = form.file
    if file.filename is None:
        raise HTTPException(status_code=400, detail="filename required")

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:  # 10 MB hard cap
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    try:
        formats = load_bank_formats(form.formats) if form.formats else []
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=[str(exc)]) from exc

    # The usage meter is charged inside, and only if the model is about to
    # run: a statement the user's rules sort entirely costs nothing.
    result = await svc.parsing.parse_statement(
        user_id=user_id,
        filename=file.filename,
        file_bytes=data,
        bank=bank,
        currency=currency,
        account_id=account_id,
        source_account=source_account,
        replaces=replaces,
        date_order=date_order,
        bank_formats=formats,
        email=email,
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
        formats=[FormatOutcomeView(**vars(f)) for f in result.formats],
    )


class StatementCheck(BaseModel):
    """What a statement holds, read and not stored: to check a bank format
    against the bank's own figures."""

    currency: CurrencyCode
    #: Transactions read.
    transactions: int
    money_in: Amount
    money_out: Amount
    first_date: str | None
    last_date: str | None
    #: The balances the file states, signed (positive in your favour); null
    #: when it states none (a format names them with a `balance` column).
    opening_balance: Amount | None
    closing_balance: Amount | None
    #: Whether opening + money in - money out = closing; null without both.
    balances_agree: bool | None
    errors: list[str]
    formats: list[FormatOutcomeView] = []


@router.post("/check")
async def check_statement(
    form: Annotated[StatementFileUpload, Form(media_type="multipart/form-data")],
    user_id: CurrentUser,
    svc: AppServices,
    currency: CurrencyCode | None = None,
    date_order: Literal["DMY", "MDY", "YMD"] | None = None,
) -> StatementCheck:
    """
    Read a statement file without importing it: how many transactions,
    money in and out, the dates, and the opening and closing balances, so
    you can compare them with the bank's statement before trusting a bank
    format (`formats`, as on upload). Stores nothing and runs no model.
    """
    file = form.file
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    try:
        formats = load_bank_formats(form.formats) if form.formats else []
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=[str(exc)]) from exc
    result = await svc.parsing.check(
        user_id,
        file.filename or "",
        data,
        currency=currency,
        date_order=date_order,
        bank_formats=formats,
    )
    return StatementCheck(
        **{**result, "formats": [FormatOutcomeView(**vars(f)) for f in result["formats"]]}
    )


class DraftTransaction(BaseModel):
    """One transaction as the person's automation read it: what a bank's
    message says, never the message itself."""

    #: When it happened, YYYY-MM-DD.
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2026-10-24"])
    #: Who was paid or who paid, as the message names them.
    description: str = Field(min_length=1, max_length=200)
    #: Always positive, as written in the message: `credit_flag` says which
    #: way the money moved.
    amount: AmountIn
    #: True when money came in.
    credit_flag: bool
    #: The bank's own reference for it, when the message gives one: the same
    #: reference drafted twice is one transaction.
    bank_ref: str = Field(default="", max_length=100)
    #: Its currency, when not the account's.
    currency: CurrencyCode | None = None
    #: The amount in your base currency, when the bank gives it: the rate
    #: posted is then derived from it.
    base_amount: AmountIn | None = None

    @field_validator("date")
    @classmethod
    def _real_date(cls, value: str) -> str:
        datetime.date.fromisoformat(value)
        return value

    @field_validator("amount")
    @classmethod
    def _positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("must be more than zero: credit_flag says which way it went")
        return value


class DraftRequest(BaseModel):
    #: The account they are on (an active asset or liability account): the
    #: money side of each, as a statement's account is.
    account_id: str
    #: What drafted them, named for review ("Messages", "Mail"): the name of
    #: the batch they start when the account has none open.
    source: str = Field(min_length=1, max_length=60)
    transactions: list[DraftTransaction] = Field(min_length=1, max_length=50)


class DraftedTransactions(BaseModel):
    #: The drafts batch they joined; empty when every one was drafted before.
    statement_id: str
    #: How many joined it, to wait for review.
    drafted: int
    #: How many were left out as drafted before (the same message twice).
    duplicates_dropped: int
    errors: list[str]
    transactions: list[StatementTransaction]


@router.post("/drafts", status_code=status.HTTP_201_CREATED)
async def draft_transactions(
    body: DraftRequest, user_id: CurrentUser, email: CurrentEmail, svc: AppServices
) -> DraftedTransactions:
    """
    Transactions drafted by the person's own automation — a bank's text
    message or email handed over by a shortcut — to wait for review as an
    import's do. Nothing is posted: they are approved, changed or discarded
    from review like any statement's (`/statements/{statement_id}/post`).

    They join the account's drafts batch while any of it waits for review,
    or start one named `source`. Each is sorted as an import is, by the
    person's rules and then, when one is set up, the model (passing the
    usage meter first), and checked for duplicates: one drafted before (the
    same `bank_ref`, or the same day, amount, direction and description on
    this account) is left out and counted, and one that looks like an entry
    already booked, or a statement's row, is flagged for review.
    """
    result = await svc.parsing.draft(
        user_id,
        [
            RawRow(
                date=t.date,
                description=t.description,
                amount=t.amount,
                credit_flag=t.credit_flag,
                currency=t.currency or "",
                bank_ref=t.bank_ref,
                base_amount=t.base_amount,
            )
            for t in body.transactions
        ],
        account_id=body.account_id,
        source=body.source,
        email=email,
    )
    if result.errors and not result.transactions and not result.duplicates_dropped:
        raise HTTPException(status_code=422, detail=result.errors)
    return DraftedTransactions(
        statement_id=result.statement_id,
        drafted=len(result.transactions),
        duplicates_dropped=result.duplicates_dropped,
        errors=result.errors,
        transactions=[_transaction(t) for t in result.transactions],
    )


@router.get("/")
async def list_statements(
    user_id: CurrentUser, svc: AppServices, limit: int = 50
) -> BankStatementList:
    """
    Statements this user has uploaded, newest first.

    Every import is kept, so a client can show the history of what was
    uploaded.
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


class TransactionChoice(BaseModel):
    transaction_id: str
    #: Where the money came from (money in) or went (money out). The
    #: statement's own account stays the other side. Left out with `splits`.
    account_id: str = ""
    category: str | None = None
    need: Literal["essential", "discretionary", "savings"] | None = None
    #: A transaction for several things, split across accounts: two parts or
    #: more, adding up to its amount. Replaces `account_id`.
    splits: list[SplitPart] | None = Field(default=None, max_length=50)


class CategorizeRequest(BaseModel):
    choices: list[TransactionChoice] = Field(min_length=1, max_length=500)


class CategorizedTransactions(BaseModel):
    #: The transactions changed, in the order given.
    updated: list[str]


@router.post("/categorize")
async def categorize(
    body: CategorizeRequest, user_id: CurrentUser, svc: AppServices
) -> CategorizedTransactions:
    """Choose the other side of pending transactions before posting them:
    what the user decided, or an AI client of theirs (over MCP) proposed and
    they accepted. Replaces what a rule or the model chose. Only transactions
    waiting for review change (422 otherwise); one that is not yours is a 404."""
    updated = await svc.parsing.categorize(
        user_id, [c.model_dump(exclude_none=True) for c in body.choices]
    )
    return CategorizedTransactions(updated=updated)


def _transaction(t: ParsedTransaction) -> StatementTransaction:
    return StatementTransaction.model_validate(transaction_view(t))
