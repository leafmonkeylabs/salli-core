"""
The `salli` CLI's scenario, template and principle fixtures, written by the
real server.

The CLI's mock server (packages/cli/test/helpers/mock-server.ts) answers
`/v1/scenarios/run` and `/compare`, `/v1/decisions/templates` and `/start`,
and `/v1/principles/figures` and `/check` with the fixtures in `scenarios.ts`,
`templates.ts` and `decisions.ts` beside it. Each is a request made here to
the API app itself (`interfaces/api/main.create_app`, so through its request
and response models) over the real services on one of the golden households
(tests/golden/), as of that household's date. So the CLI's tests read
exactly what the server sends today: a fixture goes stale when the engine,
a service or a response model changes, and
`tests/contract/test_cli_fixtures.py` fails until it is written again:

    uv run python -m tests.cli_fixtures            # write them
    uv run python -m tests.cli_fixtures --check    # what the contract test does

`scenarios.ts` and `templates.ts` are written whole. In `decisions.ts` only
FIGURES and PRINCIPLE_CHECK are written, in place: the decision journal's
stored entries (DECISION, DUE, REVIEW) keep the engine version that recorded
them, and are never written here.

Ids: the template fixtures use the mock server's own account and debt ids
(`MOCK_IDS`). The services run on the household's ids, so every hash is the
one the server computes for the household, and the ids are swapped for the
mock's in what is written. The scenario and principle fixtures keep the
households' ids; the principles have the mock's (`MOCK_PRINCIPLES`).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from httpx import ASGITransport, AsyncClient

from salli.application.services.baseline_service import BaselineService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.scenario_service import ScenarioService
from salli.application.services.template_service import TemplateService
from salli.interfaces.api.deps import Principal, get_current_user, get_principal, get_services
from salli.interfaces.api.main import create_app
from tests import baseline_ledger
from tests.fakes import FakeUoW
from tests.golden import household as h
from tests.golden import renting, taxed
from tests.golden import test_holding_scenarios as holdings

HELPERS = Path(__file__).resolve().parents[1] / "packages" / "cli" / "test" / "helpers"
COMMAND = "uv run python -m tests.cli_fixtures"


def uid(n: int) -> str:
    """The mock server's ids (`uid` in packages/cli/test/helpers/fixtures.ts)."""
    return f"{n:08x}-5a11-4000-8000-{n:012d}"


#: The household's ids, as the mock server's accounts and debts.
MOCK_IDS = {
    "chk": uid(2),
    "sav": uid(3),
    "debt-student": uid(411),
    "debt-car": uid(412),
}

#: The principles: as the mock server lists them (decisions.ts, PRINCIPLES),
#: and the one the template fixtures check, with the id they were first
#: written with.
SIX_MONTHS = {"label": "Six months of essentials in cash", "check": "emergency_months >= 6"}
CHECKING = {"label": "Checking above 5,000", "check": "account_lowest >= 5000", "account": "chk"}
MOCK_PRINCIPLES = {uid(1801): SIX_MONTHS, uid(1802): CHECKING}
TEMPLATE_PRINCIPLES = {"3a20d884-aa5c-4254-819e-865c1085b3d6": SIX_MONTHS}

#: Who asks for the scenario run and comparison: the household's books held
#: as the API tests' caller (tests/unit/api/test_baseline_api.py), as they
#: were first written. The baseline's fingerprint covers the books' rows,
#: their owner among them, so each hash is that caller's.
API_CALLER = "test-user-1"


# -- The households ----------------------------------------------------------


@dataclass
class Books:
    """A household's books, its user and the services the API is given."""

    user: str
    services: SimpleNamespace


def _services(uow: FakeUoW, baselines: BaselineService) -> SimpleNamespace:
    scenarios = ScenarioService(uow.factory(), baselines=baselines)
    principles = PrincipleService(uow.factory(), scenarios)
    templates = TemplateService(scenarios, principles)
    return SimpleNamespace(scenarios=scenarios, principles=principles, templates=templates)


async def household(
    user: str = h.USER, principles: dict[str, dict[str, Any]] | None = None
) -> Books:
    """tests/golden/household.py (euros, as of 2026-10-11), as `user`'s, with
    `principles` by id."""
    uow = h.uow()
    if user != h.USER:
        ledger = uow.ledger
        ledger.accounts = [a.model_copy(update={"user_id": user}) for a in ledger.accounts]
        ledger.entries = [e.model_copy(update={"user_id": user}) for e in ledger.entries]
        for row in uow.debts.rows.values():
            row["user_id"] = user
    services = _services(uow, BaselineService(uow.factory(), fx=h.fx(), today=lambda: h.AS_OF))
    for id_, principle in (principles or {}).items():
        added = await services.principles.add(user, principle)
        row = uow.principles.rows.pop(added["id"])
        uow.principles.rows[id_] = {**row, "id": id_}
    return Books(user, services)


def _ledger(make: Callable[[], baseline_ledger.Ledger], as_of: Any) -> Callable[[], Any]:
    async def books() -> Books:
        ledger = make()
        return Books(baseline_ledger.USER, _services(ledger.uow, ledger.service(as_of)))

    return books


#: tests/golden/taxed.py: New Zealand dollars, as of 2031-06-30, XA 2031.
taxed_household = _ledger(taxed.ledger, taxed.AS_OF)
#: tests/golden/test_holding_scenarios.py: the XA household with a fund.
holding_household = _ledger(holdings.books, holdings.AS_OF)
#: tests/golden/renting.py: New Zealand dollars, as of 2031-06-30.
renting_household = _ledger(renting.ledger, renting.AS_OF)


# -- Asking the API ----------------------------------------------------------


async def ask(books: Books, method: str, path: str, body: Any = None) -> Any:
    """What the API answers `books.user`, as JSON."""
    app = create_app()
    app.dependency_overrides[get_services] = lambda: books.services
    app.dependency_overrides[get_principal] = lambda: Principal(books.user, None, "dev")
    app.dependency_overrides[get_current_user] = lambda: books.user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request(method, path, json=body)
    if response.status_code != 200:
        raise RuntimeError(f"{method} {path}: {response.status_code} {response.text}")
    return response.json()


def scenario(label: str, *changes: dict[str, Any], **doc: Any) -> dict[str, Any]:
    return {"schema": "salli.scenario/1", "label": label, "changes": list(changes), **doc}


LAPTOP = {"type": "one_off", "date": "2026-11-02", "amount": "-2400.00", "label": "Laptop"}


def as_mock(value: Any) -> Any:
    """`value` with the household's account and debt ids as the mock's."""
    if isinstance(value, dict):
        return {MOCK_IDS.get(k, k): as_mock(v) for k, v in value.items()}
    if isinstance(value, list):
        return [as_mock(v) for v in value]
    if isinstance(value, str):
        return MOCK_IDS.get(value, value)
    return value


@dataclass
class Fixture:
    name: str
    type: str
    doc: str | None
    value: Any


async def scenario_fixtures() -> list[Fixture]:
    home = await household(API_CALLER)
    laptop = scenario(
        "Laptop",
        {**LAPTOP, "account": "chk", "label": "New laptop"},
        {
            "type": "loan",
            "principal": "18000.00",
            "annual_rate": "0.069",
            "term_months": 48,
            "start": "2026-12-01",
            "label": "Car loan",
        },
        {"type": "stop_recurring", "key": "streamflix", "from": "2026-11-01"},
    )
    instalments = {
        "type": "loan",
        "principal": "2400.00",
        "annual_rate": "0.069",
        "term_months": 12,
        "start": "2026-11-02",
        "label": "Laptop instalments",
    }
    compare = {
        "options": [scenario("Pay cash", LAPTOP), scenario("Instalments", LAPTOP, instalments)]
    }
    raise_ = scenario(
        "Raise",
        {
            "type": "income_change",
            "monthly": "1000.00",
            "from": "2031-07-01",
            "tax_role": "salary",
            "label": "Raise",
        },
    )
    sell_and_invest = scenario(
        "Sell to top up",
        {
            "type": "sell",
            "holding": "fund",
            "quantity": "4",
            "date": "2031-06-30",
            "fees": "2.00",
            "tax_role": "gains",
            "label": "Sell My index fund",
        },
        {
            "type": "invest",
            "amount": "1000.00",
            "date": "2031-06-30",
            "holding": "fund",
            "label": "Invest 1000.00 in My index fund",
        },
    )
    buy = scenario(
        "Buy",
        {
            "type": "asset",
            "price": "200000.00",
            "date": "2031-07-01",
            "selling_costs": "0.03",
            "label": "The home",
        },
        {
            "type": "loan",
            "principal": "150000.00",
            "annual_rate": "0",
            "term_months": 120,
            "start": "2031-07-01",
            "label": "Mortgage",
        },
        {"type": "stop_recurring", "key": renting.RENT_KEY, "from": "2031-07-01"},
    )
    run = "/v1/scenarios/run"
    return [
        Fixture("SCENARIO_RUN", "ScenarioRun", None, await ask(home, "POST", run, laptop)),
        Fixture(
            "SCENARIO_COMPARISON",
            "ScenarioComparison",
            None,
            await ask(home, "POST", "/v1/scenarios/compare", compare),
        ),
        Fixture(
            "TAXED_RUN",
            "ScenarioRun",
            "A raise of 1,000.00 a month before tax, tagged with the salary role, on\n"
            "the fictional XA 2031 household (tests/golden/taxed.py, as of\n"
            "2031-06-30, in New Zealand dollars).",
            await ask(await taxed_household(), "POST", run, raise_),
        ),
        Fixture(
            "HOLDING_RUN",
            "ScenarioRun",
            'A run selling 4 units of a holding the person calls "My index fund" (2.00\n'
            'of fees, the gain in an income role "gains") and investing 1,000.00 into\n'
            "it, on the 3b golden household (tests/golden/test_holding_scenarios.py:\n"
            "New Zealand dollars, as of 2031-06-30, the fictional rules XA 2031).",
            await ask(await holding_household(), "POST", run, sell_and_invest),
        ),
        Fixture(
            "ASSET_RUN",
            "ScenarioRun",
            "Buying a home on the renting household (tests/golden/renting.py, as of\n"
            "2031-06-30, in New Zealand dollars): the design's hand-worked golden,\n"
            "200,000.00 with 50,000.00 down, a mortgage of 150,000.00 at 0% over 120\n"
            "months, selling costs of 3%, the rent stopped.",
            await ask(await renting_household(), "POST", run, buy),
        ),
    ]


async def template_fixtures() -> list[Fixture]:
    home = await household(principles=TEMPLATE_PRINCIPLES)

    async def start(template: str, answers: dict[str, Any]) -> Any:
        body = {"template": template, "answers": answers}
        return as_mock(await ask(home, "POST", "/v1/decisions/start", body))

    async def template(template_id: str) -> Any:
        return as_mock(await ask(home, "GET", f"/v1/decisions/templates/{template_id}"))

    afford = {
        "price": "2400.00",
        "what": "Laptop",
        "date": "2026-11-02",
        "account": "chk",
        "instalment_months": 12,
        "instalment_rate": "0.069",
        "horizon_years": 5,
    }
    emergency = {"target_months": "9", "set_aside": ["200.00", "500.00"], "horizon_years": 5}
    rent_or_buy = {
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
    return [
        Fixture(
            "TEMPLATE_LIST",
            "DecisionTemplateList",
            None,
            await ask(home, "GET", "/v1/decisions/templates"),
        ),
        Fixture("AFFORD_IT", "DecisionTemplate", None, await template("afford-it")),
        Fixture("EMERGENCY_FUND", "DecisionTemplate", None, await template("emergency-fund")),
        Fixture("AFFORD_IT_START", "DecisionStart", None, await start("afford-it", afford)),
        Fixture(
            "EMERGENCY_FUND_START",
            "DecisionStart",
            None,
            await start("emergency-fund", emergency),
        ),
        Fixture("RENT_OR_BUY", "DecisionTemplate", None, await template("rent-or-buy")),
        Fixture(
            "RENT_OR_BUY_START", "DecisionStart", None, await start("rent-or-buy", rent_or_buy)
        ),
    ]


async def principle_fixtures() -> list[Fixture]:
    """The figures principles check, and a check of the mock's principles on
    the options of the decision decisions.ts records (DECISION)."""
    home = await household(principles=MOCK_PRINCIPLES)
    laptop = {**LAPTOP, "account": "chk"}
    instalments = {
        "type": "loan",
        "principal": "2400.00",
        "annual_rate": "0.069",
        "term_months": 12,
        "start": "2026-11-02",
        "into": "chk",
        "label": "Instalments",
    }
    options = [scenario("Pay cash", laptop), scenario("Instalments", laptop, instalments)]
    check = {"options": options}
    return [
        Fixture(
            "FIGURES", "DecisionFigures", None, await ask(home, "GET", "/v1/principles/figures")
        ),
        Fixture(
            "PRINCIPLE_CHECK",
            "PrinciplesCheck",
            None,
            await ask(home, "POST", "/v1/principles/check", check),
        ),
    ]


# -- Writing TypeScript ------------------------------------------------------

GENERATED = (
    " *\n"
    f" * Written by tests/cli_fixtures.py (`{COMMAND}`):\n"
    " * tests/contract/test_cli_fixtures.py fails while it differs from what the\n"
    " * server answers. Don't edit it by hand.\n"
    " */"
)

SCENARIOS_HEADER = (
    "/**\n"
    " * What a real server answers for scenarios: a run and a comparison of paying\n"
    " * cash against instalments on the golden household ledger\n"
    " * (tests/golden/household.py, as of Oct 11, 2026, in euros), and runs on\n"
    " * the other golden households below, each the API's response to the\n"
    " * request in tests/cli_fixtures.py.\n" + GENERATED
)

TEMPLATES_HEADER = (
    "/**\n"
    " * What a real server answers for decision templates on the golden household\n"
    " * ledger (tests/golden/household.py, as of Oct 11, 2026, in euros, with the\n"
    ' * principle "Six months of essentials in cash"): the list, the afford-it,\n'
    " * emergency-fund and rent-or-buy templates, and a start of each\n"
    " * (rent-or-buy's against the household's rent, City Lettings, with two\n"
    " * mortgages). Account and debt ids are the mock server's own; the hashes\n"
    " * are the server's for the household's.\n" + GENERATED
)


def render(header: str, fixtures: list[Fixture]) -> str:
    types = sorted({f.type for f in fixtures})
    parts = [header, f"import type {{ {', '.join(types)} }} from '@leafmonkeylabs/salli-sdk';", ""]
    for fixture in fixtures:
        if fixture.doc:
            lines = "\n".join(f" * {line}" for line in fixture.doc.splitlines())
            parts.append(f"/**\n{lines}\n */")
        value = json.dumps(fixture.value, indent=2, ensure_ascii=False)
        parts.extend([f"export const {fixture.name}: {fixture.type} = {value};", ""])
    return "\n".join(parts)


def splice(text: str, fixtures: list[Fixture]) -> str:
    """`text` with each fixture's value written in place of its old one."""
    for fixture in fixtures:
        head = f"export const {fixture.name}: {fixture.type} = "
        start = text.index(head) + len(head)
        _, length = json.JSONDecoder().raw_decode(text[start:])
        value = json.dumps(fixture.value, indent=2, ensure_ascii=False)
        text = text[:start] + value + text[start + length :]
    return text


async def files() -> dict[Path, str]:
    decisions = HELPERS / "decisions.ts"
    return {
        HELPERS / "scenarios.ts": render(SCENARIOS_HEADER, await scenario_fixtures()),
        HELPERS / "templates.ts": render(TEMPLATES_HEADER, await template_fixtures()),
        decisions: splice(decisions.read_text(), await principle_fixtures()),
    }


def stale() -> list[Path]:
    """The fixture files that differ from what the server answers now."""
    return [path for path, text in asyncio.run(files()).items() if path.read_text() != text]


def main(argv: list[str]) -> int:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if "--check" in argv:
        found = stale()
        for path in found:
            print(f"{path} is stale: {COMMAND}", file=sys.stderr)
        return 1 if found else 0
    for path, text in asyncio.run(files()).items():
        path.write_text(text)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
