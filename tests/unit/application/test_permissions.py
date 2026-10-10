"""Which sign-ins carry `tax:activate` (application/permissions.py)."""

from __future__ import annotations

import pytest

from salli.application.permissions import TAX_ACTIVATE, Actor, permissions_for
from salli.interfaces.api.deps import Principal


@pytest.mark.parametrize(
    ("method", "first_party_client", "holds"),
    [
        ("session", False, True),
        ("pat", False, True),
        ("dev", False, True),
        ("oauth", True, True),  # the salli CLI
        ("oauth", False, False),  # a client that registered itself
        ("mcp", False, False),  # an AI connector
        ("mcp", True, False),  # even as Salli's own client: MCP never activates
    ],
)
def test_only_the_user_s_own_sign_ins_may_activate(method, first_party_client, holds):
    granted = permissions_for(method, first_party_client=first_party_client)
    assert (TAX_ACTIVATE in granted) is holds
    actor = Actor.signed_in("u1", method, first_party_client=first_party_client)
    assert actor.may(TAX_ACTIVATE) is holds
    # Whoever can't activate is recorded as an agent when they write.
    assert actor.kind == ("user" if holds else "agent")


def test_a_principal_s_permissions_follow_from_its_sign_in():
    cli = Principal("u1", None, "oauth", first_party_client=True, client_name="Salli CLI")
    other = Principal("u1", None, "oauth", client_name="Some App")
    assert TAX_ACTIVATE in cli.permissions
    assert other.permissions == frozenset()
    assert other.actor() == Actor("u1", "agent", "Some App", frozenset())
    assert cli.actor().name == "Salli CLI"
