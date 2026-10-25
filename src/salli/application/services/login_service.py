"""
Salli's own accounts: who can sign in, with what, and the sessions a sign-in
starts. Signing in needs nothing but this database (decision D13).

**Accounts.** A login is an email and a password, kept as an argon2id hash
(`PasswordHasher`; adapters/auth/passwords.py). A hash made with older
parameters is made again, with the current ones, the next time its owner signs
in. There is no sign-up: the owner's account is made by `salli-server setup`,
and everyone else's by the owner (`salli-server members add`), or by the
person from an owner's single-use invitation link (`salli-server members
invite`, the /join page), which the owner passes on themselves. Passwords are
changed by their owner (`POST /v1/auth/password`, which needs the current one)
or reset by the instance's owner on the server (`salli-server members
reset-password`). Salli sends no email, so there is no reset link.

**Signing in** (`authenticate`) answers the same way, and takes about as long,
whether or not the email has an account: an unknown email is checked against
a hash of a random password, and both failures say only that the email and
password didn't match. Failures are counted, by a hash of the email tried and
of the address it came from, and a sign-in is refused without checking the
password once either has failed too often in the window (`Throttle`); the
refusal says when to try again. The count is kept for an email whether or not
it has an account, so the throttle tells no one which emails do.

**Two-step sign-in** is optional, per login: once it is on, every password
check (signing in, the sign-in, consent and device pages, changing the
password, turning it off) also needs a code from an authenticator app
(application/totp.py), or one of ten recovery codes, each good once. A wrong
code counts as a failed sign-in for the throttle; no code is used twice. The
app's secret is sealed with the key ring that seals stored AI keys, so
without an encryption key configured it can't be turned on. The person turns
it on (a secret, then a code from it to prove the app has it) and off (the
password and a code); the instance's owner can turn it off for someone who
has lost both their app and their recovery codes (`salli-server members
reset-password --clear-totp`).

**Sessions** are opaque tokens (`salli_st_` and 256 random bits), issued by
this server and stored as SHA-256 hashes: the token is seen once, when it is
issued. A session lasts a fixed time from when it starts, and ends early when
its holder signs out, revokes it from another session, or changes their
password (which ends every other session); a reset by the owner ends them all.
A new session is always a new token: a client can never choose or keep one
across a sign-in, so there is nothing to fix a session with.
"""

from __future__ import annotations

import hashlib
import math
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from salli.application import totp
from salli.application.ports import PasswordHasher
from salli.domain.currency import normalize_currency

#: What a session token starts with: secret scanners can spot a leaked one,
#: and the API can tell one from its other tokens without a lookup.
SESSION_PREFIX = "salli_st_"

#: What an invitation token starts with, and how long one is good for.
INVITATION_PREFIX = "salli_inv_"
INVITATION_TTL = timedelta(days=7)

MIN_PASSWORD_LENGTH = 12
#: Long enough for any passphrase or manager-made password; short enough that
#: no one can make the server hash a megabyte.
MAX_PASSWORD_LENGTH = 1024
MAX_EMAIL_LENGTH = 320

#: Recording "last used" on every request would be a write per request.
_TOUCH_EVERY = timedelta(minutes=1)
_USER_AGENT_LENGTH = 200

#: The one answer to a failed sign-in, whatever failed.
REFUSED = "That email and password didn't match."


class SignInRefused(Exception):
    """The email and password didn't match an account (which, is not said)."""

    def __init__(self, message: str = REFUSED) -> None:
        super().__init__(message)


class CodeNeeded(SignInRefused):
    """The password was right, and the login has two-step sign-in on: it
    needs a code too."""

    def __init__(self) -> None:
        super().__init__("Enter the code from your authenticator app, or a recovery code.")


class CodeRefused(SignInRefused):
    """The code was not the authenticator app's now, nor an unused recovery code."""

    def __init__(self) -> None:
        super().__init__("That code didn't match. Codes change every 30 seconds.")


class TwoStepUnavailable(RuntimeError):
    """This server has no encryption key to seal an authenticator secret with."""


class TwoStepState(ValueError):
    """Two-step sign-in is not in the state the request needs (on, off, begun)."""


class SignInThrottled(Exception):
    """Too many failed sign-ins lately; try again in `retry_after` seconds."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)
        # No countdown in the words; `Retry-After` carries the seconds.
        super().__init__("Too many failed sign-ins. Wait a few minutes, then try again.")


class PasswordRejected(ValueError):
    """A new password that doesn't meet the rules."""


class LoginExists(ValueError):
    """That email already has an account, or the instance already has an owner."""


class LoginNotFound(LookupError):
    """No account has that email (said only to the server's operator)."""


@dataclass(frozen=True)
class Throttle:
    """How many failed sign-ins are allowed in `window`, per email tried and
    per address tried from, before sign-ins are refused unchecked."""

    per_account: int = 5
    per_address: int = 50
    window: timedelta = timedelta(minutes=15)


@dataclass(frozen=True)
class SignedIn:
    user_id: str
    email: str


@dataclass(frozen=True)
class NewSession:
    """A session just started. `token` is the only time it is ever seen."""

    id: str
    user_id: str
    email: str
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class TwoStepEnrolment:
    """A new authenticator secret, shown once: `uri` for the app to read,
    `secret` to type in."""

    secret: str
    uri: str


@dataclass(frozen=True)
class VerifiedSession:
    id: str
    user_id: str


def normalize_email(email: str) -> str:
    """An email as accounts are kept: trimmed and lower-cased. Raises
    ValueError for something that is plainly not an address."""
    value = email.strip().lower()
    local, at, domain = value.rpartition("@")
    if (
        not at
        or not local
        or not domain
        or len(value) > MAX_EMAIL_LENGTH
        or any(ch.isspace() or ord(ch) < 32 for ch in value)
    ):
        raise ValueError("That is not an email address.")
    return value


def check_password(password: str, email: str | None = None) -> None:
    """Raises PasswordRejected unless `password` may be set."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordRejected(f"A password needs at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordRejected(f"A password can have at most {MAX_PASSWORD_LENGTH} characters.")
    if email and password.strip().lower() == email.strip().lower():
        raise PasswordRejected("A password can't be the email address.")


def is_session_token(token: str) -> bool:
    return token.startswith(SESSION_PREFIX)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _key(kind: str, value: str) -> str:
    return _sha256(f"{kind}:{value}")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _user_agent(value: str | None) -> str | None:
    if not value:
        return None
    printable = "".join(ch for ch in value if ch.isprintable())
    return printable[:_USER_AGENT_LENGTH] or None


class LoginService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        hasher: PasswordHasher,
        *,
        session_ttl: timedelta = timedelta(days=30),
        throttle: Throttle | None = None,
        default_currency: str = "USD",
        clock: Callable[[], datetime] = _utcnow,
        keyring: Any = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._hasher = hasher
        #: Seals authenticator secrets (adapters/crypto/keyring.KeyRing).
        self._keyring = keyring
        self._session_ttl = session_ttl
        self._throttle = throttle or Throttle()
        self._default_currency = default_currency
        self._clock = clock
        self._dummy_hash: str | None = None

    # ── Accounts ────────────────────────────────────────────────────────────

    async def create_account(
        self,
        email: str,
        password: str,
        *,
        base_currency: str | None = None,
        owner: bool = False,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """A new account that can sign in: a profile (kept in `base_currency`,
        or the instance's default) and its login. `user_id` gives a profile
        that already exists a login instead. Raises LoginExists if the email
        has an account, or `owner` is asked for and there is one already."""
        address = normalize_email(email)
        check_password(password, address)
        password_hash = await self._hasher.hash(password)
        async with self._uow_factory() as uow:
            return await self._create(
                uow, address, password_hash, base_currency, owner=owner, user_id=user_id
            )

    async def _create(
        self,
        uow: Any,
        address: str,
        password_hash: str,
        base_currency: str | None,
        *,
        owner: bool = False,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        if await uow.logins.get_by_email(address) is not None:
            raise LoginExists(f"{address} already has an account here.")
        if owner and await uow.logins.owner() is not None:
            raise LoginExists("This instance already has an owner.")
        uid = user_id or str(uuid.uuid4())
        if user_id is not None and await uow.logins.get(user_id) is not None:
            raise LoginExists("That user can already sign in.")
        profile = await uow.user_profiles.get(uid)
        if profile is None:
            currency = normalize_currency(base_currency or self._default_currency)
            await uow.user_profiles.upsert(uid, {"email": address, "base_currency": currency})
        elif not profile.get("email"):
            await uow.user_profiles.upsert(uid, {"email": address})
        return await uow.logins.create(
            uid, address, password_hash, is_owner=owner, at=self._clock()
        )

    # ── Invitations ─────────────────────────────────────────────────────────

    async def invite(self, email: str, *, base_currency: str | None = None) -> str:
        """A single-use invitation for `email`, good for INVITATION_TTL: the
        token, seen this once (only its hash is kept). The owner passes the
        link on; whoever opens it sets the password. In the owner's audit log."""
        address = normalize_email(email)
        currency = normalize_currency(base_currency) if base_currency else None
        token = INVITATION_PREFIX + secrets.token_urlsafe(32)
        now = self._clock()
        async with self._uow_factory() as uow:
            if await uow.logins.get_by_email(address) is not None:
                raise LoginExists(f"{address} already has an account here.")
            owner = await uow.logins.owner()
            await uow.logins.create_invitation(
                _sha256(token), address, currency, now, now + INVITATION_TTL
            )
            if owner is not None:
                await uow.audit_log.log(
                    owner["user_id"], "member.invite", {"email": address}, "succeeded"
                )
        return token

    async def invitation(self, token: str) -> dict[str, Any] | None:
        """{email, base_currency} of a good invitation, or None."""
        async with self._uow_factory() as uow:
            return await uow.logins.get_invitation(_sha256(token), self._clock())

    async def accept_invitation(
        self, token: str, password: str, *, totp_secret: str = "", code: str = ""
    ) -> dict[str, Any]:
        """Use an invitation: the account, with two-step sign-in on if the
        person gave a code from `totp_secret`. {user_id, email,
        recovery_codes}. Raises LoginNotFound for a token not good (used,
        expired, unknown), PasswordRejected, CodeRefused."""
        found = await self.invitation(token)
        if found is None:
            raise LoginNotFound("This invitation has been used or has expired.")
        check_password(password, found["email"])
        step: int | None = None
        if code.strip():
            if not self.two_step_available or not totp_secret:
                raise TwoStepUnavailable("Two-step sign-in can't be set up on this server.")
            step = totp.matching_step(totp_secret, code.strip(), self._clock().timestamp())
            if step is None:
                raise CodeRefused()
        password_hash = await self._hasher.hash(password)
        codes: list[str] = []
        async with self._uow_factory() as uow:
            invited = await uow.logins.use_invitation(_sha256(token), self._clock())
            if invited is None:
                raise LoginNotFound("This invitation has been used or has expired.")
            login = await self._create(
                uow, invited["email"], password_hash, invited["base_currency"]
            )
            user_id = login["user_id"]
            if step is not None:
                from salli.adapters.crypto.keyring import aad_for

                sealed, version = self._keyring.seal(totp_secret, aad=aad_for(user_id, "totp"))
                await uow.logins.set_totp(user_id, sealed, version)
                codes = totp.new_recovery_codes()
                await uow.logins.enable_totp(
                    user_id, [totp.recovery_hash(c) for c in codes], step=step, at=self._clock()
                )
            await uow.audit_log.log(
                user_id, "member.join", {"two_step": step is not None}, "succeeded"
            )
        return {"user_id": user_id, "email": login["email"], "recovery_codes": codes}

    async def get_login(self, user_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            login = await uow.logins.get(user_id)
        if login is not None:
            for secret in ("password_hash", "totp_secret", "totp_key_version"):
                login.pop(secret, None)
        return login

    async def owner(self) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            return await uow.logins.owner()

    async def list_logins(self) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return await uow.logins.list()

    # ── Signing in ──────────────────────────────────────────────────────────

    async def authenticate(
        self,
        email: str,
        password: str,
        *,
        address: str | None = None,
        code: str | None = None,
    ) -> SignedIn:
        """Who these credentials belong to. Raises SignInThrottled (without
        checking the password) after too many failures, and SignInRefused
        for a wrong password and an unknown email alike. A login with
        two-step sign-in on also needs `code`: CodeNeeded without one,
        CodeRefused (counted as a failure) for a wrong or used one."""
        now = self._clock()
        tried = email.strip().lower()
        throttle = self._throttle
        keys = [(_key("account", tried), throttle.per_account)]
        if address:
            keys.append((_key("address", address), throttle.per_address))

        async with self._uow_factory() as uow:
            await uow.logins.prune_failures(now - throttle.window)
            for key, limit in keys:
                failures: list[datetime] = await uow.logins.failures_since(
                    key, now - throttle.window
                )
                if len(failures) >= limit:
                    # Allowed again once enough of them have aged out.
                    frees_at = failures[len(failures) - limit] + throttle.window
                    raise SignInThrottled(math.ceil((frees_at - now).total_seconds()))
            login: dict[str, Any] | None = await uow.logins.get_by_email(tried)

        # Made (once) before anything depends on whether the email has an
        # account, so not even the first unknown email takes longer.
        dummy = await self._dummy()
        if len(password) > MAX_PASSWORD_LENGTH:
            matched = False  # never a password anyone could have set; not hashed
        elif login is None:
            # The same work as a real check, so the time taken says nothing
            # about whether the email has an account.
            await self._hasher.verify(dummy, password)
            matched = False
        else:
            matched = await self._hasher.verify(login["password_hash"], password)

        if not matched or login is None:
            await self._failed(keys, now)
            raise SignInRefused()

        if login.get("totp_enabled_at") is not None:
            if not code or not code.strip():
                raise CodeNeeded()
            if not await self._second_step(login, code.strip()):
                await self._failed(keys, now)
                raise CodeRefused()

        rehash = (
            await self._hasher.hash(password)
            if self._hasher.needs_rehash(login["password_hash"])
            else None
        )
        async with self._uow_factory() as uow:
            await uow.logins.clear_failures(keys[0][0])
            if rehash is not None:
                await uow.logins.set_password(login["user_id"], rehash, changed_at=None)
        return SignedIn(user_id=str(login["user_id"]), email=str(login["email"]))

    async def _failed(self, keys: list[tuple[str, int]], now: datetime) -> None:
        async with self._uow_factory() as uow:
            for key, _ in keys:
                await uow.logins.record_failure(key, now)

    def _open(self, login: dict[str, Any]) -> str:
        from salli.adapters.crypto.keyring import aad_for

        if self._keyring is None:
            raise TwoStepUnavailable(
                "This server has no key to open the authenticator secret with."
            )
        return self._keyring.open(
            login["totp_secret"],
            aad=aad_for(str(login["user_id"]), "totp"),
            key_version=login["totp_key_version"],
        )

    async def _second_step(self, login: dict[str, Any], code: str) -> bool:
        """Whether `code` is the app's code now (not used before) or an
        unused recovery code, using it up either way."""
        user_id = str(login["user_id"])
        if totp.looks_like_totp(code):
            step = totp.matching_step(self._open(login), code, self._clock().timestamp())
            if step is None:
                return False
            async with self._uow_factory() as uow:
                return await uow.logins.use_totp_step(user_id, step)
        async with self._uow_factory() as uow:
            return await uow.logins.use_recovery_code(user_id, totp.recovery_hash(code))

    async def _dummy(self) -> str:
        if self._dummy_hash is None:
            self._dummy_hash = await self._hasher.hash(secrets.token_urlsafe(24))
        return self._dummy_hash

    # ── Sessions ────────────────────────────────────────────────────────────

    async def sign_in(
        self,
        email: str,
        password: str,
        *,
        address: str | None = None,
        user_agent: str | None = None,
        code: str | None = None,
    ) -> NewSession:
        """Check the credentials and start a session."""
        who = await self.authenticate(email, password, address=address, code=code)
        return await self._start(who, user_agent)

    async def _start(self, who: SignedIn, user_agent: str | None) -> NewSession:
        token = SESSION_PREFIX + secrets.token_urlsafe(32)
        now = self._clock()
        expires_at = now + self._session_ttl
        async with self._uow_factory() as uow:
            row = await uow.logins.create_session(
                who.user_id, _sha256(token), _user_agent(user_agent), now, expires_at
            )
        return NewSession(
            id=str(row["id"]),
            user_id=who.user_id,
            email=who.email,
            token=token,
            expires_at=expires_at,
        )

    async def verify_session(self, token: str) -> VerifiedSession | None:
        """Whose session this is, or None if it is unknown, ended or expired."""
        if not is_session_token(token):
            return None
        now = self._clock()
        async with self._uow_factory() as uow:
            row = await uow.logins.get_session(_sha256(token), now)
            if row is None:
                return None
            last = row["last_used_at"]
            if last is None or now - last > _TOUCH_EVERY:
                await uow.logins.touch_session(row["id"], now)
        return VerifiedSession(id=str(row["id"]), user_id=str(row["user_id"]))

    async def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return await uow.logins.list_sessions(user_id, self._clock())

    async def revoke_session(self, user_id: str, session_id: str) -> bool:
        """End one of the user's sessions. False if they have no such live one."""
        async with self._uow_factory() as uow:
            return await uow.logins.revoke_session(user_id, session_id, self._clock())

    # ── Passwords ───────────────────────────────────────────────────────────

    async def change_password(
        self,
        user_id: str,
        current: str,
        new: str,
        *,
        address: str | None = None,
        keep_session: str | None = None,
        code: str | None = None,
    ) -> int:
        """The user's own change: the current password must be right (and is
        throttled like a sign-in). Ends every other session of theirs, and
        returns how many."""
        login = await self.get_login(user_id)
        if login is None:
            raise LoginNotFound("This account has no password to change.")
        who = await self.authenticate(login["email"], current, address=address, code=code)
        if who.user_id != user_id:  # an email can't change hands, but be sure
            raise SignInRefused()
        return await self._set_password(user_id, login["email"], new, keep_session=keep_session)

    async def reset_password(
        self, email: str, new: str, *, clear_totp: bool = False
    ) -> dict[str, Any]:
        """The operator's reset (`salli-server members reset-password`): no
        current password needed. Ends every session of theirs. `clear_totp`
        also turns two-step sign-in off, for someone who has lost their
        authenticator app and their recovery codes."""
        address = normalize_email(email)
        async with self._uow_factory() as uow:
            login = await uow.logins.get_by_email(address)
        if login is None:
            raise LoginNotFound(f"No account here has the email {address}.")
        revoked = await self._set_password(login["user_id"], address, new, keep_session=None)
        cleared = clear_totp and login.get("totp_secret") is not None
        if cleared:
            async with self._uow_factory() as uow:
                await uow.logins.set_totp(login["user_id"], None, None)
        for secret in ("password_hash", "totp_secret", "totp_key_version"):
            login.pop(secret, None)
        return {**login, "sessions_ended": revoked, "totp_cleared": cleared}

    async def _set_password(
        self, user_id: str, email: str, new: str, *, keep_session: str | None
    ) -> int:
        check_password(new, email)
        password_hash = await self._hasher.hash(new)
        now = self._clock()
        async with self._uow_factory() as uow:
            await uow.logins.set_password(user_id, password_hash, changed_at=now)
            ended = await uow.logins.revoke_sessions(user_id, now, keep=keep_session)
            # A changed password starts the failure count afresh.
            await uow.logins.clear_failures(_key("account", email))
        return ended

    # ── Two-step sign-in ────────────────────────────────────────────────────

    @property
    def two_step_available(self) -> bool:
        return self._keyring is not None and bool(self._keyring.available)

    async def begin_totp(self, user_id: str) -> TwoStepEnrolment:
        """A new authenticator secret, not on until a code from it is
        confirmed (`confirm_totp`). Starting again replaces one not yet
        confirmed; one that is on must be turned off first."""
        from salli.adapters.crypto.keyring import aad_for

        if not self.two_step_available:
            raise TwoStepUnavailable(
                "Two-step sign-in needs an encryption key on this server "
                "(BYOK_ENCRYPTION_KEYS); its owner can add one."
            )
        async with self._uow_factory() as uow:
            login = await uow.logins.get(user_id)
            if login is None:
                raise LoginNotFound("This account has no password to add a second step to.")
            if login.get("totp_enabled_at") is not None:
                raise TwoStepState("Two-step sign-in is already on. Turn it off first.")
            secret = totp.new_secret()
            sealed, version = self._keyring.seal(secret, aad=aad_for(user_id, "totp"))
            await uow.logins.set_totp(user_id, sealed, version)
        return TwoStepEnrolment(secret=secret, uri=totp.provisioning_uri(secret, login["email"]))

    async def confirm_totp(self, user_id: str, code: str) -> list[str]:
        """Turn two-step sign-in on with a code from the new secret; the ten
        recovery codes, returned this once."""
        async with self._uow_factory() as uow:
            login = await uow.logins.get(user_id)
        if login is None or login.get("totp_secret") is None:
            raise TwoStepState("Start setting up two-step sign-in first.")
        if login.get("totp_enabled_at") is not None:
            raise TwoStepState("Two-step sign-in is already on.")
        step = totp.matching_step(self._open(login), code.strip(), self._clock().timestamp())
        if step is None:
            raise CodeRefused()
        codes = totp.new_recovery_codes()
        async with self._uow_factory() as uow:
            enabled = await uow.logins.enable_totp(
                user_id, [totp.recovery_hash(c) for c in codes], step=step, at=self._clock()
            )
        if not enabled:
            raise TwoStepState("Two-step sign-in is already on.")
        return codes

    async def disable_totp(
        self, user_id: str, password: str, code: str | None, *, address: str | None = None
    ) -> None:
        """Turn two-step sign-in off (or drop one being set up): the password
        and, once it is on, a code, checked like a sign-in."""
        async with self._uow_factory() as uow:
            login = await uow.logins.get(user_id)
        if login is None:
            raise LoginNotFound("This account has no password.")
        if login.get("totp_secret") is None:
            raise TwoStepState("Two-step sign-in is not on.")
        who = await self.authenticate(login["email"], password, address=address, code=code)
        if who.user_id != user_id:
            raise SignInRefused()
        async with self._uow_factory() as uow:
            await uow.logins.set_totp(user_id, None, None)

    async def sign_out_everywhere(self, user_id: str) -> dict[str, int]:
        """End every way the user is signed in: sessions, OAuth tokens (the
        CLI's sign-ins and AI connectors alike) and personal access tokens.
        For an operator who thinks an account was taken over."""
        now = self._clock()
        async with self._uow_factory() as uow:
            sessions = await uow.logins.revoke_sessions(user_id, now)
            oauth = await uow.oauth_tokens.revoke_all_for_user(user_id)
            tokens = await uow.personal_access_tokens.revoke_all(user_id)
        return {"sessions": sessions, "oauth_tokens": oauth, "personal_access_tokens": tokens}
