"""
BankConnectionService — reading people's bank accounts through a provider.

Connecting stores the provider's credential sealed (never in the clear), and
records the accounts it can see. Each bank account is then mapped to one of
the user's Salli accounts. A sync fetches what was posted since the last one
and hands each mapped account's transactions to the same review pipeline a
statement goes through: duplicates are dropped, rules decide what they can, a
model suggests the rest, and nothing is booked until the user approves it.

The bank's own balance is kept at every sync, so the ledger can be reconciled
against it.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from decimal import Decimal
from typing import Any, Protocol

from salli.application.ports import BankConnector, BankLinkError, RemoteTransaction
from salli.domain.currency import is_currency, normalize_currency
from salli.domain.parsing.models import RawRow

_log = logging.getLogger(__name__)

#: How far back the first sync reaches, and how much each later one overlaps
#: the last (banks post late; duplicates are dropped by the bank's own id).
_FIRST_SYNC_DAYS = 90
_OVERLAP_DAYS = 7


class BankConnectionsUnavailable(RuntimeError):
    """A bank credential cannot be held safely here: no encryption key is
    configured, or authentication is the development fallback."""


class RowImporter(Protocol):
    def __call__(
        self, user_id: str, rows: list[RawRow], *, bank: str, account_id: str
    ) -> Awaitable[dict[str, Any]]: ...


def _aad(user_id: str, connection_id: str) -> str:
    # Binds the sealed credential to its row: moved to another user's row, or
    # another connection's, it does not decrypt.
    return f"{user_id}|bank:{connection_id}"


def to_rows(transactions: list[RemoteTransaction], currency: str) -> list[RawRow]:
    return [
        RawRow(
            date=t.posted,
            description=t.description or "(no description)",
            amount=abs(t.amount),
            credit_flag=t.amount > 0,
            currency=currency,
            bank_ref=t.remote_id,
        )
        for t in transactions
        if t.amount != 0
    ]


class BankConnectionService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        # The instance's AES-GCM key ring (adapters/crypto/keyring.py).
        keyring: Any,
        connectors: Mapping[str, BankConnector],
        importer: RowImporter | None = None,
        *,
        # False while "the bearer token is the user id" is in force: any
        # caller could then read anyone's bank (config.insecure_dev_auth).
        auth_is_real: bool = True,
    ) -> None:
        self._uow_factory = uow_factory
        self._keyring = keyring
        self._connectors = dict(connectors)
        self._importer = importer
        self._auth_is_real = auth_is_real

    @property
    def available(self) -> bool:
        return self._auth_is_real and self._keyring.available

    @property
    def providers(self) -> list[str]:
        return sorted(self._connectors)

    def _require_available(self) -> None:
        if not self._auth_is_real:
            raise BankConnectionsUnavailable(
                "Bank connections are off while development sign-in is on "
                "(SALLI_INSECURE_DEV_AUTH): anyone could act as anyone."
            )
        if not self._keyring.available:
            raise BankConnectionsUnavailable(
                "Connecting a bank needs an encryption key (BYOK_ENCRYPTION_KEYS), "
                "so its credential is never stored in the clear."
            )

    def _connector(self, provider: str) -> BankConnector:
        try:
            return self._connectors[provider]
        except KeyError:
            raise ValueError(
                f"Unknown bank provider {provider!r}; available: {', '.join(self.providers)}"
            ) from None

    async def connect(
        self, user_id: str, provider: str, setup: str, name: str | None = None
    ) -> dict[str, Any]:
        """Claim the setup token, store the credential sealed, and record the
        accounts the provider can see (with their balances)."""
        self._require_available()
        connector = self._connector(provider)
        credential = await connector.link(setup)
        snapshot = await connector.fetch(credential, start=None, balances_only=True)
        connection_id = str(uuid.uuid4())
        sealed, version = self._keyring.seal(credential, aad=_aad(user_id, connection_id))
        institutions = sorted({a.institution for a in snapshot.accounts if a.institution})
        async with self._uow_factory() as uow:
            await uow.bank_connections.create(
                user_id,
                {
                    "id": connection_id,
                    "provider": provider,
                    "name": (name or ", ".join(institutions) or provider)[:200],
                    "credential_sealed": sealed,
                    "key_version": version,
                },
            )
            await uow.bank_connections.upsert_accounts(user_id, connection_id, snapshot.accounts)
        return {"id": connection_id, "warnings": snapshot.warnings}

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return await uow.bank_connections.list(user_id)

    async def map_account(
        self,
        user_id: str,
        connection_id: str,
        remote_id: str,
        account_id: str | None = None,
        *,
        create: bool = False,
    ) -> str | None:
        """Feed a bank account into a Salli account — an existing one held in
        the same currency, or (create=True) a new asset account named after it.
        account_id=None and create=False unmaps it."""
        async with self._uow_factory() as uow:
            connections: list[dict[str, Any]] = await uow.bank_connections.list(user_id)
            connection = next((c for c in connections if c["id"] == connection_id), None)
            accounts: list[dict[str, Any]] = connection["accounts"] if connection else []
            remote = next((a for a in accounts if a["remote_id"] == remote_id), None)
            if remote is None:
                raise KeyError(remote_id)
            if (create or account_id) and not is_currency(remote["currency"]):
                raise ValueError(
                    f"{remote['name']} is held in {remote['currency']!r}, which is not a currency "
                    "a ledger can keep"
                )
            if create:
                from salli.domain.accounting.models import Account

                existing = {
                    a.code for a in await uow.ledger.get_accounts(user_id, include_inactive=True)
                }
                code = next(str(n) for n in range(1500, 1600) if str(n) not in existing)
                account_id = await uow.ledger.save_account(
                    user_id,
                    Account(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        code=code,
                        name=remote["name"],
                        type="asset",
                        currency=normalize_currency(remote["currency"]),
                    ),
                )
            elif account_id:
                account = await uow.ledger.get_account(user_id, account_id)
                if account is None or not account.is_active:
                    raise ValueError("That account doesn't exist or isn't active")
                if account.currency != remote["currency"].upper():
                    raise ValueError(
                        f"{remote['name']} is in {remote['currency']} but that account is held in "
                        f"{account.currency}; map it to an account in the same currency, or let "
                        "Salli create one"
                    )
            await uow.bank_connections.map_account(user_id, connection_id, remote_id, account_id)
        return account_id

    async def sync(self, user_id: str, connection_id: str) -> dict[str, Any]:
        """Fetch what was posted since the last sync and queue it for review."""
        self._require_available()
        if self._importer is None:
            raise RuntimeError("No importer configured for bank transactions")
        async with self._uow_factory() as uow:
            secret = await uow.bank_connections.get_secret(user_id, connection_id)
        if secret is None:
            raise KeyError(connection_id)
        credential = self._keyring.open(
            secret["credential_sealed"],
            aad=_aad(user_id, connection_id),
            key_version=secret["key_version"],
        )
        last: dt.datetime | None = secret["last_synced_at"]
        start = (
            last - dt.timedelta(days=_OVERLAP_DAYS)
            if last
            else dt.datetime.now(dt.UTC) - dt.timedelta(days=_FIRST_SYNC_DAYS)
        )
        try:
            snapshot = await self._connector(secret["provider"]).fetch(credential, start=start)
        except BankLinkError as exc:
            async with self._uow_factory() as uow:
                await uow.bank_connections.update(
                    user_id, connection_id, {"status": "error", "last_error": str(exc)}
                )
            raise

        mapped = {a["remote_id"]: a for a in secret["accounts"] if a["account_id"]}
        results: list[dict[str, Any]] = []
        for remote in snapshot.accounts:
            target = mapped.get(remote.remote_id)
            if target is None or not is_currency(remote.currency):
                continue
            rows = to_rows(
                [t for t in snapshot.transactions if t.account_remote_id == remote.remote_id],
                remote.currency.upper(),
            )
            imported = await self._importer(
                user_id,
                rows,
                bank=f"{remote.institution or secret['name']} · {remote.name}",
                account_id=target["account_id"],
            )
            results.append({"remote_id": remote.remote_id, "name": remote.name, **imported})

        async with self._uow_factory() as uow:
            await uow.bank_connections.upsert_accounts(user_id, connection_id, snapshot.accounts)
            await uow.bank_connections.update(
                user_id,
                connection_id,
                {"status": "active", "last_error": None, "last_synced_at": dt.datetime.now(dt.UTC)},
            )
        unmapped = [a.name for a in snapshot.accounts if a.remote_id not in mapped]
        return {"accounts": results, "unmapped": unmapped, "warnings": snapshot.warnings}

    async def due(self, max_age: dt.timedelta = dt.timedelta(hours=12)) -> list[tuple[str, str]]:
        """(user id, connection id) of every connection not synced within `max_age`."""
        async with self._uow_factory() as uow:
            return await uow.bank_connections.list_due(dt.datetime.now(dt.UTC) - max_age)

    async def sync_due(self, max_age: dt.timedelta = dt.timedelta(hours=12)) -> dict[str, int]:
        """Sync every connection, anyone's, not synced within `max_age`: what
        a scheduler calls. One that fails is recorded on its connection (as
        any failed sync is) and the rest carry on."""
        self._require_available()
        due = await self.due(max_age)
        synced = failed = 0
        for user_id, connection_id in due:
            try:
                await self.sync(user_id, connection_id)
                synced += 1
            except BankLinkError:
                failed += 1  # recorded on the connection by sync()
            except Exception:
                failed += 1
                _log.exception("bank_sync_failed connection=%s", connection_id)
        return {"due": len(due), "synced": synced, "failed": failed}

    async def disconnect(self, user_id: str, connection_id: str) -> bool:
        """Forget the connection and its credential. Booked entries stay."""
        async with self._uow_factory() as uow:
            return await uow.bank_connections.delete(user_id, connection_id)


def balance_drift(bank: Decimal | None, ledger: Decimal | None) -> Decimal | None:
    """How far the ledger is from the bank's own balance (None if unknown)."""
    if bank is None or ledger is None:
        return None
    return ledger - bank
