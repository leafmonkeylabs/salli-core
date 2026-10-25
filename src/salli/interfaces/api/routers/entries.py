from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from salli.domain.accounting.models import BooksLocked, Source, StoredJournalEntry
from salli.domain.accounting.models import Posting as DomainPosting
from salli.domain.currency import quantize
from salli.domain.usage import AIAction
from salli.interfaces.api.contract import Amount, CurrencyCode, DecimalString, Ref
from salli.interfaces.api.deps import AppServices, CurrentEmail, CurrentUser

router = APIRouter(prefix="/entries", tags=["entries"])


class PostingRequest(BaseModel):
    account_id: str
    direction: int  # 1 = DEBIT, -1 = CREDIT
    #: A decimal string, never a JSON number (which a client holds as a float).
    amount: DecimalString
    #: ISO 4217. Omitted: the user's base currency.
    currency: str | None = None
    #: Units of base currency per unit of `currency` — the rate the bank used.
    #: Omitted: 1 for the base currency, else the published rate for the
    #: entry's date (422 if there is none: give it then).
    fx_rate: DecimalString | None = None
    fx_rate_source: str | None = None
    # Axis → tag slug, e.g. {"category": "groceries", "need": "essential"}.
    # Tags that do not exist yet are created on the axis named here, so a client
    # can tag freely without a separate call to define the tag first.
    tags: dict[str, str] = {}


class AddEntryRequest(BaseModel):
    entry_date: str  # YYYY-MM-DD
    description: str
    source: Literal["manual", "statement", "sms", "system"] = "manual"
    external_ref: str | None = None
    postings: list[PostingRequest]


class ParseEntryRequest(BaseModel):
    text: str


class AccountHint(BaseModel):
    """A suggested NEW account (name + type) when the parser couldn't match an
    existing one but can infer what kind of account the transaction implies."""

    name: str
    type: Literal["asset", "liability", "equity", "income", "expense"]


class ParsedEntryDraft(BaseModel):
    entry_type: Literal["income", "expense", "transfer"]
    amount: str
    description: str
    debit_account_id: str | None = None
    credit_account_id: str | None = None
    debit_account_hint: AccountHint | None = None
    credit_account_hint: AccountHint | None = None
    currency: str
    confidence: float = 0.0


class Posting(BaseModel):
    #: Needed to retag: tags are edited per posting.
    id: str
    #: Axis → tag slug, e.g. {"category": "groceries", "need": "essential"}.
    tags: dict[str, str]
    account_id: str
    #: 1 = debit, -1 = credit.
    direction: Literal[1, -1]
    #: In the posting's own `currency`.
    amount: Amount
    currency: CurrencyCode
    #: Units of base currency per unit of `currency`, as a decimal string.
    fx_rate: str


class JournalEntry(BaseModel):
    id: str
    entry_date: str
    description: str
    source: Source
    external_ref: str | None
    #: The entry that reversed this one; null while it stands.
    reversed_by: str | None
    #: For a reversal, the entry it reverses.
    reverses: str | None = None
    #: For a corrected copy (a recategorised entry), the entry it corrects:
    #: it keeps that entry's source and external_ref.
    corrects: str | None = None
    #: Who posted it: the signed-in person's user id, and how they came in
    #: (console, cli, mobile, mcp:<client>, oauth:<client>, token, import,
    #: automation; "unrecorded" for entries posted before Salli kept it).
    created_by: str | None = None
    created_via: str | None = None
    #: Its place in the ledger's hash chain, and its hash
    #: (`GET /v1/ledger/verify`).
    seq: int | None = None
    hash: str | None = None
    postings: list[Posting]


class ProvenanceStatementFile(BaseModel):
    """The uploaded bank statement a transaction was read from."""

    id: str
    bank: str | None
    period_start: str | None
    period_end: str | None
    storage_key: str
    status: str
    created_at: str


class ProvenanceStatement(BaseModel):
    """The bank-statement transaction an entry was posted from."""

    parsed_transaction_id: str
    raw_description: str
    #: The amount as the statement showed it, in `currency`.
    raw_amount: Amount
    currency: CurrencyCode
    raw_date: str
    bank_ref: str
    statement: ProvenanceStatementFile | None


class ProvenanceReceipt(BaseModel):
    """The uploaded document attached to a manual entry."""

    document_id: str
    title: str
    mime_type: str
    storage_key: str | None


class ProvenanceSubscription(BaseModel):
    """A recurring subscription this entry looks like a payment of."""

    subscription_id: str
    name: str


class EntryProvenance(BaseModel):
    entry_id: str
    entry_date: str
    description: str
    source: Source
    external_ref: str | None
    #: For a corrected copy, the entry it corrects: the provenance is that
    #: entry's, which the copy keeps.
    corrects: str | None = None
    #: Set when the entry was posted from a bank statement.
    statement: ProvenanceStatement | None
    #: Set when a manual entry has a receipt attached.
    receipt: ProvenanceReceipt | None
    possible_subscriptions: list[ProvenanceSubscription]


def _posting(p: DomainPosting) -> Posting:
    assert p.id is not None  # read back from storage, so it has one
    return Posting(
        id=p.id,
        tags=p.tags,
        account_id=p.account_id,
        direction=p.direction.value,
        amount=str(quantize(p.amount, p.currency, strict=False)),
        currency=p.currency,
        fx_rate=str(p.fx_rate),
    )


def _entry(e: StoredJournalEntry) -> JournalEntry:
    return JournalEntry(
        id=e.id,
        entry_date=e.entry_date,
        description=e.description,
        source=e.source,
        external_ref=e.external_ref,
        reversed_by=e.reversed_by,
        reverses=e.reverses,
        corrects=e.corrects,
        created_by=e.created_by,
        created_via=e.created_via,
        seq=e.seq,
        hash=e.hash,
        postings=[_posting(p) for p in e.postings],
    )


@router.post("/parse")
async def parse_entry(
    body: ParseEntryRequest, user_id: CurrentUser, email: CurrentEmail, svc: AppServices
) -> ParsedEntryDraft:
    """AI-parse a free-text / dictated note into a DRAFT entry (never posted).

    The LLM extracts the stated amount and maps the note to existing account ids;
    the client pre-fills the New Entry form for the user to review and post via
    the deterministic, balance-checked POST /entries/. Passes the deployment's
    usage meter like /agent/chat — it's an AI feature like any other.
    """
    if not svc.entry_parse.available:
        raise HTTPException(status_code=503, detail="AI parsing is not configured")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    await svc.usage.charge(user_id, AIAction.ENTRY_PARSE, email=email)
    draft = await svc.entry_parse.parse_draft(user_id, body.text)
    return ParsedEntryDraft(**draft)


@router.post("/", status_code=201)
async def add_entry(body: AddEntryRequest, user_id: CurrentUser, svc: AppServices) -> Ref:
    postings_data = [
        {
            "account_id": p.account_id,
            "direction": p.direction,
            "amount": Decimal(p.amount),
            "currency": p.currency,
            "fx_rate": Decimal(p.fx_rate) if p.fx_rate is not None else None,
            "fx_rate_source": p.fx_rate_source,
            "tags": p.tags,
        }
        for p in body.postings
    ]
    entry_id = await svc.ledger.add_entry(
        user_id=user_id,
        entry_date=body.entry_date,
        description=body.description,
        source=body.source,
        postings_data=postings_data,
        external_ref=body.external_ref,
    )
    return Ref(id=entry_id)


@router.get("/")
async def list_entries(
    user_id: CurrentUser,
    svc: AppServices,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[JournalEntry]:
    entries = await svc.ledger.get_entries(user_id, from_date, to_date)
    return [_entry(e) for e in entries]


class EntryTotal(BaseModel):
    account_type: Literal["asset", "liability", "equity", "income", "expense"]
    currency: CurrencyCode
    #: Debits less credits of the postings counted, over every match.
    net: Amount


class EntrySearch(BaseModel):
    #: This page, newest first.
    entries: list[JournalEntry]
    #: How many entries match in all.
    matches: int
    #: Over every match, not only this page: per account type and currency,
    #: the net of the postings counted (on `account_id`'s, when given).
    #: Spending is positive on expense accounts, income negative on income ones.
    totals: list[EntryTotal]
    #: The currency `min_amount` and `max_amount` are in: the base currency.
    amounts_in: CurrencyCode
    #: Pass as `cursor` for the next page; null on the last.
    next_cursor: str | None


@router.get("/search")
async def search_entries(
    user_id: CurrentUser,
    svc: AppServices,
    text: str | None = Query(None, description="In the description, any case"),
    account_id: str | None = Query(None, description="Only entries with a posting on it"),
    from_date: str | None = None,
    to_date: str | None = None,
    min_amount: DecimalString | None = Query(None, description="A posting at least this"),
    max_amount: DecimalString | None = Query(None, description="A posting at most this"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None, description="`next_cursor` from the page before"),
) -> EntrySearch:
    """Entries by text, account, dates and amount (in the base currency),
    newest first, with totals over every match."""
    try:
        found = await svc.ledger.search_entries(
            user_id,
            text=text,
            account_id=account_id,
            from_date=from_date,
            to_date=to_date,
            min_amount=None if min_amount is None else Decimal(min_amount),
            max_amount=None if max_amount is None else Decimal(max_amount),
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return EntrySearch.model_validate({**found, "entries": [_entry(e) for e in found["entries"]]})


@router.get("/{entry_id}")
async def get_entry(entry_id: str, user_id: CurrentUser, svc: AppServices) -> JournalEntry:
    entry = await svc.ledger.get_entry(user_id, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return _entry(entry)


@router.get("/{entry_id}/provenance")
async def get_entry_provenance(
    entry_id: str, user_id: CurrentUser, svc: AppServices
) -> EntryProvenance:
    """Where this entry came from: a bank-statement transaction, or an attached receipt."""
    provenance = await svc.ledger.get_entry_provenance(user_id, entry_id)
    if provenance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return EntryProvenance.model_validate(provenance)


class ReverseEntryRequest(BaseModel):
    #: Why the entry is reversed, in a few words; the reversal's description
    #: keeps it ("Reversal of <description>: <reason>").
    reason: Annotated[str, Field(min_length=1, max_length=200)]


@router.post("/{entry_id}/reverse", status_code=201)
async def reverse_entry(
    entry_id: str, body: ReverseEntryRequest, user_id: CurrentUser, svc: AppServices
) -> Ref:
    """Cancel an entry with its opposite, dated the entry's own day, or today
    when that day's books are closed or the bank's statement reconciled it."""
    try:
        reversing_id = await svc.ledger.reverse_entry(user_id, entry_id, body.reason)
    except BooksLocked:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Ref(id=reversing_id)


class RecategoriseRequest(BaseModel):
    #: The posting to move, one of the entry's.
    posting_id: str
    #: The account it moves to: one of yours, of the same type.
    account_id: str
    #: Why, in a few words; the reversal's description keeps it.
    reason: Annotated[str, Field(min_length=1, max_length=200)]


class Recategorised(BaseModel):
    #: The entry that reverses the original.
    reversal_id: str
    #: The corrected copy: the original's source and external_ref, and
    #: `corrects` naming the original.
    corrected_id: str
    #: "original": both are on the original's day, which is open, so the fix
    #: lands in its month; "today": that day is closed (`dated_reason`).
    dated: Literal["original", "today"]
    dated_reason: str | None = None


@router.post("/{entry_id}/recategorise", status_code=201)
async def recategorise_entry(
    entry_id: str, body: RecategoriseRequest, user_id: CurrentUser, svc: AppServices
) -> Recategorised:
    """Move one posting to another account (a category change), in one
    transaction: the entry's reversal and a corrected copy, both dated as a
    reversal is (its own day, or today when that day is closed or
    reconciled). Entries are never edited; refused in closed books (409)."""
    try:
        made = await svc.ledger.recategorise_entry(
            user_id, entry_id, body.posting_id, body.account_id, body.reason
        )
    except BooksLocked:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Recategorised.model_validate(made)


# ── tags ──────────────────────────────────────────────────────────────────────
#
# A second classification axis, orthogonal to the chart of accounts. Tags are
# metadata *about* an immutable posting: the money record never changes, but a
# miscategorised expense has to be fixable.


class SetPostingTagsRequest(BaseModel):
    tags: dict[str, str]


@router.put("/postings/{posting_id}/tags", status_code=status.HTTP_204_NO_CONTENT)
async def set_posting_tags(
    posting_id: str, body: SetPostingTagsRequest, user_id: CurrentUser, svc: AppServices
):
    """Replace a posting's tags. Retagging never touches the posted amounts;
    a posting in the closed books keeps its tags (409)."""
    try:
        await svc.ledger.set_posting_tags(user_id, posting_id, body.tags)
    except BooksLocked:
        raise
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
