"""
Fetching a text document from a URL a user gave (a tax rule set to import),
behind the SSRF guard (guard.py).

Each request:

- goes only to an https URL whose host resolves entirely to public addresses
  (`guard.vet`), and connects to one of the addresses that were checked: the
  request is sent to the IP itself, with the host name in the `Host` header
  and in TLS (SNI, and the certificate is verified against it). Resolving the
  name a second time, as an HTTP client would, could get a different answer
  (DNS rebinding);
- follows at most a few redirects, each vetted like the first, so a public
  address can't hand the request on to a private one;
- reads at most `max_bytes` (refusing a larger `Content-Length` before
  reading), and gives up after `timeout` seconds for the whole exchange, not
  per read, so a server trickling bytes can't hold it open;
- decodes the body as UTF-8, the encoding JSON requires.

Every failure is a FetchRefused whose message is the user's to read: it never
says what a host resolved to or which connection failed.
"""

from __future__ import annotations

import asyncio
import ipaddress
from urllib.parse import urljoin, urlunsplit

import httpx

from salli.adapters.net.guard import Resolver, UnsafeAddress, VettedUrl, resolve_host, vet
from salli.application.ports import DocumentFetcher, FetchedDocument, FetchRefused

MAX_REDIRECTS = 3


def _pinned(target: VettedUrl) -> tuple[str, str]:
    """(URL with the checked address in place of the host, Host header)."""
    ip = ipaddress.ip_address(target.addresses[0].split("%", 1)[0])
    literal = f"[{ip}]" if ip.version == 6 else str(ip)
    netloc = literal if target.port == 443 else f"{literal}:{target.port}"
    host_header = target.host if target.port == 443 else f"{target.host}:{target.port}"
    parts = target.parts
    return urlunsplit(("https", netloc, parts.path or "/", parts.query, "")), host_header


class GuardedFetcher(DocumentFetcher):
    def __init__(
        self,
        *,
        max_bytes: int = 1_048_576,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Resolver = resolve_host,
    ) -> None:
        self._max_bytes = max_bytes
        self._timeout = timeout
        self._transport = transport
        self._resolve = resolver

    async def fetch_text(self, url: str) -> FetchedDocument:
        try:
            async with asyncio.timeout(self._timeout):
                return await self._fetch(url)
        except TimeoutError:
            raise FetchRefused(
                f"The address took longer than {self._timeout:g}s to answer"
            ) from None

    async def _fetch(self, url: str) -> FetchedDocument:
        async with httpx.AsyncClient(
            transport=self._transport,
            follow_redirects=False,
            timeout=self._timeout,
            # Never the environment's proxies: a proxy would resolve the name
            # itself, undoing the check.
            trust_env=False,
        ) as client:
            current = url
            for _ in range(MAX_REDIRECTS + 1):
                try:
                    target = await vet(current, self._resolve)
                except UnsafeAddress as refused:
                    raise FetchRefused(str(refused)) from None
                status, location, body = await self._get(client, target)
                if status in (301, 302, 303, 307, 308) and location:
                    current = urljoin(current, location)
                    continue
                if status != 200:
                    raise FetchRefused(f"The address answered HTTP {status}")
                try:
                    return FetchedDocument(current, body.decode("utf-8"))
                except UnicodeDecodeError:
                    raise FetchRefused("The document is not UTF-8 text") from None
        raise FetchRefused(f"The address redirected more than {MAX_REDIRECTS} times")

    async def _get(
        self, client: httpx.AsyncClient, target: VettedUrl
    ) -> tuple[int, str | None, bytes]:
        pinned, host_header = _pinned(target)
        try:
            async with client.stream(
                "GET",
                pinned,
                headers={"Host": host_header, "Accept": "application/json, text/plain"},
                extensions={"sni_hostname": target.host},
            ) as response:
                if response.is_redirect:
                    return response.status_code, response.headers.get("location"), b""
                declared = response.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > self._max_bytes:
                    raise FetchRefused(f"The document is larger than {self._max_bytes} bytes")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > self._max_bytes:
                        raise FetchRefused(f"The document is larger than {self._max_bytes} bytes")
                return response.status_code, None, bytes(body)
        except (httpx.HTTPError, httpx.InvalidURL):
            raise FetchRefused("The address could not be reached") from None
