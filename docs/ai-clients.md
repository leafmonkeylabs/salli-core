# Use Salli from Claude or ChatGPT

Salli runs an MCP server at `https://<your-salli>/mcp`. Connect it to the AI app you
already pay for, and that subscription does the thinking while Salli supplies the
numbers. Salli computes every amount; the model reads and explains them. It never
does the arithmetic itself.

You approve each connection on Salli's own consent page, with your Salli email and
password. An app that connects from its maker's cloud (Claude's, ChatGPT's) needs
your Salli reachable over HTTPS: [docs/self-host.md](self-host.md#https-on-your-own-domain)
shows how.

Once connected, your AI can:
- read your cash flow, spending, net worth over time, recurring payments and your
  cash forecast;
- weigh a decision (can I afford it, cash or instalments, pay down a debt or
  invest, a windfall, a new flat or job, a loan, an emergency fund) from a
  template, or by building the options as scenarios, which Salli runs and
  compares, never by its own sums, and without ranking them for you; check
  them against your own principles, and, once you have decided and say so,
  record the decision and your reasons in your journal, and look back on it
  when it is due;
- show your financial-independence projections, in today's money, and research
  your own planning assumptions (inflation, returns, withdrawal rate) from
  citable sources, and ask what share of your surplus you invest, setting them
  once you agree;
- sort imported transactions, then book what you approve;
- create rules, so the next statement sorts itself;
- run the Wealth Advisor and read budgets, debts, portfolio and insurance;
- read your tax, computed by Salli from the tax rules you activated, and explain
  each line from its expression and the source the rules cite;
- research your country's tax rules from official sources, write them as a Salli
  rule set, check them against the authority's worked examples and propose them to
  you. It can't activate them: only you can, in Salli.

Salli knows no country's tax law. Without rules you activated it computes no tax,
and the tax tools say so and what you can do.

Six ready-made prompts come with the server: **review my month**, **sort my pending
transactions**, **can I afford**, **think through a decision**, **set planning
assumptions** and **research tax rules** (for a country and year).

### When it helps you decide

**Think through a decision** (`think_through_decision`, with your question) has
the AI ask what you are weighing and what matters to you, build the options with
Salli (a [template](templates.md) where one fits, scenarios otherwise), compare
them with the sensitivity and check your principles, explain the trade-offs in
plain words with Salli's figures and the assumptions behind them (saying which are
placeholders), say what would change the answer (the break-evens), and leave the
choice to you. **Can I afford** does the same with the afford-it template.

Both prompts, the CLI's skill and the tools' own descriptions hold the AI to these:

- **It never computes.** Every figure is Salli's, quoted with its currency.
- **It never names a specific product, provider, fund or security of its own.** It
  may refer to your own holdings as you named them, but never suggests buying or
  selling any security, yours or another, and never compares your holdings as
  investments.
- **Regulated advice is for a licensed professional.** Where a choice is regulated
  financial advice where you live (insurance, pensions, choosing investments), it
  says so and suggests one there, without assuming any country's rules.
- **It respects your principles**, saying which each option keeps or breaks.
- **It never ranks the options** or calls one best: Salli doesn't either.
- **It never records a decision you haven't confirmed**, and records your reasons
  in your words.

### Financial independence tools

| Tool | What it does |
|---|---|
| `get_fi_projections` | Your cash and investments less your debts, projected on the baseline's monthly timeline under conservative, base and growth real returns, the FI number and the month you reach it, in today's money (and each year's own money once you set inflation). |
| `get_fi_assumptions` | The planning assumptions behind those figures: which apply and where each came from, what you set, and the placeholders. |
| `set_fi_assumption` | Sets (or clears) one of your figures, with its source. A write: the AI shows you the figure and its source first. |

### Scenario tools

| Tool | What it does |
|---|---|
| `get_scenario_schema` | The scenario document's JSON Schema (`salli.scenario/1`), to write options against. |
| `run_scenario` | One scenario on your baseline: every figure under your baseline and under the scenario, with the change, the assumptions and a hash of its inputs. Nothing is stored. |
| `compare_options` | Two to five options side by side: what each gains and gives up against the others, the same at the conservative and growth returns, and the break-evens. Never a ranking. |

A change before tax (a raise, a taxable bonus, a pension contribution) is
tagged with a role from your own tax rules (`tax_role`), and Salli works out
the change in each year's tax with your active rules; the AI never works out
an amount after tax itself. Without active rules the result says the tax
isn't computed, and why. A home is an `asset` change, counted at its value
less its selling costs; how fast it (or a rent) grows beyond inflation is
your view, never the AI's.

A scenario may invest into one of your own holdings or sell part of one
([scenarios](scenarios.md#holdings)):

| Tool | What it does |
|---|---|
| `list_holdings` | Your holdings, by your own id, symbol and name, with their units, value at your last recorded price and the investment account each is linked to. |
| `link_holding` | Links a holding to the investment account in your ledger that holds it (or unlinks it), so a scenario can sell it. A write: the AI shows you the holding and the account first. |

The AI may mention your holdings as you named them, never one you don't
hold, and never suggests buying or selling any of them or compares them as
investments. Fees are yours: it asks for them rather than assuming any.

See [scenarios](scenarios.md) for the document and how to read the results.

### Decisions: templates, principles and the journal

| Tool | What it does |
|---|---|
| `list_decision_templates` | The [decision templates](templates.md): each one's questions, with your own defaults where there are honest ones, and the options it builds. Rent-or-buy's growths beyond inflation default to a labelled 0% placeholder; the AI asks for your own view and never supplies one. |
| `start_decision` | A template and your answers (and answers to your tax rules' questions, `tax_answers`): the options built, compared and checked against your principles, and what recording needs; for rent or buy, when buying draws level with renting and the house-price growth at which the answer turns. Stores nothing, ranks nothing. |
| `list_principles` | Your principles (your own rules of thumb) and the figures a check may read. |
| `add_principle` | Keeps a principle the AI suggested, only once you have said yes to its exact label and check (`confirmed_by_user`); recorded as the agent's. |
| `check_principles` | Which principles your baseline and each option keep, break or can't tell, with the figures and the reason. Never a ranking. |
| `record_decision` | Records a decision in your journal, which can't be edited or deleted: Salli runs the options itself, with your reasons in your words. Only once you confirm (`confirmed_by_user`). |
| `list_decisions`, `get_decision` | Your journal, and one entry as recorded, with whether its hash still matches. |
| `list_due_reviews` | Decisions whose review date has come, with what the option you chose projected against what happened. |
| `review_decision` | Appends your reflection, with Salli's comparison, once you agree to the words. |

See [decision templates](templates.md) and [principles and the decision journal](decisions.md).

FI figures are in real terms. Where you have set no return or withdrawal rate, a
round placeholder (4%) stands in, and every result says so (`assumptions.status`
is `placeholder`): it is no forecast and no country's figure. Nor is the share of
your monthly surplus you invest: until you set it (`surplus_invested`), a
placeholder assumes all of it. Salli keeps no table of figures by country; your
own, with their sources, replace the placeholders.

### Tax tools

| Tool | What it does |
|---|---|
| `get_tax_computation` | Your tax for a year (your current one by default), computed from your active rules and your ledger: every line with its expression and source, and the net payable or refund. Nothing is stored. |
| `explain_tax_line` | Where one line came from: its expression, the ledger totals, answers and lines it used, any band table, the source it cites, and what uses it. |

### Tax rule tools

| Tool | What it does |
|---|---|
| `get_tax_rule_schema` | The rule-set format's JSON Schema, to write against. |
| `list_tax_rule_sets` | Your rule sets, their versions and which is active. |
| `get_tax_rule_set` | One rule set; or one version's document and validation report. |
| `draft_tax_rule_set` | Stores a document as a new version (of a set, or of the one for its jurisdiction and year), even with mistakes; recorded as the agent's. |
| `validate_tax_rule_set` | Validates a version again: errors with their paths, and each worked example's figures that differ, with the expression behind them. |
| `propose_tax_rule_set` | Asks you to review a version that passes. |
| `diff_tax_rule_set_versions` | What changed between versions, with each figure's source. |
| `evaluate_tax_rule_set` | Runs Salli's engine on your ledger with a version's rules, line by line. Nothing is stored. |
| `suggested_tax_accounts` | The accounts a rule set suggests and whether you have them; with `apply`, creates the missing ones (accounts you have are left alone). |

There is no tool to activate rules. An agent researching tax law reads pages anyone
can write, so activation needs a permission (`tax:activate`) that no AI connector's
token ever holds: you activate with `salli tax rules activate` at your
own terminal, after reviewing the changes, sources and examples (or in the
console, which asks for your password again on Salli's own page first). A personal access
token holds it only if you made it with `--allow tax:activate`, so don't give such a
token to an agent. See [docs/taxrules.md](taxrules.md#who-may-activate-taxactivate).

The same holds for an agent driving the `salli` CLI on your machine (Claude Code with
`salli skills install`, say): it can draft, validate, propose and evaluate, and
`salli tax rules activate` refuses to run for it (no terminal to ask in, no `--yes`).

Before connecting anything:
- **The switch:** MCP must be on for your account (`salli mcp enable`), and you approve
  each client on Salli's consent page.
- **Writes:** these take effect when the AI calls them. The tools tell it to show you
  what it will do first.
- **Disconnecting:** `salli mcp connections` lists connected clients, and
  `salli mcp revoke` disconnects one.

## Claude (web, desktop, mobile)

Claude connects from Anthropic's cloud, not from your device, so your Salli has to be
reachable over the public internet over HTTPS. A Salli on your laptop or home network
needs a public address first, for example behind a reverse proxy with TLS.

1. In Claude, open **Customize → Connectors**, choose **+ Add**, then **Add custom
   connector**.
2. Name it `Salli` and enter `https://<your-salli>/mcp`.
3. Leave authentication on OAuth with automatic registration, and sign in to Salli when
   asked. You are approving Claude on Salli's consent page.
4. In a chat, open **+ → Connectors** and switch Salli on.

Free plans allow one custom connector; Pro and Max allow more. See Anthropic's guide,
[Get started with custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

## Claude Code

```bash
claude mcp add --transport http salli https://<your-salli>/mcp
```

Run `/mcp` inside Claude Code to sign in. Claude Code runs on your machine, so a Salli on
`localhost` works here too.

## ChatGPT

ChatGPT adds custom MCP servers as apps. Where the option lives has changed several
times; recently it has been under **Settings → Apps** (or chatgpt.com/plugins), and on
some plans behind **Developer mode**. Add a new MCP app with the URL
`https://<your-salli>/mcp` and sign in to Salli when asked. On some plans, custom apps
may only read; sorting and booking then stay in Salli itself. See OpenAI's
[Developer mode and MCP apps in ChatGPT](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt).

## The other direction: your ChatGPT plan inside Salli

Salli's own AI features (statement sorting, quick add, the chat agent, the strategy and
briefings) can run on a ChatGPT Plus or Pro plan through OpenAI's
[Sign in with ChatGPT](https://developers.openai.com/siwc/token-sharing-open-source),
which OpenAI offers to open-source and self-hosted apps.

Anthropic does not allow Claude plans to be used this way
([Claude Code legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)).
For Claude, connect Salli to Claude as above, or give Salli an Anthropic API key.
