# Use Salli from Claude or ChatGPT

Salli runs an MCP server at `https://<your-salli>/mcp`. Connect it to the AI app you
already pay for, and that subscription does the thinking while Salli supplies the
numbers. Salli computes every amount; the model reads and explains them. It never
does the arithmetic itself.

Once connected, your AI can:
- read your cash flow, spending, net worth over time, recurring payments and your
  cash forecast;
- answer "can I afford…?" from your forecast and your FI plan;
- show your financial-independence projections, in today's money, and research
  your own planning assumptions (inflation, returns, withdrawal rate) from
  citable sources, setting them once you agree;
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

Five ready-made prompts come with the server: **review my month**, **sort my pending
transactions**, **can I afford**, **set planning assumptions** and **research tax
rules** (for a country and year).

### Financial independence tools

| Tool | What it does |
|---|---|
| `get_fi_projections` | Your investable assets projected under conservative, base and growth real-return scenarios, the FI number and the years to it, in today's money (and each year's own money once you set inflation). |
| `get_fi_assumptions` | The planning assumptions behind those figures: which apply and where each came from, what you set, and the placeholders. |
| `set_fi_assumption` | Sets (or clears) one of your figures, with its source. A write: the AI shows you the figure and its source first. |
| `simulate_purchase` | What a purchase costs in months of freedom, cash against instalments. |

FI figures are in real terms. Where you have set no return or withdrawal rate, a
round placeholder (4%) stands in, and every result says so (`assumptions.status`
is `placeholder`): it is no forecast and no country's figure. Salli keeps no
table of figures by country; your own, with their sources, replace the
placeholders.

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
token ever holds: you activate in the app, or with `salli tax rules activate` at your
own terminal, after reviewing the changes, sources and examples. A personal access
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
