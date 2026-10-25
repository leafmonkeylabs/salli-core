"""
Every market pack's rule sets (markets/*/tax/*.json) validate, and each of
their worked examples passes, and every capital-market pack (markets/*/cma.json)
parses as salli.cma/1, so a pack never ships what Salli would refuse.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from salli.domain.fi import cma
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


CMA_PACKS = sorted(MARKETS.glob("*/cma.json"))


@pytest.mark.parametrize("path", CMA_PACKS, ids=lambda p: p.relative_to(MARKETS).as_posix())
def test_a_market_cma_pack_parses(path: Path):
    pack = cma.parse(json.loads(path.read_text(encoding="utf-8")))
    assert not pack.placeholder


@pytest.mark.parametrize("path", CMA_PACKS, ids=lambda p: p.relative_to(MARKETS).as_posix())
def test_a_market_cma_pack_matches_its_readme_table(path: Path):
    """The README's table of real returns and volatilities, row by row in the
    pack's order, is the pack's: the figures a reviewer reads are the ones run."""
    pack = cma.parse(json.loads(path.read_text(encoding="utf-8")))
    lines = (path.parent / "README.md").read_text(encoding="utf-8").splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.startswith("| Asset class | Real return")
    )
    rows = [line.split("|")[2:4] for line in lines[start + 2 : start + 2 + len(pack.classes)]]
    for asset, (real, vol) in zip(pack.classes, rows, strict=True):
        assert Decimal(real.strip(" %")) / 100 == asset.real_return.value, asset.key
        assert Decimal(vol.strip(" %")) / 100 == asset.volatility.value, asset.key
