"""Tax residency and tax ids: what Salli accepts, and how it reads what it stored."""

from __future__ import annotations

import pytest

from salli.domain.jurisdiction import (
    COUNTRIES,
    LEGACY_TAX_ID_FIELDS,
    InvalidTaxIdError,
    TaxId,
    UnknownCountryError,
    country_name,
    is_country,
    make_tax_id,
    normalize_country,
    normalize_scheme,
    parse_tax_ids,
    stored_tax_ids,
    tax_id_value,
    with_tax_id,
)

# ── Countries ─────────────────────────────────────────────────────────────────


def test_every_assigned_iso_3166_code_is_known():
    assert len(COUNTRIES) == 249
    assert all(len(code) == 2 and code.isupper() and code.isalpha() for code in COUNTRIES)
    assert {"LK", "GB", "US", "IN", "DE", "AU"} <= set(COUNTRIES)


@pytest.mark.parametrize("given", ["LK", "lk", " Lk "])
def test_a_country_is_normalised_to_its_upper_case_code(given):
    assert normalize_country(given) == "LK"
    assert is_country(given)


@pytest.mark.parametrize("given", ["XX", "LKA", "Sri Lanka", "", "EU", None, 12])
def test_anything_else_is_not_a_country(given):
    with pytest.raises(UnknownCountryError):
        normalize_country(given)
    assert not is_country(given)


def test_a_country_has_a_name_to_show():
    assert country_name("LK") == "Sri Lanka"
    assert country_name("gb") == "United Kingdom"
    # Never fails: a code without a name is shown as itself.
    assert country_name("ZZ") == "ZZ"


# ── Tax ids ───────────────────────────────────────────────────────────────────


def test_the_legacy_fields_are_sri_lankan_schemes():
    assert LEGACY_TAX_ID_FIELDS == {"ird_number": "LK-TIN", "nic": "LK-NIC"}


@pytest.mark.parametrize(
    ("given", "expected"), [("LK-TIN", "LK-TIN"), ("lk-nic", "LK-NIC"), (" GB-UTR ", "GB-UTR")]
)
def test_a_scheme_is_a_country_a_hyphen_and_a_kind(given, expected):
    assert normalize_scheme(given) == expected


@pytest.mark.parametrize(
    "given", ["TIN", "LK_TIN", "LKA-TIN", "LK-", "-TIN", "LK-TIN!", "LK-T IN", "L1-TIN", None]
)
def test_other_schemes_are_refused(given):
    with pytest.raises(InvalidTaxIdError):
        normalize_scheme(given)


def test_a_tax_id_value_is_trimmed_and_must_be_short_and_present():
    assert make_tax_id("lk-tin", " 123456789 ") == TaxId("LK-TIN", "123456789")
    assert make_tax_id("LK-TIN", "1" * 32).value == "1" * 32
    for bad in ("", "   ", "1" * 33, None, 123456789):
        with pytest.raises(InvalidTaxIdError):
            make_tax_id("LK-TIN", bad)


def test_a_tax_id_knows_its_country():
    assert TaxId("LK-NIC", "x").country == "LK"


def test_a_list_takes_one_number_per_scheme():
    ids = parse_tax_ids([{"scheme": "LK-TIN", "value": "1"}, TaxId("LK-NIC", "2")])
    assert ids == [TaxId("LK-TIN", "1"), TaxId("LK-NIC", "2")]
    with pytest.raises(InvalidTaxIdError, match="more than once"):
        parse_tax_ids([{"scheme": "LK-TIN", "value": "1"}, {"scheme": "lk-tin", "value": "2"}])
    with pytest.raises(InvalidTaxIdError):
        parse_tax_ids(["LK-TIN=1"])


def test_stored_ids_are_read_leniently():
    """A malformed entry is left out rather than making the profile unreadable."""
    raw = [
        {"scheme": "LK-TIN", "value": "1"},
        {"scheme": "bad", "value": "2"},
        {"scheme": "LK-NIC"},
        "junk",
        {"scheme": "LK-TIN", "value": "3"},
    ]
    assert stored_tax_ids(raw) == [TaxId("LK-TIN", "1")]
    assert stored_tax_ids(None) == []
    assert stored_tax_ids({"scheme": "LK-TIN"}) == []


def test_setting_and_removing_one_scheme_leaves_the_others():
    ids = [TaxId("LK-TIN", "1"), TaxId("GB-UTR", "2")]
    assert with_tax_id(ids, "LK-TIN", "9") == [TaxId("LK-TIN", "9"), TaxId("GB-UTR", "2")]
    assert with_tax_id(ids, "lk-nic", "5") == [*ids, TaxId("LK-NIC", "5")]
    assert with_tax_id(ids, "LK-TIN", "") == [TaxId("GB-UTR", "2")]
    assert with_tax_id(ids, "LK-TIN", None) == [TaxId("GB-UTR", "2")]
    assert tax_id_value(ids, "GB-UTR") == "2"
    assert tax_id_value(ids, "LK-NIC") is None
