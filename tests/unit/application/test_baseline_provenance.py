"""
What a baseline records about where it came from, for a scenario's result
to cite: a fingerprint of its inputs, and the active tax rule sets that
cover its as-of date.
"""

from __future__ import annotations

import asyncio
import datetime as dt

from salli.application.services.baseline_service import BaselineService, covering_rule_sets
from tests.golden import household as h


def _build(uow) -> object:
    service = BaselineService(uow.factory(), fx=h.fx(), today=lambda: h.AS_OF)
    return asyncio.run(service.build(h.USER))


def test_the_fingerprint_is_the_inputs_and_only_them():
    uow = h.uow()
    first = _build(uow).fingerprint  # type: ignore[attr-defined]
    assert first.startswith("sha256:")
    assert _build(uow).fingerprint == first  # type: ignore[attr-defined]
    # The order the store hands entries back in is no input.
    uow.ledger.entries = list(reversed(uow.ledger.entries))
    assert _build(uow).fingerprint == first  # type: ignore[attr-defined]
    # A changed debt is.
    uow.debts.rows["debt-student"]["apr"] = "0.0460"
    assert _build(uow).fingerprint != first  # type: ignore[attr-defined]


def _active(country: str, region: str | None, start: str, end: str, version: int) -> dict:
    return {
        "id": f"{country}-{start[:4]}-{region or 'national'}",
        "country": country,
        "region": region,
        "year_label": start[:4],
        "version": {
            "version": version,
            "content_hash": f"hash-{version}",
            "content": {"year": {"label": start[:4], "start": start, "end": end}},
        },
    }


def test_the_rule_sets_recorded_are_the_residencys_that_cover_the_day():
    rows = [
        _active("XA", None, "2026-01-01", "2026-12-31", 3),
        _active("XA", None, "2025-01-01", "2025-12-31", 1),
        _active("XB", None, "2026-01-01", "2026-12-31", 2),
    ]
    found = covering_rule_sets(rows, "XA", dt.date(2026, 10, 11))
    assert [(r.country, r.year, r.version, r.content_hash) for r in found] == [
        ("XA", "2026", 3, "hash-3")
    ]
    assert covering_rule_sets(rows, None, dt.date(2026, 10, 11)) == []
    assert covering_rule_sets(rows, "XA", dt.date(2027, 1, 1)) == []


def test_the_baseline_carries_them():
    uow = h.uow(tax_residency="XA")
    uow.tax_rule_sets.active = [_active("XA", None, "2026-01-01", "2026-12-31", 4)]
    baseline = _build(uow)
    assert [(r.version, r.content_hash) for r in baseline.rule_sets] == [(4, "hash-4")]  # type: ignore[attr-defined]
