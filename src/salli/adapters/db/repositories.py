"""
SQLAlchemy repository implementations — concrete adapters for the port interfaces.
Translate between ORM models and domain models via mappers below.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Collection, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import Select, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from salli.adapters.db.models import (
    AccountORM,
    AdvisoryReportORM,
    AgentDocumentORM,
    AgentSessionORM,
    AiConnectionORM,
    AuditLogORM,
    BankConnectionAccountORM,
    BankConnectionORM,
    BudgetORM,
    CategorizationRuleORM,
    DebtORM,
    DocumentORM,
    FireStrategyORM,
    FiScoreORM,
    GoalAllocationORM,
    GoalORM,
    HoldingORM,
    InstanceSettingORM,
    InsuranceTargetORM,
    JournalEntryORM,
    OAuthAccessTokenORM,
    OAuthAuthorizationCodeORM,
    OAuthClientORM,
    OAuthDeviceCodeORM,
    OAuthRefreshTokenORM,
    ParsedTransactionORM,
    PersonalAccessTokenORM,
    PolicyORM,
    PostingORM,
    PostingTagORM,
    RecurringSubscriptionORM,
    ReminderORM,
    StatementORM,
    TagORM,
    TaxComputationORM,
    UserLlmCredentialORM,
    UserProfileORM,
)
from salli.application.ports import (
    AccountCodeTaken,
    AdvisoryRepository,
    AgentDocumentRepository,
    AgentSessionRepository,
    AiConnectionRepository,
    AuditLogRepository,
    BankConnectionRepository,
    BudgetRepository,
    DataPortabilityRepository,
    DebtRepository,
    FireStrategyRepository,
    FiScoreRepository,
    GoalRepository,
    InstanceSettingsRepository,
    InsuranceTargetRepository,
    LedgerRepository,
    LlmCredentialRepository,
    McpConnectionRow,
    OAuthClientRepository,
    OAuthTokenRepository,
    PersonalAccessTokenRepository,
    PolicyRepository,
    PortfolioRepository,
    ProfileMissing,
    RecurringSubscriptionRepository,
    ReminderRepository,
    RemoteAccount,
    RuleRepository,
    StatementRepository,
    TaxComputationRepository,
    UserProfileRepository,
)
from salli.domain.accounting.models import (
    Account,
    Direction,
    JournalEntry,
    Posting,
    StoredJournalEntry,
    Tag,
)
from salli.domain.currency import exponent, is_currency
from salli.domain.money import from_minor, to_minor
from salli.domain.tax.models import TaxComputation

if TYPE_CHECKING:
    from salli.extensions import UserDataPurger

# ── Mappers ───────────────────────────────────────────────────────────────────


def _posting_to_orm(p: Posting, entry_id: str, base_currency: str) -> PostingORM:
    # base_amount_minor is the unsigned FX-converted amount in minor units.
    # The trigger multiplies by `direction` to get the signed contribution, so
    # storing p.base_signed here would double-sign credits and break the check.
    return PostingORM(
        entry_id=entry_id,
        account_id=p.account_id,
        direction=p.direction.value,
        # In the posting's own currency's minor units: cents for USD, yen for
        # JPY, fils for KWD. to_minor rounds HALF-UP (int() truncated, silently
        # dropping a cent on amounts like 1234.565).
        amount_minor=to_minor(p.amount, p.currency),
        currency=p.currency,
        # Decimal straight into the Numeric(20,8) column — no float round-trip.
        fx_rate=p.fx_rate,
        fx_rate_source=p.fx_rate_source,
        # In the base currency's minor units, the same scale for every posting
        # of the entry, which is all the balance trigger needs.
        base_amount_minor=to_minor(p.amount * p.fx_rate, base_currency),
    )


def _posting_from_orm(row: PostingORM) -> Posting:
    return Posting(
        id=row.id,
        account_id=row.account_id,
        direction=Direction(row.direction),
        # Lenient: a row written before codes were validated still reads.
        amount=from_minor(row.amount_minor, row.currency, strict=False),
        currency=row.currency,
        fx_rate=Decimal(str(row.fx_rate)),
        fx_rate_source=row.fx_rate_source,
        tags={link.kind: link.tag.slug for link in row.tag_links},
    )


def _entry_from_orm(row: JournalEntryORM) -> StoredJournalEntry:
    return StoredJournalEntry(
        id=row.id,
        user_id=row.user_id,
        entry_date=row.entry_date,
        description=row.description,
        source=row.source,  # type: ignore[arg-type]
        external_ref=row.external_ref,
        reversed_by=row.reversed_by,
        postings=[_posting_from_orm(p) for p in row.postings],
    )


def _tag_from_orm(row: TagORM) -> Tag:
    return Tag(
        id=row.id,
        user_id=row.user_id,
        slug=row.slug,
        name=row.name,
        kind=row.kind,  # type: ignore[arg-type]
        color=row.color,
        is_system=row.is_system,
    )


def _account_from_orm(row: AccountORM) -> Account:
    return Account(
        id=row.id,
        user_id=row.user_id,
        code=row.code,
        name=row.name,
        type=row.type,  # type: ignore[arg-type]
        currency=row.currency,
        parent_id=row.parent_id,
        is_active=row.is_active,
        tax_role=row.tax_role,  # type: ignore[arg-type]
    )


# ── LedgerRepository ─────────────────────────────────────────────────────────


class SQLLedgerRepository(LedgerRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _resolve_tags(
        self, user_id: str, wanted: set[tuple[str, str]]
    ) -> dict[tuple[str, str], TagORM]:
        """(kind, slug) pairs → tag rows for this user, creating any that are missing.

        Auto-creating keeps the write path honest: a client can tag a posting
        "groceries" without a separate round-trip to define the tag first, and
        two postings tagged the same way always land on the same row thanks to
        the (user_id, kind, slug) unique constraint.

        The caller supplies the axis, so nothing here has to guess which one a
        slug belongs to.
        """
        if not wanted:
            return {}
        slugs = {slug for _, slug in wanted}
        stmt = select(TagORM).where(TagORM.user_id == user_id, TagORM.slug.in_(slugs))
        result = await self._session.execute(stmt)
        found = {(row.kind, row.slug): row for row in result.scalars().all()}

        for kind, slug in sorted(wanted):
            if (kind, slug) in found:
                continue
            tag = TagORM(
                id=str(uuid.uuid4()),
                user_id=user_id,
                slug=slug,
                name=slug.replace("-", " ").replace("_", " ").title(),
                kind=kind,
                is_system=False,
            )
            self._session.add(tag)
            found[(kind, slug)] = tag
        return found

    async def ensure_system_tags(self, user_id: str, tags: list[tuple[str, str, str]]) -> None:
        """Create the closed `need` axis for a user if it is not already there.

        Idempotent: existing slugs are left untouched, including their names, so
        a user who renamed "Wants" keeps that name across re-onboarding. Safe
        to run twice at once: a slug inserted meanwhile is skipped by the
        database (ON CONFLICT DO NOTHING), not a failed commit.
        """
        if not tags:
            return
        await self._session.execute(
            pg_insert(TagORM)
            .values(
                [
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "slug": slug,
                        "name": name,
                        "kind": "need",
                        "color": color,
                        "is_system": True,
                        "created_at": datetime.now(UTC),
                    }
                    for slug, name, color in tags
                ]
            )
            .on_conflict_do_nothing(constraint="uq_tags_user_kind_slug")
        )

    async def list_tags(self, user_id: str, kind: str | None = None) -> list[Tag]:
        stmt = select(TagORM).where(TagORM.user_id == user_id)
        if kind:
            stmt = stmt.where(TagORM.kind == kind)
        result = await self._session.execute(stmt.order_by(TagORM.kind, TagORM.name))
        return [_tag_from_orm(r) for r in result.scalars().all()]

    async def set_posting_tags(self, user_id: str, posting_id: str, tags: dict[str, str]) -> None:
        """Replace a posting's tags.

        Retagging is the one thing about a posted entry that *is* mutable. The
        money is immutable and corrections go through reversing entries, but a
        miscategorised expense has to be fixable without rewriting history —
        which is exactly why tags live in their own table.
        """
        owns = await self._session.execute(
            select(PostingORM.id)
            .join(JournalEntryORM, PostingORM.entry_id == JournalEntryORM.id)
            .where(PostingORM.id == posting_id, JournalEntryORM.user_id == user_id)
        )
        if owns.scalar_one_or_none() is None:
            raise ValueError("Posting not found")

        await self._session.execute(
            delete(PostingTagORM).where(PostingTagORM.posting_id == posting_id)
        )
        resolved = await self._resolve_tags(user_id, set(tags.items()))
        for kind, slug in tags.items():
            self._session.add(
                PostingTagORM(posting_id=posting_id, kind=kind, tag_id=resolved[(kind, slug)].id)
            )

    async def _base_currency(self, user_id: str) -> str:
        result = await self._session.execute(
            select(UserProfileORM.base_currency).where(UserProfileORM.id == user_id)
        )
        base = result.scalar_one_or_none()
        if base is None:
            raise ProfileMissing(user_id)
        return base

    async def save_entry(self, user_id: str, entry: JournalEntry) -> str:
        entry_id = str(uuid.uuid4())
        base_currency = await self._base_currency(user_id)
        orm_entry = JournalEntryORM(
            id=entry_id,
            user_id=user_id,
            entry_date=entry.entry_date,
            description=entry.description,
            source=entry.source,
            external_ref=entry.external_ref,
        )

        wanted = {(kind, slug) for p in entry.postings for kind, slug in p.tags.items()}
        tags = await self._resolve_tags(user_id, wanted)

        orm_postings: list[PostingORM] = []
        for p in entry.postings:
            orm_p = _posting_to_orm(p, entry_id, base_currency)
            # `posting_id` is left to the relationship: the posting's own id
            # comes from a column default and is still None until flush.
            orm_p.tag_links = [
                PostingTagORM(kind=kind, tag_id=tags[(kind, slug)].id)
                for kind, slug in p.tags.items()
            ]
            orm_postings.append(orm_p)

        orm_entry.postings = orm_postings
        self._session.add(orm_entry)
        return entry_id

    async def get_entries(
        self,
        user_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[StoredJournalEntry]:
        stmt = (
            select(JournalEntryORM)
            .where(JournalEntryORM.user_id == user_id)
            .options(selectinload(JournalEntryORM.postings))
            .order_by(JournalEntryORM.entry_date, JournalEntryORM.created_at)
        )
        if from_date:
            stmt = stmt.where(JournalEntryORM.entry_date >= from_date)
        if to_date:
            stmt = stmt.where(JournalEntryORM.entry_date <= to_date)

        result = await self._session.execute(stmt)
        return [_entry_from_orm(row) for row in result.scalars().all()]

    async def posting_totals(
        self, user_id: str, account_ids: Collection[str]
    ) -> list[tuple[str, str, Decimal, Decimal]]:
        if not account_ids:
            return []
        signed = PostingORM.direction * PostingORM.amount_minor
        rows = await self._session.execute(
            select(
                PostingORM.account_id,
                PostingORM.currency,
                func.sum(signed),
                func.sum(signed * PostingORM.fx_rate),
            )
            .join(JournalEntryORM, JournalEntryORM.id == PostingORM.entry_id)
            .where(JournalEntryORM.user_id == user_id, PostingORM.account_id.in_(list(account_ids)))
            .group_by(PostingORM.account_id, PostingORM.currency)
        )
        totals: list[tuple[str, str, Decimal, Decimal]] = []
        for account_id, currency, amount, base in rows.all():
            places = -exponent(currency, strict=False)
            totals.append(
                (account_id, currency, Decimal(amount).scaleb(places), Decimal(base).scaleb(places))
            )
        return totals

    async def balances_before(self, user_id: str, before: str) -> dict[str, Decimal]:
        # Exactly what Posting.base_signed sums, unrounded: direction times
        # amount (minor units of its currency) times the rate, per currency,
        # then scaled by that currency's decimals.
        rows = await self._session.execute(
            select(
                PostingORM.account_id,
                PostingORM.currency,
                func.sum(PostingORM.direction * PostingORM.amount_minor * PostingORM.fx_rate),
            )
            .join(JournalEntryORM, JournalEntryORM.id == PostingORM.entry_id)
            .where(JournalEntryORM.user_id == user_id, JournalEntryORM.entry_date < before)
            .group_by(PostingORM.account_id, PostingORM.currency)
        )
        balances: dict[str, Decimal] = {}
        for account_id, currency, total in rows.all():
            scaled = Decimal(total).scaleb(-exponent(currency, strict=False))
            balances[account_id] = balances.get(account_id, Decimal(0)) + scaled
        return balances

    async def get_accounts(self, user_id: str, include_inactive: bool = False) -> list[Account]:
        stmt = select(AccountORM).where(AccountORM.user_id == user_id).order_by(AccountORM.code)
        if not include_inactive:
            stmt = stmt.where(AccountORM.is_active == True)  # noqa: E712
        result = await self._session.execute(stmt)
        return [_account_from_orm(row) for row in result.scalars().all()]

    async def save_account(self, user_id: str, account: Account) -> str:
        import uuid

        account_id = account.id or str(uuid.uuid4())
        orm = AccountORM(
            id=account_id,
            user_id=user_id,
            code=account.code,
            name=account.name,
            type=account.type,
            currency=account.currency,
            parent_id=account.parent_id,
            is_active=account.is_active,
            tax_role=account.tax_role,
        )
        # In a savepoint, so a code taken meanwhile (two onboardings at once)
        # is a typed error the caller can act on, not a failed commit.
        try:
            async with self._session.begin_nested():
                self._session.add(orm)
        except IntegrityError as exc:
            if "uq_accounts_user_code" in str(exc.orig):
                raise AccountCodeTaken(account.code) from exc
            raise
        return account_id

    async def get_entry_by_id(self, user_id: str, entry_id: str) -> StoredJournalEntry | None:
        stmt = (
            select(JournalEntryORM)
            .where(JournalEntryORM.id == entry_id, JournalEntryORM.user_id == user_id)
            .options(selectinload(JournalEntryORM.postings))
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _entry_from_orm(row) if row else None

    async def set_reversed_by(self, entry_id: str, reversing_id: str) -> None:
        stmt = select(JournalEntryORM).where(JournalEntryORM.id == entry_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.reversed_by = reversing_id

    async def update_account(
        self,
        user_id: str,
        account_id: str,
        *,
        code: str,
        name: str,
        type: str,
        currency: str,
        tax_role: str | None = None,
    ) -> None:
        stmt = select(AccountORM).where(AccountORM.id == account_id, AccountORM.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.code = code
            row.name = name
            row.type = type
            row.currency = currency
            row.tax_role = tax_role

    async def deactivate_account(self, user_id: str, account_id: str) -> None:
        stmt = select(AccountORM).where(AccountORM.id == account_id, AccountORM.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.is_active = False

    async def reactivate_account(self, user_id: str, account_id: str) -> None:
        stmt = select(AccountORM).where(AccountORM.id == account_id, AccountORM.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.is_active = True

    async def get_account(self, user_id: str, account_id: str) -> Account | None:
        stmt = select(AccountORM).where(AccountORM.id == account_id, AccountORM.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _account_from_orm(row) if row else None


# ── TaxComputationRepository ──────────────────────────────────────────────────


class SQLTaxComputationRepository(TaxComputationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _serialize(self, computation: TaxComputation) -> dict[str, Any]:
        import dataclasses

        return json.loads(json.dumps(dataclasses.asdict(computation), default=str))

    async def save(self, user_id: str, computation: TaxComputation) -> str:
        import uuid

        result_dict = self._serialize(computation)
        # Every input the engine actually consumes. Hashing only gross+relief
        # meant two computations with completely different credits, FSI or
        # qualifying payments collided, so the hash could not do the one job it
        # exists for — telling you whether a stored result is still current.
        inputs_hash = hashlib.sha256(
            json.dumps(
                {
                    "pack_version": computation.pack_version,
                    "gross": str(computation.gross_income),
                    "fsi": str(computation.foreign_service_income),
                    "relief": str(computation.personal_relief_applied),
                    "qp": str(computation.qp_deduction),
                    "apit": str(computation.apit_credit),
                    "ait": str(computation.ait_credit),
                    "ftc": str(computation.foreign_tax_credit),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

        orm = TaxComputationORM(
            id=str(uuid.uuid4()),
            user_id=user_id,
            year=computation.pack_year,
            pack_version=computation.pack_version,
            inputs_hash=inputs_hash,
            result_json=result_dict,
        )
        self._session.add(orm)
        return orm.id

    async def get_latest(self, user_id: str, year: str) -> TaxComputation | None:
        stmt = (
            select(TaxComputationORM)
            .where(
                TaxComputationORM.user_id == user_id,
                TaxComputationORM.year == year,
            )
            .order_by(TaxComputationORM.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        # Deserialize back — used only for display/reporting, not recomputation.
        return row.result_json  # type: ignore[return-value]

    async def list_computation_keys(self) -> list[tuple[str, str]]:
        stmt = select(TaxComputationORM.user_id, TaxComputationORM.year).distinct()
        result = await self._session.execute(stmt)
        return [(r[0], r[1]) for r in result.all()]


# ── StatementRepository ───────────────────────────────────────────────────────


class SQLStatementRepository(StatementRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_statements(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            (
                await self._session.execute(
                    select(StatementORM)
                    .where(StatementORM.user_id == user_id)
                    .order_by(StatementORM.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": r.id,
                "bank": r.bank,
                "account_id": r.account_id,
                "period_start": r.period_start,
                "period_end": r.period_end,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def save_statement(
        self,
        user_id: str,
        statement_id: str,
        bank: str,
        period_start: str,
        period_end: str,
        transactions: list[Any],
        storage_key: str = "",
        account_id: str | None = None,
    ) -> None:
        import uuid as _uuid

        # The label fits its column, whoever made it: a bank feed's
        # "institution · account name" can run past it.
        width = StatementORM.__table__.c.bank.type.length or 100
        orm = StatementORM(
            id=statement_id,
            user_id=user_id,
            storage_key=storage_key,
            bank=(bank or "")[:width],
            account_id=account_id,
            period_start=period_start,
            period_end=period_end,
            status="pending",
        )
        self._session.add(orm)

        for txn in transactions:
            raw = txn.raw
            pt = ParsedTransactionORM(
                id=str(_uuid.uuid4()),
                statement_id=statement_id,
                raw=f"{raw.date}|{raw.description}|{raw.amount}|{raw.credit_flag}",
                extracted_json={
                    "date": raw.date,
                    "description": raw.description,
                    "amount": str(raw.amount),
                    "credit_flag": raw.credit_flag,
                    "bank_ref": raw.bank_ref,
                    "debit_account_id": txn.debit_account_id,
                    "credit_account_id": txn.credit_account_id,
                    "category": txn.category,
                    "currency": raw.currency,
                    "need": txn.need,
                    # "description" is the bank's text, above.
                    "booking_description": txn.description,
                    "rule_id": txn.rule_id,
                    "duplicate_of": txn.duplicate_of,
                    "ref_kind": raw.ref_kind,
                    "ref_source": raw.ref_source,
                    "source_account": raw.source_account,
                },
                confidence=txn.confidence,
                dedup_key=txn.dedup_key or None,
                dedup_status=txn.dedup_status,
            )
            self._session.add(pt)
            # What the caller hands back to the user names real rows.
            txn.id, txn.statement_id, txn.account_id = pt.id, statement_id, account_id or ""

    def _parsed(self, user_id: str) -> Any:
        """This user's parsed transactions, each with its statement's account."""
        return (
            select(ParsedTransactionORM, StatementORM.account_id)
            .join(StatementORM)
            .where(StatementORM.user_id == user_id)
        )

    async def _read(self, stmt: Any) -> list[Any]:
        result = await self._session.execute(stmt)
        return [_orm_to_parsed(row, account_id) for row, account_id in result.all()]

    async def imported_between(
        self,
        user_id: str,
        from_date: str,
        to_date: str,
        *,
        account_id: str | None = None,
        excluding_statement: str | None = None,
    ) -> list[Any]:
        # The date lives in the row's JSON, indexed as an expression
        # (ix_parsed_transactions_date); ISO dates compare as text.
        when = ParsedTransactionORM.extracted_json["date"].astext
        stmt = self._parsed(user_id).where(
            when >= from_date,
            when <= to_date,
            ParsedTransactionORM.dedup_status != "exact_duplicate",
        )
        if account_id is not None:
            # Rows of statements with no account may be on any account.
            stmt = stmt.where(
                or_(StatementORM.account_id == account_id, StatementORM.account_id.is_(None))
            )
        if excluding_statement is not None:
            stmt = stmt.where(
                or_(
                    ParsedTransactionORM.statement_id != excluding_statement,
                    ParsedTransactionORM.posted_entry_id.is_not(None),
                )
            )
        return await self._read(
            stmt.order_by(ParsedTransactionORM.created_at, ParsedTransactionORM.id)
        )

    async def get_all_pending(self, user_id: str) -> list[Any]:
        return await self._read(
            self._parsed(user_id)
            .where(*_PENDING)
            .order_by(ParsedTransactionORM.statement_id, ParsedTransactionORM.created_at)
        )

    async def get_pending(self, user_id: str, statement_id: str) -> list[Any]:
        return await self._read(
            self._parsed(user_id)
            .where(ParsedTransactionORM.statement_id == statement_id, *_PENDING)
            .order_by(ParsedTransactionORM.created_at, ParsedTransactionORM.id)
        )

    async def discard(self, user_id: str, statement_id: str, ids: list[str] | None = None) -> int:
        stmt = (
            select(ParsedTransactionORM)
            .join(StatementORM)
            .where(
                StatementORM.user_id == user_id,
                ParsedTransactionORM.statement_id == statement_id,
                *_PENDING,
            )
        )
        if ids is not None:
            stmt = stmt.where(ParsedTransactionORM.id.in_(ids))
        rows = (await self._session.execute(stmt)).scalars().all()
        for row in rows:
            row.dedup_status = "discarded"
        await self._session.flush()
        return len(rows)

    async def get_by_ids(
        self, user_id: str, ids: list[str], *, for_update: bool = False
    ) -> list[Any]:
        stmt = self._parsed(user_id).where(ParsedTransactionORM.id.in_(ids))
        if for_update:
            stmt = stmt.with_for_update(of=ParsedTransactionORM)
        return await self._read(stmt)

    async def export(self, user_id: str) -> list[dict[str, Any]]:
        statements = (
            (
                await self._session.execute(
                    select(StatementORM)
                    .where(StatementORM.user_id == user_id)
                    .order_by(StatementORM.created_at, StatementORM.id)
                )
            )
            .scalars()
            .all()
        )
        rows = await self._read(
            self._parsed(user_id).order_by(ParsedTransactionORM.created_at, ParsedTransactionORM.id)
        )
        by_statement: dict[str, list[Any]] = {}
        for txn in rows:
            by_statement.setdefault(txn.statement_id, []).append(txn)
        return [
            {
                "id": st.id,
                "bank": st.bank,
                "account_id": st.account_id,
                "period_start": st.period_start,
                "period_end": st.period_end,
                "storage_key": st.storage_key,
                "status": st.status,
                "created_at": st.created_at.isoformat() if st.created_at else None,
                "transactions": by_statement.get(st.id, []),
            }
            for st in statements
        ]

    async def set_choice(self, user_id: str, transaction_id: str, fields: dict[str, Any]) -> None:
        row = (
            await self._session.execute(
                select(ParsedTransactionORM)
                .join(StatementORM)
                .where(StatementORM.user_id == user_id, ParsedTransactionORM.id == transaction_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return
        # A new dict, not an edit in place: the JSONB column tracks assignment.
        row.extracted_json = {**row.extracted_json, **fields}
        row.confidence = Decimal(1)  # decided by someone, not guessed
        await self._session.flush()

    async def mark_posted(self, transaction_id: str, entry_id: str) -> None:
        stmt = select(ParsedTransactionORM).where(ParsedTransactionORM.id == transaction_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.posted_entry_id = entry_id
            row.dedup_status = "posted"

    async def get_statement(self, user_id: str, statement_id: str) -> dict[str, Any] | None:
        stmt = select(StatementORM).where(
            StatementORM.id == statement_id, StatementORM.user_id == user_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {
            "id": row.id,
            "bank": row.bank,
            "account_id": row.account_id,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "storage_key": row.storage_key,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }


# Waiting for review: not posted, and not discarded.
_PENDING = (
    ParsedTransactionORM.posted_entry_id.is_(None),
    # An exact duplicate needs nothing from anyone: its import's result said
    # so once, and it never posts.
    ParsedTransactionORM.dedup_status.not_in(("discarded", "exact_duplicate")),
)


def _orm_to_parsed(row: ParsedTransactionORM, account_id: str | None = None) -> Any:
    from decimal import Decimal

    from salli.domain.parsing.models import ParsedTransaction, RawRow

    j = row.extracted_json
    raw = RawRow(
        date=j["date"],
        description=j["description"],
        amount=Decimal(str(j["amount"])),
        credit_flag=j["credit_flag"],
        bank_ref=j.get("bank_ref", ""),
        # Rows saved before the currency was recorded were all rupees.
        currency=j.get("currency", "LKR"),
        ref_kind=j.get("ref_kind", "id"),
        ref_source=j.get("ref_source", ""),
        source_account=j.get("source_account", ""),
    )
    return ParsedTransaction(
        raw=raw,
        debit_account_id=j.get("debit_account_id", ""),
        credit_account_id=j.get("credit_account_id", ""),
        category=j.get("category", ""),
        need=j.get("need", ""),
        description=j.get("booking_description", ""),
        rule_id=j.get("rule_id", ""),
        duplicate_of=j.get("duplicate_of", ""),
        # Zero is a real confidence (nothing decided the row), not a missing one.
        confidence=float(row.confidence) if row.confidence is not None else 0.5,
        dedup_key=row.dedup_key or "",
        dedup_status=row.dedup_status,
        id=row.id,
        statement_id=row.statement_id,
        account_id=account_id or "",
    )


# ── ReminderRepository ────────────────────────────────────────────────────────


class SQLReminderRepository(ReminderRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_reminders(self, user_id: str, status: str | None = None) -> list[Any]:
        stmt = select(ReminderORM).where(ReminderORM.user_id == user_id)
        if status:
            stmt = stmt.where(ReminderORM.status == status)
        stmt = stmt.order_by(ReminderORM.due_date)
        result = await self._session.execute(stmt)
        return [
            {
                "id": r.id,
                "kind": r.kind,
                "due_date": r.due_date,
                "status": r.status,
                "alert_type": r.alert_type,
                "source_domain": r.source_domain,
                "source_id": r.source_id,
                "severity": r.severity,
                "created_at": r.created_at.isoformat(),
            }
            for r in result.scalars().all()
        ]

    async def create_reminder(
        self, user_id: str, reminder_id: str, kind: str, due_date: str
    ) -> None:
        self._session.add(
            ReminderORM(
                id=reminder_id,
                user_id=user_id,
                kind=kind,
                due_date=due_date,
                status="pending",
            )
        )

    async def mark_done(self, user_id: str, reminder_id: str) -> None:
        stmt = select(ReminderORM).where(
            ReminderORM.id == reminder_id, ReminderORM.user_id == user_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.status = "done"

    async def delete_reminder(self, user_id: str, reminder_id: str) -> None:
        stmt = select(ReminderORM).where(
            ReminderORM.id == reminder_id, ReminderORM.user_id == user_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            await self._session.delete(row)

    async def upsert_alert(
        self,
        user_id: str,
        alert_type: str,
        source_domain: str,
        source_id: str,
        kind: str,
        due_date: str,
        severity: str,
    ) -> str:
        stmt = select(ReminderORM).where(
            ReminderORM.user_id == user_id,
            ReminderORM.source_domain == source_domain,
            ReminderORM.source_id == source_id,
            ReminderORM.alert_type == alert_type,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.kind = kind
            row.due_date = due_date
            row.severity = severity
            row.status = "pending"
            return row.id
        alert_id = str(uuid.uuid4())
        self._session.add(
            ReminderORM(
                id=alert_id,
                user_id=user_id,
                kind=kind,
                due_date=due_date,
                status="pending",
                alert_type=alert_type,
                source_domain=source_domain,
                source_id=source_id,
                severity=severity,
            )
        )
        return alert_id


# ── Agent Documents ────────────────────────────────────────────────────────────


def _doc_to_dict(row: AgentDocumentORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "title": row.title,
        "content": row.content,
        "storage_key": row.storage_key,
        "mime_type": row.mime_type,
        "tags": row.tags or [],
        "source": row.source,
        "namespace": row.namespace,
        "slug": row.slug,
        "description": row.description,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


class SQLAgentDocumentRepository(AgentDocumentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, user_id: str, doc: dict[str, Any]) -> str:
        doc_id = doc.get("id") or str(uuid.uuid4())
        now = datetime.now(UTC)
        row = AgentDocumentORM(
            id=doc_id,
            user_id=user_id,
            title=doc.get("title", "Untitled"),
            content=doc.get("content"),
            storage_key=doc.get("storage_key"),
            mime_type=doc.get("mime_type", "text/plain"),
            tags=doc.get("tags", []),
            source=doc.get("source", "agent_created"),
            namespace=doc.get("namespace", "documents"),
            slug=doc.get("slug"),
            description=doc.get("description"),
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        return doc_id

    async def get(self, user_id: str, doc_id: str) -> dict[str, Any] | None:
        stmt = select(AgentDocumentORM).where(
            AgentDocumentORM.id == doc_id, AgentDocumentORM.user_id == user_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _doc_to_dict(row) if row else None

    async def update(self, user_id: str, doc_id: str, updates: dict[str, Any]) -> None:
        stmt = select(AgentDocumentORM).where(
            AgentDocumentORM.id == doc_id, AgentDocumentORM.user_id == user_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return
        for field in ("title", "content", "storage_key", "mime_type", "tags", "description"):
            if field in updates:
                setattr(row, field, updates[field])
        row.updated_at = datetime.now(UTC)

    async def list(
        self,
        user_id: str,
        tags: list[str] | None = None,
        namespace: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(AgentDocumentORM).where(AgentDocumentORM.user_id == user_id)
        if namespace:
            stmt = stmt.where(AgentDocumentORM.namespace == namespace)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    AgentDocumentORM.title.ilike(pattern),
                    AgentDocumentORM.content.ilike(pattern),
                )
            )
        if tags:
            for tag in tags:
                stmt = stmt.where(AgentDocumentORM.tags.contains([tag]))
        stmt = stmt.order_by(AgentDocumentORM.updated_at.desc())
        result = await self._session.execute(stmt)
        return [_doc_to_dict(r) for r in result.scalars().all()]

    async def delete(self, user_id: str, doc_id: str) -> None:
        stmt = select(AgentDocumentORM).where(
            AgentDocumentORM.id == doc_id, AgentDocumentORM.user_id == user_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            await self._session.delete(row)

    async def get_by_slug(self, user_id: str, namespace: str, slug: str) -> dict[str, Any] | None:
        stmt = select(AgentDocumentORM).where(
            AgentDocumentORM.user_id == user_id,
            AgentDocumentORM.namespace == namespace,
            AgentDocumentORM.slug == slug,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _doc_to_dict(row) if row else None

    async def upsert_by_slug(
        self, user_id: str, namespace: str, slug: str, doc: dict[str, Any]
    ) -> str:
        existing = await self.get_by_slug(user_id, namespace, slug)
        if existing:
            updates = {
                k: v for k, v in doc.items() if k not in ("id", "user_id", "slug", "namespace")
            }
            await self.update(user_id, existing["id"], updates)
            return existing["id"]
        return await self.save(
            user_id,
            {**doc, "namespace": namespace, "slug": slug, "user_id": user_id},
        )


# ── Agent session repository ──────────────────────────────────────────────────


def _session_to_dict(row: AgentSessionORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "thread_id": row.thread_id,
        "title": row.title,
        "persona": row.persona,
        "created_at": row.created_at.isoformat(),
        "last_active_at": row.last_active_at.isoformat(),
    }


class SQLAgentSessionRepository(AgentSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert(self, user_id: str, thread_id: str, persona: str = "scrooge") -> None:
        stmt = select(AgentSessionORM).where(
            AgentSessionORM.user_id == user_id,
            AgentSessionORM.thread_id == thread_id,
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.last_active_at = datetime.now(UTC)
        else:
            self._s.add(
                AgentSessionORM(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    thread_id=thread_id,
                    persona=persona,
                    last_active_at=datetime.now(UTC),
                )
            )
        await self._s.flush()

    async def set_title(self, user_id: str, thread_id: str, title: str) -> None:
        stmt = select(AgentSessionORM).where(
            AgentSessionORM.user_id == user_id,
            AgentSessionORM.thread_id == thread_id,
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one_or_none()
        if row and not row.title:
            row.title = title
            await self._s.flush()

    async def list(
        self, user_id: str, limit: int = 50, persona: str = "scrooge"
    ) -> list[dict[str, Any]]:
        stmt = (
            select(AgentSessionORM)
            .where(AgentSessionORM.user_id == user_id, AgentSessionORM.persona == persona)
            .order_by(AgentSessionORM.last_active_at.desc())
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        return [_session_to_dict(r) for r in result.scalars().all()]

    async def get(self, user_id: str, thread_id: str) -> dict[str, Any] | None:
        stmt = select(AgentSessionORM).where(
            AgentSessionORM.user_id == user_id,
            AgentSessionORM.thread_id == thread_id,
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one_or_none()
        return _session_to_dict(row) if row else None

    async def delete(self, user_id: str, thread_id: str) -> None:
        stmt = select(AgentSessionORM).where(
            AgentSessionORM.user_id == user_id,
            AgentSessionORM.thread_id == thread_id,
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            await self._s.delete(row)


class SQLUserProfileRepository(UserProfileRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, user_id: str) -> dict[str, Any] | None:
        result = await self._s.execute(select(UserProfileORM).where(UserProfileORM.id == user_id))
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {
            "id": row.id,
            "email": row.email,
            "display_name": row.display_name,
            "base_currency": row.base_currency,
            "date_of_birth": row.date_of_birth.isoformat() if row.date_of_birth else None,
            "dependents_count": row.dependents_count,
            "employment_status": row.employment_status,
            "residency_status": row.residency_status,
            "employer": row.employer,
            "employment_type": row.employment_type,
            "ird_number": row.ird_number,
            "risk_score": row.risk_score,
            "risk_category": row.risk_category,
            "life_stage": row.life_stage,
            "mcp_enabled": row.mcp_enabled,
            "daily_briefing_enabled": row.daily_briefing_enabled,
            "preferred_model": row.preferred_model,
        }

    async def upsert(self, user_id: str, fields: dict[str, Any]) -> None:
        result = await self._s.execute(select(UserProfileORM).where(UserProfileORM.id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            if not fields.get("base_currency"):
                # Only ensure_user creates a profile (with its currency); any
                # other write to a missing one is a missing profile.
                raise ProfileMissing(user_id)
            row = UserProfileORM(id=user_id)
            self._s.add(row)
        for k, v in fields.items():
            if hasattr(row, k) and v is not None:
                setattr(row, k, v)
        await self._s.flush()

    async def base_currency(self, user_id: str) -> str:
        result = await self._s.execute(
            select(UserProfileORM.base_currency).where(UserProfileORM.id == user_id)
        )
        base = result.scalar_one_or_none()
        if base is None:
            raise ProfileMissing(user_id)
        return base

    async def has_financial_data(self, user_id: str) -> bool:
        """Whether anything is stored in the user's base currency yet.

        True as soon as there is a single account, entry, or money-bearing
        record. Changing the base currency after that would reinterpret every
        stored amount, so it is only allowed while this is False.
        """
        for orm in (
            AccountORM,
            JournalEntryORM,
            BudgetORM,
            DebtORM,
            HoldingORM,
            RecurringSubscriptionORM,
            PolicyORM,
            InsuranceTargetORM,
            GoalORM,
            StatementORM,
        ):
            found = await self._s.execute(select(orm.id).where(orm.user_id == user_id).limit(1))
            if found.first() is not None:
                return True
        return False

    async def set_flag(self, user_id: str, field: str, value: bool) -> None:
        """Set a boolean profile flag, including to False.

        `upsert` skips None but also cannot express "set this to False" for a
        caller that builds its dict dynamically, and a toggle has to be able to
        turn off. Restricted to a known field list so this can't become a
        general-purpose arbitrary-column setter.
        """
        if field not in ("mcp_enabled", "daily_briefing_enabled"):
            raise ValueError(f"'{field}' is not a togglable profile flag")
        result = await self._s.execute(select(UserProfileORM).where(UserProfileORM.id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            raise ProfileMissing(user_id)
        setattr(row, field, value)
        await self._s.flush()

    async def set_preference(self, user_id: str, field: str, value: str | None) -> None:
        """Set a nullable string preference, including back to NULL.

        `upsert` skips None values, so it can set a preference but never clear
        one — "use the default model again" would be inexpressible through it.
        `set_flag` is the same escape hatch for booleans; this is its string
        sibling, allowlisted for the same reason: so it cannot quietly become a
        way to write any column from a request body.
        """
        if field not in ("preferred_model",):
            raise ValueError(f"'{field}' is not a settable profile preference")
        result = await self._s.execute(select(UserProfileORM).where(UserProfileORM.id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            raise ProfileMissing(user_id)
        setattr(row, field, value)
        await self._s.flush()

    async def get_ai_settings(self, user_id: str) -> dict[str, Any]:
        result = await self._s.execute(
            select(UserProfileORM.ai_provider, UserProfileORM.ai_models).where(
                UserProfileORM.id == user_id
            )
        )
        row = result.first()
        if row is None:
            return {"provider": None, "models": {}}
        return {"provider": row[0], "models": dict(row[1] or {})}

    async def set_ai_settings(
        self, user_id: str, *, provider: str | None, models: dict[str, Any]
    ) -> None:
        result = await self._s.execute(select(UserProfileORM).where(UserProfileORM.id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            raise ProfileMissing(user_id)
        row.ai_provider = provider
        row.ai_models = models or None
        await self._s.flush()

    async def list_daily_briefing_optins(self) -> list[dict[str, Any]]:
        """Users who asked for the scheduled daily advisor run.

        Opt-in rather than automatic: each run is a model call made on the
        user's behalf, so it has to be something they asked for.
        """
        rows = (
            (
                await self._s.execute(
                    select(UserProfileORM).where(UserProfileORM.daily_briefing_enabled.is_(True))
                )
            )
            .scalars()
            .all()
        )
        return [{"user_id": r.id, "email": r.email} for r in rows]


def _llm_credential_to_dict(row: UserLlmCredentialORM) -> dict[str, Any]:
    return {
        "provider": row.provider,
        "ciphertext": row.ciphertext,
        # Required to decrypt — omitting it would silently default every row to
        # version 1 and break the moment a key is rotated.
        "key_version": row.key_version,
        "last4": row.last4,
        "validated_at": row.validated_at.isoformat() if row.validated_at else None,
    }


class SQLLlmCredentialRepository(LlmCredentialRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        rows = (
            (
                await self._s.execute(
                    select(UserLlmCredentialORM)
                    .where(UserLlmCredentialORM.user_id == user_id)
                    .order_by(UserLlmCredentialORM.provider)
                )
            )
            .scalars()
            .all()
        )
        return [_llm_credential_to_dict(r) for r in rows]

    async def get(self, user_id: str, provider: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(UserLlmCredentialORM).where(
                    UserLlmCredentialORM.user_id == user_id,
                    UserLlmCredentialORM.provider == provider,
                )
            )
        ).scalar_one_or_none()
        return _llm_credential_to_dict(row) if row else None

    async def upsert(
        self,
        user_id: str,
        provider: str,
        *,
        ciphertext: str,
        last4: str,
        validated_at: Any,
        key_version: int,
    ) -> None:
        row = (
            await self._s.execute(
                select(UserLlmCredentialORM).where(
                    UserLlmCredentialORM.user_id == user_id,
                    UserLlmCredentialORM.provider == provider,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = UserLlmCredentialORM(user_id=user_id, provider=provider)
            self._s.add(row)
        # Assigned unconditionally, unlike the user_profiles upsert above:
        # re-saving a key must be able to clear a stale validated_at back to None.
        row.ciphertext = ciphertext
        row.key_version = key_version
        row.last4 = last4
        row.validated_at = validated_at
        await self._s.flush()

    async def delete(self, user_id: str, provider: str) -> bool:
        result = await self._s.execute(
            delete(UserLlmCredentialORM).where(
                UserLlmCredentialORM.user_id == user_id,
                UserLlmCredentialORM.provider == provider,
            )
        )
        return bool(result.rowcount)


_AI_CONNECTION_FIELDS = frozenset(
    {"sealed", "key_version", "status", "status_detail", "expires_at", "paused_until"}
)


def _ai_connection_to_dict(row: AiConnectionORM) -> dict[str, Any]:
    return {
        "provider": row.provider,
        "sealed": row.sealed,
        "key_version": row.key_version,
        "status": row.status,
        "status_detail": row.status_detail,
        "expires_at": row.expires_at,
        "paused_until": row.paused_until,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


class SQLAiConnectionRepository(AiConnectionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    def _query(self, user_id: str, provider: str) -> Select[tuple[AiConnectionORM]]:
        return select(AiConnectionORM).where(
            AiConnectionORM.user_id == user_id, AiConnectionORM.provider == provider
        )

    async def get(self, user_id: str, provider: str) -> dict[str, Any] | None:
        row = (await self._s.execute(self._query(user_id, provider))).scalar_one_or_none()
        return _ai_connection_to_dict(row) if row else None

    async def get_for_update(self, user_id: str, provider: str) -> dict[str, Any] | None:
        # populate_existing: what the lock returns is the row as committed now,
        # never a copy this session read before it had to wait.
        query = (
            self._query(user_id, provider)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        row = (await self._s.execute(query)).scalar_one_or_none()
        return _ai_connection_to_dict(row) if row else None

    async def save(self, user_id: str, provider: str, fields: dict[str, Any]) -> bool:
        row = (
            await self._s.execute(self._query(user_id, provider).with_for_update())
        ).scalar_one_or_none()
        created = row is None
        if row is None:
            row = AiConnectionORM(user_id=user_id, provider=provider)
            self._s.add(row)
        for key, value in fields.items():
            if key not in _AI_CONNECTION_FIELDS:
                raise ValueError(f"'{key}' is not a field of an AI connection")
            setattr(row, key, value)
        await self._s.flush()
        return created

    async def update(self, user_id: str, provider: str, fields: dict[str, Any]) -> bool:
        row = (
            await self._s.execute(self._query(user_id, provider).with_for_update())
        ).scalar_one_or_none()
        if row is None:
            return False
        for key, value in fields.items():
            if key not in _AI_CONNECTION_FIELDS:
                raise ValueError(f"'{key}' is not a field of an AI connection")
            setattr(row, key, value)
        await self._s.flush()
        return True

    async def delete(self, user_id: str, provider: str) -> bool:
        result = await self._s.execute(
            delete(AiConnectionORM).where(
                AiConnectionORM.user_id == user_id, AiConnectionORM.provider == provider
            )
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]


class SQLInstanceSettingsRepository(InstanceSettingsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_or_create(self, key: str, value: str) -> str:
        from sqlalchemy.dialects.postgresql import insert

        # Insert-if-absent, then read back whatever won: two first requests
        # racing to create the value end up agreeing on one.
        await self._s.execute(
            insert(InstanceSettingORM)
            .values(key=key, value=value, created_at=datetime.now(UTC))
            .on_conflict_do_nothing(index_elements=["key"])
        )
        stored = (
            await self._s.execute(
                select(InstanceSettingORM.value).where(InstanceSettingORM.key == key)
            )
        ).scalar_one()
        return str(stored)


# ── Financial Independence repositories ──────────────────────────────────────


def _goal_to_dict(r: GoalORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "name": r.name,
        "kind": r.kind,
        "target_amount_minor": r.target_amount_minor,
        "current_amount_minor": r.current_amount_minor,
        "target_date": r.target_date,
        "priority": r.priority,
        "is_active": r.is_active,
        "extra": r.extra or {},
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


class SQLGoalRepository(GoalRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, user_id: str, goal: dict[str, Any]) -> str:
        gid = goal.get("id") or str(uuid.uuid4())
        self._s.add(
            GoalORM(
                id=gid,
                user_id=user_id,
                name=goal["name"],
                kind=goal.get("kind", "custom"),
                target_amount_minor=int(goal.get("target_amount_minor", 0)),
                current_amount_minor=int(goal.get("current_amount_minor", 0)),
                target_date=goal.get("target_date"),
                priority=int(goal.get("priority", 2)),
                is_active=goal.get("is_active", True),
                extra=goal.get("extra", {}),
            )
        )
        await self._s.flush()
        return gid

    async def get(self, user_id: str, goal_id: str) -> dict[str, Any] | None:
        r = (
            await self._s.execute(
                select(GoalORM).where(GoalORM.id == goal_id, GoalORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        return _goal_to_dict(r) if r else None

    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        stmt = select(GoalORM).where(GoalORM.user_id == user_id)
        if active_only:
            stmt = stmt.where(GoalORM.is_active == True)  # noqa: E712
        stmt = stmt.order_by(GoalORM.priority, GoalORM.created_at)
        return [_goal_to_dict(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def update(self, user_id: str, goal_id: str, updates: dict[str, Any]) -> None:
        r = (
            await self._s.execute(
                select(GoalORM).where(GoalORM.id == goal_id, GoalORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if not r:
            return
        for k in (
            "name",
            "kind",
            "target_amount_minor",
            "current_amount_minor",
            "target_date",
            "priority",
            "is_active",
            "extra",
        ):
            if k in updates and updates[k] is not None:
                setattr(r, k, updates[k])
        await self._s.flush()

    async def delete(self, user_id: str, goal_id: str) -> None:
        r = (
            await self._s.execute(
                select(GoalORM).where(GoalORM.id == goal_id, GoalORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if r:
            await self._s.delete(r)

    # ── allocations ──────────────────────────────────────────────────────────

    async def list_allocations(
        self, user_id: str, goal_id: str | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(GoalAllocationORM).where(GoalAllocationORM.user_id == user_id)
        if goal_id:
            stmt = stmt.where(GoalAllocationORM.goal_id == goal_id)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            {
                "id": r.id,
                "goal_id": r.goal_id,
                "account_id": r.account_id,
                "allocated_minor": r.allocated_minor,
            }
            for r in rows
        ]

    async def set_allocation(
        self, user_id: str, goal_id: str, account_id: str, allocated_minor: int
    ) -> None:
        """Create, update, or clear one goal's claim on one account.

        An allocation of zero removes the claim rather than storing a row that
        means nothing — otherwise "un-earmark this account" would leave a
        phantom entry in every listing.
        """
        owns = (
            await self._s.execute(
                select(GoalORM.id).where(GoalORM.id == goal_id, GoalORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if owns is None:
            raise ValueError("Goal not found")

        account = (
            await self._s.execute(
                select(AccountORM.id).where(
                    AccountORM.id == account_id, AccountORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if account is None:
            raise ValueError("Account not found")

        existing = (
            await self._s.execute(
                select(GoalAllocationORM).where(
                    GoalAllocationORM.goal_id == goal_id,
                    GoalAllocationORM.account_id == account_id,
                )
            )
        ).scalar_one_or_none()

        if allocated_minor <= 0:
            if existing:
                await self._s.delete(existing)
            return

        if existing:
            existing.allocated_minor = allocated_minor
        else:
            self._s.add(
                GoalAllocationORM(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    goal_id=goal_id,
                    account_id=account_id,
                    allocated_minor=allocated_minor,
                )
            )


class SQLFiScoreRepository(FiScoreRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, user_id: str, score: dict[str, Any]) -> str:
        sid = str(uuid.uuid4())
        self._s.add(
            FiScoreORM(
                id=sid,
                user_id=user_id,
                score=score["overall_score"],
                pack_version=score["pack_version"],
                inputs_hash=score.get("inputs_hash", ""),
                result_json=score,
            )
        )
        await self._s.flush()
        return sid

    async def get_latest(self, user_id: str) -> dict[str, Any] | None:
        r = (
            await self._s.execute(
                select(FiScoreORM)
                .where(FiScoreORM.user_id == user_id)
                .order_by(FiScoreORM.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return r.result_json if r else None

    async def history(self, user_id: str, limit: int = 90) -> list[dict[str, Any]]:
        rows = (
            (
                await self._s.execute(
                    select(FiScoreORM)
                    .where(FiScoreORM.user_id == user_id)
                    .order_by(FiScoreORM.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "score": float(r.score),
                "net_worth": r.result_json.get("net_worth"),
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]


def _report_to_dict(r: AdvisoryReportORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "trigger": r.trigger,
        "fi_score_id": r.fi_score_id,
        "summary": r.summary,
        "recommendations": r.recommendations or [],
        "created_at": r.created_at.isoformat(),
    }


class SQLAdvisoryRepository(AdvisoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, user_id: str, report: dict[str, Any]) -> str:
        rid = str(uuid.uuid4())
        self._s.add(
            AdvisoryReportORM(
                id=rid,
                user_id=user_id,
                trigger=report.get("trigger", "manual"),
                fi_score_id=report.get("fi_score_id"),
                summary=report.get("summary", ""),
                recommendations=report.get("recommendations", []),
            )
        )
        await self._s.flush()
        return rid

    async def get(self, user_id: str, report_id: str) -> dict[str, Any] | None:
        r = (
            await self._s.execute(
                select(AdvisoryReportORM).where(
                    AdvisoryReportORM.id == report_id, AdvisoryReportORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        return _report_to_dict(r) if r else None

    async def get_latest(self, user_id: str) -> dict[str, Any] | None:
        r = (
            await self._s.execute(
                select(AdvisoryReportORM)
                .where(AdvisoryReportORM.user_id == user_id)
                .order_by(AdvisoryReportORM.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return _report_to_dict(r) if r else None

    async def list(self, user_id: str, limit: int = 30) -> list[dict[str, Any]]:
        rows = (
            (
                await self._s.execute(
                    select(AdvisoryReportORM)
                    .where(AdvisoryReportORM.user_id == user_id)
                    .order_by(AdvisoryReportORM.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [_report_to_dict(r) for r in rows]

    async def update_recommendations(
        self, user_id: str, report_id: str, recommendations: list
    ) -> None:
        r = (
            await self._s.execute(
                select(AdvisoryReportORM).where(
                    AdvisoryReportORM.id == report_id, AdvisoryReportORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if r:
            r.recommendations = recommendations
            await self._s.flush()

    async def ran_today(self, user_id: str, day: str) -> bool:
        rows = (
            await self._s.execute(
                select(AdvisoryReportORM.created_at)
                .where(AdvisoryReportORM.user_id == user_id)
                .order_by(AdvisoryReportORM.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return rows is not None and rows.isoformat().startswith(day)


class SQLFireStrategyRepository(FireStrategyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_latest(self, user_id: str) -> dict[str, Any] | None:
        r = (
            await self._s.execute(
                select(FireStrategyORM)
                .where(FireStrategyORM.user_id == user_id)
                .order_by(FireStrategyORM.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if r is None:
            return None
        return {"version": r.version, "created_at": r.created_at.isoformat(), **r.strategy}

    async def save(self, user_id: str, strategy: dict[str, Any]) -> int:
        # Determine next version number
        latest = (
            await self._s.execute(
                select(FireStrategyORM.version)
                .where(FireStrategyORM.user_id == user_id)
                .order_by(FireStrategyORM.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        version = (latest or 0) + 1
        self._s.add(
            FireStrategyORM(
                id=str(uuid.uuid4()),
                user_id=user_id,
                version=version,
                strategy=strategy,
            )
        )
        await self._s.flush()
        return version

    async def get_history(self, user_id: str) -> list[dict[str, Any]]:
        rows = (
            (
                await self._s.execute(
                    select(FireStrategyORM)
                    .where(FireStrategyORM.user_id == user_id)
                    .order_by(FireStrategyORM.version.desc())
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "version": r.version,
                "created_at": r.created_at.isoformat(),
                "fire_style": r.strategy.get("fire_style"),
                "theories_applied": r.strategy.get("theories_applied", []),
            }
            for r in rows
        ]


# ── Budget repository ─────────────────────────────────────────────────────────


def _budget_to_dict(r: BudgetORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "period_start": r.period_start,
        "period_end": r.period_end,
        "lines": r.lines or [],
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


class SQLBudgetRepository(BudgetRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, user_id: str, budget: dict[str, Any]) -> str:
        bid = budget.get("id") or str(uuid.uuid4())
        self._s.add(
            BudgetORM(
                id=bid,
                user_id=user_id,
                period_start=budget["period_start"],
                period_end=budget["period_end"],
                lines=budget.get("lines", []),
            )
        )
        await self._s.flush()
        return bid

    async def get(self, user_id: str, budget_id: str) -> dict[str, Any] | None:
        r = (
            await self._s.execute(
                select(BudgetORM).where(BudgetORM.id == budget_id, BudgetORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        return _budget_to_dict(r) if r else None

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(BudgetORM)
            .where(BudgetORM.user_id == user_id)
            .order_by(BudgetORM.period_start.desc())
        )
        return [_budget_to_dict(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def update(self, user_id: str, budget_id: str, updates: dict[str, Any]) -> None:
        r = (
            await self._s.execute(
                select(BudgetORM).where(BudgetORM.id == budget_id, BudgetORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if not r:
            return
        for k in ("period_start", "period_end", "lines"):
            if k in updates and updates[k] is not None:
                setattr(r, k, updates[k])
        await self._s.flush()

    async def delete(self, user_id: str, budget_id: str) -> None:
        r = (
            await self._s.execute(
                select(BudgetORM).where(BudgetORM.id == budget_id, BudgetORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if r:
            await self._s.delete(r)


# ── Debt repository ───────────────────────────────────────────────────────────


def _debt_to_dict(r: DebtORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "name": r.name,
        "principal_minor": r.principal_minor,
        "apr": str(r.apr),
        "minimum_payment_minor": r.minimum_payment_minor,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


class SQLDebtRepository(DebtRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, user_id: str, debt: dict[str, Any]) -> str:
        did = debt.get("id") or str(uuid.uuid4())
        self._s.add(
            DebtORM(
                id=did,
                user_id=user_id,
                name=debt["name"],
                principal_minor=int(debt["principal_minor"]),
                apr=debt["apr"],
                minimum_payment_minor=int(debt["minimum_payment_minor"]),
                is_active=debt.get("is_active", True),
            )
        )
        await self._s.flush()
        return did

    async def get(self, user_id: str, debt_id: str) -> dict[str, Any] | None:
        r = (
            await self._s.execute(
                select(DebtORM).where(DebtORM.id == debt_id, DebtORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        return _debt_to_dict(r) if r else None

    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        stmt = select(DebtORM).where(DebtORM.user_id == user_id)
        if active_only:
            stmt = stmt.where(DebtORM.is_active == True)  # noqa: E712
        stmt = stmt.order_by(DebtORM.created_at)
        return [_debt_to_dict(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def update(self, user_id: str, debt_id: str, updates: dict[str, Any]) -> None:
        r = (
            await self._s.execute(
                select(DebtORM).where(DebtORM.id == debt_id, DebtORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if not r:
            return
        for k in ("name", "principal_minor", "apr", "minimum_payment_minor", "is_active"):
            if k in updates and updates[k] is not None:
                setattr(r, k, updates[k])
        await self._s.flush()

    async def delete(self, user_id: str, debt_id: str) -> None:
        r = (
            await self._s.execute(
                select(DebtORM).where(DebtORM.id == debt_id, DebtORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if r:
            await self._s.delete(r)


# ── Portfolio repository ──────────────────────────────────────────────────────


def _holding_to_dict(r: HoldingORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "symbol": r.symbol,
        "name": r.name,
        "asset_class": r.asset_class,
        "cost_basis_minor": r.cost_basis_minor,
        "current_value_minor": r.current_value_minor,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


class SQLPortfolioRepository(PortfolioRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, user_id: str, holding: dict[str, Any]) -> str:
        hid = holding.get("id") or str(uuid.uuid4())
        self._s.add(
            HoldingORM(
                id=hid,
                user_id=user_id,
                symbol=holding["symbol"],
                name=holding["name"],
                asset_class=holding["asset_class"],
                cost_basis_minor=int(holding["cost_basis_minor"]),
                current_value_minor=int(holding["current_value_minor"]),
                is_active=holding.get("is_active", True),
            )
        )
        await self._s.flush()
        return hid

    async def get(self, user_id: str, holding_id: str) -> dict[str, Any] | None:
        r = (
            await self._s.execute(
                select(HoldingORM).where(HoldingORM.id == holding_id, HoldingORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        return _holding_to_dict(r) if r else None

    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        stmt = select(HoldingORM).where(HoldingORM.user_id == user_id)
        if active_only:
            stmt = stmt.where(HoldingORM.is_active == True)  # noqa: E712
        stmt = stmt.order_by(HoldingORM.created_at)
        return [_holding_to_dict(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def update(self, user_id: str, holding_id: str, updates: dict[str, Any]) -> None:
        r = (
            await self._s.execute(
                select(HoldingORM).where(HoldingORM.id == holding_id, HoldingORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if not r:
            return
        for k in (
            "symbol",
            "name",
            "asset_class",
            "cost_basis_minor",
            "current_value_minor",
            "is_active",
        ):
            if k in updates and updates[k] is not None:
                setattr(r, k, updates[k])
        await self._s.flush()

    async def delete(self, user_id: str, holding_id: str) -> None:
        r = (
            await self._s.execute(
                select(HoldingORM).where(HoldingORM.id == holding_id, HoldingORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if r:
            await self._s.delete(r)


# ── Recurring subscription repository ─────────────────────────────────────────


def _recurring_subscription_to_dict(r: RecurringSubscriptionORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "name": r.name,
        "amount_minor": r.amount_minor,
        "frequency": r.frequency,
        "next_due_date": r.next_due_date,
        "account_id": r.account_id,
        "grace_days": r.grace_days,
        "amount_tolerance_pct": str(r.amount_tolerance_pct),
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


class SQLRecurringSubscriptionRepository(RecurringSubscriptionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, user_id: str, subscription: dict[str, Any]) -> str:
        sid = subscription.get("id") or str(uuid.uuid4())
        self._s.add(
            RecurringSubscriptionORM(
                id=sid,
                user_id=user_id,
                name=subscription["name"],
                amount_minor=int(subscription["amount_minor"]),
                frequency=subscription["frequency"],
                next_due_date=subscription["next_due_date"],
                account_id=subscription.get("account_id"),
                grace_days=subscription.get("grace_days", 5),
                amount_tolerance_pct=subscription.get("amount_tolerance_pct", 0.05),
                is_active=subscription.get("is_active", True),
            )
        )
        await self._s.flush()
        return sid

    async def get(self, user_id: str, subscription_id: str) -> dict[str, Any] | None:
        r = (
            await self._s.execute(
                select(RecurringSubscriptionORM).where(
                    RecurringSubscriptionORM.id == subscription_id,
                    RecurringSubscriptionORM.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        return _recurring_subscription_to_dict(r) if r else None

    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        stmt = select(RecurringSubscriptionORM).where(RecurringSubscriptionORM.user_id == user_id)
        if active_only:
            stmt = stmt.where(RecurringSubscriptionORM.is_active == True)  # noqa: E712
        stmt = stmt.order_by(RecurringSubscriptionORM.created_at)
        return [
            _recurring_subscription_to_dict(r)
            for r in (await self._s.execute(stmt)).scalars().all()
        ]

    async def update(self, user_id: str, subscription_id: str, updates: dict[str, Any]) -> None:
        r = (
            await self._s.execute(
                select(RecurringSubscriptionORM).where(
                    RecurringSubscriptionORM.id == subscription_id,
                    RecurringSubscriptionORM.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if not r:
            return
        for k in (
            "name",
            "amount_minor",
            "frequency",
            "next_due_date",
            "account_id",
            "grace_days",
            "amount_tolerance_pct",
            "is_active",
        ):
            if k in updates and updates[k] is not None:
                setattr(r, k, updates[k])
        await self._s.flush()

    async def delete(self, user_id: str, subscription_id: str) -> None:
        r = (
            await self._s.execute(
                select(RecurringSubscriptionORM).where(
                    RecurringSubscriptionORM.id == subscription_id,
                    RecurringSubscriptionORM.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if r:
            await self._s.delete(r)


# ── Insurance repositories ─────────────────────────────────────────────────────


def _policy_to_dict(r: PolicyORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "name": r.name,
        "policy_type": r.policy_type,
        "provider": r.provider,
        "coverage_amount_minor": r.coverage_amount_minor,
        "premium_amount_minor": r.premium_amount_minor,
        "premium_frequency": r.premium_frequency,
        "expiry_date": r.expiry_date,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


class SQLPolicyRepository(PolicyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, user_id: str, policy: dict[str, Any]) -> str:
        pid = policy.get("id") or str(uuid.uuid4())
        self._s.add(
            PolicyORM(
                id=pid,
                user_id=user_id,
                name=policy["name"],
                policy_type=policy["policy_type"],
                provider=policy["provider"],
                coverage_amount_minor=int(policy["coverage_amount_minor"]),
                premium_amount_minor=int(policy["premium_amount_minor"]),
                premium_frequency=policy["premium_frequency"],
                expiry_date=policy["expiry_date"],
                is_active=policy.get("is_active", True),
            )
        )
        await self._s.flush()
        return pid

    async def get(self, user_id: str, policy_id: str) -> dict[str, Any] | None:
        r = (
            await self._s.execute(
                select(PolicyORM).where(PolicyORM.id == policy_id, PolicyORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        return _policy_to_dict(r) if r else None

    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        stmt = select(PolicyORM).where(PolicyORM.user_id == user_id)
        if active_only:
            stmt = stmt.where(PolicyORM.is_active == True)  # noqa: E712
        stmt = stmt.order_by(PolicyORM.created_at)
        return [_policy_to_dict(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def update(self, user_id: str, policy_id: str, updates: dict[str, Any]) -> None:
        r = (
            await self._s.execute(
                select(PolicyORM).where(PolicyORM.id == policy_id, PolicyORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if not r:
            return
        for k in (
            "name",
            "policy_type",
            "provider",
            "coverage_amount_minor",
            "premium_amount_minor",
            "premium_frequency",
            "expiry_date",
            "is_active",
        ):
            if k in updates and updates[k] is not None:
                setattr(r, k, updates[k])
        await self._s.flush()

    async def delete(self, user_id: str, policy_id: str) -> None:
        r = (
            await self._s.execute(
                select(PolicyORM).where(PolicyORM.id == policy_id, PolicyORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if r:
            await self._s.delete(r)


def _insurance_target_to_dict(r: InsuranceTargetORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "policy_type": r.policy_type,
        "target_amount_minor": r.target_amount_minor,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


class SQLInsuranceTargetRepository(InsuranceTargetRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert(self, user_id: str, policy_type: str, target_amount_minor: int) -> str:
        r = (
            await self._s.execute(
                select(InsuranceTargetORM).where(
                    InsuranceTargetORM.user_id == user_id,
                    InsuranceTargetORM.policy_type == policy_type,
                )
            )
        ).scalar_one_or_none()
        if r:
            r.target_amount_minor = target_amount_minor
            await self._s.flush()
            return r.id
        tid = str(uuid.uuid4())
        self._s.add(
            InsuranceTargetORM(
                id=tid,
                user_id=user_id,
                policy_type=policy_type,
                target_amount_minor=target_amount_minor,
            )
        )
        await self._s.flush()
        return tid

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        stmt = select(InsuranceTargetORM).where(InsuranceTargetORM.user_id == user_id)
        return [_insurance_target_to_dict(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def delete(self, user_id: str, policy_type: str) -> None:
        r = (
            await self._s.execute(
                select(InsuranceTargetORM).where(
                    InsuranceTargetORM.user_id == user_id,
                    InsuranceTargetORM.policy_type == policy_type,
                )
            )
        ).scalar_one_or_none()
        if r:
            await self._s.delete(r)


# ── Audit log repository ──────────────────────────────────────────────────────


def _audit_log_to_dict(r: AuditLogORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "action": r.action,
        "params": r.params,
        "decision": r.decision,
        "created_at": r.created_at.isoformat(),
    }


class SQLAuditLogRepository(AuditLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def log(self, user_id: str, action: str, params: dict[str, Any], decision: str) -> str:
        log_id = str(uuid.uuid4())
        self._s.add(
            AuditLogORM(
                id=log_id,
                user_id=user_id,
                action=action,
                params=params,
                decision=decision,
            )
        )
        await self._s.flush()
        return log_id

    async def list(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        stmt = (
            select(AuditLogORM)
            .where(AuditLogORM.user_id == user_id)
            .order_by(AuditLogORM.created_at.desc())
            .limit(limit)
        )
        return [_audit_log_to_dict(r) for r in (await self._s.execute(stmt)).scalars().all()]


# ── Data portability repository ───────────────────────────────────────────────


class SQLDataPortabilityRepository(DataPortabilityRepository):
    """Permanently deletes every row belonging to a user, across every
    user-scoped table. Deletion order is constraint-driven, not arbitrary —
    see the inline comments for exactly which foreign keys force which order."""

    def __init__(self, session: AsyncSession, purgers: Sequence[UserDataPurger] = ()) -> None:
        self._s = session
        # Extensions' own per-user tables (salli/extensions.py). Run in this
        # same session, so a failure in one rolls back the whole deletion.
        self._purgers = purgers

    async def delete_all(self, user_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}

        async def _delete(model: Any, column: Any) -> None:
            result = await self._s.execute(delete(model).where(column == user_id))
            counts[model.__tablename__] = result.rowcount or 0  # type: ignore[attr-defined]

        # parsed_transactions.posted_entry_id -> journal_entries.id has no
        # ondelete cascade, so it must be gone before journal_entries. It has
        # no user_id column of its own — scoped via its parent statement.
        result = await self._s.execute(
            delete(ParsedTransactionORM).where(
                ParsedTransactionORM.statement_id.in_(
                    select(StatementORM.id).where(StatementORM.user_id == user_id)
                )
            )
        )
        counts["parsed_transactions"] = result.rowcount or 0  # type: ignore[attr-defined]

        # recurring_subscriptions.account_id -> accounts.id has no ondelete
        # cascade either, so it must be gone before accounts.
        await _delete(RecurringSubscriptionORM, RecurringSubscriptionORM.user_id)

        # journal_entries cascade-deletes their own postings (ondelete="CASCADE"
        # on postings.entry_id); statements cascade-deletes parsed_transactions
        # the same way (already emptied above, so that cascade is a no-op —
        # harmless). Both must still go before accounts.
        await _delete(JournalEntryORM, JournalEntryORM.user_id)
        await _delete(StatementORM, StatementORM.user_id)
        await _delete(AccountORM, AccountORM.user_id)

        # posting_tags has no user_id of its own — it cascades from postings,
        # which cascade from journal_entries above. `tags` does carry a user_id
        # and would otherwise survive account deletion, so it is deleted here.
        await _delete(TagORM, TagORM.user_id)

        # Everything else has no FK ordering dependency on the tables above.
        await _delete(DocumentORM, DocumentORM.user_id)
        await _delete(AgentDocumentORM, AgentDocumentORM.user_id)
        await _delete(AgentSessionORM, AgentSessionORM.user_id)
        await _delete(ReminderORM, ReminderORM.user_id)
        await _delete(UserLlmCredentialORM, UserLlmCredentialORM.user_id)
        # Sealed ChatGPT tokens, the second place a user's AI credential lives.
        await _delete(AiConnectionORM, AiConnectionORM.user_id)
        # Allocations cascade from both fi_goals and accounts, but both of
        # those are deleted in this same sweep and a cascade only fires if the
        # parent row is still there to cascade from — so delete them explicitly
        # and first.
        await _delete(GoalAllocationORM, GoalAllocationORM.user_id)
        await _delete(GoalORM, GoalORM.user_id)
        await _delete(FiScoreORM, FiScoreORM.user_id)
        await _delete(FireStrategyORM, FireStrategyORM.user_id)
        await _delete(AdvisoryReportORM, AdvisoryReportORM.user_id)
        await _delete(BudgetORM, BudgetORM.user_id)
        await _delete(DebtORM, DebtORM.user_id)
        await _delete(HoldingORM, HoldingORM.user_id)
        await _delete(PolicyORM, PolicyORM.user_id)
        await _delete(InsuranceTargetORM, InsuranceTargetORM.user_id)
        await _delete(TaxComputationORM, TaxComputationORM.user_id)
        await _delete(AuditLogORM, AuditLogORM.user_id)
        await _delete(OAuthRefreshTokenORM, OAuthRefreshTokenORM.user_id)
        await _delete(OAuthAccessTokenORM, OAuthAccessTokenORM.user_id)
        await _delete(OAuthAuthorizationCodeORM, OAuthAuthorizationCodeORM.user_id)
        await _delete(OAuthDeviceCodeORM, OAuthDeviceCodeORM.user_id)
        await _delete(PersonalAccessTokenORM, PersonalAccessTokenORM.user_id)
        await _delete(CategorizationRuleORM, CategorizationRuleORM.user_id)
        await _delete(BankConnectionAccountORM, BankConnectionAccountORM.user_id)
        await _delete(BankConnectionORM, BankConnectionORM.user_id)

        # Extensions' tables have no foreign keys into Salli's, so they can go
        # at any point before the profile row.
        for purge in self._purgers:
            counts.update(await purge(self._s, user_id))

        # UserProfileORM's primary key IS the user id — no separate user_id
        # column — and nothing else has an FK pointing at it, so it's safe last.
        await _delete(UserProfileORM, UserProfileORM.id)

        return counts


# ── MCP OAuth ────────────────────────────────────────────────────────────────


class SQLOAuthClientRepository(OAuthClientRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def register(self, client_name: str | None, redirect_uris: list[str]) -> dict[str, Any]:
        client_id = str(uuid.uuid4())
        row = OAuthClientORM(
            client_id=client_id, client_name=client_name, redirect_uris=redirect_uris
        )
        self._s.add(row)
        await self._s.flush()
        return {
            "client_id": row.client_id,
            "client_name": row.client_name,
            "redirect_uris": row.redirect_uris,
        }

    async def get(self, client_id: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(OAuthClientORM).where(OAuthClientORM.client_id == client_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "client_id": row.client_id,
            "client_name": row.client_name,
            "redirect_uris": row.redirect_uris,
        }


class SQLOAuthTokenRepository(OAuthTokenRepository):
    """Access/refresh tokens are looked up by hash — callers never store or
    pass the plaintext token after issuance."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save_authorization_code(
        self,
        code: str,
        client_id: str,
        user_id: str,
        redirect_uri: str,
        code_challenge: str,
        scope: str,
        resource: str | None,
        expires_at: datetime,
    ) -> None:
        self._s.add(
            OAuthAuthorizationCodeORM(
                code=code,
                client_id=client_id,
                user_id=user_id,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                resource=resource,
                scope=scope,
                expires_at=expires_at,
            )
        )
        await self._s.flush()

    async def get_authorization_code(self, code: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(OAuthAuthorizationCodeORM).where(OAuthAuthorizationCodeORM.code == code)
            )
        ).scalar_one_or_none()
        if row is None or row.expires_at < datetime.now(UTC):
            return None
        return {
            "client_id": row.client_id,
            "user_id": row.user_id,
            "redirect_uri": row.redirect_uri,
            "code_challenge": row.code_challenge,
            "resource": row.resource,
            "scope": row.scope,
            "expires_at": row.expires_at,
        }

    async def delete_authorization_code(self, code: str) -> None:
        await self._s.execute(
            delete(OAuthAuthorizationCodeORM).where(OAuthAuthorizationCodeORM.code == code)
        )
        await self._s.flush()

    async def save_access_token(
        self,
        token_hash: str,
        client_id: str,
        user_id: str,
        scope: str,
        resource: str | None,
        expires_at: datetime,
    ) -> str:
        token_id = str(uuid.uuid4())
        self._s.add(
            OAuthAccessTokenORM(
                id=token_id,
                token_hash=token_hash,
                client_id=client_id,
                user_id=user_id,
                scope=scope,
                resource=resource,
                expires_at=expires_at,
            )
        )
        await self._s.flush()
        return token_id

    async def save_refresh_token(
        self,
        token_hash: str,
        access_token_id: str,
        client_id: str,
        user_id: str,
        scope: str,
        resource: str | None,
        expires_at: datetime,
    ) -> None:
        self._s.add(
            OAuthRefreshTokenORM(
                token_hash=token_hash,
                access_token_id=access_token_id,
                client_id=client_id,
                user_id=user_id,
                scope=scope,
                resource=resource,
                expires_at=expires_at,
            )
        )
        await self._s.flush()

    async def get_access_token(self, token_hash: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(OAuthAccessTokenORM).where(OAuthAccessTokenORM.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if row is None or row.revoked_at is not None or row.expires_at < datetime.now(UTC):
            return None
        return {
            "id": row.id,
            "client_id": row.client_id,
            "user_id": row.user_id,
            "scope": row.scope,
            "resource": row.resource,
            "expires_at": row.expires_at,
        }

    async def get_refresh_token(self, token_hash: str) -> dict[str, Any] | None:
        found = (
            await self._s.execute(
                select(OAuthRefreshTokenORM, OAuthAccessTokenORM.revoked_at)
                .join(
                    OAuthAccessTokenORM,
                    OAuthAccessTokenORM.id == OAuthRefreshTokenORM.access_token_id,
                )
                .where(OAuthRefreshTokenORM.token_hash == token_hash)
            )
        ).one_or_none()
        if found is None:
            return None
        row, access_revoked_at = found
        # A refresh token dies with the access token it was issued with: a
        # revoked pair (a disconnected client, a revoked access token) must
        # not be able to mint a new one.
        if (
            row.revoked_at is not None
            or access_revoked_at is not None
            or row.expires_at < datetime.now(UTC)
        ):
            return None
        return {
            "id": row.id,
            "access_token_id": row.access_token_id,
            "client_id": row.client_id,
            "user_id": row.user_id,
            "scope": row.scope,
            "resource": row.resource,
            "expires_at": row.expires_at,
        }

    async def revoke_access_token(self, token_id: str, user_id: str) -> bool:
        row = (
            await self._s.execute(
                select(OAuthAccessTokenORM).where(
                    OAuthAccessTokenORM.id == token_id, OAuthAccessTokenORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if row is None or row.revoked_at is not None:
            return False
        row.revoked_at = datetime.now(UTC)
        await self._s.flush()
        return True

    async def revoke_refresh_token(self, token_hash: str) -> None:
        row = (
            await self._s.execute(
                select(OAuthRefreshTokenORM).where(OAuthRefreshTokenORM.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            await self._s.flush()

    async def token_exists(self, token_hash: str) -> bool:
        for model in (OAuthAccessTokenORM, OAuthRefreshTokenORM):
            found = (
                await self._s.execute(select(model.id).where(model.token_hash == token_hash))
            ).first()
            if found is not None:
                return True
        return False

    async def get_access_token_by_id(self, token_id: str, user_id: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(OAuthAccessTokenORM).where(
                    OAuthAccessTokenORM.id == token_id, OAuthAccessTokenORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "client_id": row.client_id,
            "user_id": row.user_id,
            "scope": row.scope,
            "resource": row.resource,
            "expires_at": row.expires_at,
            "revoked_at": row.revoked_at,
        }

    async def revoke_client_grant(self, user_id: str, client_id: str, resource: str | None) -> int:
        now = datetime.now(UTC)
        revoked = 0
        for model in (OAuthAccessTokenORM, OAuthRefreshTokenORM):
            same_resource = (
                model.resource.is_(None) if resource is None else model.resource == resource
            )
            result = await self._s.execute(
                update(model)
                .where(
                    model.user_id == user_id,
                    model.client_id == client_id,
                    same_resource,
                    model.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            revoked += cast(Any, result).rowcount or 0
        await self._s.flush()
        return revoked

    async def list_active_connections(
        self, user_id: str, resource: str | None = None
    ) -> list[McpConnectionRow]:
        now = datetime.now(UTC)
        access_stmt = (
            select(OAuthAccessTokenORM, OAuthClientORM)
            .join(OAuthClientORM, OAuthClientORM.client_id == OAuthAccessTokenORM.client_id)
            .where(
                OAuthAccessTokenORM.user_id == user_id,
                OAuthAccessTokenORM.revoked_at.is_(None),
                OAuthAccessTokenORM.expires_at > now,
            )
        )
        # A client whose access token has run out is still connected while its
        # refresh token lives: it will be back with it.
        refresh_stmt = (
            select(OAuthRefreshTokenORM, OAuthAccessTokenORM, OAuthClientORM)
            .join(
                OAuthAccessTokenORM,
                OAuthAccessTokenORM.id == OAuthRefreshTokenORM.access_token_id,
            )
            .join(OAuthClientORM, OAuthClientORM.client_id == OAuthRefreshTokenORM.client_id)
            .where(
                OAuthRefreshTokenORM.user_id == user_id,
                OAuthRefreshTokenORM.revoked_at.is_(None),
                OAuthRefreshTokenORM.expires_at > now,
                OAuthAccessTokenORM.revoked_at.is_(None),
            )
        )
        if resource is not None:
            access_stmt = access_stmt.where(OAuthAccessTokenORM.resource == resource)
            refresh_stmt = refresh_stmt.where(OAuthRefreshTokenORM.resource == resource)
        live: list[tuple[OAuthAccessTokenORM, OAuthClientORM]] = [
            (token, client) for token, client in (await self._s.execute(access_stmt)).all()
        ]
        live += [
            (access, client) for _, access, client in (await self._s.execute(refresh_stmt)).all()
        ]

        # One connection per client grant (client, audience): rotation leaves
        # several live tokens for one client, and they are one connection.
        grants: dict[tuple[str, str | None], McpConnectionRow] = {}
        for token, client in sorted(live, key=lambda pair: pair[0].created_at, reverse=True):
            key = (token.client_id, token.resource)
            grant = grants.get(key)
            if grant is None:
                grants[key] = {
                    # The newest token's id: what revoking the connection takes.
                    "token_id": token.id,
                    "client_id": client.client_id,
                    "client_name": client.client_name or "Unnamed app",
                    "scope": token.scope,
                    # Which audience it was issued for: an AI client (MCP) or
                    # the user's own CLI (the API).
                    "resource": token.resource,
                    "connected_at": token.created_at,
                }
            else:
                grant["connected_at"] = min(grant["connected_at"], token.created_at)
        return list(grants.values())

    async def save_device_code(
        self,
        device_code_hash: str,
        user_code: str,
        client_id: str,
        scope: str,
        resource: str | None,
        interval_seconds: int,
        expires_at: datetime,
    ) -> None:
        self._s.add(
            OAuthDeviceCodeORM(
                device_code_hash=device_code_hash,
                user_code=user_code,
                client_id=client_id,
                scope=scope,
                resource=resource,
                status="pending",
                interval_seconds=interval_seconds,
                expires_at=expires_at,
            )
        )
        await self._s.flush()

    @staticmethod
    def _device(row: OAuthDeviceCodeORM) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_code": row.user_code,
            "client_id": row.client_id,
            "scope": row.scope,
            "resource": row.resource,
            "status": row.status,
            "user_id": row.user_id,
            "interval_seconds": row.interval_seconds,
            "last_polled_at": row.last_polled_at,
            "expires_at": row.expires_at,
        }

    async def get_device_code(self, device_code_hash: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(OAuthDeviceCodeORM).where(
                    OAuthDeviceCodeORM.device_code_hash == device_code_hash
                )
            )
        ).scalar_one_or_none()
        return self._device(row) if row else None

    async def get_device_code_by_user_code(self, user_code: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(OAuthDeviceCodeORM).where(
                    OAuthDeviceCodeORM.user_code == user_code,
                    OAuthDeviceCodeORM.status == "pending",
                    OAuthDeviceCodeORM.expires_at > datetime.now(UTC),
                )
            )
        ).scalar_one_or_none()
        return self._device(row) if row else None

    async def update_device_code(self, device_id: str, **fields: Any) -> None:
        row = (
            await self._s.execute(
                select(OAuthDeviceCodeORM).where(OAuthDeviceCodeORM.id == device_id)
            )
        ).scalar_one()
        for key in ("status", "user_id", "last_polled_at"):
            if key in fields:
                setattr(row, key, fields[key])
        await self._s.flush()


class SQLPersonalAccessTokenRepository(PersonalAccessTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @staticmethod
    def _row(row: PersonalAccessTokenORM) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "name": row.name,
            "prefix": row.prefix,
            "expires_at": row.expires_at,
            "last_used_at": row.last_used_at,
            "created_at": row.created_at,
        }

    async def create(
        self,
        user_id: str,
        name: str,
        token_hash: str,
        prefix: str,
        expires_at: datetime | None,
    ) -> dict[str, Any]:
        row = PersonalAccessTokenORM(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            token_hash=token_hash,
            prefix=prefix,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )
        self._s.add(row)
        await self._s.flush()
        return self._row(row)

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        rows = (
            await self._s.execute(
                select(PersonalAccessTokenORM)
                .where(
                    PersonalAccessTokenORM.user_id == user_id,
                    PersonalAccessTokenORM.revoked_at.is_(None),
                )
                .order_by(PersonalAccessTokenORM.created_at.desc())
            )
        ).scalars()
        return [self._row(r) for r in rows]

    async def get_active(self, token_hash: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(PersonalAccessTokenORM).where(
                    PersonalAccessTokenORM.token_hash == token_hash,
                    PersonalAccessTokenORM.revoked_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None or (row.expires_at is not None and row.expires_at < datetime.now(UTC)):
            return None
        return self._row(row)

    async def revoke(self, user_id: str, token_id: str) -> bool:
        row = (
            await self._s.execute(
                select(PersonalAccessTokenORM).where(
                    PersonalAccessTokenORM.id == token_id,
                    PersonalAccessTokenORM.user_id == user_id,
                    PersonalAccessTokenORM.revoked_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        row.revoked_at = datetime.now(UTC)
        await self._s.flush()
        return True

    async def touch(self, token_id: str, at: datetime) -> None:
        row = (
            await self._s.execute(
                select(PersonalAccessTokenORM).where(PersonalAccessTokenORM.id == token_id)
            )
        ).scalar_one_or_none()
        if row is not None:
            row.last_used_at = at
            await self._s.flush()


class SQLRuleRepository(RuleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @staticmethod
    def _row(row: CategorizationRuleORM) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "priority": row.priority,
            "match_all": row.match_all,
            "conditions": row.conditions,
            "actions": row.actions,
            "enabled": row.enabled,
            "hits": row.hits,
            "last_hit_at": row.last_hit_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    async def _one(self, user_id: str, rule_id: str) -> CategorizationRuleORM | None:
        return (
            await self._s.execute(
                select(CategorizationRuleORM).where(
                    CategorizationRuleORM.id == rule_id, CategorizationRuleORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        rows = (
            await self._s.execute(
                select(CategorizationRuleORM)
                .where(CategorizationRuleORM.user_id == user_id)
                .order_by(CategorizationRuleORM.priority, CategorizationRuleORM.name)
            )
        ).scalars()
        return [self._row(r) for r in rows]

    async def get(self, user_id: str, rule_id: str) -> dict[str, Any] | None:
        row = await self._one(user_id, rule_id)
        return self._row(row) if row else None

    async def save(self, user_id: str, rule: dict[str, Any]) -> str:
        now = datetime.now(UTC)
        row = CategorizationRuleORM(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=rule["name"],
            priority=rule["priority"],
            match_all=rule["match_all"],
            conditions=rule["conditions"],
            actions=rule["actions"],
            enabled=rule["enabled"],
            hits=0,
            created_at=now,
            updated_at=now,
        )
        self._s.add(row)
        await self._s.flush()
        return row.id

    async def update(self, user_id: str, rule_id: str, fields: dict[str, Any]) -> bool:
        row = await self._one(user_id, rule_id)
        if row is None:
            return False
        for key in ("name", "priority", "match_all", "conditions", "actions", "enabled"):
            if key in fields:
                setattr(row, key, fields[key])
        row.updated_at = datetime.now(UTC)
        await self._s.flush()
        return True

    async def delete(self, user_id: str, rule_id: str) -> bool:
        row = await self._one(user_id, rule_id)
        if row is None:
            return False
        await self._s.delete(row)
        await self._s.flush()
        return True

    async def record_hits(self, user_id: str, counts: dict[str, int], at: datetime) -> None:
        for rule_id, count in counts.items():
            row = await self._one(user_id, rule_id)
            if row is not None:
                row.hits += count
                row.last_hit_at = at
        await self._s.flush()


class SQLBankConnectionRepository(BankConnectionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_due(
        self, attempted_before: datetime, failed_before: datetime, now: datetime
    ) -> list[tuple[str, str]]:
        rows = await self._s.execute(
            select(BankConnectionORM.user_id, BankConnectionORM.id)
            .where(
                or_(
                    BankConnectionORM.last_attempt_at.is_(None),
                    BankConnectionORM.last_attempt_at < attempted_before,
                ),
                # A connection whose last attempt failed is retried once a day.
                or_(
                    BankConnectionORM.status != "error",
                    BankConnectionORM.last_attempt_at.is_(None),
                    BankConnectionORM.last_attempt_at < failed_before,
                ),
                or_(
                    BankConnectionORM.sync_claimed_until.is_(None),
                    BankConnectionORM.sync_claimed_until < now,
                ),
            )
            .order_by(BankConnectionORM.last_attempt_at.asc().nulls_first())
        )
        return [(user_id, connection_id) for user_id, connection_id in rows.all()]

    async def claim(self, user_id: str, connection_id: str, now: datetime, until: datetime) -> bool:
        claimed = await self._s.execute(
            update(BankConnectionORM)
            .where(
                BankConnectionORM.id == connection_id,
                BankConnectionORM.user_id == user_id,
                or_(
                    BankConnectionORM.sync_claimed_until.is_(None),
                    BankConnectionORM.sync_claimed_until < now,
                ),
            )
            .values(sync_claimed_until=until, last_attempt_at=now)
            .returning(BankConnectionORM.id)
        )
        return claimed.first() is not None

    async def release(self, user_id: str, connection_id: str) -> None:
        await self._s.execute(
            update(BankConnectionORM)
            .where(BankConnectionORM.id == connection_id, BankConnectionORM.user_id == user_id)
            .values(sync_claimed_until=None)
        )

    async def update_account(
        self, user_id: str, connection_id: str, remote_id: str, fields: dict[str, Any]
    ) -> None:
        row = (
            await self._s.execute(
                select(BankConnectionAccountORM).where(
                    BankConnectionAccountORM.connection_id == connection_id,
                    BankConnectionAccountORM.user_id == user_id,
                    BankConnectionAccountORM.remote_id == remote_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return
        for key in ("last_imported_at", "notes"):
            if key in fields:
                setattr(row, key, fields[key])
        await self._s.flush()

    async def _one(self, user_id: str, connection_id: str) -> BankConnectionORM | None:
        return (
            await self._s.execute(
                select(BankConnectionORM).where(
                    BankConnectionORM.id == connection_id, BankConnectionORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    def _account(row: BankConnectionAccountORM) -> dict[str, Any]:
        balance = None
        if row.balance_minor is not None and is_currency(row.currency):
            balance = from_minor(row.balance_minor, row.currency)
        return {
            "remote_id": row.remote_id,
            "name": row.name,
            "institution": row.institution,
            "currency": row.currency,
            "account_id": row.account_id,
            "balance": balance,
            "balance_date": row.balance_date,
            "last_imported_at": row.last_imported_at,
            "notes": row.notes,
        }

    def _connection(self, row: BankConnectionORM) -> dict[str, Any]:
        return {
            "id": row.id,
            "provider": row.provider,
            "name": row.name,
            "status": row.status,
            "last_error": row.last_error,
            "warnings": list(row.warnings or []),
            "last_synced_at": row.last_synced_at,
            "last_attempt_at": row.last_attempt_at,
            "created_at": row.created_at,
            "accounts": [self._account(a) for a in sorted(row.accounts, key=lambda a: a.name)],
        }

    async def create(self, user_id: str, connection: dict[str, Any]) -> str:
        row = BankConnectionORM(
            id=connection.get("id") or str(uuid.uuid4()),
            user_id=user_id,
            provider=connection["provider"],
            name=connection["name"],
            credential_sealed=connection["credential_sealed"],
            key_version=connection["key_version"],
            status="active",
            warnings=[],
            created_at=datetime.now(UTC),
        )
        self._s.add(row)
        await self._s.flush()
        return row.id

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        rows = (
            await self._s.execute(
                select(BankConnectionORM)
                .where(BankConnectionORM.user_id == user_id)
                .order_by(BankConnectionORM.created_at)
            )
        ).scalars()
        return [self._connection(r) for r in rows]

    async def get_secret(self, user_id: str, connection_id: str) -> dict[str, Any] | None:
        row = await self._one(user_id, connection_id)
        if row is None:
            return None
        return {
            **self._connection(row),
            "credential_sealed": row.credential_sealed,
            "key_version": row.key_version,
        }

    async def upsert_accounts(
        self, user_id: str, connection_id: str, accounts: list[RemoteAccount]
    ) -> None:
        row = await self._one(user_id, connection_id)
        if row is None:
            return
        existing = {a.remote_id: a for a in row.accounts}
        for remote in accounts:
            current = existing.get(remote.remote_id)
            if current is None:
                current = BankConnectionAccountORM(
                    id=str(uuid.uuid4()),
                    connection_id=connection_id,
                    user_id=user_id,
                    remote_id=remote.remote_id,
                    created_at=datetime.now(UTC),
                )
                row.accounts.append(current)
            current.name = remote.name
            current.institution = remote.institution
            current.currency = remote.currency
            current.balance_minor = (
                to_minor(remote.balance, remote.currency) if is_currency(remote.currency) else None
            )
            current.balance_date = remote.balance_date
        await self._s.flush()

    async def map_account(
        self, user_id: str, connection_id: str, remote_id: str, account_id: str | None
    ) -> bool:
        row = (
            await self._s.execute(
                select(BankConnectionAccountORM).where(
                    BankConnectionAccountORM.connection_id == connection_id,
                    BankConnectionAccountORM.user_id == user_id,
                    BankConnectionAccountORM.remote_id == remote_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        if row.account_id != account_id:
            # Into another account, its history starts again: the first
            # sync's window, then the overlap.
            row.last_imported_at = None
            row.notes = None
        row.account_id = account_id
        await self._s.flush()
        return True

    async def update(self, user_id: str, connection_id: str, fields: dict[str, Any]) -> None:
        row = await self._one(user_id, connection_id)
        if row is None:
            return
        for key in ("name", "status", "last_error", "last_synced_at", "warnings"):
            if key in fields:
                setattr(row, key, fields[key])
        await self._s.flush()

    async def delete(self, user_id: str, connection_id: str) -> bool:
        row = await self._one(user_id, connection_id)
        if row is None:
            return False
        await self._s.delete(row)
        await self._s.flush()
        return True
