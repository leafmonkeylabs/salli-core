"""
Currencies: ISO 4217 codes and how many decimal places each one has.

The number of decimals (the "minor unit exponent") is what turns an amount into
the integer minor units the database stores. It is not always two: a yen has
no subdivision, a Kuwaiti dinar has three. Treating every currency as having
cents stores ¥1,000 as 100,000 "minor units" and reads 1.234 KWD back as
1.23, so the exponent comes from this table and nowhere else.

Codes that ISO has withdrawn but that people still have years of records in
(the Croatian kuna, the Bulgarian lev, …) stay accepted, so history imported
from an old statement still reads correctly.

Precious metals, testing codes and other units with no minor unit (XAU, XDR,
XTS, XXX, …) are deliberately absent: they are not money a ledger posts. Crypto
assets are not here either; they are holdings with a quantity, not a currency
of account.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext

_ZERO_DECIMALS = [
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "ISK",
    "JPY",
    "KMF",
    "KRW",
    "PYG",
    "RWF",
    "UGX",
    "UYI",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
]

_THREE_DECIMALS = ["BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"]

_FOUR_DECIMALS = ["CLF", "UYW"]

_TWO_DECIMALS = [
    "AED",
    "AFN",
    "ALL",
    "AMD",
    "AOA",
    "ARS",
    "AUD",
    "AWG",
    "AZN",
    "BAM",
    "BBD",
    "BDT",
    "BMD",
    "BND",
    "BOB",
    "BOV",
    "BRL",
    "BSD",
    "BTN",
    "BWP",
    "BYN",
    "BZD",
    "CAD",
    "CDF",
    "CHE",
    "CHF",
    "CHW",
    "CNY",
    "COP",
    "COU",
    "CRC",
    "CUP",
    "CVE",
    "CZK",
    "DKK",
    "DOP",
    "DZD",
    "EGP",
    "ERN",
    "ETB",
    "EUR",
    "FJD",
    "FKP",
    "GBP",
    "GEL",
    "GHS",
    "GIP",
    "GMD",
    "GTQ",
    "GYD",
    "HKD",
    "HNL",
    "HTG",
    "HUF",
    "IDR",
    "ILS",
    "INR",
    "IRR",
    "JMD",
    "KES",
    "KGS",
    "KHR",
    "KPW",
    "KYD",
    "KZT",
    "LAK",
    "LBP",
    "LKR",
    "LRD",
    "LSL",
    "MAD",
    "MDL",
    "MGA",
    "MKD",
    "MMK",
    "MNT",
    "MOP",
    "MRU",
    "MUR",
    "MVR",
    "MWK",
    "MXN",
    "MXV",
    "MYR",
    "MZN",
    "NAD",
    "NGN",
    "NIO",
    "NOK",
    "NPR",
    "NZD",
    "PAB",
    "PEN",
    "PGK",
    "PHP",
    "PKR",
    "PLN",
    "QAR",
    "RON",
    "RSD",
    "RUB",
    "SAR",
    "SBD",
    "SCR",
    "SDG",
    "SEK",
    "SGD",
    "SHP",
    "SLE",
    "SOS",
    "SRD",
    "SSP",
    "STN",
    "SVC",
    "SYP",
    "SZL",
    "THB",
    "TJS",
    "TMT",
    "TOP",
    "TRY",
    "TTD",
    "TWD",
    "TZS",
    "UAH",
    "USD",
    "USN",
    "UYU",
    "UZS",
    "VED",
    "VES",
    "WST",
    "XCD",
    "XCG",
    "YER",
    "ZAR",
    "ZMW",
    "ZWG",
]

# Withdrawn by ISO, still found in people's records.
_HISTORIC_TWO_DECIMALS = ["ANG", "BGN", "CUC", "HRK", "SLL", "ZWL"]

EXPONENTS: dict[str, int] = {
    **dict.fromkeys(_TWO_DECIMALS, 2),
    **dict.fromkeys(_HISTORIC_TWO_DECIMALS, 2),
    **dict.fromkeys(_ZERO_DECIMALS, 0),
    **dict.fromkeys(_THREE_DECIMALS, 3),
    **dict.fromkeys(_FOUR_DECIMALS, 4),
}


class UnknownCurrencyError(ValueError):
    """A code that is not an ISO 4217 currency Salli can keep accounts in."""


def is_currency(code: object) -> bool:
    return isinstance(code, str) and code.upper() in EXPONENTS


def normalize_currency(code: object) -> str:
    """The upper-case ISO code, or `UnknownCurrencyError`.

    Use it wherever a currency enters Salli: an API body, a CLI flag, a parsed
    statement, a model's draft. Past that point every code is known to be valid.
    """
    if not isinstance(code, str):
        raise UnknownCurrencyError(f"Currency must be an ISO 4217 code, got {code!r}")
    normalized = code.strip().upper()
    if normalized not in EXPONENTS:
        raise UnknownCurrencyError(f"{code!r} is not an ISO 4217 currency code")
    return normalized


def exponent(code: str, *, strict: bool = True) -> int:
    """Decimal places of `code`: 2 for USD, 0 for JPY, 3 for KWD.

    `strict=False` is for reading rows written before codes were validated: an
    unrecognised code is read as two decimals, which is what everything was
    written with then, rather than making the whole ledger unreadable.
    """
    try:
        return EXPONENTS[code.upper()]
    except KeyError:
        if strict:
            raise UnknownCurrencyError(f"{code!r} is not an ISO 4217 currency code") from None
        return 2


def minor_factor(code: str, *, strict: bool = True) -> int:
    """How many minor units make one major unit: 100 for USD, 1 for JPY."""
    return 10 ** exponent(code, strict=strict)


def quantum(code: str, *, strict: bool = True) -> Decimal:
    """The smallest amount `code` can express: 0.01 for USD, 1 for JPY."""
    return Decimal(1).scaleb(-exponent(code, strict=strict))


def quantize(amount: Decimal, code: str, *, strict: bool = True) -> Decimal:
    """`amount` rounded HALF-UP to the decimals `code` has.

    With enough precision for any amount: the default context's 28 digits
    made quantize raise InvalidOperation past 26 integer digits."""
    with localcontext() as ctx:
        ctx.prec = max(ctx.prec, amount.adjusted() + exponent(code, strict=strict) + 2)
        return amount.quantize(quantum(code, strict=strict), rounding=ROUND_HALF_UP)


def format_amount(amount: Decimal, code: str, *, strict: bool = True) -> str:
    """`1,234.50 USD`: grouped with commas, with exactly the decimals the
    currency has, and the ISO code rather than a symbol (`$` alone could be a
    dozen currencies). For display only; never parse it back.
    """
    places = exponent(code, strict=strict)
    return f"{quantize(amount, code, strict=strict):,.{places}f} {code.upper()}"
