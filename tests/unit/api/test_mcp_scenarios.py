"""
The MCP scenario tools — `get_scenario_schema`, `run_scenario` and
`compare_options` — over the household ledger: Salli's figures, validation
equal to the API's (the same documents accepted and refused), and another
user's account or debt not found.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.scenario_service import ScenarioService
from salli.domain.accounting.models import Account
from salli.interfaces.api import mcp_server
from tests.golden import household as h
from tests.unit.api.conftest import AUTH
from tests.unit.api.test_baseline_api import USER, _household_of

pytestmark = pytest.mark.asyncio

LAPTOP = {
    "type": "one_off",
    "date": "2026-11-02",
    "amount": "-2400.00",
    "account": "chk",
    "label": "Laptop",
}


def _doc(*changes: dict[str, Any], **more: Any) -> dict[str, Any]:
    return {"schema": "salli.scenario/1", "changes": list(changes), **more}


def _scenarios() -> ScenarioService:
    books = _household_of(USER)
    books.ledger.accounts.append(
        Account(
            id="theirs",
            user_id="someone-else",
            code="1000",
            name="Theirs",
            type="asset",
            currency="EUR",
        )
    )
    books.debts.rows["their-debt"] = {
        **books.debts.rows["debt-student"],
        "id": "their-debt",
        "user_id": "x",
    }
    baselines = BaselineService(books.factory(), fx=h.fx(), today=lambda: h.AS_OF)
    return ScenarioService(books.factory(), baselines=baselines)


@pytest.fixture
def services() -> Any:
    services = MagicMock()
    services.scenarios = _scenarios()
    return services


async def _call(services: Any, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    server = mcp_server.build_mcp_server(services, "https://api.test")
    with patch.object(mcp_server, "_current_user_id", return_value=USER):
        _, structured = await server.call_tool(tool, args)
    return structured


async def test_the_schema_is_there_for_agents(services):
    described = await _call(services, "get_scenario_schema", {})
    assert described["properties"]["schema"]["const"] == "salli.scenario/1"
    # And written out in each tool's own input schema, $refs and all inlined.
    server = mcp_server.build_mcp_server(services, "https://api.test")
    tools = {t.name: t for t in await server.list_tools()}
    run_input = tools["run_scenario"].inputSchema
    assert "$ref" not in str(run_input)
    assert run_input["properties"]["scenario"]["properties"]["horizon_years"]["maximum"] == 50
    compare_input = tools["compare_options"].inputSchema["properties"]["options"]
    assert (compare_input["minItems"], compare_input["maxItems"]) == (2, 5)


async def test_a_scenario_runs_as_the_api_runs_it(services):
    result = await _call(services, "run_scenario", {"scenario": _doc(LAPTOP)})
    chk = next(a for a in result["cash"]["accounts"] if a["account_id"] == "chk")
    assert chk["lowest"]["scenario"] == "4883.77"
    assert result["fi"]["months_gained"] == -1
    assert result["placeholders"] == [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "inflation",
    ]


async def test_options_compare_without_a_ranking(services):
    invest = {
        "type": "invest",
        "amount": "5000.00",
        "date": "2026-12-01",
        "from": "sav",
        "label": "Invest",
    }
    extra = {
        "type": "extra_debt_payment",
        "debt": "debt-student",
        "monthly": "5000.00",
        "from": "2026-12-01",
        "to": "2026-12-31",
    }
    result = await _call(
        services,
        "compare_options",
        {
            "options": [
                _doc(invest, label="Invest", horizon_years=10),
                _doc(extra, label="Pay down", horizon_years=10),
            ]
        },
    )
    # The student loan's own 4.5%, to the bisection's basis point: the
    # golden household (tests/golden/test_household_scenarios.py) works it
    # through.
    (break_even,) = result["break_evens"]
    assert (break_even["kind"], break_even["value"]) == ("invest_vs_debt_return", "0.0451")
    assert break_even["says"].startswith("At a real return of 4.51% a year or more, Invest")


INVALID = [
    _doc({**LAPTOP, "amount": -2400}),
    _doc({**LAPTOP, "date": "2026-02-30"}),
    _doc(horizon_years=51),
    _doc(*[LAPTOP] * 51),
    _doc({**LAPTOP, "date": "2026-10-01"}),
    _doc({**LAPTOP, "account": "brk"}),
    _doc({**LAPTOP, "amount": "-1.001"}),
    _doc(as_of="2026-12-01"),
    {"changes": []},
]
VALID = [_doc(), _doc(LAPTOP), _doc({**LAPTOP, "amount": "-2400"}, horizon_years=1)]


@pytest.mark.parametrize("doc", INVALID + VALID)
async def test_mcp_accepts_and_refuses_exactly_what_the_api_does(
    services, client, mock_services, doc
):
    mock_services.scenarios = services.scenarios
    api = await client.post("/v1/scenarios/run", json=doc, headers=AUTH)
    mcp = await _call(services, "run_scenario", {"scenario": doc})
    if doc in VALID:
        assert api.status_code == 200 and "error" not in mcp
        assert mcp["hash"] == api.json()["hash"]
    else:
        assert api.status_code == 422
        assert mcp["problems"], mcp
        # The same paths, in each one's shape.
        api_paths = {
            ".".join(str(p) for p in e["loc"][1:] if p not in ("one_off",))
            for e in api.json()["detail"]
        }
        mcp_paths = {p["path"].replace("[", ".").replace("]", "") for p in mcp["problems"]}
        assert api_paths == mcp_paths


@pytest.mark.parametrize(
    ("change", "said"),
    [
        ({**LAPTOP, "account": "theirs"}, "Account not found: theirs"),
        ({**LAPTOP, "account": "nowhere"}, "Account not found: nowhere"),
        (
            {
                "type": "extra_debt_payment",
                "debt": "their-debt",
                "monthly": "1",
                "from": "2026-11-02",
            },
            "Debt not found: their-debt",
        ),
    ],
)
async def test_another_users_account_or_debt_is_not_found(services, change, said):
    assert await _call(services, "run_scenario", {"scenario": _doc(change)}) == {"error": said}
    compared = await _call(
        services, "compare_options", {"options": [_doc(label="A"), _doc(change, label="B")]}
    )
    assert compared == {"error": said}
