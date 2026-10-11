"""
Salli's own accounts, without a database: passwords, signing in, throttling
and sessions (application/services/login_service.py). The same rules against
Postgres are in tests/integration/test_logins.py.
"""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from salli.application.services.login_service import (
    MAX_PASSWORD_LENGTH,
    REFUSED,
    SESSION_PREFIX,
    LoginExists,
    LoginNotFound,
    LoginService,
    PasswordRejected,
    SignInRefused,
    SignInThrottled,
    Throttle,
    check_password,
    normalize_email,
)

pytestmark = pytest.mark.asyncio

PASSWORD = "a long enough password"
T0 = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


class Hasher:
    """A transparent stand-in for argon2: records what it was asked."""

    def __init__(self, version: int = 1) -> None:
        self.version = version
        self.verified: list[str] = []
        self.hashed = 0

    async def hash(self, password: str) -> str:
        self.hashed += 1
        return f"v{self.version}:{password}"

    async def verify(self, password_hash: str, password: str) -> bool:
        self.verified.append(password_hash)
        return password_hash.split(":", 1)[1] == password

    def needs_rehash(self, password_hash: str) -> bool:
        return not password_hash.startswith(f"v{self.version}:")


class Logins:
    """The LoginRepository port, in memory."""

    def __init__(self) -> None:
        self.logins: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.failures: list[tuple[str, datetime]] = []

    async def create(self, user_id, email, password_hash, *, is_owner, at):
        self.logins[user_id] = {
            "user_id": user_id,
            "email": email,
            "password_hash": password_hash,
            "is_owner": is_owner,
            "password_changed_at": at,
            "created_at": at,
        }
        return {k: v for k, v in self.logins[user_id].items() if k != "password_hash"}

    async def get(self, user_id):
        login = self.logins.get(user_id)
        return dict(login) if login else None

    async def get_by_email(self, email):
        return next((dict(v) for v in self.logins.values() if v["email"] == email), None)

    async def owner(self):
        return next((dict(v) for v in self.logins.values() if v["is_owner"]), None)

    async def list(self):
        return [dict(v) for v in self.logins.values()]

    async def set_password(self, user_id, password_hash, *, changed_at):
        self.logins[user_id]["password_hash"] = password_hash
        if changed_at is not None:
            self.logins[user_id]["password_changed_at"] = changed_at
        return True

    async def create_session(self, user_id, token_hash, user_agent, at, expires_at):
        sid = f"s{len(self.sessions) + 1}"
        self.sessions[sid] = {
            "id": sid,
            "user_id": user_id,
            "token_hash": token_hash,
            "user_agent": user_agent,
            "created_at": at,
            "last_used_at": at,
            "expires_at": expires_at,
            "revoked_at": None,
        }
        return dict(self.sessions[sid])

    def _live(self, s, now):
        return s["revoked_at"] is None and s["expires_at"] > now

    async def get_session(self, token_hash, now):
        return next(
            (
                dict(s)
                for s in self.sessions.values()
                if s["token_hash"] == token_hash and self._live(s, now)
            ),
            None,
        )

    async def list_sessions(self, user_id, now):
        return [
            dict(s)
            for s in self.sessions.values()
            if s["user_id"] == user_id and self._live(s, now)
        ]

    async def touch_session(self, session_id, at):
        self.sessions[session_id]["last_used_at"] = at

    async def revoke_session(self, user_id, session_id, at):
        s = self.sessions.get(session_id)
        if s is None or s["user_id"] != user_id or s["revoked_at"] is not None:
            return False
        s["revoked_at"] = at
        return True

    async def revoke_sessions(self, user_id, at, *, keep=None):
        n = 0
        for s in self.sessions.values():
            if s["user_id"] == user_id and s["revoked_at"] is None and s["id"] != keep:
                s["revoked_at"] = at
                n += 1
        return n

    async def record_failure(self, key_hash, at):
        self.failures.append((key_hash, at))

    async def failures_since(self, key_hash, since):
        return sorted(at for k, at in self.failures if k == key_hash and at > since)

    async def clear_failures(self, key_hash):
        self.failures = [(k, at) for k, at in self.failures if k != key_hash]

    async def prune_failures(self, before):
        self.failures = [(k, at) for k, at in self.failures if at > before]


class Profiles:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def get(self, user_id):
        return self.rows.get(user_id)

    async def upsert(self, user_id, fields):
        self.rows.setdefault(user_id, {"id": user_id}).update(fields)


class World(SimpleNamespace):
    service: LoginService
    logins: Logins
    profiles: Profiles
    hasher: Hasher
    clock: Clock


@pytest.fixture
def world() -> World:
    logins, profiles, hasher, clock = Logins(), Profiles(), Hasher(), Clock()
    revoked: dict[str, int] = {"oauth": 0, "pat": 0}

    async def revoke_all_oauth(user_id):
        revoked["oauth"] += 1
        return 3

    async def revoke_all_pats(user_id):
        revoked["pat"] += 1
        return 2

    @asynccontextmanager
    async def uow():
        yield SimpleNamespace(
            logins=logins,
            user_profiles=profiles,
            oauth_tokens=SimpleNamespace(revoke_all_for_user=revoke_all_oauth),
            personal_access_tokens=SimpleNamespace(revoke_all=revoke_all_pats),
        )

    service = LoginService(
        uow, hasher, session_ttl=timedelta(days=30), default_currency="EUR", clock=clock
    )
    return World(service=service, logins=logins, profiles=profiles, hasher=hasher, clock=clock)


async def _account(world: World, email: str = "Ada@Example.org", **kw) -> str:
    login = await world.service.create_account(email, PASSWORD, **kw)
    return login["user_id"]


# ── Accounts ────────────────────────────────────────────────────────────────


async def test_an_account_is_a_profile_and_a_login_kept_lower_cased(world):
    uid = await _account(world, base_currency="jpy", owner=True)
    assert world.profiles.rows[uid] == {
        "id": uid,
        "email": "ada@example.org",
        "base_currency": "JPY",
    }
    login = world.logins.logins[uid]
    assert (login["email"], login["is_owner"]) == ("ada@example.org", True)
    # Only the hash is kept.
    assert login["password_hash"] == f"v1:{PASSWORD}" and PASSWORD not in str(world.profiles.rows)


async def test_a_new_account_takes_the_instance_s_currency_by_default(world):
    uid = await _account(world)
    assert world.profiles.rows[uid]["base_currency"] == "EUR"


async def test_an_email_has_one_account_whatever_its_case(world):
    await _account(world, "ada@example.org")
    with pytest.raises(LoginExists):
        await _account(world, "  ADA@example.ORG ")


async def test_an_instance_has_one_owner(world):
    await _account(world, "owner@example.org", owner=True)
    with pytest.raises(LoginExists, match="already has an owner"):
        await _account(world, "second@example.org", owner=True)
    assert (await world.service.owner())["email"] == "owner@example.org"


@pytest.mark.parametrize("email", ["", "no-at-sign", "@example.org", "ada@", "a b@example.org"])
async def test_something_that_is_not_an_email_is_refused(email):
    with pytest.raises(ValueError):
        normalize_email(email)


@pytest.mark.parametrize(
    ("password", "why"),
    [
        ("short", "at least 12"),
        ("x" * (MAX_PASSWORD_LENGTH + 1), "at most"),
        ("Ada@Example.org", "can't be the email"),
    ],
)
async def test_a_weak_password_is_refused(password, why):
    with pytest.raises(PasswordRejected, match=why):
        check_password(password, "ada@example.org")


async def test_a_weak_password_makes_no_account(world):
    with pytest.raises(PasswordRejected):
        await world.service.create_account("ada@example.org", "too short")
    assert world.logins.logins == {} and world.profiles.rows == {}


# ── Signing in ──────────────────────────────────────────────────────────────


async def test_the_right_password_signs_in_whatever_the_email_s_case(world):
    uid = await _account(world)
    who = await world.service.authenticate(" ADA@example.org", PASSWORD)
    assert (who.user_id, who.email) == (uid, "ada@example.org")


async def test_a_wrong_password_and_an_unknown_email_fail_alike(world):
    await _account(world)
    with pytest.raises(SignInRefused) as wrong:
        await world.service.authenticate("ada@example.org", "not the password")
    with pytest.raises(SignInRefused) as unknown:
        await world.service.authenticate("nobody@example.org", PASSWORD)
    assert str(wrong.value) == str(unknown.value) == REFUSED


async def test_an_unknown_email_is_checked_against_a_hash_all_the_same(world):
    """The same work either way, so the time taken says nothing about who has
    an account."""
    with pytest.raises(SignInRefused):
        await world.service.authenticate("nobody@example.org", PASSWORD)
    assert len(world.hasher.verified) == 1
    assert world.hasher.verified[0] != ""


async def test_a_known_email_costs_the_same_work_as_an_unknown_one(world):
    """Hash and verify counts match either way, the first time as after."""
    await _account(world)
    hashed, verified = world.hasher.hashed, len(world.hasher.verified)
    with pytest.raises(SignInRefused):
        await world.service.authenticate("ada@example.org", "a wrong password")
    known = (world.hasher.hashed - hashed, len(world.hasher.verified) - verified)

    other = LoginService(world.service._uow_factory, world.hasher, clock=world.clock)  # noqa: SLF001
    hashed, verified = world.hasher.hashed, len(world.hasher.verified)
    with pytest.raises(SignInRefused):
        await other.authenticate("nobody@example.org", "a wrong password")
    assert (world.hasher.hashed - hashed, len(world.hasher.verified) - verified) == known


async def test_a_password_too_long_to_be_anyone_s_is_not_hashed(world):
    await _account(world)
    with pytest.raises(SignInRefused):
        await world.service.authenticate("ada@example.org", "x" * (MAX_PASSWORD_LENGTH + 1))
    assert world.hasher.verified == []


async def test_a_hash_with_old_parameters_is_made_again_at_sign_in(world):
    uid = await _account(world)
    changed_at = world.logins.logins[uid]["password_changed_at"]
    world.hasher.version = 2
    world.clock.advance(days=1)
    await world.service.authenticate("ada@example.org", PASSWORD)
    login = world.logins.logins[uid]
    assert login["password_hash"] == f"v2:{PASSWORD}"
    # The same password: not a change.
    assert login["password_changed_at"] == changed_at
    # Done once.
    hashed = world.hasher.hashed
    await world.service.authenticate("ada@example.org", PASSWORD)
    assert world.hasher.hashed == hashed


# ── Throttling ──────────────────────────────────────────────────────────────


async def _fail(world: World, email: str = "ada@example.org", address: str | None = None) -> None:
    with pytest.raises(SignInRefused):
        await world.service.authenticate(email, "wrong password", address=address)


async def test_five_failures_lock_an_email_for_fifteen_minutes_without_checking(world):
    await _account(world)
    for _ in range(5):
        await _fail(world)
    checked = len(world.hasher.verified)
    with pytest.raises(SignInThrottled) as throttled:
        await world.service.authenticate("ada@example.org", PASSWORD)
    # Even the right password is not checked while locked.
    assert len(world.hasher.verified) == checked
    assert throttled.value.retry_after == 15 * 60
    assert "Try again in 15 minutes" in str(throttled.value)

    world.clock.advance(minutes=15)
    assert (await world.service.authenticate("ada@example.org", PASSWORD)).email


async def test_the_lock_lifts_as_the_oldest_failures_age_out(world):
    await _account(world)
    await _fail(world)
    world.clock.advance(minutes=10)
    for _ in range(4):
        await _fail(world)
    with pytest.raises(SignInThrottled) as throttled:
        await world.service.authenticate("ada@example.org", PASSWORD)
    # The first failure leaves the window in five minutes.
    assert throttled.value.retry_after == 5 * 60
    world.clock.advance(minutes=5)
    await world.service.authenticate("ada@example.org", PASSWORD)


async def test_an_email_without_an_account_is_throttled_the_same(world):
    """Otherwise the throttle would say which emails have accounts."""
    for _ in range(5):
        await _fail(world, "nobody@example.org")
    with pytest.raises(SignInThrottled):
        await world.service.authenticate("nobody@example.org", PASSWORD)


async def test_a_throttled_attempt_does_not_extend_the_lock(world):
    await _account(world)
    for _ in range(5):
        await _fail(world)
    for _ in range(3):
        with pytest.raises(SignInThrottled):
            await world.service.authenticate("ada@example.org", "wrong password")
    assert len(world.logins.failures) == 5


async def test_an_address_that_fails_across_many_emails_is_locked_too(world):
    service = LoginService(
        world.service._uow_factory,  # noqa: SLF001
        world.hasher,
        throttle=Throttle(per_account=5, per_address=3),
        clock=world.clock,
    )
    for i in range(3):
        with pytest.raises(SignInRefused):
            await service.authenticate(f"user{i}@example.org", "guess", address="203.0.113.9")
    with pytest.raises(SignInThrottled):
        await service.authenticate("fresh@example.org", "guess", address="203.0.113.9")
    # From somewhere else, the same email is fine to try.
    with pytest.raises(SignInRefused):
        await service.authenticate("fresh@example.org", "guess", address="198.51.100.7")


async def test_signing_in_clears_the_email_s_failures_but_not_the_address_s(world):
    await _account(world)
    for _ in range(4):
        await _fail(world, address="203.0.113.9")
    await world.service.authenticate("ada@example.org", PASSWORD, address="203.0.113.9")
    keys = {k for k, _ in world.logins.failures}
    assert keys == {hashlib.sha256(b"address:203.0.113.9").hexdigest()}


async def test_failures_are_kept_by_hash_never_by_email(world):
    await _fail(world, "ada@example.org", address="203.0.113.9")
    stored = repr(world.logins.failures)
    assert "ada@example.org" not in stored and "203.0.113.9" not in stored


# ── Sessions ────────────────────────────────────────────────────────────────


async def test_a_session_is_an_opaque_token_stored_only_as_its_hash(world):
    uid = await _account(world)
    session = await world.service.sign_in("ada@example.org", PASSWORD, user_agent="Salli iOS")
    assert session.token.startswith(SESSION_PREFIX) and len(session.token) >= 50
    assert session.expires_at == T0 + timedelta(days=30)
    [stored] = world.logins.sessions.values()
    assert stored["token_hash"] == hashlib.sha256(session.token.encode()).hexdigest()
    assert session.token not in repr(world.logins.sessions)
    assert (await world.service.verify_session(session.token)).user_id == uid


async def test_every_sign_in_is_a_new_token(world):
    await _account(world)
    first = await world.service.sign_in("ada@example.org", PASSWORD)
    second = await world.service.sign_in("ada@example.org", PASSWORD)
    assert first.token != second.token and first.id != second.id


async def test_a_session_ends_when_it_expires_however_much_it_is_used(world):
    await _account(world)
    session = await world.service.sign_in("ada@example.org", PASSWORD)
    for _ in range(3):
        world.clock.advance(days=9)
        assert await world.service.verify_session(session.token) is not None
    world.clock.advance(days=3)
    assert await world.service.verify_session(session.token) is None


async def test_last_use_is_recorded_at_most_once_a_minute(world):
    await _account(world)
    session = await world.service.sign_in("ada@example.org", PASSWORD)
    world.clock.advance(seconds=30)
    await world.service.verify_session(session.token)
    assert world.logins.sessions[session.id]["last_used_at"] == T0
    world.clock.advance(seconds=31)
    await world.service.verify_session(session.token)
    assert world.logins.sessions[session.id]["last_used_at"] == world.clock.now


@pytest.mark.parametrize("token", ["", "salli_st_", "salli_st_made-up", "salli_pat_x", "ada"])
async def test_a_token_that_was_never_issued_is_no_session(world, token):
    await _account(world)
    await world.service.sign_in("ada@example.org", PASSWORD)
    assert await world.service.verify_session(token) is None


async def test_a_revoked_session_ends_and_only_its_owner_can_revoke_it(world):
    ada = await _account(world)
    bob = await _account(world, "bob@example.org")
    session = await world.service.sign_in("ada@example.org", PASSWORD)
    assert not await world.service.revoke_session(bob, session.id)
    assert await world.service.verify_session(session.token) is not None
    assert await world.service.revoke_session(ada, session.id)
    assert await world.service.verify_session(session.token) is None
    assert not await world.service.revoke_session(ada, session.id)


async def test_a_user_agent_is_kept_short_and_printable(world):
    await _account(world)
    await world.service.sign_in(
        "ada@example.org", PASSWORD, user_agent="evil\x1b[31m\n" + "x" * 500
    )
    [stored] = world.logins.sessions.values()
    assert "\x1b" not in stored["user_agent"] and "\n" not in stored["user_agent"]
    assert len(stored["user_agent"]) == 200


# ── Passwords ───────────────────────────────────────────────────────────────


async def test_changing_the_password_ends_every_other_session(world):
    uid = await _account(world)
    here = await world.service.sign_in("ada@example.org", PASSWORD)
    there = await world.service.sign_in("ada@example.org", PASSWORD)
    ended = await world.service.change_password(
        uid, PASSWORD, "an even longer password", keep_session=here.id
    )
    assert ended == 1
    assert await world.service.verify_session(here.token) is not None
    assert await world.service.verify_session(there.token) is None
    with pytest.raises(SignInRefused):
        await world.service.authenticate("ada@example.org", PASSWORD)
    await world.service.authenticate("ada@example.org", "an even longer password")


async def test_a_change_needs_the_current_password_and_is_throttled_like_a_sign_in(world):
    uid = await _account(world)
    for _ in range(5):
        with pytest.raises(SignInRefused):
            await world.service.change_password(uid, "wrong guess", "a brand new password")
    with pytest.raises(SignInThrottled):
        await world.service.change_password(uid, PASSWORD, "a brand new password")
    assert world.logins.logins[uid]["password_hash"] == f"v1:{PASSWORD}"


async def test_a_change_to_a_weak_password_is_refused_and_ends_nothing(world):
    uid = await _account(world)
    session = await world.service.sign_in("ada@example.org", PASSWORD)
    with pytest.raises(PasswordRejected):
        await world.service.change_password(uid, PASSWORD, "short")
    assert await world.service.verify_session(session.token) is not None


async def test_the_owner_s_reset_needs_no_password_and_ends_every_session(world):
    uid = await _account(world)
    sessions = [await world.service.sign_in("ada@example.org", PASSWORD) for _ in range(2)]
    for _ in range(5):
        await _fail(world)
    reset = await world.service.reset_password("ADA@example.org", "a fresh password here")
    assert (reset["user_id"], reset["sessions_ended"]) == (uid, 2)
    assert "password_hash" not in reset
    for session in sessions:
        assert await world.service.verify_session(session.token) is None
    # The reset lifts the lock too: the person can sign in at once.
    await world.service.authenticate("ada@example.org", "a fresh password here")


async def test_a_reset_for_an_unknown_email_says_so(world):
    with pytest.raises(LoginNotFound):
        await world.service.reset_password("nobody@example.org", "a fresh password here")


async def test_signing_out_everywhere_revokes_sessions_oauth_tokens_and_access_tokens(world):
    uid = await _account(world)
    session = await world.service.sign_in("ada@example.org", PASSWORD)
    ended = await world.service.sign_out_everywhere(uid)
    assert ended == {"sessions": 1, "oauth_tokens": 3, "personal_access_tokens": 2}
    assert await world.service.verify_session(session.token) is None
