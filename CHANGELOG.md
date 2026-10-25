# Changelog

## Unreleased

### Added

- **Bank formats as data.** A bank's statement layout is a
  `salli.bankformat/1` JSON document (columns by header or position, date
  format, decimal and thousands separators, debit and credit columns, a
  direction column or a sign), given with an import: `salli import
  --format <file or directory>`, the `formats` field of `POST
  /v1/statements/upload`. It reads CSV files and the tables of PDF and Excel
  statements; with several, the one that reads the most rows is used, and
  the result's `formats` counts what each read and could not. The first
  market pack's banks are in `markets/lk/banks/`, each with a synthetic
  sample the tests read, none yet verified against a real export.
- **Usage counts for the owner.** `SALLI_USAGE_COUNTERS=true` (off by
  default) enables `salli-server stats`: members active, statement entries
  imported and reconciliations completed in the last seven days, counted
  from the database when asked and never sent anywhere
  (business/metrics.md).
- **A hosted path.** `deploy/host.sh` sets up one instance per person or
  household with the published image, HTTPS, the owner and nightly
  backups, and upgrades it; docs/hosting.md is the guide, including where
  a hosted service's extension would report counts and where a payment
  processor sits (outside the core).
- **Connector directory kit.** docs/connectors.md lists what Claude's and
  ChatGPT's connector directories ask, and a test checks the server's side:
  the OAuth metadata now carries `scopes_supported` (and
  `bearer_methods_supported`), the protected resource metadata is also served
  at `/.well-known/oauth-protected-resource/mcp`, a 401 from `/mcp` names it in
  `WWW-Authenticate`, and every MCP tool has a title.
- **docs/scope.md**: the surface is frozen until the first pilots (no new
  engines), what is core and what is experimental; the decision lab's docs
  say it is experimental.

- **An investment policy statement.** Target allocation by asset class with
  a band each, a rebalancing rule (bands, calendar or both), horizon,
  objectives, constraints and a review date, stored as versions and never
  changed (`salli.ips/1`; `GET`/`POST /v1/ips`, `GET /v1/ips/versions`;
  `salli ips show|history|set`). `GET /v1/ips/drift` (`salli ips drift`)
  reports each class against its target and band, the amount to its
  target, and whether the rule says rebalance or the review date has come.
  The portfolio summary takes its targets and bands when none are given
  (`target_source`). MCP `get_investment_policy`. Migration
  `core_0040_investment_policy`.
- **Risk capacity beside tolerance.** From the baseline: emergency months,
  income stability, horizon (the policy's, or the questionnaire's, now
  kept) and debt service, 0 to 100; the profile is the lower of tolerance
  and capacity (`GET /v1/ips/risk-profile`, `salli ips risk`, and beside
  the drift report). It gates nothing; a policy whose equity target is
  above the profile's band is flagged.
- **Risk figures and costs.** Portfolio performance carries `risk`: monthly
  time-weighted returns compounded to a year, volatility, largest fall and
  a Sharpe ratio against a cash yield (`cash_yield`) or a benchmark's
  recorded closes (`benchmark`, any symbol), else the active CMA pack's
  cash yield. A holding takes an expense
  ratio (your figure); the summary's `costs` weight them by value and say
  what they take in a year.
- **Average cost.** A holding's sales are costed first in, first out (named
  lots allowed) or at average cost (`cost_method`), the holding's choice,
  else the active tax rule set's new optional `cost_basis`, else first in,
  first out. A scenario's sale is replayed by the holding's own method.
  Rule sets without it hash as before.
- **An insurance needs analysis** (`GET /v1/insurance/needs`, `salli
  insurance needs`, and `needs` in MCP `get_coverage_report`): life cover from years of
  income, debts and goals less cash, savings and investments, against the
  life cover held; income protection as a month's spending. Figures, never
  a product.
- **Plainer signals.** A signal's `detail` is in plain words, and why Salli
  says so is in a new `rationale`. The emergency fund signal is graded: high
  under a month, medium under three, low (a new severity) under the target.

- **The odds of a plan.** A seeded, reproducible Monte Carlo on the
  baseline's monthly timeline (`GET /v1/fi/odds`, `POST /v1/scenarios/odds`,
  `salli fi odds`, MCP `get_fi_odds`): the share of paths whose money lasts
  to a horizon, the share reaching the FI number, 10/50/90 percentile wealth
  paths, a horizon-derived withdrawal rate beside yours, and optional
  spending guardrails. Debt or invest's start carries the share of paths on
  which investing grows by more than paying down the debt saves.
- **Capital-market assumptions as user data** (`salli.cma/1`;
  `/v1/fi/cma-packs`, `salli fi cma`; migration core_0039): per asset class
  a real return and volatility, correlations, a cash yield and inflation,
  each sourced and dated, imported unchanged and activated one at a time.
  An active pack sets the real return and inflation where you set none,
  cash earns its yield, and the odds draw with its volatility; a labelled
  placeholder pack stands in otherwise.
- **Guaranteed income, spending phases and tax on withdrawals in the FI
  number** (`/v1/fi/plan`, `salli fi plan`): pensions, annuities and
  provident-fund payouts (start month, real or nominal, indexed or not, a
  lump sum) reduce the FI number from their start and come into cash;
  spending can change by age band; and with an income role `withdrawal` in
  your active tax rules the FI number is grossed up for the tax on
  withdrawals.

- **Bank reconciliation.** A statement with the bank's opening and closing
  balance (an MT940 or camt.053 import carries them; any other is typed in)
  is reconciled by clearing the postings it shows; it completes only at a
  difference of zero and records who completed it and when. `salli reconcile
  list|add|show|clear|complete`, `/v1/reconciliation/*`, the MCP read
  `get_reconciliation` ([docs/books.md](docs/books.md)). Clearing is the one
  change a closed month's posting still takes (core_0038).

- **Where the books start.** `books_start` on the profile (`salli profile set
  --books-start`): opening balances are posted on it, and a balance sheet or
  income statement for a time before it says so.

- **Currencies balance exactly.** A multi-currency entry's rounding in the
  base currency (a minor unit a posting at most) is posted to an
  `fx_rounding` account, opened when first needed. Unrealised exchange gains
  and losses are computed as of a day (`salli ledger unrealised-fx`, the
  balance sheet's `unrealised_fx` and its `as_of`, the income statement's
  `unrealised_fx`), and posted only when asked at a month's end (`salli
  ledger revalue`).

- **Imports: the bank's base amount and splits.** A drafted or fed row may
  carry its amount in the base currency, and the rate posted is derived from
  it; a transaction is split across accounts in review (`salli statements
  categorize <id> --split account:amount`).

- **Document retention.** A retention period on the profile (`salli profile
  set --retention-years`) keeps each document saved from then on until its
  `retain_until`; a document an entry cites is not deleted while no retention
  period has passed, and one cited by an entry in a filed tax return's
  period is kept for the period from the return's filing.

- **Capital gains for tax rules.** A rule set's `realised_gain` role is filled
  from the holdings' sales in its year.

- **The plain-text exports are checked by their tools.** CI runs the
  Beancount and hledger exports through `bean-check` and `hledger check`.

- **Filed years, a year-end close, and who posted what.** A return record
  keeps what was filed: each version of a year's return (draft, filed,
  amended with a reason), with a snapshot of its computation and the
  snapshot's hash, the authority's reference, the filing date and the
  payments against it, append-only (`/v1/tax/return-records`, `salli tax
  returns list|show|record|pay`, MCP `list_tax_returns`). While a year's
  return is filed its books can't be opened again (the lock date can't move
  before its end, nor be cleared) until an amendment is recorded. `salli
  ledger close-year <date>` (`POST /v1/ledger/year-end-close`) moves the
  year's income and expenses to the equity account set with `salli ledger
  retained-earnings <account>`, and the balance sheet shows what isn't
  closed yet as current-year earnings. Every entry records who posted it
  and how (`created_by`, `created_via`: console, cli, mobile,
  `mcp:<client>`, import, automation), in its reads and the export, and is
  hash-chained to the one before; `salli ledger verify` (`GET
  /v1/ledger/verify`) names the first entry that changed. Migration
  `core_0037_filed_years` chains the entries already stored, recorded as
  posted by their owner via "unrecorded".

- **Read-only access to another member's books.** A member lets another
  member of the same server read their books (`salli access grant <email>`,
  `POST /v1/access-grants`, behind the step-up; never from a token or
  another application), both see it (`salli access list`), and either ends
  it (`salli access revoke`). The grantee reads by naming the books
  (`salli --books <member-id>`, `SALLI_BOOKS`, the `Salli-Books` header):
  GET requests on the books' routes only; giving, receiving, ending and
  every read are in the audit logs. Migration `core_0036_access_grants`.
- **MCP catches up with the API.** `list_budgets`, `list_debts`,
  `list_goals`, `list_reminders`, `get_entry`, and `reverse_entry` (a write,
  with `confirmed_by_user`). A headless agent may send a personal access
  token as its MCP bearer: it reads only, while MCP is on.
- **The benchmark runs through Claude Code.** `uv run python -m
  benchmark.run --via claude` asks `claude -p` with only Salli's MCP server
  (`benchmark/serve.py`), so a run needs no API key of its own.
- **Business notes** (`business/`): a commercial thesis for a first
  launch, a commercial-licence offer for the AGPL parts and a metrics plan,
  every figure in them a hypothesis.
- **A benchmark scorer that can't be talked round.** An answer Salli can
  answer that opens by declining or hedging, that adds a figure Salli didn't
  give, or that advises (a ranking word, "you should buy", a product) is
  wrong whatever its headline; and a placeholder caveat is wrong on any
  answer whose figures are the person's own.
- **Market packs** (`markets/`): a country's tax rule sets, planning assumptions and pension schemes as cited data, outside the core, with the bar to add one. The first is `markets/lk`: rule sets for two years of assessment with the authority's worked examples, capital-market assumptions, and the provident funds. `tests/taxrules/test_market_packs.py` validates every pack's rule sets and runs their examples.

- **Fat tails in the odds.** The Monte Carlo draws each month's return
  from a Student-t, scaled to keep the pack's volatility; a CMA pack may
  give its `degrees_of_freedom` (3 to 100), else 5, listed in
  `placeholders` and shown in `cma.degrees_of_freedom`.
- **Withdrawals taxed beside guaranteed income.** A guaranteed income
  stream may name the income role it is taxed under (`tax_role`); the FI
  number and the odds gross withdrawals up at the marginal tax beside it.
- Scenario sales on a holding that names no cost method are costed by the
  active tax rules' `cost_basis`, as portfolio reads are, else first in,
  first out.

### Security

- **Outside text is fenced everywhere a model reads it.** Every free-text
  field any MCP read tool or in-app agent tool returns (descriptions,
  payees, memos, account and holding names, principle labels, decisions'
  text, signals, reminders, subscription reports, suggested rules, web
  search results) comes inside `{"untrusted_text": ...}`, fenced once where
  the answer is serialised, not field by field; a contract test walks every
  MCP read tool on the golden households. The in-app agents' approvals fail
  closed: an action whose approval the audit log can't record is not done.

### Breaking

#### Changed

- **The odds move.** Monte Carlo draws are fat-tailed now (above), so
  the same seed gives different odds, percentiles and horizon-derived
  rates than before; the share of paths where investing beats paying down
  a debt moves too.
- **FI pack 4.0.0: debt is scored by its size too.** Half of the debt
  component is now the debt-service ratio (scheduled payments ÷ income),
  no marks at 40%. Scores with debts move (the golden household's from
  57.59 to 57.42).
- **A signal's `severity` may be `low`.** Clients that map severities need
  the new value.

- **A stored entry never changes.** The database now refuses any update of
  a journal entry or posting, and any deletion but erasure, in open books
  as in closed ones; a reversal records the entry it reverses (`reverses`)
  and the original's `reversed_by` is read from it. The column
  `journal_entries.reversed_by` is gone. A refusal to store a closed year's
  tax no longer suggests moving the lock date earlier.

- MCP: every free-text string in a read tool's answer is now
  `{"untrusted_text": ...}` (names, labels, notes, titles too, not only
  descriptions and payees), and `get_budget_summary` takes a `budget_id`
  (from `list_budgets`) instead of picking the first budget.

## 0.5.0 — 2026-10-25

Every change under **Breaking** needs something written against the last
release to change with it, so this is a minor release of each part: the
server (and the console with it), the SDK and the CLI are all 0.5.0
([RELEASING.md](RELEASING.md#breaking-changes)).

### Added

- **Two more signals.** `emergency_fund_low`: cash and savings cover fewer
  months of average spending than the FI method's emergency target, once a
  full month is seen. `expensive_debt`: a declared debt charging at or above
  8% a year, Salli's labelled line (the placeholder real return plus a 4%
  margin, not any country's figure). A new action, `see_debts`, opens the
  baseline's debts in the console and Decide on the phone.
- **A stricter benchmark scorer.** A refusal must decline in its first
  sentence and quote no amount; a negative word must sit by the figure it
  signs; an answer quoting more than five tool figures is a dump however it
  is worded; text answers have a length cap; and an FI month that claims
  placeholders it doesn't rest on is wrong. A hedged prose dump of the tools'
  output, which scored 35 of 100, now scores 5.

- **Two-step sign-in.** Turn it on with `salli totp enable` or in the
  console's Settings: add the secret to an authenticator app, enter a code,
  and keep the ten recovery codes, shown once. From then on every sign-in
  with your password (Salli's sign-in, consent and device pages, so the
  console's step-up too; `POST /v1/auth/sessions`; `salli password`) also
  needs the app's code, or a recovery code, each good once; wrong codes are
  throttled like wrong passwords. `POST /v1/auth/totp`, `POST
  /v1/auth/totp/confirm` and `DELETE /v1/auth/totp` (the password and a
  code) turn it on and off, behind the step-up; `GET /v1/auth/me` says
  whether it is on (`totp_enabled`). The secret is sealed with
  `BYOK_ENCRYPTION_KEYS`. The owner turns it off for someone who has lost
  both with `salli-server members reset-password --clear-totp`. The app
  signs in on the same pages, so it asks for the code there. Migration
  `core_0027_totp`.
- **A fidelity benchmark for agents** (`benchmark/`,
  [docs/benchmark.md](docs/benchmark.md)): 100 questions a person asks their
  AI about their money, on the golden households, each answered by Salli's
  own tools into a committed key (`uv run python -m benchmark.answer_key`).
  `uv run python -m benchmark.run --model anthropic:<model>` (or
  `openai:<model>`) asks a model through Salli's whole MCP tool list
  in-process, on a connection that may only read, and scores how faithfully
  its answers quote Salli (whose figures the golden tests check): each
  answer's headline figure, with its sign, an FI month on placeholder
  assumptions only with that caveat, and pasted tool output never; fidelity
  overall and by category, and how many answers invented a figure, advised
  or pasted tool output. `--self-check` scores the key against itself; a
  contract test runs it, and the ways the scorer was gamed. No results are
  published yet.
- **Your AI starts from where you stand, and can find what you booked.**
  MCP `get_overview` is one small read of Salli's figures: net worth, cash
  and savings, free until payday and its low point, signals, the FI month
  and progress (null, with `fi.status` `not_enough_data`, under two full
  months observed), reminders due within 30 days, and how fresh the ledger is (`data_as_of`,
  `is_stale`). MCP `search_entries` finds entries by text, account, dates
  and amount, a page at a time (`next_cursor`), with the server's totals
  over every match, so "what did I spend at the bakery?" needs no sum by
  the model. The same search is `GET /v1/entries/search` and
  `salli entries search`.
- **Every MCP tool says whether it only reads** (MCP tool annotations:
  `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`). The
  Salli app now runs unasked only the tools the server marks read-only, and
  asks about every other, in place of guessing from their names.
- **A retried entry books once.** MCP `post_journal_entry` takes an optional
  `client_ref` (up to 180 characters); sent again, even at the same time, it
  returns the entry first booked with it (`already_posted`) and books
  nothing. It is kept as the entry's `external_ref` after `client-ref:`,
  which a unique index covers (migration `core_0028_mcp_scopes_audit`).

- **A briefing says an AI wrote it.** `AdvisoryReport` and `BriefingDraft`
  carry `written_by` (`"ai"`) and a `notice` ("Written by an AI from Salli's
  own figures. Not financial advice."), which `salli advisor` prints under
  every briefing in place of its own words.
- **Security and privacy, written down.** `docs/security.md` (the threat
  model, and the controls with the gaps still open), `docs/privacy.md` (what
  Salli stores, who else sees it and when, retention, export and erasure,
  and an impact assessment template), response times and supported versions
  in `SECURITY.md`, and a breaking-change policy in `RELEASING.md`.
- **The supply chain is checked.** Every workflow's actions are pinned to
  commit SHAs; Dependabot updates Python, npm, actions and base images
  weekly; CodeQL scans the Python and TypeScript; and CI runs pip-audit and
  npm audit (reporting only, until the current findings are fixed).
- **Savings: cash you keep, not spend.** An asset account's role may be
  `savings` (a savings account, an emergency fund, a term deposit). It counts
  as cash in net worth, FI's asset base, liquid savings and emergency-fund
  months, and never in the daily cash forecast, free until payday or the
  low-balance signals: an emergency fund no longer shows as money to spend.
  The plan counts a regular move into savings as staying in its cash, so FI
  doesn't move when an account becomes savings.
  - API (still v1): `asset_role` takes `savings` on accounts, opening
    balances and MCP's `create_account` and `update_account`; the baseline's
    balance `role` may be `savings`, and its `totals` add `savings`.
  - CLI: `--asset-role savings`, `salli profile balance-sheet`'s `:savings`,
    and a Savings line in `salli baseline`. The app's first run offers
    Savings between Cash to spend and Investments, and an asset account's
    screen changes its role later.
  - Migration `core_0026_savings_role` allows the role.

- **No FI score on too little data.** `GET /v1/fi/score` adds `status`
  (`ok`, or `not_enough_data` under two full months of income and spending)
  and `months_observed`. The app's Home and Independence screen, the
  console's Home and the CLI say "Needs two months of data" in place of the
  score and grade (the app's Independence screen in place of the FI month
  and progress too).

- **Day one on the phone.** Until a month of income and spending is in the
  books (the opening balances of first run are not), Home's Needs attention
  shows one row, Import a statement, in place of "Nothing needs attention".
  Under Free until payday, Home shows what it is made of: cash today,
  everyday spending, the cushion, what is held for goals, the low point and
  its day, and the server's notes.

- **Erasing an account leaves nothing behind, and the export has your
  conversations.** `DELETE /v1/onboarding/account` deletes the rows first,
  then the person's uploaded files and every conversation and review
  workflow thread in LangGraph's checkpoint tables; `counts` adds
  `stored_files` and `conversations`, or `stored_files_failed` or
  `conversations_failed` when some are left for the operator.
  `GET /v1/onboarding/export` adds `conversations`: each thread, newest
  first, with its messages in order (role, text, and the tools called, by
  name only).

### Security

- The tax agent and the briefing and return workflows refuse to build on the
  in-memory checkpointer in production (`ENVIRONMENT=production`), as the
  server's start-up already did, so nothing awaiting review can live only in
  memory there.
- Prompt injection is fenced: statement and bank descriptions, payees,
  documents and saved memories reach a model only inside an
  `untrusted_text` field, and every prompt says never to follow
  instructions there. The in-app agents' web search now asks the person
  first, and never carries their figures or payees.
- **Closed books keep their accounts' type and tax role in the database.**
  A trigger (migration `core_0032_account_freeze`) refuses changing either on
  an account with any posting on or before the lock date, even postings that
  net to zero, by whatever path.

- Every MCP tool call is in the audit log: a read as one row (the tool, the
  client and the outcome, no arguments), written before its answer is sent.
- An AI client's connection ends 90 days after the person approved it
  (`MCP_GRANT_LIFETIME_DAYS`), however often it refreshes; core_0029 gives
  existing connections that end. The console keeps its 12 hours; the CLI and
  the app have none.
- A client that registers itself may use only https or loopback redirects,
  never the device grant (Salli's CLI's alone), and the consent page shows its
  name beside "Not verified by Salli".
- Exporting everything and deleting the account go through the step-up in the
  console and the app; the console's export follows it.
- HSTS where `SALLI_PUBLIC_URL` is https; MCP's DNS rebinding protection on,
  for the public URL's host; production refuses to start without the Postgres
  checkpointer; compose believes forwarded addresses only from Caddy and pins
  the image to a release.

- **No known vulnerability in what ships, and CI now fails on one.** Python:
  aiohttp 3.14.5, anyio 4.15.1, certifi 2026.10.23, cryptography 50.0.2,
  langgraph-checkpoint-postgres 3.1.3, langgraph-sdk 0.4.4, langsmith 0.8.18,
  mcp 1.30.0, multidict 6.9.1, pillow 13.0.0, pydantic-settings 2.14.2,
  PyJWT 2.15.1, pypdf 6.21.2 and urllib3 2.8.0. python-jose, which has an
  unfixed key-confusion flaw and brought in ecdsa (also unfixed), is replaced
  by PyJWT for the MCP sign-in link and ChatGPT's ID token. The app: zod 4.6.7
  for the AI SDK, js-yaml 4.3.2, and `@bacons/apple-targets` on the same
  `@expo/plist` as Expo. The three advisories that remain, with no fixed
  release, are listed with why in [docs/security.md](docs/security.md#accepted-advisories).

### Breaking

#### Changed

- **FI pack 3.0.0.** "FI-ready" needs 100% progress to FI and "Strong" 50%;
  the debt component is scored by what the debts cost (their rates weighted by
  balance, no marks at 20%) where rates are known, by liabilities over assets
  otherwise; and under two full months of income and spending the engine's
  grade is "Not enough data", so every caller agrees with `status`. A
  household's score and grade can move.
- MCP `search_entries` and `list_pending_transactions` return `description`,
  `get_recurring_payments` `payee` and `examples`, the documents tools
  `content` and `description`, and the memory tools `value` as
  `{"untrusted_text": ...}` instead of a bare string.
- **Closed years keep their tax figure.** Computing or preparing a return
  for a tax year that ends on or before the lock date no longer stores a new
  computation: it is refused with a 409 `/problems/books-locked`. A preview
  (`persist=false`) still works and warns that the year is closed; the
  recompute sweep leaves closed years as they are.
- **An account holding a balance can't be closed.** `DELETE
  /accounts/{id}` (`salli accounts deactivate`) refuses it with a 409
  `/problems/account-not-empty`; move the balance first.

- `compose.yaml` runs a named release (0.4.1), not `latest`, and believes
  `X-Forwarded-For` only from Caddy (`FORWARDED_ALLOW_IPS=10.248.53.2`); set
  it to your own proxy's address if you use one. `/mcp` answers only requests
  whose Host is `SALLI_PUBLIC_URL`'s. Self-registered clients lose the device
  grant and plain-http redirects other than loopback.

- **One net worth.** Net worth over time and the balance sheet said a
  different net worth from the overview, FI and the reports for the same
  day: book value, with each foreign balance at the rates its entries
  recorded and no debt the ledger doesn't hold. Both are now the baseline's,
  as every other net worth is ([docs/baseline.md](docs/baseline.md#net-worth)):
  each account at the published rate for the day, judged on its own sign,
  and a declared debt the ledger doesn't hold at its principal.
  - API (still v1): `GET /v1/insights/net-worth` (MCP
    `get_net_worth_history`, `salli insights net-worth`): each point's
    `assets`, `liabilities` and `net_worth` are the baseline's as of the
    month's end, and this month's as of today, no longer book value; a new
    `notes` says what a point left out (an account in a currency with no
    published rate for that day). `GET /v1/reports/balance-sheet` (`salli
    reports balance-sheet`, `salli status`, the console's and the app's net
    worth): asset and liability lines at today's published rate, a line for
    each declared debt the ledger doesn't hold (`account_id` null, `code`
    empty; breaking for clients that took it to be a string), totals with
    each account judged on its own sign, and a new `notes`. Equity stays as
    the books keep it.
  - On the golden household, for 2026-10-11: 335,901.47 everywhere, where
    the history and the balance sheet said 344,026.47.
  - `LedgerRepository.balances_before`, `insights.net_worth_series`,
    `ledger.net_worth` and `LedgerService.get_net_worth` (book value) are
    gone; `BaselineService.worth` and `baseline.worth` /
    `baseline.worth_by_day` give what is owned and owed as of any days.

- **AI connections read unless you allow changes** (breaking for MCP clients
  that wrote without asking). A connection gets `mcp:read`, and
  `mcp:write` only when the person ticks **Allow changes** on the consent or
  device page (unticked to begin with); the Salli app's own AI always gets
  it, as the app asks before each change. A tool that isn't read-only, on a
  connection without `mcp:write`, answers an error (`isError`) telling the
  person to reconnect and allow changes, and does nothing. The scope a client
  asks for is no longer what it gets, and grants from before this only read:
  reconnect to allow changes.
  - API (still v1): `POST /mcp/oauth/consent` takes `allow_changes` (false
    by default).
  - The audit log is an audit trail: every MCP write, refused or not, records
    the person, the connection's client (`client_id`, new on
    `GET /v1/agent/audit-log`), the tool, its arguments and the outcome
    (`decision`: `succeeded`, `refused` or `failed`, no longer `approved`),
    in the transaction that makes the change, so a change whose row can't be
    written isn't made. A database trigger keeps the log append-only, except
    erasing an account.
  - Migration `core_0028_mcp_scopes_audit` adds `audit_logs.client_id`, the
    trigger, and the unique index for `client_ref`.

- **MCP tools fail as errors, with a code** (breaking for MCP clients that
  read `{"error": ...}` from a result). A tool that can't answer returns an
  error result (`isError` true) whose `error` has a `code` (`invalid_input`,
  `not_found`, `refused`, `scope`, `not_enough_data`, `unavailable`), a short
  `message`, `retryable`, and for input the `problems` with their paths; it
  used to answer `{"error": ...}` as data, and a malformed amount
  (`"1O.00"`) came back as a crash's raw text. Amounts and rates are read by
  one check that names the field. Arguments that don't fit a tool are
  `invalid_input` too.
- **MCP: the tool list is a third of the size** (119 KB to 39 KB as JSON).
  `run_scenario`, `compare_options`, `check_principles` and
  `record_decision` take scenarios as objects pointing to
  `get_scenario_schema`, which gives the schema once, with how tax, holdings
  and assets go into one in its `description`; Salli still validates each.
  Descriptions are sent on one line, without generated titles or the output
  schemas that only said "an object", and an optional argument as its type.

- **MCP: `suggested_tax_accounts` only reads** (breaking for MCP clients):
  its `apply` is gone, and `apply_suggested_tax_accounts` creates the
  missing accounts.

- **The advisor is a monthly briefing.** It describes Salli's own figures and
  signals and gives no advice: no recommendation, priority, product or rate
  research. The model writes sentences with slots (`{spending}`) and Salli
  fills in every figure; a draft that writes a digit, advises, judges or
  names a kind of product is refused and asked for once more.
  - API (still v1): `AdvisoryReport` and `BriefingDraft` now carry `summary`,
    `notes`, `figures`, `signals` and `assumptions`, in place of
    `fire_tier_assessment` and `recommendations`.
    `POST /v1/advisor/reports/{report_id}/recommendations/{rec_id}/apply` and
    `/dismiss` are gone. The reads list briefings only; the advisor's earlier
    reports, with their recommendations, stay in the export.
  - MCP and the agent: `get_latest_advisor_report` and `run_wealth_advisor`
    are now `get_latest_briefing` and `run_briefing`.
  - CLI: `salli advisor apply` and `dismiss` are gone; `run`, `latest`,
    `reports` and `briefing` show the briefing.
  - Migration `core_0024_briefings` adds `advisory_reports.briefing`.

- **Safe to spend is "free until payday".** It used to be your cash less
  scheduled bills only. Now it also takes off a usual day's everyday spending
  until payday, a cushion (a tenth of a usual month's spending) and the cash
  set aside for goals. `GET /v1/insights/safe-to-spend` adds `low_point`,
  `low_point_date`, `everyday_spending`, `cushion` and `held_for_goals`;
  `amount` (breaking: same field, new meaning) is the low point less the
  cushion and goals' cash. Scenarios and principle checks read the same
  figure.

- **First run books only what is true.** An opening balance for something
  you own takes an `asset_role` (cash, investment or other); without one it
  is "other", never cash, so a brokerage account or a car no longer counts as
  money to spend. An opening balance in another currency opens its account
  in that currency (it used to open in the base currency, freezing it at the
  day's rate), and one for an existing account in another currency is
  refused. `POST /v1/onboarding/income` opens an income account per
  source and posts nothing (it used to book a made-up month of pay dated
  today); it answers `income_accounts`, and `amount`, `currency` and
  `fx_rate` are gone from `IncomeItem`. `salli profile balance-sheet` takes
  `CODE:NAME:TYPE:AMOUNT[:ROLE]`; `salli profile income` takes `CODE:NAME`.

- **Closed books, and reversals that say why.** You can close your books up
  to and including a day before today, so a filed year stays as filed:
  nothing is posted, reversed, imported, changed or retagged on or before
  it (a 409 `books-locked` problem), an account with entries there keeps
  its type and tax role, and database triggers refuse an entry or posting
  added, changed or deleted there whatever path it comes by (erasing your
  account aside). Every change of the lock date (set, later, earlier,
  cleared) is in the audit log, with the client. A reversal is dated the
  original's day while that day is open, so correcting last month's
  category corrects last month, and today when it is closed; it has the
  source `reversal`, and needs a reason, kept in its description
  ("Reversal of Lunch: Paid twice").
  - API (still v1): `PUT /v1/ledger/lock-date` (`{"lock_date": "YYYY-MM-DD"}`,
    or null to open the books); moving it earlier takes your own sign-in,
    with a recent password where the client asks for one (the console and
    the app). The profile carries `lock_date`. `POST
    /v1/entries/{entry_id}/reverse` takes `{"reason": "..."}` (breaking).
  - CLI: `salli ledger lock <date>` and `salli ledger unlock`;
    `salli entries reverse` needs `--reason`. The console and the app ask
    for the reason. No MCP tool changes the lock date.
  - Migration `core_0025_books_lock` adds `user_profiles.lock_date`, the
    trigger, and `reversal` to the entry sources; `core_0030_lock_edits`
    extends the trigger to changes and deletions, and to postings.

#### Removed

- **The FIRE strategy generator.** A model no longer drafts a FIRE strategy:
  its allocation buckets, returns and withdrawal rate amounted to
  personalised advice. FI figures now rest only on your own assumptions
  (each with its source) or the labelled placeholders.
  - API (still v1): `GET /v1/fi/strategy`, `GET /v1/fi/strategy/history` and
    `POST /v1/fi/strategy/generate` are gone, with the `FireStrategy`,
    `FireStrategyBucket`, `FireStrategySummary` and `FireStrategyHistory`
    schemas. An assumption's `origin` is now `user` or `placeholder`.
    `versions.fire_strategy` is no longer in a scenario's result; decisions
    recorded before keep it, as recorded.
  - SDK: `streamStrategyGeneration` and `StrategyEvent`, and the generated
    `fiStrategyGet`, `fiStrategyHistory` and `fiStrategyGenerate`.
  - CLI: `salli fi strategy show`, `history` and `generate`.
  - Console and app: the strategy section and screen.
  - Extensions: `AIAction.FIRE_STRATEGY` and `Surface.FIRE_STRATEGY`.
  - A stored strategy's target spending no longer sets the FI number: it is a
    year of your average spending over your withdrawal rate.
  - Strategies drafted before stay yours: `GET /v1/onboarding/export` lists
    them under `fire_strategies`, and erasing your account deletes them.
