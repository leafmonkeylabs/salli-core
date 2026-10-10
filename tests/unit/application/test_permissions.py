"""Which sign-ins carry `tax:activate` (application/permissions.py)."""

from __future__ import annotations

from typing import get_args

import pytest

from salli.application.permissions import (
    KNOWN_PERMISSIONS,
    TAX_ACTIVATE,
    Actor,
    Permission,
    may_grant,
    permissions_for,
    unknown_permissions,
)
from salli.interfaces.api.deps import Principal

ACTIVATE = frozenset({TAX_ACTIVATE})


@pytest.mark.parametrize(
    ("method", "first_party_client", "granted", "holds"),
    [
        ("session", False, (), True),
        ("dev", False, (), True),
        ("oauth", True, (), True),  # the salli CLI
        ("pat", False, (), False),  # a token made without it
        ("pat", False, (TAX_ACTIVATE,), True),  # a token the user made with it
        ("oauth", False, (), False),  # a client that registered itself
        ("mcp", False, (), False),  # an AI connector
        ("mcp", True, (), False),  # even as Salli's own client: MCP never activates
        # What only a token can store counts for nothing else.
        ("oauth", False, (TAX_ACTIVATE,), False),
        ("mcp", False, (TAX_ACTIVATE,), False),
    ],
)
def test_who_may_activate(method, first_party_client, granted, holds):
    held = permissions_for(method, first_party_client=first_party_client, granted=granted)
    assert (TAX_ACTIVATE in held) is holds
    actor = Actor.signed_in("u1", method, first_party_client=first_party_client, granted=granted)
    assert actor.may(TAX_ACTIVATE) is holds


@pytest.mark.parametrize(
    ("method", "first_party_client", "kind"),
    [
        ("session", False, "user"),
        ("dev", False, "user"),
        ("pat", False, "user"),  # the user made it, whatever it may do
        ("oauth", True, "user"),
        ("oauth", False, "agent"),
        ("mcp", False, "agent"),
        ("mcp", True, "agent"),
    ],
)
def test_who_is_recorded_as_the_author(method, first_party_client, kind):
    assert Actor.signed_in("u1", method, first_party_client=first_party_client).kind == kind


def test_a_token_holds_only_permissions_that_exist():
    assert permissions_for("pat", granted=("tax:activate", "tax:everything")) == ACTIVATE
    assert unknown_permissions(["tax:everything", TAX_ACTIVATE, "admin"]) == [
        "admin",
        "tax:everything",
    ]


def test_the_typed_names_are_the_known_permissions():
    assert frozenset(get_args(Permission)) == KNOWN_PERMISSIONS


@pytest.mark.parametrize(
    ("method", "first_party_client", "requested", "allowed", "missing"),
    [
        ("session", False, [TAX_ACTIVATE], True, []),
        ("dev", False, [TAX_ACTIVATE], True, []),
        ("oauth", True, [TAX_ACTIVATE], True, []),  # the salli CLI
        ("session", False, [], True, []),
        # A token never makes another, even one with nothing.
        ("pat", False, [], False, []),
        ("pat", False, [TAX_ACTIVATE], False, [TAX_ACTIVATE]),
        # Another application can't make a token at all: it would be a way
        # round what its own sign-in may do.
        ("oauth", False, [], False, []),
        ("oauth", False, [TAX_ACTIVATE], False, [TAX_ACTIVATE]),
    ],
)
def test_who_may_make_a_token_with_what(method, first_party_client, requested, allowed, missing):
    held = permissions_for(method, first_party_client=first_party_client)
    assert may_grant(
        method, first_party_client=first_party_client, held=held, requested=requested
    ) == (allowed, missing)


def test_a_principal_s_permissions_follow_from_its_sign_in():
    cli = Principal("u1", None, "oauth", first_party_client=True, client_name="Salli CLI")
    other = Principal("u1", None, "oauth", client_name="Some App")
    assert TAX_ACTIVATE in cli.permissions
    assert other.permissions == frozenset()
    assert other.actor() == Actor("u1", "agent", "Some App", frozenset())
    assert cli.actor().name == "Salli CLI"


def test_a_principal_s_token_permissions_are_what_it_stores():
    plain = Principal("u1", None, "pat", client_name="backup job")
    trusted = Principal("u1", None, "pat", client_name="laptop", granted=ACTIVATE)
    assert plain.permissions == frozenset()
    assert plain.actor() == Actor("u1", "user", "backup job", frozenset())
    assert trusted.permissions == ACTIVATE
    assert trusted.actor().may(TAX_ACTIVATE)
    # `granted` means nothing to any other sign-in.
    assert Principal("u1", None, "oauth", granted=ACTIVATE).permissions == frozenset()
