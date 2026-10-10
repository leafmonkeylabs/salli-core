"""Fetching a user's URL (a rule set to import) without letting it reach Salli's
own network: the SSRF guard and the fetch built on it."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from salli.adapters.net.fetch import GuardedFetcher
from salli.adapters.net.guard import is_public
from salli.application.ports import FetchRefused

PUBLIC = "93.184.215.14"


def _resolver(table: dict[str, list[str]]):
    async def resolve(host: str, port: int) -> list[str]:
        if host not in table:
            raise OSError("no such host")
        return table[host]

    return resolve


def _fetcher(handler, table=None, **kwargs) -> GuardedFetcher:
    return GuardedFetcher(
        transport=httpx.MockTransport(handler),
        resolver=_resolver(table if table is not None else {"rules.example": [PUBLIC]}),
        **kwargs,
    )


def _never(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"no request should have been made, but {request.url} was")


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",  # cloud metadata
        "100.64.0.1",  # shared address space (CGNAT)
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "::ffff:127.0.0.1",  # IPv4-mapped
        "64:ff9b::a00:1",  # NAT64 of 10.0.0.1
        "2002:7f00:1::",  # 6to4 of 127.0.0.1
    ],
)
def test_addresses_off_the_public_internet_are_not_public(address):
    assert not is_public(address)


def test_public_addresses_are_public():
    assert is_public(PUBLIC)
    assert is_public("2606:4700:4700::1111")
    assert is_public("64:ff9b::808:808")  # NAT64 of 8.8.8.8


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://rules.example/xa.json", "Only https"),
        ("ftp://rules.example/xa.json", "Only https"),
        ("https://user:pw@rules.example/xa.json", "user name or password"),
        ("https://127.0.0.1/xa.json", "not on the public internet"),
        ("https://[::1]/xa.json", "not on the public internet"),
        ("https://internal.example/xa.json", "not on the public internet"),
        ("https://mixed.example/xa.json", "not on the public internet"),
        ("https://nowhere.example/xa.json", "could not be reached"),
    ],
)
async def test_a_url_that_could_reach_salli_s_own_network_is_refused_before_any_request(
    url, message
):
    table = {
        "rules.example": [PUBLIC],
        "internal.example": ["10.0.0.5"],
        # One private answer among public ones is enough to refuse.
        "mixed.example": [PUBLIC, "192.168.0.10"],
    }
    with pytest.raises(FetchRefused, match=message):
        await _fetcher(_never, table).fetch_text(url)


async def test_the_request_goes_to_the_address_that_was_checked():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text='{"schema": "salli.tax/1"}')

    fetched = await _fetcher(handler).fetch_text("https://rules.example/sets/xa.json?v=2")
    assert fetched.text == '{"schema": "salli.tax/1"}'
    assert fetched.url == "https://rules.example/sets/xa.json?v=2"
    [request] = seen
    # Not resolved again by the HTTP client: the checked IP, with the name in
    # the Host header and in TLS, where the certificate is checked against it.
    assert request.url.host == PUBLIC
    assert request.url.path == "/sets/xa.json" and request.url.query == b"v=2"
    assert request.headers["host"] == "rules.example"
    assert request.extensions["sni_hostname"] == "rules.example"


async def test_a_redirect_to_a_private_address_is_refused():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://internal.example/secret"})

    table = {"rules.example": [PUBLIC], "internal.example": ["10.0.0.5"]}
    with pytest.raises(FetchRefused, match="not on the public internet"):
        await _fetcher(handler, table).fetch_text("https://rules.example/xa.json")


async def test_a_redirect_to_another_public_address_is_followed_and_checked_again():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers["host"] == "rules.example":
            return httpx.Response(301, headers={"location": "https://cdn.example/xa.json"})
        assert request.url.host == "1.1.1.1"
        return httpx.Response(200, text="{}")

    table = {"rules.example": [PUBLIC], "cdn.example": ["1.1.1.1"]}
    fetched = await _fetcher(handler, table).fetch_text("https://rules.example/xa.json")
    assert fetched.url == "https://cdn.example/xa.json"


async def test_endless_redirects_are_refused():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/again"})

    with pytest.raises(FetchRefused, match="redirected more than"):
        await _fetcher(handler).fetch_text("https://rules.example/xa.json")


async def test_a_document_over_the_limit_is_refused_whether_or_not_it_says_so():
    def declared(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-length": "999999"}, content=b"{}")

    with pytest.raises(FetchRefused, match="larger than 100 bytes"):
        await _fetcher(declared, max_bytes=100).fetch_text("https://rules.example/xa.json")

    async def chunks():
        for _ in range(2):
            yield b"x" * 60

    def streamed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=chunks())

    with pytest.raises(FetchRefused, match="larger than 100 bytes"):
        await _fetcher(streamed, max_bytes=100).fetch_text("https://rules.example/xa.json")


async def test_the_whole_exchange_has_a_time_limit():
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return httpx.Response(200, text="{}")

    with pytest.raises(FetchRefused, match="longer than 0.05s"):
        await _fetcher(slow, timeout=0.05).fetch_text("https://rules.example/xa.json")


async def test_errors_never_describe_the_network():
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused by 93.184.215.14:443")

    with pytest.raises(FetchRefused) as raised:
        await _fetcher(refused).fetch_text("https://rules.example/xa.json")
    assert str(raised.value) == "The address could not be reached"


async def test_only_a_200_with_utf8_text_is_read():
    with pytest.raises(FetchRefused, match="HTTP 404"):
        await _fetcher(lambda r: httpx.Response(404)).fetch_text("https://rules.example/x")
    with pytest.raises(FetchRefused, match="not UTF-8"):
        await _fetcher(lambda r: httpx.Response(200, content=b"\xff\xfe{")).fetch_text(
            "https://rules.example/x"
        )
