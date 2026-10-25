# Usage collector (example)

A minimal receiver for the weekly reports `salli-server stats --send` makes
(see [docs/self-host.md](../../docs/self-host.md#usage-reports) for exactly
what one holds). One Python file, standard library only, SQLite: one row per
install id and week. It is an example for running a pilot, not part of Salli.

```bash
python collector.py --db usage.sqlite --port 8085   # behind TLS
curl -s localhost:8085/v1/usage                     # totals by week
```

On each instance, as its owner chooses:

```bash
SALLI_USAGE_COUNTERS=true
SALLI_USAGE_REPORT_URL=https://counts.example.org/v1/usage
SALLI_USAGE_INSTALL_ID=any-value-you-pick   # change it to rotate
# weekly, from cron:
salli-server jobs send-usage
```
