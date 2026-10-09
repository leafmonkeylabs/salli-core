from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from salli.domain.currency import quantize


class Direction(int, Enum):
    DEBIT = 1
    CREDIT = -1


AccountType = Literal["asset", "liability", "equity", "income", "expense"]

Source = Literal["manual", "statement", "sms", "system"]

# What an account means to the tax engine, declared explicitly rather than
# guessed from its name.
#
# This replaces substring matching on `Account.name` ("apit" in name.lower(),
# "qualifying" or "donation", code.startswith("FSI")), which was wrong in two
# directions at once: it silently missed the accounts onboarding actually seeds
# — "APIT Receivable" is an *asset*, while the old mapping only inspected
# liabilities, so every onboarded user's withheld tax was ignored and their tax
# payable overstated by that amount — and it could fire on unrelated accounts
# that merely contained the letters (a liability named "Waiting Clearing"
# counted as AIT withheld).
#
# `AccountType` stays the accounting classification; `TaxRole` is the tax
# treatment. They answer different questions and an account needs both.
TaxRole = Literal[
    "apit_credit",
    "ait_credit",
    "foreign_tax_credit",
    "qualifying_payment",
    "fsi_income",
]


def _currency_code(value: object) -> str:
    """Shape check only — three letters, upper-cased. Whether the code is a real
    ISO 4217 currency is checked where a currency enters Salli
    (`currency.normalize_currency`), so a row stored before that check existed
    still loads."""
    if not isinstance(value, str) or len(value.strip()) != 3 or not value.strip().isalpha():
        raise ValueError(f"{value!r} is not a currency code")
    return value.strip().upper()


class Account(BaseModel):
    id: str
    user_id: str
    code: str
    name: str
    type: AccountType
    # The currency the account is held in: a USD bank account's balance is in
    # dollars, whatever the owner's base currency is.
    currency: str
    parent_id: str | None = None
    is_active: bool = True
    tax_role: TaxRole | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def _code(cls, v: object) -> str:
        return _currency_code(v)


#: Accounts that hold money (a bank, cash) or owe it (a card, a loan): what a
#: statement or a bank feed can be for.
MONEY_TYPES: tuple[AccountType, ...] = ("asset", "liability")


def money_account_problem(account: Account | None, ref: str) -> str | None:
    """Why `account` (looked up by `ref`) can't take a statement's or a bank
    feed's transactions, or None when it can: it must be active, and an
    asset or liability account."""
    if account is None or not account.is_active:
        return f"No active account {ref!r}"
    if account.type not in MONEY_TYPES:
        return (
            f"{account.name} is an {account.type} account. A statement is for an asset "
            "or liability account: a bank, cash or card account."
        )
    return None


# The axis a tag belongs to. One tag per axis per posting, so a spending
# breakdown along any single axis sums to the total without double counting.
#
# `category` is what the money was for (groceries, rent, transport).
# `need` is how necessary it was — the 50/30/20 split.
#
# This is a second classification dimension, orthogonal to the chart of
# accounts. The account tree answers "which ledger account did this hit"; it
# cannot also answer "was this essential" without duplicating the whole tree
# under each answer.
TagKind = Literal["category", "need"]


class Tag(BaseModel):
    id: str
    user_id: str
    slug: str
    name: str
    kind: TagKind
    color: str = ""
    # Seeded tags the product relies on (the `need` axis). Users can rename
    # these but not delete them, since reports reference them by slug.
    is_system: bool = False


class Posting(BaseModel):
    # Set when read back from storage, None on the write path — the same
    # split `StoredJournalEntry` makes for entries. Needed because tags are
    # edited per posting, so a client has to be able to name one.
    id: str | None = None
    account_id: str
    direction: Direction
    amount: Decimal = Field(gt=Decimal(0))
    currency: str
    fx_rate: Decimal = Decimal(1)
    fx_rate_source: str | None = None
    # Axis → tag slug, e.g. {"category": "groceries", "need": "essential"}.
    #
    # A mapping rather than a list because a posting carries at most one tag per
    # axis — expressing that in the type means a breakdown along any axis sums
    # to the total without double counting, and it tells the repository which
    # axis a slug belongs to instead of making it guess.
    #
    # Slugs rather than ids so the domain and the API can talk about tags
    # without knowing their storage identity. Tags are metadata *about* an
    # immutable posting, not part of it: the money record never changes, but a
    # miscategorised expense has to be fixable, so tags live in their own table
    # and stay editable after the fact.
    tags: dict[str, str] = Field(default_factory=dict)

    @field_validator("amount", mode="before")
    @classmethod
    def no_float(cls, v: object) -> object:
        if isinstance(v, float):
            raise ValueError("Use Decimal, never float for monetary amounts")
        return v

    @field_validator("currency", mode="before")
    @classmethod
    def _code(cls, v: object) -> str:
        return _currency_code(v)

    @model_validator(mode="after")
    def _to_currency_precision(self) -> Posting:
        """Round the amount to the decimals its currency has (HALF-UP).

        What is stored is the amount in the currency's minor units, so this is
        the amount the ledger will hold. Rounding here rather than at storage
        means the entry's balance check sees exactly that: an entry that only
        balanced on a fraction of a cent fails now, with a clear error, instead
        of at commit in the database trigger.
        """
        rounded = quantize(self.amount, self.currency, strict=False)
        if rounded == 0:
            raise ValueError(f"{self.amount} {self.currency} is less than the smallest unit")
        self.amount = rounded
        return self

    @property
    def base_signed(self) -> Decimal:
        """Signed base-currency equivalent — positive for debit, negative for credit."""
        return Decimal(self.direction.value) * (self.amount * self.fx_rate)


class JournalEntry(BaseModel):
    entry_date: str
    description: str
    source: Source
    external_ref: str | None = None
    postings: list[Posting] = Field(min_length=2)

    @model_validator(mode="after")
    def must_balance(self) -> JournalEntry:
        total = sum((p.base_signed for p in self.postings), Decimal(0))
        if total != Decimal(0):
            raise ValueError(
                f"Journal entry is unbalanced: net base amount = {total} (must be exactly zero)"
            )
        return self


class StoredJournalEntry(JournalEntry):
    """A JournalEntry that has been persisted and given an ID."""

    id: str
    user_id: str
    reversed_by: str | None = None
