"""
Bank reconciliation: a statement's closing balance against the ledger's
cleared postings (application/services/reconciliation_service.py).

GET  /reconciliation/statements                — statements with the bank's balances
POST /reconciliation/statements                — one typed in from the bank's
GET  /reconciliation/statements/{id}           — its postings, cleared total and difference
POST /reconciliation/statements/{id}/clear     — mark postings cleared, or not
POST /reconciliation/statements/{id}/complete  — record it, at a difference of zero
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from salli.interfaces.api.contract import Amount, AmountIn, CurrencyCode
from salli.interfaces.api.deps import AppServices, CurrentPrincipal, CurrentUser

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


class Reconciliation(BaseModel):
    """A completed reconciliation: recorded only at a difference of zero."""

    cleared_total: Amount
    difference: Amount
    #: Who completed it: how they signed in, or the client that did.
    completed_by: str
    completed_at: str


class ReconcilableStatement(BaseModel):
    statement_id: str
    account_id: str
    account_name: str
    #: The account's currency: every amount here is in it.
    currency: CurrencyCode
    period_start: str
    period_end: str
    #: As the bank states them, in the account's normal direction: what an
    #: asset account holds, what a liability account owes.
    opening_balance: Amount
    closing_balance: Amount
    #: Null until it is complete.
    reconciliation: Reconciliation | None


class ReconcilableStatementList(BaseModel):
    statements: list[ReconcilableStatement]


class ReconcilingPosting(BaseModel):
    posting_id: str
    entry_id: str
    entry_date: str
    description: str
    #: What it adds to the account's balance, in its normal direction.
    amount: Amount
    #: Matched to a line of the statement.
    cleared: bool


class ReconciliationStatus(ReconcilableStatement):
    #: The opening balance plus the cleared postings.
    cleared_total: Amount
    #: The closing balance less the cleared total: zero to complete.
    difference: Amount
    #: The account's postings in the period, in the account's currency.
    postings: list[ReconcilingPosting]


class StatementBalancesRequest(BaseModel):
    #: An asset or liability account.
    account_id: str
    period_start: dt.date
    period_end: dt.date
    #: As the bank's statement states them, held (an asset) or owed (a liability).
    opening_balance: AmountIn
    closing_balance: AmountIn
    bank: str = Field(default="", max_length=100)


class ClearRequest(BaseModel):
    posting_ids: list[str] = Field(min_length=1, max_length=500)
    #: False un-clears them.
    cleared: bool = True


def _found(result: dict | None) -> ReconciliationStatus:
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Statement not found")
    return ReconciliationStatus.model_validate(result)


@router.get("/statements")
async def list_statements(user_id: CurrentUser, svc: AppServices) -> ReconcilableStatementList:
    """Statements that carry the bank's opening and closing balances (an
    import that had them, or one typed in), newest period first."""
    return ReconcilableStatementList.model_validate(
        {"statements": await svc.reconciliation.list_statements(user_id)}
    )


@router.post("/statements", status_code=status.HTTP_201_CREATED)
async def add_statement(
    body: StatementBalancesRequest, user_id: CurrentUser, svc: AppServices
) -> ReconciliationStatus:
    """A statement typed in from the bank's: its account, period and balances."""
    return _found(
        await svc.reconciliation.add_statement(
            user_id,
            account_id=body.account_id,
            period_start=body.period_start.isoformat(),
            period_end=body.period_end.isoformat(),
            opening_balance=body.opening_balance,
            closing_balance=body.closing_balance,
            bank=body.bank,
        )
    )


@router.get("/statements/{statement_id}")
async def get_status(
    statement_id: str, user_id: CurrentUser, svc: AppServices
) -> ReconciliationStatus:
    """The statement's account's postings in its period, the cleared total
    and the difference from the closing balance."""
    return _found(await svc.reconciliation.status(user_id, statement_id))


@router.post("/statements/{statement_id}/clear")
async def clear(
    statement_id: str, body: ClearRequest, user_id: CurrentUser, svc: AppServices
) -> ReconciliationStatus:
    """Mark postings cleared (matched to the statement's lines), or not.
    Refused once the reconciliation is complete (409)."""
    return _found(
        await svc.reconciliation.clear(user_id, statement_id, body.posting_ids, body.cleared)
    )


@router.post("/statements/{statement_id}/complete")
async def complete(
    statement_id: str, principal: CurrentPrincipal, user_id: CurrentUser, svc: AppServices
) -> ReconciliationStatus:
    """Record the reconciliation: only at a difference of zero (422
    otherwise), once (409)."""
    by = principal.client_id or principal.method or "user"
    return _found(await svc.reconciliation.complete(user_id, statement_id, by))
