"""The loopback listener a sign-in's browser comes back to. These connect to
it over 127.0.0.1 from inside the test: nothing leaves the machine."""

from __future__ import annotations

import asyncio

import pytest

from salli.adapters.llm.loopback import LoopbackCallback


async def browser_get(port: int, target: str) -> tuple[int, str]:
    """What the browser does when it is redirected to the callback."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {target} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode())
    await writer.drain()
    response = (await reader.read()).decode()
    writer.close()
    status = int(response.split(" ", 2)[1])
    return status, response.split("\r\n\r\n", 1)[1]


async def test_the_callback_is_answered_and_handed_back():
    async with LoopbackCallback(port=0) as listener:
        assert listener.redirect_uri == f"http://127.0.0.1:{listener.port}/auth/callback"
        waiting = asyncio.create_task(listener.wait(5))

        status, _ = await browser_get(listener.port, "/favicon.ico")
        assert status == 404
        assert not waiting.done()

        status, page = await browser_get(
            listener.port, "/auth/callback?code=abc&state=xyz&client_id=oaiapp_1"
        )
        assert status == 200 and "close this tab" in page
        assert await waiting == {"code": "abc", "state": "xyz", "client_id": "oaiapp_1"}


async def test_a_taken_port_falls_back_to_a_free_one():
    async with LoopbackCallback(port=0) as first, LoopbackCallback(port=first.port) as second:
        assert second.port != first.port
        assert second.redirect_uri.startswith("http://127.0.0.1:")


async def test_a_browser_that_never_comes_back_times_out():
    async with LoopbackCallback(port=0) as listener:
        with pytest.raises(TimeoutError):
            await listener.wait(0.05)


async def test_it_listens_on_the_loopback_address_only():
    async with LoopbackCallback(port=0) as listener:
        assert listener._server is not None
        hosts = {sock.getsockname()[0] for sock in listener._server.sockets}
        assert hosts == {"127.0.0.1"}


async def test_a_callback_for_another_attempt_is_turned_away():
    """Another process on this machine reaching the port first cannot end the
    sign-in: only this attempt's state is accepted."""
    async with LoopbackCallback(port=0) as listener:
        listener.expect("this-attempt")
        waiting = asyncio.create_task(listener.wait(5))

        status, _ = await browser_get(listener.port, "/auth/callback?code=x&state=forged")
        assert status == 400
        assert not waiting.done()

        status, _ = await browser_get(listener.port, "/auth/callback?code=c&state=this-attempt")
        assert status == 200
        assert (await waiting)["code"] == "c"
