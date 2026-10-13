"""
The console's fixtures are what the server answers today.

The console's component tests, and its visual and accessibility runs, answer
Home's, the decision lab's and where you stand's reads with the fixtures in
packages/console/test/fixtures/ (home.ts, lab.ts and where.ts).
tests/console_fixtures.py writes them by asking the API app over the real
services on the golden household; a change to an engine, a service or a
response model that changes what the server sends makes them stale, and the
console's tests would go on passing against what it no longer sends.
"""

from __future__ import annotations

from tests import console_fixtures


def test_the_console_fixtures_are_what_the_server_answers():
    stale = [path.name for path in console_fixtures.stale()]
    assert not stale, (
        f"The console's fixtures {stale} differ from what the server answers. "
        f"Write them again: {console_fixtures.COMMAND}"
    )
