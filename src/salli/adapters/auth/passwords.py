"""
Argon2id password hashing (RFC 9106), through argon2-cffi.

The parameters are RFC 9106's second recommended option, which is also
argon2-cffi's default: 64 MiB of memory, three passes, four lanes, a 16-byte
salt and a 32-byte hash, taking tens of milliseconds on a server. Each hash
records its own parameters, so a hash made with older ones still verifies,
and `needs_rehash` says when to make it again at the next sign-in.

Hashing is deliberately slow and memory-hungry, so it runs in a worker thread
(never on the event loop), and at most `concurrency` at once: a burst of
sign-in attempts queues instead of taking 64 MiB each.
"""

from __future__ import annotations

import asyncio
import threading

from argon2 import PasswordHasher as Argon2Hasher
from argon2 import Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from salli.application.ports import PasswordHasher

#: RFC 9106 §4, second recommended option ("low memory").
TIME_COST = 3
MEMORY_COST_KIB = 64 * 1024
PARALLELISM = 4
HASH_LEN = 32
SALT_LEN = 16


class Argon2PasswordHasher(PasswordHasher):
    def __init__(
        self,
        *,
        time_cost: int = TIME_COST,
        memory_cost: int = MEMORY_COST_KIB,
        parallelism: int = PARALLELISM,
        concurrency: int = 4,
    ) -> None:
        self._hasher = Argon2Hasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=HASH_LEN,
            salt_len=SALT_LEN,
            type=Type.ID,
        )
        # A thread semaphore, taken in the worker thread: unlike an asyncio
        # one it is bound to no event loop, so the same hasher serves the
        # server's loop and each of a CLI command's.
        self._slots = threading.BoundedSemaphore(concurrency)

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._hash, password)

    async def verify(self, password_hash: str, password: str) -> bool:
        return await asyncio.to_thread(self._verify, password_hash, password)

    def _hash(self, password: str) -> str:
        with self._slots:
            return self._hasher.hash(password)

    def _verify(self, password_hash: str, password: str) -> bool:
        with self._slots:
            try:
                return self._hasher.verify(password_hash, password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False

    def needs_rehash(self, password_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True
