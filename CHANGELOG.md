# Changelog

## Unreleased

Every change under **Breaking** needs something written against the last
release to change with it, so the next releases are minor bumps: the SDK and
the CLI are 0.5.0, and the server's next release is 0.5.0
([RELEASING.md](RELEASING.md#breaking-changes)).

### Added

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
- **An accuracy benchmark for agents** (`benchmark/`,
  [docs/benchmark.md](docs/benchmark.md)): 100 questions a person asks their
  AI about their money, on the golden households, each answered by Salli's
  own tools into a committed key (`uv run python -m benchmark.answer_key`).
  `uv run python -m benchmark.run --model anthropic:<model>` (or
  `openai:<model>`) asks a model through Salli's MCP tools in-process and
  scores its answers: accuracy overall and by category, and how many
  answers invented a figure or advised. `--self-check` scores the key
  against itself; a contract test runs it. No results are published yet.
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
  nothing is posted, reversed or imported on or before it (a 409
  `books-locked` problem), and a database trigger refuses an entry dated
  there whatever path it comes by. A reversal is now dated the day it is
  made, never the original's day, has the source `reversal`, and needs a
  reason, kept in its description ("Reversal of Lunch: Paid twice").
  - API (still v1): `PUT /v1/ledger/lock-date` (`{"lock_date": "YYYY-MM-DD"}`,
    or null to open the books); moving it earlier takes your own sign-in,
    with a recent password where the client asks for one (the console and
    the app). The profile carries `lock_date`. `POST
    /v1/entries/{entry_id}/reverse` takes `{"reason": "..."}` (breaking).
  - CLI: `salli ledger lock <date>` and `salli ledger unlock`;
    `salli entries reverse` needs `--reason`. The console and the app ask
    for the reason. No MCP tool changes the lock date.
  - Migration `core_0025_books_lock` adds `user_profiles.lock_date`, the
    trigger, and `reversal` to the entry sources.

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
