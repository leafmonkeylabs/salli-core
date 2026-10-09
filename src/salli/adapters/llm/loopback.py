"""
The loopback listener a sign-in's browser comes back to.

OpenAI's sign-in redirects the browser to `http://127.0.0.1:<port>/auth/callback`
(never `localhost`; only the port may vary), so the listener has to run on
the computer the browser is on. It binds 127.0.0.1 only, answers the one
callback it is waiting for, and is closed as soon as that arrives. Port 1455,
the guide's example, when it is free; any free port otherwise.

The callback's query (the authorization code, `state`, the issued client id)
is handed back as it came; checking it is the caller's job (read_callback).
Nothing here logs it.
"""

from __future__ import annotations

import asyncio
from types import TracebackType
from urllib.parse import parse_qsl, urlsplit

from salli.adapters.llm.chatgpt_oauth import CALLBACK_PATH, loopback_redirect_uri

DEFAULT_PORT = 1455

_PAGE = (
    "<!doctype html><meta charset=utf-8><title>Salli</title>"
    "<body style='font-family:system-ui;margin:3rem'>"
    "<h1>Back to Salli</h1><p>The sign-in reached Salli. You can close this tab and "
    "return to the terminal.</p></body>"
)


class LoopbackCallback:
    """`async with LoopbackCallback() as listener:` then build the
    authorization URL with `listener.redirect_uri`, open it, and
    `await listener.wait(timeout)` for the callback's query."""

    def __init__(self, port: int = DEFAULT_PORT) -> None:
        self._wanted = port
        self._server: asyncio.Server | None = None
        self._result: asyncio.Future[dict[str, str]] | None = None
        self.port = 0

    async def __aenter__(self) -> LoopbackCallback:
        self._result = asyncio.get_running_loop().create_future()
        try:
            self._server = await asyncio.start_server(self._handle, "127.0.0.1", self._wanted)
        except OSError:
            # Taken: any free port will do ("Later sign-ins may use another
            # available port").
            self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = int(self._server.sockets[0].getsockname()[1])
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    @property
    def redirect_uri(self) -> str:
        return loopback_redirect_uri(self.port)

    async def wait(self, timeout: float) -> dict[str, str]:
        """The callback's query parameters. TimeoutError if the browser never
        came back."""
        assert self._result is not None, "use LoopbackCallback as an async context manager"
        return await asyncio.wait_for(asyncio.shield(self._result), timeout)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), 10)
            # The headers carry nothing needed; read past them.
            while True:
                header = await asyncio.wait_for(reader.readline(), 10)
                if header in (b"\r\n", b"\n", b""):
                    break
            method, _, rest = request_line.decode("latin-1").partition(" ")
            target = rest.split(" ", 1)[0]
            parts = urlsplit(target)
            if method == "GET" and parts.path == CALLBACK_PATH:
                body, status = _PAGE.encode(), "200 OK"
                if self._result is not None and not self._result.done():
                    self._result.set_result(dict(parse_qsl(parts.query)))
            else:
                body, status = b"Not found", "404 Not Found"
            writer.write(
                f"HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(body)}\r\nConnection: close\r\n"
                "Cache-Control: no-store\r\n\r\n".encode()
                + body
            )
            await writer.drain()
        except (TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()
