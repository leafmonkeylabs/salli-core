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

The setup token is the user's paste, so the address in it is untrusted: Salli
must not be made to call into its own network. Before any request, the host
of the claim URL and of the access URL it returns is resolved, and an address
that is not public (loopback, private, link-local, ULA, ...) is refused;
answers are read up to 20 MB; and a failure to connect says only that, never
the connection's details.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import datetime as dt
import ipaddress
import json
import re
import socket
from collections.abc import Awaitable, Callable
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.parse import unquote, urlsplit, urlunsplit

import httpx

from salli.application.ports import (
    BankConnector,
    BankLinkError,
    BankSnapshot,
    RemoteAccount,
    RemoteTransaction,
)
from salli.domain.currency import is_currency, normalize_currency

#: What resolves a host name to its addresses (injectable for tests).
Resolver = Callable[[str, int], Awaitable[list[str]]]

# An account set for a few years of a household's banks is a few MB.
MAX_BODY_BYTES = 20 * 1024 * 1024


async def resolve_host(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(
        host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
    )
    return [str(info[4][0]) for info in infos]


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


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

    def __init__(
        self,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Resolver = resolve_host,
    ):
        self._timeout = timeout
        self._transport = transport
        self._resolve = resolver

    def _client(self, **kwargs: Any) -> httpx.AsyncClient:
        # No redirects: a public address must not hand the request on to a
        # private one.
        return httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport, follow_redirects=False, **kwargs
        )

    async def _vet(self, url: str) -> None:
        """Refuse a URL whose host is not on the public internet."""
        try:
            parts = urlsplit(url)
            host, port = parts.hostname, parts.port or 443
        except ValueError:
            raise BankLinkError("SimpleFIN gave an address Salli can't use") from None
        if parts.scheme != "https" or not host:
            raise BankLinkError("SimpleFIN gave an address Salli can't use")
        try:
            addresses = [host] if _is_ip(host) else await self._resolve(host, port)
        except (OSError, UnicodeError):
            raise BankLinkError("Could not reach SimpleFIN") from None
        if not addresses or not all(_public(a) for a in addresses):
            raise BankLinkError("That SimpleFIN address is not on the public internet; refused")

    async def _request(self, method: str, url: str, **kwargs: Any) -> tuple[int, str]:
        """(status, body) of one request to a vetted URL, the body capped."""
        await self._vet(url)
        auth = kwargs.pop("auth", None)
        try:
            async with (
                self._client(auth=auth) as client,
                client.stream(method, url, **kwargs) as resp,
            ):
                body = bytearray()
                async for chunk in resp.aiter_bytes():
                    body += chunk
                    if len(body) > MAX_BODY_BYTES:
                        raise BankLinkError("SimpleFIN sent more than Salli reads; refused")
                return resp.status_code, body.decode("utf-8", errors="replace")
        except (httpx.HTTPError, httpx.InvalidURL):
            # Which port or host refused says nothing the user can act on,
            # and would map the server's network for whoever sent the token.
            raise BankLinkError("Could not reach SimpleFIN") from None

    async def link(self, setup: str) -> str:
        try:
            claim_url = base64.b64decode(setup.strip(), validate=True).decode("utf-8").strip()
        except (binascii.Error, UnicodeDecodeError):
            raise BankLinkError("That is not a SimpleFIN setup token") from None
        if not claim_url.startswith("https://"):
            raise BankLinkError("A SimpleFIN setup token must point to an https address")
        status, text = await self._request("POST", claim_url)
        if status == 403:
            raise BankLinkError(
                "SimpleFIN refused this token: it was already used, or never existed. "
                "If you didn't use it yourself, disable it at your SimpleFIN bridge."
            )
        if status != 200:
            raise BankLinkError(f"SimpleFIN answered HTTP {status}")
        access_url = text.strip()
        if not access_url.startswith("https://"):
            raise BankLinkError("SimpleFIN returned an access address Salli can't use")
        await self._vet(access_url)
        return access_url

    async def fetch(
        self, credential: str, start: dt.datetime | None, balances_only: bool = False
    ) -> BankSnapshot:
        try:
            parts = urlsplit(credential)
            # Percent-encoded in the URL (a "/" or "@" in a password).
            auth = (unquote(parts.username or ""), unquote(parts.password or ""))
            host = parts.netloc.rsplit("@", 1)[-1]
        except ValueError:
            raise BankLinkError("The stored SimpleFIN address can't be used") from None
        # The same address without the credentials in it; they go as Basic Auth.
        base = urlunsplit((parts.scheme, host, parts.path, "", ""))
        params: dict[str, str] = {"version": "2"}
        if start is not None:
            params["start-date"] = str(int(start.timestamp()))
        if balances_only:
            params["balances-only"] = "1"
        status, text = await self._request(
            "GET", f"{base.rstrip('/')}/accounts", params=params, auth=auth
        )
        if status == 403:
            raise BankLinkError("SimpleFIN access was revoked; connect this bank again")
        if status == 402:
            raise BankLinkError("Your SimpleFIN subscription needs attention at the bridge")
        if status != 200:
            raise BankLinkError(f"SimpleFIN answered HTTP {status}")
        try:
            data: object = json.loads(text, parse_float=Decimal)
        except ValueError as exc:
            raise BankLinkError("SimpleFIN answered with something that is not JSON") from exc
        try:
            return _snapshot(_object(data))
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            # A payload missing what the protocol promises (an account's
            # id, a transaction's date) is the provider's fault, said as
            # such; never taken for a missing connection.
            raise BankLinkError(
                f"SimpleFIN sent an account set Salli can't read ({type(exc).__name__})"
            ) from exc


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    return True


def _objects(value: object) -> list[dict[str, Any]]:
    """The objects in a JSON array; anything else there is passed over."""
    if not isinstance(value, list):
        return []
    return [cast(dict[str, Any], v) for v in cast(list[object], value) if isinstance(v, dict)]


def _object(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _currency(value: Any) -> str:
    """An ISO 4217 code, normalised once here; anything else (a custom
    currency's URL: points, miles) kept as given, which no ledger can hold."""
    text = str(value or "").strip()
    return normalize_currency(text) if is_currency(text) else text


def _snapshot(data: dict[str, Any]) -> BankSnapshot:
    connections = {c.get("conn_id"): c for c in _objects(data.get("connections"))}
    errlist = _objects(data.get("errlist"))
    # Institutions (and accounts) the bridge says it could not read in full.
    failed_connections = {e.get("conn_id") for e in errlist if e.get("conn_id")}
    failed_accounts = {str(e.get("account_id")) for e in errlist if e.get("account_id")}
    accounts: list[RemoteAccount] = []
    transactions: list[RemoteTransaction] = []
    troubled: set[str] = set()
    for raw in _objects(data.get("accounts")):
        conn = connections.get(raw.get("conn_id")) or {}
        org = _object(raw.get("org"))  # version 1 servers
        institution = conn.get("name") or conn.get("org_name") or org.get("name") or ""
        remote_id = str(raw["id"])
        if raw.get("conn_id") in failed_connections or remote_id in failed_accounts:
            troubled.add(remote_id)
        balance_date = raw.get("balance-date")
        accounts.append(
            RemoteAccount(
                remote_id=remote_id,
                name=_clean(raw.get("name") or remote_id, 100),
                institution=_clean(institution, 100),
                # A URL here is a custom currency (points, a token); those are
                # not money a ledger posts, and sync skips them.
                currency=_currency(raw.get("currency")),
                balance=_decimal(raw.get("balance", "0")),
                balance_date=dt.datetime.fromtimestamp(int(balance_date), dt.UTC)
                if balance_date
                else None,
            )
        )
        for txn in _objects(raw.get("transactions")):
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
    warnings = [_clean(str(e["msg"])) for e in errlist if e.get("msg")]
    errors = data.get("errors")
    if isinstance(errors, list):
        warnings += [_clean(e) for e in cast(list[object], errors) if isinstance(e, str)]
    return BankSnapshot(
        accounts=accounts,
        transactions=transactions,
        warnings=list(dict.fromkeys(warnings)),
        troubled=frozenset(troubled),
    )
