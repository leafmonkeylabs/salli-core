"""
The `salli` CLI's scenario, template and principle fixtures are what the
server answers today.

The CLI's tests run against a mock server that answers with the fixtures in
packages/cli/test/helpers/. tests/cli_fixtures.py writes the scenario,
template and principle ones by asking the API app over the real services on
the golden households; a change to the engine, a service or a response model
that changes what the server sends makes them stale, and the CLI's tests
would go on passing against what it no longer sends.
"""

from __future__ import annotations

from tests import cli_fixtures


def test_the_cli_fixtures_are_what_the_server_answers():
    stale = [path.name for path in cli_fixtures.stale()]
    assert not stale, (
        f"The CLI's fixtures {stale} differ from what the server answers. "
        f"Write them again: {cli_fixtures.COMMAND}"
    )
