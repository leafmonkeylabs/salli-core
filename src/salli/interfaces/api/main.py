"""
Salli FastAPI application.

Thin HTTP adapter over the same composition root the CLI uses.
All business logic lives in the application services; this module only wires
routing, CORS, error handling, and the lifespan startup/shutdown.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from salli.application.ports import FxUnavailableError, ProfileMissing
from salli.application.services.user_profile_service import BaseCurrencyLockedError
from salli.config import get_settings
from salli.domain.secrets import redact
from salli.domain.usage import UsageLimitReached
from salli.extensions import enabled_specs
from salli.interfaces.api.contract import API_PREFIX, document_problems, operation_id
from salli.interfaces.api.deps import get_services
from salli.interfaces.api.request_context import RequestContextMiddleware
from salli.interfaces.api.routers import (
    accounts,
    advisor,
    agent,
    auth,
    banks,
    budget,
    debt,
    documents,
    entries,
    exports,
    fi,
    insights,
    insurance,
    ledger,
    llm_keys,
    mcp_consent_page,
    mcp_oauth,
    meta,
    onboarding,
    portfolio,
    reminders,
    reports,
    rules,
    statements,
    subscriptions,
    tags,
    tax,
    tokens,
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


class Health(BaseModel):
    """`GET /healthz`: the process is up and serving."""

    status: Literal["ok"]
    #: The server's version (salli-core's).
    version: str


def problem(
    status_code: int, kind: str | None, title: str, detail: Any, **headers: str
) -> JSONResponse:
    """An RFC 9457 problem-details response (see contract.Problem)."""
    return JSONResponse(
        status_code=status_code,
        content={
            "type": f"/problems/{kind}" if kind else "about:blank",
            "title": title,
            "status": status_code,
            "detail": detail,
        },
        media_type="application/problem+json",
        headers=headers or None,
    )


async def _deprecated_path(request: Request, response: Response) -> None:
    """Marks a response served at a pre-/v1 path (RFC 9745 `Deprecation`), and
    names where it lives now. Responses an endpoint builds itself (streams,
    files) go out without it; the path still works."""
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = f'<{API_PREFIX}{request.url.path}>; rel="successor-version"'


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
        version=meta.server_version(),
        # Stable, deliberate operation ids: they are the function names of every
        # client generated from this API's schema (see contract.py).
        generate_unique_id_function=operation_id,
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
    # The REST API lives under /v1 (see contract.py). Each router is also
    # served at its old unversioned path, outside the schema and marked
    # deprecated, so clients written before /v1 keep working while they move.
    rest = [
        auth.router,
        accounts.router,
        entries.router,
        ledger.router,
        tags.router,
        tax.router,
        agent.router,
        documents.router,
        onboarding.router,
        statements.router,
        reminders.router,
        fi.router,
        advisor.router,
        budget.router,
        debt.router,
        portfolio.router,
        subscriptions.router,
        insurance.router,
        reports.router,
        llm_keys.router,
        mcp_oauth.connections_router,
        tokens.router,
        rules.router,
        exports.router,
        insights.router,
        banks.router,
    ]
    # Routers contributed by enabled extensions (salli/extensions.py), after
    # Salli's own, so an extension adds paths but cannot shadow one of Salli's.
    rest += [router for spec in enabled_specs(settings) for router in spec.api_routers]
    for router in rest:
        app.include_router(router, prefix=API_PREFIX)
        app.include_router(
            router, include_in_schema=False, dependencies=[Depends(_deprecated_path)]
        )
    app.include_router(meta.router, prefix=API_PREFIX)
    # OAuth and the MCP consent page keep the paths their protocols fix.
    app.include_router(mcp_oauth.router)
    # A server-rendered page for people, not an API operation: kept out of the schema.
    app.include_router(mcp_consent_page.router, include_in_schema=False)

    # ── Exception handlers ────────────────────────────────────────────────────
    # Every error is RFC 9457 problem details (contract.Problem). `detail` keeps
    # the value it always had, so clients written before this shape still work.
    #
    # The ValueError and KeyError handlers echo the exception text, so they are
    # redacted: a provider SDK error (or our own validation of a user-supplied
    # API key) can carry the key itself, and these are catch-alls for *any*
    # uncaught ValueError/KeyError.
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid", "Invalid request", redact(str(exc))
        )

    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
        return problem(
            status.HTTP_404_NOT_FOUND, "not-found", "Not found", redact(f"Not found: {exc}")
        )

    # No exchange rate for a posting in another currency. Before ValueError's
    # catch-all would see it (it is a LookupError): the client can fix this by
    # sending the rate it has, so it is a 422 that says so, not a 500.
    @app.exception_handler(FxUnavailableError)
    async def fx_unavailable_handler(request: Request, exc: FxUnavailableError) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "fx-rate-unavailable",
            "No exchange rate",
            f"{exc}. Send the exchange rate (fx_rate) with the amount.",
        )

    # A write that needs the caller's profile before it exists. Every request
    # provisions its caller first, so this is rare: say what to do.
    @app.exception_handler(ProfileMissing)
    async def profile_missing_handler(request: Request, exc: ProfileMissing) -> JSONResponse:
        return problem(
            status.HTTP_409_CONFLICT,
            "profile-missing",
            "No profile yet",
            "This account has no profile yet. Complete onboarding (POST /v1/onboarding/complete)"
            " first.",
        )

    # Asked to change the base currency once amounts are stored in it.
    @app.exception_handler(BaseCurrencyLockedError)
    async def base_currency_locked_handler(
        request: Request, exc: BaseCurrencyLockedError
    ) -> JSONResponse:
        return problem(
            status.HTTP_409_CONFLICT, "base-currency-locked", "Base currency is fixed", str(exc)
        )

    # The usage meter refused an AI action. The meter chose the status and the
    # detail, so they pass through untouched — clients of a metered deployment
    # branch on them. Raised before any stream opens, so this is always a plain
    # JSON response rather than an SSE error event.
    @app.exception_handler(UsageLimitReached)
    async def usage_limit_handler(request: Request, exc: UsageLimitReached) -> JSONResponse:
        return problem(exc.status_code, "usage-limit", "Usage limit reached", exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(
            exc.status_code, None, _status_title(exc.status_code), exc.detail, **(exc.headers or {})
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation",
            "Request validation failed",
            jsonable_encoder(exc.errors()),
        )

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/healthz", tags=["meta"])
    async def health() -> Health:
        return Health(status="ok", version=app.version)

    # The spec documents errors as the problem details they are.
    build_openapi = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = document_problems(build_openapi())
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]

    return app


def _status_title(code: int) -> str:
    from http import HTTPStatus

    try:
        return HTTPStatus(code).phrase
    except ValueError:
        return "Error"


app = create_app()
