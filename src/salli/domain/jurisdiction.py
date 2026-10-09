"""
Where a user is taxed, and the numbers their tax authorities know them by.

Pure domain: no I/O.

- A **tax residency** is an ISO 3166-1 alpha-2 country code ("LK", "GB"), or
  None while the user has not said. It decides which tax packs apply to them
  (domain/tax/packs). Nothing assumes a country when it is None.
- A **tax id** is a scheme and a value. The scheme names the country and the
  kind of number: "LK-TIN" is a Sri Lankan taxpayer identification number,
  "LK-NIC" a Sri Lankan national identity card number. A list of them replaces
  the profile's two Sri Lankan fields, `ird_number` and `nic`, which live on as
  those two schemes (`LEGACY_TAX_ID_FIELDS`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, cast

#: Every officially assigned ISO 3166-1 alpha-2 code, with a short English name
#: for display and for the agents' prompts. Names are never stored.
COUNTRIES: dict[str, str] = {
    "AD": "Andorra",
    "AE": "United Arab Emirates",
    "AF": "Afghanistan",
    "AG": "Antigua and Barbuda",
    "AI": "Anguilla",
    "AL": "Albania",
    "AM": "Armenia",
    "AO": "Angola",
    "AQ": "Antarctica",
    "AR": "Argentina",
    "AS": "American Samoa",
    "AT": "Austria",
    "AU": "Australia",
    "AW": "Aruba",
    "AX": "Åland Islands",
    "AZ": "Azerbaijan",
    "BA": "Bosnia and Herzegovina",
    "BB": "Barbados",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BF": "Burkina Faso",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BI": "Burundi",
    "BJ": "Benin",
    "BL": "Saint Barthélemy",
    "BM": "Bermuda",
    "BN": "Brunei",
    "BO": "Bolivia",
    "BQ": "Caribbean Netherlands",
    "BR": "Brazil",
    "BS": "Bahamas",
    "BT": "Bhutan",
    "BV": "Bouvet Island",
    "BW": "Botswana",
    "BY": "Belarus",
    "BZ": "Belize",
    "CA": "Canada",
    "CC": "Cocos (Keeling) Islands",
    "CD": "Democratic Republic of the Congo",
    "CF": "Central African Republic",
    "CG": "Republic of the Congo",
    "CH": "Switzerland",
    "CI": "Côte d'Ivoire",
    "CK": "Cook Islands",
    "CL": "Chile",
    "CM": "Cameroon",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CU": "Cuba",
    "CV": "Cabo Verde",
    "CW": "Curaçao",
    "CX": "Christmas Island",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DJ": "Djibouti",
    "DK": "Denmark",
    "DM": "Dominica",
    "DO": "Dominican Republic",
    "DZ": "Algeria",
    "EC": "Ecuador",
    "EE": "Estonia",
    "EG": "Egypt",
    "EH": "Western Sahara",
    "ER": "Eritrea",
    "ES": "Spain",
    "ET": "Ethiopia",
    "FI": "Finland",
    "FJ": "Fiji",
    "FK": "Falkland Islands",
    "FM": "Micronesia",
    "FO": "Faroe Islands",
    "FR": "France",
    "GA": "Gabon",
    "GB": "United Kingdom",
    "GD": "Grenada",
    "GE": "Georgia",
    "GF": "French Guiana",
    "GG": "Guernsey",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GL": "Greenland",
    "GM": "Gambia",
    "GN": "Guinea",
    "GP": "Guadeloupe",
    "GQ": "Equatorial Guinea",
    "GR": "Greece",
    "GS": "South Georgia and the South Sandwich Islands",
    "GT": "Guatemala",
    "GU": "Guam",
    "GW": "Guinea-Bissau",
    "GY": "Guyana",
    "HK": "Hong Kong",
    "HM": "Heard Island and McDonald Islands",
    "HN": "Honduras",
    "HR": "Croatia",
    "HT": "Haiti",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IM": "Isle of Man",
    "IN": "India",
    "IO": "British Indian Ocean Territory",
    "IQ": "Iraq",
    "IR": "Iran",
    "IS": "Iceland",
    "IT": "Italy",
    "JE": "Jersey",
    "JM": "Jamaica",
    "JO": "Jordan",
    "JP": "Japan",
    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KH": "Cambodia",
    "KI": "Kiribati",
    "KM": "Comoros",
    "KN": "Saint Kitts and Nevis",
    "KP": "North Korea",
    "KR": "South Korea",
    "KW": "Kuwait",
    "KY": "Cayman Islands",
    "KZ": "Kazakhstan",
    "LA": "Laos",
    "LB": "Lebanon",
    "LC": "Saint Lucia",
    "LI": "Liechtenstein",
    "LK": "Sri Lanka",
    "LR": "Liberia",
    "LS": "Lesotho",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "LY": "Libya",
    "MA": "Morocco",
    "MC": "Monaco",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MF": "Saint Martin",
    "MG": "Madagascar",
    "MH": "Marshall Islands",
    "MK": "North Macedonia",
    "ML": "Mali",
    "MM": "Myanmar",
    "MN": "Mongolia",
    "MO": "Macao",
    "MP": "Northern Mariana Islands",
    "MQ": "Martinique",
    "MR": "Mauritania",
    "MS": "Montserrat",
    "MT": "Malta",
    "MU": "Mauritius",
    "MV": "Maldives",
    "MW": "Malawi",
    "MX": "Mexico",
    "MY": "Malaysia",
    "MZ": "Mozambique",
    "NA": "Namibia",
    "NC": "New Caledonia",
    "NE": "Niger",
    "NF": "Norfolk Island",
    "NG": "Nigeria",
    "NI": "Nicaragua",
    "NL": "Netherlands",
    "NO": "Norway",
    "NP": "Nepal",
    "NR": "Nauru",
    "NU": "Niue",
    "NZ": "New Zealand",
    "OM": "Oman",
    "PA": "Panama",
    "PE": "Peru",
    "PF": "French Polynesia",
    "PG": "Papua New Guinea",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PM": "Saint Pierre and Miquelon",
    "PN": "Pitcairn Islands",
    "PR": "Puerto Rico",
    "PS": "Palestine",
    "PT": "Portugal",
    "PW": "Palau",
    "PY": "Paraguay",
    "QA": "Qatar",
    "RE": "Réunion",
    "RO": "Romania",
    "RS": "Serbia",
    "RU": "Russia",
    "RW": "Rwanda",
    "SA": "Saudi Arabia",
    "SB": "Solomon Islands",
    "SC": "Seychelles",
    "SD": "Sudan",
    "SE": "Sweden",
    "SG": "Singapore",
    "SH": "Saint Helena, Ascension and Tristan da Cunha",
    "SI": "Slovenia",
    "SJ": "Svalbard and Jan Mayen",
    "SK": "Slovakia",
    "SL": "Sierra Leone",
    "SM": "San Marino",
    "SN": "Senegal",
    "SO": "Somalia",
    "SR": "Suriname",
    "SS": "South Sudan",
    "ST": "São Tomé and Príncipe",
    "SV": "El Salvador",
    "SX": "Sint Maarten",
    "SY": "Syria",
    "SZ": "Eswatini",
    "TC": "Turks and Caicos Islands",
    "TD": "Chad",
    "TF": "French Southern Territories",
    "TG": "Togo",
    "TH": "Thailand",
    "TJ": "Tajikistan",
    "TK": "Tokelau",
    "TL": "Timor-Leste",
    "TM": "Turkmenistan",
    "TN": "Tunisia",
    "TO": "Tonga",
    "TR": "Türkiye",
    "TT": "Trinidad and Tobago",
    "TV": "Tuvalu",
    "TW": "Taiwan",
    "TZ": "Tanzania",
    "UA": "Ukraine",
    "UG": "Uganda",
    "UM": "United States Minor Outlying Islands",
    "US": "United States",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VA": "Vatican City",
    "VC": "Saint Vincent and the Grenadines",
    "VE": "Venezuela",
    "VG": "British Virgin Islands",
    "VI": "United States Virgin Islands",
    "VN": "Vietnam",
    "VU": "Vanuatu",
    "WF": "Wallis and Futuna",
    "WS": "Samoa",
    "YE": "Yemen",
    "YT": "Mayotte",
    "ZA": "South Africa",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}


class UnknownCountryError(ValueError):
    """A code that is not an assigned ISO 3166-1 alpha-2 country code."""


class InvalidTaxIdError(ValueError):
    """A tax id whose scheme or value Salli cannot keep."""


def is_country(code: object) -> bool:
    return isinstance(code, str) and code.strip().upper() in COUNTRIES


def normalize_country(code: object) -> str:
    """The upper-case ISO 3166-1 alpha-2 code, or `UnknownCountryError`.

    Use it wherever a country enters Salli: an API body, a CLI flag.
    """
    if not isinstance(code, str):
        raise UnknownCountryError(f"A country must be an ISO 3166-1 alpha-2 code, got {code!r}")
    normalized = code.strip().upper()
    if normalized not in COUNTRIES:
        raise UnknownCountryError(f"{code!r} is not an ISO 3166-1 alpha-2 country code")
    return normalized


def country_name(code: str) -> str:
    """ "Sri Lanka" for "LK"; the code itself for one Salli has no name for."""
    return COUNTRIES.get(code.upper(), code.upper())


# ── Tax ids ──────────────────────────────────────────────────────────────────

#: "<country>-<kind>": two capital letters, a hyphen, then capitals and digits.
SCHEME_PATTERN = re.compile(r"^[A-Z]{2}-[A-Z0-9]+$")

#: Tax numbers are short (Sri Lanka's TIN has 9 digits, its NIC 10 or 12
#: characters); this is also the width of the legacy `ird_number` column, so a
#: Sri Lankan TIN always fits in both places.
MAX_TAX_ID_LENGTH = 32

LK_TIN = "LK-TIN"
LK_NIC = "LK-NIC"

#: The profile fields that predate tax ids, and the scheme each one now is. The
#: web and mobile apps still read and write them, so the API keeps serving them,
#: derived from the tax ids.
LEGACY_TAX_ID_FIELDS: dict[str, str] = {"ird_number": LK_TIN, "nic": LK_NIC}


@dataclass(frozen=True)
class TaxId:
    scheme: str
    value: str

    @property
    def country(self) -> str:
        """The country whose scheme this is: "LK" for "LK-TIN"."""
        return self.scheme[:2]

    def as_dict(self) -> dict[str, str]:
        return {"scheme": self.scheme, "value": self.value}


def normalize_scheme(scheme: object) -> str:
    """The scheme upper-cased, or `InvalidTaxIdError` if it is not "XX-KIND"."""
    if not isinstance(scheme, str):
        raise InvalidTaxIdError(f"A tax id scheme must be a string, got {scheme!r}")
    normalized = scheme.strip().upper()
    if not SCHEME_PATTERN.fullmatch(normalized):
        raise InvalidTaxIdError(
            f"{scheme!r} is not a tax id scheme: a country code, a hyphen and a name "
            "in capitals or digits, like LK-TIN"
        )
    return normalized


def make_tax_id(scheme: object, value: object) -> TaxId:
    """A validated tax id: a known scheme shape and a short, non-empty value."""
    normalized = normalize_scheme(scheme)
    if not isinstance(value, str) or not value.strip():
        raise InvalidTaxIdError(f"The {normalized} number is empty")
    cleaned = value.strip()
    if len(cleaned) > MAX_TAX_ID_LENGTH:
        raise InvalidTaxIdError(
            f"The {normalized} number is longer than {MAX_TAX_ID_LENGTH} characters"
        )
    return TaxId(normalized, cleaned)


def _parts(item: object) -> tuple[object, object]:
    if isinstance(item, TaxId):
        return item.scheme, item.value
    if isinstance(item, Mapping):
        entry = cast("Mapping[str, object]", item)
        return entry.get("scheme"), entry.get("value")
    raise InvalidTaxIdError(f"A tax id is a scheme and a value, got {item!r}")


def parse_tax_ids(items: Iterable[object]) -> list[TaxId]:
    """Validate a list of tax ids as a user gave it. One number per scheme:
    a scheme given twice is refused rather than one of them silently kept."""
    parsed: list[TaxId] = []
    seen: set[str] = set()
    for item in items:
        tax_id = make_tax_id(*_parts(item))
        if tax_id.scheme in seen:
            raise InvalidTaxIdError(f"{tax_id.scheme} is given more than once")
        seen.add(tax_id.scheme)
        parsed.append(tax_id)
    return parsed


def stored_tax_ids(raw: object) -> list[TaxId]:
    """Tax ids as stored. Read leniently: an entry that does not parse is left
    out rather than making the whole profile unreadable."""
    if not isinstance(raw, list):
        return []
    found: list[TaxId] = []
    seen: set[str] = set()
    for item in cast("list[Any]", raw):
        try:
            tax_id = make_tax_id(*_parts(item))
        except InvalidTaxIdError:
            continue
        if tax_id.scheme not in seen:
            seen.add(tax_id.scheme)
            found.append(tax_id)
    return found


def tax_id_value(ids: Iterable[TaxId], scheme: str) -> str | None:
    """The number under `scheme`, or None."""
    return next((t.value for t in ids if t.scheme == scheme), None)


def with_tax_id(ids: Iterable[TaxId], scheme: str, value: str | None) -> list[TaxId]:
    """`ids` with `scheme` set to `value`, in place if it was there and last if
    not; or with `scheme` removed when `value` is None or blank."""
    scheme = normalize_scheme(scheme)
    current = list(ids)
    if value is None or not value.strip():
        return [t for t in current if t.scheme != scheme]
    new = make_tax_id(scheme, value)
    if any(t.scheme == scheme for t in current):
        return [new if t.scheme == scheme else t for t in current]
    return [*current, new]
