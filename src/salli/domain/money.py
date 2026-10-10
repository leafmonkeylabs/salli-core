from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Self

from salli.domain.currency import exponent, format_amount, minor_factor, normalize_currency


def to_minor(amount: Decimal, currency: str) -> int:
    """
    Decimal amount → integer minor units of `currency`, rounded HALF-UP.

    Use this instead of `int(amount * 100)`, which *truncates*: `int(Decimal("1234.565")
    * 100)` silently loses a cent. And never assume 100: a yen has no minor unit and
    a Kuwaiti dinar has a thousand, so the factor comes from the currency.
    The single rounding rule for the money path.
    """
    with localcontext() as ctx:  # exact for any amount, however large
        ctx.prec = max(ctx.prec, amount.adjusted() + 6)
        return int((amount * minor_factor(currency)).to_integral_value(ROUND_HALF_UP))


def from_minor(minor_units: int, currency: str, *, strict: bool = True) -> Decimal:
    """Integer minor units → a Decimal with exactly `currency`'s decimals.

    `from_minor(123450, "USD")` is `Decimal("1234.50")`, not `1234.5`, so an amount
    always reads with the precision it is kept at. `strict=False` reads rows
    written before currency codes were validated (see `currency.exponent`).
    """
    return Decimal(minor_units).scaleb(-exponent(currency, strict=strict))


class Money:
    """
    Immutable value object: integer minor units + ISO-4217 currency code.
    Minor units are always integers — passing a float raises TypeError.
    """

    __slots__ = ("_minor", "_currency")

    def __init__(self, minor_units: int, currency: str) -> None:
        # A runtime guard for callers the type checker never sees: a float that
        # got this far must fail here, not become money.
        if not isinstance(minor_units, int):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"minor_units must be int, got {type(minor_units).__name__}")
        self._minor = minor_units
        self._currency = normalize_currency(currency)

    # ── constructors ──────────────────────────────────────────────────────────

    @classmethod
    def of(cls, amount: Decimal, currency: str) -> Self:
        """Convert a Decimal amount to `currency`'s minor units, rounding HALF-UP."""
        return cls(to_minor(amount, currency), currency)

    @classmethod
    def zero(cls, currency: str) -> Self:
        return cls(0, currency)

    # ── properties ────────────────────────────────────────────────────────────

    @property
    def minor_units(self) -> int:
        return self._minor

    @property
    def currency(self) -> str:
        return self._currency

    def to_decimal(self) -> Decimal:
        return from_minor(self._minor, self._currency)

    # ── arithmetic ────────────────────────────────────────────────────────────

    def __add__(self, other: Self) -> Self:
        self._assert_same_currency(other)
        return type(self)(self._minor + other._minor, self._currency)

    def __sub__(self, other: Self) -> Self:
        self._assert_same_currency(other)
        return type(self)(self._minor - other._minor, self._currency)

    def __neg__(self) -> Self:
        return type(self)(-self._minor, self._currency)

    def __abs__(self) -> Self:
        return type(self)(abs(self._minor), self._currency)

    # ── comparison ────────────────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._minor == other._minor and self._currency == other._currency

    def __lt__(self, other: Self) -> bool:
        self._assert_same_currency(other)
        return self._minor < other._minor

    def __le__(self, other: Self) -> bool:
        return self == other or self < other

    def __gt__(self, other: Self) -> bool:
        return not self <= other

    def __ge__(self, other: Self) -> bool:
        return not self < other

    def __hash__(self) -> int:
        return hash((self._minor, self._currency))

    # ── display ───────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"Money({self._minor}, {self._currency!r})"

    def __str__(self) -> str:
        return format_amount(self.to_decimal(), self._currency)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _assert_same_currency(self, other: Self) -> None:
        if self._currency != other._currency:
            raise ValueError(f"Currency mismatch: {self._currency} vs {other._currency}")
