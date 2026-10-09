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

import hmac
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from salli.application.ports import BankLinkError
from salli.application.services.bank_connection_service import BankConnectionsUnavailable
from salli.config import Settings, get_settings
from salli.domain.currency import is_currency, quantize
from salli.interfaces.api.contract import Amount
from salli.interfaces.api.deps import AppServices, CurrentUser

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


class BankConnection(BaseModel):
    id: str
    provider: str
    name: str
    #: "error" when the last sync failed: `last_error` says why.
    status: str
    last_error: str | None
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
    balance = a.get("balance")
    currency = a["currency"]
    return BankAccount(
        remote_id=a["remote_id"],
        name=a["name"],
        institution=a.get("institution") or "",
        currency=currency,
        balance=(
            str(quantize(balance, currency))
            if balance is not None and is_currency(currency)
            else None
        ),
        balance_date=a.get("balance_date"),
        account_id=a.get("account_id"),
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
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such connection") from exc
    except BankLinkError as exc:
        # The provider refused: the connection is marked, and the user has to act.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return BankSync.model_validate(result)


class ScheduledBankSyncs(BaseModel):
    """Accepted: each due connection syncs after this response."""

    #: Connections, anyone's, not synced in the last 12 hours.
    due: int
    scheduled: bool


@router.post("/cron/sync-due", status_code=status.HTTP_202_ACCEPTED)
async def cron_sync_due(
    svc: AppServices,
    settings: Annotated[Settings, Depends(get_settings)],
    background: BackgroundTasks,
    x_cron_secret: Annotated[str | None, Header()] = None,
) -> ScheduledBankSyncs:
    """Sync every connection that is due, for a scheduler (the hosted
    product's pg_cron, or a self-hoster's cron). Auth: X-Cron-Secret header."""
    secret = settings.cron_secret
    if not secret or not x_cron_secret or not hmac.compare_digest(x_cron_secret, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cron secret")
    banks = svc.bank_connections
    if not banks.available:
        return ScheduledBankSyncs(due=0, scheduled=False)
    due = await banks.due()
    background.add_task(banks.sync_due)
    return ScheduledBankSyncs(due=len(due), scheduled=True)


@router.delete("/{connection_id}", status_code=204)
async def disconnect(connection_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    if not await svc.bank_connections.disconnect(user_id, connection_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such connection")
