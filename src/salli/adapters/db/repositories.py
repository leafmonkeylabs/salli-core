"""
SQLAlchemy repository implementations — concrete adapters for the port interfaces.
Translate between ORM models and domain models via mappers below.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import Select, delete, func, or_, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from salli.adapters.db.models import (
    AccessGrantORM,
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
    DecisionNoteORM,
    DecisionORM,
    DecisionReviewORM,
    DocumentORM,
    FireStrategyORM,
    FiScoreORM,
    GoalAllocationORM,
    GoalORM,
    HoldingORM,
    HoldingPriceORM,
    HoldingTransactionORM,
    InstanceSettingORM,
    InsuranceTargetORM,
    JournalEntryORM,
    LoginFailureORM,
    LoginORM,
    LoginSessionORM,
    NotificationDeliveryORM,
    NotificationPreferencesORM,
    OAuthAccessTokenORM,
    OAuthAuthorizationCodeORM,
    OAuthClientORM,
    OAuthDeviceCodeORM,
    OAuthGrantORM,
    OAuthRefreshTokenORM,
    ParsedTransactionORM,
    PersonalAccessTokenORM,
    PolicyORM,
    PostingORM,
    PostingTagORM,
    PrincipleORM,
    ReconciliationORM,
    RecurringSubscriptionORM,
    ReminderORM,
    StatementORM,
    TagORM,
    TaxComputationORM,
    TaxReturnORM,
    TaxReturnPaymentORM,
    TaxRuleSetORM,
    TaxRuleSetVersionORM,
    UserLlmCredentialORM,
    UserProfileORM,
)
from salli.application.entry_author import current_author
from salli.application.ports import (
    AccountCodeTaken,
    AccountNotFound,
    AdvisoryRepository,
    AgentDocumentRepository,
    AgentSessionRepository,
    AiConnectionRepository,
    AuditLogRepository,
    BankConnectionRepository,
    BudgetRepository,
    DataPortabilityRepository,
    DebtRepository,
    EntryRefTaken,
    FireStrategyRepository,
    FiScoreRepository,
    GoalRepository,
    HoldingPriceRepository,
    HoldingTransactionRepository,
    InstanceSettingsRepository,
    InsuranceTargetRepository,
    LedgerRepository,
    LlmCredentialRepository,
    LoginRepository,
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
    SignInGrantRow,
    StatementRepository,
    UserProfileRepository,
)
from salli.domain.accounting import chain
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
        reverses=row.reverses_id,
        reversed_by=row.reversed_by,  # type: ignore[attr-defined]
        created_by=row.created_by,
        created_via=row.created_via,
        seq=row.seq,
        hash=row.hash,
        postings=[_posting_from_orm(p) for p in row.postings],
    )


def _chain_content(row: JournalEntryORM) -> dict[str, Any]:
    """An entry as stored now, as the hash chain covers it."""
    return chain.content(
        seq=row.seq,
        prev_hash=row.prev_hash,
        entry_id=row.id,
        user_id=row.user_id,
        entry_date=row.entry_date,
        description=row.description,
        source=row.source,
        external_ref=row.external_ref,
        reverses=row.reverses_id,
        created_by=row.created_by,
        created_via=row.created_via,
        postings=[
            {
                "account_id": p.account_id,
                "direction": p.direction,
                "amount_minor": p.amount_minor,
                "currency": p.currency,
                "fx_rate": chain.rate_text(Decimal(str(p.fx_rate))),
            }
            for p in row.postings
        ],
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
        asset_role=row.asset_role,  # type: ignore[arg-type]
        equity_role=row.equity_role,  # type: ignore[arg-type]
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

    async def posting_entry_date(self, user_id: str, posting_id: str) -> str | None:
        return (
            await self._session.execute(
                select(JournalEntryORM.entry_date)
                .join(PostingORM, PostingORM.entry_id == JournalEntryORM.id)
                .where(PostingORM.id == posting_id, JournalEntryORM.user_id == user_id)
            )
        ).scalar_one_or_none()

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
        # Every posting's account is this user's. Nothing below the service
        # checks it (postings reference accounts by id alone), so an id from
        # another ledger would otherwise be booked against that ledger.
        named = {p.account_id for p in entry.postings}
        owned = set(
            (
                await self._session.execute(
                    select(AccountORM.id).where(
                        AccountORM.user_id == user_id, AccountORM.id.in_(named)
                    )
                )
            )
            .scalars()
            .all()
        )
        if named - owned:
            raise AccountNotFound(named - owned)

        # The user's chain is extended one entry at a time: the lock holds
        # until this transaction ends, so two entries never claim one place.
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "ledger:" + user_id}
        )
        last = (
            await self._session.execute(
                select(JournalEntryORM.seq, JournalEntryORM.hash)
                .where(JournalEntryORM.user_id == user_id)
                .order_by(JournalEntryORM.seq.desc())
                .limit(1)
            )
        ).first()
        seq, prev_hash = (last[0] + 1, last[1]) if last else (1, None)
        author = current_author()
        created_by = author.user_id or user_id
        created_via = "import" if entry.source in ("statement", "sms") else author.via
        orm_entry = JournalEntryORM(
            id=entry_id,
            user_id=user_id,
            entry_date=entry.entry_date,
            description=entry.description,
            source=entry.source,
            external_ref=entry.external_ref,
            reverses_id=entry.reverses,
            created_by=created_by,
            created_via=created_via,
            seq=seq,
            prev_hash=prev_hash,
        )
        orm_entry.hash = chain.entry_hash(
            chain.content(
                seq=seq,
                prev_hash=prev_hash,
                entry_id=entry_id,
                user_id=user_id,
                entry_date=entry.entry_date,
                description=entry.description,
                source=entry.source,
                external_ref=entry.external_ref,
                reverses=entry.reverses,
                created_by=created_by,
                created_via=created_via,
                postings=[
                    {
                        "account_id": p.account_id,
                        "direction": p.direction.value,
                        "amount_minor": to_minor(p.amount, p.currency),
                        "currency": p.currency,
                        "fx_rate": chain.rate_text(p.fx_rate),
                    }
                    for p in entry.postings
                ],
            )
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
        if entry.source != "manual" or not entry.external_ref:
            self._session.add(orm_entry)
            return entry_id
        # In a savepoint, so the same client_ref booked meanwhile (core_0027's
        # unique index) is a typed error the caller can act on.
        try:
            async with self._session.begin_nested():
                self._session.add(orm_entry)
        except IntegrityError as exc:
            if "uq_journal_entries_client_ref" in str(exc.orig):
                raise EntryRefTaken(entry.external_ref) from exc
            raise
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
        self, user_id: str, account_ids: Collection[str], to_date: str | None = None
    ) -> list[tuple[str, str, Decimal, Decimal]]:
        if not account_ids:
            return []
        signed = PostingORM.direction * PostingORM.amount_minor
        stmt = (
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
        if to_date:
            stmt = stmt.where(JournalEntryORM.entry_date <= to_date)
        rows = await self._session.execute(stmt)
        totals: list[tuple[str, str, Decimal, Decimal]] = []
        for account_id, currency, amount, base in rows.all():
            places = -exponent(currency, strict=False)
            totals.append(
                (account_id, currency, Decimal(amount).scaleb(places), Decimal(base).scaleb(places))
            )
        return totals

    async def search_entries(
        self,
        user_id: str,
        *,
        text: str | None = None,
        account_id: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        min_base_minor: int | None = None,
        max_base_minor: int | None = None,
        after: tuple[str, str] | None = None,
        limit: int = 50,
    ) -> tuple[list[StoredJournalEntry], int, list[tuple[str, str, Decimal]]]:
        matched = select(JournalEntryORM.id).where(JournalEntryORM.user_id == user_id)
        if text:
            escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            matched = matched.where(JournalEntryORM.description.ilike(f"%{escaped}%", escape="\\"))
        if from_date:
            matched = matched.where(JournalEntryORM.entry_date >= from_date)
        if to_date:
            matched = matched.where(JournalEntryORM.entry_date <= to_date)
        if account_id or min_base_minor is not None or max_base_minor is not None:
            posting = select(PostingORM.id).where(PostingORM.entry_id == JournalEntryORM.id)
            if account_id:
                posting = posting.where(PostingORM.account_id == account_id)
            if min_base_minor is not None:
                posting = posting.where(PostingORM.base_amount_minor >= min_base_minor)
            if max_base_minor is not None:
                posting = posting.where(PostingORM.base_amount_minor <= max_base_minor)
            matched = matched.where(posting.exists())
        ids = matched.subquery()

        page = (
            select(JournalEntryORM)
            .where(JournalEntryORM.id.in_(select(ids.c.id)))
            .options(selectinload(JournalEntryORM.postings))
            .order_by(JournalEntryORM.entry_date.desc(), JournalEntryORM.id.desc())
            .limit(limit)
        )
        if after:
            page = page.where(tuple_(JournalEntryORM.entry_date, JournalEntryORM.id) < after)
        entries = [_entry_from_orm(row) for row in (await self._session.execute(page)).scalars()]

        count = (await self._session.execute(select(func.count()).select_from(ids))).scalar_one()
        sums = (
            select(
                AccountORM.type,
                PostingORM.currency,
                func.sum(PostingORM.direction * PostingORM.amount_minor),
            )
            .join(AccountORM, AccountORM.id == PostingORM.account_id)
            .where(PostingORM.entry_id.in_(select(ids.c.id)))
            .group_by(AccountORM.type, PostingORM.currency)
            .order_by(AccountORM.type, PostingORM.currency)
        )
        if account_id:
            sums = sums.where(PostingORM.account_id == account_id)
        totals = [
            (type_, currency, Decimal(net).scaleb(-exponent(currency, strict=False)))
            for type_, currency, net in (await self._session.execute(sums)).all()
        ]
        return entries, count, totals

    async def manual_entry_by_ref(
        self, user_id: str, external_ref: str
    ) -> StoredJournalEntry | None:
        result = await self._session.execute(
            select(JournalEntryORM)
            .where(
                JournalEntryORM.user_id == user_id,
                JournalEntryORM.source == "manual",
                JournalEntryORM.external_ref == external_ref,
            )
            .options(selectinload(JournalEntryORM.postings))
            .order_by(JournalEntryORM.created_at)
            .limit(1)
        )
        row = result.scalars().first()
        return _entry_from_orm(row) if row else None

    async def first_flow_date(self, user_id: str, to_date: str | None = None) -> str | None:
        # A reversed entry and its reversal net to nothing: neither says when
        # the record of money in and out began.
        reversals = select(JournalEntryORM.reverses_id).where(
            JournalEntryORM.user_id == user_id, JournalEntryORM.reverses_id.is_not(None)
        )
        stmt = (
            select(func.min(JournalEntryORM.entry_date))
            .join(PostingORM, PostingORM.entry_id == JournalEntryORM.id)
            .join(AccountORM, AccountORM.id == PostingORM.account_id)
            .where(
                JournalEntryORM.user_id == user_id,
                AccountORM.user_id == user_id,
                AccountORM.type.in_(("income", "expense")),
                JournalEntryORM.reverses_id.is_(None),
                JournalEntryORM.id.not_in(reversals),
            )
        )
        if to_date:
            stmt = stmt.where(JournalEntryORM.entry_date <= to_date)
        return (await self._session.execute(stmt)).scalar_one_or_none()

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
            asset_role=account.asset_role,
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

    async def verify_chain(self, user_id: str) -> dict[str, Any]:
        result = await self._session.execute(
            select(JournalEntryORM)
            .where(JournalEntryORM.user_id == user_id)
            .options(selectinload(JournalEntryORM.postings))
            .order_by(JournalEntryORM.seq)
        )
        return chain.verify(
            chain.Link(_chain_content(row), row.hash) for row in result.scalars().all()
        )

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
        asset_role: str | None = None,
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
            row.asset_role = asset_role

    async def set_retained_earnings(self, user_id: str, account_id: str) -> None:
        await self._session.execute(
            update(AccountORM)
            .where(AccountORM.user_id == user_id, AccountORM.id != account_id)
            .where(AccountORM.equity_role == "retained_earnings")
            .values(equity_role=None)
        )
        await self._session.flush()
        await self._session.execute(
            update(AccountORM)
            .where(AccountORM.user_id == user_id, AccountORM.id == account_id)
            .values(equity_role="retained_earnings")
        )

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
        kind: str = "import",
        balances_minor: tuple[int, int] | None = None,
    ) -> None:
        # The label fits its column, whoever made it: a bank feed's
        # "institution · account name" can run past it.
        width = StatementORM.__table__.c.bank.type.length or 100
        orm = StatementORM(
            id=statement_id,
            user_id=user_id,
            storage_key=storage_key,
            bank=(bank or "")[:width],
            account_id=account_id,
            kind=kind,
            period_start=period_start,
            period_end=period_end,
            opening_balance_minor=balances_minor[0] if balances_minor else None,
            closing_balance_minor=balances_minor[1] if balances_minor else None,
            # Nothing to review (empty, or every row an exact duplicate): done.
            status=(
                "pending"
                if any(t.dedup_status not in _SETTLED for t in transactions)
                else "reviewed"
            ),
        )
        self._session.add(orm)
        self._add(statement_id, account_id, transactions)

    async def open_drafts(self, user_id: str, account_id: str) -> str | None:
        waiting = (
            select(ParsedTransactionORM.id)
            .where(ParsedTransactionORM.statement_id == StatementORM.id, *_PENDING)
            .exists()
        )
        return await self._session.scalar(
            select(StatementORM.id)
            .where(
                StatementORM.user_id == user_id,
                StatementORM.account_id == account_id,
                StatementORM.kind == "drafts",
                waiting,
            )
            .order_by(StatementORM.created_at.desc())
            .limit(1)
            .with_for_update(of=StatementORM)
        )

    async def add_rows(
        self,
        user_id: str,
        statement_id: str,
        transactions: list[Any],
        *,
        period_start: str,
        period_end: str,
    ) -> None:
        statement = await self._session.get(StatementORM, statement_id)
        if statement is None or statement.user_id != user_id:
            raise ValueError(f"Statement {statement_id} not found")
        # ISO dates compare as text.
        statement.period_start = min(filter(None, (statement.period_start, period_start)))
        statement.period_end = max(filter(None, (statement.period_end, period_end)))
        self._add(statement_id, statement.account_id, transactions)
        await self._session.flush()
        await self._settle(statement_id)

    def _add(self, statement_id: str, account_id: str | None, transactions: list[Any]) -> None:
        """Rows for a statement, each given its new id."""
        import uuid as _uuid

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
                    "base_amount": None if raw.base_amount is None else str(raw.base_amount),
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
        await self._settle(statement_id)
        return len(rows)

    async def _settle(self, statement_id: str) -> None:
        """A statement is reviewed once none of its rows waits for anyone."""
        waiting = await self._session.scalar(
            select(func.count())
            .select_from(ParsedTransactionORM)
            .where(ParsedTransactionORM.statement_id == statement_id, *_PENDING)
        )
        statement = await self._session.get(StatementORM, statement_id)
        if statement is not None:
            statement.status = "pending" if waiting else "reviewed"
            await self._session.flush()

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
            await self._session.flush()
            await self._settle(row.statement_id)

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
_SETTLED = ("posted", "discarded", "exact_duplicate")
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
        # Every row records its currency when it is saved: there is no default
        # currency to fall back on.
        currency=j["currency"],
        ref_kind=j.get("ref_kind", "id"),
        ref_source=j.get("ref_source", ""),
        source_account=j.get("source_account", ""),
        base_amount=Decimal(j["base_amount"]) if j.get("base_amount") else None,
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
        splits=list(j.get("splits") or []),
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

    async def sync_source(
        self,
        user_id: str,
        source_domain: str,
        source_prefix: str,
        items: list[tuple[str, str, str]],
    ) -> dict[str, list[str]]:
        for source_id, _, _ in items:
            if not source_id.startswith(source_prefix):
                raise ValueError(f"{source_id!r} is not under {source_prefix!r}")
        rows = (
            (
                await self._session.execute(
                    select(ReminderORM).where(
                        ReminderORM.user_id == user_id,
                        ReminderORM.source_domain == source_domain,
                        ReminderORM.source_id.startswith(source_prefix, autoescape=True),
                    )
                )
            )
            .scalars()
            .all()
        )
        existing = {row.source_id: row for row in rows}
        wanted = {source_id: (kind, due) for source_id, kind, due in items}
        report: dict[str, list[str]] = {"created": [], "updated": [], "removed": []}
        for source_id, row in existing.items():
            if source_id not in wanted:
                await self._session.delete(row)
                report["removed"].append(row.id)
        for source_id, (kind, due) in wanted.items():
            row = existing.get(source_id)
            if row is None:
                reminder_id = str(uuid.uuid4())
                self._session.add(
                    ReminderORM(
                        id=reminder_id,
                        user_id=user_id,
                        kind=kind,
                        due_date=due,
                        status="pending",
                        source_domain=source_domain,
                        source_id=source_id,
                    )
                )
                report["created"].append(reminder_id)
            elif (row.kind, row.due_date) != (kind, due):
                if row.due_date != due:
                    row.status = "pending"
                row.kind, row.due_date = kind, due
                report["updated"].append(row.id)
        await self._session.flush()
        return report


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
        "retain_until": row.retain_until.isoformat() if row.retain_until else None,
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
            retain_until=doc.get("retain_until"),
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        return doc_id

    async def cited_by_entry(self, user_id: str, doc_id: str) -> bool:
        """Whether one of the user's journal entries cites the document (a
        manual entry's receipt, its external_ref)."""
        return (
            await self._session.scalar(
                select(JournalEntryORM.id)
                .where(JournalEntryORM.user_id == user_id, JournalEntryORM.external_ref == doc_id)
                .limit(1)
            )
        ) is not None

    async def filed_return_citing(self, user_id: str, doc_id: str) -> date | None:
        """The latest filing date of a filed tax return whose period holds an
        entry citing the document; None when there is none."""
        day = func.to_char
        return await self._session.scalar(
            select(func.max(TaxReturnORM.filed_on)).where(
                TaxReturnORM.user_id == user_id,
                TaxReturnORM.status == "filed",
                select(JournalEntryORM.id)
                .where(
                    JournalEntryORM.user_id == user_id,
                    JournalEntryORM.external_ref == doc_id,
                    JournalEntryORM.entry_date >= day(TaxReturnORM.period_start, "YYYY-MM-DD"),
                    JournalEntryORM.entry_date <= day(TaxReturnORM.period_end, "YYYY-MM-DD"),
                )
                .exists(),
            )
        )

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
            "risk_score": row.risk_score,
            "risk_category": row.risk_category,
            "life_stage": row.life_stage,
            "mcp_enabled": row.mcp_enabled,
            "daily_briefing_enabled": row.daily_briefing_enabled,
            "preferred_model": row.preferred_model,
            "tax_residency": row.tax_residency,
            "tax_ids": list(row.tax_ids or []),
            "fi_assumptions": dict(row.fi_assumptions or {}),
            "time_zone": row.time_zone,
            "lock_date": row.lock_date.isoformat() if row.lock_date else None,
            "books_start": row.books_start.isoformat() if row.books_start else None,
            "document_retention_years": row.document_retention_years,
        }

    async def set_lock_date(self, user_id: str, lock_date: str | None) -> None:
        result = await self._s.execute(select(UserProfileORM).where(UserProfileORM.id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            raise ProfileMissing(user_id)
        row.lock_date = date.fromisoformat(lock_date) if lock_date else None
        await self._s.flush()

    async def set_fi_assumptions(self, user_id: str, stored: dict[str, Any]) -> None:
        """Replace the user's own FI assumptions with `stored` (as
        `OwnAssumptions.as_stored()` writes them: the service validates)."""
        if not isinstance(stored, dict):
            raise ValueError("FI assumptions are stored as an object")
        result = await self._s.execute(select(UserProfileORM).where(UserProfileORM.id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            raise ProfileMissing(user_id)
        row.fi_assumptions = stored
        await self._s.flush()

    async def set_tax_identity(
        self,
        user_id: str,
        *,
        tax_residency: str | None,
        tax_ids: list[dict[str, str]],
    ) -> None:
        """Write where the user is taxed and their tax ids, exactly as given.

        `upsert` skips None, so it could never clear a residency; this writes
        NULL too.
        """
        result = await self._s.execute(select(UserProfileORM).where(UserProfileORM.id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            raise ProfileMissing(user_id)
        row.tax_residency = tax_residency
        row.tax_ids = tax_ids
        await self._s.flush()

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
        if field not in ("preferred_model", "time_zone"):
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
        "briefing": r.briefing,
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
                briefing=report.get("briefing"),
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

    async def export(self, user_id: str) -> list[dict[str, Any]]:
        rows = (
            (
                await self._s.execute(
                    select(AdvisoryReportORM)
                    .where(AdvisoryReportORM.user_id == user_id)
                    .order_by(AdvisoryReportORM.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return [_report_to_dict(r) for r in rows]

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

    async def export(self, user_id: str) -> list[dict[str, Any]]:
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
            {"version": r.version, "created_at": r.created_at.isoformat(), **r.strategy}
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
        "account_id": r.account_id,
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
                account_id=debt.get("account_id"),
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
        # None is a value here: it unlinks the debt from its account.
        if "account_id" in updates:
            r.account_id = updates["account_id"]
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
        "currency": r.currency,
        "cost_basis_minor": r.cost_basis_minor,
        "current_value_minor": r.current_value_minor,
        "is_active": r.is_active,
        "account_id": r.account_id,
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
                currency=holding["currency"],
                cost_basis_minor=int(holding["cost_basis_minor"]),
                current_value_minor=int(holding["current_value_minor"]),
                is_active=holding.get("is_active", True),
                account_id=holding.get("account_id"),
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
            "currency",
            "cost_basis_minor",
            "current_value_minor",
            "is_active",
        ):
            if k in updates and updates[k] is not None:
                setattr(r, k, updates[k])
        # None unlinks the holding from its account.
        if "account_id" in updates:
            r.account_id = updates["account_id"]
        await self._s.flush()

    async def delete(self, user_id: str, holding_id: str) -> None:
        r = (
            await self._s.execute(
                select(HoldingORM).where(HoldingORM.id == holding_id, HoldingORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        if r:
            # Its transactions go with it (ON DELETE CASCADE).
            await self._s.delete(r)

    async def lock(self, user_id: str, holding_id: str) -> None:
        # SELECT … FOR UPDATE: a second change to the same holding's history
        # waits here until the first commits, then checks against it.
        await self._s.execute(
            select(HoldingORM.id)
            .where(HoldingORM.id == holding_id, HoldingORM.user_id == user_id)
            .with_for_update()
        )


_TRANSACTION_COLUMNS = (
    "kind",
    "transaction_date",
    "quantity",
    "price",
    "fees_minor",
    "amount_minor",
    "withholding_tax_minor",
    "split_to",
    "split_from",
    "lots",
    "fx_rate",
    "fx_rate_source",
    "note",
)


def _transaction_to_dict(r: HoldingTransactionORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "holding_id": r.holding_id,
        **{column: getattr(r, column) for column in _TRANSACTION_COLUMNS},
        "transaction_date": r.transaction_date.isoformat(),
        "lots": [dict(pick) for pick in r.lots or []],
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


def _transaction_columns(fields: dict[str, Any]) -> dict[str, Any]:
    columns = {k: fields[k] for k in _TRANSACTION_COLUMNS if k in fields}
    if isinstance(columns.get("transaction_date"), str):
        columns["transaction_date"] = date.fromisoformat(columns["transaction_date"])
    return columns


class SQLHoldingTransactionRepository(HoldingTransactionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _row(self, user_id: str, transaction_id: str) -> HoldingTransactionORM | None:
        return (
            await self._s.execute(
                select(HoldingTransactionORM).where(
                    HoldingTransactionORM.id == transaction_id,
                    HoldingTransactionORM.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

    async def list(self, user_id: str, holding_id: str | None = None) -> list[dict[str, Any]]:
        stmt = select(HoldingTransactionORM).where(HoldingTransactionORM.user_id == user_id)
        if holding_id is not None:
            stmt = stmt.where(HoldingTransactionORM.holding_id == holding_id)
        stmt = stmt.order_by(HoldingTransactionORM.created_at, HoldingTransactionORM.id)
        return [_transaction_to_dict(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def get(self, user_id: str, transaction_id: str) -> dict[str, Any] | None:
        r = await self._row(user_id, transaction_id)
        return _transaction_to_dict(r) if r else None

    async def save(self, user_id: str, transaction: dict[str, Any]) -> str:
        tid = transaction.get("id") or str(uuid.uuid4())
        self._s.add(
            HoldingTransactionORM(
                id=tid,
                user_id=user_id,
                holding_id=transaction["holding_id"],
                **_transaction_columns(transaction),
            )
        )
        await self._s.flush()
        return tid

    async def update(self, user_id: str, transaction_id: str, fields: dict[str, Any]) -> bool:
        r = await self._row(user_id, transaction_id)
        if r is None:
            return False
        for column, value in _transaction_columns(fields).items():
            setattr(r, column, value)
        await self._s.flush()
        return True

    async def delete(self, user_id: str, transaction_id: str) -> bool:
        r = await self._row(user_id, transaction_id)
        if r is None:
            return False
        await self._s.delete(r)
        await self._s.flush()
        return True


def _price_to_dict(r: HoldingPriceORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "symbol": r.symbol,
        "price_date": r.price_date.isoformat(),
        "close": r.close,
        "currency": r.currency,
        "source": r.source,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


class SQLHoldingPriceRepository(HoldingPriceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert(self, user_id: str, price: dict[str, Any]) -> str:
        now = datetime.now(UTC)
        values = {
            "symbol": price["symbol"],
            "price_date": date.fromisoformat(str(price["price_date"])),
            "close": price["close"],
            "currency": price["currency"],
            "source": price["source"],
        }
        # One statement, so two recordings of the same close cannot race into
        # a unique-constraint error.
        stmt = (
            pg_insert(HoldingPriceORM)
            .values(id=str(uuid.uuid4()), user_id=user_id, created_at=now, updated_at=now, **values)
            .on_conflict_do_update(
                constraint="uq_holding_prices_user_symbol_currency_date",
                set_={
                    "close": values["close"],
                    "source": values["source"],
                    "updated_at": now,
                },
            )
            .returning(HoldingPriceORM.id)
        )
        return str((await self._s.execute(stmt)).scalar_one())

    async def list(
        self,
        user_id: str,
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(HoldingPriceORM).where(HoldingPriceORM.user_id == user_id)
        if symbol is not None:
            stmt = stmt.where(HoldingPriceORM.symbol == symbol)
        if start is not None:
            stmt = stmt.where(HoldingPriceORM.price_date >= date.fromisoformat(start))
        if end is not None:
            stmt = stmt.where(HoldingPriceORM.price_date <= date.fromisoformat(end))
        stmt = stmt.order_by(HoldingPriceORM.price_date, HoldingPriceORM.symbol)
        return [_price_to_dict(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def get(self, user_id: str, quote_id: str) -> dict[str, Any] | None:
        r = (
            await self._s.execute(
                select(HoldingPriceORM).where(
                    HoldingPriceORM.id == quote_id, HoldingPriceORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        return _price_to_dict(r) if r else None

    async def delete(self, user_id: str, quote_id: str) -> bool:
        result = await self._s.execute(
            delete(HoldingPriceORM).where(
                HoldingPriceORM.id == quote_id, HoldingPriceORM.user_id == user_id
            )
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]


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
        "client_id": r.client_id,
        "created_at": r.created_at.isoformat(),
    }


class SQLAuditLogRepository(AuditLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def log(
        self,
        user_id: str,
        action: str,
        params: dict[str, Any],
        decision: str,
        client_id: str | None = None,
    ) -> str:
        log_id = str(uuid.uuid4())
        self._s.add(
            AuditLogORM(
                id=log_id,
                user_id=user_id,
                action=action,
                params=params,
                decision=decision,
                client_id=client_id,
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
        # principles.account_id -> accounts.id likewise.
        await _delete(PrincipleORM, PrincipleORM.user_id)
        # The decision journal is append-only, and the database refuses a
        # DELETE on it (core_0017) unless the transaction says whose account
        # it is erasing. Notes and reviews point at their entry, so go first.
        await self._s.execute(
            text("select set_config('salli.erase_user', :user_id, true)").bindparams(
                user_id=user_id
            )
        )
        await _delete(DecisionReviewORM, DecisionReviewORM.user_id)
        await _delete(DecisionNoteORM, DecisionNoteORM.user_id)
        await _delete(DecisionORM, DecisionORM.user_id)
        # debts.account_id -> accounts.id likewise.
        await _delete(DebtORM, DebtORM.user_id)
        # holdings.account_id -> accounts.id likewise. Transactions cascade
        # from their holding, but are deleted by owner first, like goal
        # allocations, rather than relying on the cascade.
        await _delete(HoldingTransactionORM, HoldingTransactionORM.user_id)
        await _delete(HoldingORM, HoldingORM.user_id)

        # journal_entries cascade-deletes their own postings (ondelete="CASCADE"
        # on postings.entry_id); statements cascade-deletes parsed_transactions
        # the same way (already emptied above, so that cascade is a no-op —
        # harmless). Both must still go before accounts.
        await _delete(JournalEntryORM, JournalEntryORM.user_id)
        await _delete(ReconciliationORM, ReconciliationORM.user_id)
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
        # The digest's preferences and its delivery log go with the account.
        await _delete(NotificationPreferencesORM, NotificationPreferencesORM.user_id)
        await _delete(NotificationDeliveryORM, NotificationDeliveryORM.user_id)
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
        await _delete(HoldingPriceORM, HoldingPriceORM.user_id)
        await _delete(PolicyORM, PolicyORM.user_id)
        await _delete(InsuranceTargetORM, InsuranceTargetORM.user_id)
        # Returns point at computations, payments at returns.
        await _delete(TaxReturnPaymentORM, TaxReturnPaymentORM.user_id)
        await _delete(TaxReturnORM, TaxReturnORM.user_id)
        await _delete(TaxComputationORM, TaxComputationORM.user_id)
        # After tax_computations, which may point at a version. A set is
        # deleted before its versions (its active version points back at it),
        # which cascade from it; deleting them by owner after is then a no-op,
        # kept so nothing depends on the cascade alone.
        await _delete(TaxRuleSetORM, TaxRuleSetORM.user_id)
        await _delete(TaxRuleSetVersionORM, TaxRuleSetVersionORM.user_id)
        await _delete(AuditLogORM, AuditLogORM.user_id)
        await _delete(OAuthRefreshTokenORM, OAuthRefreshTokenORM.user_id)
        await _delete(OAuthAccessTokenORM, OAuthAccessTokenORM.user_id)
        # After their tokens, which point at them.
        await _delete(OAuthGrantORM, OAuthGrantORM.user_id)
        await _delete(OAuthAuthorizationCodeORM, OAuthAuthorizationCodeORM.user_id)
        await _delete(OAuthDeviceCodeORM, OAuthDeviceCodeORM.user_id)
        await _delete(PersonalAccessTokenORM, PersonalAccessTokenORM.user_id)
        # Access to their books they gave, and to others' they held.
        result = await self._s.execute(
            delete(AccessGrantORM).where(
                or_(AccessGrantORM.grantor_id == user_id, AccessGrantORM.grantee_id == user_id)
            )
        )
        counts["access_grants"] = result.rowcount or 0  # type: ignore[attr-defined]
        # Their sessions, then their login: no one signs in as them again.
        await _delete(LoginSessionORM, LoginSessionORM.user_id)
        await _delete(LoginORM, LoginORM.user_id)
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
        # Never first party: a client that registers itself is whoever it says.
        row = OAuthClientORM(
            client_id=client_id,
            client_name=client_name,
            redirect_uris=redirect_uris,
            first_party=False,
        )
        self._s.add(row)
        await self._s.flush()
        return {
            "client_id": row.client_id,
            "client_name": row.client_name,
            "redirect_uris": row.redirect_uris,
            "first_party": False,
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
            "first_party": row.first_party,
        }


class SQLOAuthTokenRepository(OAuthTokenRepository):
    """Access/refresh tokens are looked up by hash — callers never store or
    pass the plaintext token after issuance. Each belongs to a grant."""

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
        authenticated_at: datetime,
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
                authenticated_at=authenticated_at,
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
            "authenticated_at": row.authenticated_at,
            "expires_at": row.expires_at,
        }

    async def delete_authorization_code(self, code: str) -> bool:
        result = await self._s.execute(
            delete(OAuthAuthorizationCodeORM).where(OAuthAuthorizationCodeORM.code == code)
        )
        await self._s.flush()
        return bool(cast(Any, result).rowcount)

    async def create_grant(
        self,
        user_id: str,
        client_id: str,
        scope: str,
        resource: str | None,
        authenticated_at: datetime,
        expires_at: datetime | None,
    ) -> str:
        grant_id = str(uuid.uuid4())
        self._s.add(
            OAuthGrantORM(
                id=grant_id,
                user_id=user_id,
                client_id=client_id,
                scope=scope,
                resource=resource,
                authenticated_at=authenticated_at,
                expires_at=expires_at,
            )
        )
        await self._s.flush()
        return grant_id

    async def save_access_token(
        self,
        token_hash: str,
        grant_id: str,
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
                grant_id=grant_id,
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
        grant_id: str,
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
                grant_id=grant_id,
                access_token_id=access_token_id,
                client_id=client_id,
                user_id=user_id,
                scope=scope,
                resource=resource,
                expires_at=expires_at,
            )
        )
        await self._s.flush()

    @staticmethod
    def _grant_ended(grant: OAuthGrantORM, now: datetime) -> bool:
        return grant.revoked_at is not None or (
            grant.expires_at is not None and grant.expires_at <= now
        )

    async def get_access_token(self, token_hash: str) -> dict[str, Any] | None:
        found = (
            await self._s.execute(
                select(OAuthAccessTokenORM, OAuthGrantORM, OAuthClientORM)
                .join(OAuthGrantORM, OAuthGrantORM.id == OAuthAccessTokenORM.grant_id)
                .join(OAuthClientORM, OAuthClientORM.client_id == OAuthAccessTokenORM.client_id)
                .where(OAuthAccessTokenORM.token_hash == token_hash)
            )
        ).one_or_none()
        if found is None:
            return None
        row, grant, client = found
        now = datetime.now(UTC)
        if row.revoked_at is not None or row.expires_at < now or self._grant_ended(grant, now):
            return None
        return {
            "id": row.id,
            "grant_id": row.grant_id,
            "client_id": row.client_id,
            "user_id": row.user_id,
            "scope": row.scope,
            "resource": row.resource,
            "expires_at": row.expires_at,
            # When the password behind it was checked, and how recent its
            # client wants that for powerful permissions.
            "authenticated_at": grant.authenticated_at,
            "last_used_at": grant.last_used_at,
            # Whose client holds it: what a token may do depends on it
            # (application/permissions.py).
            "client_name": client.client_name,
            "client_first_party": bool(client.first_party),
            "client_step_up_seconds": client.step_up_seconds,
        }

    async def find_refresh_token(self, token_hash: str) -> dict[str, Any] | None:
        found = (
            await self._s.execute(
                select(OAuthRefreshTokenORM, OAuthAccessTokenORM.revoked_at, OAuthGrantORM)
                .join(
                    OAuthAccessTokenORM,
                    OAuthAccessTokenORM.id == OAuthRefreshTokenORM.access_token_id,
                )
                .join(OAuthGrantORM, OAuthGrantORM.id == OAuthRefreshTokenORM.grant_id)
                .where(OAuthRefreshTokenORM.token_hash == token_hash)
            )
        ).one_or_none()
        if found is None:
            return None
        row, access_revoked_at, grant = found
        return {
            "id": row.id,
            "grant_id": row.grant_id,
            "access_token_id": row.access_token_id,
            "client_id": row.client_id,
            "user_id": row.user_id,
            "scope": row.scope,
            "resource": row.resource,
            "expires_at": row.expires_at,
            "revoked_at": row.revoked_at,
            "access_revoked_at": access_revoked_at,
            "grant_revoked_at": grant.revoked_at,
            "grant_expires_at": grant.expires_at,
            "authenticated_at": grant.authenticated_at,
        }

    async def rotate_refresh_token(self, token_hash: str) -> bool:
        # One statement, so of two requests racing with the same token only
        # one rotates it; the other is a second use.
        result = await self._s.execute(
            update(OAuthRefreshTokenORM)
            .where(
                OAuthRefreshTokenORM.token_hash == token_hash,
                OAuthRefreshTokenORM.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        await self._s.flush()
        return bool(cast(Any, result).rowcount)

    @staticmethod
    def _grant(row: OAuthGrantORM) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "client_id": row.client_id,
            "scope": row.scope,
            "resource": row.resource,
            "authenticated_at": row.authenticated_at,
            "expires_at": row.expires_at,
            "last_used_at": row.last_used_at,
            "revoked_at": row.revoked_at,
            "created_at": row.created_at,
        }

    async def get_grant(self, grant_id: str) -> dict[str, Any] | None:
        row = await self._s.get(OAuthGrantORM, grant_id)
        return self._grant(row) if row is not None else None

    async def grant_of_token(self, token_hash: str) -> dict[str, Any] | None:
        for model in (OAuthAccessTokenORM, OAuthRefreshTokenORM):
            grant = (
                await self._s.execute(
                    select(OAuthGrantORM)
                    .join(model, model.grant_id == OAuthGrantORM.id)
                    .where(model.token_hash == token_hash)
                )
            ).scalar_one_or_none()
            if grant is not None:
                return self._grant(grant)
        return None

    async def revoke_grant(self, grant_id: str, user_id: str | None = None) -> int:
        now = datetime.now(UTC)
        grant = await self._s.get(OAuthGrantORM, grant_id)
        if grant is None or (user_id is not None and grant.user_id != user_id):
            return 0
        revoked = 0
        if grant.revoked_at is None:
            grant.revoked_at = now
            revoked += 1
        for model in (OAuthAccessTokenORM, OAuthRefreshTokenORM):
            result = await self._s.execute(
                update(model)
                .where(model.grant_id == grant_id, model.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            revoked += cast(Any, result).rowcount or 0
        await self._s.flush()
        return revoked

    async def touch_grant(self, grant_id: str, at: datetime) -> None:
        await self._s.execute(
            update(OAuthGrantORM).where(OAuthGrantORM.id == grant_id).values(last_used_at=at)
        )

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
            "grant_id": row.grant_id,
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
        for model in (OAuthGrantORM, OAuthAccessTokenORM, OAuthRefreshTokenORM):
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
            if model is not OAuthGrantORM:
                revoked += cast(Any, result).rowcount or 0
        await self._s.flush()
        return revoked

    async def revoke_all_for_user(self, user_id: str) -> int:
        now = datetime.now(UTC)
        revoked = 0
        for model in (OAuthGrantORM, OAuthAccessTokenORM, OAuthRefreshTokenORM):
            result = await self._s.execute(
                update(model)
                .where(model.user_id == user_id, model.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            if model is not OAuthGrantORM:
                revoked += cast(Any, result).rowcount or 0
        await self._s.flush()
        return revoked

    async def list_active_connections(
        self, user_id: str, resource: str | None = None
    ) -> list[McpConnectionRow]:
        now = datetime.now(UTC)
        grant_live = (
            OAuthGrantORM.revoked_at.is_(None),
            or_(OAuthGrantORM.expires_at.is_(None), OAuthGrantORM.expires_at > now),
        )
        access_stmt = (
            select(OAuthAccessTokenORM, OAuthClientORM)
            .join(OAuthClientORM, OAuthClientORM.client_id == OAuthAccessTokenORM.client_id)
            .join(OAuthGrantORM, OAuthGrantORM.id == OAuthAccessTokenORM.grant_id)
            .where(
                OAuthAccessTokenORM.user_id == user_id,
                OAuthAccessTokenORM.revoked_at.is_(None),
                OAuthAccessTokenORM.expires_at > now,
                *grant_live,
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
            .join(OAuthGrantORM, OAuthGrantORM.id == OAuthRefreshTokenORM.grant_id)
            .where(
                OAuthRefreshTokenORM.user_id == user_id,
                OAuthRefreshTokenORM.revoked_at.is_(None),
                OAuthRefreshTokenORM.expires_at > now,
                OAuthAccessTokenORM.revoked_at.is_(None),
                *grant_live,
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

    async def list_sign_in_grants(
        self, user_id: str, resource: str, now: datetime
    ) -> list[SignInGrantRow]:
        live_access = (
            select(OAuthAccessTokenORM.id)
            .where(
                OAuthAccessTokenORM.grant_id == OAuthGrantORM.id,
                OAuthAccessTokenORM.revoked_at.is_(None),
                OAuthAccessTokenORM.expires_at > now,
            )
            .exists()
        )
        newest_refresh = (
            select(func.max(OAuthRefreshTokenORM.expires_at))
            .where(
                OAuthRefreshTokenORM.grant_id == OAuthGrantORM.id,
                OAuthRefreshTokenORM.revoked_at.is_(None),
                OAuthRefreshTokenORM.expires_at > now,
            )
            .scalar_subquery()
        )
        rows = (
            await self._s.execute(
                select(OAuthGrantORM, OAuthClientORM.client_name, newest_refresh)
                .join(OAuthClientORM, OAuthClientORM.client_id == OAuthGrantORM.client_id)
                .where(
                    OAuthGrantORM.user_id == user_id,
                    OAuthGrantORM.resource == resource,
                    OAuthGrantORM.revoked_at.is_(None),
                    or_(OAuthGrantORM.expires_at.is_(None), OAuthGrantORM.expires_at > now),
                    or_(live_access, newest_refresh.is_not(None)),
                )
                .order_by(OAuthGrantORM.created_at.desc())
            )
        ).all()
        out: list[SignInGrantRow] = []
        for grant, client_name, refresh_ends in rows:
            ends: datetime | None = grant.expires_at or refresh_ends
            if grant.expires_at is not None and refresh_ends is not None:
                ends = min(grant.expires_at, refresh_ends)
            out.append(
                {
                    "grant_id": grant.id,
                    "client_id": grant.client_id,
                    "client_name": client_name or "Unnamed app",
                    "created_at": grant.created_at,
                    "last_used_at": grant.last_used_at,
                    "expires_at": ends,
                }
            )
        return out

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
            "authenticated_at": row.authenticated_at,
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
        for key in ("status", "user_id", "authenticated_at", "last_polled_at", "scope"):
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
            "permissions": sorted(row.permissions or []),
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
        permissions: list[str],
    ) -> dict[str, Any]:
        row = PersonalAccessTokenORM(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            token_hash=token_hash,
            prefix=prefix,
            permissions=sorted(set(permissions)),
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

    async def revoke_all(self, user_id: str) -> int:
        result = await self._s.execute(
            update(PersonalAccessTokenORM)
            .where(
                PersonalAccessTokenORM.user_id == user_id,
                PersonalAccessTokenORM.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        await self._s.flush()
        return cast(Any, result).rowcount or 0

    async def touch(self, token_id: str, at: datetime) -> None:
        row = (
            await self._s.execute(
                select(PersonalAccessTokenORM).where(PersonalAccessTokenORM.id == token_id)
            )
        ).scalar_one_or_none()
        if row is not None:
            row.last_used_at = at
            await self._s.flush()


class SQLLoginRepository(LoginRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @staticmethod
    def _login(row: LoginORM, *, with_hash: bool = True) -> dict[str, Any]:
        login: dict[str, Any] = {
            "user_id": row.user_id,
            "email": row.email,
            "is_owner": row.is_owner,
            "password_changed_at": row.password_changed_at,
            "created_at": row.created_at,
            "totp_enabled_at": row.totp_enabled_at,
            "totp_recovery_codes_left": len(row.totp_recovery_codes or []),
        }
        if with_hash:
            login["password_hash"] = row.password_hash
            login["totp_secret"] = row.totp_secret
            login["totp_key_version"] = row.totp_key_version
        return login

    @staticmethod
    def _session(row: LoginSessionORM) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "user_agent": row.user_agent,
            "created_at": row.created_at,
            "last_used_at": row.last_used_at,
            "expires_at": row.expires_at,
        }

    async def create(
        self, user_id: str, email: str, password_hash: str, *, is_owner: bool, at: datetime
    ) -> dict[str, Any]:
        row = LoginORM(
            user_id=user_id,
            email=email,
            password_hash=password_hash,
            is_owner=is_owner,
            password_changed_at=at,
            created_at=at,
        )
        self._s.add(row)
        await self._s.flush()
        return self._login(row, with_hash=False)

    async def get(self, user_id: str) -> dict[str, Any] | None:
        row = await self._s.get(LoginORM, user_id)
        return self._login(row) if row is not None else None

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(select(LoginORM).where(LoginORM.email == email))
        ).scalar_one_or_none()
        return self._login(row) if row is not None else None

    async def owner(self) -> dict[str, Any] | None:
        row = (
            await self._s.execute(select(LoginORM).where(LoginORM.is_owner.is_(True)))
        ).scalar_one_or_none()
        return self._login(row, with_hash=False) if row is not None else None

    async def list(self) -> list[dict[str, Any]]:
        rows = (await self._s.execute(select(LoginORM).order_by(LoginORM.created_at))).scalars()
        return [self._login(r, with_hash=False) for r in rows]

    async def set_password(
        self, user_id: str, password_hash: str, *, changed_at: datetime | None
    ) -> bool:
        row = await self._s.get(LoginORM, user_id)
        if row is None:
            return False
        row.password_hash = password_hash
        if changed_at is not None:
            row.password_changed_at = changed_at
        await self._s.flush()
        return True

    async def create_session(
        self,
        user_id: str,
        token_hash: str,
        user_agent: str | None,
        at: datetime,
        expires_at: datetime,
    ) -> dict[str, Any]:
        row = LoginSessionORM(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token_hash=token_hash,
            user_agent=user_agent,
            created_at=at,
            last_used_at=at,
            expires_at=expires_at,
        )
        self._s.add(row)
        await self._s.flush()
        return self._session(row)

    async def get_session(self, token_hash: str, now: datetime) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(LoginSessionORM).where(
                    LoginSessionORM.token_hash == token_hash,
                    LoginSessionORM.revoked_at.is_(None),
                    LoginSessionORM.expires_at > now,
                )
            )
        ).scalar_one_or_none()
        return self._session(row) if row is not None else None

    async def list_sessions(self, user_id: str, now: datetime) -> list[dict[str, Any]]:
        rows = (
            await self._s.execute(
                select(LoginSessionORM)
                .where(
                    LoginSessionORM.user_id == user_id,
                    LoginSessionORM.revoked_at.is_(None),
                    LoginSessionORM.expires_at > now,
                )
                .order_by(LoginSessionORM.created_at.desc())
            )
        ).scalars()
        return [self._session(r) for r in rows]

    async def touch_session(self, session_id: str, at: datetime) -> None:
        await self._s.execute(
            update(LoginSessionORM).where(LoginSessionORM.id == session_id).values(last_used_at=at)
        )

    async def revoke_session(self, user_id: str, session_id: str, at: datetime) -> bool:
        result = await self._s.execute(
            update(LoginSessionORM)
            .where(
                LoginSessionORM.id == session_id,
                LoginSessionORM.user_id == user_id,
                LoginSessionORM.revoked_at.is_(None),
            )
            .values(revoked_at=at)
        )
        return bool(cast(Any, result).rowcount)

    async def revoke_sessions(self, user_id: str, at: datetime, *, keep: str | None = None) -> int:
        where = [LoginSessionORM.user_id == user_id, LoginSessionORM.revoked_at.is_(None)]
        if keep is not None:
            where.append(LoginSessionORM.id != keep)
        result = await self._s.execute(update(LoginSessionORM).where(*where).values(revoked_at=at))
        return cast(Any, result).rowcount or 0

    async def set_totp(self, user_id: str, sealed: str | None, key_version: int | None) -> None:
        await self._s.execute(
            update(LoginORM)
            .where(LoginORM.user_id == user_id)
            .values(
                totp_secret=sealed,
                totp_key_version=key_version,
                totp_enabled_at=None,
                totp_last_step=None,
                totp_recovery_codes=[],
            )
        )

    async def enable_totp(
        self, user_id: str, recovery_hashes: list[str], *, step: int, at: datetime
    ) -> bool:
        result = await self._s.execute(
            update(LoginORM)
            .where(
                LoginORM.user_id == user_id,
                LoginORM.totp_secret.is_not(None),
                LoginORM.totp_enabled_at.is_(None),
            )
            .values(totp_enabled_at=at, totp_last_step=step, totp_recovery_codes=recovery_hashes)
        )
        return bool(cast(Any, result).rowcount)

    async def use_totp_step(self, user_id: str, step: int) -> bool:
        # One statement, so two requests with the same code can't both pass.
        result = await self._s.execute(
            update(LoginORM)
            .where(
                LoginORM.user_id == user_id,
                or_(LoginORM.totp_last_step.is_(None), LoginORM.totp_last_step < step),
            )
            .values(totp_last_step=step)
        )
        return bool(cast(Any, result).rowcount)

    async def use_recovery_code(self, user_id: str, code_hash: str) -> bool:
        result = await self._s.execute(
            update(LoginORM)
            .where(LoginORM.user_id == user_id, LoginORM.totp_recovery_codes.has_key(code_hash))
            .values(totp_recovery_codes=LoginORM.totp_recovery_codes.op("-")(code_hash))
        )
        return bool(cast(Any, result).rowcount)

    async def record_failure(self, key_hash: str, at: datetime) -> None:
        self._s.add(LoginFailureORM(key_hash=key_hash, at=at))
        await self._s.flush()

    async def failures_since(self, key_hash: str, since: datetime) -> list[datetime]:
        rows = await self._s.execute(
            select(LoginFailureORM.at)
            .where(LoginFailureORM.key_hash == key_hash, LoginFailureORM.at > since)
            .order_by(LoginFailureORM.at)
        )
        return list(rows.scalars())

    async def clear_failures(self, key_hash: str) -> None:
        await self._s.execute(delete(LoginFailureORM).where(LoginFailureORM.key_hash == key_hash))

    async def prune_failures(self, before: datetime) -> None:
        await self._s.execute(delete(LoginFailureORM).where(LoginFailureORM.at <= before))


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
