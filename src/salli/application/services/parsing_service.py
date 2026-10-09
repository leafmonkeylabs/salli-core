"""
ParsingService — orchestrates statement ingestion.

Flow:
  upload file bytes
  → detect format (PDF / XLSX / CSV)
  → extract RawRows (deterministic, no LLM)
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
from collections.abc import Callable
from typing import Any

from salli.application.fx import rate_to_base
from salli.application.ports import StoragePort
from salli.domain.currency import normalize_currency
from salli.domain.dedup.matcher import (
    CandidateTransaction,
    DedupStatus,
    batch_check,
    compute_dedup_key,
)
from salli.domain.money import to_minor
from salli.domain.parsing.models import ParsedTransaction, ParseResult, RawRow


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

    async def parse_statement(
        self,
        user_id: str,
        filename: str,
        file_bytes: bytes,
        bank: str = "",
        *,
        currency: str | None = None,
        api_key: Any = None,
    ) -> ParseResult:
        """
        Parse a bank statement file and store the extracted transactions.
        Returns a ParseResult — caller should display pending transactions for review.

        `currency` is the statement's (a statement never mixes currencies); it
        defaults to the user's base currency.
        """
        from salli.adapters.parsing.llm_classifier import classify_transactions

        if currency:
            currency = normalize_currency(currency)
        else:
            async with self._uow_factory() as uow:
                currency = await uow.user_profiles.base_currency(user_id)

        # 1. Extract raw rows
        raw_rows = _extract(filename, file_bytes, currency)
        if not raw_rows:
            return ParseResult(
                statement_id="",
                bank=bank,
                period_start="",
                period_end="",
                errors=["No transactions found in the file. Check the format is supported"],
            )

        period_start = min(r.date for r in raw_rows)
        period_end = max(r.date for r in raw_rows)

        # 2. Intra-batch dedup using the dedup matcher
        candidates = [
            CandidateTransaction(
                id=str(i),
                account_id="unknown",  # account not classified yet
                entry_date=r.date,
                amount_minor=to_minor(r.amount, r.currency),
                currency=r.currency,
                description=r.description,
                source="statement",
                bank_ref=r.bank_ref or None,
            )
            for i, r in enumerate(raw_rows)
        ]
        dedup_results = batch_check(candidates, existing=[], existing_keys=set())

        unique_rows = [
            r
            for r, dr in zip(raw_rows, dedup_results, strict=False)
            if dr.status != DedupStatus.EXACT_DUPLICATE
        ]

        # 3. Load accounts for LLM classification
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id)

        if not accounts:
            return ParseResult(
                statement_id="",
                bank=bank,
                period_start=period_start,
                period_end=period_end,
                raw_rows=raw_rows,
                errors=["No accounts found. Create a chart of accounts first"],
            )

        # 4. LLM classifies transactions
        parsed = await classify_transactions(
            unique_rows, accounts, api_key=await self._key_for(user_id, api_key)
        )

        # 5. Stamp dedup keys and check against existing ledger entries
        async with self._uow_factory() as uow:
            existing_entries = await uow.ledger.get_entries(
                user_id, from_date=period_start, to_date=period_end
            )

        existing_keys: set[str] = set()
        for entry in existing_entries:
            for posting in entry.postings:
                if posting.bank_ref if hasattr(posting, "bank_ref") else False:
                    existing_keys.add(posting.bank_ref)

        for txn in parsed:
            candidate = CandidateTransaction(
                id="0",
                account_id=txn.debit_account_id or "unknown",
                entry_date=txn.raw.date,
                amount_minor=to_minor(txn.raw.amount, txn.raw.currency),
                currency=txn.raw.currency,
                description=txn.raw.description,
                source="statement",
                bank_ref=txn.raw.bank_ref or None,
            )
            txn.dedup_key = compute_dedup_key(candidate)
            if txn.dedup_key in existing_keys:
                txn.dedup_status = DedupStatus.EXACT_DUPLICATE.value

        # 6. Upload raw file to storage (best-effort — parsing proceeds even if storage fails)
        statement_id = str(uuid.uuid4())
        storage_key = ""
        if self._storage is not None:
            try:
                storage_key = await self._storage.upload(
                    user_id, f"{statement_id}/{filename}", file_bytes
                )
            except Exception:
                pass

        # 7. Persist to DB
        async with self._uow_factory() as uow:
            await uow.statements.save_statement(
                user_id=user_id,
                statement_id=statement_id,
                bank=bank,
                period_start=period_start,
                period_end=period_end,
                transactions=parsed,
                storage_key=storage_key,
            )

        return ParseResult(
            statement_id=statement_id,
            bank=bank,
            period_start=period_start,
            period_end=period_end,
            transactions=parsed,
            raw_rows=raw_rows,
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
            entry_ids = []

            for txn in txns:
                if txn.dedup_status == DedupStatus.EXACT_DUPLICATE.value:
                    continue
                if not txn.debit_account_id or not txn.credit_account_id:
                    continue

                # The classifier already produced a plain-language label for
                # this row, which was shown during review and then thrown away
                # at posting time. Carry it onto the debit side as a category
                # tag so the work is not wasted and spending is classified from
                # the moment a statement is imported.
                category_tags = {"category": _slugify(txn.category)} if txn.category else {}

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
                        tags=category_tags,
                    ),
                    Posting(
                        account_id=txn.credit_account_id,
                        direction=Direction.CREDIT,
                        amount=txn.raw.amount,
                        currency=txn.raw.currency,
                        fx_rate=fx_rate,
                        fx_rate_source=fx_source,
                    ),
                ]
                entry = JournalEntry(
                    entry_date=txn.raw.date,
                    description=txn.raw.description,
                    source="statement",
                    external_ref=txn.id,
                    postings=postings,
                )
                entry_id = await uow.ledger.save_entry(user_id, entry)
                await uow.statements.mark_posted(txn.id, entry_id)
                entry_ids.append(entry_id)

        return entry_ids


# ── Format detection ───────────────────────────────────────────────────────────


def _extract(filename: str, data: bytes, currency: str) -> list[RawRow]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        from salli.adapters.parsing.pdf_extractor import extract_from_pdf

        raw = extract_from_pdf(data)
    elif ext in ("xlsx", "xls"):
        from salli.adapters.parsing.excel_extractor import extract_from_excel

        raw = extract_from_excel(data)
    elif ext == "csv":
        from salli.adapters.parsing.excel_extractor import extract_from_csv

        raw = extract_from_csv(data)
    else:
        # Sniff by magic bytes
        if data[:4] == b"%PDF":
            from salli.adapters.parsing.pdf_extractor import extract_from_pdf

            raw = extract_from_pdf(data)
        elif data[:2] in (b"PK", b"\x50\x4b"):  # ZIP = XLSX
            from salli.adapters.parsing.excel_extractor import extract_from_excel

            raw = extract_from_excel(data)
        else:
            return []

    return [
        RawRow(
            date=r["date"],
            description=r["description"],
            amount=r["amount"],
            credit_flag=r["credit_flag"],
            currency=currency,
            bank_ref=r.get("bank_ref", ""),
            source_page=r.get("page", 0),
        )
        for r in raw
    ]
