"""
Whether an address a user gave is one Salli may call: the guard against
server-side request forgery, shared by everything that fetches a URL from a
user (a SimpleFIN setup token, a tax rule set to import).

Such a URL is untrusted. Pointed at the server's own network (a database, a
cloud metadata endpoint, an admin port on loopback), a fetch would make Salli
reach what its users must not. So before any request:

- the scheme must be https, and the URL may not carry credentials;
- the host is resolved, and *every* address it resolves to must be on the
  public internet: not loopback, private, link-local, shared (CGNAT), unique
  local, multicast, reserved or unspecified, nor a public-looking IPv6 address
  that carries a private IPv4 one inside it (IPv4-mapped, 6to4, NAT64,
  Teredo).

`vet` returns the addresses it checked, so a caller can connect to one of
them rather than resolving the name again (which a hostile DNS server could
answer differently the second time: DNS rebinding). `fetch.GuardedFetcher`
does; the SimpleFIN connector checks first and lets its HTTP client resolve,
the narrower guard it has always had.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal
from urllib.parse import SplitResult, urlsplit

#: What resolves a host name to its addresses (injectable for tests).
Resolver = Callable[[str, int], Awaitable[list[str]]]

# NAT64's well-known prefix (RFC 6052): the IPv4 address is in the last 32 bits.
_NAT64 = ipaddress.IPv6Network("64:ff9b::/96")


Refusal = Literal["unusable", "unreachable", "not_public"]


class UnsafeAddress(Exception):
    """A URL Salli won't call. The message is safe to show the user: it never
    says what an address resolved to, or which part of a network refused.
    `reason` lets a caller say it in its own words."""

    def __init__(self, reason: Refusal, message: str) -> None:
        super().__init__(message)
        self.reason: Refusal = reason


async def resolve_host(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(
        host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
    )
    return [str(info[4][0]) for info in infos]


def is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    return True


def _global(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip.is_global and not ip.is_multicast


def is_public(address: str) -> bool:
    """Whether `address` (an IP literal) is on the public internet, including
    any IPv4 address an IPv6 one embeds."""
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address):
        embedded: list[ipaddress.IPv4Address] = []
        if ip.ipv4_mapped is not None:
            embedded.append(ip.ipv4_mapped)
        if ip.sixtofour is not None:
            embedded.append(ip.sixtofour)
        if ip.teredo is not None:
            embedded.extend(ip.teredo)
        if ip in _NAT64:
            embedded.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
        if embedded:
            return all(_global(e) for e in embedded)
    return _global(ip)


@dataclass(frozen=True)
class VettedUrl:
    url: str
    parts: SplitResult
    host: str
    port: int
    #: Every address the host resolved to, all of them public.
    addresses: tuple[str, ...]


async def vet(
    url: str, resolver: Resolver = resolve_host, *, allow_credentials: bool = False
) -> VettedUrl:
    """`url`, checked: https, no credentials (unless `allow_credentials`: a
    SimpleFIN access URL carries its own), and a host whose every address is
    public. UnsafeAddress otherwise."""
    try:
        parts = urlsplit(url)
        host, port = parts.hostname, parts.port or 443
    except ValueError:
        raise UnsafeAddress("unusable", "That address can't be used") from None
    if parts.scheme != "https" or not host:
        raise UnsafeAddress("unusable", "Only https addresses can be fetched")
    if not allow_credentials and (parts.username is not None or parts.password is not None):
        raise UnsafeAddress(
            "unusable", "An address with a user name or password in it can't be fetched"
        )
    try:
        addresses = [host] if is_ip(host) else await resolver(host, port)
    except (OSError, UnicodeError):
        raise UnsafeAddress("unreachable", "That address could not be reached") from None
    try:
        public = bool(addresses) and all(is_public(a) for a in addresses)
    except ValueError:
        public = False
    if not public:
        raise UnsafeAddress("not_public", "That address is not on the public internet; refused")
    return VettedUrl(url, parts, host, port, tuple(addresses))
