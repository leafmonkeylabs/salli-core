"""
ReconciliationService: a bank statement against the ledger.

A statement for reconciling is one of an asset or liability account, for a
period, with the bank's opening and closing balance (an import that carried
them, or one typed in from the bank's). The person clears the account's
postings in the period that the statement shows; the cleared total is the
opening balance plus the cleared postings, and the difference is the closing
balance less that. A reconciliation completes only at a difference of zero,
and is then recorded (who completed it, and when) and its postings stay as
they are.

Balances and amounts are in the account's own currency, in its normal
direction: what an asset account holds, what a liability account owes.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.domain.accounting.models import Account, money_account_problem
from salli.domain.currency import quantize
from salli.domain.money import from_minor, to_minor


class Reconciled(ValueError):
    """A change to a statement whose reconciliation is complete."""


def normal_sign(account: Account) -> int:
    """+1 when the account's balance grows with debits (an asset), −1 when
    with credits (a liability)."""
    return 1 if account.type == "asset" else -1


class ReconciliationService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    async def _account(self, uow: Any, user_id: str, account_id: str) -> Account:
        account = await uow.ledger.get_account(user_id, account_id)
        problem = money_account_problem(account, account_id)
        if problem is not None:
            raise ValueError(problem)
        assert account is not None
        return account

    async def add_statement(
        self,
        user_id: str,
        *,
        account_id: str,
        period_start: str,
        period_end: str,
        opening_balance: Decimal,
        closing_balance: Decimal,
        bank: str = "",
    ) -> dict[str, Any]:
        """A statement typed in from the bank's: its account, period and the
        balances it states (in the account's currency, held or owed)."""
        if period_start > period_end:
            raise ValueError("A statement's period starts before it ends")
        async with self._uow_factory() as uow:
            account = await self._account(uow, user_id, account_id)
            statement_id = await uow.reconciliations.add_statement(
                user_id,
                {
                    "account_id": account.id,
                    "period_start": period_start,
                    "period_end": period_end,
                    "opening_balance_minor": to_minor(
                        quantize(opening_balance, account.currency), account.currency
                    ),
                    "closing_balance_minor": to_minor(
                        quantize(closing_balance, account.currency), account.currency
                    ),
                    "bank": bank,
                },
            )
        status = await self.status(user_id, statement_id)
        assert status is not None
        return status

    async def list_statements(self, user_id: str) -> list[dict[str, Any]]:
        """Statements with the bank's balances, newest period first, and
        whether each is reconciled."""
        async with self._uow_factory() as uow:
            rows = await uow.reconciliations.statements(user_id)
            accounts = {a.id: a for a in await uow.ledger.get_accounts(user_id, True)}
        return [_statement_view(r, accounts[r["account_id"]]) for r in rows]

    async def status(self, user_id: str, statement_id: str) -> dict[str, Any] | None:
        """The statement, its account's postings in the period (cleared or
        not), the cleared total and the difference; None for a statement
        that isn't the user's or carries no balances."""
        async with self._uow_factory() as uow:
            return await self._status(uow, user_id, statement_id)

    async def _status(self, uow: Any, user_id: str, statement_id: str) -> dict[str, Any] | None:
        rows = await uow.reconciliations.statements(user_id, statement_id)
        if not rows:
            return None
        row = rows[0]
        account = await uow.ledger.get_account(user_id, row["account_id"])
        assert account is not None
        sign = normal_sign(account)
        currency = account.currency
        postings = await uow.reconciliations.postings(
            user_id, account.id, row["period_start"], row["period_end"]
        )
        cleared = from_minor(row["opening_balance_minor"], currency)
        lines: list[dict[str, Any]] = []
        for p in postings:
            # A posting in another currency than the account's has no amount
            # a bank statement in the account's currency could show.
            if p["currency"] != currency:
                continue
            amount = sign * p["direction"] * from_minor(p["amount_minor"], currency)
            if p["cleared"]:
                cleared += amount
            lines.append(
                {
                    "posting_id": p["posting_id"],
                    "entry_id": p["entry_id"],
                    "entry_date": p["entry_date"],
                    "description": p["description"],
                    "amount": str(amount),
                    "cleared": p["cleared"],
                }
            )
        closing = from_minor(row["closing_balance_minor"], currency)
        return {
            **_statement_view(row, account),
            "cleared_total": str(quantize(cleared, currency)),
            "difference": str(quantize(closing - cleared, currency)),
            "postings": lines,
        }

    async def clear(
        self, user_id: str, statement_id: str, posting_ids: list[str], cleared: bool = True
    ) -> dict[str, Any] | None:
        """Mark postings cleared (or not): each must be one of the statement's
        account's in its period. Refused once the reconciliation is complete
        (`Reconciled`)."""
        async with self._uow_factory() as uow:
            status = await self._status(uow, user_id, statement_id)
            if status is None:
                return None
            if status["reconciliation"] is not None:
                raise Reconciled("This statement is reconciled: its postings stay as they are.")
            mine = {p["posting_id"] for p in status["postings"]}
            stray = [p for p in posting_ids if p not in mine]
            if stray:
                raise ValueError(
                    f"Not a posting on this statement's account in its period: {', '.join(stray)}"
                )
            await uow.reconciliations.set_cleared(user_id, posting_ids, cleared)
            return await self._status(uow, user_id, statement_id)

    async def complete(
        self, user_id: str, statement_id: str, completed_by: str
    ) -> dict[str, Any] | None:
        """Record the reconciliation, only at a difference of zero (ValueError
        otherwise, saying what is left), and only once (`Reconciled`)."""
        async with self._uow_factory() as uow:
            status = await self._status(uow, user_id, statement_id)
            if status is None:
                return None
            if status["reconciliation"] is not None:
                raise Reconciled("This statement is already reconciled.")
            if Decimal(status["difference"]) != 0:
                raise ValueError(
                    f"The cleared postings are {status['difference']} {status['currency']} "
                    "short of the closing balance: a reconciliation completes only at a "
                    "difference of zero."
                )
            currency = status["currency"]
            await uow.reconciliations.complete(
                user_id,
                {
                    "statement_id": statement_id,
                    "cleared_total_minor": to_minor(Decimal(status["cleared_total"]), currency),
                    "difference_minor": 0,
                    "completed_by": completed_by,
                },
            )
            return await self._status(uow, user_id, statement_id)


def _statement_view(row: dict[str, Any], account: Account) -> dict[str, Any]:
    currency = account.currency
    done = row["reconciliation"]
    return {
        "statement_id": row["id"],
        "account_id": account.id,
        "account_name": account.name,
        "currency": currency,
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "opening_balance": str(from_minor(row["opening_balance_minor"], currency)),
        "closing_balance": str(from_minor(row["closing_balance_minor"], currency)),
        "reconciliation": None
        if done is None
        else {
            "cleared_total": str(from_minor(done["cleared_total_minor"], currency)),
            "difference": str(from_minor(done["difference_minor"], currency)),
            "completed_by": done["completed_by"],
            "completed_at": done["completed_at"],
        },
    }
