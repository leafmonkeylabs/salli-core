"""Which sign-ins carry `tax:activate` (application/permissions.py)."""

from __future__ import annotations

from datetime import timedelta
from typing import get_args

import pytest

from salli.application.permissions import (
    KNOWN_PERMISSIONS,
    TAX_ACTIVATE,
    Actor,
    Permission,
    may_grant,
    needs_step_up,
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


# ── Step-up: the console's tax:activate, within five minutes of the password ──

FIVE_MINUTES = timedelta(seconds=300)


@pytest.mark.parametrize(
    ("age", "holds"),
    [
        (timedelta(0), True),
        (timedelta(minutes=4, seconds=59), True),
        (timedelta(minutes=5), True),  # five minutes is within five minutes
        (timedelta(minutes=5, seconds=1), False),
        (timedelta(hours=11), False),
        (None, False),  # a sign-in whose password check isn't known
        (timedelta(seconds=-1), False),  # a check in the future is no check
    ],
)
def test_the_console_holds_tax_activate_only_just_after_the_password(age, holds):
    held = permissions_for(
        "oauth", first_party_client=True, sign_in_age=age, fresh_within=FIVE_MINUTES
    )
    assert (TAX_ACTIVATE in held) is holds
    actor = Actor.signed_in(
        "u1", "oauth", first_party_client=True, sign_in_age=age, fresh_within=FIVE_MINUTES
    )
    assert actor.may(TAX_ACTIVATE) is holds
    assert actor.kind == "user"  # a person either way: only the permission waits
    assert needs_step_up(
        "oauth",
        TAX_ACTIVATE,
        first_party_client=True,
        sign_in_age=age,
        fresh_within=FIVE_MINUTES,
    ) is (not holds)


def test_a_client_that_asks_for_no_recency_keeps_its_permissions_at_any_age():
    # The CLI: a terminal an agent can't fake is its protection.
    for age in (None, timedelta(days=30)):
        assert permissions_for("oauth", first_party_client=True, sign_in_age=age) == ACTIVATE
        assert not needs_step_up("oauth", TAX_ACTIVATE, first_party_client=True, sign_in_age=age)


@pytest.mark.parametrize(
    ("method", "first_party_client", "granted"),
    [
        ("mcp", False, ()),
        ("mcp", True, ()),
        ("oauth", False, ()),  # another application
        ("pat", False, ()),  # a token made without it
    ],
)
def test_signing_in_again_never_gives_what_a_sign_in_can_never_hold(
    method, first_party_client, granted
):
    """MCP never activates, however fresh; nor another application; nor a
    token made without it. Step-up is no way round any of them."""
    for age in (timedelta(0), timedelta(hours=1)):
        assert TAX_ACTIVATE not in permissions_for(
            method,
            first_party_client=first_party_client,
            granted=granted,
            sign_in_age=age,
            fresh_within=FIVE_MINUTES,
        )
        assert not needs_step_up(
            method,
            TAX_ACTIVATE,
            first_party_client=first_party_client,
            granted=granted,
            sign_in_age=age,
            fresh_within=FIVE_MINUTES,
        )


def test_a_principal_carries_its_sign_in_s_age_into_its_permissions():
    fresh = Principal(
        "u1",
        None,
        "oauth",
        first_party_client=True,
        sign_in_age=timedelta(minutes=4, seconds=59),
        fresh_within=FIVE_MINUTES,
    )
    stale = Principal(
        "u1",
        None,
        "oauth",
        first_party_client=True,
        sign_in_age=timedelta(minutes=5, seconds=1),
        fresh_within=FIVE_MINUTES,
    )
    assert fresh.permissions == ACTIVATE and fresh.actor().may(TAX_ACTIVATE)
    assert stale.permissions == frozenset() and not stale.actor().may(TAX_ACTIVATE)
    assert stale.needs_step_up(TAX_ACTIVATE) and not fresh.needs_step_up(TAX_ACTIVATE)
