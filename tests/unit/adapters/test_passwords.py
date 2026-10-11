"""Argon2id password hashing: what is stored, what verifies, and when a
stored hash is made again."""

from __future__ import annotations

import asyncio

import pytest

from salli.adapters.auth.passwords import Argon2PasswordHasher

pytestmark = pytest.mark.asyncio

# Cheap parameters for speed; the parameters themselves are tested below.
FAST = {"time_cost": 1, "memory_cost": 1024, "parallelism": 1}


async def test_the_default_is_argon2id_with_rfc_9106_s_low_memory_parameters():
    stored = await Argon2PasswordHasher().hash("correct horse battery staple")
    assert stored.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert "correct horse" not in stored


async def test_only_the_password_verifies():
    hasher = Argon2PasswordHasher(**FAST)
    stored = await hasher.hash("correct horse battery staple")
    assert await hasher.verify(stored, "correct horse battery staple")
    for wrong in ("correct horse battery stapl", "Correct horse battery staple", "", " " * 30):
        assert not await hasher.verify(stored, wrong)


async def test_the_same_password_hashes_differently_each_time():
    hasher = Argon2PasswordHasher(**FAST)
    first, second = await hasher.hash("same password!"), await hasher.hash("same password!")
    assert first != second
    assert await hasher.verify(first, "same password!") and await hasher.verify(
        second, "same password!"
    )


@pytest.mark.parametrize("garbage", ["", "plaintext", "$argon2id$v=19$m=1,t=1,p=1$bad", "$2b$12$x"])
async def test_a_hash_it_cannot_read_never_verifies_and_never_raises(garbage):
    hasher = Argon2PasswordHasher(**FAST)
    assert not await hasher.verify(garbage, "anything")
    assert hasher.needs_rehash(garbage)


async def test_a_hash_made_with_other_parameters_verifies_and_asks_to_be_made_again():
    old = Argon2PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    new = Argon2PasswordHasher(time_cost=2, memory_cost=2048, parallelism=1)
    stored = await old.hash("a long enough password")
    assert await new.verify(stored, "a long enough password")
    assert new.needs_rehash(stored)
    assert not new.needs_rehash(await new.hash("a long enough password"))


async def test_hashing_runs_off_the_event_loop():
    hasher = Argon2PasswordHasher(time_cost=2, memory_cost=8192, parallelism=1)
    ticks = 0

    async def tick() -> None:
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0)

    ticker = asyncio.create_task(tick())
    await asyncio.gather(*(hasher.hash(f"password {i}") for i in range(4)))
    ticker.cancel()
    # The loop kept turning while the hashes ran in worker threads.
    assert ticks > 4
