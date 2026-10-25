"""
The plain-text exports round-trip through the tools they are for: the
Beancount file passes `bean-check`, and the hledger journal passes
`hledger check` and reads back with every transaction. CI installs both
(and sets SALLI_REQUIRE_PLAINTEXT_TOOLS, so a missing tool fails there); a
checkout without them skips.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from salli.domain.export.plaintext import beancount, hledger
from tests.unit.domain.test_plaintext_export import ACCOUNTS, ENTRIES


def _tool(name: str) -> str:
    found = shutil.which(name) or shutil.which(name, path=str(Path(sys.executable).parent))
    if found is None:
        if os.environ.get("SALLI_REQUIRE_PLAINTEXT_TOOLS"):
            pytest.fail(f"{name} is not installed")
        pytest.skip(f"{name} is not installed")
    return found


def _run(*args: str) -> str:
    done = subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def test_bean_check_accepts_the_beancount_export(tmp_path):
    tool = _tool("bean-check")
    path = tmp_path / "ledger.beancount"
    path.write_text(beancount(ACCOUNTS, ENTRIES, "LKR"), encoding="utf-8")
    _run(tool, str(path))


def test_hledger_checks_and_reads_back_the_journal(tmp_path):
    tool = _tool("hledger")
    path = tmp_path / "ledger.journal"
    path.write_text(hledger(ACCOUNTS, ENTRIES, "LKR"), encoding="utf-8")
    _run(tool, "check", "-f", str(path))
    printed = json.loads(_run(tool, "print", "-f", str(path), "-O", "json"))
    assert len(printed) == len(ENTRIES)
