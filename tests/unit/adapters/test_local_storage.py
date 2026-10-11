"""The local storage adapter writes and reads inside its root, and nowhere else."""

from __future__ import annotations

import pytest

from salli.adapters.storage.local import LocalStorageAdapter

pytestmark = pytest.mark.asyncio


async def test_a_file_is_written_under_the_users_folder_and_read_back(tmp_path):
    storage = LocalStorageAdapter(tmp_path / "storage")

    key = await storage.upload("u1", "stmt-1/october.csv", b"date,amount")

    assert key == "u1/stmt-1/october.csv"
    assert (tmp_path / "storage" / "u1" / "stmt-1" / "october.csv").read_bytes() == b"date,amount"
    assert await storage.download(key) == b"date,amount"


async def test_a_key_still_reads_after_the_root_moves(tmp_path):
    """Keys are relative, so a restore onto another path keeps every file."""
    key = await LocalStorageAdapter(tmp_path / "old").upload("u1", "a.csv", b"x")
    (tmp_path / "old").rename(tmp_path / "new")

    assert await LocalStorageAdapter(tmp_path / "new").download(key) == b"x"


@pytest.mark.parametrize(
    "key",
    [
        "stmt-1/../../../evil.txt",
        "../u2/stolen.csv",
        "../../evil.txt",
    ],
)
async def test_a_key_that_climbs_out_of_the_users_folder_is_refused(tmp_path, key):
    storage = LocalStorageAdapter(tmp_path / "storage")

    with pytest.raises(ValueError):
        await storage.upload("u1", key, b"x")

    assert not (tmp_path / "evil.txt").exists()
    assert not (tmp_path / "storage" / "u2").exists()


async def test_an_absolute_key_is_refused(tmp_path):
    storage = LocalStorageAdapter(tmp_path / "storage")
    target = tmp_path / "outside.txt"

    with pytest.raises(ValueError):
        await storage.upload("u1", str(target), b"x")

    assert not target.exists()


async def test_a_user_id_that_climbs_out_of_the_root_is_refused(tmp_path):
    storage = LocalStorageAdapter(tmp_path / "storage")

    with pytest.raises(ValueError):
        await storage.upload("..", "evil.txt", b"x")

    assert not (tmp_path / "evil.txt").exists()


async def test_a_path_outside_the_root_is_not_read(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"not yours")
    storage = LocalStorageAdapter(tmp_path / "storage")

    for key in (str(secret), "../secret.txt", "u1/../../secret.txt", ""):
        with pytest.raises(ValueError):
            await storage.download(key)
