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

import asyncio
import re
import uuid
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Literal

from salli.application.fx import rate_to_base
from salli.application.ports import StoragePort
from salli.domain.accounting.models import MONEY_TYPES, money_account_problem
from salli.domain.currency import UnknownCurrencyError, normalize_currency, quantize
from salli.domain.dedup.matcher import (
    DATE_WINDOW_DAYS,
    REFERENCE_WINDOW_DAYS,
    Candidate,
    DedupStatus,
    Imported,
    dedup_key,
    find_duplicates,
)
from salli.domain.llm import LLMError
from salli.domain.parsing.models import DedupState, ParsedTransaction, ParseResult, RawRow
from salli.domain.rules.engine import Facts, Rule
from salli.domain.rules.history import booked_transactions
from salli.domain.secrets import redact
from salli.domain.usage import AIAction, UsageLimitReached

if TYPE_CHECKING:
    from salli.adapters.parsing.csv_import import CsvMapping
    from salli.adapters.parsing.dates import DateOrder
    from salli.adapters.parsing.support import Extraction
    from salli.domain.accounting.models import Account

# What a statement can be for: where money is held (a bank or cash account)
# or owed (a card, a loan).
_MONEY_TYPES = MONEY_TYPES


def _slugify(label: str) -> str:
    """LLM category label → tag slug ("Bank Charge" → "bank-charge")."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", label.strip().lower())
    return cleaned.strip("-")[:60]


#: The need tags a transaction can carry (as rules set them).
_NEEDS = ("essential", "discretionary", "savings")


class ParsingService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        storage: StoragePort | None = None,
        credentials: Any = None,
        fx: Any = None,
        rules: Any = None,
        usage: Any = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage
        self._credentials = credentials
        # Rates for statements in a currency other than the owner's base one.
        self._fx = fx
        # The user's categorisation rules (RulesService), tried before the model.
        self._rules = rules
        # The deployment's usage meter (application/ports.UsageMeter), charged
        # only when the model is about to run: an import the user's rules
        # decide, or one with no key, spends nothing and costs nothing.
        self._usage = usage

    async def _llm_for(self, user_id: str, api_key: Any) -> Any:
        """Use the caller's already-resolved credential, else resolve for this
        user; None when there is nothing to run on (no credential source, or
        neither a key or plan of the user's own nor a platform key).

        `api_key` is an LLMClient, or an Anthropic key as it always was. The
        HTTP routes resolve once at the boundary and pass it down, so the hot
        path does one lookup. The MCP server, the agent's own tools, and
        salli-server's jobs have no such boundary, so they omit it and this resolves on their behalf
        — which keeps every surface on the same credential rather than leaving
        some of them on the platform's.
        """
        from salli.application.services.llm_credential_service import as_llm

        if api_key is not None:
            return as_llm(api_key)
        if self._credentials is None:
            return None
        return (await self._credentials.resolve(user_id)).llm

    async def _decide(self, user_id: str, rows: list[RawRow]) -> list[Rule | None]:
        """The rule that decides each row, or None. Hits are counted once the
        import is saved (`_count_hits`), so a refused import counts none."""
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
            record=False,
        )

    async def _count_hits(self, user_id: str, decided: list[Rule | None]) -> None:
        if self._rules is not None and any(decided):
            await self._rules.record_hits(user_id, decided)

    async def _money_account(self, user_id: str, account_id: str) -> Account:
        """The account a statement is for: one of the user's active asset or
        liability accounts (a bank, cash or card account). ValueError otherwise."""
        async with self._uow_factory() as uow:
            account = await uow.ledger.get_account(user_id, account_id)
        problem = money_account_problem(account, account_id)
        if problem is not None or account is None:
            raise ValueError(problem)
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
        source_account: str | None = None,
        replaces: str | None = None,
        date_order: DateOrder | None = None,
        csv_mapping: CsvMapping | None = None,
        api_key: Any = None,
        email: str | None = None,
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

        A file holding several accounts (a QIF with a card register, an OFX
        with two statements) is imported one account at a time:
        `source_account` names the file's account to import, when the
        statement's account does not match one by name or code.

        `replaces` is the id of an earlier import of the same statement, being
        imported again on purpose: its rows are not taken for duplicates, and
        those still waiting for review are discarded once this one is saved.
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
        if replaces is not None:
            async with self._uow_factory() as uow:
                if await uow.statements.get_statement(user_id, replaces) is None:
                    raise ValueError(f"No statement {replaces!r} to replace")

        # Reading a file is CPU work, kept off the event loop: a heavy PDF or
        # workbook must not stall every other request this worker serves.
        raw_rows, errors = await asyncio.to_thread(
            _extract, filename, file_bytes, currency, date_order=date_order, csv_mapping=csv_mapping
        )
        raw_rows, refusal = _on_account(raw_rows, account, source_account, errors)
        if refusal is not None or not raw_rows:
            return ParseResult(
                statement_id="",
                bank=bank,
                period_start="",
                period_end="",
                errors=[
                    *errors,
                    refusal or "No transactions found in the file. Check the format is supported",
                ],
            )
        return await self._import(
            user_id,
            raw_rows,
            account=account,
            bank=bank,
            errors=errors,
            filename=filename,
            file_bytes=file_bytes,
            api_key=api_key,
            email=email,
            replaces=replaces,
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
        email: str | None = None,
        keep_duplicates: bool = True,
        on_usage_limit: Literal["raise", "skip"] = "raise",
    ) -> ParseResult:
        """
        Import transactions already read from somewhere — a statement file, a
        bank feed — as one statement for review: everything after extraction.

        A statement keeps its exact duplicates, so its result can say what was
        imported before; a feed (`keep_duplicates=False`), which overlaps its
        last sync on purpose, leaves them out and only counts them. When the
        usage meter refuses the model, a request (`on_usage_limit="raise"`)
        is refused, as it always was; a scheduled sync ("skip") goes ahead
        with the user's rules alone and says so.

        `account_id` is the account they are all on (validated as in
        parse_statement), `errors` what the reading already had to say, and
        `file_bytes` (with its `filename`) the original, kept in storage when
        there is one. Rows from a feed carry the provider's transaction id as
        their bank_ref, with `ref_kind="id"` and their feed as `ref_source`.
        """
        account = await self._money_account(user_id, account_id) if account_id else None
        return await self._import(
            user_id,
            rows,
            account=account,
            bank=bank,
            errors=errors,
            filename=filename,
            file_bytes=file_bytes,
            api_key=api_key,
            email=email,
            keep_duplicates=keep_duplicates,
            on_usage_limit=on_usage_limit,
        )

    async def _import(
        self,
        user_id: str,
        rows: list[RawRow],
        *,
        account: Account | None,
        bank: str,
        errors: list[str] | None,
        filename: str | None,
        file_bytes: bytes | None,
        api_key: Any,
        email: str | None,
        keep_duplicates: bool = True,
        on_usage_limit: Literal["raise", "skip"] = "raise",
        replaces: str | None = None,
    ) -> ParseResult:
        """`import_rows` with the statement's account already resolved."""
        from salli.adapters.parsing import llm_classifier

        errors = list(errors or [])
        kept, undated = _real_dates(rows)
        if undated:
            # A feed (or any caller) can hand over a placeholder such as
            # 9999-12-31: no transaction's date, and past what date
            # arithmetic can reach.
            errors.append(f"Skipped {undated} transaction(s) without a real date")
        if account is not None:
            kept, skipped = _in_currency_of(account, kept)
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
        money_id = account.id if account is not None else ""

        async with self._uow_factory() as uow:
            every_account = await uow.ledger.get_accounts(user_id, include_inactive=True)
            history = await uow.statements.imported_between(
                user_id,
                _shift(period_start, -REFERENCE_WINDOW_DAYS),
                _shift(period_end, REFERENCE_WINDOW_DAYS),
                account_id=money_id or None,
                excluding_statement=replaces,
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
        # identical rows in one statement are two transactions. Each verdict
        # is stamped on its row at once.
        candidates = [_candidate(r) for r in kept]
        verdicts = find_duplicates(
            candidates,
            account_id=money_id,
            imported=[
                Imported(
                    t.id, _candidate(t.raw), t.account_id, discarded=t.dedup_status == "discarded"
                )
                for t in history
            ],
            booked=booked_transactions(entries, every_account),
            money_accounts={a.id for a in every_account if a.type in _MONEY_TYPES},
        )
        parsed: list[ParsedTransaction] = []
        for row, candidate, verdict in zip(kept, candidates, verdicts, strict=True):
            txn = ParsedTransaction(
                raw=row,
                debit_account_id="",
                credit_account_id="",
                account_id=money_id,
                dedup_key=dedup_key(candidate),
                dedup_status=_status(verdict.status),
                duplicate_of=verdict.duplicate_of,
            )
            # The statement's account is the money side of every row.
            if money_id:
                _place(txn, money_id, money=True)
            parsed.append(txn)

        dropped = 0
        if not keep_duplicates:
            fresh = [t for t in parsed if t.dedup_status != "exact_duplicate"]
            dropped, parsed = len(parsed) - len(fresh), fresh
            if not parsed:
                return ParseResult(
                    statement_id="",
                    bank=bank,
                    period_start=period_start,
                    period_end=period_end,
                    raw_rows=rows,
                    errors=errors,
                    duplicates_dropped=dropped,
                )

        # An exact duplicate is booked already: it stays for review, but needs
        # no other account, no rule and no model call.
        live = [t for t in parsed if t.dedup_status != "exact_duplicate"]
        valid = {a.id for a in accounts}

        # The user's rules first: what one decides is booked the same way every
        # time, and costs no model call.
        decided = await self._decide(user_id, [t.raw for t in live])
        for txn, rule in zip(live, decided, strict=True):
            if rule is not None:
                _apply(rule, txn, valid)

        # The model, for the rows still missing an account, when there is a
        # key to ask it with. Without one the import still goes ahead.
        undecided = [t for t in live if not _booked(t)]
        # A model that cannot run at all (the user's ChatGPT plan paused at its
        # usage limit, a sign-in to renew) is treated like a refusing meter: a
        # request is refused with its message, a sync goes on with the user's
        # rules alone and says why.
        why_not = ""
        try:
            llm = await self._llm_for(user_id, api_key) if undecided else None
        except LLMError as unavailable:
            if on_usage_limit == "raise":
                raise
            llm, why_not = None, "with the model not asked"
            errors.append(f"The model was not asked: {unavailable.message}")
        if llm is None and undecided and not why_not:
            why_not = "with no AI key set up"
        if llm is not None and self._usage is not None:
            try:
                await self._usage.charge(user_id, AIAction.STATEMENT_IMPORT, email=email)
            except UsageLimitReached as limit:
                if on_usage_limit == "raise":
                    raise
                llm, why_not = None, "with the model not asked (usage limit)"
                errors.append(f"The model was not asked: {limit}")
        modelled: set[int] = set()
        if llm is not None:
            try:
                guesses = await llm_classifier.classify_transactions(
                    [t.raw for t in undecided], accounts, llm=llm, money_account=account
                )
            except LLMError as failed:
                # Once charged, a model that fails is like any other failure
                # below: the rows stay undecided. A typed error (the plan's
                # limit reached mid-import, a sign-in that lapsed) carries our
                # own sentence, with where to go about it.
                why_not = "with the model unavailable"
                errors.append(f"The model could not sort this import: {failed.message}")
            except Exception as failure:  # the provider's error, a timeout, a bad answer
                # The rows stay undecided: an import, or a bank feed's sync,
                # must not fail because the model did.
                why_not = "with the model unreachable"
                errors.append(
                    f"The model could not be reached: {redact(type(failure).__name__)}"
                    f" ({redact(str(failure))[:200]})"
                )
            else:
                for txn, guess in zip(undecided, guesses, strict=True):
                    _take(guess, txn, valid)
                    modelled.add(id(txn))
        missing = sum(1 for t in live if not _booked(t))
        if missing and why_not:
            errors.append(
                f"{missing} transaction(s) need an account: {why_not}, only your rules "
                "sorted this statement"
            )
        elif missing:
            errors.append(f"{missing} transaction(s) still need an account; choose one to post")

        for txn in parsed:
            # Sure when the statement and a rule decided it, the model's
            # confidence when the model did, and nothing while a side is open.
            if txn.dedup_status == "exact_duplicate" or not _booked(txn):
                txn.confidence = 0.0
            elif id(txn) not in modelled:
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
            if replaces is not None:
                await uow.statements.discard(user_id, replaces)
        await self._count_hits(user_id, decided)

        return ParseResult(
            statement_id=statement_id,
            bank=bank,
            period_start=period_start,
            period_end=period_end,
            transactions=parsed,
            raw_rows=rows,
            errors=errors,
            duplicates_dropped=dropped,
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

    async def categorize(self, user_id: str, choices: Sequence[Mapping[str, Any]]) -> list[str]:
        """Choose the other side of pending transactions: what the user, or an
        AI client working for them over MCP, decided before posting.

        Each choice names a `transaction_id` and an `account_id`, and may set
        a `category` and a `need`. The statement's own account stays the money
        side. A choice replaces whatever a rule or the model chose, so the row
        no longer says a rule decided it. Refused (ValueError) for a row that
        is not waiting for review, an account that is not one of the user's
        active ones, or the statement's own account; KeyError for a row that
        is not theirs. Returns the ids changed, in order.
        """
        if not choices:
            return []
        async with self._uow_factory() as uow:
            accounts = {a.id: a for a in await uow.ledger.get_accounts(user_id)}
            ids = [str(c["transaction_id"]) for c in choices]
            rows = {t.id: t for t in await uow.statements.get_by_ids(user_id, ids)}
            for choice in choices:
                txn = rows.get(str(choice["transaction_id"]))
                if txn is None:
                    raise KeyError(choice["transaction_id"])
                if txn.dedup_status in ("posted", "discarded", "exact_duplicate"):
                    raise ValueError(
                        f"Transaction {txn.id} is {txn.dedup_status.replace('_', ' ')}: "
                        "only transactions waiting for review can change"
                    )
                account = accounts.get(str(choice["account_id"]))
                if account is None:
                    raise ValueError(f"No active account {choice['account_id']!r}")
                if account.id == txn.account_id:
                    raise ValueError(
                        f"{account.name} is the statement's own account: choose where the "
                        "money came from or went"
                    )
                need = choice.get("need") or ""
                if need and need not in _NEEDS:
                    raise ValueError(f"need must be one of {', '.join(_NEEDS)}")
                # Money in is credited to where it came from; money out is
                # debited to where it went. The statement's account is the other.
                money_in = txn.raw.credit_flag
                money_side = txn.account_id or (
                    txn.debit_account_id if money_in else txn.credit_account_id
                )
                if not money_side:
                    raise ValueError(
                        f"Transaction {txn.id} came from a statement with no account, so "
                        "nothing says which of your accounts it moved: import it again "
                        "with its account"
                    )
                fields: dict[str, Any] = {
                    "debit_account_id": money_side if money_in else account.id,
                    "credit_account_id": account.id if money_in else money_side,
                    "rule_id": "",
                }
                if choice.get("category") is not None:
                    fields["category"] = str(choice["category"])
                if need:
                    fields["need"] = need
                await uow.statements.set_choice(user_id, txn.id, fields)
        return ids

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
            # Locked until this unit of work ends: a second approval of the
            # same rows waits, then finds them posted.
            txns = await uow.statements.get_by_ids(user_id, list(approved_ids), for_update=True)
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


def transaction_view(t: ParsedTransaction) -> dict[str, Any]:
    """A parsed transaction as every surface shows it (the API's
    StatementTransaction, and the MCP tools): `description` is the
    bank's text, `description_override` what it will be booked as."""
    raw = t.raw
    return {
        "id": t.id,
        "date": raw.date,
        "description": raw.description,
        # As the extractor read it, which can carry more or fewer decimals
        # than the currency has; posting stores it at the currency's.
        "amount": str(quantize(raw.amount, raw.currency, strict=False)),
        "credit_flag": raw.credit_flag,
        "bank_ref": raw.bank_ref,
        "currency": raw.currency,
        "account_id": t.account_id or None,
        "debit_account_id": t.debit_account_id,
        "credit_account_id": t.credit_account_id,
        "category": t.category,
        "need": t.need or None,
        "rule_id": t.rule_id or None,
        "description_override": t.description or None,
        "confidence": t.confidence,
        "dedup_status": t.dedup_status,
        "duplicate_of": t.duplicate_of or None,
    }


def upload_view(result: ParseResult) -> dict[str, Any]:
    """An import's result as every surface shows it (the API's StatementUpload)."""
    return {
        "statement_id": result.statement_id,
        "bank": result.bank,
        "period_start": result.period_start,
        "period_end": result.period_end,
        "total_rows": len(result.raw_rows),
        "parsed": len(result.transactions),
        "errors": result.errors,
        "transactions": [transaction_view(t) for t in result.transactions],
    }


def _candidate(row: RawRow) -> Candidate:
    return Candidate(
        date=row.date,
        amount=row.amount,
        currency=row.currency,
        money_in=row.credit_flag,
        description=row.description,
        bank_ref=row.bank_ref,
        ref_kind="text" if row.ref_kind == "text" else "id",
        source=row.ref_source,
    )


def _status(status: DedupStatus) -> DedupState:
    """How a verdict is kept on its row: a unique one waits for review."""
    if status is DedupStatus.EXACT_DUPLICATE:
        return "exact_duplicate"
    if status is DedupStatus.FUZZY_MATCH:
        return "fuzzy_match"
    return "pending"


def _on_account(
    rows: list[RawRow], account: Account | None, source_account: str | None, errors: list[str]
) -> tuple[list[RawRow], str | None]:
    """The rows of a file to import on `account`, or why none can be.

    A file holding one account's rows (most do) is imported as it is. One
    holding several (a QIF's checking and card registers, two OFX
    statements) is never flattened onto one account, where a card payment
    would net to nothing: `source_account` names the file's account to take,
    else the one whose name or number matches the statement's account; with
    no statement account named the rows go in together, and the accounts
    found are said."""
    found = list(dict.fromkeys(r.source_account for r in rows if r.source_account))
    if len(found) < 2:
        return rows, None
    listed = ", ".join(repr(a) for a in found)
    wanted = source_account
    if wanted is None and account is not None:
        names = {account.name.casefold(), account.code.casefold()}
        matching = [a for a in found if a.casefold() in names]
        wanted = matching[0] if len(matching) == 1 else None
    if wanted is None and account is None:
        errors.append(
            f"This file holds {len(found)} accounts ({listed}); they were imported together. "
            "Import it once per account, naming the statement's account and the file's "
            "(source account), to keep them apart"
        )
        return rows, None
    if wanted is None or wanted not in found:
        return [], (
            f"This file holds {len(found)} accounts ({listed}), and "
            + (f"none is {wanted!r}" if wanted else "Salli can't tell which one this is")
            + ". Import it again naming the file's account to take (source account)"
        )
    errors.append(f"Imported the transactions on {wanted!r}; the file also holds others")
    return [r for r in rows if r.source_account == wanted], None


def _shift(day: str, days: int) -> str:
    """`day` moved by `days`, kept within the calendar (date.min..date.max)."""
    try:
        return (date.fromisoformat(day) + timedelta(days=days)).isoformat()
    except OverflowError:
        return (date.max if days > 0 else date.min).isoformat()


# The years a statement's transactions can be in (as the importers read them).
_FIRST_YEAR, _LAST_YEAR = 1900, 2100


def _real_dates(rows: list[RawRow]) -> tuple[list[RawRow], int]:
    """The rows with a real date in 1900-2100, and how many had none."""
    kept: list[RawRow] = []
    for row in rows:
        try:
            year = date.fromisoformat(row.date).year
        except ValueError:
            continue
        if _FIRST_YEAR <= year <= _LAST_YEAR:
            kept.append(row)
    return kept, len(rows) - len(kept)


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
    """The file's transactions as RawRows, and what could not be read. Each
    row names the account in the file it is on, when the file holds several.

    Numbers come from deterministic importers only, never the LLM. Dates
    that read either way are read the way the statement's country writes
    them (`dates.default_order`).
    """
    from salli.adapters.parsing.dates import default_order

    prefer = default_order(currency)
    kind = _statement_format(filename, data)
    if kind == "pdf":
        from salli.adapters.parsing.pdf_extractor import extract_from_pdf

        extraction = extract_from_pdf(
            data, date_order=date_order, prefer_order=prefer, currency=currency
        )
    elif kind == "xlsx":
        from salli.adapters.parsing.excel_extractor import extract_from_excel

        extraction = extract_from_excel(
            data, date_order=date_order, prefer_order=prefer, currency=currency
        )
    elif kind == "xls":
        message = (
            "This is an old-style (.xls) or password-protected Excel workbook, which Salli "
            "can't read. Save it as an unprotected .xlsx, or as CSV, and import that"
        )
        return [], [message]
    elif kind == "ofx":
        from salli.adapters.parsing.ofx import extract_from_ofx

        extraction = extract_from_ofx(data)
    elif kind == "qif":
        from salli.adapters.parsing.qif import extract_from_qif

        extraction = extract_from_qif(data, date_order=date_order, prefer_order=prefer)
    elif kind == "camt053":
        from salli.adapters.parsing.camt053 import extract_from_camt053

        extraction = extract_from_camt053(data)
    elif kind == "mt940":
        from salli.adapters.parsing.mt940 import extract_from_mt940

        extraction = extract_from_mt940(data)
    elif kind == "csv":
        from salli.adapters.parsing.csv_import import extract_from_csv

        extraction = extract_from_csv(
            data, csv_mapping, date_order=date_order, prefer_order=prefer, currency=currency
        )
    else:
        message = (
            "Salli can't read this file. It reads PDF, Excel (.xlsx), CSV, OFX/QFX, QIF, "
            "camt.053 and MT940 statements"
        )
        return [], [message]
    return _raw_rows(extraction, currency, kind)


def _raw_rows(
    extraction: Extraction, currency: str, source: str = ""
) -> tuple[list[RawRow], list[str]]:
    """An importer's lines as RawRows, each in a currency Salli knows.

    A line in a currency the file names is in that one; any other line is in
    the statement's `currency`. A code that is not ISO 4217 skips its rows,
    and says so, rather than booking them as something they are not.
    """
    errors = list(extraction.errors)
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
                bank_ref=line.bank_ref,
                source_page=line.source_page,
                ref_kind=line.ref_kind,
                source_account=line.account,
                ref_source=source,
            )
        )
    for code, count in unknown.items():
        errors.append(
            f"Skipped {count} transaction(s) in {code!r}, which is not an ISO 4217 currency code"
        )
    return rows, errors
