"""
The console's books, tax and settings fixtures (C4), written by the real
server: part of tests/console_fixtures.py, which writes them beside Home's,
the decision lab's and where you stand's, and whose contract test holds them
to what the server answers.

- `books.ts`: imports, the review queue and categorisation rules on the
  golden household (tests/golden/household.py, euros, as of 2026-10-11):
  the person's rule for FreshMart, then a checking statement for October so
  far imported against it (the rent, which Salli takes for an entry
  already booked; FreshMart, which the rule sorts; three that need an
  account, no model being set up); the reads; then the
  answers to the console's writes, made after every read (an account
  chosen, two posted, two discarded, a rule tested, refused, made from a
  suggestion, edited).
- `tax.ts`: the fictional rules "XA 2031" (tests/golden/rules/xa2031.json,
  with a filing deadline) on the taxed household (tests/golden/taxed.py,
  New Zealand dollars, as of 2031-06-30): version 1 the person's, active,
  with a computation; version 2 an agent's, proposed, raising the relief
  and citing the budget that does; version 3 an agent's draft whose worked
  example fails. Then the console's writes: activating version 2 from a
  console sign-in whose password is six minutes old (Salli's step-up
  answer), then from a fresh one; computing again; validating and proposing
  version 3 (refused).
- `settings.ts`: personal access tokens, stored model keys, digests and
  exports on the golden household: two tokens and an Anthropic key kept
  before the reads, a digest set up and sent on Monday; then a token made
  with `tax:activate` (shown once), the same asked for by a stale console
  sign-in (the step-up answer), a token refused for want of a name, a key
  the provider refuses, the digest made monthly. Every secret here is a
  fixture's and opens nothing.

The fakes the services run over are tests/console_fakes.py. Every id the
services make is fixed (`fixed_ids`), and every clock.
"""

from __future__ import annotations

import base64
import copy
import datetime as dt
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest import mock

from httpx import ASGITransport, AsyncClient

from salli.adapters.crypto.keyring import KeyRing
from salli.adapters.llm.key_check import InvalidProviderKey
from salli.application.defaults import FullAccess
from salli.application.services import (
    llm_credential_service,
    personal_access_token_service,
    rules_service,
)
from salli.application.services.bank_connection_service import BankConnectionService
from salli.application.services.data_portability_service import DataPortabilityService
from salli.application.services.llm_credential_service import LlmCredentialService
from salli.application.services.notification_service import NotificationService
from salli.application.services.parsing_service import ParsingService
from salli.application.services.personal_access_token_service import (
    PersonalAccessTokenService,
)
from salli.application.services.rules_service import RulesService
from salli.application.services.tax_rule_service import TaxRuleService
from salli.application.services.tax_service import TaxService
from salli.interfaces.api.deps import Principal, get_current_user, get_principal, get_services
from salli.interfaces.api.main import create_app
from tests.cli_fixtures import Books, Fixture
from tests.console_fakes import (
    ClosedKeyRing,
    FakeAuditLog,
    FakeBankConnections,
    FakeLlmCredentials,
    FakeRules,
    FakeStatements,
    FakeTaxComputations,
    FakeTaxRuleSets,
    FakeTokens,
)
from tests.fakes import FakeFx, RecordingNotifier
from tests.golden import household as h
from tests.golden import taxed

COMMAND = "uv run python -m tests.console_fixtures"


class Clock:
    """A clock the fixtures move on, step by step."""

    def __init__(self, at: dt.datetime) -> None:
        self.at = at

    def __call__(self) -> dt.datetime:
        return self.at


def _header(lines: str) -> str:
    return (
        "/**\n"
        + "".join(f" * {line}\n" if line else " *\n" for line in lines.splitlines())
        + " *\n"
        f" * Written by tests/console_fixtures.py (`{COMMAND}`):\n"
        " * tests/contract/test_console_fixtures.py fails while it differs from what\n"
        " * the server answers. Don't edit it by hand.\n"
        " */"
    )


def you(user: str) -> Principal:
    """The person, signed in as the development sign-in (as every fixture asks)."""
    return Principal(user, None, "dev")


def an_agent(user: str) -> Principal:
    """An AI agent the person connected: another application's sign-in, which
    may draft and propose rules but never activate them."""
    return Principal(user, None, "oauth", first_party_client=False, client_name="Claude")


def a_stale_console(user: str) -> Principal:
    """The console, signed in with a password checked six minutes ago: past
    the five minutes its powerful permissions need."""
    return Principal(
        user,
        None,
        "oauth",
        first_party_client=True,
        client_name="Salli console",
        sign_in_age=timedelta(minutes=6),
        fresh_within=timedelta(seconds=300),
    )


async def ask_as(
    books: Books,
    principal: Principal,
    method: str,
    path: str,
    body: Any = None,
    ok: tuple[int, ...] = (200,),
    files: dict[str, tuple[str, bytes, str]] | None = None,
) -> Any:
    """What the API answers `principal`, as JSON (an error unless its status
    is one of `ok`). `files` makes the request a multipart upload."""
    app = create_app()
    app.dependency_overrides[get_services] = lambda: books.services
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_current_user] = lambda: principal.user_id
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        if files is not None:
            response = await client.request(method, path, files=files)
        else:
            response = await client.request(method, path, json=body)
    if response.status_code not in ok:
        raise RuntimeError(f"{method} {path}: {response.status_code} {response.text}")
    if response.status_code == 204:
        return None
    if response.headers.get("content-type", "").startswith("text/plain"):
        return response.text
    return response.json()


# ── Books: imports, review and rules ─────────────────────────────────────────

BOOKS_HEADER = _header(
    "What a real server answers the console's imports, review queue and\n"
    "categorisation rules (docs/design/console.md, section 5) on the golden\n"
    "household ledger (tests/golden/household.py, as of Oct 11, 2026, in\n"
    "euros): the person's rule for FreshMart, then a checking statement for\n"
    "October so far imported against it (no model is set up, so only the rule\n"
    "sorts it). The writes at the end (an account chosen, two posted, two\n"
    "discarded, rules tested, refused, made and edited) come after every read,\n"
    "so the reads are what the console sees first."
)

#: The person's own rule, before the import.
FRESHMART_RULE = {
    "name": "FreshMart is groceries",
    "conditions": [{"field": "description", "operator": "contains", "value": "FRESHMART"}],
    "actions": {"account_id": "food", "category": "groceries", "need": "essential"},
}
#: Checking's statement for October so far, as the bank exports it: the rent
#: and the car loan are booked already; the bakery and the refund are new.
OCTOBER_CSV = (
    "Date,Description,Amount\n"
    "2026-10-01,CITY LETTINGS RENT,-1500.00\n"
    "2026-10-05,AUTOFIN CAR LOAN,-350.00\n"
    "2026-10-07,CORNER BAKERY,-8.40\n"
    "2026-10-09,FRESHMART,-46.20\n"
    "2026-10-10,HARDWARE STORE REFUND,19.99\n"
)
#: A rule the console tests against what is already booked.
BISTRO_RULE = {
    "name": "Bistro Novo is eating out",
    "conditions": [{"field": "description", "operator": "contains", "value": "BISTRO"}],
    "actions": {"account_id": "out", "category": "eating-out", "need": "discretionary"},
}
#: A rule Salli refuses: its pattern doesn't compile.
BROKEN_RULE = {
    "name": "Anything in brackets",
    "conditions": [{"field": "description", "operator": "matches", "value": "(UNCLOSED"}],
    "actions": {"account_id": "out"},
}
#: The one bank connection the household has: SimpleFIN, feeding checking.
BANK_CONNECTION = {
    "id": "bank-1",
    "user_id": h.USER,
    "provider": "simplefin",
    "name": "Example Bank",
    "status": "ok",
    "last_error": None,
    "warnings": [],
    "last_synced_at": dt.datetime(2026, 10, 11, 6, 0, tzinfo=dt.UTC),
    "created_at": dt.datetime(2026, 9, 1, 9, 0, tzinfo=dt.UTC),
    "accounts": [
        {
            "remote_id": "ACT-1",
            "name": "Everyday checking",
            "institution": "Example Bank",
            "currency": "EUR",
            "balance": Decimal("2104.33"),
            "balance_date": dt.datetime(2026, 10, 11, 6, 0, tzinfo=dt.UTC),
            "account_id": "chk",
            "last_imported_at": dt.datetime(2026, 10, 11, 6, 0, tzinfo=dt.UTC),
            "notes": None,
        }
    ],
}


async def books_household(clock: Clock) -> Books:
    """The golden household with the import's services: its rules, the
    statement import (no model: only rules sort a statement) and its bank
    connections, over in-memory storage."""
    uow = h.uow()
    uow.rules = FakeRules(clock)
    uow.statements = FakeStatements(clock)
    uow.bank_connections = FakeBankConnections()
    uow.bank_connections.connections.append(copy.deepcopy(BANK_CONNECTION))
    rules = RulesService(uow.factory())
    services = SimpleNamespace(
        rules=rules,
        parsing=ParsingService(uow.factory(), fx=h.fx(), rules=rules),
        bank_connections=BankConnectionService(uow.factory(), ClosedKeyRing(), {}),
        entitlements=FullAccess(),
        usage=None,
    )
    return Books(h.USER, services)


async def books_fixtures() -> list[Fixture]:
    clock = Clock(dt.datetime(2026, 10, 1, 9, 0, tzinfo=dt.UTC))
    with clocked(clock):
        return await _books_fixtures(clock)


async def _books_fixtures(clock: Clock) -> list[Fixture]:
    books = await books_household(clock)
    me = you(books.user)

    async def send(method: str, path: str, body: Any = None, ok: tuple[int, ...] = (200,)) -> Any:
        return await ask_as(books, me, method, path, body, ok=ok)

    # The person's own: the rule first, then the statement, on the household's date.
    rule = await send("POST", "/v1/rules", FRESHMART_RULE, (201,))
    clock.at = dt.datetime(2026, 10, 11, 9, 30, tzinfo=dt.UTC)
    upload = await ask_as(
        books,
        me,
        "POST",
        "/v1/statements/upload?account_id=chk&bank=Example%20Bank",
        ok=(202,),
        files={"file": ("checking-october.csv", OCTOBER_CSV.encode(), "text/csv")},
    )
    statement = upload["statement_id"]
    by = {t["description"]: t for t in upload["transactions"]}

    reads = [
        Fixture(
            "UPLOADED",
            "StatementUpload",
            "The answer to importing checking-october.csv into Checking.",
            upload,
        ),
        Fixture("STATEMENTS", "BankStatementList", None, await send("GET", "/v1/statements/")),
        Fixture(
            "PENDING",
            "PendingStatementTransactions",
            "The October statement's transactions waiting for review.",
            await send("GET", f"/v1/statements/{statement}"),
        ),
        Fixture("RULES", "CategorizationRule[]", None, await send("GET", "/v1/rules")),
        Fixture(
            "SUGGESTIONS",
            "RuleSuggestion[]",
            "The rules the household's own bookkeeping implies.",
            await send("GET", "/v1/rules/suggestions"),
        ),
        Fixture("BANKS", "BankConnections", None, await send("GET", "/v1/bank-connections")),
    ]
    suggestions = reads[4].value

    # The console's writes, after every read.
    clock.at = dt.datetime(2026, 10, 11, 10, 0, tzinfo=dt.UTC)
    bakery, freshmart = by["CORNER BAKERY"]["id"], by["FRESHMART"]["id"]
    rent, loan = by["CITY LETTINGS RENT"]["id"], by["AUTOFIN CAR LOAN"]["id"]
    choice = {"choices": [{"transaction_id": bakery, "account_id": "out"}]}
    categorized = await send("POST", "/v1/statements/categorize", choice)
    after_choice = await send("GET", f"/v1/statements/{statement}")
    posted = await send(
        "POST", f"/v1/statements/{statement}/post", {"approved_ids": [freshmart, bakery]}
    )
    after_post = await send("GET", f"/v1/statements/{statement}")
    discarded = await send("POST", f"/v1/statements/{statement}/discard", {"ids": [rent, loan]})
    after_discard = await send("GET", f"/v1/statements/{statement}")
    refused_upload = await ask_as(
        books,
        me,
        "POST",
        "/v1/statements/upload?account_id=chk",
        ok=(422,),
        files={"file": ("notes.csv", b"Nothing,to,see\n", "text/csv")},
    )
    writes = [
        Fixture("CATEGORIZED", "CategorizedTransactions", "The bakery is eating out.", categorized),
        Fixture("PENDING_CHOSEN", "PendingStatementTransactions", None, after_choice),
        Fixture("POSTED", "PostedStatementTransactions", "FreshMart and the bakery.", posted),
        Fixture("PENDING_POSTED", "PendingStatementTransactions", None, after_post),
        Fixture(
            "DISCARDED",
            "DiscardedStatementTransactions",
            "The rent and the car loan: already booked.",
            discarded,
        ),
        Fixture("PENDING_DISCARDED", "PendingStatementTransactions", None, after_discard),
        Fixture(
            "STATEMENTS_REVIEWED",
            "BankStatementList",
            "After the console's writes.",
            await send("GET", "/v1/statements/"),
        ),
        Fixture(
            "UPLOAD_REFUSED",
            "ProblemDetails",
            "A file with no transactions in it.",
            refused_upload,
        ),
        Fixture(
            "RULE_TEST",
            "RuleTestResult",
            "Bistro Novo, tested against what is booked.",
            await send("POST", "/v1/rules/test", BISTRO_RULE),
        ),
        Fixture(
            "RULE_REFUSED",
            "ProblemDetails",
            "A pattern that doesn't compile.",
            await send("POST", "/v1/rules", BROKEN_RULE, (422,)),
        ),
    ]
    first = {
        k: v for k, v in suggestions[0].items() if k not in ("support", "agreement", "examples")
    }
    made = await send("POST", "/v1/rules", first, (201,))
    edited = await send(
        "PATCH", f"/v1/rules/{rule['id']}", {"name": "FreshMart: groceries", "priority": 10}
    )
    writes += [
        Fixture("RULE_MADE", "Ref", "The first suggestion, made a rule.", made),
        Fixture("RULE_EDITED", "Ref", None, edited),
        Fixture("RULES_EDITED", "CategorizationRule[]", None, await send("GET", "/v1/rules")),
    ]
    return [*reads, *writes]


# ── Tax: rule sets, their versions, and the tax they compute ────────────────

TAX_HEADER = _header(
    "What a real server answers the console's tax pages on the fictional rules\n"
    '"XA 2031" (tests/golden/rules/xa2031.json, with a filing deadline) and the\n'
    "taxed household (tests/golden/taxed.py, as of Jun 30, 2031, in New Zealand\n"
    "dollars; XA is a user-assigned code, no country's). Version 1 is the\n"
    "person's, active, with a computation; version 2 an agent's, proposed;\n"
    "version 3 an agent's draft whose worked example fails. The writes at the\n"
    "end (activating version 2, first from a sign-in six minutes old, then\n"
    "just after the password; computing again; version 3 validated and its\n"
    "proposal refused) come after every read."
)

#: Version 1: the rules as the golden tests know them, with a deadline.
XA_V1: dict[str, Any] = {
    **copy.deepcopy(taxed.RULES),
    "deadlines": [{"key": "return", "label": "Return due", "date": "2032-04-30", "source": "act"}],
}


def _v2() -> dict[str, Any]:
    """Version 2: the relief raised to 12,500 by the (fictional) 2031 budget,
    with the worked examples worked again."""
    doc = copy.deepcopy(XA_V1)
    doc["sources"].append(
        {
            "id": "budget",
            "url": "https://example.org/xa/budget-2031",
            "title": "XA Budget 2031 (fictional)",
            "retrieved": "2031-06-01",
        }
    )
    for block in doc["blocks"]:
        if block["key"] == "relief":
            block["amount"] = "12500"
            block["source"] = "budget"
    doc["examples"] = [
        {
            "name": "48,000",
            "source": "budget",
            "inputs": {"salary": "48000"},
            "expected": {"payable": "7100"},
        },
        {
            "name": "54,000",
            "source": "budget",
            "inputs": {"salary": "54000"},
            "expected": {"payable": "8600"},
        },
        {
            "name": "60,000",
            "source": "budget",
            "inputs": {"salary": "60000"},
            "expected": {"payable": "11000"},
        },
        {
            "name": "A pension contribution",
            "source": "budget",
            "inputs": {"salary": "54000", "pension": "6000"},
            "expected": {"payable": "7100"},
        },
    ]
    return doc


XA_V2 = _v2()


def _v3() -> dict[str, Any]:
    """Version 3: an agent's draft whose second example expects the old
    relief's figure."""
    doc = copy.deepcopy(XA_V2)
    doc["examples"][1]["expected"]["payable"] = "8800"
    return doc


XA_V3 = _v3()


async def tax_household(clock: Clock) -> Books:
    """The taxed household, with no rules yet: the person adds them."""
    ledger = taxed.ledger(active=False)
    uow = ledger.uow
    uow.tax_rule_sets = FakeTaxRuleSets(clock)
    uow.tax_computations = FakeTaxComputations(clock, uow.tax_rule_sets)
    uow.audit_log = FakeAuditLog()
    rules = TaxRuleService(uow.factory(), fx=FakeFx({}), clock=clock)
    services = SimpleNamespace(
        tax_rules=rules,
        tax=TaxService(uow.factory(), rules, clock=lambda: taxed.AS_OF),
        entitlements=FullAccess(),
    )
    return Books(taxed.USER, services)


async def tax_fixtures() -> list[Fixture]:
    clock = Clock(dt.datetime(2031, 2, 1, 9, 0, tzinfo=dt.UTC))
    books = await tax_household(clock)
    me, agent = you(books.user), an_agent(books.user)

    async def send(
        method: str, path: str, body: Any = None, ok: tuple[int, ...] = (200,), who: Principal = me
    ) -> Any:
        return await ask_as(books, who, method, path, body, ok=ok)

    # Version 1, the person's: added, activated, and the tax computed with it.
    v1 = await send(
        "POST", "/v1/tax/rule-sets", {"document": XA_V1, "note": "From the Act"}, (201,)
    )
    base = f"/v1/tax/rule-sets/{v1['rule_set_id']}"
    await send("POST", f"{base}/versions/{v1['id']}/activate")
    clock.at = dt.datetime(2031, 5, 31, 18, 0, tzinfo=dt.UTC)
    await send("POST", "/v1/tax/compute")
    # Version 2, an agent's: drafted, then proposed for the person to review.
    clock.at = dt.datetime(2031, 6, 20, 14, 0, tzinfo=dt.UTC)
    v2 = await send(
        "POST",
        f"{base}/versions",
        {"document": XA_V2, "note": "The 2031 budget raises the relief to 12,500."},
        (201,),
        agent,
    )
    await send("POST", f"{base}/versions/{v2['id']}/propose", who=agent)
    # Version 3, an agent's draft with an example that doesn't pass.
    clock.at = dt.datetime(2031, 6, 25, 11, 0, tzinfo=dt.UTC)
    v3 = await send(
        "POST",
        f"{base}/versions",
        {"document": XA_V3, "note": "Rounding the examples."},
        (201,),
        agent,
    )

    reads = [
        Fixture("RULE_SETS", "TaxRuleSet[]", None, await send("GET", "/v1/tax/rule-sets")),
        Fixture("RULE_SET", "TaxRuleSet", None, await send("GET", base)),
        Fixture(
            "VERSION_1",
            "TaxRuleSetVersion",
            "The person's, active.",
            await send("GET", f"{base}/versions/{v1['id']}"),
        ),
        Fixture(
            "VERSION_2",
            "TaxRuleSetVersion",
            "An agent's, proposed.",
            await send("GET", f"{base}/versions/{v2['id']}"),
        ),
        Fixture(
            "VERSION_3",
            "TaxRuleSetVersion",
            "An agent's draft: one worked example fails.",
            await send("GET", f"{base}/versions/{v3['id']}"),
        ),
        Fixture(
            "DIFF_2",
            "TaxRuleDiff",
            "Version 2 against the active version.",
            await send("GET", f"{base}/diff?to={v2['id']}"),
        ),
        Fixture(
            "DIFF_3",
            "TaxRuleDiff",
            "Version 3 against the active version.",
            await send("GET", f"{base}/diff?to={v3['id']}"),
        ),
        Fixture(
            "DIFF_1",
            "TaxRuleDiff",
            "Version 1, the first: nothing before it.",
            await send("GET", f"{base}/diff?to={v1['id']}&from={v1['id']}"),
        ),
        Fixture(
            "EXPORT_2",
            "TaxRuleExport",
            None,
            await send("GET", f"{base}/versions/{v2['id']}/export"),
        ),
        Fixture("YEAR", "TaxYearStatus", None, await send("GET", "/v1/tax/current-year")),
        Fixture("LATEST", "LatestTaxComputation", None, await send("GET", "/v1/tax/latest")),
        Fixture(
            "EXPLAINED",
            "TaxLineExplanation",
            "Where the income tax line came from.",
            await send("POST", "/v1/tax/explain", {"line_key": "income_tax"}),
        ),
    ]

    # The console's writes, after every read.
    clock.at = dt.datetime(2031, 6, 30, 9, 0, tzinfo=dt.UTC)
    step_up = await send(
        "POST", f"{base}/versions/{v2['id']}/activate", ok=(403,), who=a_stale_console(books.user)
    )
    clock.at = dt.datetime(2031, 6, 30, 9, 6, tzinfo=dt.UTC)
    activated = await send("POST", f"{base}/versions/{v2['id']}/activate")
    after = [
        Fixture(
            "STEP_UP",
            "ProblemDetails",
            "Activating version 2 from the console, six minutes after the password.",
            step_up,
        ),
        Fixture(
            "ACTIVATED",
            "TaxRuleSetVersion",
            "Version 2, activated just after the password.",
            activated,
        ),
        Fixture("RULE_SET_ACTIVATED", "TaxRuleSet", None, await send("GET", base)),
        Fixture(
            "VERSION_1_SUPERSEDED",
            "TaxRuleSetVersion",
            None,
            await send("GET", f"{base}/versions/{v1['id']}"),
        ),
        Fixture(
            "COMPUTED",
            "TaxComputation",
            "Computed again, with version 2.",
            await send("POST", "/v1/tax/compute"),
        ),
        Fixture(
            "VALIDATED_3",
            "TaxRuleSetVersion",
            "Version 3 validated again: still a draft.",
            await send("POST", f"{base}/versions/{v3['id']}/validate"),
        ),
        Fixture(
            "PROPOSE_REFUSED",
            "ProblemDetails",
            "Proposing version 3, whose example fails.",
            await send("POST", f"{base}/versions/{v3['id']}/propose", ok=(409,)),
        ),
    ]
    return [*reads, *after]


# ── Settings: tokens, model keys, digests and exports ───────────────────────

SETTINGS_HEADER = _header(
    "What a real server answers the console's settings (docs/design/console.md,\n"
    "section 5) on the golden household (tests/golden/household.py, as of Oct\n"
    "11, 2026, in euros): two personal access tokens and an Anthropic key kept\n"
    "before the reads, a weekly digest set up and sent on Monday Oct 5; then\n"
    "the console's writes, after every read: a token made with tax:activate\n"
    "(its secret shown this once, a fixture's, never a real one), the same\n"
    "asked for by a console sign-in whose password is six minutes old (the\n"
    "step-up answer), and a key the provider refuses. No secret here opens\n"
    "anything."
)

#: What each fixture token says in place of 43 random characters: no secret.
TOKEN_BODIES = ("backups", "spreadsheet", "tax-helper", "spare")
#: The key the person keeps for Anthropic: a fixture's, not a key.
ANTHROPIC_KEY = "sk-ant-fixture-not-a-key-7f3a"
#: The instance's sealing key in the fixtures: 32 bytes of 7s.
SEALING = f"1:{base64.b64encode(bytes([7] * 32)).decode()}"


class _Rejecting:
    """The provider's check: it accepts the person's key and refuses any other."""

    async def __call__(self, provider: str, key: str) -> None:
        if key != ANTHROPIC_KEY:
            raise InvalidProviderKey(provider)


@contextmanager
def deterministic_secrets() -> Iterator[None]:
    """Each token's random part is the fixture's (`fixture-backups-not-a-secret`
    and so on, in the order they are made), so the fixtures stay the same each
    time they are written."""
    names = iter(TOKEN_BODIES)
    with mock.patch.object(
        secrets, "token_urlsafe", lambda n=32: f"fixture-{next(names)}-not-a-secret".ljust(43, "0")
    ):
        yield


def _stopped(clock: Clock) -> type[dt.datetime]:
    """`datetime` whose now() is the fixtures' clock."""

    class _Now(dt.datetime):
        @classmethod
        def now(cls, tz: dt.tzinfo | None = None) -> _Now:  # type: ignore[override]
            return cls.fromtimestamp(clock().timestamp(), tz)

    return _Now


@contextmanager
def clocked(clock: Clock) -> Iterator[None]:
    """What the services stamp with the time (a rule's last hit, a token's
    expiry, when a provider accepted a key) on the fixtures' clock."""
    stopped = _stopped(clock)
    with (
        mock.patch.object(rules_service, "datetime", stopped),
        mock.patch.object(personal_access_token_service, "datetime", stopped),
        mock.patch.object(
            llm_credential_service, "datetime", SimpleNamespace(**{**vars(dt), "datetime": stopped})
        ),
    ):
        yield


async def settings_household(clock: Clock) -> Books:
    """The golden household with what settings read: tokens, model keys, the
    digest and the plain-text exports."""
    from tests.console_fixtures import home_writes, household

    books = await household()
    await home_writes(books)
    uow = books.services.ledger._uow_factory()
    uow.personal_access_tokens = FakeTokens(clock)
    uow.llm_credentials = FakeLlmCredentials()
    uow.user_profiles.rows.setdefault(h.USER, {})

    async def get_ai_settings(user_id: str) -> dict[str, Any]:
        row = uow.user_profiles.rows.get(user_id, {})
        return {"provider": row.get("ai_provider"), "models": dict(row.get("ai_models") or {})}

    uow.user_profiles.get_ai_settings = get_ai_settings
    s = books.services
    s.tokens = PersonalAccessTokenService(uow.factory())
    s.llm_credentials = LlmCredentialService(
        uow.factory(), KeyRing(SEALING), validator=_Rejecting()
    )
    s.notifications = NotificationService(
        uow.factory(),
        s.reminders,
        s.insights,
        RecordingNotifier(),
        notifier_name="email",
        clock=clock,
    )
    s.data_portability = DataPortabilityService(uow.factory(), *([None] * 12))
    s.entitlements = FullAccess()
    return books


async def settings_fixtures() -> list[Fixture]:
    clock = Clock(dt.datetime(2026, 9, 1, 9, 0, tzinfo=dt.UTC))
    with deterministic_secrets(), clocked(clock):
        return await _settings_fixtures(clock)


async def _settings_fixtures(clock: Clock) -> list[Fixture]:
    books = await settings_household(clock)
    me = you(books.user)

    async def send(
        method: str, path: str, body: Any = None, ok: tuple[int, ...] = (200,), who: Principal = me
    ) -> Any:
        return await ask_as(books, who, method, path, body, ok=ok)

    # The person's own, before the household's date.
    await send("POST", "/v1/tokens", {"name": "Backups", "expires_in_days": 90}, (201,))
    clock.at = dt.datetime(2026, 9, 15, 20, 0, tzinfo=dt.UTC)
    await send("PUT", "/v1/llm-keys/anthropic", {"key": ANTHROPIC_KEY}, (204,))
    clock.at = dt.datetime(2026, 10, 1, 8, 0, tzinfo=dt.UTC)
    await send("POST", "/v1/tokens", {"name": "Spreadsheet"}, (201,))
    await send(
        "PATCH",
        "/v1/notifications/preferences",
        {"enabled": True, "time_zone": "Europe/Lisbon", "hour": 8, "weekday": "monday"},
    )
    # Monday Oct 5, 08:00 in Lisbon: the digest goes out.
    monday = dt.datetime(2026, 10, 5, 7, 0, tzinfo=dt.UTC)
    clock.at = monday
    await books.services.notifications.send_due(monday)
    clock.at = dt.datetime(2026, 10, 11, 10, 0, tzinfo=dt.UTC)

    reads = [
        Fixture("TOKENS", "PersonalAccessToken[]", None, await send("GET", "/v1/tokens")),
        Fixture("LLM_KEYS", "LlmKeys", None, await send("GET", "/v1/llm-keys")),
        Fixture("AI_SETTINGS", "AiSettings", None, await send("GET", "/v1/ai/settings")),
        Fixture(
            "PREFERENCES",
            "NotificationPreferences",
            None,
            await send("GET", "/v1/notifications/preferences"),
        ),
        Fixture(
            "PREVIEW",
            "DigestPreview",
            "The digest as it would go now.",
            await send("GET", "/v1/notifications/preview"),
        ),
        Fixture(
            "DELIVERIES",
            "DigestDeliveries",
            "The digest sent on Monday.",
            await send("GET", "/v1/notifications/deliveries"),
        ),
        Fixture(
            "BEANCOUNT",
            "string",
            "The ledger as a Beancount file.",
            await send("GET", "/v1/export/beancount"),
        ),
        Fixture(
            "HLEDGER",
            "string",
            "The ledger as an hledger journal.",
            await send("GET", "/v1/export/hledger"),
        ),
    ]

    created = await send(
        "POST", "/v1/tokens", {"name": "Tax helper", "permissions": ["tax:activate"]}, (201,)
    )
    writes = [
        Fixture(
            "TOKEN_MADE",
            "NewPersonalAccessToken",
            "A token made with tax:activate: its secret, shown this once (a fixture's).",
            created,
        ),
        Fixture(
            "TOKEN_STEP_UP",
            "ProblemDetails",
            "The same, asked for by a console sign-in six minutes after the password.",
            await send(
                "POST",
                "/v1/tokens",
                {"name": "Tax helper", "permissions": ["tax:activate"]},
                (403,),
                a_stale_console(books.user),
            ),
        ),
        Fixture(
            "TOKEN_REFUSED",
            "ProblemDetails",
            "A token with no name.",
            await send("POST", "/v1/tokens", {"name": ""}, (422,)),
        ),
        Fixture(
            "KEY_REFUSED",
            "ProblemDetails",
            "A key OpenAI refuses.",
            await send("PUT", "/v1/llm-keys/openai", {"key": "sk-fixture-wrong"}, (400,)),
        ),
        Fixture(
            "PREFERENCES_SAVED",
            "NotificationPreferences",
            "Monthly instead, at 7.",
            await send("PATCH", "/v1/notifications/preferences", {"cadence": "monthly", "hour": 7}),
        ),
    ]
    return [*reads, *writes]


FILES: dict[str, tuple[str, Any]] = {
    "books.ts": (BOOKS_HEADER, books_fixtures),
    "tax.ts": (TAX_HEADER, tax_fixtures),
    "settings.ts": (SETTINGS_HEADER, settings_fixtures),
}
