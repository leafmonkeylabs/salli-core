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
from salli.domain.rules.engine import Facts, Rule
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
        rules: Any = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage
        self._credentials = credentials
        # Rates for statements in a currency other than the owner's base one.
        self._fx = fx
        # The user's categorisation rules (RulesService), tried before the model.
        self._rules = rules

    async def _key_for(self, user_id: str, api_key: Any) -> Any:
        """Use the caller's already-resolved key, else resolve for this user;
        None when there is no key to use (no credential source, or neither a
        key of the user's own nor a platform key).

        The HTTP routes resolve once at the boundary and pass it down, so the hot
        path does one lookup. The MCP server, the agent's own tools, and the CLI
        have no such boundary, so they omit it and this resolves on their behalf
        — which keeps every surface on the same key rather than leaving some of
        them on the platform's.
        """
        if api_key is not None:
            return api_key or None
        if self._credentials is None:
            return None
        return (await self._credentials.resolve(user_id)).anthropic or None

    async def _decide(self, user_id: str, rows: list[RawRow]) -> list[Rule | None]:
        """The rule that decides each row, or None; each hit is counted."""
        if self._rules is None or not rows:
            return [None] * len(rows)
        return await self._rules.decide(
            user_id,
            [
                Facts(
                    description=r.description,
                    amount=r.amount,
                    direction="in" if r.credit_flag else "out",
                    currency=r.currency,
                )
                for r in rows
            ],
        )

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

        # The statement's account is the money side of every row; an exact
        # duplicate gets nothing more. It is booked already: it stays for
        # review, but needs no other account, no rule and no model call.
        money_id = account.id if account is not None else ""
        parsed = [
            ParsedTransaction(
                raw=row, debit_account_id="", credit_account_id="", account_id=money_id
            )
            for row in kept
        ]
        if money_id:
            for txn in parsed:
                _place(txn, money_id, money=True)
        live = [i for i, v in enumerate(verdicts) if v.status is not DedupStatus.EXACT_DUPLICATE]
        valid = {a.id for a in accounts}

        # The user's rules first: what one decides is booked the same way every
        # time, and costs no model call.
        for i, rule in zip(live, await self._decide(user_id, [kept[i] for i in live]), strict=True):
            if rule is not None:
                _apply(rule, parsed[i], valid)

        # The model, for the rows still missing an account, when there is a
        # key to ask it with. Without one the import still goes ahead.
        undecided = [i for i in live if not _booked(parsed[i])]
        key = await self._key_for(user_id, api_key) if undecided else None
        if key is not None:
            guesses = await classify_transactions(
                [kept[i] for i in undecided], accounts, api_key=key, money_account=account
            )
            for i, guess in zip(undecided, guesses, strict=True):
                _take(guess, parsed[i], valid)
        missing = sum(1 for i in live if not _booked(parsed[i]))
        if missing and key is None:
            errors.append(
                f"{missing} transaction(s) need an account: with no AI key set up, only your "
                "rules sorted this statement"
            )
        elif missing:
            errors.append(f"{missing} transaction(s) still need an account; choose one to post")

        modelled: set[int] = set(undecided) if key is not None else set()
        for i, (txn, candidate, verdict) in enumerate(
            zip(parsed, candidates, verdicts, strict=True)
        ):
            txn.dedup_key = dedup_key(candidate)
            txn.dedup_status = (
                "pending" if verdict.status is DedupStatus.UNIQUE else verdict.status.value
            )
            txn.duplicate_of = verdict.duplicate_of
            # Sure when the statement and a rule decided it, the model's
            # confidence when the model did, and nothing while a side is open.
            if verdict.status is DedupStatus.EXACT_DUPLICATE or not _booked(txn):
                txn.confidence = 0.0
            elif i not in modelled:
                txn.confidence = 1.0

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

    async def get_statement(self, user_id: str, statement_id: str) -> dict[str, Any] | None:
        """One of this user's statements, or None if it is not theirs."""
        async with self._uow_factory() as uow:
            return await uow.statements.get_statement(user_id, statement_id)

    async def get_pending(
        self, user_id: str, statement_id: str | None = None
    ) -> list[ParsedTransaction]:
        """Transactions waiting for review — neither posted nor discarded —
        across every statement of this user's, or in one."""
        async with self._uow_factory() as uow:
            if statement_id is None:
                return await uow.statements.get_all_pending(user_id)
            return await uow.statements.get_pending(user_id, statement_id)

    async def discard(
        self, user_id: str, statement_id: str, ids: list[str] | None = None
    ) -> int | None:
        """Discard a statement's pending transactions (those of `ids`, or every
        one): they are never posted and leave review. How many, or None when
        the statement is not this user's."""
        async with self._uow_factory() as uow:
            if await uow.statements.get_statement(user_id, statement_id) is None:
                return None
            return await uow.statements.discard(user_id, statement_id, ids)

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
                # A duplicate is booked already, and so is a row posted before;
                # a discarded one never happened.
                if txn.dedup_status in (DedupStatus.EXACT_DUPLICATE.value, "posted", "discarded"):
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


def _place(txn: ParsedTransaction, account_id: str, *, money: bool) -> None:
    """Put `account_id` on `txn`'s money side — debited for money in, credited
    for money out — or, with money=False, on its other side."""
    if txn.raw.credit_flag == money:
        txn.debit_account_id = account_id
    else:
        txn.credit_account_id = account_id


def _booked(txn: ParsedTransaction) -> bool:
    return bool(txn.debit_account_id and txn.credit_account_id)


def _apply(rule: Rule, txn: ParsedTransaction, valid: set[str]) -> None:
    """What a rule decides about a row: its other side's account (while that
    is still in the chart and is not the row's own account), its tags, and
    the description to book it with."""
    txn.rule_id = rule.id
    txn.category = rule.actions.category or ""
    txn.need = rule.actions.need or ""
    txn.description = rule.actions.description or ""
    target = rule.actions.account_id
    if target in valid and target != txn.account_id:
        _place(txn, target, money=False)


def _take(guess: ParsedTransaction, txn: ParsedTransaction, valid: set[str]) -> None:
    """The model's answer, for the sides still open. An id that is not in the
    chart is dropped — the model only ever proposes — and so is one already on
    the other side. A rule's category stands over the model's label."""
    debit = guess.debit_account_id if guess.debit_account_id in valid else ""
    credit = guess.credit_account_id if guess.credit_account_id in valid else ""
    if not txn.debit_account_id and debit != txn.credit_account_id:
        txn.debit_account_id = debit
    if not txn.credit_account_id and credit != txn.debit_account_id:
        txn.credit_account_id = credit
    txn.category = txn.category or guess.category
    txn.confidence = guess.confidence


# ── Format detection ───────────────────────────────────────────────────────────

_FORMAT_BY_EXTENSION = {
    "pdf": "pdf",
    "xlsx": "xlsx",
    "xls": "xls",
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
    if data.startswith(b"\xd0\xcf\x11\xe0"):  # an OLE2 file: an old .xls, or a locked .xlsx
        return "xls"
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
    kind = _statement_format(filename, data)
    if kind == "pdf":
        from salli.adapters.parsing.pdf_extractor import extract_from_pdf

        extraction = extract_from_pdf(data, date_order=date_order)
    elif kind == "xlsx":
        from salli.adapters.parsing.excel_extractor import extract_from_excel

        extraction = extract_from_excel(data, date_order=date_order)
    elif kind == "xls":
        return [], [
            "This is an old-style (.xls) or password-protected Excel workbook, which Salli "
            "can't read. Save it as an unprotected .xlsx, or as CSV, and import that"
        ]
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
