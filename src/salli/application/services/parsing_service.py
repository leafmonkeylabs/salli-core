"""
ParsingService — orchestrates statement ingestion.

Flow:
  upload file bytes
  → detect format (OFX/QFX, QIF, camt.053, MT940, CSV, PDF, XLSX) from the
    content, else the extension
  → extract RawRows (deterministic, no LLM), each in the file's own currency
    where it names one, else the caller's
  → run dedup check against existing entries
  → LLM classifies non-duplicate rows
  → persist to parsed_transactions table (status=pending)
  → return ParseResult for user review

  User calls post_approved() with the list of approved transaction IDs
  → converts to JournalEntries and posts to ledger
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from salli.application.fx import rate_to_base
from salli.application.ports import StoragePort
from salli.domain.currency import UnknownCurrencyError, normalize_currency
from salli.domain.dedup.matcher import (
    DATE_WINDOW_DAYS,
    Candidate,
    DedupStatus,
    Imported,
    dedup_key,
    find_duplicates,
)
from salli.domain.parsing.models import ParsedTransaction, ParseResult, RawRow
from salli.domain.rules.history import booked_transactions

if TYPE_CHECKING:
    from salli.adapters.parsing.csv_import import CsvMapping
    from salli.adapters.parsing.dates import DateOrder
    from salli.adapters.parsing.support import Extraction
    from salli.domain.accounting.models import Account

# What a statement can be for: where money is held (a bank or cash account)
# or owed (a card, a loan).
_MONEY_TYPES = ("asset", "liability")

# How far around an import's dates earlier imports are searched for the same
# transactions: a bank's reference can come back with another date (pending,
# then booked).
_HISTORY_DAYS = 7


def _slugify(label: str) -> str:
    """LLM category label → tag slug ("Bank Charge" → "bank-charge")."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", label.strip().lower())
    return cleaned.strip("-")[:60]


class ParsingService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        storage: StoragePort | None = None,
        credentials: Any = None,
        fx: Any = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage
        self._credentials = credentials
        # Rates for statements in a currency other than the owner's base one.
        self._fx = fx

    async def _key_for(self, user_id: str, api_key: Any) -> Any:
        """Use the caller's already-resolved key, else resolve for this user.

        The HTTP routes resolve once at the boundary and pass it down, so the hot
        path does one lookup. The MCP server, the agent's own tools, and the CLI
        have no such boundary, so they omit it and this resolves on their behalf
        — which keeps every surface on the same key rather than leaving some of
        them on the platform's.
        """
        if api_key is not None:
            return api_key
        if self._credentials is None:
            raise RuntimeError("No LLM credential source configured")
        return (await self._credentials.resolve(user_id)).anthropic

    async def _money_account(self, user_id: str, account_id: str) -> Account:
        """The account a statement is for: one of the user's active asset or
        liability accounts (a bank, cash or card account). ValueError otherwise."""
        async with self._uow_factory() as uow:
            account = await uow.ledger.get_account(user_id, account_id)
        if account is None or not account.is_active:
            raise ValueError(f"No active account {account_id!r}")
        if account.type not in _MONEY_TYPES:
            raise ValueError(
                f"{account.name} is an {account.type} account. A statement is for an asset "
                "or liability account: a bank, cash or card account."
            )
        return account

    async def parse_statement(
        self,
        user_id: str,
        filename: str,
        file_bytes: bytes,
        bank: str = "",
        *,
        currency: str | None = None,
        account_id: str | None = None,
        date_order: DateOrder | None = None,
        csv_mapping: CsvMapping | None = None,
        api_key: Any = None,
    ) -> ParseResult:
        """
        Parse a bank statement file and store the extracted transactions.
        Returns a ParseResult — caller should display pending transactions for review.

        `account_id` is the account the statement is for, one of the user's
        active asset or liability accounts; it is the money side of every row.
        `currency` is the statement's, for the rows of a file that does not
        name its own (OFX, camt.053 and MT940 always do; a CSV may); it
        defaults to the account's currency, else the user's base currency. A
        row in another currency than the account's is skipped. `date_order`
        ("DMY", "MDY" or "YMD") settles dates a QIF or CSV file leaves
        ambiguous, and `csv_mapping` states a CSV's layout instead of
        detecting it. Rows the importer could not read are listed in
        `errors`, and so are its guesses.
        """
        account = await self._money_account(user_id, account_id) if account_id else None
        if currency:
            currency = normalize_currency(currency)
            if account is not None and currency != account.currency:
                raise ValueError(
                    f"{account.name} is kept in {account.currency}, not {currency}: "
                    "a statement is in its account's currency"
                )
        elif account is not None:
            currency = account.currency
        else:
            async with self._uow_factory() as uow:
                currency = await uow.user_profiles.base_currency(user_id)

        raw_rows, errors = _extract(
            filename, file_bytes, currency, date_order=date_order, csv_mapping=csv_mapping
        )
        if not raw_rows:
            return ParseResult(
                statement_id="",
                bank=bank,
                period_start="",
                period_end="",
                errors=[
                    *errors,
                    "No transactions found in the file. Check the format is supported",
                ],
            )
        return await self.import_rows(
            user_id,
            raw_rows,
            bank=bank,
            account_id=account_id,
            errors=errors,
            filename=filename,
            file_bytes=file_bytes,
            api_key=api_key,
        )

    async def import_rows(
        self,
        user_id: str,
        rows: list[RawRow],
        *,
        bank: str,
        account_id: str | None,
        errors: list[str] | None = None,
        filename: str | None = None,
        file_bytes: bytes | None = None,
        api_key: Any = None,
    ) -> ParseResult:
        """
        Import transactions already read from somewhere — a statement file, a
        bank feed — as one statement for review: everything after extraction.

        `account_id` is the account they are all on (validated as in
        parse_statement), `errors` what the reading already had to say, and
        `file_bytes` (with its `filename`) the original, kept in storage when
        there is one. Rows from a feed carry the provider's transaction id as
        their bank_ref.
        """
        from salli.adapters.parsing.llm_classifier import classify_transactions

        errors = list(errors or [])
        account = await self._money_account(user_id, account_id) if account_id else None
        kept = rows
        if account is not None:
            kept, skipped = _in_currency_of(account, rows)
            errors += skipped
        if not kept:
            return ParseResult(
                statement_id="",
                bank=bank,
                period_start="",
                period_end="",
                errors=[*errors, "No transactions to import"],
            )

        period_start = min(r.date for r in kept)
        period_end = max(r.date for r in kept)

        async with self._uow_factory() as uow:
            every_account = await uow.ledger.get_accounts(user_id, include_inactive=True)
            history = await uow.statements.imported_between(
                user_id, _shift(period_start, -_HISTORY_DAYS), _shift(period_end, _HISTORY_DAYS)
            )
            entries = await uow.ledger.get_entries(
                user_id,
                from_date=_shift(period_start, -DATE_WINDOW_DAYS),
                to_date=_shift(period_end, DATE_WINDOW_DAYS),
            )
        accounts = [a for a in every_account if a.is_active]
        if not accounts:
            return ParseResult(
                statement_id="",
                bank=bank,
                period_start=period_start,
                period_end=period_end,
                raw_rows=rows,
                errors=[*errors, "No accounts found. Create a chart of accounts first"],
            )

        # Against earlier imports and the ledger, never against itself: two
        # identical rows in one statement are two transactions.
        candidates = [_candidate(r) for r in kept]
        verdicts = find_duplicates(
            candidates,
            account_id=account.id if account is not None else "",
            imported=[Imported(t.id, _candidate(t.raw), t.account_id) for t in history],
            booked=booked_transactions(entries, every_account),
            money_accounts={a.id for a in every_account if a.type in _MONEY_TYPES},
        )

        # An exact duplicate is booked already: it stays for review, but needs
        # no accounts and costs no model call.
        undecided = [
            r
            for r, v in zip(kept, verdicts, strict=True)
            if v.status is not DedupStatus.EXACT_DUPLICATE
        ]
        classified = iter(
            await classify_transactions(
                undecided, accounts, api_key=await self._key_for(user_id, api_key)
            )
            if undecided
            else []
        )
        parsed: list[ParsedTransaction] = []
        for row, candidate, verdict in zip(kept, candidates, verdicts, strict=True):
            if verdict.status is DedupStatus.EXACT_DUPLICATE:
                txn = ParsedTransaction(
                    raw=row, debit_account_id="", credit_account_id="", confidence=0.0
                )
            else:
                txn = next(classified)
            txn.dedup_key = dedup_key(candidate)
            txn.dedup_status = (
                "pending" if verdict.status is DedupStatus.UNIQUE else verdict.status.value
            )
            txn.duplicate_of = verdict.duplicate_of
            if account is not None:
                _book_money_side(txn, account.id)
            parsed.append(txn)

        statement_id = str(uuid.uuid4())
        storage_key = ""
        # The original is kept when there is one: a feed has no file. Storing
        # it is best-effort, so an import never fails over it.
        if self._storage is not None and file_bytes is not None:
            try:
                storage_key = await self._storage.upload(
                    user_id, f"{statement_id}/{filename or 'statement'}", file_bytes
                )
            except Exception:
                pass

        async with self._uow_factory() as uow:
            await uow.statements.save_statement(
                user_id=user_id,
                statement_id=statement_id,
                bank=bank,
                period_start=period_start,
                period_end=period_end,
                transactions=parsed,
                storage_key=storage_key,
                account_id=account.id if account is not None else None,
            )

        return ParseResult(
            statement_id=statement_id,
            bank=bank,
            period_start=period_start,
            period_end=period_end,
            transactions=parsed,
            raw_rows=rows,
            errors=errors,
        )

    async def list_statements(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Every statement this user has uploaded, newest first."""
        async with self._uow_factory() as uow:
            return await uow.statements.list_statements(user_id, limit)

    async def get_pending(self, user_id: str) -> list[ParsedTransaction]:
        """Return all unposted transactions across all statements for this user."""
        async with self._uow_factory() as uow:
            return await uow.statements.get_all_pending(user_id)

    async def post_approved(
        self,
        user_id: str,
        approved_ids: list[str],
    ) -> list[str]:
        """
        Post approved transactions as journal entries.
        Returns list of created journal entry IDs.
        """
        from salli.domain.accounting.models import Direction, JournalEntry, Posting

        async with self._uow_factory() as uow:
            base = await uow.user_profiles.base_currency(user_id)
            txns = await uow.statements.get_by_ids(user_id, list(approved_ids))
            kinds = {
                a.id: a.type for a in await uow.ledger.get_accounts(user_id, include_inactive=True)
            }
            entry_ids = []

            for txn in txns:
                # A duplicate is booked already, and so is a row posted before.
                if txn.dedup_status in (DedupStatus.EXACT_DUPLICATE.value, "posted"):
                    continue
                if not txn.debit_account_id or not txn.credit_account_id:
                    continue

                # What the row was for — the classifier's label or a rule's
                # category, and a rule's need — tags the other side of the
                # entry, the expense or income, never the bank account.
                tags = {"category": _slugify(txn.category)} if txn.category else {}
                if txn.need:
                    tags["need"] = txn.need
                debit_tags, credit_tags = (
                    (tags, {}) if _counter_is_debit(txn, kinds) else ({}, tags)
                )

                # A statement in another currency is converted at the rate for
                # the transaction's own date (see application/fx.py).
                fx_rate, fx_source = await rate_to_base(
                    self._fx, txn.raw.currency, base, txn.raw.date
                )
                postings = [
                    Posting(
                        account_id=txn.debit_account_id,
                        direction=Direction.DEBIT,
                        amount=txn.raw.amount,
                        currency=txn.raw.currency,
                        fx_rate=fx_rate,
                        fx_rate_source=fx_source,
                        tags=debit_tags,
                    ),
                    Posting(
                        account_id=txn.credit_account_id,
                        direction=Direction.CREDIT,
                        amount=txn.raw.amount,
                        currency=txn.raw.currency,
                        fx_rate=fx_rate,
                        fx_rate_source=fx_source,
                        tags=credit_tags,
                    ),
                ]
                entry = JournalEntry(
                    entry_date=txn.raw.date,
                    description=txn.description or txn.raw.description,
                    source="statement",
                    external_ref=txn.id,
                    postings=postings,
                )
                entry_id = await uow.ledger.save_entry(user_id, entry)
                await uow.statements.mark_posted(txn.id, entry_id)
                entry_ids.append(entry_id)

        return entry_ids


def _candidate(row: RawRow) -> Candidate:
    return Candidate(
        date=row.date,
        amount=row.amount,
        currency=row.currency,
        money_in=row.credit_flag,
        description=row.description,
        bank_ref=row.bank_ref,
    )


def _shift(day: str, days: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()


def _counter_is_debit(txn: ParsedTransaction, kinds: dict[str, str]) -> bool:
    """Whether the debit, rather than the credit, is the other side of `txn`:
    the expense money went to, the income it came from. With the statement's
    account known, that is whichever side is not it; without, the side that
    is an income or expense account, and the debit when that does not settle it."""
    if txn.account_id:
        return txn.debit_account_id != txn.account_id
    flows = [
        kinds.get(a) in ("income", "expense") for a in (txn.debit_account_id, txn.credit_account_id)
    ]
    return flows != [False, True]


def _in_currency_of(account: Account, rows: list[RawRow]) -> tuple[list[RawRow], list[str]]:
    """The rows in the account's own currency, and a word about the rest.

    An account is held in one currency, so a row in another (a file that
    names its own) cannot be on it as written; it is skipped rather than
    booked at a number that is wrong by the exchange rate.
    """
    other = Counter(row.currency for row in rows if row.currency != account.currency)
    return [row for row in rows if row.currency == account.currency], [
        f"Skipped {count} transaction(s) in {code}: {account.name} is kept in {account.currency}"
        for code, count in other.items()
    ]


def _book_money_side(txn: ParsedTransaction, account_id: str) -> None:
    """Put the statement's account on the money side of `txn`: debited for
    money in, credited for money out. Of the accounts already chosen, the one
    that is not the statement's account becomes the other side, preferring
    the side it would normally be on."""
    first, second = (
        (txn.credit_account_id, txn.debit_account_id)
        if txn.raw.credit_flag
        else (txn.debit_account_id, txn.credit_account_id)
    )
    counter = next((a for a in (first, second) if a and a != account_id), "")
    if txn.raw.credit_flag:
        txn.debit_account_id, txn.credit_account_id = account_id, counter
    else:
        txn.debit_account_id, txn.credit_account_id = counter, account_id
    txn.account_id = account_id


# ── Format detection ───────────────────────────────────────────────────────────

_FORMAT_BY_EXTENSION = {
    "pdf": "pdf",
    "xlsx": "xlsx",
    "xls": "xlsx",
    "ofx": "ofx",
    "qfx": "ofx",
    "qif": "qif",
    "xml": "camt053",
    "sta": "mt940",
    "940": "mt940",
    "mt940": "mt940",
    "csv": "csv",
    "tsv": "csv",
    "txt": "csv",
}


def _statement_format(filename: str, data: bytes) -> str | None:
    """Which importer reads this file.

    What a file holds says what it is more reliably than its name: banks
    save MT940 as .txt and OFX as .xml, and a download can lose its
    extension. So distinctive content decides first, and the extension only
    when there is none — as there never is in a CSV.
    """
    from salli.adapters.parsing.support import decode_text

    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK"):  # a ZIP archive, which is what an .xlsx is
        return "xlsx"
    head = decode_text(data[:8192])
    if re.search(r"OFXHEADER\s*:|<OFX[\s>]", head, re.I):
        return "ofx"
    if re.search(r"^\s*!Type\s*:", head, re.I | re.M):
        return "qif"
    if "<Document" in head and ("camt.053" in head or "BkToCstmrStmt" in head):
        return "camt053"
    if re.search(r"(?:^|\{4:)\s*:20:", head, re.M) and re.search(r"^:61:", head, re.M):
        return "mt940"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _FORMAT_BY_EXTENSION:
        return _FORMAT_BY_EXTENSION[ext]
    # Nothing distinctive and no telling extension: text can still be a CSV.
    return "csv" if b"\x00" not in data[:8192] else None


def _extract(
    filename: str,
    data: bytes,
    currency: str,
    *,
    date_order: DateOrder | None = None,
    csv_mapping: CsvMapping | None = None,
) -> tuple[list[RawRow], list[str]]:
    """The file's transactions as RawRows, and what could not be read.

    Numbers come from deterministic importers only, never the LLM.
    """
    from salli.adapters.parsing.support import Extraction, StatementLine

    kind = _statement_format(filename, data)
    if kind in ("pdf", "xlsx"):
        if kind == "pdf":
            from salli.adapters.parsing.pdf_extractor import extract_from_pdf

            raw = extract_from_pdf(data)
        else:
            from salli.adapters.parsing.excel_extractor import extract_from_excel

            raw = extract_from_excel(data)
        extraction = Extraction(
            lines=[
                StatementLine(
                    date=r["date"],
                    description=r["description"],
                    amount=r["amount"],
                    credit_flag=r["credit_flag"],
                    bank_ref=r.get("bank_ref", ""),
                    source_page=r.get("page", 0),
                )
                for r in raw
            ]
        )
    elif kind == "ofx":
        from salli.adapters.parsing.ofx import extract_from_ofx

        extraction = extract_from_ofx(data)
    elif kind == "qif":
        from salli.adapters.parsing.qif import extract_from_qif

        extraction = extract_from_qif(data, date_order=date_order)
    elif kind == "camt053":
        from salli.adapters.parsing.camt053 import extract_from_camt053

        extraction = extract_from_camt053(data)
    elif kind == "mt940":
        from salli.adapters.parsing.mt940 import extract_from_mt940

        extraction = extract_from_mt940(data)
    elif kind == "csv":
        from salli.adapters.parsing.csv_import import extract_from_csv

        extraction = extract_from_csv(data, csv_mapping, date_order=date_order)
    else:
        return [], [
            "Salli can't read this file. It reads PDF, Excel (.xlsx), CSV, OFX/QFX, QIF, "
            "camt.053 and MT940 statements"
        ]
    return _raw_rows(extraction, currency)


def _raw_rows(extraction: Extraction, currency: str) -> tuple[list[RawRow], list[str]]:
    """An importer's lines as RawRows, each in a currency Salli knows.

    A line in a currency the file names is in that one; any other line is in
    the statement's `currency`. A code that is not ISO 4217 skips its rows,
    and says so, rather than booking them as something they are not.
    """
    errors = list(extraction.errors)
    # The dedup matcher takes two rows with the same bank reference for one
    # transaction. A reference repeated within a file is not one — a bank
    # reusing an id, a cheque number on a payment and on its fee — and would
    # silently drop real transactions, so it is left off those rows.
    references = Counter(line.bank_ref for line in extraction.lines if line.bank_ref)
    unknown: Counter[str] = Counter()
    rows: list[RawRow] = []
    for line in extraction.lines:
        try:
            code = normalize_currency(line.currency) if line.currency else currency
        except UnknownCurrencyError:
            unknown[line.currency or ""] += 1
            continue
        rows.append(
            RawRow(
                date=line.date,
                description=line.description,
                amount=line.amount,
                credit_flag=line.credit_flag,
                currency=code,
                bank_ref=line.bank_ref if references[line.bank_ref] == 1 else "",
                source_page=line.source_page,
            )
        )
    for code, count in unknown.items():
        errors.append(
            f"Skipped {count} transaction(s) in {code!r}, which is not an ISO 4217 currency code"
        )
    return rows, errors
