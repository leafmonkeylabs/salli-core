# Hosting Salli for someone else

A hosted beta runs **one Salli per person or household**: its own machine
(or VM), its own database, its own secrets, its own domain. Nothing is
shared between them, so one customer's data never sits beside another's,
and each instance is exactly what a self-hoster runs
([self-host.md](self-host.md)): the published image and `compose.yaml`.

## What you need

- A small Linux machine per instance with Docker and the compose plugin (2
  vCPU and 2 GB of memory is plenty for a household), ports 80 and 443
  open.
- A domain name for it, its DNS pointing at the machine
  (`alex.example.org`).
- A checkout of this repository on the machine, at the release you run.

## Set one up

```bash
deploy/host.sh init /srv/salli alex.example.org alex@example.org EUR < password-file
```

`init` copies `compose.yaml` into `/srv/salli`, writes its `.env`
(`SALLI_DOMAIN`, `SALLI_PUBLIC_URL=https://alex.example.org`, the `tls`
profile on), starts Postgres, Salli and Caddy (which gets the certificate),
makes the **owner** with that email, ledger currency and the password from
stdin (or asks, in a terminal), and runs `salli-server doctor`. Hand the
password over separately, and ask the owner to change it
(`salli password` from their own computer) and turn on two-step sign-in
(`salli totp enable`).

The owner then adds their household (`salli-server members add`, run on the
machine by you at their request) and connects their AI client to
`https://alex.example.org/mcp` ([ai-clients.md](ai-clients.md)).

Anything else (an AI key for the instance, digests, extensions) goes in
`/srv/salli/.env` as in [self-host.md](self-host.md#configuration), then
`docker compose --project-directory /srv/salli up -d`.

## Backups

```bash
deploy/host.sh backup /srv/salli
```

writes the database (`pg_dump`) and the files and secrets (a tar) into
`/srv/salli/backups`, readable only by its owner, and keeps two weeks there.
Run it nightly from cron (`init` prints the line), and copy `backups/` off
the machine, encrypted: the secrets are in it. Restore as in
[self-host.md](self-host.md#backup-and-restore), and rehearse a restore
before the beta starts.

## Upgrades

```bash
git -C /path/to/salli checkout server-vX.Y.Z
deploy/host.sh upgrade /srv/salli
```

backs up first, takes the release's `compose.yaml`, pulls its image and
restarts; Salli migrates the database as it starts. Migrations only go
forward, so the backup is the way back.

## Measuring a beta

Each instance can count its own use without anyone's data leaving it:
set `SALLI_USAGE_COUNTERS=true` in its `.env` and run
`docker compose exec salli salli-server stats` (members active, statement
entries imported and reconciliations completed in the last seven days;
`--json` for a script). Salli itself never sends them anywhere. The plan
for what to count and how is [business/metrics.md](../business/metrics.md).

A hosted service that wants the counts in one place reports them from an
**extension** (`salli/extensions.py`): a `salli-server` command group of its
own that reads the same counts (`salli.adapters.db.usage_counts`) and sends
the totals, run from the instance's cron. It is the hosted service's code,
said in its privacy notice and agreed by the pilot's participants; the open
core ships nothing that sends.

## Charging for it

Salli has no billing, plans or metering, and adds none. A hosted service
that charges does so outside the core:

- **Payments** go through a licensed payment processor, from the service's
  own sign-up and account pages, which sit outside Salli and create the
  instance (`deploy/host.sh init`) once paid.
- **Limits**, if any, are an extension's `UsageMeter` (refusing an AI action
  past an allowance) and `EntitlementPolicy` (shaping a surface), enabled
  with `SALLI_EXTENSIONS`. The defaults meter nothing and show everything.
- **Ending** a subscription is the service's: export the person's data for
  them (`salli profile export`), then stop the instance and delete its volumes and
  backups.

See [business/commercial-licence.md](../business/commercial-licence.md) for
what a hosted service owes under the licence.
