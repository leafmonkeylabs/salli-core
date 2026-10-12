"""
A small ledger to build baselines from in tests: accounts, entries booked
one line at a time, declared debts and assumptions, and the baseline as of a
day, built the way the application builds it (BaselineService over an
in-memory unit of work).
"""

from __future__ import annotations

import asyncio
import datetime as dt
from decimal import Decimal
from typing import Any

from salli.application.services.baseline_service import BaselineService
from salli.domain.accounting.ledger import build_reversing_entry
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.baseline import Baseline
from tests.fakes import FakeFx, FakeUoW

USER = "u"


class Ledger:
    """One user's books. The base currency is `base`; every account is held
    in it unless said otherwise."""

    def __init__(self, base: str = "CHF") -> None:
        self.uow = FakeUoW(base)
        self.base = base
        self.rates: dict[tuple[str, str, str | None], tuple[Any, ...]] = {}
        self._n = 0

    def account(self, id_: str, type_: str, currency: str | None = None, **kw: Any) -> str:
        self.uow.ledger.accounts.append(
            Account(
                id=id_,
                user_id=USER,
                code=f"{len(self.uow.ledger.accounts) + 1000}",
                name=kw.pop("name", id_.title()),
                type=type_,  # type: ignore[arg-type]
                currency=currency or self.base,
                **kw,
            )
        )
        return id_

    def book(
        self,
        day: str,
        debit: str,
        credit: str,
        amount: str | Decimal,
        *,
        currency: str | None = None,
        fx: str = "1",
        description: str = "",
        tags: dict[str, str] | None = None,
    ) -> StoredJournalEntry:
        self._n += 1
        cur = currency or self.base
        legs = {"amount": Decimal(amount), "currency": cur, "fx_rate": Decimal(fx)}
        entry = StoredJournalEntry(
            id=f"e{self._n}",
            user_id=USER,
            entry_date=day,
            description=description or f"ENTRY {self._n}",
            source="statement",
            postings=[
                Posting(account_id=debit, direction=Direction.DEBIT, tags=tags or {}, **legs),
                Posting(account_id=credit, direction=Direction.CREDIT, **legs),
            ],
        )
        self.uow.ledger.entries.append(entry)
        return entry

    def reverse(self, original: StoredJournalEntry) -> StoredJournalEntry:
        """The reversing entry, as LedgerService books it: every posting
        flipped, with the original's tags, and the original marked reversed."""
        self._n += 1
        reversal = build_reversing_entry(original)
        postings = [
            p.model_copy(update={"tags": dict(o.tags)})
            for p, o in zip(reversal.postings, original.postings, strict=True)
        ]
        stored = StoredJournalEntry(
            **{**reversal.model_dump(), "postings": postings}, id=f"e{self._n}", user_id=USER
        )
        entries = self.uow.ledger.entries
        entries[entries.index(original)] = original.model_copy(update={"reversed_by": stored.id})
        entries.append(stored)
        return stored

    def debt(
        self,
        id_: str,
        principal: str,
        apr: str,
        minimum: str,
        account_id: str | None = None,
    ) -> str:
        from salli.domain.money import to_minor

        self.uow.debts.rows[id_] = {
            "id": id_,
            "user_id": USER,
            "name": id_.title(),
            "principal_minor": to_minor(Decimal(principal), self.base),
            "apr": apr,
            "minimum_payment_minor": to_minor(Decimal(minimum), self.base),
            "is_active": True,
            "account_id": account_id,
            "created_at": "",
            "updated_at": "",
        }
        return id_

    def holding(
        self,
        id_: str,
        name: str,
        *,
        symbol: str | None = None,
        currency: str | None = None,
        account_id: str | None = None,
    ) -> str:
        """A holding, as the portfolio keeps it (the person's own symbol and
        name), linked to `account_id` if given."""
        self.uow.holdings.rows[id_] = {
            "id": id_,
            "user_id": USER,
            "symbol": symbol or id_.upper(),
            "name": name,
            "asset_class": "equity",
            "currency": currency or self.base,
            "cost_basis_minor": 0,
            "current_value_minor": 0,
            "is_active": True,
            "account_id": account_id,
            "created_at": "",
            "updated_at": "",
        }
        return id_

    def trade(
        self,
        holding: str,
        kind: str,
        day: str,
        quantity: str,
        price: str,
        *,
        fees: str = "0",
        fx: str = "1",
        id_: str | None = None,
    ) -> str:
        """A buy or a sale of a holding, as the portfolio stores it."""
        from salli.domain.money import to_minor

        currency = self.uow.holdings.rows[holding]["currency"]
        self._n += 1
        tid = id_ or f"t{self._n}"
        self.uow.holding_transactions.rows[tid] = {
            **self.uow.holding_transactions.DEFAULTS,
            "id": tid,
            "user_id": USER,
            "holding_id": holding,
            "kind": kind,
            "transaction_date": day,
            "quantity": Decimal(quantity),
            "price": Decimal(price),
            "fees_minor": to_minor(Decimal(fees), currency),
            "fx_rate": Decimal(fx),
            "created_at": "",
            "updated_at": "",
        }
        return tid

    def close(self, holding: str, day: str, price: str) -> None:
        """A closing price the person recorded for a holding's symbol."""
        row = self.uow.holdings.rows[holding]
        self.uow.holding_prices.rows[f"p{len(self.uow.holding_prices.rows) + 1}"] = {
            "id": f"p{len(self.uow.holding_prices.rows) + 1}",
            "user_id": USER,
            "symbol": row["symbol"],
            "price_date": day,
            "close": Decimal(price),
            "currency": row["currency"],
            "source": "user",
        }

    def assume(self, **figures: str) -> None:
        """Set the user's own FI assumptions ("inflation", "real_return", ...)."""
        self.uow.user_profiles.rows.setdefault(USER, {})["fi_assumptions"] = {
            name: {"value": value} for name, value in figures.items()
        }

    def rate(self, currency: str, rate: str, day: str | None = None) -> None:
        self.rates[(currency, self.base, day)] = (Decimal(rate), "test-bank")

    def service(self, as_of: dt.date) -> BaselineService:
        return BaselineService(self.uow.factory(), fx=FakeFx(self.rates), today=lambda: as_of)

    def baseline(self, as_of: dt.date) -> Baseline:
        return asyncio.run(self.service(as_of).build(USER, as_of))
