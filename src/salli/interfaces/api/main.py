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

from salli.application.ports import (
    AccountNotFound,
    DebtNotFound,
    DecisionNotFound,
    FetchRefused,
    FxUnavailableError,
    HoldingNotFound,
    PrincipleNotFound,
    ProfileMissing,
)
from salli.application.services.document_service import DocumentRetained
from salli.application.services.reconciliation_service import Reconciled
from salli.application.services.tax_rule_service import (
    RuleSetConflict,
    RuleSetDocumentError,
    RuleSetInputError,
    RuleSetNotFound,
    RuleSetPermissionError,
    RuleSetRateMissing,
    RuleSetStateError,
)
from salli.application.services.tax_service import NoTaxRulesError
from salli.application.services.user_profile_service import BaseCurrencyLockedError
from salli.config import database_url, get_settings
from salli.domain.accounting.models import AccountNotEmpty, BooksLocked
from salli.domain.decisions.journal import JournalError
from salli.domain.decisions.principles import PrincipleError
from salli.domain.decisions.templates import TemplateError, UnknownTemplate
from salli.domain.llm import LLMError
from salli.domain.scenarios import ScenarioError
from salli.domain.secrets import redact
from salli.domain.taxrules.explain import UnknownLine
from salli.domain.usage import UsageLimitReached
from salli.extensions import enabled_specs
from salli.interfaces.api.console import NoStoreMiddleware, console_router
from salli.interfaces.api.contract import API_PREFIX, document_problems, operation_id
from salli.interfaces.api.deps import StepUpRequired, get_services
from salli.interfaces.api.request_context import UNEXPECTED_TITLE, RequestContextMiddleware
from salli.interfaces.api.routers import (
    access,
    accounts,
    advisor,
    agent,
    ai,
    auth,
    banks,
    baseline,
    budget,
    debt,
    decisions,
    documents,
    entries,
    exports,
    fi,
    insights,
    insurance,
    ips,
    ledger,
    llm_keys,
    mcp_consent_page,
    mcp_oauth,
    meta,
    notifications,
    onboarding,
    portfolio,
    principles,
    reconciliation,
    reminders,
    reports,
    rules,
    scenarios,
    statements,
    subscriptions,
    tags,
    tax,
    tax_rules,
    tokens,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = logging.getLogger(__name__)
    settings = get_settings()

    # ── PostgreSQL checkpointer for LangGraph agent conversations ─────────────
    # The same database through psycopg 3 (a different driver), password and all.
    from sqlalchemy.engine import make_url

    pg_url = (
        make_url(database_url(settings))
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )

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
        # In memory, a briefing or return awaiting review, and every
        # conversation, would vanish on a restart and escape the export and
        # erasure: tests and development only.
        if settings.environment == "production":
            raise RuntimeError(
                "Salli can't start: the PostgreSQL checkpointer is unavailable in "
                f"production ({exc})."
            ) from exc
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

    mcp_server = build_mcp_server(
        svc,
        issuer_url=settings.salli_public_url.rstrip("/"),
        allowed_origins=settings.allowed_origins,
    )
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
    status_code: int,
    kind: str | None,
    title: str,
    detail: Any,
    extra: dict[str, Any] | None = None,
    **headers: str,
) -> JSONResponse:
    """An RFC 9457 problem-details response (see contract.Problem), with any
    `extra` members the problem's type defines."""
    return JSONResponse(
        status_code=status_code,
        content={
            "type": f"/problems/{kind}" if kind else "about:blank",
            "title": title,
            "status": status_code,
            "detail": detail,
            **(extra or {}),
        },
        media_type="application/problem+json",
        headers=headers or None,
    )


def _path_parts(path: str) -> list[str | int]:
    """A problem's path (`options[1].changes[0].amount`) as a validation
    error's `loc` parts (`["options", 1, "changes", 0, "amount"]`)."""
    if path == "$":
        return []
    parts: list[str | int] = []
    for piece in path.replace("[", ".[").split("."):
        if not piece:
            continue
        parts.append(int(piece[1:-1]) if piece.startswith("[") else piece)
    return parts


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

    # ── No caching of anyone's ledger ─────────────────────────────────────────
    # Every response but the console's own files says `no-store` unless it
    # set its own Cache-Control, so no browser or proxy keeps a page of
    # someone's data. Served over HTTPS, every response also tells the browser
    # to use nothing else (HSTS).
    app.add_middleware(
        NoStoreMiddleware, hsts=settings.salli_public_url.lower().startswith("https://")
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Only the origins ALLOWED_ORIGINS names, in every environment: none by
    # default. Nothing Salli ships runs in a browser on another origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
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
        tax_rules.router,
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
        ips.router,
        subscriptions.router,
        insurance.router,
        reports.router,
        reconciliation.router,
        llm_keys.router,
        ai.router,
        mcp_oauth.connections_router,
        tokens.router,
        rules.router,
        exports.router,
        insights.router,
        baseline.router,
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
    # New in /v1, so with no unversioned path to keep.
    app.include_router(scenarios.router, prefix=API_PREFIX)
    # OAuth and the MCP consent page keep the paths their protocols fix.
    app.include_router(mcp_oauth.router)
    # A server-rendered page for people, not an API operation: kept out of the schema.
    app.include_router(mcp_consent_page.router, include_in_schema=False)
    # New in /v1 too (after the protocol routes only to keep the API
    # document's order stable).
    app.include_router(principles.router, prefix=API_PREFIX)
    app.include_router(decisions.router, prefix=API_PREFIX)
    app.include_router(notifications.router, prefix=API_PREFIX)
    app.include_router(access.router, prefix=API_PREFIX)
    # The console's static files, at /console: here, so before the MCP app's
    # catch-all mount at "/", which the lifespan adds last. None when it is
    # switched off (SALLI_CONSOLE=false) or no console is built.
    console = console_router(settings)
    if console is not None:
        app.include_router(console, include_in_schema=False)

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

    # A posting on an account that is not the caller's (missing, or another
    # user's: they look the same). Before KeyError's catch-all, to say which.
    @app.exception_handler(AccountNotFound)
    async def account_not_found_handler(request: Request, exc: AccountNotFound) -> JSONResponse:
        return problem(status.HTTP_404_NOT_FOUND, "not-found", "Not found", str(exc))

    # A debt a scenario names that is not one of the caller's active debts.
    @app.exception_handler(DebtNotFound)
    async def debt_not_found_handler(request: Request, exc: DebtNotFound) -> JSONResponse:
        return problem(status.HTTP_404_NOT_FOUND, "not-found", "Not found", str(exc))

    # A holding a scenario names that is not one of the caller's.
    @app.exception_handler(HoldingNotFound)
    async def holding_not_found_handler(request: Request, exc: HoldingNotFound) -> JSONResponse:
        return problem(status.HTTP_404_NOT_FOUND, "not-found", "Not found", str(exc))

    # A scenario Salli can't run on this user's money (domain/scenarios):
    # each problem with its path in the body, in the shape a validation
    # error's `detail` takes, so clients show both the same way.
    @app.exception_handler(ScenarioError)
    async def scenario_error_handler(request: Request, exc: ScenarioError) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid-scenario",
            "Not a scenario Salli can run",
            [{"loc": ["body", *_path_parts(p.path)], "msg": p.message} for p in exc.problems],
        )

    # A principle Salli can't keep, or a decision, note or review it can't
    # record: each problem with its path, in a validation error's shape.
    @app.exception_handler(PrincipleError)
    async def principle_error_handler(request: Request, exc: PrincipleError) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid-principle",
            "Not a principle Salli can keep",
            [
                {"loc": ["body", *_path_parts(p.path)], "msg": p.message, "snippet": p.snippet}
                for p in exc.problems
            ],
        )

    @app.exception_handler(JournalError)
    async def journal_error_handler(request: Request, exc: JournalError) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid-decision",
            "Not something Salli can record in the decision journal",
            [{"loc": ["body", *_path_parts(p.path)], "msg": p.message} for p in exc.problems],
        )

    # A principle or a decision that is not the caller's (missing, or
    # another user's: they look the same).
    @app.exception_handler(PrincipleNotFound)
    async def principle_not_found_handler(request: Request, exc: PrincipleNotFound) -> JSONResponse:
        return problem(status.HTTP_404_NOT_FOUND, "not-found", "Not found", str(exc))

    @app.exception_handler(DecisionNotFound)
    async def decision_not_found_handler(request: Request, exc: DecisionNotFound) -> JSONResponse:
        return problem(status.HTTP_404_NOT_FOUND, "not-found", "Not found", str(exc))

    # Answers to a decision template Salli can't build options from, each
    # problem with its path (`answers.price`); and a template that doesn't
    # exist.
    @app.exception_handler(TemplateError)
    async def template_error_handler(request: Request, exc: TemplateError) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid-answers",
            "Not answers Salli can build options from",
            [{"loc": ["body", *_path_parts(p.path)], "msg": p.message} for p in exc.problems],
        )

    @app.exception_handler(UnknownTemplate)
    async def unknown_template_handler(request: Request, exc: UnknownTemplate) -> JSONResponse:
        return problem(status.HTTP_404_NOT_FOUND, "not-found", "Not found", str(exc))

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

    # No active tax rules to compute this user's tax with: no country to go by,
    # no rule set for it, or none activated. The detail says what to do (add
    # rules with the CLI or an agent, then activate them). Before KeyError's
    # catch-all, whose LookupError it is.
    @app.exception_handler(NoTaxRulesError)
    async def no_tax_rules_handler(request: Request, exc: NoTaxRulesError) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "no-tax-rules", "No active tax rules", str(exc)
        )

    # A line to explain that the rules don't have; the detail lists those they do.
    @app.exception_handler(UnknownLine)
    async def unknown_line_handler(request: Request, exc: UnknownLine) -> JSONResponse:
        return problem(status.HTTP_404_NOT_FOUND, "not-found", "Not found", str(exc))

    # Tax rule sets (application/services/tax_rule_service.py). Each before
    # the ValueError and LookupError it is a kind of.
    def _with_problems(message: str, problems: tuple[Any, ...]) -> str:
        return f"{message}: " + "; ".join(str(p) for p in problems) if problems else message

    @app.exception_handler(RuleSetNotFound)
    async def rule_set_not_found_handler(request: Request, exc: RuleSetNotFound) -> JSONResponse:
        # Someone else's rule set is "not found", exactly like a missing one.
        return problem(status.HTTP_404_NOT_FOUND, "not-found", "Not found", str(exc))

    @app.exception_handler(RuleSetDocumentError)
    async def rule_set_document_handler(
        request: Request, exc: RuleSetDocumentError
    ) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid-rule-set",
            "Not a rule set Salli can store",
            _with_problems(str(exc), exc.problems),
        )

    @app.exception_handler(RuleSetInputError)
    async def rule_set_input_handler(request: Request, exc: RuleSetInputError) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid", "Invalid request", str(exc)
        )

    @app.exception_handler(RuleSetStateError)
    async def rule_set_state_handler(request: Request, exc: RuleSetStateError) -> JSONResponse:
        return problem(
            status.HTTP_409_CONFLICT, "rule-set-state", "Not possible in this state", str(exc)
        )

    @app.exception_handler(RuleSetConflict)
    async def rule_set_conflict_handler(request: Request, exc: RuleSetConflict) -> JSONResponse:
        return problem(
            status.HTTP_409_CONFLICT, "rule-set-exists", "Rule set already exists", str(exc)
        )

    @app.exception_handler(RuleSetPermissionError)
    async def rule_set_permission_handler(
        request: Request, exc: RuleSetPermissionError
    ) -> JSONResponse:
        return problem(status.HTTP_403_FORBIDDEN, "permission", "Not permitted", str(exc))

    @app.exception_handler(RuleSetRateMissing)
    async def rule_set_rate_handler(request: Request, exc: RuleSetRateMissing) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "fx-rate-unavailable",
            "No exchange rate",
            str(exc),
        )

    # A URL the server won't fetch (not https, not public, too large or slow).
    # The message never describes the network.
    @app.exception_handler(FetchRefused)
    async def fetch_refused_handler(request: Request, exc: FetchRefused) -> JSONResponse:
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "fetch-refused", "Not fetched", str(exc)
        )

    # An entry dated in the user's closed books (domain/accounting/models.py).
    # Before ValueError's catch-all, whose kind it is.
    @app.exception_handler(BooksLocked)
    async def books_locked_handler(request: Request, exc: BooksLocked) -> JSONResponse:
        return problem(status.HTTP_409_CONFLICT, "books-locked", "The books are closed", str(exc))

    # Deleting a document that is kept (its retention, or an entry cites it).
    @app.exception_handler(DocumentRetained)
    async def retained_handler(request: Request, exc: DocumentRetained) -> JSONResponse:
        return problem(status.HTTP_409_CONFLICT, "document-retained", "Document kept", str(exc))

    # A change to a statement whose reconciliation is complete.
    @app.exception_handler(Reconciled)
    async def reconciled_handler(request: Request, exc: Reconciled) -> JSONResponse:
        return problem(status.HTTP_409_CONFLICT, "reconciled", "Already reconciled", str(exc))

    @app.exception_handler(AccountNotEmpty)
    async def account_not_empty_handler(request: Request, exc: AccountNotEmpty) -> JSONResponse:
        return problem(
            status.HTTP_409_CONFLICT, "account-not-empty", "The account holds a balance", str(exc)
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

    # A model request that could not be served: a ChatGPT plan at its usage
    # limit (429, with where to change it), a sign-in to renew (409), a
    # provider that refused or could not be reached. The message is always
    # Salli's own sentence, never the provider's, so it is safe to show. Raised
    # before a stream opens, it is a plain problem response; once a stream is
    # open, the stream's own `error` event carries the same detail.
    @app.exception_handler(LLMError)
    async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else {}
        return problem(
            exc.status, exc.code.replace("_", "-"), "AI unavailable", exc.detail(), **headers
        )

    # The console's sign-in would hold this permission if its password check
    # were recent (application/permissions.py): send the person through the
    # sign-in page again. RFC 9470's challenge says the same to a client that
    # reads WWW-Authenticate.
    @app.exception_handler(StepUpRequired)
    async def step_up_handler(request: Request, exc: StepUpRequired) -> JSONResponse:
        return problem(
            status.HTTP_403_FORBIDDEN,
            "step-up-required",
            "Sign in again",
            str(exc),
            {"max_age": exc.max_age},
            **{
                "WWW-Authenticate": 'Bearer error="insufficient_user_authentication", '
                f'error_description="Sign in again to continue", max_age={exc.max_age}'
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(
            exc.status_code, None, _status_title(exc.status_code), exc.detail, **(exc.headers or {})
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Where and why, never what was sent: pydantic puts the offending
        # input (for a missing field, the whole body) in each error, and a
        # body can hold a credential (an API key, a ChatGPT sign-in's tokens).
        errors = [
            {k: v for k, v in error.items() if k not in ("input", "ctx", "url")}
            for error in exc.errors()
        ]
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation",
            "Request validation failed",
            jsonable_encoder(errors),
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


#: A plain HTTP error's title (`about:blank`) in Salli's words, not the
#: status's reason phrase; `detail` says what happened and what to do.
_STATUS_TITLES = {
    400: "Salli didn't do this",
    401: "Not signed in",
    403: "Not permitted",
    404: "Not found",
    405: "Not something this address does",
    409: "Not possible right now",
    413: "Too large to accept",
    415: "Not a kind of file Salli reads",
    422: "Salli couldn't use what was sent",
    429: "Too many attempts",
    500: UNEXPECTED_TITLE,
    502: "Another service refused",
    503: "Not available right now",
}


def _status_title(code: int) -> str:
    return _STATUS_TITLES.get(code) or (UNEXPECTED_TITLE if code >= 500 else "Salli didn't do this")


app = create_app()
