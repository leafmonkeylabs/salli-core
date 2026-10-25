"""
Two-step sign-in in the login service, without a database: turning it on
with a code, every password check then needing one, codes used once, wrong
codes throttled like wrong passwords, turning it off, and the owner's reset.
The same against Postgres and over HTTP: tests/integration/test_two_step_sign_in.py.
"""

from __future__ import annotations

import base64
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from salli.adapters.crypto.keyring import KeyRing
from salli.application import totp
from salli.application.services.login_service import (
    CodeNeeded,
    CodeRefused,
    LoginService,
    SignInRefused,
    SignInThrottled,
    TwoStepState,
    TwoStepUnavailable,
)
from tests.fakes import FakeAuditLog
from tests.unit.application.test_login_service import PASSWORD, Clock, Hasher, Logins, Profiles

pytestmark = pytest.mark.asyncio

EMAIL = "ada@example.org"
KEYS = "1:" + base64.b64encode(b"k" * 32).decode()


class TwoStepLogins(Logins):
    """The fake LoginRepository, with two-step sign-in."""

    async def create(self, user_id, email, password_hash, *, is_owner, at):
        made = await super().create(user_id, email, password_hash, is_owner=is_owner, at=at)
        self.logins[user_id].update(
            totp_secret=None,
            totp_key_version=None,
            totp_enabled_at=None,
            totp_last_step=None,
            totp_recovery_codes=[],
        )
        return made

    async def set_totp(self, user_id, sealed, key_version):
        self.logins[user_id].update(
            totp_secret=sealed,
            totp_key_version=key_version,
            totp_enabled_at=None,
            totp_last_step=None,
            totp_recovery_codes=[],
        )

    async def enable_totp(self, user_id, recovery_hashes, *, step, at):
        login = self.logins[user_id]
        if login["totp_secret"] is None or login["totp_enabled_at"] is not None:
            return False
        login.update(totp_enabled_at=at, totp_last_step=step, totp_recovery_codes=recovery_hashes)
        return True

    async def use_totp_step(self, user_id, step):
        login = self.logins[user_id]
        if login["totp_last_step"] is not None and login["totp_last_step"] >= step:
            return False
        login["totp_last_step"] = step
        return True

    async def use_recovery_code(self, user_id, code_hash):
        codes = self.logins[user_id]["totp_recovery_codes"]
        if code_hash not in codes:
            return False
        codes.remove(code_hash)
        return True


def _service(logins, clock, keyring=None) -> LoginService:
    profiles = Profiles()
    audit = FakeAuditLog()

    @asynccontextmanager
    async def uow():
        yield SimpleNamespace(logins=logins, user_profiles=profiles, audit_log=audit)

    return LoginService(uow, Hasher(), clock=clock, keyring=keyring)


@pytest.fixture
def world():
    logins, clock = TwoStepLogins(), Clock()
    return SimpleNamespace(
        logins=logins, clock=clock, service=_service(logins, clock, KeyRing(KEYS))
    )


def _code(world, secret: str, steps_on: int = 0) -> str:
    return totp.code_at(secret, totp.step_of(world.clock().timestamp()) + steps_on)


async def _turned_on(world) -> tuple[str, str, list[str]]:
    uid = (await world.service.create_account(EMAIL, PASSWORD))["user_id"]
    enrolment = await world.service.begin_totp(uid)
    codes = await world.service.confirm_totp(uid, _code(world, enrolment.secret))
    world.clock.advance(seconds=30)  # the confirming code is used; the next one isn't
    return uid, enrolment.secret, codes


async def test_turning_it_on_takes_a_code_from_the_new_secret(world):
    uid = (await world.service.create_account(EMAIL, PASSWORD))["user_id"]
    enrolment = await world.service.begin_totp(uid)
    assert enrolment.uri.startswith("otpauth://totp/Salli%3Aada%40example.org?secret=")
    stored = world.logins.logins[uid]
    # Sealed, not kept as typed; and not on yet, so a password alone still signs in.
    assert stored["totp_secret"] and enrolment.secret not in stored["totp_secret"]
    assert stored["totp_enabled_at"] is None
    await world.service.authenticate(EMAIL, PASSWORD)

    with pytest.raises(CodeRefused):
        await world.service.confirm_totp(uid, _code(world, enrolment.secret, 2))  # a minute out
    codes = await world.service.confirm_totp(uid, _code(world, enrolment.secret))
    assert len(codes) == 10
    assert stored["totp_enabled_at"] is not None
    assert stored["totp_recovery_codes"] == [totp.recovery_hash(c) for c in codes]
    assert (await world.service.get_login(uid)).keys().isdisjoint({"totp_secret", "password_hash"})
    with pytest.raises(TwoStepState):
        await world.service.begin_totp(uid)  # off first, then a new one


async def test_once_on_the_password_alone_is_refused(world):
    _, secret, _ = await _turned_on(world)
    with pytest.raises(CodeNeeded):
        await world.service.authenticate(EMAIL, PASSWORD)
    with pytest.raises(CodeNeeded):
        await world.service.sign_in(EMAIL, PASSWORD, code="  ")
    # Leaving the code out is not a failed attempt; a wrong one is.
    assert world.logins.failures == []
    with pytest.raises(CodeRefused):
        await world.service.authenticate(EMAIL, PASSWORD, code="12345x")
    assert len(world.logins.failures) == 1
    session = await world.service.sign_in(EMAIL, PASSWORD, code=_code(world, secret))
    assert session.token
    # The code is needed after the right password only: a wrong password says only that.
    with pytest.raises(SignInRefused) as wrong:
        await world.service.authenticate(EMAIL, "not the password", code=_code(world, secret))
    assert type(wrong.value) is SignInRefused


async def test_a_code_is_used_once(world):
    _, secret, _ = await _turned_on(world)
    code = _code(world, secret)
    await world.service.authenticate(EMAIL, PASSWORD, code=code)
    with pytest.raises(CodeRefused):
        await world.service.authenticate(EMAIL, PASSWORD, code=code)
    # Nor one from before it.
    with pytest.raises(CodeRefused):
        await world.service.authenticate(EMAIL, PASSWORD, code=_code(world, secret, -1))
    world.clock.advance(seconds=30)
    await world.service.authenticate(EMAIL, PASSWORD, code=_code(world, secret))


async def test_a_recovery_code_stands_in_for_the_app_once(world):
    _, _, codes = await _turned_on(world)
    await world.service.authenticate(EMAIL, PASSWORD, code=codes[0].upper())
    with pytest.raises(CodeRefused):
        await world.service.authenticate(EMAIL, PASSWORD, code=codes[0])
    await world.service.authenticate(EMAIL, PASSWORD, code=codes[1])


async def test_wrong_codes_are_throttled_like_wrong_passwords(world):
    _, secret, _ = await _turned_on(world)
    for _ in range(5):
        with pytest.raises(CodeRefused):
            await world.service.authenticate(EMAIL, PASSWORD, code="aaaaa-aaaaa")
    with pytest.raises(SignInThrottled):
        await world.service.authenticate(EMAIL, PASSWORD, code=_code(world, secret))
    world.clock.advance(minutes=16)
    await world.service.authenticate(EMAIL, PASSWORD, code=_code(world, secret))


async def test_changing_the_password_needs_the_code(world):
    uid, secret, _ = await _turned_on(world)
    with pytest.raises(CodeNeeded):
        await world.service.change_password(uid, PASSWORD, "another long password")
    await world.service.change_password(
        uid, PASSWORD, "another long password", code=_code(world, secret)
    )


async def test_turning_it_off_needs_the_password_and_a_code(world):
    uid, secret, codes = await _turned_on(world)
    with pytest.raises(CodeNeeded):
        await world.service.disable_totp(uid, PASSWORD, None)
    with pytest.raises(SignInRefused):
        await world.service.disable_totp(uid, "not the password", _code(world, secret))
    await world.service.disable_totp(uid, PASSWORD, codes[3])
    assert world.logins.logins[uid]["totp_secret"] is None
    assert world.logins.logins[uid]["totp_recovery_codes"] == []
    await world.service.authenticate(EMAIL, PASSWORD)
    with pytest.raises(TwoStepState):
        await world.service.disable_totp(uid, PASSWORD, None)


async def test_the_owner_s_reset_can_turn_it_off(world):
    uid, _, _ = await _turned_on(world)
    kept = await world.service.reset_password(EMAIL, "a fresh password here")
    assert kept["totp_cleared"] is False
    with pytest.raises(CodeNeeded):
        await world.service.authenticate(EMAIL, "a fresh password here")
    reset = await world.service.reset_password(EMAIL, "a fresh password here", clear_totp=True)
    assert reset["totp_cleared"] is True and "totp_secret" not in reset
    await world.service.authenticate(EMAIL, "a fresh password here")


async def test_without_an_encryption_key_it_can_t_be_turned_on():
    logins, clock = TwoStepLogins(), Clock()
    for keyring in (None, KeyRing("")):
        service = _service(logins, clock, keyring)
        uid = (await service.create_account(f"x{id(keyring)}@example.org", PASSWORD))["user_id"]
        with pytest.raises(TwoStepUnavailable, match="BYOK_ENCRYPTION_KEYS"):
            await service.begin_totp(uid)
