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

import asyncio
import datetime as dt
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol

from salli.application.ports import BankConnector, BankLinkError, RemoteTransaction
from salli.domain.accounting.models import money_account_problem
from salli.domain.currency import is_currency
from salli.domain.parsing.models import RawRow

_log = logging.getLogger(__name__)

#: How far back an account's first import reaches, and how much each later
#: one overlaps the last (banks post late; duplicates are dropped by the
#: bank's own id).
_FIRST_SYNC_DAYS = 90
_OVERLAP_DAYS = 7
#: How long a sync holds its connection: longer than any sync takes, short
#: enough that a crashed one does not hold it for long.
_CLAIM = dt.timedelta(minutes=15)
#: Scheduled syncs at once, across every user.
_CONCURRENCY = 8
#: A connection whose last attempt failed is retried at most this often.
_RETRY_FAILED = dt.timedelta(days=1)


class BankConnectionsUnavailable(RuntimeError):
    """A bank credential cannot be held safely here: no encryption key is
    configured, or authentication is the development fallback."""


class BankConnectionNotFound(LookupError):
    """No such connection for this user."""


class SyncInProgress(RuntimeError):
    """Another sync of this connection is running."""


class RowImporter(Protocol):
    def __call__(
        self, user_id: str, rows: list[RawRow], *, bank: str, account_id: str
    ) -> Awaitable[dict[str, Any]]: ...


def _aad(user_id: str, connection_id: str) -> str:
    # Binds the sealed credential to its row: moved to another user's row, or
    # another connection's, it does not decrypt.
    return f"{user_id}|bank:{connection_id}"


def to_rows(
    transactions: list[RemoteTransaction], currency: str, provider: str = ""
) -> list[RawRow]:
    """A feed's transactions as rows to import: each carries the provider's
    own id for it, an id from this feed and no other source."""
    return [
        RawRow(
            date=t.posted,
            description=t.description or "(no description)",
            amount=abs(t.amount),
            credit_flag=t.amount > 0,
            currency=currency,
            bank_ref=t.remote_id,
            ref_kind="id",
            ref_source=f"feed:{provider}" if provider else "feed",
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
        # False while any caller can name any user id (the development
        # fallback, `config.auth_can_hold_secrets`): they could read anyone's bank.
        auth_is_real: bool = True,
        clock: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC),
    ) -> None:
        self._uow_factory = uow_factory
        self._keyring = keyring
        self._connectors = dict(connectors)
        self._importer = importer
        self._auth_is_real = auth_is_real
        self._now = clock

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
        accounts the provider can see (with their balances).

        The token works once, so the credential is stored the moment it is
        claimed. If reading the accounts then fails, the connection is kept,
        marked with why, so a later sync can finish the job instead of the
        user needing a new token."""
        self._require_available()
        connector = self._connector(provider)
        credential = await connector.link(setup)
        connection_id = str(uuid.uuid4())
        sealed, version = self._keyring.seal(credential, aad=_aad(user_id, connection_id))
        async with self._uow_factory() as uow:
            await uow.bank_connections.create(
                user_id,
                {
                    "id": connection_id,
                    "provider": provider,
                    "name": (name or provider)[:200],
                    "credential_sealed": sealed,
                    "key_version": version,
                },
            )
        try:
            snapshot = await connector.fetch(credential, start=None, balances_only=True)
        except BankLinkError as exc:
            async with self._uow_factory() as uow:
                await uow.bank_connections.update(
                    user_id, connection_id, {"status": "error", "last_error": str(exc)}
                )
            return {"id": connection_id, "warnings": [], "error": str(exc)}
        institutions = sorted({a.institution for a in snapshot.accounts if a.institution})
        async with self._uow_factory() as uow:
            fields: dict[str, Any] = {
                "warnings": snapshot.warnings,
                "status": "attention" if snapshot.warnings else "active",
            }
            if not name and institutions:
                fields["name"] = ", ".join(institutions)[:200]
            await uow.bank_connections.update(user_id, connection_id, fields)
            await uow.bank_connections.upsert_accounts(user_id, connection_id, snapshot.accounts)
        return {"id": connection_id, "warnings": snapshot.warnings, "error": None}

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
        """Feed a bank account into a Salli account — an existing bank, cash
        or card account held in the same currency, or (create=True) a new
        asset account named after it. account_id=None and create=False
        unmaps it. KeyError for a bank account that isn't there; ValueError
        for a Salli account that can't take it."""
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
                        currency=remote["currency"],
                    ),
                )
            elif account_id:
                account = await uow.ledger.get_account(user_id, account_id)
                # The same rule a statement's account follows: every sync into
                # an expense account would fail.
                problem = money_account_problem(account, account_id)
                if problem is not None or account is None:
                    raise ValueError(problem)
                if account.currency != remote["currency"]:
                    raise ValueError(
                        f"{remote['name']} is in {remote['currency']} but that account is held in "
                        f"{account.currency}; map it to an account in the same currency, or let "
                        "Salli create one"
                    )
            await uow.bank_connections.map_account(user_id, connection_id, remote_id, account_id)
        return account_id

    async def sync(self, user_id: str, connection_id: str) -> dict[str, Any]:
        """Fetch what was posted since each mapped account's last import and
        queue it for review.

        The connection is held while this runs: a second sync of it is
        refused (SyncInProgress), never a second copy of every transaction.
        An account whose import fails is noted on it and the rest carry on;
        an account whose institution reported a problem is imported, but its
        marker stays where it was, so the next sync covers the same days
        again rather than leaving a gap."""
        self._require_available()
        if self._importer is None:
            raise RuntimeError("No importer configured for bank transactions")
        now = self._now()
        async with self._uow_factory() as uow:
            secret = await uow.bank_connections.get_secret(user_id, connection_id)
            if secret is None:
                raise BankConnectionNotFound(connection_id)
            claimed = await uow.bank_connections.claim(user_id, connection_id, now, now + _CLAIM)
        if not claimed:
            raise SyncInProgress("This bank is syncing already; try again in a moment")
        try:
            return await self._sync(user_id, connection_id, secret, now)
        finally:
            async with self._uow_factory() as uow:
                await uow.bank_connections.release(user_id, connection_id)

    async def _sync(
        self, user_id: str, connection_id: str, secret: dict[str, Any], now: dt.datetime
    ) -> dict[str, Any]:
        assert self._importer is not None
        credential = self._keyring.open(
            secret["credential_sealed"],
            aad=_aad(user_id, connection_id),
            key_version=secret["key_version"],
        )
        mapped = {a["remote_id"]: a for a in secret["accounts"] if a["account_id"]}
        # From the earliest day any mapped account needs: a newly mapped one
        # gets the first sync's window, the others a week before their last.
        starts = [
            a["last_imported_at"] - dt.timedelta(days=_OVERLAP_DAYS)
            if a.get("last_imported_at")
            else now - dt.timedelta(days=_FIRST_SYNC_DAYS)
            for a in mapped.values()
        ]
        start = min(starts) if starts else now - dt.timedelta(days=_OVERLAP_DAYS)
        provider = secret["provider"]
        try:
            snapshot = await self._connector(provider).fetch(
                credential, start=start, balances_only=not mapped
            )
        except BankLinkError as exc:
            async with self._uow_factory() as uow:
                await uow.bank_connections.update(
                    user_id, connection_id, {"status": "error", "last_error": str(exc)}
                )
            raise

        results: list[dict[str, Any]] = []
        failures: list[str] = []
        for remote in snapshot.accounts:
            target = mapped.get(remote.remote_id)
            if target is None or not is_currency(remote.currency):
                continue
            rows = to_rows(
                [t for t in snapshot.transactions if t.account_remote_id == remote.remote_id],
                remote.currency,
                provider,
            )
            label = f"{remote.institution or secret['name']} · {remote.name}"
            try:
                imported = await self._importer(
                    user_id, rows, bank=label, account_id=target["account_id"]
                )
            except Exception as exc:
                # One account's failure (its Salli account closed, a model or
                # database error) is that account's: noted on it, and the
                # others are imported as usual.
                note = (
                    f"Could not import: {exc}"
                    if isinstance(exc, ValueError)
                    else (f"Could not import ({type(exc).__name__})")
                )
                if not isinstance(exc, ValueError):
                    _log.exception("bank_import_failed connection=%s", connection_id)
                failures.append(f"{remote.name}: {note}")
                async with self._uow_factory() as uow:
                    await uow.bank_connections.update_account(
                        user_id, connection_id, remote.remote_id, {"notes": note}
                    )
                results.append(
                    {"remote_id": remote.remote_id, "name": remote.name, "notes": [note]}
                )
                continue
            troubled = remote.remote_id in snapshot.troubled
            fields: dict[str, Any] = {"notes": None}
            if not troubled:
                fields["last_imported_at"] = now
            async with self._uow_factory() as uow:
                await uow.bank_connections.update_account(
                    user_id, connection_id, remote.remote_id, fields
                )
            notes = list(imported.get("notes", []))
            if troubled:
                notes.append(
                    "The bank reported a problem with this account; the same days will be "
                    "fetched again next time"
                )
            results.append(
                {"remote_id": remote.remote_id, "name": remote.name, **imported, "notes": notes}
            )

        attention = bool(snapshot.warnings or failures)
        async with self._uow_factory() as uow:
            await uow.bank_connections.upsert_accounts(user_id, connection_id, snapshot.accounts)
            await uow.bank_connections.update(
                user_id,
                connection_id,
                {
                    "status": "attention" if attention else "active",
                    "last_error": "; ".join(failures) or None,
                    "warnings": snapshot.warnings,
                    "last_synced_at": now,
                },
            )
        unmapped = [a.name for a in snapshot.accounts if a.remote_id not in mapped]
        return {"accounts": results, "unmapped": unmapped, "warnings": snapshot.warnings}

    async def due(self, max_age: dt.timedelta = dt.timedelta(hours=12)) -> list[tuple[str, str]]:
        """(user id, connection id) of every connection due a sync: not
        attempted within `max_age`, not held by a sync running now, and, if
        its last attempt failed, not attempted in the last day."""
        now = self._now()
        async with self._uow_factory() as uow:
            return await uow.bank_connections.list_due(now - max_age, now - _RETRY_FAILED, now)

    async def sync_due(
        self,
        max_age: dt.timedelta = dt.timedelta(hours=12),
        due: list[tuple[str, str]] | None = None,
    ) -> dict[str, int]:
        """Sync every connection due (`due`, or those `self.due(max_age)`
        lists), anyone's: what a scheduler calls. Up to eight at once. One
        that fails is recorded on its connection (as any failed sync is) and
        the rest carry on; one another sync holds is left to it."""
        self._require_available()
        if due is None:
            due = await self.due(max_age)
        gate = asyncio.Semaphore(_CONCURRENCY)

        async def one(user_id: str, connection_id: str) -> str:
            async with gate:
                try:
                    await self.sync(user_id, connection_id)
                except SyncInProgress:
                    return "skipped"
                except BankLinkError:
                    return "failed"  # recorded on the connection by sync()
                except Exception:
                    _log.exception("bank_sync_failed connection=%s", connection_id)
                    return "failed"
                return "synced"

        outcomes = await asyncio.gather(*(one(u, c) for u, c in due))
        return {
            "due": len(due),
            "synced": outcomes.count("synced"),
            "failed": outcomes.count("failed"),
            "skipped": outcomes.count("skipped"),
        }

    async def disconnect(self, user_id: str, connection_id: str) -> bool:
        """Forget the connection and its credential. Booked entries stay."""
        async with self._uow_factory() as uow:
            return await uow.bank_connections.delete(user_id, connection_id)
