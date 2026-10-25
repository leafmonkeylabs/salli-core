"""
Every market pack's rule sets (markets/*/tax/*.json) validate, and each of
their worked examples passes, so a pack never ships rules Salli would refuse.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from salli.domain.taxrules.validate import validate

MARKETS = Path(__file__).resolve().parents[2] / "markets"
RULE_SETS = sorted(MARKETS.glob("*/tax/*.json"))


def test_there_is_at_least_one_market_rule_set():
    assert RULE_SETS


@pytest.mark.parametrize("path", RULE_SETS, ids=lambda p: p.relative_to(MARKETS).as_posix())
def test_a_market_rule_set_validates_with_its_examples(path: Path):
    report = validate(path.read_text(encoding="utf-8"))
    assert report.errors == (), [str(e) for e in report.errors]
    assert report.warnings == (), [str(w) for w in report.warnings]
    failed = [e for e in report.examples if not e.passed]
    assert report.ok and report.examples and not failed, failed
