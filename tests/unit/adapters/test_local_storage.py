"""The local storage adapter writes and reads inside its root, and nowhere else."""

from __future__ import annotations

import pytest

from salli.adapters.storage.local import LocalStorageAdapter

pytestmark = pytest.mark.asyncio


async def test_a_file_is_written_under_the_users_folder_and_read_back(tmp_path):
    storage = LocalStorageAdapter(tmp_path / "storage")

    key = await storage.upload("u1", "stmt-1/october.csv", b"date,amount")

    assert key == str((tmp_path / "storage" / "u1" / "stmt-1" / "october.csv").resolve())
    assert await storage.download(key) == b"date,amount"


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

    with pytest.raises(ValueError):
        await storage.download(str(secret))
    with pytest.raises(ValueError):
        await storage.download(str(tmp_path / "storage" / ".." / "secret.txt"))
