# Changelog

## Unreleased

### Changed

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
  money to spend. `POST /v1/onboarding/income` opens an income account per
  source and posts nothing (it used to book a made-up month of pay dated
  today); it answers `income_accounts`, and `amount`, `currency` and
  `fx_rate` are gone from `IncomeItem`. `salli profile balance-sheet` takes
  `CODE:NAME:TYPE:AMOUNT[:ROLE]`; `salli profile income` takes `CODE:NAME`.

### Removed

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
