"""
What the agents are told about the user they are talking to: the date, the
currency their ledger is kept in, where they are taxed, and the tax year they
are in. Pure, no I/O: AgentService gathers a `UserContext` per turn, and every
prompt ends with the section rendered from it.

The static prompts know no country, and neither does Salli: a user's tax is
computed only from the rule set they activated (docs/taxrules.md). A user with
no tax residency gets no country's tax framing at all; a user with active
rules is told which year and version they are, and what they cite; a user
without is told plainly that Salli can't compute their tax, and how to add
rules. No figure of any country's law appears here: those are the rules', and
reach the user only through the engine's results.
"""

from __future__ import annotations

import datetime
from contextvars import ContextVar
from dataclasses import dataclass, field

from salli.domain.jurisdiction import country_phrase


@dataclass(frozen=True)
class TaxRulesContext:
    """An active rule set version, as the prompts describe it."""

    country: str
    region: str | None
    #: What the rules call the year: "2031/32".
    year: str
    start: datetime.date
    end: datetime.date
    version: int
    #: The titles of the sources the rules cite.
    sources: tuple[str, ...] = ()
    #: The ledger totals the rules take: (key, label, kind) of each role.
    roles: tuple[tuple[str, str, str], ...] = field(default=())


@dataclass(frozen=True)
class UserContext:
    today: datetime.date
    #: The currency the user's ledger is kept in.
    base_currency: str | None = None
    #: Where the user said they are taxed.
    tax_residency: str | None = None
    #: Their active rules whose year contains today: the current tax year.
    current: TaxRulesContext | None = None
    #: The rules a computation uses when no year is named: today's, else the
    #: latest active year that has begun.
    latest: TaxRulesContext | None = None


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


def _year(rules: TaxRulesContext) -> str:
    return f"{rules.year} ({_day(rules.start)} to {_day(rules.end)})"


def _place(code: str) -> str:
    return f"{country_phrase(code)} ({code})"


#: Said with every mention of a user's own rules.
_PROVENANCE = (
    "Salli computes it from rules the user or their agent entered and doesn't vouch for "
    "the law: present figures as computed from their rules, citing the rules' sources."
)

#: How a user gets rules, in the agents' words.
_ADD_RULES = (
    "They can add rules (`salli tax rules create` or `import`), or have an AI agent "
    "research them with Salli's research_tax_rules prompt; only the user can activate them."
)


def _rules_line(rules: TaxRulesContext, what: str) -> str:
    region = f", {rules.region}" if rules.region else ""
    cites = f", citing {'; '.join(rules.sources)}" if rules.sources else ""
    return (
        f"{what} is {_year(rules)}, computed from their own rule set for "
        f"{rules.country}{region} (version {rules.version}{cites})."
    )


def _residency_lines(ctx: UserContext) -> list[str]:
    if ctx.tax_residency is None:
        return [
            "The user has not said where they are tax resident, so assume no country's "
            "tax rules. Before discussing their tax, ask where they are tax resident, and "
            "suggest they set it on their profile."
        ]

    place = _place(ctx.tax_residency)
    if ctx.current is None and ctx.latest is None:
        return [
            f"The user is tax resident in {place}. They have no active tax rules for "
            f"{country_phrase(ctx.tax_residency)}, so Salli can't compute their tax: say so, "
            "and never apply another country's rules, or figures from your own knowledge. "
            + _ADD_RULES
        ]

    lines = [f"The user is tax resident in {place}."]
    if ctx.current is not None:
        lines.append(_rules_line(ctx.current, "Their current tax year"))
    elif ctx.latest is not None:
        lines.append(
            "Today falls in no tax year their active rules cover (the next year's rules "
            "aren't in yet). "
            + _rules_line(ctx.latest, "The latest year they can compute")
            + " The tax tools use it unless asked for another."
        )
    lines.append(_PROVENANCE)
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


def tax_specialist_section(ctx: UserContext) -> str:
    """The context section, with the ledger totals the user's rules take, so
    the specialist can say which accounts feed which line."""
    section = context_section(ctx)
    rules = ctx.latest or ctx.current
    if ctx.tax_residency and rules is not None and rules.roles:
        roles = "; ".join(f"{key} ({label}, {kind})" for key, label, kind in rules.roles)
        section += (
            "\n- Their rules take these ledger totals, each from the accounts whose tax role "
            f"it is: {roles}."
        )
    return section


# ── Investing: local knowledge is researched, never built in ─────────────────


def investing_context(tax_residency: str | None) -> str:
    """What the FIRE strategy should know about where the user invests: only
    where that is, and that local products are theirs to check. The strategy is
    one model call with no web access, so it suggests kinds of product, never
    named local ones."""
    if tax_residency is None:
        return (
            "Where the user is tax resident is not known: keep investment suggestions to "
            "broad, low-cost index funds, and assume no country's products or tax rules."
        )
    return (
        f"The user is tax resident in {_place(tax_residency)}. Salli has no built-in notes "
        "on any country's investment products or rates, and you have no way to look them "
        "up here: suggest the kinds of low-cost index funds and tax-advantaged accounts to "
        "look for there, by type rather than by product or provider name, and say in "
        "ai_rationale that the user (or their AI agent) should check what is available "
        "locally against current, official sources."
    )
