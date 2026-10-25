# Changelog

## Unreleased

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
