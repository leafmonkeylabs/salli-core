"""
Bank connections — `/v1/bank-connections`.

A connection reads accounts at a bank through a provider (SimpleFIN today).
Its credential is stored sealed, never in the clear. Each bank account is
mapped to one of the user's Salli accounts; a sync then queues what was posted
since the last one for the same review a statement goes through: duplicates
are flagged, rules decide what they can, and nothing is booked until the user
approves it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

from salli.application.ports import BankLinkError
from salli.application.services.bank_connection_service import (
    BankConnectionNotFound,
    BankConnectionsUnavailable,
    SyncInProgress,
)
from salli.domain.currency import quantize
from salli.interfaces.api.contract import Amount
from salli.interfaces.api.deps import AppServices, CronSecret, CurrentUser

router = APIRouter(prefix="/bank-connections", tags=["bank-connections"])


class BankAccount(BaseModel):
    """An account at the bank, as the provider reports it."""

    #: The provider's id for it.
    remote_id: str
    name: str
    institution: str
    #: An ISO 4217 code, or a provider's own unit (points, miles), which no
    #: ledger account can hold.
    currency: str
    #: The bank's own balance at the last sync; null for a unit that is not
    #: a currency.
    balance: Amount | None
    balance_date: datetime | None
    #: The Salli account its transactions are imported into; null until mapped.
    account_id: str | None
    #: When its transactions were last imported in full; null before the first.
    last_imported_at: datetime | None = None
    #: Why its last import failed, if it did.
    notes: str | None = None


class BankConnection(BaseModel):
    id: str
    provider: str
    name: str
    #: "active"; "error" when the last sync failed (`last_error` says why);
    #: "attention" when it synced but the bank reported a problem
    #: (`warnings`) or an account could not be imported (`last_error`).
    status: str
    last_error: str | None
    #: What the provider asked to show the user at the last sync (an
    #: institution asking to sign in again).
    warnings: list[str] = Field(default_factory=list)
    last_synced_at: datetime | None
    created_at: datetime
    accounts: list[BankAccount]


class BankConnections(BaseModel):
    #: Whether this server can hold bank credentials (an encryption key is
    #: configured and sign-in is real).
    available: bool
    providers: list[str]
    connections: list[BankConnection]


class ConnectBank(BaseModel):
    provider: str = Field(examples=["simplefin"])
    #: What the provider hands the user to give Salli: for SimpleFIN, the
    #: setup token from the SimpleFIN Bridge. It is used once.
    setup_token: str = Field(min_length=1)
    #: Defaults to the institutions' names.
    name: str | None = Field(default=None, max_length=200)


class BankConnected(BaseModel):
    id: str
    #: What the provider said needs attention (an institution asking to sign in again).
    warnings: list[str]
    #: Why the accounts could not be read yet, when they could not: the
    #: connection is kept, and a sync can finish it without a new token.
    error: str | None = None


class MapBankAccount(BaseModel):
    """Import into `account_id` (one held in the same currency), or `create`
    an asset account named after the bank account; neither unmaps it."""

    account_id: str | None = None
    create: bool = False


class BankAccountMapping(BaseModel):
    remote_id: str
    account_id: str | None


class SyncedAccount(BaseModel):
    remote_id: str
    name: str
    #: The review batch its transactions went into, if any.
    statement_id: str | None = None
    #: New transactions queued for review.
    queued: int = 0
    #: Transactions left out as imported before: a sync overlaps the last.
    duplicates: int = 0
    #: What the import had to say: rows that still need an account, or why
    #: the model was not asked.
    notes: list[str] = Field(default_factory=list)


class BankSync(BaseModel):
    accounts: list[SyncedAccount]
    #: Bank accounts with no Salli account to import into yet.
    unmapped: list[str]
    warnings: list[str]


def _unavailable(exc: BankConnectionsUnavailable) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


def _account(a: dict[str, Any]) -> BankAccount:
    # The repository gives a balance only for a currency a ledger can hold.
    balance = a.get("balance")
    return BankAccount(
        remote_id=a["remote_id"],
        name=a["name"],
        institution=a.get("institution") or "",
        currency=a["currency"],
        balance=str(quantize(balance, a["currency"])) if balance is not None else None,
        balance_date=a.get("balance_date"),
        account_id=a.get("account_id"),
        last_imported_at=a.get("last_imported_at"),
        notes=a.get("notes"),
    )


@router.get("")
async def list_connections(user_id: CurrentUser, svc: AppServices) -> BankConnections:
    banks = svc.bank_connections
    return BankConnections(
        available=banks.available,
        providers=banks.providers,
        connections=[
            BankConnection(
                **{k: c[k] for k in ("id", "provider", "name", "status", "last_error")},
                warnings=c.get("warnings") or [],
                last_synced_at=c.get("last_synced_at"),
                created_at=c["created_at"],
                accounts=[_account(a) for a in c.get("accounts", [])],
            )
            for c in await banks.list(user_id)
        ],
    )


@router.post("", status_code=201)
async def connect(body: ConnectBank, user_id: CurrentUser, svc: AppServices) -> BankConnected:
    try:
        connected = await svc.bank_connections.connect(
            user_id, body.provider, body.setup_token, body.name
        )
    except BankConnectionsUnavailable as exc:
        raise _unavailable(exc) from exc
    except BankLinkError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BankConnected.model_validate(connected)


@router.put("/{connection_id}/accounts/{remote_id}")
async def map_account(
    connection_id: str,
    remote_id: str,
    body: MapBankAccount,
    user_id: CurrentUser,
    svc: AppServices,
) -> BankAccountMapping:
    try:
        account_id = await svc.bank_connections.map_account(
            user_id, connection_id, remote_id, body.account_id, create=body.create
        )
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such bank account") from exc
    return BankAccountMapping(remote_id=remote_id, account_id=account_id)


@router.post("/{connection_id}/sync")
async def sync(connection_id: str, user_id: CurrentUser, svc: AppServices) -> BankSync:
    try:
        result = await svc.bank_connections.sync(user_id, connection_id)
    except BankConnectionsUnavailable as exc:
        raise _unavailable(exc) from exc
    except BankConnectionNotFound as exc:
        # Only the connection's own lookup: a KeyError from deeper in a sync
        # is not a missing connection.
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such connection") from exc
    except SyncInProgress as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except BankLinkError as exc:
        # The provider refused: the connection is marked, and the user has to act.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return BankSync.model_validate(result)


class ScheduledBankSyncs(BaseModel):
    """Accepted: each due connection syncs after this response."""

    #: Connections, anyone's, due a sync: not attempted in the last 12
    #: hours (a failed one, not in the last day), and none syncing now.
    due: int
    scheduled: bool


@router.post("/cron/sync-due", status_code=status.HTTP_202_ACCEPTED, dependencies=[CronSecret])
async def cron_sync_due(svc: AppServices, background: BackgroundTasks) -> ScheduledBankSyncs:
    """Sync every connection that is due, for a scheduler (the hosted
    product's pg_cron, or a self-hoster's cron). Auth: X-Cron-Secret header."""
    banks = svc.bank_connections
    if not banks.available:
        return ScheduledBankSyncs(due=0, scheduled=False)
    due = await banks.due()
    # The same list it counts: listed once, then synced.
    background.add_task(banks.sync_due, due=due)
    return ScheduledBankSyncs(due=len(due), scheduled=True)


@router.delete("/{connection_id}", status_code=204)
async def disconnect(connection_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    if not await svc.bank_connections.disconnect(user_id, connection_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such connection")
