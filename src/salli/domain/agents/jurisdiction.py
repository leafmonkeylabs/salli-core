"""
What the agents are told about the user they are talking to: the date, the
currency their ledger is kept in, where they are taxed, and the tax year they
are in. Pure, no I/O: AgentService gathers a `UserContext` per turn, and every
prompt ends with the section rendered from it.

The static prompts know no country. A user with no tax residency gets no
country's tax framing at all; a user taxed somewhere Salli has a pack for gets
that pack's facts (its authority, its law, its withholding kinds, its figures);
a user taxed elsewhere is told plainly that Salli cannot compute their tax.
Figures come from the pack, never from the model.
"""

from __future__ import annotations

import datetime
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal

from salli.domain.jurisdiction import country_phrase
from salli.domain.tax.models import CurrentTaxYear, TaxPack, TaxYear


@dataclass(frozen=True)
class UserContext:
    today: datetime.date
    #: The currency the user's ledger is kept in.
    base_currency: str | None = None
    #: Where the user said they are taxed.
    tax_residency: str | None = None
    #: Whose packs the tax tools compute with: the residency, or, while there is
    #: none, the one country whose packs compute in the base currency.
    tax_country: str | None = None
    #: Where the tax country stands today, when Salli has packs for it.
    current: CurrentTaxYear | None = None


#: The context of the agent run in progress, set by AgentService before each
#: turn, like the current user the tools act for.
_context: ContextVar[UserContext | None] = ContextVar("salli_user_context", default=None)


def set_user_context(context: UserContext) -> None:
    _context.set(context)


def user_context() -> UserContext:
    """The current run's context, or a neutral one: today, and nothing else."""
    return _context.get() or UserContext(today=datetime.date.today())


# ── Rendering ────────────────────────────────────────────────────────────────


def _day(day: datetime.date) -> str:
    return f"{day.day} {day.strftime('%B %Y')}"


def _year(year: TaxYear) -> str:
    return f"{year.label} ({_day(year.start)} to {_day(year.end)})"


def _place(code: str) -> str:
    return f"{country_phrase(code)} ({code})"


def _number(value: Decimal) -> str:
    return f"{value.normalize():,f}"


def _percent(rate: Decimal) -> str:
    return f"{(rate * 100).normalize():f}"


def _residency_lines(ctx: UserContext) -> list[str]:
    if ctx.tax_residency is None:
        lines = [
            "The user has not said where they are tax resident, so assume no country's "
            "tax rules. Before discussing their tax, ask where they are tax resident, and "
            "suggest they set it on their profile."
        ]
        if ctx.tax_country:
            lines.append(
                "Until they do, Salli's tax tools compute with the pack for their base "
                "currency: confirm they are tax resident in that pack's country before "
                "treating a computation as theirs."
            )
        return lines

    place = _place(ctx.tax_residency)
    current = ctx.current
    if current is None:
        return [
            f"The user is tax resident in {place}. Salli has no tax pack for "
            f"{country_phrase(ctx.tax_residency)} yet, so it cannot compute their tax: say "
            "so, and never apply another country's rules. General explanations are fine; "
            "for their own position, suggest a local tax professional."
        ]

    latest = current.latest
    pack = latest or current.pack
    name = pack.year_name if pack else "tax year"
    lines = [f"The user is tax resident in {place}."]
    if pack and (pack.authority or pack.law):
        administered = f", administered by the {pack.authority}" if pack.authority else ""
        lines.append(f"Their income tax is under {pack.law or 'its law'}{administered}.")
    lines.append(f"Their current {name} is {_year(current.year)}.")
    if current.pack is None:
        if latest is None:
            lines.append("Salli has no pack for a year that has begun, so it cannot compute it.")
        else:
            lines.append(
                f"Salli has no pack for {current.year.label} yet. The latest year it can "
                f"compute is {latest.year}, which the tax tools use unless asked for another."
            )
    if pack and pack.withholding_kinds:
        kinds = "; ".join(
            f"{k.label} ({k.description.rstrip('.')})" for k in pack.withholding_kinds
        )
        lines.append(f"Tax withheld or paid ahead that their pack credits: {kinds}.")
    return lines


def context_section(ctx: UserContext) -> str:
    """The section every conversational prompt ends with."""
    lines = [f"Today's date is {ctx.today.strftime('%A')}, {_day(ctx.today)}."]
    if ctx.base_currency:
        lines.append(
            f"The user's base currency is {ctx.base_currency}: the tools report amounts "
            "in it unless they say otherwise."
        )
    lines += _residency_lines(ctx)
    return "About this user:\n" + "\n".join(f"- {line}" for line in lines)


def pack_figures(pack: TaxPack) -> str:
    """A pack's headline figures, as the pack states them."""
    rates = "/".join(_percent(band.rate) for band in pack.bands)
    facts = [
        f"personal relief {pack.currency} {_number(pack.personal_relief)}",
        f"progressive bands {rates}% on taxable income",
    ]
    fsi = pack.foreign_service_income
    if fsi is not None:
        via = " remitted through a bank" if fsi.requires_bank_remittance else ""
        facts.append(f"foreign service income{via}: {_percent(fsi.max_rate)}% final tax")
    if pack.has_qualifying_payment_relief:
        facts.append(
            f"qualifying payments deductible up to {pack.currency} "
            f"{_number(pack.qualifying_payment_cap)}"
        )
    period = f"{_day(datetime.date.fromisoformat(pack.period_start))} to " + _day(
        datetime.date.fromisoformat(pack.period_end)
    )
    return f"The {pack.year} pack (v{pack.version}, {period}): " + "; ".join(facts) + "."


def tax_specialist_section(ctx: UserContext) -> str:
    """The context section, with the figures of the pack the tools compute with."""
    section = context_section(ctx)
    pack = ctx.current.latest if ctx.current else None
    if ctx.tax_residency and pack is not None:
        section += f"\n- {pack_figures(pack)}"
    return section


# ── FIRE strategy: what to suggest where ─────────────────────────────────────

#: Where an investment suggestion needs local knowledge, by tax residency.
_MARKETS: dict[str, str] = {
    "LK": (
        "In Sri Lanka, CSE index funds (tracking the ASPI) and unit trusts are the local "
        "low-cost options; for the international portion, broad index ETFs through a "
        "foreign account where needed. The LKR's depreciation risk is real: weight a "
        "currency-hedge bucket accordingly."
    ),
}


def market_notes(tax_residency: str | None) -> str:
    """What the FIRE strategy should know about where the user invests."""
    if tax_residency is None:
        return (
            "Where the user is tax resident is not known: keep investment suggestions to "
            "broad, low-cost index funds, and assume no country's products or tax rules."
        )
    known = _MARKETS.get(tax_residency)
    if known:
        return f"The user is tax resident in {_place(tax_residency)}. {known}"
    return (
        f"The user is tax resident in {_place(tax_residency)}: suggest the low-cost index "
        "funds and tax-advantaged accounts available there, by type rather than by "
        "product name if unsure."
    )
