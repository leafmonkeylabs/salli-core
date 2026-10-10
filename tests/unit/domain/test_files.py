"""A client's filename, made safe to put in a storage key."""

from __future__ import annotations

import pytest

from salli.domain.files import MAX_FILENAME_BYTES, safe_filename


@pytest.mark.parametrize(
    ("name", "safe"),
    [
        ("../../evil.txt", "evil.txt"),
        ("/etc/passwd", "passwd"),
        ("a\\..\\b", "b"),
        ("C:\\Users\\me\\statement.pdf", "statement.pdf"),
        ("folder/october.csv", "october.csv"),
        ("..", "fallback"),
        ("../..", "fallback"),
        ("/", "fallback"),
        ("", "fallback"),
        (None, "fallback"),
        ("   ", "fallback"),
        (".hidden", "hidden"),
        ("...env", "env"),
        ("october.csv", "october.csv"),
        ("ඔක්තෝබර් ප්‍රකාශය.pdf", "ඔක්තෝබර් ප්‍රකාශය.pdf"),
        ("relevé été.csv", "relevé été.csv"),
        ("bad\x00name\n.csv", "badname.csv"),
        ("fdp\u202eexe.pdf", "fdpexe.pdf"),
        ("%2e%2e%2fother-user%2fx.csv", "_2e_2e_2fother-user_2fx.csv"),
        ("what?#.csv", "what__.csv"),
    ],
)
def test_only_the_last_plain_component_of_a_name_is_kept(name, safe):
    assert safe_filename(name, "fallback") == safe


def test_a_long_name_is_cut_and_keeps_its_extension():
    safe = safe_filename("x" * 400 + ".pdf", "fallback")

    assert safe.endswith(".pdf")
    assert len(safe.encode()) == MAX_FILENAME_BYTES


def test_a_long_name_in_sinhala_is_cut_on_whole_characters():
    # Three bytes a character: a cut on characters alone would leave 450 bytes.
    safe = safe_filename("ප" * 200 + ".csv", "fallback")

    assert safe.endswith(".csv")
    assert len(safe.encode()) <= MAX_FILENAME_BYTES
    assert set(safe.removesuffix(".csv")) == {"ප"}


def test_a_long_name_without_an_extension_is_just_cut():
    assert safe_filename("y" * 400, "fallback") == "y" * MAX_FILENAME_BYTES
