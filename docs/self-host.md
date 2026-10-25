# Running your own Salli

Salli runs on one machine with Docker: the server and its Postgres database,
started from one compose file. You use it from your own computer with the
`salli` command line, and from your AI client over MCP.

Salli keeps its own accounts. Signing in needs nothing but the database:
there is no outside auth service and no email to configure (decision D13).

- [What you need](#what-you-need)
- [Quickstart](#quickstart)
- [Who can sign in](#who-can-sign-in)
- [The console](#the-console)
- [Configuration](#configuration)
- [HTTPS on your own domain](#https-on-your-own-domain)
- [Scheduled jobs](#scheduled-jobs)
- [Digests](#digests)
- [Backup and restore](#backup-and-restore)
- [Upgrades](#upgrades)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

## What you need

- **Docker** with Compose 2.24 or later (Docker Desktop, or Docker Engine
  with the compose plugin), on amd64 or arm64.
- About **2 GB of memory** and a few GB of disk.
- **Node.js 22** on the computer you use Salli from, for the `salli` command
  line.
- Optionally, an [Anthropic API key](https://console.anthropic.com/). Without
  one, everything but the AI features works, and each person can bring their
  own key or ChatGPT plan instead.

## Quickstart

On the machine that will run Salli:

```bash
mkdir salli && cd salli
curl -fsSLO https://raw.githubusercontent.com/leafmonkeylabs/salli-core/main/compose.yaml
docker compose up -d
docker compose exec salli salli-server setup
```

`setup` asks for your email, a password (at least 12 characters) and the
currency you keep your money in. It creates your account, which owns the
instance, and a starter chart of accounts.

Then, on your own computer:

```bash
npm install --global @leafmonkeylabs/salli
salli login
```

`salli login` opens your browser at Salli's sign-in page, where you sign in
with that email and password. Without a browser (over SSH, say), it shows a
code to approve from another device: `salli login --device`. If Salli runs on
another machine, name it: `salli login --server http://<host>:8000`.

What `docker compose up` starts:

| Service | What it is |
|---|---|
| `secrets` | Generates the server's secrets on the first run, into the `secrets` volume, then exits. It never replaces one. |
| `postgres` | Postgres 17. It publishes no port and is on a network with no way out: only Salli reaches it. |
| `salli` | The API, the MCP server and the sign-in pages, on `127.0.0.1:8000`. It migrates the database each time it starts, then serves. |

Data lives in named volumes: `postgres` (the database), `files` (uploaded
statements and receipts) and `secrets`. `docker compose down` keeps them;
`docker compose down -v` deletes them, and everything in Salli with them.

> [!NOTE]
> From a clone of the repository, `docker compose up -d --build` builds the
> image from source instead of pulling it.

`docker compose exec salli salli-server doctor` checks the configuration, the
database, the migrations and the owner, and never prints a secret.

## Who can sign in

There is no sign-up. The owner adds everyone else, from the server:

| To… | Run |
|---|---|
| Add a member (a partner, a household member) | `docker compose exec salli salli-server members add partner@example.com` |
| Invite someone to set their own password (and two-step sign-in) | `docker compose exec salli salli-server members invite partner@example.com`: a link, good once for seven days, that you pass on yourself |
| See who can sign in | `docker compose exec salli salli-server members list` |
| Set a forgotten password | `docker compose exec salli salli-server members reset-password partner@example.com` |
| …and sign them out everywhere | add `--sign-out-everywhere` |
| …and turn off their two-step sign-in (a lost authenticator app and recovery codes) | add `--clear-totp` |

Each member has their own ledger and signs in with `salli login`. Salli sends
no email, so a forgotten password is reset by the owner, never by a link.

A member may let another member read their books, and change nothing: `salli
access grant partner@example.com` (a recent password where the sign-in asks
for one; never a token or another application). Both see it in `salli access
list`, and either ends it with `salli access revoke`. The other member reads
by naming the books (`salli --books <member-id> ...`, the `Salli-Books`
header): only reads of the books (accounts, entries, reports, plans, tax),
never sign-ins, tokens, keys, documents, imports or exports. Giving,
receiving, ending and every read are in the audit logs.

People change their own password with `salli password`. That signs out their
other sessions; their CLI and console sign-ins and personal access tokens keep
working. `salli sign-ins list` shows every way they are signed in (sessions,
the CLI on each machine, the console in each browser tab), and `salli
sign-ins revoke` ends one.

A reset signs out every session, and lifts any lock from failed sign-ins.
`--sign-out-everywhere` also revokes the person's CLI and console sign-ins,
AI connectors and personal access tokens: use it when you think an account
was taken over.

How each way in works:

| Way in | How | May activate tax rules |
|---|---|---|
| The `salli` CLI | `salli login`: the browser or device page, with your password | yes |
| The console | `salli ui`, or the server's `/console` in a browser: Salli's sign-in page, with your password | only within 5 minutes of entering the password; it asks for it again first |
| The Salli app (in development) | Salli's sign-in page in the phone's secure browser sheet, with your password; HTTPS needed | only within 5 minutes of entering the password |
| A session | `POST /v1/auth/sessions` with your email and password, for an app or a script | yes |
| A personal access token | `salli tokens create`, for scripts and CI | only if made with `--allow tax:activate` |
| An AI client over MCP | approved on Salli's consent page with your password | never |

## The console

The console is Salli in a browser: where you stand, the decision lab, imports,
tax rules and settings, as pages. The server serves it at
`{SALLI_PUBLIC_URL}/console`; `salli ui` opens it (or prints the address with
`--no-open`, to type into a phone). Each household member signs in with their
own email and password, on Salli's own sign-in page; the console has no
sign-in form of its own and is handed nothing by the CLI.

The console has:

- **Home**: where you stand, as `salli status` shows it (net worth, safe to
  spend, the month so far, the FI score, what needs attention, what's
  coming up, decisions due for review, net worth over time).
- **Cash**, **Attention** and **Independence**: the cash forecast, cash
  flow and spending; signals and reminders; the FI number and its
  assumptions.
- **Decide**: the decision lab (the baseline, templates, scenarios,
  principles, the journal and reviews). Experimental: it works, but may
  change before the first pilots end ([scope](scope.md)).
- **Books**: the accounts and the ledger, adding and reversing an entry;
  **imports** (a statement file uploaded from your device, then a review
  queue where you choose accounts and post or discard: nothing is booked
  until you post it, and nothing twice) and categorisation **rules**. Bank
  connections are shown there; connecting one stays with `salli banks`.
- **Tax**: your tax line by line from the rules you activated, each line
  explained; your rule sets and their versions, each reviewed (what is
  new, with its sources, and every worked example) and activated by you.
  Drafting rules stays with your AI agent and the CLI.
- **Settings**: your profile and sign-ins; personal access tokens (a new
  token is shown once); AI connections (MCP on or off, connected clients,
  your own model keys, never shown again once saved); digests; and your
  data, saved as Beancount, hledger or JSON. Members stay with
  `salli-server members`.

Home and the decision lab offer **Think this through with your AI**, which
copies a prompt for your own AI client over MCP: the console holds no chat
and sends nothing anywhere.

The image carries the built console (`SALLI_CONSOLE_DIR=/opt/salli-console`);
`docker compose up` serves it at `/console`, and `salli ui` opens it.

- **HTTPS, or this machine.** The console signs in only over HTTPS, or at
  `http://localhost:8000` on the server's own machine: browsers allow the
  sign-in's cryptography nowhere else, and a password should only cross a
  network encrypted. To use it from other devices, phones included, use the
  [`tls` profile](#https-on-your-own-domain). Over plain HTTP on a network
  address, the server refuses to sign the console in, and says why.
- **One sign-in per tab.** A reload keeps it; closing the tab ends it; a tab
  you duplicate signs in on its own. A console sign-in ends 12 hours after
  the password was entered, however much it is used
  (`SALLI_CONSOLE_SIGN_IN_HOURS`), and after 30 minutes without a key or a
  click, in case the screen is shared.
- **Phones.** The console lays itself out for a phone, with its places in a
  bar at the bottom. Reach it over HTTPS (above).
- **Your display choices** (light, dark or as the system; a locale for
  numbers and dates) are kept in that browser only. Nothing else is kept on
  the device but the tab's own sign-in.
- **Activating tax rules** from the console, making a personal access token
  that can, or saving everything Salli keeps (Settings, Your data), needs the
  password entered in the last five minutes: the console sends you through
  the sign-in page again first.
- **Switching it off:** `SALLI_CONSOLE=false` serves no console, and its
  sign-in refuses everyone. The CLI, MCP and the API are unaffected.

## Configuration

Settings come from the environment. With compose, put them in a `.env` file
next to `compose.yaml` (start from [`.env.example`](../.env.example)) and run
`docker compose up -d` again. Every setting in `.env` reaches the server. None
is needed to start.

### compose.yaml

| Setting | Default | |
|---|---|---|
| `SALLI_PUBLIC_URL` | `http://localhost:8000` | The URL clients reach Salli at. With the `tls` profile, `https://<SALLI_DOMAIN>`. It is also the link in a digest. |
| `SALLI_BIND` | `127.0.0.1` | The interface the port is published on. `0.0.0.0` publishes it to your network: see [Security](#security). |
| `SALLI_PORT` | `8000` | The port on that interface. |
| `SALLI_DOMAIN` | none | The domain Caddy serves with HTTPS (the `tls` profile). |
| `SALLI_IMAGE` | `ghcr.io/leafmonkeylabs/salli:0.5.0` | The image to run: the release this `compose.yaml` names, never `latest`. See [Upgrades](#upgrades). |
| `FORWARDED_ALLOW_IPS` | `10.248.53.2` (Caddy) | Whose `X-Forwarded-For` to believe: only the bundled proxy. See [Security](#security). |

### The server

| Setting | Default | |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | The server's own key. Every AI feature runs on it, unless a person brings their own key or ChatGPT plan. |
| `SALLI_DEFAULT_CURRENCY` | `USD` | The base currency for a new account when none is named (ISO 4217). |
| `ALLOWED_ORIGINS` | none | Web origins whose pages may call the API from a browser, comma-separated. The CLI, scripts and MCP clients need none. |
| `SALLI_SESSION_TTL_DAYS` | `30` | How long a session lasts from sign-in, however much it is used. |
| `SALLI_CONSOLE` | `true` | Whether to serve [the console](#the-console). `false`: no `/console`, and the console's sign-in refuses everyone. |
| `SALLI_CONSOLE_DIR` | `/opt/salli-console` in the image | Where the console's built files are (`index.html` and `assets/`). Without them, no console is served: from a source checkout, build it (`npm run build --workspace @leafmonkeylabs/salli-console`) and point this at `packages/console/dist`. |
| `SALLI_CONSOLE_SIGN_IN_HOURS` | `12` | How long a console sign-in lasts after its password, however often it refreshes (1 to 168). The CLI's sign-ins are not affected. |
| `SALLI_CHATGPT_PLAN_USAGE` | `true` | Whether people may run Salli's AI on their ChatGPT plan. |
| `SALLI_USAGE_COUNTERS` | `false` | Lets the owner see this instance's weekly usage counts with `salli-server stats` (members active, statement entries imported, reconciliations completed). Counts only, read from the database when asked; sent nowhere unless the next two are set ([usage reports](#usage-reports)). |
| `SALLI_EXPERIMENTAL` | `true` | `false` leaves the experimental engines' tools out of what AI agents see over MCP ([scope.md](scope.md#experimental)). |
| `SALLI_USAGE_REPORT_URL` | (none) | Where `salli-server stats --send` and `jobs send-usage` POST the week's totals. Unset, nothing is sent. |
| `SALLI_USAGE_INSTALL_ID` | (none) | The id a report carries: any value you pick (`uuidgen`); change it to rotate. |
| `TAVILY_API_KEY` | none | Web search for the agents. |
| `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | none, `salli` | Tracing. |
| `LOG_LEVEL` | `INFO` | |
| `ENVIRONMENT` | `production` in the image | `development` serves API docs at `/docs` and allows the development sign-in. Never on a server others can reach. |
| `MCP_CONSENT_URL` | Salli's own page | Where people approve an MCP connection, if you run your own web app for it. |
| `MCP_ACCESS_TOKEN_TTL_SECONDS` | `3600` | How long an OAuth access token lasts (the CLI's, an AI client's). |
| `MCP_REFRESH_TOKEN_TTL_SECONDS` | `2592000` | How long a refresh token lasts (30 days). Each refresh issues a new one; a sign-in lasts while it keeps refreshing, except the console's (above) and an AI client's (below). |
| `MCP_GRANT_LIFETIME_DAYS` | `90` | How long an AI client's connection lasts after the person approved it, however often it refreshes (1 to 365); then the person connects it again. Salli's own CLI and app are not affected. |
| `MCP_AUTH_CODE_TTL_SECONDS`, `MCP_ART_TTL_SECONDS` | `120`, `1800` | How long an authorisation code, and a pending approval, last. |
| `SALLI_EXTENSIONS` | none | Extensions to load, comma-separated. They must be installed in the image. |
| `SALLI_USER_ID` | the owner | Whom a `salli-server` command that acts on one user acts as. |

### Set by compose.yaml

You don't set these with compose; they are listed for running Salli another
way.

| Setting | In compose | |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://salli@postgres:5432/salli` | The database. It may leave the password out. |
| `DATABASE_PASSWORD` | from the secrets volume | The database password, when `DATABASE_URL` has none. |
| `SALLI_SECRETS_DIR` | `/var/lib/salli/secrets` | A directory of secrets, one file per setting, named in lower case (`mcp_signing_secret`). A variable of the same name wins over its file. |
| `SALLI_STORAGE_DIR` | `/var/lib/salli/files` | Where uploaded files are kept. Default outside the image: `~/.salli/storage`. |
| `BYOK_ENCRYPTION_KEYS` | generated | Encrypts the AI keys and bank credentials people store, as `version:base64`, comma-separated. The highest version encrypts; every listed one decrypts. |
| `MCP_SIGNING_SECRET` | generated | Signs pending approvals on the consent page. |
| `CRON_SECRET` | generated | Lets a scheduler call `/v1/advisor/cron/run-due`, `/v1/bank-connections/cron/sync-due` and `/v1/notifications/cron/send-due`. |
| `SALLI_INSECURE_DEV_AUTH` | off | Development only: any bearer token is taken as a user id. Honoured only with `ENVIRONMENT=development`. |

To rotate the BYOK key, add a new version to the file in the secrets volume
(`2:<new key>,1:<old key>`) and restart. New secrets are sealed with the new
key; old ones still open with the old.

## HTTPS on your own domain

To reach Salli from other machines, or to connect Claude's apps (which
connect from Anthropic's cloud), give it a domain and HTTPS. Compose includes
[Caddy](https://caddyserver.com), which gets and renews a certificate itself.

1. Point the domain's DNS at this machine, and open ports 80 and 443.
2. In `.env`:

   ```bash
   SALLI_DOMAIN=money.example.org
   SALLI_PUBLIC_URL=https://money.example.org
   ```

3. Start with the `tls` profile:

   ```bash
   docker compose --profile tls up -d
   ```

Sign in with `salli login --server https://money.example.org`. Your AI
client's connector is `https://money.example.org/mcp`
([docs/ai-clients.md](ai-clients.md)).

Salli's own port stays on `127.0.0.1`; only Caddy is reachable from outside.
Pass `--profile tls` to every `docker compose up`, or set
`COMPOSE_PROFILES=tls` in `.env`.

## Scheduled jobs

Three jobs run for every user who wants them: the daily briefing,
syncing connected banks, and the digests (below). Run them from the host's
crontab:

```cron
0 6 * * *   cd /path/to/salli && docker compose exec -T salli salli-server jobs run-advisor
0 */6 * * * cd /path/to/salli && docker compose exec -T salli salli-server jobs sync-banks
0 * * * *   cd /path/to/salli && docker compose exec -T salli salli-server jobs send-digests
```

A scheduler that calls the API instead uses each job's cron route with the
`X-Cron-Secret` header (the `CRON_SECRET` in the secrets volume):
`POST /v1/advisor/cron/run-due`, `/v1/bank-connections/cron/sync-due` and
`/v1/notifications/cron/send-due`.

## Usage reports

Off unless you turn on `SALLI_USAGE_COUNTERS` and set both
`SALLI_USAGE_REPORT_URL` and `SALLI_USAGE_INSTALL_ID`, for a pilot whose
participants have agreed to it. Then `salli-server jobs send-usage`, weekly
from cron (or `salli-server stats --send`), POSTs this JSON and nothing else:

```json
{
  "schema": "salli.usage/1",
  "install_id": "the value you set",
  "salli_version": "0.5.0",
  "week_ending": "2026-10-25",
  "active_members": 3,
  "entries_imported": 120,
  "reconciliations_completed": 2
}
```

The three numbers are counts over the seven days to `week_ending`
([business/metrics.md](../business/metrics.md)): no user id, email, name,
description or amount. `--dry-run` prints the report without sending it.
A minimal receiver is in [examples/usage-collector](../examples/usage-collector/).

## Digests

A person can ask for a digest: weekly or monthly, on the weekday and at the
local hour they choose, saying what is waiting for them in Salli (`salli
notifications set --on --time-zone Europe/Lisbon`; `salli notifications
preview` shows the message). Salli builds every message itself and sends
none: your deployment delivers it, through a **notifier** you plug in as an
extension. Without one, nothing is sent; people's preferences still save,
and the preview still works.

**What a message holds.** Each kind of thing waiting (decisions ready for
review, their own reminders, filing deadlines in the next 14 days, cash
forecast below zero, and, if they ask, transactions to review), how many,
the earliest date (as Salli writes dates on screen: "1 reminder due on
Oct 14, 2026"), and a link to `SALLI_PUBLIC_URL`. Never an amount, a
balance, a name (an account's, a payee's, a reminder's), a decision's
question, a note or anything else from the ledger, and never the person's
email. A message goes through your mail server or push service, so it says
what is waiting, never what it is about. Nothing goes when nothing is
waiting, and no more than one a period.

**Scheduling.** Run `salli-server jobs send-digests` every hour (above), or
call `POST /v1/notifications/cron/send-due` hourly. Each run sends the
digests whose hour it is, in each person's time zone; every other hour is
quiet. Running it twice, or on two servers, sends nothing twice: a period's
digest is claimed in the delivery log before it goes. A send that fails is
tried again at the same hour on a later day of the period, three attempts
in all. `salli-server doctor` names the notifier and warns when the job has
not run in the last day.

**Plugging in a sender.** A notifier is a Python package with an entry point
in `salli.extensions` whose `build` returns an `Extension` with a
`notifier`. It gets each `Notification` (`id`, `user_id`, `period`,
`subject`, `text`, `items`, `link`) and returns a `Delivery`: `SENT`,
`NO_DESTINATION` (it has nowhere to send this person's) or `FAILED`. It
finds where to send by the user id, in its own tables: Salli never stores an
email for sending, a push token or a chat id. A minimal one, which Salli
does not ship:

```python
# my_mailer/extension.py
from salli.application.ports import Delivery, Notification, Notifier
from salli.extensions import Extension, ExtensionContext, ExtensionSpec


class Mailer(Notifier):
    """Sends each digest by email, to an address kept in its own table."""

    def __init__(self, ctx: ExtensionContext) -> None:
        self._ctx = ctx  # its own settings, sessions and secrets

    async def send(self, notification: Notification) -> Delivery:
        address = await self._address_of(notification.user_id)
        if address is None:
            return Delivery.NO_DESTINATION
        try:
            # The id is the same for every attempt in a period: pass it on
            # (a Message-ID, an idempotency key) so a repeat can be dropped.
            await self._smtp(address, notification.subject, notification.text, notification.id)
        except OSError:
            return Delivery.FAILED
        return Delivery.SENT

    async def _address_of(self, user_id: str) -> str | None: ...
    async def _smtp(self, to: str, subject: str, text: str, key: str) -> None: ...


spec = ExtensionSpec(
    name="mailer",
    build=lambda ctx: Extension(name="mailer", notifier=Mailer(ctx)),
    # migrations=...,  # its own Alembic directory, if it keeps tables of its own
)
```

```toml
# my_mailer's pyproject.toml
[project.entry-points."salli.extensions"]
mailer = "my_mailer.extension:spec"
```

Install the package where the server runs (with compose, an image built
`FROM` Salli's that adds it) and set `SALLI_EXTENSIONS=mailer`. One notifier
per deployment: two stop startup. Keep to the privacy rule when you render
the message: restyle it, but add nothing to it. Keep its destinations and
secrets in its own tables and settings, give the extension
`user_data_purgers` and `user_data_exporters` for them, so erasing and
exporting an account reach them, and never log a message's text.

## Backup and restore

A backup is three things: the database, the uploaded files, and the secrets.
Without the secrets, the AI keys and bank credentials people stored can't be
opened again.

**Back up**, from the directory with `compose.yaml`:

```bash
docker compose exec -T postgres pg_dump --username=salli --format=custom salli > salli.dump
docker compose exec -T salli tar -C /var/lib/salli -cf - files secrets > salli-data.tar
```

Both files hold everything in Salli, secrets included. Keep them encrypted, and
somewhere other than this machine.

**Restore** onto a new machine, or after `docker compose down -v`. The
secrets go back first, so the new database is made with the old password:

```bash
docker compose run --rm --no-deps -T secrets tar -C /var/lib/salli -xf - secrets < salli-data.tar
docker compose up -d --wait postgres
docker compose exec -T postgres pg_restore --username=salli --dbname=salli --no-owner < salli.dump
docker compose up -d --wait
docker compose exec -T salli tar -C /var/lib/salli -xf - files < salli-data.tar
```

Everyone's sign-ins come back with the database: nobody needs to sign in again.

## Upgrades

`compose.yaml` names one release of the image. To upgrade, take the newer
`compose.yaml` (or set `SALLI_IMAGE` to the new version), then:

```bash
docker compose pull
docker compose up -d
```

Salli migrates the database when it starts. A migration that has already run
does nothing, and two servers starting at once take turns, so this is safe on
every start. Take a backup before an upgrade: migrations only go forward.

Postgres stays on 17. Moving to a newer major version means a dump and a
restore, as above, onto the new version.

## Security

- **Exposure.** By default Salli listens on `127.0.0.1` only, and Postgres on
  no port at all. To reach Salli from elsewhere, use the `tls` profile rather
  than publishing port 8000: passwords and tokens should only cross a network
  over HTTPS.
- **Secrets.** They are generated into the `secrets` volume, readable only by
  the server's user (the database password also by Postgres). None is written
  to `.env` or printed. `.env` may still hold your Anthropic key: keep it
  readable only by you (`chmod 600 .env`).
- **Passwords** are stored as argon2id hashes (64 MiB, three passes), and
  hashed again with newer parameters when they change. A password needs at
  least 12 characters, and can't be the email.
- **Failed sign-ins** are throttled. After 5 failures for one email in 15
  minutes, or 50 from one address, sign-ins are refused until enough of them
  are 15 minutes old: even the right password is not checked. The count is
  kept for any email, so it says nothing about who has an account. A reset by
  the owner lifts the lock. This holds on the consent and device pages (where
  `salli login` signs in) and for `POST /v1/auth/sessions` alike.
- **Addresses.** The throttle counts by the client's address. Behind Caddy
  that comes from `X-Forwarded-For`, which Salli believes only from Caddy, at
  its fixed address on compose's `proxy` network (`FORWARDED_ALLOW_IPS`).
  Behind a proxy of your own, set that to its address.
- **HTTPS only.** Where `SALLI_PUBLIC_URL` is `https://`, every response
  carries `Strict-Transport-Security` (a year), so a browser never falls back
  to plain HTTP.
- **MCP answers only its own address.** `/mcp` serves a request only when its
  `Host` is `SALLI_PUBLIC_URL`'s (a 421 otherwise), and a browser's only from
  that origin or one `ALLOWED_ORIGINS` names, against DNS rebinding.
- **Production refuses to start** without the Postgres store for
  conversations and reviews (`ENVIRONMENT=production`, as the image is), rather
  than keep them in memory.
- **Sessions and tokens** are opaque random strings, and only their SHA-256
  hashes are stored. Sessions expire after 30 days, and end on sign-out, on a
  password change (the others) and on a reset (all). Nothing uses cookies, so
  there is nothing for another site to forge a request with.
- **Refresh tokens** (the CLI's, the console's, an AI client's) change with
  every use. One used a second time ends the whole sign-in it belongs to:
  whoever copied it and the person both lose it, and the person finds out by
  being signed out. Signing out of any one token ends the sign-in.
- **API responses** say `Cache-Control: no-store`, so no browser or proxy
  keeps a copy of anyone's data.
- **The console and the sign-in pages** run under a strict Content Security
  Policy: no script but the console's own (and none at all on the sign-in
  pages), no third-party request, no framing, and Trusted Types with no
  policy, so a page can't be made to write HTML into itself.
- **Wrong passwords and unknown emails** get the same answer, in about the
  same time.
- **CORS** trusts no web origin unless `ALLOWED_ORIGINS` names it.
- **AI connectors** never hold `tax:activate`, and their tokens are refused by
  the REST API. Only you, at your own terminal or with your own password, can
  make a tax rule set the one Salli computes with: in the console, with the
  password entered in the last five minutes.
- **Updates.** The image is rebuilt for each release; pin a version with
  `SALLI_IMAGE` and upgrade on your own schedule.

Report a vulnerability as [SECURITY.md](../SECURITY.md) says.

## Troubleshooting

**`docker compose up` fails: "port is already allocated".** Something else
uses port 8000. Set `SALLI_PORT=8001` (and `SALLI_PUBLIC_URL` to match) in
`.env`.

**`salli` is unhealthy, or keeps restarting.** `docker compose logs salli`
says why. `docker compose exec salli salli-server doctor` checks the rest.

**"Too many failed sign-ins".** Wait a few minutes (the response's
`Retry-After` gives the seconds), or have the owner reset the password.

**The owner forgot their password.** Anyone who can run commands on the
server can reset it: `docker compose exec salli salli-server members
reset-password you@example.com`.

**Someone lost their authenticator app and their recovery codes.** With
two-step sign-in on (`salli totp enable`), a password alone no longer signs
them in. Reset their password with `--clear-totp`, which turns two-step
sign-in off; they can turn it on again with a new app. The app's secret is
sealed with `BYOK_ENCRYPTION_KEYS`, so two-step sign-in can't be turned on
without one, and losing that key locks out everyone who has it on until the
owner clears it.

**Postgres won't start, or Salli can't sign in to it ("password
authentication failed").** The `secrets` volume was deleted but the `postgres`
volume was not, so the database expects a password the new secrets don't
have. Restore the secrets from a backup; or, with nothing to keep, `docker
compose down -v` and start again.

**`salli login` says the server is unreachable.** Check `SALLI_PUBLIC_URL`
matches the address you use, and that you can open `<url>/healthz` from the
same computer.

**After changing `SALLI_PUBLIC_URL`, sign-ins fail.** OAuth tokens are bound
to the URL they were issued for. Sign in again with `salli login`, and
reconnect AI clients.

**`salli ui` says the server serves no console.** Check `SALLI_CONSOLE` isn't
`false`, and that the image is one with the console (`salli-server doctor`
says). An older server has none.

**The console says it needs HTTPS.** Open it at `http://localhost:8000` on the
server's own machine, or set up [HTTPS](#https-on-your-own-domain) and open it
at `https://<your domain>/console`.

**AI features say no model is available.** Set `ANTHROPIC_API_KEY` in `.env`
and `docker compose up -d`, or add your own key: `salli llm-keys set
anthropic`.
