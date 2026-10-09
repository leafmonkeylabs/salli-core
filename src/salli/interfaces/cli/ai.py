"""
`salli ai` — your ChatGPT plan, connected to Salli.

`salli ai connect chatgpt` signs in with ChatGPT on this computer: it listens
on 127.0.0.1 for the browser to come back (OpenAI's sign-in only returns to a
loopback address), opens the browser, and keeps the result once it checks
out. Run it where the browser is:

- on the machine Salli runs on: it is kept straight away;
- for a Salli server somewhere else: `--save-to FILE --host-id <the server's
  host id>` writes the sign-in to a file only you can read (0600), which
  `salli ai connect chatgpt --from-file FILE` on the server then keeps (or a
  client hands it to `PUT /v1/ai/connections/chatgpt`). The server renews it
  from then on, under its own host id (OpenAI's guide for self-hosted VMs).

Using the plan counts toward its usage limits; review them, and Salli's own
limit, in ChatGPT's settings (https://chatgpt.com/settings/usage). Anthropic
offers nothing like this, so Claude runs on an API key only (`salli llm-keys`).

No token is ever printed.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import secrets
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

from salli.interfaces.cli.support import console, emit, require_user, services

ai_app = typer.Typer(help="AI providers: your ChatGPT plan, and the host id it signs in with")

#: Opens the system browser. Swapped in tests.
open_browser: Callable[[str], bool] = webbrowser.open

_MANAGE = "https://chatgpt.com/settings/usage"


def _only_chatgpt(provider: str) -> None:
    if provider != "chatgpt":
        console.print(
            "[red]Only `chatgpt` is signed in to.[/red] For an API key, use "
            "[bold]salli llm-keys set openai[/bold] (or anthropic)."
        )
        raise typer.Exit(2)


def write_private(path: Path, data: dict[str, Any]) -> Path:
    """Write `data` as JSON, atomically, readable and writable by its owner
    only (0600), as OpenAI's guide asks of a credential file."""
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


async def _browser_sign_in(
    oauth: Any,
    *,
    host_id: str,
    client_id: str | None,
    login_hint: str | None,
    id_token_hint: str | None,
    ask_consent: bool,
    port: int,
    timeout: float,
    no_browser: bool,
) -> tuple[Any, Any, Any]:
    """Sign in through the browser on this computer. (tokens, callback, pending)."""
    from salli.adapters.llm.chatgpt_oauth import authorization_url, begin_sign_in, read_callback
    from salli.adapters.llm.loopback import LoopbackCallback

    async with LoopbackCallback(port) as listener:
        pending = begin_sign_in(
            host_id=host_id, redirect_uri=listener.redirect_uri, client_id=client_id
        )
        listener.expect(pending.state)
        console.print(
            "[bold]Continue with ChatGPT[/bold] in your browser to connect your ChatGPT plan "
            "to Salli.\nSalli's AI requests will then use your ChatGPT plan and count toward "
            f"its usage limits. Manage usage: {_MANAGE}"
        )
        url = authorization_url(
            pending, login_hint=login_hint, id_token_hint=id_token_hint, ask_consent=ask_consent
        )
        if no_browser or not open_browser(url):
            # Printed without the ID token hint: a link carrying one must not
            # end up in a terminal's scrollback or a log. It still works; it
            # only asks which account.
            shown = authorization_url(pending, login_hint=login_hint, ask_consent=ask_consent)
            console.print(f"Open this link to continue:\n{shown}")
        query = await listener.wait(timeout)
    callback = read_callback(pending, query)
    tokens = await oauth.exchange_code(pending, callback)
    return tokens, callback, pending


def _report(status: dict[str, Any]) -> None:
    if status.get("first_time"):
        console.print(
            "\n[bold green]You're using your ChatGPT plan.[/bold green]\n"
            "Salli's AI requests now use your ChatGPT plan. Review and manage what Salli "
            f"uses in ChatGPT settings: {_MANAGE}"
        )
    else:
        console.print(
            f"[green]Connected to ChatGPT[/green] as {status.get('email') or 'your account'}."
        )


def _fail(message: str) -> typer.Exit:
    console.print(f"[red]{message}[/red]")
    return typer.Exit(1)


@ai_app.command("host")
def ai_host() -> None:
    """This instance's host id for Sign in with ChatGPT (not a secret).

    A sign-in done on another computer for this server sends it."""
    host = asyncio.run(services().chatgpt.host_id())
    if emit({"ext_agent_host_id": host}):
        return
    console.print(host)


_SOURCE = {
    "user": "yours",
    "platform": "this server's key",
    "none": "nothing set up yet",
}


@ai_app.command("status")
def ai_status() -> None:
    """Which provider powers your AI, and your ChatGPT plan connection."""
    user_id = require_user()
    svc = services()

    async def _run() -> tuple[dict[str, Any], dict[str, Any]]:
        return await svc.llm_credentials.settings(user_id), await svc.chatgpt.status(user_id)

    settings, status = asyncio.run(_run())
    if emit({"settings": settings, "chatgpt": status}):
        return
    active = settings["active"]
    console.print(
        f"AI provider: [bold]{settings['provider']}[/bold] → {active['provider']} "
        f"({_SOURCE[active['source']]})"
    )
    if settings["keys"]:
        console.print(f"  Your API keys: {', '.join(settings['keys'])}")
    if not status["available"]:
        console.print(
            "ChatGPT: [yellow]off on this server[/yellow] (needs BYOK_ENCRYPTION_KEYS and real sign-in)."
        )
        return
    line = {
        "active": f"[green]connected[/green] as {status['email'] or 'your account'}",
        "needs_sign_in": "[yellow]needs you to sign in again[/yellow]",
        "needs_consent": "[yellow]signed in, but plan use is not allowed[/yellow]",
        "signed_out": "disconnected",
        "not_connected": "not connected",
    }[status["status"]]
    console.print(f"ChatGPT: {line}")
    if status.get("detail"):
        console.print(f"  {status['detail']}")
    if status.get("paused_until"):
        console.print(f"  Paused at the plan's usage limit until {status['paused_until']}.")
    if status["status"] != "not_connected":
        console.print(f"  Manage usage: {_MANAGE}")


@ai_app.command("use")
def ai_use(
    provider: str = typer.Argument(..., help="auto, anthropic, openai or chatgpt"),
) -> None:
    """Choose what powers your AI. `auto` prefers your ChatGPT plan, then your
    own Anthropic key, then your own OpenAI key, then this server's key."""
    user_id = require_user()
    try:
        settings = asyncio.run(services().llm_credentials.set_provider(user_id, provider))
    except ValueError as exc:
        raise _fail(str(exc)) from None
    if emit(settings):
        return
    active = settings["active"]
    console.print(
        f"[green]AI provider set to {settings['provider']}[/green]: runs on "
        f"{active['provider']} ({_SOURCE[active['source']]})."
    )


def _print_models(result: dict[str, Any]) -> None:
    console.print(
        f"{result['provider']}: best = [bold]{result['best']}[/bold], fast = [bold]{result['fast']}[/bold]"
    )
    chosen = {k: v for k, v in result["chosen"].items() if v}
    if chosen:
        console.print("  chosen by you: " + ", ".join(f"{k} = {v}" for k, v in chosen.items()))
    for model in result["models"]:
        console.print(
            f"  {model['id']}" + (f"  ({model['name']})" if model["name"] != model["id"] else "")
        )


@ai_app.command("models")
def ai_models(
    provider: str = typer.Argument(
        None, help="anthropic, openai or chatgpt (default: the one in use)"
    ),
) -> None:
    """The models a provider offers you, and which one each task runs on."""
    from salli.domain.llm import LLMError

    user_id = require_user()
    svc = services()

    async def _run() -> dict[str, Any]:
        name = provider or (await svc.llm_credentials.settings(user_id))["active"]["provider"]
        return await svc.llm_credentials.models(user_id, name)

    try:
        result = asyncio.run(_run())
    except LLMError as exc:
        raise _fail(exc.message) from None
    except ValueError as exc:
        raise _fail(str(exc)) from None
    if emit(result):
        return
    _print_models(result)


@ai_app.command("set-models")
def ai_set_models(
    provider: str = typer.Argument(..., help="openai or chatgpt"),
    fast: str | None = typer.Option(None, "--fast", help="For sorting statements, quick add"),
    best: str | None = typer.Option(None, "--best", help="For chat, the FIRE strategy, advice"),
) -> None:
    """Name the model each task runs on (neither: let Salli pick again)."""
    from salli.domain.llm import LLMError

    user_id = require_user()
    try:
        result = asyncio.run(
            services().llm_credentials.set_models(user_id, provider, fast=fast, best=best)
        )
    except LLMError as exc:
        raise _fail(exc.message) from None
    except ValueError as exc:
        raise _fail(str(exc)) from None
    if emit(result):
        return
    _print_models(result)


@ai_app.command("connect")
def ai_connect(
    provider: str = typer.Argument(..., help="chatgpt"),
    new_account: bool = typer.Option(
        False, "--new-account", help="Register a different ChatGPT account than the connected one"
    ),
    from_file: Path | None = typer.Option(
        None, "--from-file", help="Keep a sign-in completed on another computer (a credential file)"
    ),
    save_to: Path | None = typer.Option(
        None,
        "--save-to",
        help="Sign in here for a server elsewhere: write the sign-in to this file (0600) "
        "instead of keeping it",
    ),
    host_id: str | None = typer.Option(
        None, "--host-id", help="With --save-to: the server's host id (`salli ai host` there)"
    ),
    client_id: str | None = typer.Option(
        None,
        "--client-id",
        help="With --save-to: the server's issued client id for your account, to sign in again "
        "rather than register",
    ),
    port: int = typer.Option(1455, "--port", help="Loopback port for the browser to return to"),
    timeout: int = typer.Option(300, "--timeout", help="Seconds to wait for the browser"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Print the link instead"),
) -> None:
    """Connect your ChatGPT plan: sign in with ChatGPT in your browser."""
    from salli.adapters.llm.chatgpt_oauth import OAuthUnavailable, SignInError
    from salli.application.services.chatgpt_connection_service import ChatGPTUnavailable
    from salli.domain.llm import LLMError

    _only_chatgpt(provider)
    try:
        if save_to is not None:
            if not host_id:
                raise _fail("--save-to needs --host-id: the host id of the server it is for.")
            written = asyncio.run(
                _save_sign_in(save_to, host_id, client_id, port, timeout, no_browser)
            )
            emit({"saved_to": str(written)})
            console.print(
                f"[green]Saved the sign-in to {written}[/green] (readable by you only). Move it "
                "to the server over a secure channel, then run there:\n"
                f"  salli ai connect chatgpt --from-file {written.name}"
            )
            return
        user_id = require_user()
        if from_file is not None:
            credential = json.loads(from_file.expanduser().read_text())
            status = asyncio.run(services().chatgpt.import_credential(user_id, credential))
            # The server holds it sealed now and renews it; the file's copy is
            # a live refresh token in the clear.
            console.print(
                f"[yellow]Delete {from_file}[/yellow]: Salli keeps the sign-in sealed now, "
                "and the file still holds a working refresh token."
            )
        else:
            status = asyncio.run(_sign_in_here(user_id, new_account, port, timeout, no_browser))
    except (SignInError, ChatGPTUnavailable) as exc:
        raise _fail(str(exc)) from None
    except LLMError as exc:
        raise _fail(exc.message) from None
    except OAuthUnavailable:
        raise _fail("Couldn't reach OpenAI to finish signing in. Please try again.") from None
    except TimeoutError:
        raise _fail(
            f"The browser didn't come back within {timeout} seconds. Please try again."
        ) from None
    if emit(status):
        return
    _report(status)


async def _sign_in_here(
    user_id: str, new_account: bool, port: int, timeout: float, no_browser: bool
) -> dict[str, Any]:
    chatgpt = services().chatgpt
    context = await chatgpt.sign_in_context(user_id, new_account=new_account)
    tokens, callback, pending = await _browser_sign_in(
        chatgpt.oauth,
        host_id=context.host_id,
        client_id=context.client_id,
        login_hint=context.login_hint,
        id_token_hint=context.id_token_hint,
        ask_consent=context.ask_consent,
        port=port,
        timeout=timeout,
        no_browser=no_browser,
    )
    return await chatgpt.connect(
        user_id,
        tokens,
        client_id=callback.client_id,
        nonce=pending.nonce,
        expected_sub=context.expected_sub if context.client_id else None,
    )


async def _save_sign_in(
    path: Path, host_id: str, client_id: str | None, port: int, timeout: float, no_browser: bool
) -> Path:
    """Sign in here for a server elsewhere, and write OpenAI's credential
    record to `path`: checked here first (the ID token and its nonce, and that
    plan use was granted), and again by the server when it is handed over."""
    from salli.adapters.llm.chatgpt_oauth import ChatGPTOAuth, SignInError

    oauth = ChatGPTOAuth()
    tokens, callback, pending = await _browser_sign_in(
        oauth,
        host_id=host_id,
        client_id=client_id,
        login_hint=None,
        id_token_hint=None,
        ask_consent=False,
        port=port,
        timeout=timeout,
        no_browser=no_browser,
    )
    if not tokens.id_token:
        raise SignInError("The sign-in has no ID token, so it can't be verified.")
    claims = await oauth.verify_id_token(
        tokens.id_token,
        client_id=callback.client_id,
        nonce=pending.nonce,
        access_token=tokens.access_token,
    )
    if not tokens.plan_granted:
        raise SignInError("ChatGPT plan use wasn't allowed, so there is nothing to hand over.")
    return write_private(
        path,
        {
            "email": claims.get("email"),
            "issuer": "https://auth.openai.com",
            "subject": claims["sub"],
            "client_id": callback.client_id,
            "ext_agent_host_id": host_id,
            "id_token": tokens.id_token,
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "token_type": tokens.token_type,
            "expires_in": tokens.expires_in,
            "scopes": list(tokens.scopes),
            "saved_at": dt.datetime.now(dt.UTC).isoformat(),
        },
    )


@ai_app.command("disconnect")
def ai_disconnect(provider: str = typer.Argument(..., help="chatgpt")) -> None:
    """Disconnect your ChatGPT plan: end the sign-in with OpenAI and forget its tokens."""
    _only_chatgpt(provider)
    user_id = require_user()
    result = asyncio.run(services().chatgpt.disconnect(user_id))
    if not result["disconnected"]:
        raise _fail("ChatGPT is not connected.")
    if emit(result):
        return
    console.print(result["message"])
