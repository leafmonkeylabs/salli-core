# From the Python `salli` to `salli` and `salli-server`

Salli used to have one Python command line, `salli`, that did everything: it
ran the server, and it also kept your books, by reading and writing the
database directly as whoever `SALLI_USER_ID` named. It now has two:

- **`salli`**, the TypeScript command line in [`packages/cli`](../packages/cli/README.md)
  (`npm install --global @leafmonkeylabs/salli`). Everything a person does with
  their own finances. It is a client of the API, like the web and mobile apps
  and the MCP server's AI clients, so every surface goes through the same
  routes, the same sign-in and the same checks, and it works from any machine.
- **`salli-server`**, the Python package's only console script. What must run
  where the server runs: `setup`, `serve`, `doctor`, `db`, `members`, and
  `jobs` that act on every user at once. Enabled extensions add their own
  groups to it.

There was no deprecation window: Salli had no users to migrate yet, and the
`salli` name now belongs to the TypeScript CLI alone.

## For deployments

- Start commands change name: `salli db upgrade` is now
  `salli-server db upgrade`, `salli serve` is `salli-server serve`, and an
  extension's groups move with them (`salli cloud …` becomes
  `salli-server cloud …`). **The hosted product must switch its container start
  command to `salli-server` when it moves off its salli-core v0.1.0 pin.**
- A system crontab that ran `salli advisor run-due` or `salli banks sync-due`
  runs `salli-server jobs run-advisor` and `salli-server jobs sync-banks`. Both
  now exit 1 when any run failed.
- `salli-server doctor` is new: configuration, extensions, database
  reachability, every migration history at its head, authentication and the
  server's secrets (set or not, never their values). It exits 1 when anything
  fails, so it can gate a deploy.
- The Python import surface extensions build on is unchanged:
  `salli.interfaces.cli.support` (`console`, `emit`, `json_mode`,
  `require_user`, `services`, `leaf_commands`, `with_json_option`,
  `resolve_id`, `money`, `amount`) and `salli.interfaces.cli.main` (`app`,
  `cli()`, `main()`). `ExtensionSpec.cli_groups` mounts on `salli-server`.
- `salli.interfaces.parity` is gone. Its job, making sure every route has a
  command, is now `packages/cli/test/api-coverage.test.ts`, against the
  TypeScript CLI.

## Every old command

171 commands: **153** have a `salli` command that already did the same thing
through the API; **7** got one on this change (marked **(new)**); **8** stay
with the server under `salli-server`; **3** have no replacement yet (below).

| Old (Python `salli`) | Now | API operation |
|---|---|---|
| `salli setup` | `salli-server setup` | server only |
| `salli serve` | `salli-server serve` | server only |
| `salli whoami` | `salli whoami` | auth.me |
| `salli accounts list` | `salli accounts list` | accounts.list |
| `salli accounts add` | `salli accounts add` | accounts.create |
| `salli accounts show` | `salli accounts show` | accounts.overview |
| `salli accounts update` | `salli accounts update` | accounts.update |
| `salli accounts deactivate` | `salli accounts deactivate` | accounts.deactivate |
| `salli accounts reactivate` | `salli accounts reactivate` | accounts.reactivate |
| `salli entry add` | `salli entries add` | entries.create |
| `salli entry show` | `salli entries show` | entries.get, entries.provenance |
| `salli entry reverse` | `salli entries reverse` | entries.reverse |
| `salli entry list` | `salli entries list` | entries.list |
| `salli entry parse` | `salli add` | entries.parse |
| `salli entry tag` | `salli entries tag` | entries.postings.setTags |
| `salli ledger trial-balance` | `salli ledger trial-balance` | ledger.trialBalance |
| `salli ledger income-statement` | `salli ledger income-statement` | ledger.incomeStatement |
| `salli ledger tags` | `salli tags` | tags.list |
| `salli tax compute` | `salli tax compute` | tax.compute |
| `salli tax explain` | `salli tax explain <line>` | tax.explain |
| `salli tax prepare-return` | `salli tax return prepare`, `salli tax return review <thread>` | tax.returns.prepare, tax.returns.get, tax.returns.resume |
| `salli tax packs` | none: there are no built-in packs; your own rule sets are `salli tax rules list` | tax.ruleSets.list |
| `salli tax recompute-stored` | `salli-server jobs recompute-tax` | every user's stored results; no API |
| `salli tax latest` | `salli tax latest` | tax.latest |
| `salli tax year` | `salli tax year` | tax.currentYear |
| `salli agent chat` | `salli chat` | agent.chat, agent.resume |
| `salli agent sessions` | `salli sessions list` | agent.sessions.list |
| `salli agent audit-log` | `salli sessions audit-log` | agent.auditLog |
| `salli agent history` | `salli sessions show` | agent.history |
| `salli agent resume` | `salli chat` (approvals are answered in the conversation) | agent.resume |
| `salli agent delete-session` | `salli sessions delete` | agent.sessions.delete |
| `salli parse upload` | `salli import` | statements.upload |
| `salli parse pending` | `salli statements pending` | statements.pending |
| `salli parse post` | `salli statements post` | statements.post |
| `salli parse discard` | `salli statements discard` | statements.discard |
| `salli parse categorize` | `salli statements categorize` | statements.categorize |
| `salli parse list` | `salli statements list` | statements.list |
| `salli reminders list` | `salli reminders list` | reminders.list |
| `salli reminders add` | `salli reminders add` | reminders.create |
| `salli reminders done` | `salli reminders done` | reminders.markDone |
| `salli reminders delete` | `salli reminders delete` | reminders.delete |
| `salli reminders seed` | `salli reminders seed` | reminders.seedFilingCalendar |
| `salli reminders sync-alerts` | `salli reminders sync-alerts` | reminders.syncAlerts |
| `salli fi score` | `salli fi score` | fi.score.get, fi.score.recompute |
| `salli fi history` | `salli fi history` | fi.score.history |
| `salli fi projections` | `salli fi projections` | fi.projections |
| `salli fi assumptions` | `salli fi assumptions` | fi.assumptions |
| `salli fi surplus` | `salli fi surplus` | fi.surplus |
| `salli fi simulate-purchase` | `salli fi simulate-purchase` (or fi afford) | fi.simulatePurchase |
| `salli fi goals list` | `salli goals list` | goals.list |
| `salli fi goals add` | `salli goals add` | goals.create |
| `salli fi goals update` | `salli goals update` | goals.update |
| `salli fi goals delete` | `salli goals delete` | goals.delete |
| `salli fi goals allocate` | `salli goals allocate` | goals.allocations.set |
| `salli fi goals allocations` | `salli goals allocations` | goals.allocations.list |
| `salli fi strategy show` | `salli fi strategy show` | fi.strategy.get |
| `salli fi strategy history` | `salli fi strategy history` | fi.strategy.history |
| `salli fi strategy generate` | `salli fi strategy generate` | fi.strategy.generate |
| `salli advisor run` | `salli advisor run` | advisor.run |
| `salli advisor apply` | `salli advisor apply` | advisor.recommendations.apply |
| `salli advisor dismiss` | `salli advisor dismiss` | advisor.recommendations.dismiss |
| `salli advisor briefing` | `salli advisor briefing` **(new)** | advisor.briefing.prepare, advisor.briefing.resume |
| `salli advisor daily-briefing` | `salli advisor daily-briefing` | advisor.dailyBriefing.get, .set |
| `salli advisor run-due` | `salli-server jobs run-advisor` | every due user, in-process (advisor.cron.runDue over HTTP) |
| `salli advisor reports list` | `salli advisor reports` | advisor.reports.list |
| `salli advisor reports latest` | `salli advisor latest` | advisor.reports.latest |
| `salli documents list` | `salli documents list` | documents.list |
| `salli documents show` | `salli documents show` | documents.get |
| `salli documents delete` | `salli documents delete` | documents.delete |
| `salli documents upload` | `salli documents upload` | agent.files.upload |
| `salli profile show` | `salli profile get` (or profile show) | profile.get |
| `salli profile update` | `salli profile set` | profile.update |
| `salli profile risk-questionnaire` | `salli profile risk-questionnaire` **(new)** | onboarding.riskQuestionnaire |
| `salli profile balance-sheet` | `salli profile balance-sheet` **(new)** | onboarding.balanceSheet |
| `salli profile income` | `salli profile income` **(new)** | onboarding.income |
| `salli profile export` | `salli profile export` | account.export |
| `salli profile delete-account` | `salli profile delete-account` **(new)** | account.delete |
| `salli budget list` | `salli budgets list` | budgets.list |
| `salli budget add` | `salli budgets add` | budgets.create |
| `salli budget summary` | `salli budgets summary` | budgets.summary |
| `salli budget delete` | `salli budgets delete` | budgets.delete |
| `salli budget show` | `salli budgets show` | budgets.get |
| `salli budget update` | `salli budgets update` | budgets.update |
| `salli debt list` | `salli debts list` | debts.list |
| `salli debt add` | `salli debts add` | debts.create |
| `salli debt update` | `salli debts update` | debts.update |
| `salli debt delete` | `salli debts delete` | debts.delete |
| `salli debt payoff-plan` | `salli debts payoff-plan` | debts.payoffPlan |
| `salli debt show` | `salli debts show` | debts.get |
| `salli portfolio list` | `salli holdings list` | holdings.list |
| `salli portfolio add` | `salli holdings add` | holdings.create |
| `salli portfolio update` | `salli holdings update` | holdings.update |
| `salli portfolio delete` | `salli holdings delete` | holdings.delete |
| `salli portfolio summary` | `salli portfolio` (portfolio summary) | portfolio.summary |
| `salli portfolio show` | `salli holdings show` | holdings.get |
| `salli portfolio lots` | `salli portfolio lots` | holdings.lots |
| `salli portfolio performance` | `salli portfolio performance` | portfolio.performance, holdings.performance |
| `salli portfolio transactions list` | `salli portfolio transactions list` | holdings.transactions.list |
| `salli portfolio transactions add` | `salli portfolio transactions add` | holdings.transactions.create |
| `salli portfolio transactions show` | `salli portfolio transactions show` | holdings.transactions.get |
| `salli portfolio transactions update` | `salli portfolio transactions update` | holdings.transactions.update |
| `salli portfolio transactions delete` | `salli portfolio transactions delete` | holdings.transactions.delete |
| `salli portfolio prices list` | `salli portfolio prices list` | portfolio.prices.list |
| `salli portfolio prices set` | `salli portfolio prices set` | portfolio.prices.set |
| `salli portfolio prices delete` | `salli portfolio prices delete` | portfolio.prices.delete |
| `salli subscription list` | `salli subscriptions list` | subscriptions.list |
| `salli subscription add` | `salli subscriptions add` | subscriptions.create |
| `salli subscription update` | `salli subscriptions update` | subscriptions.update |
| `salli subscription delete` | `salli subscriptions delete` | subscriptions.delete |
| `salli subscription report` | `salli subscriptions report` | subscriptions.reports, subscriptions.report |
| `salli subscription show` | `salli subscriptions show` | subscriptions.get |
| `salli insurance report` | `salli insurance report` | insurance.report |
| `salli insurance policy list` | `salli insurance policies list` | insurance.policies.list |
| `salli insurance policy add` | `salli insurance policies add` | insurance.policies.create |
| `salli insurance policy update` | `salli insurance policies update` | insurance.policies.update |
| `salli insurance policy delete` | `salli insurance policies delete` | insurance.policies.delete |
| `salli insurance policy show` | `salli insurance policies show` | insurance.policies.get |
| `salli insurance target set` | `salli insurance targets set` | insurance.targets.set |
| `salli insurance target list` | `salli insurance targets list` | insurance.targets.list |
| `salli insurance target delete` | `salli insurance targets delete` | insurance.targets.delete |
| `salli reports balance-sheet` | `salli reports balance-sheet` | reports.balanceSheet |
| `salli reports net-worth` | `salli reports net-worth` | reports.netWorth |
| `salli reports goal-progress` | `salli reports goal-progress` | reports.goalProgress |
| `salli reports export` | `salli reports export` | reports.exportCsv |
| `salli db upgrade` | `salli-server db upgrade` | server only |
| `salli db current` | `salli-server db current` | server only |
| `salli onboarding status` | `salli onboarding status` **(new)** | onboarding.status |
| `salli onboarding complete` | `salli onboarding complete` **(new)** | onboarding.complete |
| `salli llm-keys list` | `salli llm-keys list` | llmKeys.list |
| `salli llm-keys set` | `salli llm-keys set` | llmKeys.set |
| `salli llm-keys delete` | `salli llm-keys delete` | llmKeys.delete |
| `salli ai host` | `salli ai host` | ai.host.get |
| `salli ai status` | `salli ai status` | ai.settings.get, ai.chatgpt.get |
| `salli ai use` | `salli ai use` | ai.settings.set |
| `salli ai models` | `salli ai models` | ai.models.list |
| `salli ai set-models` | `salli ai set-models` | ai.models.set |
| `salli ai connect` | `salli ai connect` | ai.chatgpt.connect |
| `salli ai disconnect` | `salli ai disconnect` | ai.chatgpt.disconnect |
| `salli tokens create` | `salli tokens create` | tokens.create |
| `salli tokens list` | `salli tokens list` | tokens.list |
| `salli tokens revoke` | `salli tokens revoke` | tokens.revoke |
| `salli rules list` | `salli rules list` | rules.list |
| `salli rules add` | `salli rules add` | rules.create |
| `salli rules show` | `salli rules show` | rules.get |
| `salli rules update` | `salli rules update` | rules.update |
| `salli rules delete` | `salli rules delete` | rules.delete |
| `salli rules test` | `salli rules test` | rules.test |
| `salli rules suggest` | `salli rules suggest` | rules.suggestions |
| `salli export beancount` | `salli export beancount` | exports.beancount |
| `salli export hledger` | `salli export hledger` | exports.hledger |
| `salli insights cash-flow` | `salli insights cash-flow` | insights.cashFlow |
| `salli insights spending` | `salli insights spending` | insights.spending |
| `salli insights net-worth` | `salli insights net-worth` | insights.netWorth |
| `salli insights recurring` | `salli insights recurring` | insights.recurring |
| `salli insights forecast` | `salli insights forecast` | insights.forecast |
| `salli insights safe-to-spend` | `salli insights safe-to-spend` | insights.safeToSpend |
| `salli insights signals` | `salli insights signals` | insights.signals |
| `salli banks list` | `salli banks list` | bankConnections.list |
| `salli banks connect` | `salli banks connect` | bankConnections.connect |
| `salli banks map` | `salli banks map` | bankConnections.mapAccount |
| `salli banks sync` | `salli banks sync` | bankConnections.sync |
| `salli banks sync-due` | `salli-server jobs sync-banks` | every user, in-process (bankConnections.cron.syncDue over HTTP) |
| `salli banks disconnect` | `salli banks disconnect` | bankConnections.disconnect |
| `salli mcp status` | `salli mcp status` | mcp.enabled.get |
| `salli mcp enable` | `salli mcp enable` | mcp.enabled.set |
| `salli mcp disable` | `salli mcp disable` | mcp.enabled.set |
| `salli mcp connections` | `salli mcp connections` | mcp.connections.list |
| `salli mcp revoke` | `salli mcp revoke` | mcp.connections.revoke |
| `salli members add` | `salli-server members add` | server only |
| `salli skills list` | `salli skills list` | no API operation (bundled in the CLI) |
| `salli skills install` | `salli skills install` | no API operation (bundled in the CLI) |

Names that changed on the way: `entry` is `entries`, `parse` is `import` and
`statements`, `agent` is `chat`, `ask` and `sessions`, `fi goals` is `goals`,
`budget`/`debt`/`subscription` are plural, `portfolio`'s holdings are
`holdings` (with `portfolio` keeping the summary, transactions, lots, prices
and performance), `insurance policy`/`target` are `policies`/`targets`, and
`profile show`/`update` are `profile get`/`set`. Accounts are named by code or
name as well as id.

## Not carried over

These had no API operation, so no client can offer them until one exists:

- **`salli skills list` / `install`** are now in the TypeScript CLI (with
  `uninstall`, `--project` and `--dir`). The skills live in
  [`packages/cli/skills`](../packages/cli/skills) and are bundled into the CLI
  (`npm run generate:skills`), so the standalone binaries carry them too.

## API operations no command calls

`packages/cli/test/api-coverage.test.ts` lists them with their reasons: the
OAuth protocol endpoints (`salli login` and `logout` reach them through the
SDK at the URLs `/v1/meta` names), the MCP consent screen's two endpoints, the
liveness probe, the two scheduler routes behind `X-Cron-Secret` (operators use
`salli-server jobs`), `accounts.get` (`salli accounts show` uses the overview,
which includes it) and `onboarding.goals` (the wizard's batch form of
`goals.create`).
