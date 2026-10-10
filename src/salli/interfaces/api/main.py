"""
Salli FastAPI application.

Thin HTTP adapter over the same composition root the CLI uses.
All business logic lives in the application services; this module only wires
routing, CORS, error handling, and the lifespan startup/shutdown.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from salli.config import get_settings
from salli.domain.secrets import redact
from salli.domain.usage import UsageLimitReached
from salli.extensions import enabled_specs
from salli.interfaces.api.deps import get_services
from salli.interfaces.api.request_context import RequestContextMiddleware
from salli.interfaces.api.routers import (
    accounts,
    advisor,
    agent,
    auth,
    budget,
    debt,
    documents,
    entries,
    fi,
    insurance,
    ledger,
    llm_keys,
    mcp_consent_page,
    mcp_oauth,
    onboarding,
    portfolio,
    reminders,
    reports,
    statements,
    subscriptions,
    tags,
    tax,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = logging.getLogger(__name__)
    settings = get_settings()

    # ── PostgreSQL checkpointer for LangGraph agent conversations ─────────────
    # Converts asyncpg URL → psycopg3 URL (different drivers, same DB)
    pg_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    checkpointer_ctx = None
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        checkpointer_ctx = AsyncPostgresSaver.from_conn_string(pg_url)
        checkpointer = await checkpointer_ctx.__aenter__()
        await checkpointer.setup()  # creates checkpoint tables if not present
        from salli.interfaces.api.deps import set_checkpointer

        set_checkpointer(checkpointer)
        log.info("LangGraph PostgreSQL checkpointer initialised")
    except Exception as exc:
        log.warning("PostgreSQL checkpointer unavailable (%s) — falling back to in-memory", exc)

    # ── Warm the DB connection pool ───────────────────────────────────────────
    svc = get_services()

    # ── MCP server ─────────────────────────────────────────────────────────────
    # FastMCP's session_manager owns its own task group tied to its lifespan —
    # it must be entered here, in the app's own lifespan, rather than relying on
    # the Starlette app streamable_http_app() builds internally (mounting alone
    # does not forward lifespan events to a mounted sub-application), or every
    # request throws "Task group is not initialized".
    from salli.interfaces.api.mcp_server import build_mcp_server

    mcp_server = build_mcp_server(svc, issuer_url=settings.mcp_public_base_url.rstrip("/"))
    # Mounted at root, not "/mcp": FastMCP's own streamable_http_path default
    # ("/mcp") already puts the real route at exactly /mcp with no trailing
    # slash, matching the resource URL we advertise everywhere. Mounting at
    # "/mcp" too would put the route at /mcp/ instead, and a bare /mcp request
    # (what every real client sends) would 307-redirect there instead of being
    # served directly — several MCP/OAuth clients don't follow that redirect
    # on a POST, surfacing as an opaque "couldn't refresh actions" failure.
    # This mount is added last, after every other router, so it only ever
    # catches requests no other route matched.
    app.mount("/", mcp_server.streamable_http_app())

    async with mcp_server.session_manager.run():
        yield

    # ── Teardown ──────────────────────────────────────────────────────────────
    if checkpointer_ctx is not None:
        try:
            await checkpointer_ctx.__aexit__(None, None, None)
        except Exception:
            pass


def create_app() -> FastAPI:
    settings = get_settings()

    # The first and only place logging is configured. Guarded because every API
    # test builds a fresh app, and re-running basicConfig would stack handlers.
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=getattr(logging, settings.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )

    app = FastAPI(
        title="Salli API",
        description="Privacy-first personal finance, tax and financial independence",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        lifespan=lifespan,
    )

    # ── Request correlation ───────────────────────────────────────────────────
    # Registered BEFORE CORS so that CORS ends up outermost: add_middleware
    # inserts at index 0, so the last-added middleware wraps the earlier ones.
    # The 500 JSON body this produces has to pass back out through CORS, or the
    # browser cannot read it and the request id never reaches the user.
    app.add_middleware(RequestContextMiddleware)

    # ── CORS ──────────────────────────────────────────────────────────────────
    origins = ["*"] if settings.environment == "development" else settings.allowed_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # allow_headers already permits the client to *send* this; expose_headers
        # is what lets browser JS *read* it off the response.
        expose_headers=["X-Request-Id"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth.router)
    app.include_router(accounts.router)
    app.include_router(entries.router)
    app.include_router(ledger.router)
    app.include_router(tags.router)
    app.include_router(tax.router)
    app.include_router(agent.router)
    app.include_router(documents.router)
    app.include_router(onboarding.router)
    app.include_router(statements.router)
    app.include_router(reminders.router)
    app.include_router(fi.router)
    app.include_router(advisor.router)
    app.include_router(budget.router)
    app.include_router(debt.router)
    app.include_router(portfolio.router)
    app.include_router(subscriptions.router)
    app.include_router(insurance.router)
    app.include_router(reports.router)
    app.include_router(llm_keys.router)
    app.include_router(mcp_oauth.router)
    app.include_router(mcp_oauth.connections_router)
    app.include_router(mcp_consent_page.router)

    # Routers contributed by enabled extensions (salli/extensions.py). Mounted
    # last, so an extension adds paths but cannot shadow one of Salli's.
    for spec in enabled_specs(settings):
        for extension_router in spec.api_routers:
            app.include_router(extension_router)

    # ── Exception handlers ────────────────────────────────────────────────────
    # Both handlers echo the exception text, so both are redacted: a provider
    # SDK error (or our own validation of a user-supplied API key) can carry the
    # key itself, and these are catch-alls for *any* uncaught ValueError/KeyError.
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": redact(str(exc))},
        )

    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": redact(f"Not found: {exc}")},
        )

    # The usage meter refused an AI action. The meter chose the status and the
    # body, so they pass through untouched — clients of a metered deployment
    # branch on them. Raised before any stream opens, so this is always a plain
    # JSON response rather than an SSE error event.
    @app.exception_handler(UsageLimitReached)
    async def usage_limit_handler(request: Request, exc: UsageLimitReached) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/healthz", tags=["meta"])
    async def health():
        return {"status": "ok", "version": app.version}

    return app


app = create_app()
