"""
The console's fixtures, written by the real server.

The console's component tests and its visual and accessibility runs
(packages/console/test, packages/console/e2e) answer the API with the
fixtures in `packages/console/test/fixtures/home.ts`: what the API app
(`interfaces/api/main.create_app`, so through its request and response
models) answers Home's eight reads on the golden household
(tests/golden/household.py: euros, as of 2026-10-11), with two reminders
of the person's own and a decision recorded in August, due for review on
2026-09-30. So the console's tests read exactly what the server sends today:
a fixture goes stale when an engine, a service or a response model changes,
and `tests/contract/test_console_fixtures.py` fails until it is written
again:

    uv run python -m tests.console_fixtures            # write them
    uv run python -m tests.console_fixtures --check    # what the contract test does

The ids the services make (the reminders', the decision's) are fixed, so the
file is the same each time it is written. The sign-in's own fixtures (who
is signed in, the profile, the sign-ins) are not a household's books, and
are written by hand in `auth.ts` beside it, typed by the SDK.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

from salli.application.services.baseline_service import BaselineService
from salli.application.services.decision_service import DecisionService
from salli.application.services.fi_service import FiService
from salli.application.services.insights_service import InsightsService
from salli.application.services.ledger_service import LedgerService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.reminder_service import ReminderService
from salli.application.services.report_service import ReportService
from salli.application.services.scenario_service import ScenarioService
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


async def household() -> Books:
    """The golden household, with every service Home reads."""
    uow = h.uow()
    today = lambda: h.AS_OF  # noqa: E731
    baselines = BaselineService(uow.factory(), fx=h.fx(), today=today)
    ledger = LedgerService(uow.factory(), fx=h.fx())
    fi = FiService(uow.factory(), baselines=baselines, today=today)
    scenarios = ScenarioService(uow.factory(), baselines=baselines)
    services = SimpleNamespace(
        ledger=ledger,
        fi=fi,
        reports=ReportService(ledger, fi),
        reminders=ReminderService(uow.factory()),
        insights=InsightsService(uow.factory(), today=today, baselines=baselines),
        scenarios=scenarios,
        principles=PrincipleService(uow.factory(), scenarios),
        decisions=DecisionService(
            uow.factory(),
            scenarios,
            PrincipleService(uow.factory(), scenarios),
            now=lambda: dt.datetime(2026, 8, 11, 9, tzinfo=dt.UTC),
        ),
    )
    return Books(h.USER, services)


async def home_fixtures() -> list[Fixture]:
    books = await household()

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


async def files() -> dict[Path, str]:
    with fixed_ids():
        fixtures = await home_fixtures()
    return {FIXTURES / "home.ts": render(HEADER, fixtures)}


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
