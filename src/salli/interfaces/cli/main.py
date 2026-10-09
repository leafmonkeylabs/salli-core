"""
Salli CLI — Phase 1 control surface (Typer + Rich).

All commands are thin wrappers over application services.
The CLI and the FastAPI layer share the same services via composition.py.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import typer
from rich.table import Table

from salli.interfaces.cli.setup import members_app, serve, setup
from salli.interfaces.cli.skills import skills_app
from salli.interfaces.cli.support import console, emit, json_mode, with_json_option
from salli.interfaces.cli.support import require_user as _require_user
from salli.interfaces.cli.support import resolve_id as _resolve_id
from salli.interfaces.cli.support import services as _services

app = typer.Typer(
    name="salli",
    help="Salli — personal finance & tax preparation for Sri Lanka",
    no_args_is_help=True,
)

accounts_app = typer.Typer(help="Manage the chart of accounts")
entry_app = typer.Typer(help="Journal entry commands")
ledger_app = typer.Typer(help="Ledger reports")
tax_app = typer.Typer(help="Tax computation and return preparation")
agent_app = typer.Typer(help="Tax Agent and return preparation")
parse_app = typer.Typer(help="Bank statement parsing and import")
reminders_app = typer.Typer(help="Filing and task reminders")
fi_app = typer.Typer(help="Financial independence score, goals, and strategy")
fi_goals_app = typer.Typer(help="FI goals")
fi_strategy_app = typer.Typer(help="FIRE strategy")
advisor_app = typer.Typer(help="Wealth Advisor")
advisor_reports_app = typer.Typer(help="Advisor reports")
documents_app = typer.Typer(help="Uploaded documents and memories")
profile_app = typer.Typer(help="Fact-find profile: identity, risk, opening balances, income")
budget_app = typer.Typer(help="Category budgets vs. actual ledger spend")
debt_app = typer.Typer(help="Structured debts and avalanche/snowball payoff planning")
portfolio_app = typer.Typer(help="Investment holdings, allocation, and rebalancing")
subscription_app = typer.Typer(help="Recurring subscriptions and missed-charge/price-change alerts")
insurance_app = typer.Typer(help="Insurance policy inventory and coverage-gap analysis")
insurance_policy_app = typer.Typer(help="Insurance policies")
insurance_target_app = typer.Typer(help="Declared coverage targets")
reports_app = typer.Typer(help="Exportable statements: balance sheet, net worth, goal progress")
db_app = typer.Typer(help="Database migrations")
onboarding_app = typer.Typer(help="First-run setup of your profile and starter accounts")
llm_keys_app = typer.Typer(help="Your own LLM API keys, stored encrypted")
mcp_app = typer.Typer(help="AI clients (Claude, ChatGPT) connected over MCP")

app.add_typer(accounts_app, name="accounts")
app.add_typer(entry_app, name="entry")
app.add_typer(ledger_app, name="ledger")
app.add_typer(tax_app, name="tax")
app.add_typer(agent_app, name="agent")
app.add_typer(parse_app, name="parse")
app.add_typer(reminders_app, name="reminders")
app.add_typer(fi_app, name="fi")
fi_app.add_typer(fi_goals_app, name="goals")
fi_app.add_typer(fi_strategy_app, name="strategy")
app.add_typer(advisor_app, name="advisor")
advisor_app.add_typer(advisor_reports_app, name="reports")
app.add_typer(documents_app, name="documents")
app.add_typer(profile_app, name="profile")
app.add_typer(budget_app, name="budget")
app.add_typer(debt_app, name="debt")
app.add_typer(portfolio_app, name="portfolio")
app.add_typer(subscription_app, name="subscription")
app.add_typer(insurance_app, name="insurance")
insurance_app.add_typer(insurance_policy_app, name="policy")
insurance_app.add_typer(insurance_target_app, name="target")
app.add_typer(reports_app, name="reports")
app.add_typer(db_app, name="db")
app.add_typer(onboarding_app, name="onboarding")
app.add_typer(llm_keys_app, name="llm-keys")
app.add_typer(mcp_app, name="mcp")
app.add_typer(members_app, name="members")
app.add_typer(skills_app, name="skills")
app.command("setup")(setup)
app.command("serve")(serve)


@asynccontextmanager
async def _agent_services():
    """
    Build services with a PostgreSQL-backed LangGraph checkpointer.

    Agent conversations and human-in-the-loop workflows (return prep, briefing)
    persist state via the checkpointer — without one, aget_state()/interrupt()
    raise 'No checkpointer set'. The FastAPI app wires this up once at startup
    (see interfaces/api/main.py); each CLI invocation is a fresh process, so it
    opens and tears down its own checkpointer connection per command.
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from salli.composition import build_services
    from salli.config import get_settings

    settings = get_settings()
    pg_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    async with AsyncPostgresSaver.from_conn_string(pg_url) as checkpointer:
        await checkpointer.setup()
        yield build_services(settings, checkpointer=checkpointer)


# ── accounts ──────────────────────────────────────────────────────────────────


@accounts_app.command("list")
def accounts_list():
    """List all accounts in the chart of accounts."""
    user_id = _require_user()
    accounts = asyncio.run(_services().ledger.list_accounts(user_id))
    if emit(accounts):
        return
    if not accounts:
        console.print("[dim]No accounts found. Use 'salli accounts add' to create one.[/dim]")
        return
    table = Table(title="Chart of Accounts")
    table.add_column("Code")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Currency")
    for acc in accounts:
        table.add_row(acc.code, acc.name, acc.type, acc.currency)
    console.print(table)


@accounts_app.command("add")
def accounts_add(
    code: str = typer.Argument(..., help="Account code, e.g. 1001"),
    name: str = typer.Argument(..., help="Account name"),
    type: str = typer.Argument(..., help="asset|liability|equity|income|expense"),
    currency: str = typer.Option("LKR", help="ISO currency code"),
):
    """Add an account to the chart of accounts."""
    user_id = _require_user()
    valid_types = {"asset", "liability", "equity", "income", "expense"}
    if type not in valid_types:
        console.print(
            f"[red]Invalid type '{type}'. Must be one of: {', '.join(sorted(valid_types))}[/red]"
        )
        raise typer.Exit(1)
    account_id = asyncio.run(
        _services().ledger.add_account(user_id, code, name, type, currency)  # type: ignore[arg-type]
    )
    emit({"id": account_id, "code": code, "name": name, "type": type, "currency": currency})
    console.print(f"[green]Account created:[/green] {code} — {name} ({account_id})")


@accounts_app.command("show")
def accounts_show(
    account_id: str = typer.Argument(...),
    from_date: str = typer.Option(None, "--from", help="YYYY-MM-DD"),
    to_date: str = typer.Option(None, "--to", help="YYYY-MM-DD"),
):
    """Show an account's detail, current balance, and transaction history."""
    from decimal import Decimal

    user_id = _require_user()
    overview = asyncio.run(
        _services().ledger.get_account_overview(user_id, account_id, from_date, to_date)
    )
    if overview is None:
        console.print(f"[red]Account not found:[/red] {account_id}")
        raise typer.Exit(1)
    if emit(overview):
        return

    acc = overview["account"]
    console.print(
        f"\n[bold]{acc['code']} — {acc['name']}[/bold]  ({acc['type']}, {acc['currency']})"
    )
    status_label = "active" if acc["is_active"] else "[red]inactive[/red]"
    console.print(f"  Status:          {status_label}")
    console.print(f"  Current balance: LKR {Decimal(overview['current_balance']):>16,.2f}\n")

    transactions = overview.get("transactions") or []
    if transactions:
        table = Table(title="Transactions")
        table.add_column("Date")
        table.add_column("Description")
        table.add_column("Source")
        table.add_column("Running Balance", justify="right")
        for t in transactions:
            table.add_row(
                t["entry_date"],
                t["description"],
                t["source"],
                f"{Decimal(t['running_balance']):,.2f}",
            )
        console.print(table)
    else:
        console.print("[dim]No transactions for this account.[/dim]")


@accounts_app.command("update")
def accounts_update(
    account_id: str = typer.Argument(...),
    code: str = typer.Option(..., "--code"),
    name: str = typer.Option(..., "--name"),
    type: str = typer.Option(..., "--type", help="asset|liability|equity|income|expense"),
    currency: str = typer.Option("LKR", "--currency"),
):
    """Update an account's code, name, type, and currency."""
    user_id = _require_user()
    valid_types = {"asset", "liability", "equity", "income", "expense"}
    if type not in valid_types:
        console.print(
            f"[red]Invalid type '{type}'. Must be one of: {', '.join(sorted(valid_types))}[/red]"
        )
        raise typer.Exit(1)
    asyncio.run(_services().ledger.update_account(user_id, account_id, code, name, type, currency))
    emit({"id": account_id, "code": code, "name": name, "type": type, "currency": currency})
    console.print(f"[green]Account updated:[/green] {account_id}")


@accounts_app.command("deactivate")
def accounts_deactivate(
    account_id: str = typer.Argument(...),
):
    """Deactivate (soft-delete) an account."""
    user_id = _require_user()
    asyncio.run(_services().ledger.deactivate_account(user_id, account_id))
    emit({"id": account_id, "is_active": False})
    console.print(f"[green]Account deactivated:[/green] {account_id}")


@accounts_app.command("reactivate")
def accounts_reactivate(
    account_id: str = typer.Argument(...),
):
    """Reactivate a previously deactivated account."""
    user_id = _require_user()
    asyncio.run(_services().ledger.reactivate_account(user_id, account_id))
    emit({"id": account_id, "is_active": True})
    console.print(f"[green]Account reactivated:[/green] {account_id}")


# ── entry ─────────────────────────────────────────────────────────────────────


@entry_app.command("add")
def entry_add(
    date: str = typer.Option(..., "--date", help="YYYY-MM-DD"),
    desc: str = typer.Option(..., "--desc", help="Description"),
    debit: list[str] = typer.Option(..., "--debit", help="ACCOUNT_ID:AMOUNT (repeat for splits)"),
    credit: list[str] = typer.Option(..., "--credit", help="ACCOUNT_ID:AMOUNT (repeat for splits)"),
    receipt: str = typer.Option(
        None, "--receipt", help="Document ID of an attached receipt/file (source stays 'manual')"
    ),
):
    """Add a balanced journal entry (ACCOUNT_ID:AMOUNT pairs)."""
    from decimal import Decimal

    from salli.domain.accounting.models import Direction

    user_id = _require_user()

    def parse_side(pairs: list[str], direction: Direction) -> list[dict]:
        postings = []
        for pair in pairs:
            try:
                account_id, amount_str = pair.rsplit(":", 1)
                postings.append(
                    {
                        "account_id": account_id.strip(),
                        "direction": direction,
                        "amount": Decimal(amount_str.strip()),
                        "currency": "LKR",
                    }
                )
            except ValueError:
                console.print(f"[red]Invalid format '{pair}'. Use ACCOUNT_ID:AMOUNT[/red]")
                raise typer.Exit(1)
        return postings

    postings_data = parse_side(debit, Direction.DEBIT) + parse_side(credit, Direction.CREDIT)

    try:
        entry_id = asyncio.run(
            _services().ledger.add_entry(
                user_id, date, desc, "manual", postings_data, external_ref=receipt
            )
        )
        emit({"id": entry_id})
        console.print(f"[green]Entry posted:[/green] {entry_id}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@entry_app.command("show")
def entry_show(
    entry_id: str = typer.Argument(...),
):
    """Show a journal entry's full detail and provenance (statement/receipt trace)."""
    from decimal import Decimal

    user_id = _require_user()
    entry = asyncio.run(_services().ledger.get_entry(user_id, entry_id))
    if entry is None:
        console.print(f"[red]Entry not found:[/red] {entry_id}")
        raise typer.Exit(1)
    provenance = asyncio.run(_services().ledger.get_entry_provenance(user_id, entry_id))
    if emit({"entry": entry, "provenance": provenance}):
        return

    console.print(f"\n[bold]{entry.description}[/bold]  ({entry.entry_date})")
    console.print(f"  Source:       {entry.source}")
    if entry.reversed_by:
        console.print(f"  [yellow]Reversed by:[/yellow]  {entry.reversed_by}\n")
    else:
        console.print()

    table = Table(title="Postings")
    table.add_column("Account ID")
    table.add_column("Direction")
    table.add_column("Amount", justify="right")
    table.add_column("Currency")
    for p in entry.postings:
        table.add_row(
            p.account_id,
            "DEBIT" if p.direction.value == 1 else "CREDIT",
            f"{Decimal(p.amount):,.2f}",
            p.currency,
        )
    console.print(table)

    if provenance and provenance.get("statement"):
        stmt = provenance["statement"]
        console.print("\n[bold]Provenance:[/bold] bank statement")
        console.print(f"  Raw description:  {stmt['raw_description']}")
        console.print(f"  Bank ref:          {stmt.get('bank_ref') or '—'}")
        if stmt.get("statement"):
            s = stmt["statement"]
            console.print(f"  Bank:              {s.get('bank') or '—'}")
            console.print(f"  Period:            {s.get('period_start')} → {s.get('period_end')}")
            console.print(f"  File:              {s.get('storage_key') or '—'}")
    elif provenance and provenance.get("receipt"):
        receipt_info = provenance["receipt"]
        console.print("\n[bold]Provenance:[/bold] attached receipt")
        console.print(f"  Title:      {receipt_info['title']}")
        console.print(f"  MIME type:  {receipt_info['mime_type']}")
        console.print(f"  Document:   {receipt_info['document_id']}")
    else:
        console.print(
            "\n[dim]No provenance recorded (manually entered, no receipt attached).[/dim]"
        )


@entry_app.command("reverse")
def entry_reverse(
    entry_id: str = typer.Argument(..., help="ID of the journal entry to reverse"),
):
    """Post a reversing entry for a previously posted journal entry."""
    user_id = _require_user()
    try:
        reversing_id = asyncio.run(_services().ledger.reverse_entry(user_id, entry_id))
        emit({"id": reversing_id, "reversed": entry_id})
        console.print(f"[green]Reversing entry posted:[/green] {reversing_id}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@entry_app.command("list")
def entry_list(
    from_date: str = typer.Option(None, "--from", help="YYYY-MM-DD"),
    to_date: str = typer.Option(None, "--to", help="YYYY-MM-DD"),
):
    """List journal entries, with each posting and its tags."""
    user_id = _require_user()
    entries = asyncio.run(_services().ledger.get_entries(user_id, from_date, to_date))
    if emit(entries):
        return
    table = Table(title="Journal entries")
    table.add_column("ID")
    table.add_column("Date")
    table.add_column("Description")
    table.add_column("Source")
    table.add_column("Reversed by")
    for e in entries:
        table.add_row(e.id[:8], str(e.entry_date), e.description, e.source, e.reversed_by or "")
    console.print(table)


@entry_app.command("parse")
def entry_parse(text: str = typer.Argument(..., help='e.g. "groceries 2500 cash yesterday"')):
    """Draft an entry from free text (AI). Nothing is posted."""
    user_id = _require_user()
    svc = _services()
    if not svc.entry_parse.available:
        console.print("[red]AI parsing is not available: no LLM key configured.[/red]")
        raise typer.Exit(1)
    draft = asyncio.run(svc.entry_parse.parse_draft(user_id, text))
    if emit(draft):
        return
    for key, value in draft.items():
        console.print(f"  {key}: {value}")
    console.print("[dim]Draft only — post it with 'salli entry add'.[/dim]")


@entry_app.command("tag")
def entry_tag(
    posting_id: str = typer.Argument(..., help="Posting id (from 'salli entry list --json')"),
    tag: list[str] = typer.Option([], "--tag", help="Tag id (repeat; none clears the tags)"),
):
    """Replace a posting's tags. Never touches the posted amounts."""
    user_id = _require_user()
    asyncio.run(_services().ledger.set_posting_tags(user_id, posting_id, tag))
    emit({"posting_id": posting_id, "tags": tag})
    console.print(f"[green]Tags set on posting[/green] {posting_id}: {', '.join(tag) or 'none'}")


# ── ledger ────────────────────────────────────────────────────────────────────


@ledger_app.command("trial-balance")
def trial_balance_cmd(
    from_date: str = typer.Option(None, "--from", help="YYYY-MM-DD"),
    to_date: str = typer.Option(None, "--to", help="YYYY-MM-DD"),
):
    """Print the trial balance (must net to zero)."""
    user_id = _require_user()
    balances = asyncio.run(_services().ledger.get_trial_balance(user_id, from_date, to_date))
    if emit(balances):
        return
    if not balances:
        console.print("[dim]No entries found.[/dim]")
        return

    from decimal import Decimal

    table = Table(title="Trial Balance")
    table.add_column("Account ID")
    table.add_column("Balance (LKR)", justify="right")
    total = Decimal(0)
    for acc_id, bal in sorted(balances.items()):
        table.add_row(acc_id, f"{bal:,.2f}")
        total += bal
    table.add_section()
    table.add_row("[bold]NET[/bold]", f"[bold]{total:,.2f}[/bold]")
    console.print(table)


@ledger_app.command("income-statement")
def income_statement(
    from_date: str = typer.Option(..., "--from"),
    to_date: str = typer.Option(..., "--to"),
):
    """Print net income (income − expenses) for a date range."""
    from decimal import Decimal

    user_id = _require_user()
    svc = _services()

    async def _run() -> Decimal | None:
        accounts = await svc.ledger.list_accounts(user_id)
        income_ids = {a.id for a in accounts if a.type == "income"}
        expense_ids = {a.id for a in accounts if a.type == "expense"}
        if not income_ids and not expense_ids:
            return None
        return await svc.ledger.get_income_statement(
            user_id, from_date, to_date, income_ids, expense_ids
        )

    net_income = asyncio.run(_run())
    if emit({"from": from_date, "to": to_date, "net_income": net_income}):
        return
    if net_income is None:
        console.print("[dim]No income/expense accounts found.[/dim]")
        return
    console.print(f"\n[bold]Income Statement[/bold]  {from_date} → {to_date}\n")
    console.print(f"  [bold]Net income:  LKR {net_income:>16,.2f}[/bold]\n")


@ledger_app.command("tags")
def ledger_tags(
    kind: str = typer.Option(None, "--kind", help="category | need"),
):
    """List the tags you can put on postings."""
    user_id = _require_user()
    tags = asyncio.run(_services().ledger.list_tags(user_id, kind))
    if emit(tags):
        return
    table = Table(title="Tags")
    table.add_column("ID")
    table.add_column("Kind")
    table.add_column("Slug")
    table.add_column("Name")
    for t in tags:
        table.add_row(t.id[:8], t.kind, t.slug, t.name)
    console.print(table)


# ── tax ───────────────────────────────────────────────────────────────────────


@tax_app.command("compute")
def tax_compute(
    year: str = typer.Option("2025/26", "--year", help="Year of assessment"),
):
    """Compute income tax using the versioned rules engine."""
    user_id = _require_user()
    try:
        result = asyncio.run(_services().tax.compute_tax(user_id, year))
    except KeyError as e:
        console.print(f"[red]Unknown tax pack:[/red] {e}")
        raise typer.Exit(1)
    if emit(result):
        return

    console.print(f"\n[bold]Tax Computation — {result.pack_year} (v{result.pack_version})[/bold]\n")

    table = Table(title="Band Workings")
    table.add_column("Band")
    table.add_column("Taxable in Band (LKR)", justify="right")
    table.add_column("Rate")
    table.add_column("Tax (LKR)", justify="right")
    for i, bw in enumerate(result.band_workings, 1):
        upto = f"{bw.to_amount:,.0f}" if bw.to_amount else "∞"
        table.add_row(
            f"{i} (up to {upto})",
            f"{bw.taxable_in_band:,.2f}",
            f"{bw.rate * 100:.0f}%",
            f"{bw.tax:,.2f}",
        )
    console.print(table)

    console.print(f"\n  Gross income:        LKR {result.gross_income:>16,.2f}")
    console.print(f"  Personal relief:     LKR {result.personal_relief_applied:>16,.2f}")
    console.print(f"  Taxable income:      LKR {result.taxable_income:>16,.2f}")
    console.print(f"  Tax before credits:  LKR {result.tax_before_credits:>16,.2f}")
    console.print(f"  APIT credit:         LKR {result.apit_credit:>16,.2f}")
    console.print(f"  AIT credit:          LKR {result.ait_credit:>16,.2f}")
    console.print(f"  Foreign tax credit:  LKR {result.foreign_tax_credit:>16,.2f}")
    console.print(f"\n[bold]  Tax payable:         LKR {result.tax_payable:>16,.2f}[/bold]\n")


@tax_app.command("explain")
def tax_explain(
    year: str = typer.Option("2025/26", "--year"),
):
    """Launch the Tax Agent REPL to explain your tax situation."""
    # Delegate to agent chat with a priming message
    _run_agent_chat(f"Please explain my tax situation for the {year} year of assessment.")


@tax_app.command("prepare-return")
def tax_prepare_return(
    year: str = typer.Option("2025/26", "--year"),
    thread_id: str = typer.Option(None, "--thread-id", help="Resume an existing return thread"),
):
    """Run the return preparation workflow (pauses for review before finalizing)."""

    user_id = _require_user()

    async def _run():
        async with _agent_services() as svc:
            result = await svc.agent.prepare_return(user_id, year=year, thread_id=thread_id)
            draft = result.get("draft_return", {})
            tid = result.get("thread_id", "")

            console.print(f"\n[bold]Draft Return — {year}[/bold]  (thread: {tid})\n")
            for cage, value in draft.items():
                if cage == "note":
                    continue
                console.print(f"  {cage:<40} {value}")
            if draft.get("note"):
                console.print(f"\n[dim]{draft['note']}[/dim]")

            console.print(
                "\nApprove this draft? "
                "[[green]approve[/green]/[yellow]edit[/yellow]/[red]reject[/red]]"
            )
            decision = input("> ").strip().lower()
            if decision not in ("approve", "edit", "reject"):
                decision = "reject"

            final = await svc.agent.resume_return(tid, decision)
            if final.get("error"):
                console.print(f"[yellow]{final['error']}[/yellow]")
            else:
                ws = final.get("worksheet", {})
                console.print("\n[bold green]Return worksheet ready.[/bold green]")
                console.print(f"  Status: {ws.get('status')}")
                if ws.get("instructions"):
                    console.print(f"\n{ws['instructions']}")

    asyncio.run(_run())


@tax_app.command("packs")
def tax_packs():
    """List available tax packs."""
    from salli.domain.tax.packs.registry import list_packs

    if emit(list_packs()):
        return

    table = Table(title="Available Tax Packs", show_header=True)
    table.add_column("Country")
    table.add_column("Year")
    table.add_column("Version")
    table.add_column("Period")

    for pack in list_packs():
        table.add_row(
            pack.country,
            pack.year,
            pack.version,
            f"{pack.period_start} → {pack.period_end}",
        )

    console.print(table)


@tax_app.command("recompute-stored")
def tax_recompute_stored(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Actually write the corrected results. Without this, only reports what would change.",
    ),
):
    """
    Re-run every stored tax computation against the current engine.

    `/tax/latest` serves the most recently *saved* result, so after an engine
    fix a user keeps seeing the old figure until they happen to press
    Recompute — and a wrong tax number is exactly what they would act on.

    Dry-run by default: inspect the report, then re-run with --apply.
    """
    report = asyncio.run(_services().tax.recompute_stored(apply=apply))
    if emit(report):
        return

    if not report:
        console.print("[yellow]No stored tax computations found.[/yellow]")
        return

    table = Table(
        title=("Recomputed stored tax" if apply else "Dry run — nothing written"),
        show_header=True,
    )
    table.add_column("User")
    table.add_column("Year")
    table.add_column("Credits was")
    table.add_column("Credits now")
    table.add_column("Payable was")
    table.add_column("Payable now")
    table.add_column("Refund")
    table.add_column("Status")

    changed = 0
    errored = 0
    for row in report:
        if "error" in row:
            errored += 1
            table.add_row(
                row["user_id"][:8],
                row["year"],
                "—",
                "—",
                "—",
                "—",
                "—",
                f"[red]{row['error']}[/red]",
            )
            continue
        if row["changed"]:
            changed += 1
            status = "[green]applied[/green]" if row["applied"] else "[yellow]would change[/yellow]"
        else:
            status = "[dim]unchanged[/dim]"
        table.add_row(
            row["user_id"][:8],
            row["year"],
            row["old_credits"],
            row["new_credits"],
            row["old_tax_payable"],
            row["new_tax_payable"],
            row["new_refund_due"],
            status,
        )

    console.print(table)
    console.print(
        f"{len(report)} stored · [bold]{changed} changed[/bold]"
        + (f" · [red]{errored} errored[/red]" if errored else "")
        + ("" if apply else "  —  re-run with [bold]--apply[/bold] to write")
    )


@tax_app.command("latest")
def tax_latest(year: str = typer.Option("2025/26", help="Year of assessment")):
    """Show the most recently stored tax computation for a year."""
    user_id = _require_user()
    result = asyncio.run(_services().tax.get_latest_computation(user_id, year))
    if emit(result):
        return
    if result is None:
        console.print(f"[dim]No stored computation for {year}. Run 'salli tax compute'.[/dim]")
        return
    console.print(result)


# ── parse ─────────────────────────────────────────────────────────────────────


@parse_app.command("upload")
def parse_upload(
    file: str = typer.Argument(..., help="Path to bank statement (PDF, XLSX, or CSV)"),
    bank: str = typer.Option("unknown", "--bank", help="Bank name hint (e.g. 'ComBank', 'HNB')"),
):
    """
    Parse a bank statement and queue transactions for review.

    Runs PDF/XLSX/CSV extraction, deduplication, and LLM classification.
    Prints a summary and prompts for immediate inline review.
    """
    import pathlib

    user_id = _require_user()
    path = pathlib.Path(file)
    if not path.exists():
        console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(1)

    data = path.read_bytes()
    filename = path.name
    svc = _services()

    console.print(f"[dim]Parsing {filename} …[/dim]")
    result = asyncio.run(svc.parsing.parse_statement(user_id, filename, data, bank))
    if emit(result):
        return

    console.print(
        f"\n[bold]Parsed:[/bold] {len(result.transactions)} transactions "
        f"({result.period_start} → {result.period_end}), "
        f"{len(result.errors)} error(s)\n"
    )

    if not result.transactions:
        console.print("[dim]No transactions found.[/dim]")
        return

    _interactive_review(user_id, svc, result)


def _interactive_review(user_id, svc, result) -> None:
    """Walk the user through each pending transaction, then post approved ones."""
    from rich.panel import Panel

    approved_ids: list[str] = []
    skipped = 0

    for i, txn in enumerate(result.transactions, 1):
        raw = txn.raw
        header = f"[{i}/{len(result.transactions)}] {raw.date}  {raw.description[:50]}"
        amount_str = f"{'CR' if raw.credit_flag else 'DR'} {raw.currency} {raw.amount:,.2f}"
        dedup = "[yellow]DUPLICATE — skipping[/yellow]" if txn.dedup_status == "duplicate" else ""

        console.print(
            Panel(
                f"{amount_str}\n"
                f"  DR: {txn.debit_account_id or '[dim]—[/dim]'}\n"
                f"  CR: {txn.credit_account_id or '[dim]—[/dim]'}\n"
                f"  Confidence: {txn.confidence:.0%}  {dedup}",
                title=header,
                border_style="cyan",
            )
        )

        if txn.dedup_status == "duplicate":
            skipped += 1
            continue

        try:
            choice = input("  [a]pprove / [s]kip / [q]uit  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Aborted.[/dim]")
            break

        if choice in ("q", "quit"):
            console.print("[dim]Stopped early.[/dim]")
            break
        if choice in ("a", "approve", ""):
            if txn.id:
                approved_ids.append(txn.id)
        else:
            skipped += 1

    if approved_ids:
        console.print(f"\n[dim]Posting {len(approved_ids)} approved transaction(s)…[/dim]")
        asyncio.run(svc.parsing.post_approved(user_id, approved_ids))
        console.print(f"[green]Posted {len(approved_ids)} entries.[/green]")
    else:
        console.print("[dim]Nothing posted.[/dim]")

    if skipped:
        console.print(f"[dim]{skipped} transaction(s) skipped/duplicated.[/dim]")


@parse_app.command("pending")
def parse_pending():
    """List transactions parsed but not yet posted."""
    user_id = _require_user()
    svc = _services()
    pending = asyncio.run(svc.parsing.get_pending(user_id))
    if emit(pending):
        return

    if not pending:
        console.print("[dim]No pending transactions.[/dim]")
        return

    table = Table(title=f"Pending Transactions ({len(pending)})")
    table.add_column("ID", style="dim")
    table.add_column("Date")
    table.add_column("Description")
    table.add_column("Amount", justify="right")
    table.add_column("DR account")
    table.add_column("CR account")

    for txn in pending:
        raw = txn.raw
        table.add_row(
            str(txn.id or "")[:8],
            raw.date,
            raw.description[:40],
            f"{'CR' if raw.credit_flag else 'DR'} {raw.currency} {raw.amount:,.2f}",
            txn.debit_account_id or "—",
            txn.credit_account_id or "—",
        )

    console.print(table)


@parse_app.command("post")
def parse_post(
    ids: list[str] = typer.Argument(..., help="Transaction IDs to post (space-separated)"),
):
    """Post specific approved transactions to the ledger."""
    user_id = _require_user()
    svc = _services()

    async def _run() -> list[str]:
        pending = await svc.parsing.get_pending(user_id)
        pending_dicts = [{"id": str(txn.id)} for txn in pending]
        resolved_ids = [_resolve_id(pending_dicts, id_, "pending transaction") for id_ in ids]
        return await svc.parsing.post_approved(user_id, resolved_ids)

    entry_ids = asyncio.run(_run())
    emit({"entry_ids": entry_ids})
    console.print(f"[green]Posted {len(entry_ids)} transaction(s).[/green]")


@parse_app.command("list")
def parse_list(limit: int = typer.Option(50, help="Maximum statements to show")):
    """List uploaded statements, newest first."""
    user_id = _require_user()
    statements = asyncio.run(_services().parsing.list_statements(user_id, limit))
    if emit(statements):
        return
    table = Table(title="Statements")
    for column in ("ID", "File", "Bank", "Uploaded"):
        table.add_column(column)
    for st in statements:
        table.add_row(
            str(st.get("id", ""))[:8],
            str(st.get("filename", "")),
            str(st.get("bank", "")),
            str(st.get("created_at", "")),
        )
    console.print(table)


# ── reminders ─────────────────────────────────────────────────────────────────


@reminders_app.command("list")
def reminders_list(
    status: str = typer.Option(None, "--status", help="Filter by status, e.g. 'pending'/'done'"),
    alerts_only: bool = typer.Option(
        False, "--alerts-only", help="Show only system-detected alerts, not user-created reminders"
    ),
):
    """List reminders."""
    user_id = _require_user()
    reminders = asyncio.run(_services().reminders.list_reminders(user_id, status))
    if alerts_only:
        reminders = [r for r in reminders if r.get("alert_type")]
    if emit(reminders):
        return
    if not reminders:
        console.print("[dim]No reminders found.[/dim]")
        return
    table = Table(title="Reminders")
    table.add_column("ID", style="dim")
    table.add_column("Kind")
    table.add_column("Due Date")
    table.add_column("Status")
    table.add_column("Alert Type")
    table.add_column("Severity")
    for r in reminders:
        severity = r.get("severity") or ""
        style = {"critical": "red", "warning": "yellow"}.get(severity, "")
        table.add_row(
            str(r.get("id", ""))[:8],
            r.get("kind", ""),
            str(r.get("due_date", "")),
            r.get("status", ""),
            r.get("alert_type") or "",
            f"[{style}]{severity}[/{style}]" if style else severity,
        )
    console.print(table)


@reminders_app.command("add")
def reminders_add(
    kind: str = typer.Argument(..., help="Reminder kind, e.g. 'quarterly_installment'"),
    due_date: str = typer.Option(..., "--due-date", help="YYYY-MM-DD"),
):
    """Create a reminder."""
    user_id = _require_user()
    reminder_id = asyncio.run(_services().reminders.create_reminder(user_id, kind, due_date))
    emit({"id": reminder_id, "kind": kind, "due_date": due_date})
    console.print(f"[green]Reminder created:[/green] {reminder_id}")


@reminders_app.command("done")
def reminders_done(
    reminder_id: str = typer.Argument(...),
):
    """Mark a reminder as done."""
    user_id = _require_user()
    reminders = asyncio.run(_services().reminders.list_reminders(user_id, None))
    reminder_id = _resolve_id(reminders, reminder_id, "reminder")
    asyncio.run(_services().reminders.mark_done(user_id, reminder_id))
    emit({"id": reminder_id, "status": "done"})
    console.print(f"[green]Reminder marked done:[/green] {reminder_id}")


@reminders_app.command("delete")
def reminders_delete(
    reminder_id: str = typer.Argument(...),
):
    """Delete a reminder."""
    user_id = _require_user()
    reminders = asyncio.run(_services().reminders.list_reminders(user_id, None))
    reminder_id = _resolve_id(reminders, reminder_id, "reminder")
    asyncio.run(_services().reminders.delete_reminder(user_id, reminder_id))
    emit({"id": reminder_id, "deleted": True})
    console.print(f"[green]Reminder deleted:[/green] {reminder_id}")


@reminders_app.command("seed")
def reminders_seed(
    year: str = typer.Option("2025/26", "--year", help="Year of assessment"),
):
    """Seed the standard filing calendar for a year of assessment."""
    user_id = _require_user()
    ids = asyncio.run(_services().reminders.seed_filing_calendar(user_id, year))
    emit({"year": year, "ids": ids})
    console.print(f"[green]Seeded {len(ids)} reminder(s) for {year}.[/green]")


@reminders_app.command("sync-alerts")
def reminders_sync_alerts():
    """Detect current Budget/Subscription/Insurance alert conditions and
    upsert them as reminders. Safe to run repeatedly."""
    import datetime

    user_id = _require_user()
    today = datetime.date.today().isoformat()
    counts = asyncio.run(_services().reminders.sync_alerts(user_id, today))
    if emit(counts):
        return
    if not counts:
        console.print("[dim]No alert conditions detected.[/dim]")
        return
    table = Table(title="Alerts Synced")
    table.add_column("Alert Type")
    table.add_column("Count", justify="right")
    for alert_type, count in counts.items():
        table.add_row(alert_type, str(count))
    console.print(table)


# ── fi ─────────────────────────────────────────────────────────────────────────


@fi_app.command("score")
def fi_score(
    recompute: bool = typer.Option(False, "--recompute", help="Force a fresh computation"),
):
    """Show the latest FI score, or recompute it."""
    user_id = _require_user()
    svc = _services()
    if recompute:
        score = asyncio.run(svc.fi.compute_score(user_id))
    else:
        score = asyncio.run(svc.fi.get_or_compute_score(user_id))
    if emit(score):
        return

    console.print(f"\n[bold]FI Score[/bold]  (pack v{score.get('pack_version')})\n")
    console.print(
        f"  Overall score:        {score.get('overall_score')}  (grade {score.get('grade')})"
    )
    console.print(f"  Monthly income:       LKR {score.get('monthly_income')}")
    console.print(f"  Monthly expenses:     LKR {score.get('monthly_expenses')}")
    console.print(f"  Monthly surplus:      LKR {score.get('monthly_surplus')}")
    console.print(f"  Savings rate:         {score.get('savings_rate')}")
    console.print(f"  FI number:            LKR {score.get('fi_number')}")
    console.print(f"  Net worth:            LKR {score.get('net_worth')}")
    console.print(f"  Progress to FI:       {score.get('progress_to_fi')}")
    console.print(f"  Emergency fund:       {score.get('emergency_fund_months')} months")
    console.print(f"  Projected FI date:    {score.get('projected_fi_date')}\n")

    components = score.get("components") or []
    if components:
        table = Table(title="Score Components")
        table.add_column("Component")
        table.add_column("Score", justify="right")
        table.add_column("Weight", justify="right")
        table.add_column("Detail")
        for c in components:
            table.add_row(
                c.get("label", ""),
                str(c.get("score", "")),
                str(c.get("weight", "")),
                c.get("detail", ""),
            )
        console.print(table)


@fi_app.command("history")
def fi_history():
    """Show FI score history."""
    user_id = _require_user()
    history = asyncio.run(_services().fi.get_score_history(user_id))
    if emit(history):
        return
    if not history:
        console.print("[dim]No score history found.[/dim]")
        return
    table = Table(title="FI Score History")
    table.add_column("Computed At")
    table.add_column("Score", justify="right")
    table.add_column("Net Worth", justify="right")
    for s in history:
        table.add_row(
            str(s.get("created_at", "")), str(s.get("score", "")), str(s.get("net_worth", ""))
        )
    console.print(table)


@fi_app.command("projections")
def fi_projections():
    """Show FI projection scenarios (conservative/base/growth)."""
    user_id = _require_user()
    proj = asyncio.run(_services().fi.get_projections(user_id))
    if emit(proj):
        return

    console.print(f"\n[bold]FI Projections[/bold]  (FI number: LKR {proj.get('fi_number')})\n")
    console.print(f"  FIRE year (conservative): {proj.get('fire_year_conservative')}")
    console.print(f"  FIRE year (base):         {proj.get('fire_year_base')}")
    console.print(f"  FIRE year (growth):       {proj.get('fire_year_growth')}")
    console.print(f"  Current portfolio:        LKR {proj.get('current_portfolio')}\n")

    points = proj.get("points") or []
    if points:
        table = Table(title="Projection by Year")
        table.add_column("Year", justify="right")
        table.add_column("Conservative", justify="right")
        table.add_column("Base", justify="right")
        table.add_column("Growth", justify="right")
        for p in points:
            table.add_row(
                str(p.get("year")),
                p.get("conservative", ""),
                p.get("base", ""),
                p.get("growth", ""),
            )
        console.print(table)


@fi_app.command("surplus")
def fi_surplus():
    """Show the monthly income/expense surplus breakdown."""
    user_id = _require_user()
    breakdown = asyncio.run(_services().fi.get_surplus_breakdown(user_id))
    if emit(breakdown):
        return

    console.print("\n[bold]Surplus Breakdown[/bold]\n")
    console.print(f"  Gross monthly income:    LKR {breakdown.get('gross_monthly_income')}")
    console.print(f"  Gross monthly expenses:  LKR {breakdown.get('gross_monthly_expenses')}")
    console.print(f"  Monthly surplus:         LKR {breakdown.get('monthly_surplus')}")
    console.print(f"  Savings rate:            {breakdown.get('savings_rate')}\n")

    income_by_source = breakdown.get("income_by_source") or {}
    if income_by_source:
        table = Table(title="Income by Source")
        table.add_column("Source")
        table.add_column("Amount", justify="right")
        for source, amount in income_by_source.items():
            table.add_row(source, amount)
        console.print(table)

    expense_by_category = breakdown.get("expense_by_category") or {}
    if expense_by_category:
        table = Table(title="Expenses by Category")
        table.add_column("Category")
        table.add_column("Amount", justify="right")
        for category, amount in expense_by_category.items():
            table.add_row(category, amount)
        console.print(table)


@fi_goals_app.command("list")
def fi_goals_list():
    """List financial goals."""
    user_id = _require_user()
    goals = asyncio.run(_services().fi.list_goals(user_id))
    if emit(goals):
        return
    if not goals:
        console.print("[dim]No goals found. Use 'salli fi goals add' to create one.[/dim]")
        return
    table = Table(title="Financial Goals")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Target", justify="right")
    table.add_column("Earmarked", justify="right")
    table.add_column("Funded", justify="right")
    table.add_column("Progress", justify="right")
    table.add_column("Target Date")
    for g in goals:
        shortfall = g.get("shortfall", "0")
        earmarked = g.get("allocated_amount", "0")
        table.add_row(
            str(g.get("id", ""))[:8],
            g.get("name", ""),
            g.get("kind", ""),
            g.get("target_amount", ""),
            # A gap between earmarked and funded means the accounts backing this
            # goal do not hold what was claimed against them.
            f"[yellow]{earmarked}[/yellow]" if shortfall not in ("0", "") else earmarked,
            g.get("current_amount", ""),
            f"{g.get('progress', 0) * 100:.0f}%",
            str(g.get("target_date", "")),
        )
    console.print(table)


@fi_goals_app.command("add")
def fi_goals_add(
    name: str = typer.Argument(..., help="Goal name"),
    kind: str = typer.Option("custom", "--kind"),
    target_amount: str = typer.Option(None, "--target-amount"),
    target_date: str = typer.Option(None, "--target-date", help="YYYY-MM-DD"),
    priority: int = typer.Option(2, "--priority"),
):
    """Create a financial goal."""
    user_id = _require_user()
    data = {"name": name, "kind": kind, "priority": priority}
    if target_amount is not None:
        data["target_amount"] = target_amount
    if target_date is not None:
        data["target_date"] = target_date
    goal_id = asyncio.run(_services().fi.create_goal(user_id, data))
    emit({"id": goal_id, **data})
    console.print(f"[green]Goal created:[/green] {name} ({goal_id})")


@fi_goals_app.command("update")
def fi_goals_update(
    goal_id: str = typer.Argument(...),
    name: str = typer.Option(None, "--name"),
    target_amount: str = typer.Option(None, "--target-amount"),
    target_date: str = typer.Option(None, "--target-date"),
    priority: int = typer.Option(None, "--priority"),
    is_active: bool = typer.Option(None, "--is-active/--is-inactive"),
):
    """Update fields on an existing goal."""
    user_id = _require_user()
    data = {}
    if name is not None:
        data["name"] = name
    if target_amount is not None:
        data["target_amount"] = target_amount
    if target_date is not None:
        data["target_date"] = target_date
    if priority is not None:
        data["priority"] = priority
    if is_active is not None:
        data["is_active"] = is_active
    if not data:
        console.print("[yellow]Nothing to update.[/yellow]")
        raise typer.Exit(1)
    goals = asyncio.run(_services().fi.list_goals(user_id))
    goal_id = _resolve_id(goals, goal_id, "goal")
    asyncio.run(_services().fi.update_goal(user_id, goal_id, data))
    emit({"id": goal_id, "updated": data})
    console.print(f"[green]Goal updated:[/green] {goal_id}")


@fi_goals_app.command("delete")
def fi_goals_delete(
    goal_id: str = typer.Argument(...),
):
    """Delete a goal."""
    user_id = _require_user()
    goals = asyncio.run(_services().fi.list_goals(user_id))
    goal_id = _resolve_id(goals, goal_id, "goal")
    asyncio.run(_services().fi.delete_goal(user_id, goal_id))
    emit({"id": goal_id, "deleted": True})
    console.print(f"[green]Goal deleted:[/green] {goal_id}")


@fi_goals_app.command("allocate")
def fi_goals_allocate(
    goal_id: str = typer.Argument(..., help="Goal id or unique prefix"),
    account: str = typer.Argument(..., help="Account id, code, or unique name prefix"),
    amount: str = typer.Argument(..., help="How much of that account is for this goal; 0 clears"),
):
    """
    Earmark part of an account for a goal.

    Progress is derived from what the account actually holds, so it moves when
    money moves. One account can back several goals — if their claims exceed the
    balance, the goals' priority decides who stays funded.
    """
    from decimal import Decimal

    user_id = _require_user()
    goals = asyncio.run(_services().fi.list_goals(user_id))
    goal_id = _resolve_id(goals, goal_id, "goal")

    accounts = asyncio.run(_services().ledger.list_accounts(user_id))
    match = next(
        (a for a in accounts if a.id == account or a.code == account),
        None,
    ) or next((a for a in accounts if a.name.lower().startswith(account.lower())), None)
    if match is None:
        console.print(f"[red]No account matching '{account}'.[/red]")
        raise typer.Exit(1)

    asyncio.run(_services().fi.set_allocation(user_id, goal_id, match.id, Decimal(amount)))
    emit({"goal_id": goal_id, "account_id": match.id, "amount": Decimal(amount)})
    if Decimal(amount) <= 0:
        console.print(f"[green]Cleared[/green] {match.name} from this goal.")
    else:
        console.print(f"[green]Earmarked[/green] {amount} of {match.name} for this goal.")

    for g in asyncio.run(_services().fi.list_goals(user_id)):
        if g["id"] == goal_id:
            console.print(
                f"  {g['name']}: earmarked {g['allocated_amount']}, "
                f"actually funded {g['current_amount']} "
                f"({g['progress'] * 100:.0f}% of {g['target_amount']})"
            )
            if g["shortfall"] not in ("0", ""):
                console.print(
                    f"  [yellow]Shortfall {g['shortfall']}[/yellow] — the accounts "
                    "backing this goal do not hold what has been claimed against them."
                )


@fi_strategy_app.command("show")
def fi_strategy_show():
    """Show the current FIRE strategy."""
    user_id = _require_user()
    strategy = asyncio.run(_services().fi.get_strategy(user_id))
    if emit(strategy):
        return
    if not strategy:
        console.print(
            "[dim]No strategy found. Use 'salli fi strategy generate' to create one.[/dim]"
        )
        return
    _print_strategy(strategy)


@fi_strategy_app.command("history")
def fi_strategy_history():
    """Show past FIRE strategy versions."""
    user_id = _require_user()
    history = asyncio.run(_services().fi.get_strategy_history(user_id))
    if emit(history):
        return
    if not history:
        console.print("[dim]No strategy history found.[/dim]")
        return
    table = Table(title="Strategy History")
    table.add_column("Version", justify="right")
    table.add_column("Style")
    table.add_column("Created At")
    for s in history:
        table.add_row(
            str(s.get("version", "")), s.get("fire_style", ""), str(s.get("created_at", ""))
        )
    console.print(table)


@fi_strategy_app.command("generate")
def fi_strategy_generate():
    """Generate a new AI-assisted FIRE strategy (streams progress)."""
    user_id = _require_user()
    svc = _services()

    async def _run():
        strategy = None
        async for chunk in svc.fi.generate_strategy(user_id):
            if not chunk.startswith("data: "):
                continue
            import json

            payload = json.loads(chunk[len("data: ") :].strip())
            if payload.get("type") == "status":
                console.print(f"[dim]  ▸ {payload.get('message', '')}[/dim]")
            elif payload.get("type") == "done":
                strategy = payload.get("strategy")
        return strategy

    strategy = asyncio.run(_run())
    if emit(strategy):
        return
    if strategy:
        console.print()
        _print_strategy(strategy)
    else:
        console.print("[yellow]No strategy generated.[/yellow]")


def _print_strategy(strategy: dict) -> None:
    console.print(
        f"\n[bold]FIRE Strategy[/bold]  (v{strategy.get('version')}, {strategy.get('fire_style')})\n"
    )
    console.print(f"  SWR:                      {strategy.get('swr')}")
    console.print(f"  Return (conservative):    {strategy.get('return_conservative')}")
    console.print(f"  Return (base):            {strategy.get('return_base')}")
    console.print(f"  Return (growth):          {strategy.get('return_growth')}")
    console.print(f"  Target monthly expenses:  {strategy.get('target_monthly_expenses')}")
    console.print(f"  Target age:               {strategy.get('target_age')}\n")

    buckets = strategy.get("buckets") or []
    if buckets:
        table = Table(title="Allocation Buckets")
        table.add_column("Bucket")
        table.add_column("Target %", justify="right")
        table.add_column("Description")
        for b in buckets:
            table.add_row(b.get("name", ""), f"{b.get('target_pct', '')}", b.get("description", ""))
        console.print(table)

    if strategy.get("ai_rationale"):
        console.print(f"\n[dim]{strategy['ai_rationale']}[/dim]")


@fi_app.command("simulate-purchase")
def fi_simulate_purchase(
    amount: str = typer.Argument(..., help="Purchase price, e.g. 450000"),
    term_months: int = typer.Option(None, "--term-months", help="Pay in instalments over N months"),
    annual_interest_rate: str = typer.Option(
        "0", "--rate", help="Annual rate as a fraction, e.g. 0.18 for 18%"
    ),
):
    """What a purchase costs you in months of freedom — cash vs. instalments."""
    from decimal import Decimal, InvalidOperation

    user_id = _require_user()
    try:
        price, rate = Decimal(amount), Decimal(annual_interest_rate)
    except InvalidOperation:
        console.print("[red]Amount and rate must be numbers.[/red]")
        raise typer.Exit(1)
    if not 0 <= rate <= 1:
        console.print("[red]--rate is a fraction: 0.18 means 18%.[/red]")
        raise typer.Exit(1)
    impact = asyncio.run(
        _services().fi.simulate_purchase(
            user_id, price, term_months=term_months, annual_interest_rate=rate
        )
    )
    if emit(impact):
        return
    for key, value in impact.items():
        console.print(f"  {key}: {value}")


@fi_goals_app.command("allocations")
def fi_goals_allocations(goal_id: str = typer.Argument(...)):
    """Which accounts back a goal, and how much of each."""
    user_id = _require_user()
    allocations = asyncio.run(_services().fi.list_allocations(user_id, goal_id))
    if emit(allocations):
        return
    table = Table(title="Allocations")
    table.add_column("Account")
    table.add_column("Allocated", justify="right")
    for a in allocations:
        table.add_row(str(a.get("account_id", "")), str(a.get("allocated_amount", "")))
    console.print(table)


# ── advisor ────────────────────────────────────────────────────────────────────


@advisor_app.command("run")
def advisor_run(
    trigger: str = typer.Option("manual", "--trigger"),
):
    """Run the Wealth Advisor and generate a fresh report."""
    user_id = _require_user()
    try:
        report = asyncio.run(_services().advisor.run_advisor(user_id, trigger=trigger))
    except Exception as e:  # e.g. the deployment's usage meter refused the run
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    if emit(report):
        return
    _print_advisor_report(report)


@advisor_reports_app.command("list")
def advisor_reports_list():
    """List past advisor reports."""
    user_id = _require_user()
    reports = asyncio.run(_services().advisor.list_reports(user_id))
    if emit(reports):
        return
    if not reports:
        console.print("[dim]No advisor reports found.[/dim]")
        return
    table = Table(title="Advisor Reports")
    table.add_column("ID", style="dim")
    table.add_column("Trigger")
    table.add_column("Created At")
    for r in reports:
        table.add_row(str(r.get("id", ""))[:8], r.get("trigger", ""), str(r.get("created_at", "")))
    console.print(table)


@advisor_reports_app.command("latest")
def advisor_reports_latest():
    """Show the most recent advisor report."""
    user_id = _require_user()
    report = asyncio.run(_services().advisor.get_latest_report(user_id))
    if emit(report):
        return
    if not report:
        console.print(
            "[dim]No advisor report found. Use 'salli advisor run' to generate one.[/dim]"
        )
        return
    _print_advisor_report(report)


def _print_advisor_report(report: dict) -> None:
    console.print(f"\n[bold]Advisor Report[/bold]  ({report.get('id')})\n")
    console.print(f"  {report.get('summary', '')}\n")
    if report.get("fire_tier_assessment"):
        console.print(f"  [dim]{report['fire_tier_assessment']}[/dim]\n")

    recs = report.get("recommendations") or []
    if recs:
        table = Table(title="Recommendations")
        table.add_column("ID", style="dim")
        table.add_column("Title")
        table.add_column("Category")
        table.add_column("Status")
        for rec in recs:
            table.add_row(
                str(rec.get("id", ""))[:8],
                rec.get("title", ""),
                rec.get("category", ""),
                rec.get("status", ""),
            )
        console.print(table)


def _resolve_report_and_rec_id(user_id: str, report_id: str, rec_id: str) -> tuple[str, str]:
    reports = asyncio.run(_services().advisor.list_reports(user_id))
    report_id = _resolve_id(reports, report_id, "report")
    report = next(r for r in reports if r["id"] == report_id)
    rec_id = _resolve_id(report.get("recommendations") or [], rec_id, "recommendation")
    return report_id, rec_id


@advisor_app.command("apply")
def advisor_apply(
    report_id: str = typer.Argument(...),
    rec_id: str = typer.Argument(...),
):
    """Apply a recommendation from an advisor report."""
    user_id = _require_user()
    report_id, rec_id = _resolve_report_and_rec_id(user_id, report_id, rec_id)
    try:
        result = asyncio.run(_services().advisor.apply_recommendation(user_id, report_id, rec_id))
        emit(result)
        console.print(f"[green]Recommendation applied:[/green] {result.get('id')}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@advisor_app.command("dismiss")
def advisor_dismiss(
    report_id: str = typer.Argument(...),
    rec_id: str = typer.Argument(...),
):
    """Dismiss a recommendation from an advisor report."""
    user_id = _require_user()
    report_id, rec_id = _resolve_report_and_rec_id(user_id, report_id, rec_id)
    try:
        result = asyncio.run(_services().advisor.dismiss_recommendation(user_id, report_id, rec_id))
        emit(result)
        console.print(f"[green]Recommendation dismissed:[/green] {result.get('id')}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@advisor_app.command("briefing")
def advisor_briefing(
    thread_id: str = typer.Option(None, "--thread-id", help="Resume an existing briefing thread"),
):
    """Run the monthly financial-health briefing workflow (pauses for review before persisting)."""
    user_id = _require_user()

    async def _run():
        async with _agent_services() as svc:
            result = await svc.agent.prepare_briefing(user_id, email=None, thread_id=thread_id)
            tid = result.get("thread_id", "")

            if result.get("error"):
                console.print(f"[yellow]{result['error']}[/yellow]")
                return

            briefing = result.get("briefing", {})
            console.print(f"\n[bold]Monthly Briefing[/bold]  (thread: {tid})\n")
            console.print(f"  {briefing.get('summary', '')}\n")
            console.print(f"  [dim]{briefing.get('fire_tier_assessment', '')}[/dim]\n")

            recs = briefing.get("recommendations") or []
            if recs:
                table = Table(title="Recommendations")
                table.add_column("Priority", justify="right")
                table.add_column("Title")
                table.add_column("Rationale")
                for r in recs:
                    table.add_row(
                        str(r.get("priority", "")), r.get("title", ""), r.get("rationale", "")
                    )
                console.print(table)

            console.print(
                "\nApprove this briefing? "
                "[[green]approve[/green]/[yellow]edit[/yellow]/[red]reject[/red]]"
            )
            decision = input("> ").strip().lower()
            if decision not in ("approve", "edit", "reject"):
                decision = "reject"

            final = await svc.agent.resume_briefing(tid, decision)
            if final.get("error"):
                console.print(f"[yellow]{final['error']}[/yellow]")
            else:
                console.print("\n[bold green]Briefing saved as an advisory report.[/bold green]")
                console.print(f"  Report ID: {final.get('report', {}).get('id')}")

    asyncio.run(_run())


@advisor_app.command("daily-briefing")
def advisor_daily_briefing(
    enable: bool = typer.Option(None, "--on/--off", help="Switch the daily run on or off"),
):
    """Show, or switch on/off, the scheduled daily advisor run."""
    user_id = _require_user()

    async def run() -> bool:
        svc = _services()
        if enable is not None:
            await svc.advisor.set_daily_briefing_enabled(user_id, enable)
        return await svc.advisor.get_daily_briefing_enabled(user_id)

    enabled = asyncio.run(run())
    if emit({"enabled": enabled}):
        return
    console.print(f"Daily briefing: {'on' if enabled else 'off'}")


@advisor_app.command("run-due")
def advisor_run_due():
    """Run the advisor for every opted-in user due today. For a system cron job
    (the API's /advisor/cron/run-due does the same over HTTP)."""
    from salli.domain.usage import UsageLimitReached

    ran: list[str] = []
    refused: list[str] = []
    failed: list[str] = []

    async def run() -> list[dict[str, str]]:
        svc = _services()
        due = await svc.advisor.due_users()
        for user in due:
            try:
                await svc.advisor.run_advisor(user["user_id"], None, trigger="scheduled")
                ran.append(user["user_id"])
            except UsageLimitReached:
                refused.append(user["user_id"])
            except Exception as exc:
                console.print(f"[red]{user['user_id']}: {type(exc).__name__}[/red]")
                failed.append(user["user_id"])
        return due

    due = asyncio.run(run())
    emit({"due": len(due), "ran": ran, "refused": refused, "failed": failed})
    console.print(
        f"Due: {len(due)} · ran {len(ran)} · refused {len(refused)} · failed {len(failed)}"
    )


# ── documents ──────────────────────────────────────────────────────────────────


@documents_app.command("list")
def documents_list(
    namespace: str = typer.Option(None, "--namespace"),
    search: str = typer.Option(None, "--search"),
):
    """List uploaded documents."""
    user_id = _require_user()
    docs = asyncio.run(
        _services().documents.list_documents(user_id, namespace=namespace, search=search)
    )
    if emit(docs):
        return
    if not docs:
        console.print("[dim]No documents found.[/dim]")
        return
    table = Table(title="Documents")
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Namespace")
    table.add_column("MIME Type")
    table.add_column("Created At")
    for d in docs:
        table.add_row(
            str(d.get("id", ""))[:8],
            d.get("title", ""),
            d.get("namespace", ""),
            d.get("mime_type", ""),
            str(d.get("created_at", "")),
        )
    console.print(table)


@documents_app.command("show")
def documents_show(
    doc_id: str = typer.Argument(...),
):
    """Show a document's details."""
    user_id = _require_user()
    docs = asyncio.run(_services().documents.list_documents(user_id))
    doc_id = _resolve_id(docs, doc_id, "document")
    doc = asyncio.run(_services().documents.get_document(user_id, doc_id))
    if not doc:
        console.print(f"[red]Document not found:[/red] {doc_id}")
        raise typer.Exit(1)
    if emit(doc):
        return
    for key, value in doc.items():
        console.print(f"  {key:<16} {value}")


@documents_app.command("delete")
def documents_delete(
    doc_id: str = typer.Argument(...),
):
    """Delete a document."""
    user_id = _require_user()
    docs = asyncio.run(_services().documents.list_documents(user_id))
    doc_id = _resolve_id(docs, doc_id, "document")
    asyncio.run(_services().documents.delete_document(user_id, doc_id))
    emit({"id": doc_id, "deleted": True})
    console.print(f"[green]Document deleted:[/green] {doc_id}")


@documents_app.command("upload")
def documents_upload(file: str = typer.Argument(..., help="Path to a file (PDF, image, CSV…)")):
    """Store a file, e.g. a receipt to attach to an entry (`entry add --receipt`)."""
    import mimetypes
    from pathlib import Path

    user_id = _require_user()
    path = Path(file)
    if not path.is_file():
        console.print(f"[red]No such file:[/red] {file}")
        raise typer.Exit(1)
    doc = asyncio.run(
        _services().documents.save_file(
            user_id,
            filename=path.name,
            file_bytes=path.read_bytes(),
            mime_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )
    )
    emit({"id": doc["id"], "name": doc["title"], "mime_type": doc["mime_type"]})
    console.print(f"[green]Stored:[/green] {doc['title']} ({doc['id']})")


# ── agent ─────────────────────────────────────────────────────────────────────


@agent_app.command("chat")
def agent_chat(
    thread_id: str = typer.Option(None, "--thread-id", help="Continue a prior conversation"),
):
    """
    Start an interactive Tax Agent REPL (streamed responses).
    Type 'quit' or press Ctrl-C to exit.
    """
    _run_agent_chat(None, thread_id=thread_id)


@agent_app.command("sessions")
def agent_sessions(
    limit: int = typer.Option(50, "--limit"),
):
    """List past chat sessions."""
    user_id = _require_user()
    sessions = asyncio.run(_services().agent.list_sessions(user_id, limit))
    if emit(sessions):
        return
    if not sessions:
        console.print("[dim]No chat sessions found.[/dim]")
        return
    table = Table(title="Chat Sessions")
    table.add_column("Thread ID", style="dim")
    table.add_column("Title")
    table.add_column("Last Active")
    for s in sessions:
        table.add_row(
            str(s.get("thread_id", ""))[:8],
            s.get("title", ""),
            str(s.get("last_active_at", "")),
        )
    console.print(table)


@agent_app.command("audit-log")
def agent_audit_log(
    limit: int = typer.Option(100, "--limit"),
):
    """Show every agent-initiated write decision (approved or denied)."""
    user_id = _require_user()
    entries = asyncio.run(_services().agent.get_audit_log(user_id, limit))
    if emit(entries):
        return
    if not entries:
        console.print("[dim]No audit log entries found.[/dim]")
        return
    table = Table(title="Agent Write Audit Log")
    table.add_column("When")
    table.add_column("Action")
    table.add_column("Decision")
    table.add_column("Params")
    for e in entries:
        style = "green" if e.get("decision") == "approved" else "red"
        table.add_row(
            str(e.get("created_at", "")),
            e.get("action", ""),
            f"[{style}]{e.get('decision', '')}[/{style}]",
            str(e.get("params", {}))[:60],
        )
    console.print(table)


@agent_app.command("history")
def agent_history(
    thread_id: str = typer.Argument(..., help="Thread ID to show the conversation for"),
):
    """Print the full message history for a chat thread."""
    user_id = _require_user()

    async def _run():
        async with _agent_services() as svc:
            sessions = await svc.agent.list_sessions(user_id, 1000)
            resolved = _resolve_id([{"id": s["thread_id"]} for s in sessions], thread_id, "thread")
            return await svc.agent.get_history(user_id, resolved)

    history = asyncio.run(_run())
    if emit(history):
        return
    if not history:
        console.print("[dim]No history found for that thread.[/dim]")
        return

    def _print_part(part: dict, indent: str = "  ") -> None:
        part_type = part.get("type")
        if part_type in ("text", "token"):
            console.print(f"{indent}{part.get('content', '')}")
        elif part_type == "tool_call":
            console.print(f"{indent}[dim]▸ {part.get('name', '')}[/dim]")
        elif part_type == "subagent_section":
            console.print(f"{indent}[dim]▸ subagent: {part.get('agent', '')}[/dim]")
            for sub_part in part.get("parts", []):
                _print_part(sub_part, indent=indent + "  ")

    for msg in history:
        role = msg.get("role", "")
        if role == "user":
            console.print(f"\n[bold cyan]You:[/bold cyan] {msg.get('content', '')}")
        else:
            console.print("\n[bold green]Salli:[/bold green]")
            for part in msg.get("parts", []):
                _print_part(part)


@agent_app.command("resume")
def agent_resume(
    thread_id: str = typer.Argument(..., help="Thread ID to continue chatting in"),
):
    """Resume an interactive chat REPL in an existing thread."""
    user_id = _require_user()

    async def _resolve() -> str:
        async with _agent_services() as svc:
            sessions = await svc.agent.list_sessions(user_id, 1000)
            return _resolve_id([{"id": s["thread_id"]} for s in sessions], thread_id, "thread")

    resolved_thread_id = asyncio.run(_resolve())
    _run_agent_chat(None, thread_id=resolved_thread_id)


def _run_agent_chat(priming_message: str | None, thread_id: str | None = None):
    import uuid

    user_id = _require_user()

    if thread_id is None:
        thread_id = str(uuid.uuid4())

    console.print(
        f"\n[bold cyan]Salli Tax Agent[/bold cyan]  (thread: {thread_id})\n"
        "[dim]Type your question. 'quit' to exit.[/dim]\n"
    )

    async def _stream_one(svc, msg: str) -> None:
        console.print("[bold green]Salli:[/bold green] ", end="")
        async for event_type, payload in svc.agent.stream_chat(user_id, msg, thread_id=thread_id):
            if event_type == "token":
                console.print(payload, end="")
            elif event_type == "tool_call":
                console.print(f"\n[dim]  ▸ {payload.get('name')}…[/dim]", end="")
            elif event_type == "interrupt":
                console.print(f"\n[yellow]  ⏸ Review required: {payload}[/yellow]")
            elif event_type in ("done", "error"):
                break
        console.print()

    async def _run() -> None:
        async with _agent_services() as svc:
            if priming_message:
                await _stream_one(svc, priming_message)

            while True:
                try:
                    user_input = input("\nYou: ").strip()
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[dim]Goodbye.[/dim]")
                    break
                if user_input.lower() in ("quit", "exit", "q"):
                    console.print("[dim]Goodbye.[/dim]")
                    break
                if not user_input:
                    continue
                await _stream_one(svc, user_input)

    asyncio.run(_run())


@agent_app.command("delete-session")
def agent_delete_session(thread_id: str = typer.Argument(...)):
    """Delete a conversation."""
    user_id = _require_user()
    asyncio.run(_services().agent.delete_session(user_id=user_id, thread_id=thread_id))
    emit({"thread_id": thread_id, "deleted": True})
    console.print(f"[green]Conversation deleted:[/green] {thread_id}")


# ── profile ───────────────────────────────────────────────────────────────────


@profile_app.command("show")
def profile_show():
    """Show the fact-find profile: identity, risk profile, life stage."""
    user_id = _require_user()
    profile = asyncio.run(_services().profile.get_profile(user_id))
    if emit(profile):
        return
    for key, value in profile.items():
        console.print(f"  {key:<20} {value}")


@profile_app.command("update")
def profile_update(
    display_name: str = typer.Option(None, "--display-name"),
    date_of_birth: str = typer.Option(None, "--date-of-birth", help="YYYY-MM-DD"),
    dependents_count: int = typer.Option(None, "--dependents-count"),
    employment_status: str = typer.Option(
        None, "--employment-status", help="employed|self_employed|unemployed|student|retired"
    ),
    employment_type: str = typer.Option(
        None, "--employment-type", help="permanent|contract|self_employed|other"
    ),
    residency_status: str = typer.Option(None, "--residency-status", help="resident|non_resident"),
    employer: str = typer.Option(None, "--employer"),
    ird_number: str = typer.Option(None, "--ird-number"),
):
    """Update identity fields on the fact-find profile."""
    user_id = _require_user()
    data: dict[str, object] = {}
    if display_name is not None:
        data["display_name"] = display_name
    if date_of_birth is not None:
        data["date_of_birth"] = date_of_birth
    if dependents_count is not None:
        data["dependents_count"] = dependents_count
    if employment_status is not None:
        data["employment_status"] = employment_status
    if employment_type is not None:
        data["employment_type"] = employment_type
    if residency_status is not None:
        data["residency_status"] = residency_status
    if employer is not None:
        data["employer"] = employer
    if ird_number is not None:
        data["ird_number"] = ird_number
    if not data:
        console.print("[yellow]Nothing to update.[/yellow]")
        raise typer.Exit(1)
    asyncio.run(_services().profile.update_identity(user_id, data))
    emit({"updated": data})
    console.print("[green]Profile updated.[/green]")


@profile_app.command("risk-questionnaire")
def profile_risk_questionnaire(
    time_horizon_years: int = typer.Option(..., "--time-horizon-years"),
    drawdown_reaction: str = typer.Option(
        ..., "--drawdown-reaction", help="sell_all|sell_some|hold|buy_more"
    ),
    income_stability: str = typer.Option(
        ..., "--income-stability", help="unstable|moderate|stable"
    ),
    investment_experience: str = typer.Option(
        ..., "--investment-experience", help="none|some|experienced"
    ),
    dependents_count: int = typer.Option(0, "--dependents-count"),
):
    """Submit the risk-tolerance questionnaire and persist the scored result."""
    user_id = _require_user()
    result = asyncio.run(
        _services().profile.submit_risk_questionnaire(
            user_id,
            {
                "time_horizon_years": time_horizon_years,
                "drawdown_reaction": drawdown_reaction,
                "income_stability": income_stability,
                "investment_experience": investment_experience,
                "dependents_count": dependents_count,
            },
        )
    )
    if emit(result):
        return
    console.print(f"\n[bold]Risk score:[/bold] {result['score']} ({result['category']})\n")
    for key, points in result["breakdown"].items():
        console.print(f"  {key:<24} {points}")


@profile_app.command("balance-sheet")
def profile_balance_sheet(
    balance: list[str] = typer.Option(..., "--balance", help="CODE:NAME:TYPE:AMOUNT (repeat)"),
):
    """Declare opening balances — posts real journal entries (asset|liability)."""
    user_id = _require_user()
    items = []
    for raw in balance:
        try:
            code, name, type_, amount = raw.split(":", 3)
        except ValueError:
            console.print(f"[red]Invalid format '{raw}'. Use CODE:NAME:TYPE:AMOUNT[/red]")
            raise typer.Exit(1)
        items.append({"code": code, "name": name, "type": type_, "amount": amount})
    entry_ids = asyncio.run(_services().profile.declare_opening_balances(user_id, items))
    emit({"entry_ids": entry_ids})
    console.print(f"[green]Posted {len(entry_ids)} opening-balance entry(ies).[/green]")


@profile_app.command("income")
def profile_income(
    income: list[str] = typer.Option(..., "--income", help="CODE:NAME:AMOUNT (repeat)"),
    deposit_account_code: str = typer.Option("1200", "--deposit-account-code"),
    deposit_account_name: str = typer.Option("Bank Account", "--deposit-account-name"),
):
    """Declare income sources — posts one representative monthly entry each."""
    user_id = _require_user()
    items = []
    for raw in income:
        try:
            code, name, amount = raw.split(":", 2)
        except ValueError:
            console.print(f"[red]Invalid format '{raw}'. Use CODE:NAME:AMOUNT[/red]")
            raise typer.Exit(1)
        items.append(
            {
                "code": code,
                "name": name,
                "amount": amount,
                "deposit_account_code": deposit_account_code,
                "deposit_account_name": deposit_account_name,
            }
        )
    entry_ids = asyncio.run(_services().profile.declare_income(user_id, items))
    emit({"entry_ids": entry_ids})
    console.print(f"[green]Posted {len(entry_ids)} income entry(ies).[/green]")


@profile_app.command("export")
def profile_export(
    output: str = typer.Option(..., "--output", "-o", help="Output JSON file path"),
):
    """Export everything Salli has stored about you as one JSON document."""
    import json

    user_id = _require_user()
    data = asyncio.run(_services().data_portability.export_all(user_id))
    with open(output, "w") as f:
        json.dump(data, f, indent=2, default=str)
    emit({"path": str(output)})
    console.print(f"[green]Exported account data to:[/green] {output}")


@profile_app.command("delete-account")
def profile_delete_account(
    confirm: bool = typer.Option(
        False, "--confirm", help="Skip the interactive confirmation prompt"
    ),
):
    """Permanently delete every row belonging to your account. Irreversible."""
    user_id = _require_user()
    if not confirm:
        typed = typer.prompt(
            f"This will permanently delete ALL data for '{user_id}'. Type the user id to confirm"
        )
        if typed.strip() != user_id:
            console.print("[yellow]Confirmation did not match. Aborted.[/yellow]")
            raise typer.Exit(1)
    counts = asyncio.run(_services().data_portability.delete_account(user_id))
    total = sum(counts.values())
    emit({"total": total, "tables": counts})
    console.print(f"[red]Deleted {total} row(s) across {len(counts)} table(s).[/red]")
    for table, count in counts.items():
        if count:
            console.print(f"  {table:<28} {count}")


# ── budget ────────────────────────────────────────────────────────────────────


@budget_app.command("list")
def budget_list():
    """List budgets."""
    user_id = _require_user()
    budgets = asyncio.run(_services().budget.list_budgets(user_id))
    if emit(budgets):
        return
    if not budgets:
        console.print("[dim]No budgets found. Use 'salli budget add' to create one.[/dim]")
        return
    table = Table(title="Budgets")
    table.add_column("ID", style="dim")
    table.add_column("Period Start")
    table.add_column("Period End")
    table.add_column("Categories", justify="right")
    for b in budgets:
        table.add_row(
            str(b.get("id", ""))[:8],
            b.get("period_start", ""),
            b.get("period_end", ""),
            str(len(b.get("lines", []))),
        )
    console.print(table)


@budget_app.command("add")
def budget_add(
    period_start: str = typer.Option(..., "--period-start", help="YYYY-MM-DD"),
    period_end: str = typer.Option(..., "--period-end", help="YYYY-MM-DD"),
    line: list[str] = typer.Option(
        ..., "--line", help="ACCOUNT_ID:LIMIT_AMOUNT (repeat for multiple categories)"
    ),
):
    """Create a budget for a period with per-category (expense account) limits."""
    user_id = _require_user()
    lines = []
    for raw in line:
        try:
            account_id, limit_amount = raw.rsplit(":", 1)
        except ValueError:
            console.print(f"[red]Invalid format '{raw}'. Use ACCOUNT_ID:LIMIT_AMOUNT[/red]")
            raise typer.Exit(1)
        lines.append({"account_id": account_id.strip(), "limit_amount": limit_amount.strip()})
    budget_id = asyncio.run(
        _services().budget.create_budget(user_id, period_start, period_end, lines)
    )
    emit({"id": budget_id, "period_start": period_start, "period_end": period_end, "lines": lines})
    console.print(f"[green]Budget created:[/green] {budget_id}")


@budget_app.command("summary")
def budget_summary(
    budget_id: str = typer.Argument(..., help="Budget ID"),
):
    """Show category limits vs. actual ledger spend for a budget's period."""
    from decimal import Decimal

    user_id = _require_user()
    budgets = asyncio.run(_services().budget.list_budgets(user_id))
    budget_id = _resolve_id(budgets, budget_id, "budget")
    summary = asyncio.run(_services().budget.get_summary(user_id, budget_id))
    if summary is None:
        console.print(f"[red]Budget not found:[/red] {budget_id}")
        raise typer.Exit(1)
    if emit(summary):
        return

    console.print(
        f"\n[bold]Budget Summary[/bold]  {summary['period_start']} → {summary['period_end']}\n"
    )
    table = Table(title="Category Limits")
    table.add_column("Category")
    table.add_column("Limit", justify="right")
    table.add_column("Actual", justify="right")
    table.add_column("Variance", justify="right")
    for line in summary["lines"]:
        variance = Decimal(line["variance"])
        style = "red" if variance < 0 else "green"
        table.add_row(
            line["category"],
            f"{Decimal(line['limit_amount']):,.2f}",
            f"{Decimal(line['actual_amount']):,.2f}",
            f"[{style}]{variance:,.2f}[/{style}]",
        )
    console.print(table)
    console.print(f"\n  Total limit:    LKR {Decimal(summary['total_limit']):>16,.2f}")
    console.print(f"  Total actual:   LKR {Decimal(summary['total_actual']):>16,.2f}")
    console.print(f"  Total variance: LKR {Decimal(summary['total_variance']):>16,.2f}\n")


@budget_app.command("delete")
def budget_delete(
    budget_id: str = typer.Argument(...),
):
    """Delete a budget."""
    user_id = _require_user()
    budgets = asyncio.run(_services().budget.list_budgets(user_id))
    budget_id = _resolve_id(budgets, budget_id, "budget")
    asyncio.run(_services().budget.delete_budget(user_id, budget_id))
    emit({"id": budget_id, "deleted": True})
    console.print(f"[green]Budget deleted:[/green] {budget_id}")


@budget_app.command("show")
def budget_show(budget_id: str = typer.Argument(...)):
    """Show one budget."""
    user_id = _require_user()
    item = asyncio.run(_services().budget.get_budget(user_id, budget_id))
    if item is None:
        console.print(f"[red]Budget not found:[/red] {budget_id}")
        raise typer.Exit(1)
    if emit(item):
        return
    for key, value in item.items():
        console.print(f"  {key}: {value}")


@budget_app.command("update")
def budget_update(
    budget_id: str = typer.Argument(...),
    period_start: str = typer.Option(None, "--period-start", help="YYYY-MM-DD"),
    period_end: str = typer.Option(None, "--period-end", help="YYYY-MM-DD"),
    line: list[str] = typer.Option(
        None, "--line", help="ACCOUNT_ID:LIMIT_AMOUNT (repeat; replaces all lines)"
    ),
):
    """Change a budget's period or replace its category limits."""
    user_id = _require_user()
    data: dict[str, Any] = {}
    if period_start:
        data["period_start"] = period_start
    if period_end:
        data["period_end"] = period_end
    if line:
        lines = []
        for raw in line:
            try:
                account_id, limit_amount = raw.rsplit(":", 1)
            except ValueError:
                console.print(f"[red]Invalid format '{raw}'. Use ACCOUNT_ID:LIMIT_AMOUNT[/red]")
                raise typer.Exit(1)
            lines.append({"account_id": account_id.strip(), "limit_amount": limit_amount.strip()})
        data["lines"] = lines
    if not data:
        console.print("[red]Nothing to update.[/red]")
        raise typer.Exit(1)
    asyncio.run(_services().budget.update_budget(user_id, budget_id, data))
    emit({"id": budget_id, "updated": data})
    console.print(f"[green]Budget updated:[/green] {budget_id}")


# ── debt ──────────────────────────────────────────────────────────────────────


@debt_app.command("list")
def debt_list(
    all: bool = typer.Option(False, "--all", help="Include inactive debts"),
):
    """List debts."""
    user_id = _require_user()
    debts = asyncio.run(_services().debt.list_debts(user_id, active_only=not all))
    if emit(debts):
        return
    if not debts:
        console.print("[dim]No debts found. Use 'salli debt add' to create one.[/dim]")
        return
    table = Table(title="Debts")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Principal", justify="right")
    table.add_column("APR", justify="right")
    table.add_column("Min. Payment", justify="right")
    for d in debts:
        table.add_row(
            str(d.get("id", ""))[:8],
            d.get("name", ""),
            d.get("principal", ""),
            f"{float(d.get('apr', 0)) * 100:.2f}%",
            d.get("minimum_payment", ""),
        )
    console.print(table)


@debt_app.command("add")
def debt_add(
    name: str = typer.Argument(..., help="Debt name, e.g. 'Credit Card'"),
    principal: str = typer.Option(..., "--principal", help="Outstanding balance"),
    apr: str = typer.Option(..., "--apr", help="Annual percentage rate, e.g. 0.18 for 18%"),
    minimum_payment: str = typer.Option(..., "--minimum-payment"),
):
    """Add a structured debt."""
    user_id = _require_user()
    debt_id = asyncio.run(
        _services().debt.add_debt(
            user_id,
            {"name": name, "principal": principal, "apr": apr, "minimum_payment": minimum_payment},
        )
    )
    emit({"id": debt_id, "name": name})
    console.print(f"[green]Debt created:[/green] {name} ({debt_id})")


@debt_app.command("update")
def debt_update(
    debt_id: str = typer.Argument(...),
    name: str = typer.Option(None, "--name"),
    principal: str = typer.Option(None, "--principal"),
    apr: str = typer.Option(None, "--apr"),
    minimum_payment: str = typer.Option(None, "--minimum-payment"),
    active: bool = typer.Option(None, "--active/--inactive"),
):
    """Update fields on an existing debt."""
    user_id = _require_user()
    data: dict[str, object] = {}
    if name is not None:
        data["name"] = name
    if principal is not None:
        data["principal"] = principal
    if apr is not None:
        data["apr"] = apr
    if minimum_payment is not None:
        data["minimum_payment"] = minimum_payment
    if active is not None:
        data["is_active"] = active
    if not data:
        console.print("[yellow]Nothing to update.[/yellow]")
        raise typer.Exit(1)
    debts = asyncio.run(_services().debt.list_debts(user_id, active_only=False))
    debt_id = _resolve_id(debts, debt_id, "debt")
    asyncio.run(_services().debt.update_debt(user_id, debt_id, data))
    emit({"id": debt_id, "updated": data})
    console.print(f"[green]Debt updated:[/green] {debt_id}")


@debt_app.command("delete")
def debt_delete(
    debt_id: str = typer.Argument(...),
):
    """Delete a debt."""
    user_id = _require_user()
    debts = asyncio.run(_services().debt.list_debts(user_id, active_only=False))
    debt_id = _resolve_id(debts, debt_id, "debt")
    asyncio.run(_services().debt.delete_debt(user_id, debt_id))
    emit({"id": debt_id, "deleted": True})
    console.print(f"[green]Debt deleted:[/green] {debt_id}")


@debt_app.command("payoff-plan")
def debt_payoff_plan(
    extra_monthly_payment: str = typer.Option("0", "--extra", help="Extra monthly payment"),
    strategy: str = typer.Option(
        "avalanche",
        "--strategy",
        help="avalanche (highest APR first) or snowball (smallest balance first)",
    ),
):
    """Show the avalanche/snowball payoff plan for all active debts."""
    from decimal import Decimal

    if strategy not in ("avalanche", "snowball"):
        console.print(f"[red]Invalid strategy '{strategy}'. Use avalanche or snowball.[/red]")
        raise typer.Exit(1)

    user_id = _require_user()
    plan = asyncio.run(
        _services().debt.get_payoff_plan(user_id, Decimal(extra_monthly_payment), strategy)
    )
    if emit(plan):
        return

    months = plan.get("months_to_payoff")
    months_str = str(months) if months is not None else "not within horizon"
    console.print(f"\n[bold]Payoff Plan[/bold]  ({plan['strategy']})\n")
    console.print(f"  Months to payoff:     {months_str}")
    console.print(f"  Total interest paid:  LKR {Decimal(plan['total_interest_paid']):>16,.2f}\n")

    schedule = plan.get("schedule") or []
    if schedule:
        table = Table(title="First 12 Months")
        table.add_column("Month", justify="right")
        table.add_column("Debt")
        table.add_column("Payment", justify="right")
        table.add_column("Principal", justify="right")
        table.add_column("Interest", justify="right")
        table.add_column("Balance", justify="right")
        for entry in schedule[:12]:
            table.add_row(
                str(entry["month"]),
                entry["debt_name"],
                f"{Decimal(entry['payment']):,.2f}",
                f"{Decimal(entry['principal_paid']):,.2f}",
                f"{Decimal(entry['interest_paid']):,.2f}",
                f"{Decimal(entry['remaining_balance']):,.2f}",
            )
        console.print(table)


@debt_app.command("show")
def debt_show(debt_id: str = typer.Argument(...)):
    """Show one debt."""
    user_id = _require_user()
    item = asyncio.run(_services().debt.get_debt(user_id, debt_id))
    if item is None:
        console.print(f"[red]Debt not found:[/red] {debt_id}")
        raise typer.Exit(1)
    if emit(item):
        return
    for key, value in item.items():
        console.print(f"  {key}: {value}")


# ── portfolio ─────────────────────────────────────────────────────────────────


@portfolio_app.command("list")
def portfolio_list(
    all: bool = typer.Option(False, "--all", help="Include inactive holdings"),
):
    """List investment holdings."""
    user_id = _require_user()
    holdings = asyncio.run(_services().portfolio.list_holdings(user_id, active_only=not all))
    if emit(holdings):
        return
    if not holdings:
        console.print("[dim]No holdings found. Use 'salli portfolio add' to create one.[/dim]")
        return
    table = Table(title="Holdings")
    table.add_column("ID", style="dim")
    table.add_column("Symbol")
    table.add_column("Name")
    table.add_column("Asset Class")
    table.add_column("Cost Basis", justify="right")
    table.add_column("Current Value", justify="right")
    for h in holdings:
        table.add_row(
            str(h.get("id", ""))[:8],
            h.get("symbol", ""),
            h.get("name", ""),
            h.get("asset_class", ""),
            h.get("cost_basis", ""),
            h.get("current_value", ""),
        )
    console.print(table)


@portfolio_app.command("add")
def portfolio_add(
    symbol: str = typer.Argument(..., help="Ticker or short identifier, e.g. 'VOO'"),
    name: str = typer.Option(..., "--name", help="Display name"),
    asset_class: str = typer.Option(..., "--asset-class", help="e.g. equity, bond, cash, crypto"),
    cost_basis: str = typer.Option(..., "--cost-basis", help="Total amount invested"),
    current_value: str = typer.Option(..., "--current-value", help="Total current worth"),
):
    """Add an investment holding (manually declared, no live pricing)."""
    user_id = _require_user()
    holding_id = asyncio.run(
        _services().portfolio.add_holding(
            user_id,
            {
                "symbol": symbol,
                "name": name,
                "asset_class": asset_class,
                "cost_basis": cost_basis,
                "current_value": current_value,
            },
        )
    )
    emit({"id": holding_id, "symbol": symbol})
    console.print(f"[green]Holding created:[/green] {symbol} ({holding_id})")


@portfolio_app.command("update")
def portfolio_update(
    holding_id: str = typer.Argument(...),
    symbol: str = typer.Option(None, "--symbol"),
    name: str = typer.Option(None, "--name"),
    asset_class: str = typer.Option(None, "--asset-class"),
    cost_basis: str = typer.Option(None, "--cost-basis"),
    current_value: str = typer.Option(None, "--current-value"),
    active: bool = typer.Option(None, "--active/--inactive"),
):
    """Update fields on an existing holding."""
    user_id = _require_user()
    data: dict[str, object] = {}
    if symbol is not None:
        data["symbol"] = symbol
    if name is not None:
        data["name"] = name
    if asset_class is not None:
        data["asset_class"] = asset_class
    if cost_basis is not None:
        data["cost_basis"] = cost_basis
    if current_value is not None:
        data["current_value"] = current_value
    if active is not None:
        data["is_active"] = active
    if not data:
        console.print("[yellow]Nothing to update.[/yellow]")
        raise typer.Exit(1)
    holdings = asyncio.run(_services().portfolio.list_holdings(user_id, active_only=False))
    holding_id = _resolve_id(holdings, holding_id, "holding")
    asyncio.run(_services().portfolio.update_holding(user_id, holding_id, data))
    emit({"id": holding_id, "updated": data})
    console.print(f"[green]Holding updated:[/green] {holding_id}")


@portfolio_app.command("delete")
def portfolio_delete(
    holding_id: str = typer.Argument(...),
):
    """Delete a holding."""
    user_id = _require_user()
    holdings = asyncio.run(_services().portfolio.list_holdings(user_id, active_only=False))
    holding_id = _resolve_id(holdings, holding_id, "holding")
    asyncio.run(_services().portfolio.delete_holding(user_id, holding_id))
    emit({"id": holding_id, "deleted": True})
    console.print(f"[green]Holding deleted:[/green] {holding_id}")


@portfolio_app.command("summary")
def portfolio_summary(
    target: list[str] = typer.Option(
        [],
        "--target",
        help="ASSET_CLASS:FRACTION, e.g. equity:0.7 (repeat); omit to skip rebalancing alerts",
    ),
):
    """Show allocation by asset class, total gain/ROI, and rebalancing alerts."""
    from decimal import Decimal

    user_id = _require_user()
    target_allocation = None
    if target:
        target_allocation = {}
        for raw in target:
            try:
                asset_class, pct = raw.split(":", 1)
            except ValueError:
                console.print(f"[red]Invalid format '{raw}'. Use ASSET_CLASS:FRACTION[/red]")
                raise typer.Exit(1)
            target_allocation[asset_class.strip()] = Decimal(pct.strip())

    summary = asyncio.run(_services().portfolio.get_summary(user_id, target_allocation))
    if emit(summary):
        return

    console.print("\n[bold]Portfolio Summary[/bold]\n")
    console.print(f"  Total value:       LKR {Decimal(summary['total_value']):>16,.2f}")
    console.print(f"  Total cost basis:  LKR {Decimal(summary['total_cost_basis']):>16,.2f}")
    console.print(f"  Total gain:        LKR {Decimal(summary['total_gain']):>16,.2f}")
    console.print(f"  Total gain %:      {float(summary['total_gain_pct']) * 100:.2f}%\n")

    allocation = summary.get("allocation") or []
    if allocation:
        table = Table(title="Allocation")
        table.add_column("Asset Class")
        table.add_column("Value", justify="right")
        table.add_column("% of Portfolio", justify="right")
        for a in allocation:
            table.add_row(
                a["asset_class"],
                f"{Decimal(a['current_value']):,.2f}",
                f"{float(a['pct_of_portfolio']) * 100:.2f}%",
            )
        console.print(table)

    alerts = summary.get("alerts") or []
    if alerts:
        table = Table(title="Rebalancing Alerts")
        table.add_column("Asset Class")
        table.add_column("Current %", justify="right")
        table.add_column("Target %", justify="right")
        table.add_column("Drift", justify="right")
        for alert in alerts:
            drift = float(alert["drift_pct"]) * 100
            style = "red" if drift > 0 else "yellow"
            table.add_row(
                alert["asset_class"],
                f"{float(alert['current_pct']) * 100:.2f}%",
                f"{float(alert['target_pct']) * 100:.2f}%",
                f"[{style}]{drift:+.2f}%[/{style}]",
            )
        console.print(table)


@portfolio_app.command("show")
def portfolio_show(holding_id: str = typer.Argument(...)):
    """Show one holding."""
    user_id = _require_user()
    item = asyncio.run(_services().portfolio.get_holding(user_id, holding_id))
    if item is None:
        console.print(f"[red]Holding not found:[/red] {holding_id}")
        raise typer.Exit(1)
    if emit(item):
        return
    for key, value in item.items():
        console.print(f"  {key}: {value}")


# ── subscription ──────────────────────────────────────────────────────────────


@subscription_app.command("list")
def subscription_list(
    all: bool = typer.Option(False, "--all", help="Include inactive subscriptions"),
):
    """List recurring subscriptions."""
    user_id = _require_user()
    subscriptions = asyncio.run(
        _services().subscription.list_subscriptions(user_id, active_only=not all)
    )
    if emit(subscriptions):
        return
    if not subscriptions:
        console.print(
            "[dim]No subscriptions found. Use 'salli subscription add' to create one.[/dim]"
        )
        return
    table = Table(title="Recurring Subscriptions")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Amount", justify="right")
    table.add_column("Frequency")
    table.add_column("Next Due")
    for s in subscriptions:
        table.add_row(
            str(s.get("id", ""))[:8],
            s.get("name", ""),
            s.get("amount", ""),
            s.get("frequency", ""),
            s.get("next_due_date", ""),
        )
    console.print(table)


@subscription_app.command("add")
def subscription_add(
    name: str = typer.Argument(..., help="Subscription name, e.g. 'Netflix'"),
    amount: str = typer.Option(..., "--amount", help="Expected charge amount"),
    frequency: str = typer.Option(..., "--frequency", help="weekly|monthly|quarterly|yearly"),
    next_due_date: str = typer.Option(..., "--next-due-date", help="YYYY-MM-DD"),
    account_id: str = typer.Option(
        None, "--account-id", help="Restrict matching to this expense account"
    ),
    grace_days: int = typer.Option(5, "--grace-days"),
    amount_tolerance_pct: str = typer.Option("0.05", "--tolerance"),
):
    """Add a recurring subscription."""
    user_id = _require_user()
    subscription_id = asyncio.run(
        _services().subscription.add_subscription(
            user_id,
            {
                "name": name,
                "amount": amount,
                "frequency": frequency,
                "next_due_date": next_due_date,
                "account_id": account_id,
                "grace_days": grace_days,
                "amount_tolerance_pct": amount_tolerance_pct,
            },
        )
    )
    emit({"id": subscription_id, "name": name})
    console.print(f"[green]Subscription created:[/green] {name} ({subscription_id})")


@subscription_app.command("update")
def subscription_update(
    subscription_id: str = typer.Argument(...),
    name: str = typer.Option(None, "--name"),
    amount: str = typer.Option(None, "--amount"),
    frequency: str = typer.Option(None, "--frequency"),
    next_due_date: str = typer.Option(None, "--next-due-date"),
    account_id: str = typer.Option(None, "--account-id"),
    grace_days: int = typer.Option(None, "--grace-days"),
    amount_tolerance_pct: str = typer.Option(None, "--tolerance"),
    active: bool = typer.Option(None, "--active/--inactive"),
):
    """Update fields on an existing subscription."""
    user_id = _require_user()
    data: dict[str, object] = {}
    if name is not None:
        data["name"] = name
    if amount is not None:
        data["amount"] = amount
    if frequency is not None:
        data["frequency"] = frequency
    if next_due_date is not None:
        data["next_due_date"] = next_due_date
    if account_id is not None:
        data["account_id"] = account_id
    if grace_days is not None:
        data["grace_days"] = grace_days
    if amount_tolerance_pct is not None:
        data["amount_tolerance_pct"] = amount_tolerance_pct
    if active is not None:
        data["is_active"] = active
    if not data:
        console.print("[yellow]Nothing to update.[/yellow]")
        raise typer.Exit(1)
    subs = asyncio.run(_services().subscription.list_subscriptions(user_id, active_only=False))
    subscription_id = _resolve_id(subs, subscription_id, "subscription")
    asyncio.run(_services().subscription.update_subscription(user_id, subscription_id, data))
    emit({"id": subscription_id, "updated": data})
    console.print(f"[green]Subscription updated:[/green] {subscription_id}")


@subscription_app.command("delete")
def subscription_delete(
    subscription_id: str = typer.Argument(...),
):
    """Delete a subscription."""
    user_id = _require_user()
    subs = asyncio.run(_services().subscription.list_subscriptions(user_id, active_only=False))
    subscription_id = _resolve_id(subs, subscription_id, "subscription")
    asyncio.run(_services().subscription.delete_subscription(user_id, subscription_id))
    emit({"id": subscription_id, "deleted": True})
    console.print(f"[green]Subscription deleted:[/green] {subscription_id}")


@subscription_app.command("report")
def subscription_report(
    subscription_id: str = typer.Argument(None, help="Omit to show reports for all subscriptions"),
):
    """Show missed-charge/price-change report(s)."""
    import datetime

    user_id = _require_user()
    today = datetime.date.today().isoformat()

    if subscription_id:
        subs = asyncio.run(_services().subscription.list_subscriptions(user_id, active_only=False))
        subscription_id = _resolve_id(subs, subscription_id, "subscription")
        report = asyncio.run(_services().subscription.get_report(user_id, subscription_id, today))
        if report is None:
            console.print(f"[red]Subscription not found:[/red] {subscription_id}")
            raise typer.Exit(1)
        reports = [report]
    else:
        reports = asyncio.run(_services().subscription.get_all_reports(user_id, today))

    if emit(reports):
        return
    if not reports:
        console.print("[dim]No subscriptions found.[/dim]")
        return

    for report in reports:
        console.print(f"\n[bold]{report['name']}[/bold]  ({report['subscription_id'][:8]})")
        if not report["alerts"]:
            console.print("  [green]No alerts.[/green]")
        for alert in report["alerts"]:
            style = "red" if alert["kind"] == "missed_charge" else "yellow"
            console.print(f"  [{style}]{alert['kind']}:[/{style}] {alert['message']}")
        if report["matches"]:
            table = Table(title="Matched Charges")
            table.add_column("Date")
            table.add_column("Amount", justify="right")
            for m in report["matches"][-5:]:
                table.add_row(m["entry_date"], m["amount"])
            console.print(table)


@subscription_app.command("show")
def subscription_show(subscription_id: str = typer.Argument(...)):
    """Show one subscription."""
    user_id = _require_user()
    item = asyncio.run(_services().subscription.get_subscription(user_id, subscription_id))
    if item is None:
        console.print(f"[red]Subscription not found:[/red] {subscription_id}")
        raise typer.Exit(1)
    if emit(item):
        return
    for key, value in item.items():
        console.print(f"  {key}: {value}")


# ── insurance ──────────────────────────────────────────────────────────────────


@insurance_policy_app.command("list")
def insurance_policy_list(
    all: bool = typer.Option(False, "--all", help="Include inactive policies"),
):
    """List insurance policies."""
    user_id = _require_user()
    policies = asyncio.run(_services().insurance.list_policies(user_id, active_only=not all))
    if emit(policies):
        return
    if not policies:
        console.print(
            "[dim]No policies found. Use 'salli insurance policy add' to create one.[/dim]"
        )
        return
    table = Table(title="Insurance Policies")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Provider")
    table.add_column("Coverage", justify="right")
    table.add_column("Expiry")
    for p in policies:
        table.add_row(
            str(p.get("id", ""))[:8],
            p.get("name", ""),
            p.get("policy_type", ""),
            p.get("provider", ""),
            p.get("coverage_amount", ""),
            p.get("expiry_date", ""),
        )
    console.print(table)


@insurance_policy_app.command("add")
def insurance_policy_add(
    name: str = typer.Argument(..., help="Policy name, e.g. 'Life Basic'"),
    policy_type: str = typer.Option(..., "--type", help="life|health|motor|property|other"),
    provider: str = typer.Option(..., "--provider"),
    coverage_amount: str = typer.Option(..., "--coverage"),
    premium_amount: str = typer.Option(..., "--premium"),
    premium_frequency: str = typer.Option(
        "monthly", "--frequency", help="monthly|quarterly|yearly"
    ),
    expiry_date: str = typer.Option(..., "--expiry-date", help="YYYY-MM-DD"),
):
    """Add an insurance policy."""
    user_id = _require_user()
    policy_id = asyncio.run(
        _services().insurance.add_policy(
            user_id,
            {
                "name": name,
                "policy_type": policy_type,
                "provider": provider,
                "coverage_amount": coverage_amount,
                "premium_amount": premium_amount,
                "premium_frequency": premium_frequency,
                "expiry_date": expiry_date,
            },
        )
    )
    emit({"id": policy_id, "name": name})
    console.print(f"[green]Policy created:[/green] {name} ({policy_id})")


@insurance_policy_app.command("update")
def insurance_policy_update(
    policy_id: str = typer.Argument(...),
    name: str = typer.Option(None, "--name"),
    policy_type: str = typer.Option(None, "--type"),
    provider: str = typer.Option(None, "--provider"),
    coverage_amount: str = typer.Option(None, "--coverage"),
    premium_amount: str = typer.Option(None, "--premium"),
    premium_frequency: str = typer.Option(None, "--frequency"),
    expiry_date: str = typer.Option(None, "--expiry-date"),
    active: bool = typer.Option(None, "--active/--inactive"),
):
    """Update fields on an existing policy."""
    user_id = _require_user()
    data: dict[str, object] = {}
    if name is not None:
        data["name"] = name
    if policy_type is not None:
        data["policy_type"] = policy_type
    if provider is not None:
        data["provider"] = provider
    if coverage_amount is not None:
        data["coverage_amount"] = coverage_amount
    if premium_amount is not None:
        data["premium_amount"] = premium_amount
    if premium_frequency is not None:
        data["premium_frequency"] = premium_frequency
    if expiry_date is not None:
        data["expiry_date"] = expiry_date
    if active is not None:
        data["is_active"] = active
    if not data:
        console.print("[yellow]Nothing to update.[/yellow]")
        raise typer.Exit(1)
    policies = asyncio.run(_services().insurance.list_policies(user_id, active_only=False))
    policy_id = _resolve_id(policies, policy_id, "policy")
    asyncio.run(_services().insurance.update_policy(user_id, policy_id, data))
    emit({"id": policy_id, "updated": data})
    console.print(f"[green]Policy updated:[/green] {policy_id}")


@insurance_policy_app.command("delete")
def insurance_policy_delete(
    policy_id: str = typer.Argument(...),
):
    """Delete a policy."""
    user_id = _require_user()
    policies = asyncio.run(_services().insurance.list_policies(user_id, active_only=False))
    policy_id = _resolve_id(policies, policy_id, "policy")
    asyncio.run(_services().insurance.delete_policy(user_id, policy_id))
    emit({"id": policy_id, "deleted": True})
    console.print(f"[green]Policy deleted:[/green] {policy_id}")


@insurance_target_app.command("set")
def insurance_target_set(
    policy_type: str = typer.Argument(..., help="life|health|motor|property|other"),
    target_amount: str = typer.Option(..., "--amount", help="Desired total coverage for this type"),
):
    """Set (or update) the declared coverage target for a policy type."""
    from decimal import Decimal

    user_id = _require_user()
    target_id = asyncio.run(
        _services().insurance.set_target(user_id, policy_type, Decimal(target_amount))
    )
    emit({"id": target_id, "policy_type": policy_type, "target_amount": Decimal(target_amount)})
    console.print(f"[green]Target set:[/green] {policy_type} = {target_amount} ({target_id})")


@insurance_target_app.command("list")
def insurance_target_list():
    """List declared coverage targets."""
    user_id = _require_user()
    targets = asyncio.run(_services().insurance.list_targets(user_id))
    if emit(targets):
        return
    if not targets:
        console.print(
            "[dim]No targets found. Use 'salli insurance target set' to declare one.[/dim]"
        )
        return
    table = Table(title="Coverage Targets")
    table.add_column("Type")
    table.add_column("Target Amount", justify="right")
    for t in targets:
        table.add_row(t.get("policy_type", ""), t.get("target_amount", ""))
    console.print(table)


@insurance_target_app.command("delete")
def insurance_target_delete(
    policy_type: str = typer.Argument(...),
):
    """Delete the declared coverage target for a policy type."""
    user_id = _require_user()
    asyncio.run(_services().insurance.delete_target(user_id, policy_type))
    emit({"policy_type": policy_type, "deleted": True})
    console.print(f"[green]Target deleted:[/green] {policy_type}")


@insurance_app.command("report")
def insurance_report():
    """Show the coverage-gap report: target vs. actual coverage, missing types,
    and policies expiring within 30 days."""
    import datetime

    user_id = _require_user()
    today = datetime.date.today().isoformat()
    report = asyncio.run(_services().insurance.get_report(user_id, today))
    if emit(report):
        return

    if report["lines"]:
        table = Table(title="Coverage Gap")
        table.add_column("Type")
        table.add_column("Target", justify="right")
        table.add_column("Actual", justify="right")
        table.add_column("Gap", justify="right")
        for line in report["lines"]:
            from decimal import Decimal

            gap = Decimal(line["gap"])
            style = "red" if gap > 0 else "green"
            table.add_row(
                line["policy_type"],
                line["target_amount"],
                line["actual_coverage"],
                f"[{style}]{line['gap']}[/{style}]",
            )
        console.print(table)
    else:
        console.print("[dim]No coverage targets declared.[/dim]")

    if report["missing_types"]:
        console.print(f"\n[red]Missing coverage:[/red] {', '.join(report['missing_types'])}")

    if report["expiring_soon"]:
        table = Table(title="Expiring Soon")
        table.add_column("Policy")
        table.add_column("Type")
        table.add_column("Expiry")
        table.add_column("Days Left", justify="right")
        for alert in report["expiring_soon"]:
            table.add_row(
                alert["policy_name"],
                alert["policy_type"],
                alert["expiry_date"],
                str(alert["days_until_expiry"]),
            )
        console.print(table)


@insurance_policy_app.command("show")
def insurance_policy_show(policy_id: str = typer.Argument(...)):
    """Show one policy."""
    user_id = _require_user()
    item = asyncio.run(_services().insurance.get_policy(user_id, policy_id))
    if item is None:
        console.print(f"[red]Policy not found:[/red] {policy_id}")
        raise typer.Exit(1)
    if emit(item):
        return
    for key, value in item.items():
        console.print(f"  {key}: {value}")


# ── reports ────────────────────────────────────────────────────────────────────


@reports_app.command("balance-sheet")
def reports_balance_sheet():
    """Show the balance sheet: assets, liabilities, equity, and net worth."""
    user_id = _require_user()
    report = asyncio.run(_services().reports.get_balance_sheet(user_id))
    if emit(report):
        return

    for section, label in (
        ("assets", "Assets"),
        ("liabilities", "Liabilities"),
        ("equity", "Equity"),
    ):
        lines = report.get(section) or []
        if not lines:
            continue
        table = Table(title=label)
        table.add_column("Code")
        table.add_column("Account")
        table.add_column("Balance", justify="right")
        for line in lines:
            table.add_row(line["code"], line["name"], line["balance"])
        console.print(table)

    console.print(f"\n[bold]Total Assets:[/bold]      {report['total_assets']}")
    console.print(f"[bold]Total Liabilities:[/bold] {report['total_liabilities']}")
    console.print(f"[bold]Net Worth:[/bold]         {report['net_worth']}\n")


@reports_app.command("net-worth")
def reports_net_worth():
    """Show current net worth and its historical trend."""
    user_id = _require_user()
    report = asyncio.run(_services().reports.get_net_worth_statement(user_id))
    if emit(report):
        return

    console.print(f"\n[bold]Current Net Worth:[/bold] {report['current_net_worth']}")
    console.print(f"[dim]As of: {report['as_of']}[/dim]\n")

    trend = report.get("trend") or []
    if trend:
        table = Table(title="Net Worth Trend")
        table.add_column("Date")
        table.add_column("Net Worth", justify="right")
        for point in trend[-12:]:
            table.add_row(str(point["date"]), str(point["net_worth"]))
        console.print(table)


@reports_app.command("goal-progress")
def reports_goal_progress():
    """Show progress toward all active FI goals."""
    user_id = _require_user()
    report = asyncio.run(_services().reports.get_goal_progress_report(user_id))
    if emit(report):
        return

    goals = report.get("goals") or []
    if not goals:
        console.print("[dim]No goals found. Use 'salli fi goals add' to create one.[/dim]")
        return

    table = Table(title="Goal Progress")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Target", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Progress", justify="right")
    for g in goals:
        pct = f"{g['progress'] * 100:.1f}%"
        style = "green" if g["progress"] >= 1.0 else "yellow"
        table.add_row(
            g["name"],
            g["kind"],
            g["target_amount"],
            g["current_amount"],
            f"[{style}]{pct}[/{style}]",
        )
    console.print(table)
    console.print(
        f"\n[bold]Completed:[/bold] {report['completed_count']}  "
        f"[bold]In progress:[/bold] {report['in_progress_count']}"
    )


@reports_app.command("export")
def reports_export(
    report_type: str = typer.Argument(..., help="balance-sheet|net-worth|goal-progress"),
    output: str = typer.Option(..., "--output", "-o", help="Output CSV file path"),
):
    """Export a report as CSV."""
    if report_type not in ("balance-sheet", "net-worth", "goal-progress"):
        console.print(f"[red]Unknown report type '{report_type}'.[/red]")
        raise typer.Exit(1)
    user_id = _require_user()
    csv_bytes = asyncio.run(_services().reports.export_csv(report_type, user_id))
    with open(output, "wb") as f:
        f.write(csv_bytes)
    emit({"path": str(output), "report_type": report_type, "bytes": len(csv_bytes)})
    console.print(f"[green]Exported {report_type} to:[/green] {output}")


# ── onboarding ────────────────────────────────────────────────────────────────


@onboarding_app.command("status")
def onboarding_status():
    """Whether first-run onboarding has been completed."""
    user_id = _require_user()
    complete = asyncio.run(_services().onboarding.is_complete(user_id))
    if emit({"complete": complete}):
        return
    console.print(f"Onboarding: {'complete' if complete else 'not done yet'}")


@onboarding_app.command("complete")
def onboarding_complete(
    name: str = typer.Option(..., help="Your name"),
    income: str = typer.Option(
        "", help="Comma-separated: employment,freelance,rental,interest,foreign,dividends"
    ),
    residency: str = typer.Option("resident", help="resident | non_resident"),
    primary_goal: str = typer.Option(
        "",
        help="financial_independence | retirement | home | emergency_fund | debt_free | "
        "wealth_growth",
    ),
    goal_amount: float = typer.Option(0, help="Target amount for that goal (LKR)"),
    goal_year: str = typer.Option("", help="Target year, YYYY"),
):
    """Save your profile and create a starter chart of accounts. Safe to re-run."""
    user_id = _require_user()
    result = asyncio.run(
        _services().onboarding.complete(
            user_id,
            {
                "name": name,
                "residency": residency,
                "income_sources": [s.strip() for s in income.split(",") if s.strip()],
                "primary_goal": primary_goal,
                "goal_target_amount": goal_amount,
                "goal_target_year": goal_year,
            },
        )
    )
    if emit(result):
        return
    console.print(f"[green]Accounts created:[/green] {len(result['accounts_created'])}")
    for created in result["accounts_created"]:
        console.print(f"  {created}")


# ── llm-keys ──────────────────────────────────────────────────────────────────


@llm_keys_app.command("list")
def llm_keys_list():
    """Which provider keys you have stored (never the keys themselves)."""
    user_id = _require_user()
    svc = _services()
    keys = asyncio.run(svc.llm_credentials.status(user_id))
    if emit({"available": svc.llm_credentials.available, "keys": keys}):
        return
    if not svc.llm_credentials.available:
        console.print("[yellow]Storing keys is off: set BYOK_ENCRYPTION_KEYS and auth.[/yellow]")
    for k in keys:
        console.print(f"  {k}")


@llm_keys_app.command("set")
def llm_keys_set(provider: str = typer.Argument("anthropic", help="anthropic")):
    """Store your key for a provider (checked with the provider first)."""
    user_id = _require_user()
    key = typer.prompt(f"{provider} API key", hide_input=True)
    try:
        asyncio.run(_services().llm_credentials.save(user_id, provider, key.strip()))
    except Exception as exc:
        # Our own wording: a provider's error message can echo the key back.
        console.print(f"[red]Key not saved ({type(exc).__name__}).[/red]")
        raise typer.Exit(1) from None
    emit({"provider": provider, "saved": True})
    console.print(f"[green]Saved your {provider} key.[/green]")


@llm_keys_app.command("delete")
def llm_keys_delete(provider: str = typer.Argument("anthropic", help="anthropic")):
    """Remove your stored key for a provider."""
    user_id = _require_user()
    removed = asyncio.run(_services().llm_credentials.delete(user_id, provider))
    if not removed:
        console.print(f"[red]No {provider} key stored.[/red]")
        raise typer.Exit(1)
    emit({"provider": provider, "deleted": True})
    console.print(f"[green]Removed your {provider} key.[/green]")


# ── mcp ───────────────────────────────────────────────────────────────────────


@mcp_app.command("status")
def mcp_status():
    """Whether AI clients may connect to your Salli over MCP."""
    user_id = _require_user()
    enabled = asyncio.run(_services().mcp_oauth.is_mcp_enabled(user_id))
    if emit({"enabled": enabled}):
        return
    console.print(f"MCP: {'on' if enabled else 'off'}")


@mcp_app.command("enable")
def mcp_enable():
    """Allow AI clients to connect (each one still asks for your approval)."""
    user_id = _require_user()
    asyncio.run(_services().mcp_oauth.set_mcp_enabled(user_id, True))
    emit({"enabled": True})
    console.print("[green]MCP on.[/green]")


@mcp_app.command("disable")
def mcp_disable():
    """Disconnect every AI client now and refuse new ones."""
    user_id = _require_user()
    asyncio.run(_services().mcp_oauth.set_mcp_enabled(user_id, False))
    emit({"enabled": False})
    console.print("[green]MCP off.[/green] Existing connections stop working immediately.")


@mcp_app.command("connections")
def mcp_connections():
    """AI clients currently connected."""
    user_id = _require_user()
    connections = asyncio.run(_services().mcp_oauth.list_connections(user_id))
    if emit(connections):
        return
    table = Table(title="MCP connections")
    for column in ("ID", "Client", "Scope", "Expires"):
        table.add_column(column)
    for c in connections:
        table.add_row(
            str(c.get("id", ""))[:8],
            str(c.get("client_name", "")),
            str(c.get("scope", "")),
            str(c.get("expires_at", "")),
        )
    console.print(table)


@mcp_app.command("revoke")
def mcp_revoke(token_id: str = typer.Argument(..., help="Connection id")):
    """Disconnect one AI client."""
    user_id = _require_user()
    connections = asyncio.run(_services().mcp_oauth.list_connections(user_id))
    token_id = _resolve_id(connections, token_id, "connection")
    asyncio.run(_services().mcp_oauth.revoke_connection(user_id, token_id))
    emit({"id": token_id, "revoked": True})
    console.print(f"[green]Disconnected:[/green] {token_id}")


# ── whoami ────────────────────────────────────────────────────────────────────


@app.command("whoami")
def whoami():
    """The user this CLI acts as."""
    user_id = _require_user()
    profile = asyncio.run(_services().profile.get_profile(user_id))
    if emit({"user_id": user_id, "email": profile.get("email")}):
        return
    console.print(f"{user_id}  {profile.get('email') or ''}")


# ── helpers ───────────────────────────────────────────────────────────────────


# ── db ────────────────────────────────────────────────────────────────────────


@db_app.command("upgrade")
def db_upgrade(
    revision: str = typer.Option("head", help="Target revision (Salli's history only)"),
):
    """Migrate the database: Salli's tables, then each enabled extension's."""
    from salli.config import get_settings
    from salli.migrations.support import script_locations, upgrade

    upgraded: dict[str, str] = {}
    for name, location in script_locations(get_settings()):
        console.print(f"[bold]{name}[/bold]")
        upgraded[name] = revision if name == "salli" else "head"
        upgrade(location, upgraded[name])
    emit({"upgraded": upgraded})


@db_app.command("current")
def db_current():
    """Show the revision each migration history is at."""
    import io

    from alembic import command

    from salli.config import get_settings
    from salli.migrations.support import alembic_config, script_locations

    current: dict[str, str] = {}
    for name, location in script_locations(get_settings()):
        console.print(f"[bold]{name}[/bold]")
        cfg = alembic_config(location)
        if json_mode():
            cfg.stdout = io.StringIO()
        command.current(cfg)
        if json_mode():
            current[name] = cfg.stdout.getvalue().strip()
    emit(current)


# ── extensions ────────────────────────────────────────────────────────────────


def _add_extension_groups() -> None:
    """Command groups contributed by enabled extensions (salli/extensions.py)."""
    from salli.config import get_settings
    from salli.extensions import enabled_specs

    for spec in enabled_specs(get_settings()):
        for name, group in spec.cli_groups:
            app.add_typer(group, name=name)


_add_extension_groups()


# ── entrypoint ────────────────────────────────────────────────────────────────


def cli() -> Any:
    """The `salli` command tree, with --json on every non-interactive command."""
    return with_json_option(typer.main.get_command(app))


def main():
    cli()()


if __name__ == "__main__":
    main()
