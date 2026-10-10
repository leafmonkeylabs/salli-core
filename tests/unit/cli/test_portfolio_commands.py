"""
`salli portfolio` for investments: transactions, lots, prices and performance,
end to end through the command line, over the in-memory unit of work.
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest
import typer.testing
from typer.testing import CliRunner

from salli.application.services.portfolio_service import PortfolioService
from salli.interfaces.cli import main as cli_main
from salli.interfaces.cli import support
from tests.fakes import FakeRecordsUoW
from tests.unit.application.test_portfolio_transactions import Rates


@pytest.fixture
def run(monkeypatch):
    uow = FakeRecordsUoW("LKR")
    svc = PortfolioService(lambda: uow, fx=Rates(), today=lambda: date(2026, 10, 9))
    monkeypatch.setattr(cli_main, "_services", lambda: SimpleNamespace(portfolio=svc))
    monkeypatch.setenv("SALLI_USER_ID", "u1")
    # The command tree `salli` runs: with --json on every command, which a
    # tree Typer builds afresh from the app would not have.
    command = cli_main.cli()
    monkeypatch.setattr(typer.testing, "_get_command", lambda app: command)
    runner = CliRunner()

    def invoke(*args: str):
        # --json flips module state for the rest of the process; start clean.
        monkeypatch.setattr(support, "_json_mode", False)
        monkeypatch.setattr(support.console, "file", None)
        result = runner.invoke(cli_main.app, ["portfolio", *args])
        if "--json" in args and result.exit_code == 0:
            return json.loads(result.stdout)
        return result

    return invoke


def test_a_foreign_holding_bought_sold_and_valued(run):
    holding = run(
        "add", "VOO", "--name", "S&P 500", "--asset-class", "equity", "--currency", "USD", "--json"
    )["id"]
    short = holding[:8]
    buy = run(
        "transactions",
        "add",
        short,
        "buy",
        "--date",
        "2026-01-05",
        "--quantity",
        "10",
        "--price",
        "100",
        "--fees",
        "1",
        "--fx-rate",
        "300",
        "--json",
    )["id"]
    run(
        "transactions",
        "add",
        short,
        "sell",
        "--date",
        "2026-03-05",
        "--quantity",
        "4",
        "--price",
        "120",
        "--lot",
        f"{buy[:8]}:4",
        "--fx-rate",
        "305",
        "--json",
    )
    run("prices", "set", "voo", "130", "--date", "2026-10-08", "--json")

    lots = run("lots", short, "--json")
    [sale] = lots["sales"]
    # 480 − 4 × 100.10 = 79.60 USD.
    assert (sale["gain"], sale["consumed"][0]["lot_id"]) == ("79.60", buy)
    assert lots["quantity"] == "6"

    [listed] = run("list", "--json")
    # No rate for 8 October in this test's sources: valued in dollars, carried
    # at cost in rupees, and said.
    assert (listed["native"]["current_value"], listed["converted"]) == ("780.00", False)
    assert listed["notes"]

    report = run("performance", "--from", "2026-01-01", "--to", "2026-12-31", "--json")
    # In rupees: 480 × 305 − (4/10 × 1001) × 300 = 146,400 − 120,120.
    assert report["portfolio"]["realised_gain"] == "26280.00"
    assert report["holdings"][0]["native"]["realised_gain"] == "79.60"

    # Without --json, the same commands print tables.
    for args in (
        ("list",),
        ("lots", short),
        ("performance",),
        ("prices", "list"),
        ("transactions", "list", short),
    ):
        result = run(*args)
        assert result.exit_code == 0, (args, result.output)


def test_an_impossible_sale_is_refused_with_a_message(run):
    holding = run("add", "VOO", "--name", "S&P 500", "--asset-class", "equity", "--json")["id"]
    run(
        "transactions",
        "add",
        holding,
        "buy",
        "--date",
        "2026-01-05",
        "--quantity",
        "1",
        "--price",
        "1",
        "--json",
    )
    result = run(
        "transactions",
        "add",
        holding,
        "sell",
        "--date",
        "2026-01-06",
        "--quantity",
        "2",
        "--price",
        "1",
    )
    assert result.exit_code == 1
    assert "only 1 are held" in result.output


def test_transactions_are_edited_and_deleted_by_short_ids(run):
    holding = run("add", "X", "--name", "X", "--asset-class", "equity", "--json")["id"]
    split = run(
        "transactions",
        "add",
        holding[:6],
        "split",
        "--date",
        "2026-01-05",
        "--ratio",
        "1:10",
        "--json",
    )["id"]
    run("transactions", "update", holding[:6], split[:6], "--ratio", "2:1", "--json")
    shown = run("transactions", "show", holding[:6], split[:6], "--json")
    assert shown["ratio"] == "2:1"
    assert run("transactions", "delete", holding[:6], split[:6], "--json")["deleted"] is True
    assert run("transactions", "list", holding[:6], "--json") == []


def test_a_price_is_deleted_by_its_short_id(run):
    run("add", "X", "--name", "X", "--asset-class", "equity", "--json")
    quote = run("prices", "set", "X", "1.5", "--json")["id"]
    assert run("prices", "list", "--symbol", "x", "--json")[0]["close"] == "1.5"
    run("prices", "delete", quote[:8], "--json")
    assert run("prices", "list", "--json") == []
