"""Tax residency and tax ids: what Salli accepts, and how it reads what it stored."""

from __future__ import annotations

import pytest

from salli.domain.jurisdiction import (
    COUNTRIES,
    InvalidTaxIdError,
    TaxId,
    UnknownCountryError,
    country_name,
    country_phrase,
    is_country,
    make_tax_id,
    normalize_country,
    normalize_scheme,
    parse_tax_ids,
    stored_tax_ids,
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


def test_salli_knows_no_country_s_schemes():
    """Tax ids are generic: no constants, no legacy fields, for any country."""
    import salli.domain.jurisdiction as jurisdiction

    assert not [name for name in vars(jurisdiction) if name.startswith(("LK_", "LEGACY_"))]


@pytest.mark.parametrize(
    ("given", "expected"), [("KE-PIN", "KE-PIN"), ("br-cpf", "BR-CPF"), (" GB-UTR ", "GB-UTR")]
)
def test_a_scheme_is_a_country_a_hyphen_and_a_kind(given, expected):
    assert normalize_scheme(given) == expected


@pytest.mark.parametrize(
    "given", ["TIN", "XX_TIN", "XXX-TIN", "XX-", "-TIN", "XX-TIN!", "XX-T IN", "X1-TIN", None]
)
def test_other_schemes_are_refused(given):
    with pytest.raises(InvalidTaxIdError):
        normalize_scheme(given)


def test_a_tax_id_value_is_trimmed_and_must_be_short_and_present():
    assert make_tax_id("ke-pin", " A00123 ") == TaxId("KE-PIN", "A00123")
    assert make_tax_id("KE-PIN", "1" * 32).value == "1" * 32
    for bad in ("", "   ", "1" * 33, None, 123456789):
        with pytest.raises(InvalidTaxIdError):
            make_tax_id("KE-PIN", bad)


def test_a_tax_id_knows_its_country():
    assert TaxId("BR-CPF", "x").country == "BR"


def test_a_list_takes_one_number_per_scheme():
    ids = parse_tax_ids([{"scheme": "MX-RFC", "value": "1"}, TaxId("MX-CURP", "2")])
    assert ids == [TaxId("MX-RFC", "1"), TaxId("MX-CURP", "2")]
    with pytest.raises(InvalidTaxIdError, match="more than once"):
        parse_tax_ids([{"scheme": "MX-RFC", "value": "1"}, {"scheme": "mx-rfc", "value": "2"}])
    with pytest.raises(InvalidTaxIdError):
        parse_tax_ids(["MX-RFC=1"])


def test_stored_ids_are_read_leniently():
    """A malformed entry is left out rather than making the profile unreadable."""
    raw = [
        {"scheme": "DE-IDNR", "value": "1"},
        {"scheme": "bad", "value": "2"},
        {"scheme": "DE-STNR"},
        "junk",
        {"scheme": "DE-IDNR", "value": "3"},
    ]
    assert stored_tax_ids(raw) == [TaxId("DE-IDNR", "1")]
    assert stored_tax_ids(None) == []
    assert stored_tax_ids({"scheme": "DE-IDNR"}) == []


def test_a_country_reads_naturally_in_a_sentence():
    assert country_phrase("LK") == "Sri Lanka"
    assert country_phrase("US") == "the United States"
    assert country_phrase("GB") == "the United Kingdom"
    assert country_phrase("PH") == "the Philippines"
    assert country_phrase("KY") == "the Cayman Islands"
    assert country_phrase("DE") == "Germany"
