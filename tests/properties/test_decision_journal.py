"""
Appending to the decision journal never changes an entry: whatever notes
are appended, through the service and its append-only store, the entry
reads back exactly as recorded, with the same hash, and every note names it.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import functools

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salli.domain.decisions import journal


@functools.cache
def _record():
    from salli.application.services.baseline_service import BaselineService
    from salli.application.services.decision_service import DecisionService
    from salli.application.services.principle_service import PrincipleService
    from salli.application.services.scenario_service import ScenarioService
    from tests.golden import household as h

    uow = h.uow()
    baselines = BaselineService(uow.factory(), fx=h.fx(), today=lambda: h.AS_OF)
    scenarios = ScenarioService(uow.factory(), baselines=baselines)
    service = DecisionService(
        uow.factory(),
        scenarios,
        PrincipleService(uow.factory(), scenarios),
        now=lambda: dt.datetime(2026, 10, 11, 9, tzinfo=dt.UTC),
    )
    recorded = asyncio.run(
        service.record(
            h.USER,
            {
                "question": "Keep or change?",
                "options": [{"schema": "salli.scenario/1", "label": "Keep"}],
                "chosen": "Keep",
                "reasons": "Fine as it is.",
                "review_on": "2026-10-31",
            },
            via={"channel": "api"},
        )
    )
    return service, h.USER, recorded


@settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(texts=st.lists(st.text(min_size=1, max_size=200).filter(str.strip), min_size=1, max_size=4))
def test_appending_notes_never_changes_the_entry_or_its_hash(texts: list[str]):
    service, user, recorded = _record()
    for text in texts:
        asyncio.run(service.add_note(user, recorded["id"], text))
    read = asyncio.run(service.get(user, recorded["id"]))
    assert read["entry"] == recorded["entry"]
    assert read["hash"] == recorded["hash"] == journal.digest(read["entry"])
    assert read["verified"] and all(n["verified"] for n in read["notes"])
    assert all(n["note"]["entry_hash"] == recorded["hash"] for n in read["notes"])
