"""`salli insights forecast` writes amounts inline as every inline amount is
written: "1,234.50 USD" (currency.format_amount)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from typer.testing import CliRunner

from salli.interfaces.cli import main

FORECAST = {
    "currency": "USD",
    "start": "2026-10-09",
    "end": "2026-11-08",
    "today": "1234.5",
    "end_balance": "1000",
    "lowest": "900",
    "lowest_date": "2026-10-20",
    "daily": [],
    "accounts": [],
    "flows": [],
    "notes": ["[bold]Odd[/bold]: left out"],
}


def test_the_forecast_writes_amounts_as_format_amount_does(monkeypatch):
    insights = SimpleNamespace(forecast=AsyncMock(return_value=FORECAST))
    monkeypatch.setattr(main, "_services", lambda: SimpleNamespace(insights=insights))
    monkeypatch.setattr(main, "_require_user", lambda: "u1")
    result = CliRunner().invoke(main.app, ["insights", "forecast"])
    assert result.exit_code == 0, result.output
    assert "Cash today 1,234.50 USD" in result.output
    assert "Lowest: 900.00 USD" in result.output
    assert "[bold]Odd[/bold]: left out" in result.output  # a note is text, not markup
