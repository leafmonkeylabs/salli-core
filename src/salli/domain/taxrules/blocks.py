"""
Building blocks: shorthand for the shapes tax law keeps repeating, each of
which compiles to plain lines.

A block is never evaluated as a block. `expand` turns it into ordinary lines with
expressions in the same language an author would write by hand, so an
explanation can show exactly what a block became, and the engine has only one
kind of thing to evaluate.

Derived keys. A block with key `k` produces these lines (`of`, `amount`, … are
the block's own expressions, inserted as written):

    relief, deduction   k             the amount applied:  min(amount, max(0, of))
                        k.remaining   what is left:        max(0, of - line.k)
    capped_share        k.limit       the most allowed:    min(of * fraction, cap)
                                                           (of * fraction with no cap)
                        k             the amount allowed:  min(claimed, line.k.limit)
                        k.remaining   what is left:        max(0, of - line.k)
    schedule            k.band_N.amount   the part of `of` in band N of the table
                        k.band_N.tax      that part times the band's rate (rounded,
                                          if the table rounds per band)
                        k             the total: line.k.band_1.tax + … + line.k.band_M.tax
    final_rate          k             of * rate, rounded if the block says so
    credit              k             of, or min(of, cap) when a cap is given;
                                      marked refundable or not

`relief` and `deduction` compile identically; the name says which the law calls
it. A credit's refundability is recorded on its line for explanations and
forms; the engine doesn't apply credits by itself, the rule set's `result.net`
does. A non-refundable credit should therefore be capped by its author (at the
tax it may reduce), and validation warns when one isn't.

Block keys are plain keys (no dots), so a derived key can't collide with a line
an author declared.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field

from salli.domain.taxrules.arith import BandTable
from salli.domain.taxrules.common import (
    ExprText,
    Key,
    Label,
    Model,
    NonNegativeFigure,
    Rate,
    RoundingSpec,
)
from salli.domain.taxrules.expr import Expr, unparse


class _Block(Model):
    key: Key
    label: Label | None = None
    source: Key | None = None


class Relief(_Block):
    """An allowance that reduces an amount, never below zero."""

    type: Literal["relief"]
    of: ExprText
    amount: ExprText


class Deduction(_Block):
    """The same arithmetic as a relief, for laws that call it a deduction."""

    type: Literal["deduction"]
    of: ExprText
    amount: ExprText


class CappedShare(_Block):
    """A claim allowed up to a fraction of an amount, and at most `cap`
    (qualifying donations up to a third of income, say)."""

    type: Literal["capped_share"]
    of: ExprText
    claimed: ExprText
    fraction: Rate
    cap: NonNegativeFigure | None = None


class Schedule(_Block):
    """Progressive tax on an amount over one of the rule set's band tables."""

    type: Literal["schedule"]
    of: ExprText
    table: Key


class FinalRate(_Block):
    """A flat rate on an amount, outside any schedule."""

    type: Literal["final_rate"]
    of: ExprText
    rate: Rate
    round: RoundingSpec | None = None


class Credit(_Block):
    """Tax already paid or relieved, which the result subtracts."""

    type: Literal["credit"]
    of: ExprText
    refundable: bool
    cap: ExprText | None = None


Block = Annotated[
    Relief | Deduction | CappedShare | Schedule | FinalRate | Credit,
    Field(discriminator="type"),
]


def expression_fields(block: Block) -> dict[str, str]:
    """The block's fields that hold expressions, by field name."""
    fields = {"of": block.of}
    if isinstance(block, Relief | Deduction):
        fields["amount"] = block.amount
    elif isinstance(block, CappedShare):
        fields["claimed"] = block.claimed
    elif isinstance(block, Credit) and block.cap is not None:
        fields["cap"] = block.cap
    return fields


@dataclass(frozen=True)
class LineDraft:
    """A line a block compiles to, before the engine parses and checks it."""

    key: str
    label: str
    text: str
    source: str | None
    refundable: bool | None = None


def default_label(key: str) -> str:
    return key.replace("_", " ").capitalize()


def expand(block: Block, parsed: dict[str, Expr], table: BandTable | None) -> list[LineDraft]:
    """The lines `block` compiles to. `parsed` holds its expression fields,
    already parsed (so composing them can't change what they mean); `table` is
    the band table a schedule names, which the engine has looked up."""
    k = block.key
    label = block.label or default_label(k)
    source = block.source

    def sub(name: str) -> str:
        # Parenthesised, so an `of` of `a + b` stays one operand of `* rate`.
        return f"({unparse(parsed[name])})"

    def line(key: str, suffix: str, text: str, refundable: bool | None = None) -> LineDraft:
        return LineDraft(key, f"{label}: {suffix}" if suffix else label, text, source, refundable)

    if isinstance(block, Relief | Deduction):
        return [
            line(k, "", f"min({sub('amount')}, max(0, {sub('of')}))"),
            line(f"{k}.remaining", "remaining", f"max(0, {sub('of')} - line.{k})"),
        ]
    if isinstance(block, CappedShare):
        share = f"{sub('of')} * {format(block.fraction, 'f')}"
        limit = share if block.cap is None else f"min({share}, {format(block.cap, 'f')})"
        return [
            line(f"{k}.limit", "limit", limit),
            line(k, "", f"min({sub('claimed')}, line.{k}.limit)"),
            line(f"{k}.remaining", "remaining", f"max(0, {sub('of')} - line.{k})"),
        ]
    if isinstance(block, Schedule):
        assert table is not None, "the engine looks the table up before expanding"
        drafts: list[LineDraft] = []
        for n, band in enumerate(table.bands, start=1):
            amount = f"line.{k}.band_{n}.amount"
            drafts.append(
                line(
                    amount.removeprefix("line."),
                    f"band {n} amount",
                    f'band_amount({sub("of")}, "{block.table}", {n})',
                )
            )
            tax = f"{amount} * {format(band.rate, 'f')}"
            if table.rounding is not None:
                r = table.rounding
                tax = f'round({tax}, "{r.mode}", {format(r.unit, "f")})'
            drafts.append(line(f"{k}.band_{n}.tax", f"band {n} tax", tax))
        total = " + ".join(f"line.{k}.band_{n}.tax" for n in range(1, len(table.bands) + 1))
        drafts.append(line(k, "", total))
        return drafts
    if isinstance(block, FinalRate):
        tax = f"{sub('of')} * {format(block.rate, 'f')}"
        if block.round is not None:
            tax = f'round({tax}, "{block.round.mode}", {format(block.round.unit, "f")})'
        return [line(k, "", tax)]
    # Credit
    text = sub("of") if block.cap is None else f"min({sub('of')}, {sub('cap')})"
    return [line(k, "", text, refundable=block.refundable)]


def derived_keys(block: Block, table: BandTable | None) -> list[str]:
    """The keys `expand` would produce, known even when a block's expressions
    don't parse (so references to them don't pile up as unknown, too). A
    schedule whose table is missing yields only its own key."""
    k = block.key
    if isinstance(block, Relief | Deduction):
        return [k, f"{k}.remaining"]
    if isinstance(block, CappedShare):
        return [f"{k}.limit", k, f"{k}.remaining"]
    if isinstance(block, Schedule) and table is not None:
        keys: list[str] = []
        for n in range(1, len(table.bands) + 1):
            keys += [f"{k}.band_{n}.amount", f"{k}.band_{n}.tax"]
        return [*keys, k]
    return [k]
