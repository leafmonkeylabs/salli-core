"""
SimpleFIN (https://www.simplefin.org/protocol.html): read-only access to
people's bank accounts, through a bridge such as SimpleFIN Bridge.

The user gets a setup token from the bridge and pastes it in. The token is a
base64-encoded claim URL; claiming it (one POST, once) returns an access URL
with Basic Auth credentials in it, which is the credential Salli keeps,
encrypted. Every sync is then `GET {access URL}/accounts`.

Amounts arrive as decimal strings and stay Decimals; nothing passes through a
float. Messages from the bridge are shown to the user, so they are stripped to
plain printable text first, as the protocol asks.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from salli.application.ports import (
    BankConnector,
    BankLinkError,
    BankSnapshot,
    RemoteAccount,
    RemoteTransaction,
)

_UNPRINTABLE = re.compile(r"[^\x20-\x7E -￿]")


def _clean(text: Any, limit: int = 300) -> str:
    return _UNPRINTABLE.sub("", str(text))[:limit]


def _day(epoch: Any) -> str:
    return dt.datetime.fromtimestamp(int(epoch), dt.UTC).date().isoformat()


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise BankLinkError(f"SimpleFIN sent an amount that is not a number: {value!r}") from None


class SimpleFinConnector(BankConnector):
    provider = "simplefin"

    def __init__(self, timeout: float = 60.0, transport: httpx.AsyncBaseTransport | None = None):
        self._timeout = timeout
        self._transport = transport

    def _client(self, **kwargs: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport, **kwargs)

    async def link(self, setup: str) -> str:
        try:
            claim_url = base64.b64decode(setup.strip(), validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            raise BankLinkError("That is not a SimpleFIN setup token") from None
        if not claim_url.startswith("https://"):
            raise BankLinkError("A SimpleFIN setup token must point to an https address")
        try:
            async with self._client() as client:
                resp = await client.post(claim_url)
        except httpx.HTTPError as exc:
            raise BankLinkError(f"Could not reach SimpleFIN: {exc}") from exc
        if resp.status_code == 403:
            raise BankLinkError(
                "SimpleFIN refused this token: it was already used, or never existed. "
                "If you didn't use it yourself, disable it at your SimpleFIN bridge."
            )
        if resp.status_code != 200:
            raise BankLinkError(f"SimpleFIN answered HTTP {resp.status_code}")
        access_url = resp.text.strip()
        if not access_url.startswith("https://"):
            raise BankLinkError("SimpleFIN returned an access address Salli can't use")
        return access_url

    async def fetch(
        self, credential: str, start: dt.datetime | None, balances_only: bool = False
    ) -> BankSnapshot:
        parts = urlsplit(credential)
        auth = (parts.username or "", parts.password or "")
        # The same address without the credentials in it; they go as Basic Auth.
        host = parts.netloc.rsplit("@", 1)[-1]
        base = urlunsplit((parts.scheme, host, parts.path, "", ""))
        params: dict[str, str] = {"version": "2"}
        if start is not None:
            params["start-date"] = str(int(start.timestamp()))
        if balances_only:
            params["balances-only"] = "1"
        try:
            async with self._client(auth=auth) as client:
                resp = await client.get(f"{base.rstrip('/')}/accounts", params=params)
        except httpx.HTTPError as exc:
            raise BankLinkError(f"Could not reach SimpleFIN: {exc}") from exc
        if resp.status_code == 403:
            raise BankLinkError("SimpleFIN access was revoked; connect this bank again")
        if resp.status_code == 402:
            raise BankLinkError("Your SimpleFIN subscription needs attention at the bridge")
        if resp.status_code != 200:
            raise BankLinkError(f"SimpleFIN answered HTTP {resp.status_code}")
        data = json.loads(resp.text, parse_float=Decimal)
        return _snapshot(data)


def _snapshot(data: dict[str, Any]) -> BankSnapshot:
    connections = {c.get("conn_id"): c for c in data.get("connections") or []}
    accounts: list[RemoteAccount] = []
    transactions: list[RemoteTransaction] = []
    for raw in data.get("accounts") or []:
        conn = connections.get(raw.get("conn_id")) or {}
        org = raw.get("org") or {}  # version 1 servers
        institution = conn.get("name") or conn.get("org_name") or org.get("name") or ""
        remote_id = str(raw["id"])
        balance_date = raw.get("balance-date")
        accounts.append(
            RemoteAccount(
                remote_id=remote_id,
                name=_clean(raw.get("name") or remote_id, 100),
                institution=_clean(institution, 100),
                # A URL here is a custom currency (points, a token); those are
                # not money a ledger posts, and sync skips them.
                currency=str(raw.get("currency") or ""),
                balance=_decimal(raw.get("balance", "0")),
                balance_date=dt.datetime.fromtimestamp(int(balance_date), dt.UTC)
                if balance_date
                else None,
            )
        )
        for txn in raw.get("transactions") or []:
            if txn.get("pending") or not txn.get("posted"):
                continue  # only what the bank has settled
            transactions.append(
                RemoteTransaction(
                    remote_id=str(txn["id"]),
                    account_remote_id=remote_id,
                    posted=_day(txn["posted"]),
                    amount=_decimal(txn["amount"]),
                    description=_clean(txn.get("description") or txn.get("payee") or "", 300),
                )
            )
    warnings = [_clean(e.get("msg", "")) for e in data.get("errlist") or [] if e.get("msg")]
    warnings += [_clean(e) for e in data.get("errors") or [] if isinstance(e, str)]
    return BankSnapshot(
        accounts=accounts, transactions=transactions, warnings=list(dict.fromkeys(warnings))
    )
