"""
The console's fixtures, written by the real server.

The console's component tests and its visual and accessibility runs
(packages/console/test, packages/console/e2e) answer the API with the
fixtures in `packages/console/test/fixtures/`: what the API app
(`interfaces/api/main.create_app`, so through its request and response
models) answers on the golden household (tests/golden/household.py: euros,
as of 2026-10-11).

- `home.ts`: Home's eight reads, with two reminders of the person's own and
  a decision recorded in August, due for review on 2026-09-30.
- `lab.ts`: the decision lab's reads on the same household after the
  person's own writes (three principles, one archived; a laptop weighed with
  the afford-it template and recorded on the household's date, with a note),
  and the answers to the writes the console makes, made after every read (a
  principle added, edited and refused; a template's answers refused; the
  August decision reviewed). Its reviews due are Home's, which the console
  reads for both.
- `where.ts`: where you stand (C2): the accounts and the ledger, cash,
  attention and financial independence, on Home's household after one
  reminder of the person's own marked done; then the answers to the writes
  those pages make, made after every read (an entry posted, read back and
  reversed; one posted in dollars at the published rate; one refused for
  want of a rate; a reversal refused; an FI assumption set, and one
  refused), and the strategy of a household that has one.

So the console's tests read exactly what the server sends today: a fixture
goes stale when an engine, a service or a response model changes, and
`tests/contract/test_console_fixtures.py` fails until they are written
again:

    uv run python -m tests.console_fixtures            # write them
    uv run python -m tests.console_fixtures --check    # what the contract test does

The ids the services make (the reminders', the decisions', the
principles', the entries') are fixed, so each file is the same each time it
is written. The golden ledger's postings carry no ids (a database gives
them), so `where.ts` gives each its entry's id and its place: `e070.1`.
The sign-in's own fixtures (who is signed in, the profile, the sign-ins) are
not a household's books, and are written by hand in `auth.ts` beside them,
typed by the SDK.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
import sys
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

from httpx import ASGITransport, AsyncClient

from salli.application.defaults import FullAccess
from salli.application.services import fi_service
from salli.application.services.baseline_service import BaselineService
from salli.application.services.debt_service import DebtService
from salli.application.services.decision_service import DecisionService
from salli.application.services.fi_service import FiService
from salli.application.services.insights_service import InsightsService
from salli.application.services.ledger_service import LedgerService
from salli.application.services.portfolio_service import PortfolioService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.reminder_service import ReminderService
from salli.application.services.report_service import ReportService
from salli.application.services.scenario_service import ScenarioService
from salli.application.services.template_service import TemplateService
from salli.interfaces.api.deps import Principal, get_current_user, get_principal, get_services
from salli.interfaces.api.main import create_app
from tests import fakes
from tests.cli_fixtures import Books, Fixture, ask, render, uid
from tests.golden import household as h

FIXTURES = Path(__file__).resolve().parents[1] / "packages" / "console" / "test" / "fixtures"
COMMAND = "uv run python -m tests.console_fixtures"

#: Home's month so far, as the console asks for it on the household's date.
MONTH = {"from_date": "2026-10-01", "to_date": h.AS_OF.isoformat()}

HEADER = (
    "/**\n"
    " * What a real server answers Home's eight reads (docs/design/console.md,\n"
    " * section 5) on the golden household ledger (tests/golden/household.py,\n"
    " * as of Oct 11, 2026, in euros), with two reminders of the person's own\n"
    " * and a decision recorded in August that is due for review.\n"
    " *\n"
    f" * Written by tests/console_fixtures.py (`{COMMAND}`):\n"
    " * tests/contract/test_console_fixtures.py fails while it differs from what\n"
    " * the server answers. Don't edit it by hand.\n"
    " */"
)


@contextlib.contextmanager
def fixed_ids() -> Iterator[None]:
    """The ids services make with uuid4, as uid(9001), uid(9002), …, in order."""
    counter = iter(range(9001, 10000))
    with mock.patch.object(uuid, "uuid4", lambda: uuid.UUID(uid(next(counter)))):
        yield


#: When Home's decision was recorded, and when the decision lab's writes are
#: made: the household's date, in the morning.
AUGUST = dt.datetime(2026, 8, 11, 9, tzinfo=dt.UTC)
OCTOBER = dt.datetime(2026, 10, 11, 10, tzinfo=dt.UTC)


class _October(dt.datetime):
    """The time the in-memory repositories stamp on a row (a principle's
    `created_at`, as the database's `now()` would): the household's date."""

    @classmethod
    def now(cls, tz: dt.tzinfo | None = None) -> _October:  # type: ignore[override]
        return cls.fromtimestamp(OCTOBER.timestamp(), tz)


@contextlib.contextmanager
def stamped_in_october() -> Iterator[None]:
    """Rows the fakes stamp, and an assumption's `set_at`, on the household's
    date."""
    clock = SimpleNamespace(**{**vars(dt), "datetime": _October})
    with (
        mock.patch.object(fakes, "datetime", _October),
        mock.patch.object(fi_service, "datetime", clock),
    ):
        yield


@dataclass
class Clock:
    """When the decision journal records something: Home's decision in
    August, the decision lab's writes on the household's date."""

    at: dt.datetime = AUGUST

    def now(self) -> dt.datetime:
        return self.at


async def household() -> Books:
    """The golden household, with every service Home and the decision lab
    read."""
    uow = h.uow()
    today = lambda: h.AS_OF  # noqa: E731
    baselines = BaselineService(uow.factory(), fx=h.fx(), today=today)
    ledger = LedgerService(uow.factory(), fx=h.fx())
    fi = FiService(uow.factory(), baselines=baselines, today=today)
    scenarios = ScenarioService(uow.factory(), baselines=baselines)
    principles = PrincipleService(uow.factory(), scenarios)
    clock = Clock()
    services = SimpleNamespace(
        ledger=ledger,
        fi=fi,
        reports=ReportService(ledger, fi),
        reminders=ReminderService(uow.factory()),
        insights=InsightsService(uow.factory(), today=today, baselines=baselines),
        baseline=baselines,
        debt=DebtService(uow.factory(), baselines=baselines, today=today),
        portfolio=PortfolioService(uow.factory(), today=today),
        scenarios=scenarios,
        principles=principles,
        templates=TemplateService(scenarios, principles),
        decisions=DecisionService(
            uow.factory(), scenarios, PrincipleService(uow.factory(), scenarios), now=clock.now
        ),
        # Not a service: the journal's clock, which the decision lab moves on.
        clock=clock,
    )
    return Books(h.USER, services)


async def home_writes(books: Books) -> None:
    """What the person did before Home's reads: two reminders of their own,
    and a decision recorded in August, due for review on 2026-09-30."""

    async def post(path: str, body: dict[str, Any]) -> None:
        await ask(books, "POST", path, body, ok=(201,))

    await post("/v1/reminders/", {"kind": "Renew the car's insurance", "due_date": "2026-10-20"})
    await post(
        "/v1/reminders/", {"kind": "Send the landlord the signed lease", "due_date": "2026-10-05"}
    )
    keep = {"schema": "salli.scenario/1", "label": "Keep as is", "as_of": "2026-08-11"}
    await post(
        "/v1/decisions",
        {
            "question": "Change anything?",
            "options": [keep],
            "chosen": "Keep as is",
            "reasons": "It works.",
            "review_on": "2026-09-30",
        },
    )


async def home_fixtures() -> list[Fixture]:
    books = await household()
    await home_writes(books)
    month = f"from_date={MONTH['from_date']}&to_date={MONTH['to_date']}"

    async def get(path: str) -> Any:
        return await ask(books, "GET", path)

    return [
        Fixture("BALANCE_SHEET", "BalanceSheet", None, await get("/v1/reports/balance-sheet")),
        Fixture(
            "INCOME_STATEMENT",
            "IncomeStatement",
            "October 1 to 11, 2026: the month so far on the household's date.",
            await get(f"/v1/ledger/income-statement?{month}"),
        ),
        Fixture("FI_SCORE", "FiScore", None, await get("/v1/fi/score")),
        Fixture("REMINDERS", "ReminderList", None, await get("/v1/reminders/?status=pending")),
        Fixture("SAFE_TO_SPEND", "SafeToSpend", None, await get("/v1/insights/safe-to-spend")),
        Fixture("SIGNALS", "FinanceSignals", None, await get("/v1/insights/signals")),
        Fixture("REVIEWS_DUE", "DueReviews", None, await get("/v1/decisions/reviews")),
        Fixture(
            "NET_WORTH", "NetWorthByMonth", None, await get("/v1/insights/net-worth?months=12")
        ),
    ]


LAB_HEADER = (
    "/**\n"
    " * What a real server answers the decision lab's reads and writes\n"
    " * (docs/design/console.md, section 5) on the golden household ledger\n"
    " * (tests/golden/household.py, as of Oct 11, 2026, in euros), after what\n"
    " * Home's fixtures (home.ts) rest on: three principles (one archived), a\n"
    " * laptop weighed with the afford-it template and recorded on Oct 11 with a\n"
    " * note, beside the August decision that is due for review. The writes at\n"
    " * the end (a principle added and edited, the August decision reviewed)\n"
    " * come after every read, so the reads are what the console sees first.\n"
    " *\n"
    f" * Written by tests/console_fixtures.py (`{COMMAND}`):\n"
    " * tests/contract/test_console_fixtures.py fails while it differs from what\n"
    " * the server answers. Don't edit it by hand.\n"
    " */"
)

SIX_MONTHS = {"label": "Six months of essentials in cash", "check": "emergency_months >= 6"}
CHECKING = {
    "label": "Checking above 5,000",
    "check": "account_lowest >= 5000",
    "account": "chk",
    "note": "The rent and the card come out of it.",
}
DEAR_DEBT = {
    "label": "Clear debt above 7% before investing",
    "check": "max_debt_rate_while_investing <= 0.07",
}
#: The afford-it answers the laptop was weighed with.
LAPTOP_ANSWERS = {
    "price": "2400.00",
    "what": "Laptop",
    "date": "2026-11-02",
    "account": "chk",
    "instalment_months": 12,
    "instalment_rate": "0.069",
    "wait_months": 6,
    "save_monthly": "400.00",
    "horizon_years": 5,
}
RENT_OR_BUY_ANSWERS = {
    "price": "350000.00",
    "deposit": "70000.00",
    "account": "chk",
    "mortgages": [
        {"annual_rate": "0.042", "term_months": 300},
        {"annual_rate": "0.039", "term_months": 240, "label": "Shorter"},
    ],
    "buying_costs": "9000.00",
    "owning_costs": "250.00",
    "rent": "city",
    "selling_costs": "0.03",
}
EMERGENCY_ANSWERS = {"target_months": "9", "set_aside": ["200.00", "500.00"], "horizon_years": 5}
LAPTOP = {
    "type": "one_off",
    "date": "2026-11-02",
    "amount": "-2400.00",
    "account": "chk",
    "label": "Laptop",
}
INSTALMENTS = {
    "type": "loan",
    "principal": "2400.00",
    "annual_rate": "0.069",
    "term_months": 12,
    "start": "2026-11-02",
    "into": "chk",
    "label": "Laptop instalments",
}


def scenario(label: str, *changes: dict[str, Any]) -> dict[str, Any]:
    """An option over five years, as the laptop is weighed."""
    return {
        "schema": "salli.scenario/1",
        "label": label,
        "horizon_years": 5,
        "changes": list(changes),
    }


async def lab_fixtures(home_due: Any) -> list[Fixture]:
    """The decision lab on the household Home shows: its reads after the
    person's own writes, then the answers to the writes the console makes.
    Its reviews due must be Home's (`home_due`), which the console reads for
    both."""
    books = await household()
    await home_writes(books)
    books.services.clock.at = OCTOBER

    async def get(path: str) -> Any:
        return await ask(books, "GET", path)

    async def post(path: str, body: Any = None, ok: tuple[int, ...] = (200,)) -> Any:
        return await ask(books, "POST", path, body, ok=ok)

    # The person's own writes, before anything is read.
    kept = [await post("/v1/principles", p, ok=(201,)) for p in (SIX_MONTHS, CHECKING, DEAR_DEBT)]
    await post(f"/v1/principles/{kept[2]['id']}/archive")
    afford = await post("/v1/decisions/start", {"template": "afford-it", "answers": LAPTOP_ANSWERS})
    recorded = await post(
        "/v1/decisions",
        {
            "question": "Laptop: pay cash, spread it or wait?",
            "options": afford["record"]["options"],
            "chosen": afford["record"]["labels"][0],
            "reasons": "The old one is failing, and I would rather not owe anything.",
            "review_on": "2027-04-30",
        },
        ok=(201,),
    )
    laptop = recorded["id"]
    note = await post(
        f"/v1/decisions/{laptop}/notes",
        {"text": "The shop held the price until November."},
        ok=(201,),
    )
    due = await get("/v1/decisions/reviews")
    august = due["reviews"][0]["id"]
    compare = {
        "options": [scenario("Pay cash", LAPTOP), scenario("Instalments", LAPTOP, INSTALMENTS)]
    }

    reads = [
        Fixture("BASELINE", "Baseline", None, await get("/v1/baseline")),
        Fixture("ACCOUNTS", "Account[]", None, await get("/v1/accounts/")),
        Fixture("DEBTS", "DebtList", None, await get("/v1/debt/?active_only=true")),
        Fixture("HOLDINGS", "HoldingList", None, await get("/v1/portfolio/?active_only=true")),
        Fixture("RECURRING", "RecurringPayments", None, await get("/v1/insights/recurring")),
        Fixture("TEMPLATES", "DecisionTemplateList", None, await get("/v1/decisions/templates")),
        *[
            Fixture(name, "DecisionTemplate", None, await get(f"/v1/decisions/templates/{id_}"))
            for name, id_ in (
                ("AFFORD_IT", "afford-it"),
                ("DEBT_OR_INVEST", "debt-or-invest"),
                ("WINDFALL", "windfall"),
                ("BIG_CHANGE", "big-change"),
                ("BORROW", "borrow"),
                ("EMERGENCY_FUND", "emergency-fund"),
                ("RENT_OR_BUY", "rent-or-buy"),
            )
        ],
        Fixture(
            "AFFORD_IT_START",
            "DecisionStart",
            "The laptop: 2,400.00 on Nov 2, paid at once, over 12 months at 6.9%, or\n"
            "after six months of setting 400.00 aside; over five years.",
            await post("/v1/decisions/start", {"template": "afford-it", "answers": LAPTOP_ANSWERS}),
        ),
        Fixture(
            "RENT_OR_BUY_START",
            "DecisionStart",
            "Keep renting from City Lettings, or buy a home for 350,000.00 with\n"
            "70,000.00 down on either of two mortgages.",
            await post(
                "/v1/decisions/start", {"template": "rent-or-buy", "answers": RENT_OR_BUY_ANSWERS}
            ),
        ),
        Fixture(
            "EMERGENCY_FUND_START",
            "DecisionStart",
            "Nine months of spending in cash, setting aside 200.00 or 500.00 a month.",
            await post(
                "/v1/decisions/start", {"template": "emergency-fund", "answers": EMERGENCY_ANSWERS}
            ),
        ),
        Fixture(
            "SCENARIO_RUN",
            "ScenarioRun",
            "The laptop paid at once, with both timelines.",
            await post("/v1/scenarios/run?timeline=true", scenario("Pay cash", LAPTOP)),
        ),
        Fixture(
            "SCENARIO_COMPARISON",
            "ScenarioComparison",
            "Paying cash against instalments, with each option's timelines.",
            await post("/v1/scenarios/compare?timeline=true", compare),
        ),
        Fixture(
            "PRINCIPLES",
            "PrincipleList",
            None,
            await get("/v1/principles?include_archived=true"),
        ),
        Fixture("FIGURES", "DecisionFigures", None, await get("/v1/principles/figures")),
        Fixture(
            "BASELINE_CHECK",
            "PrinciplesCheck",
            "The principles in use, checked on the baseline alone.",
            await post("/v1/principles/check", {"options": []}),
        ),
        Fixture(
            "PRINCIPLE_CHECK",
            "PrinciplesCheck",
            "The principles in use, checked on paying cash and on instalments.",
            await post("/v1/principles/check", compare),
        ),
        Fixture("DECISIONS", "DecisionList", None, await get("/v1/decisions")),
        Fixture(
            "DECISION",
            "Decision",
            "The laptop, with its note.",
            await get(f"/v1/decisions/{laptop}"),
        ),
        Fixture(
            "DECISION_DUE",
            "Decision",
            "The August decision, due for review.",
            await get(f"/v1/decisions/{august}"),
        ),
        Fixture("JOURNAL", "DecisionJournal", None, await get("/v1/decisions/export")),
        Fixture(
            "JOURNAL_MARKDOWN",
            "string",
            None,
            await markdown(books, "/v1/decisions/export/markdown"),
        ),
        Fixture("RECORDED", "Decision", "The answer to recording the laptop.", recorded),
        Fixture("NOTE", "DecisionNote", "The answer to the laptop's note.", note),
    ]
    if due != home_due:
        raise RuntimeError("The decision lab's household has other reviews due than Home's")

    # The console's writes, after every read.
    added = await post(
        "/v1/principles",
        {
            "label": "Never below 2,000 in checking",
            "check": "account_lowest >= 2000",
            "account": "chk",
        },
        ok=(201,),
    )
    edited = await ask(
        books,
        "PATCH",
        f"/v1/principles/{kept[0]['id']}",
        {"label": "Nine months of essentials in cash", "check": "emergency_months >= 9"},
    )
    reviewed = await post(
        f"/v1/decisions/{august}/review",
        {"reflection": "Nothing needed changing, and nothing did."},
        ok=(201,),
    )
    writes = [
        Fixture("PRINCIPLE_ADDED", "Principle", None, added),
        Fixture("PRINCIPLE_EDITED", "Principle", None, edited),
        Fixture(
            "PRINCIPLE_REFUSED",
            "ProblemDetails",
            "A check naming a figure that doesn't exist, refused with where and why.",
            await post(
                "/v1/principles",
                {"label": "Half a year in cash", "check": "emergency_month >= 6"},
                ok=(422,),
            ),
        ),
        Fixture(
            "START_REFUSED",
            "ProblemDetails",
            "Afford it with no price and a rate that isn't one, refused at their paths.",
            await post(
                "/v1/decisions/start",
                {
                    "template": "afford-it",
                    "answers": {"instalment_months": 12, "instalment_rate": "6.9%"},
                },
                ok=(422,),
            ),
        ),
        Fixture(
            "REVIEWED", "DecisionReview", "The answer to reviewing the August decision.", reviewed
        ),
        Fixture(
            "DECISION_REVIEWED",
            "Decision",
            "The August decision once reviewed.",
            await get(f"/v1/decisions/{august}"),
        ),
    ]
    return [*reads, *writes]


WHERE_HEADER = (
    "/**\n"
    " * What a real server answers the pages of where you stand (C2: the\n"
    " * accounts and the ledger, cash, attention, financial independence;\n"
    " * docs/design/console.md, section 5) on the golden household ledger\n"
    " * (tests/golden/household.py, as of Oct 11, 2026, in euros), on what\n"
    " * Home's fixtures (home.ts) rest on and one reminder of the person's own\n"
    " * marked done. The writes at the end (an entry posted and reversed, one\n"
    " * posted in dollars, two refused, an FI assumption set and one refused)\n"
    " * come after every read, so the reads are what the console sees first.\n"
    " *\n"
    f" * Written by tests/console_fixtures.py (`{COMMAND}`):\n"
    " * tests/contract/test_console_fixtures.py fails while it differs from what\n"
    " * the server answers. Don't edit it by hand.\n"
    " */"
)

#: What the person posts from the console: one amount from one account to another.
LUNCH = {
    "entry_date": "2026-10-11",
    "description": "Lunch with a friend",
    "postings": [
        {"account_id": "out", "direction": 1, "amount": "12.50"},
        {"account_id": "chk", "direction": -1, "amount": "12.50"},
    ],
}
#: Dollars moved from checking, at the published rate for the day.
DOLLARS = {
    "entry_date": "2026-10-11",
    "description": "Dollars for the trip",
    "postings": [
        {"account_id": "usd", "direction": 1, "amount": "100.00", "currency": "USD"},
        {"account_id": "chk", "direction": -1, "amount": "100.00", "currency": "USD"},
    ],
}
#: Pounds, for which Salli has no published rate on the day.
POUNDS = {
    "entry_date": "2026-10-11",
    "description": "Pounds for the trip",
    "postings": [
        {"account_id": "out", "direction": 1, "amount": "40.00", "currency": "GBP"},
        {"account_id": "chk", "direction": -1, "amount": "40.00", "currency": "GBP"},
    ],
}
#: The real return the person sets, with where it comes from.
REAL_RETURN = {
    "real_return": {
        "value": "0.035",
        "source": "My own long-run view, after inflation",
        "note": "Halfway between the conservative and base scenarios.",
    }
}
#: A household's FIRE strategy, as the model wrote it (rates as JSON numbers).
STRATEGY = {
    "version": 2,
    "created_at": "2026-09-01T00:00:00+00:00",
    "fire_style": "standard",
    "swr": 0.035,
    "real_return_conservative": 0.02,
    "real_return_base": 0.035,
    "real_return_growth": 0.05,
    "target_monthly_expenses": 2200.0,
    "target_age": 55,
    "buckets": [
        {
            "key": "moat",
            "name": "Emergency moat",
            "target_pct": 0.1,
            "description": "Six months of spending in cash.",
            "color": "emerald",
        },
        {
            "key": "growth",
            "name": "Growth",
            "target_pct": 0.9,
            "description": "Broad index funds, held for the long run.",
            "color": "indigo",
        },
    ],
    "ai_rationale": "Keep the moat full, then invest the rest of the surplus every month.",
    "theories_applied": ["The 4% rule, at 3.5%"],
    "is_initial": False,
}


def with_posting_ids(books: Books) -> None:
    """Gives each golden posting an id, as a database would: its entry's id
    and its place (`e070.1`), so the fixtures stay the same each time."""
    ledger = books.services.ledger._uow_factory().ledger
    ledger.entries = [
        e.model_copy(
            update={
                "postings": [
                    p.model_copy(update={"id": f"{e.id}.{i}"})
                    for i, p in enumerate(e.postings, start=1)
                ]
            }
        )
        for e in ledger.entries
    ]


async def where_fixtures(home: list[Fixture]) -> list[Fixture]:
    """Where you stand (C2) on the household Home shows: its reads after one
    reminder of the person's own is marked done, then the answers to the
    writes its pages make. What Home already reads (safe to spend, the
    signals, the FI score) must be Home's, which the console reads for both."""
    books = await household()
    books.services.entitlements = FullAccess()
    with_posting_ids(books)
    await home_writes(books)
    books.services.clock.at = OCTOBER

    async def get(path: str, ok: tuple[int, ...] = (200,)) -> Any:
        return await ask(books, "GET", path, ok=ok)

    async def send(method: str, path: str, body: Any = None, ok: tuple[int, ...] = (200,)) -> Any:
        return await ask(books, method, path, body, ok=ok)

    # The person's own: a reminder of theirs, done before the household's date.
    window = await send(
        "POST",
        "/v1/reminders/",
        {"kind": "Pay the window cleaner", "due_date": "2026-10-02"},
        (201,),
    )
    await send("PATCH", f"/v1/reminders/{window['id']}/done", ok=(204,))
    # The score kept on the household's date: its history.
    await send("POST", "/v1/fi/score/recompute")

    accounts = await get("/v1/accounts/")
    entries = await get("/v1/entries/")
    shared = {f.name: f.value for f in home}
    for name, path in (
        ("SAFE_TO_SPEND", "/v1/insights/safe-to-spend"),
        ("SIGNALS", "/v1/insights/signals"),
        ("FI_SCORE", "/v1/fi/score"),
        ("REMINDERS", "/v1/reminders/?status=pending"),
    ):
        if await get(path) != shared[name]:
            raise RuntimeError(f"Where you stand reads another {name} than Home's")

    reads = [
        Fixture("TRIAL_BALANCE", "TrialBalance", None, await get("/v1/ledger/trial-balance")),
        Fixture(
            "OVERVIEWS",
            "AccountOverview[]",
            "Every account's overview: its balances and its entries, each with the\n"
            "running balance after it.",
            [await get(f"/v1/accounts/{a['id']}/overview") for a in accounts],
        ),
        Fixture("ENTRIES", "JournalEntry[]", "Every entry, oldest first.", entries),
        Fixture(
            "PROVENANCES",
            "EntryProvenance[]",
            "Where each entry came from.",
            [await get(f"/v1/entries/{e['id']}/provenance") for e in entries],
        ),
        Fixture(
            "FORECAST", "CashForecast", "The next 60 days.", await get("/v1/insights/forecast")
        ),
        Fixture(
            "CASH_FLOW",
            "CashFlow",
            "Six full months and this one so far.",
            await get("/v1/insights/cash-flow?months=6"),
        ),
        Fixture(
            "SPENDING",
            "Spending",
            "By category, August to October so far.",
            await get("/v1/insights/spending?months=3&by=category"),
        ),
        Fixture("REMINDERS_ALL", "ReminderList", "Pending and done.", await get("/v1/reminders/")),
        Fixture("ASSUMPTIONS", "FiAssumptionsReport", None, await get("/v1/fi/assumptions")),
        Fixture("PROJECTIONS", "FiProjections", None, await get("/v1/fi/projections")),
        Fixture(
            "SCORE_HISTORY",
            "FiScoreHistory",
            "The score as Salli kept it on the household's date.",
            await get("/v1/fi/score/history"),
        ),
        Fixture(
            "NO_STRATEGY",
            "ProblemDetails",
            "The household has no FIRE strategy.",
            await get("/v1/fi/strategy", ok=(404,)),
        ),
    ]

    # The console's writes, after every read.
    posted = await send("POST", "/v1/entries/", LUNCH, (201,))
    lunch = posted["id"]
    after_post = [
        Fixture("POSTED", "Ref", "The answer to posting lunch from checking.", posted),
        Fixture("LUNCH", "JournalEntry", "Lunch, as posted.", await get(f"/v1/entries/{lunch}")),
        Fixture(
            "LUNCH_PROVENANCE",
            "EntryProvenance",
            None,
            await get(f"/v1/entries/{lunch}/provenance"),
        ),
        Fixture(
            "CHECKING_POSTED",
            "AccountOverview",
            "Checking with lunch posted.",
            await get("/v1/accounts/chk/overview"),
        ),
        Fixture(
            "TRIAL_BALANCE_POSTED",
            "TrialBalance",
            "With lunch posted.",
            await get("/v1/ledger/trial-balance"),
        ),
    ]
    reversed_ = await send("POST", f"/v1/entries/{lunch}/reverse", ok=(201,))
    reversal = reversed_["id"]
    after_reverse = [
        Fixture("REVERSED", "Ref", "The answer to reversing lunch.", reversed_),
        Fixture(
            "LUNCH_REVERSED", "JournalEntry", "Lunch, reversed.", await get(f"/v1/entries/{lunch}")
        ),
        Fixture("REVERSAL", "JournalEntry", None, await get(f"/v1/entries/{reversal}")),
        Fixture(
            "REVERSAL_PROVENANCE",
            "EntryProvenance",
            None,
            await get(f"/v1/entries/{reversal}/provenance"),
        ),
        Fixture(
            "CHECKING_REVERSED",
            "AccountOverview",
            "Checking with lunch and its reversal.",
            await get("/v1/accounts/chk/overview"),
        ),
        Fixture(
            "TRIAL_BALANCE_REVERSED",
            "TrialBalance",
            "With lunch and its reversal.",
            await get("/v1/ledger/trial-balance"),
        ),
        Fixture(
            "REVERSE_REFUSED",
            "ProblemDetails",
            "Reversing lunch a second time.",
            await send("POST", f"/v1/entries/{lunch}/reverse", ok=(400,)),
        ),
    ]
    dollars = await send("POST", "/v1/entries/", DOLLARS, (201,))
    others = [
        Fixture("DOLLARS_POSTED", "Ref", None, dollars),
        Fixture(
            "DOLLARS",
            "JournalEntry",
            "100.00 USD from checking, at the published rate for the day.",
            await get(f"/v1/entries/{dollars['id']}"),
        ),
        Fixture(
            "NO_RATE",
            "ProblemDetails",
            "Pounds, with no rate given and none published for the day.",
            await send("POST", "/v1/entries/", POUNDS, (422,)),
        ),
        Fixture(
            "ASSUMPTION_SET",
            "FiAssumptionsReport",
            "The answer to setting the real return, with its source and a note.",
            await send("PATCH", "/v1/fi/assumptions", REAL_RETURN),
        ),
        Fixture("FI_SCORE_SET", "FiScore", "With the real return set.", await get("/v1/fi/score")),
        Fixture(
            "PROJECTIONS_SET",
            "FiProjections",
            "With the real return set.",
            await get("/v1/fi/projections"),
        ),
        Fixture(
            "ASSUMPTION_REFUSED",
            "ProblemDetails",
            "A real return of 60% a year.",
            await send("PATCH", "/v1/fi/assumptions", {"real_return": {"value": "0.6"}}, (422,)),
        ),
    ]

    planner = await household()
    planner.services.entitlements = FullAccess()
    planner.services.fi._uow_factory().fire_strategies.strategy = STRATEGY
    strategy = Fixture(
        "STRATEGY",
        "FireStrategy",
        "The strategy of a household that has one (the AI drafted its words;\n"
        "every figure in it is the engine's or the person's).",
        await ask(planner, "GET", "/v1/fi/strategy"),
    )
    return [*reads, *after_post, *after_reverse, *others, strategy]


async def markdown(books: Books, path: str) -> str:
    """What the API answers as text (Markdown), not JSON."""
    app = create_app()
    app.dependency_overrides[get_services] = lambda: books.services
    app.dependency_overrides[get_principal] = lambda: Principal(books.user, None, "dev")
    app.dependency_overrides[get_current_user] = lambda: books.user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    response.raise_for_status()
    return response.text


async def files() -> dict[Path, str]:
    with fixed_ids():
        home = await home_fixtures()
    due = next(f.value for f in home if f.name == "REVIEWS_DUE")
    with fixed_ids(), stamped_in_october():
        lab = await lab_fixtures(due)
    with fixed_ids(), stamped_in_october():
        where = await where_fixtures(home)
    return {
        FIXTURES / "home.ts": render(HEADER, home),
        FIXTURES / "lab.ts": render(LAB_HEADER, lab),
        FIXTURES / "where.ts": render(WHERE_HEADER, where),
    }


def stale() -> list[Path]:
    """The fixture files that differ from what the server answers now."""
    return [
        path
        for path, text in asyncio.run(files()).items()
        if not path.exists() or path.read_text() != text
    ]


def main(argv: list[str]) -> int:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if "--check" in argv:
        found = stale()
        for path in found:
            print(f"{path} is stale: {COMMAND}", file=sys.stderr)
        return 1 if found else 0
    for path, text in asyncio.run(files()).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
