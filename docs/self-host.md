# Running your own Salli

Salli runs on one machine with Docker: the server and its Postgres database,
started from one compose file. You use it from your own computer with the
`salli` command line, and from your AI client over MCP.

Salli keeps its own accounts. Signing in needs nothing but the database:
there is no outside auth service and no email to configure (decision D13).

- [What you need](#what-you-need)
- [Quickstart](#quickstart)
- [Who can sign in](#who-can-sign-in)
- [Configuration](#configuration)
- [HTTPS on your own domain](#https-on-your-own-domain)
- [Scheduled jobs](#scheduled-jobs)
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
| See who can sign in | `docker compose exec salli salli-server members list` |
| Set a forgotten password | `docker compose exec salli salli-server members reset-password partner@example.com` |
| …and sign them out everywhere | add `--sign-out-everywhere` |

Each member has their own ledger and signs in with `salli login`. Salli sends
no email, so a forgotten password is reset by the owner, never by a link.

People change their own password with `salli password`. That signs out their
other sessions; their CLI sign-ins and personal access tokens keep working.

A reset signs out every session, and lifts any lock from failed sign-ins.
`--sign-out-everywhere` also revokes the person's CLI sign-ins, AI connectors
and personal access tokens: use it when you think an account was taken over.

How each way in works:

| Way in | How | May activate tax rules |
|---|---|---|
| The `salli` CLI | `salli login`: the browser or device page, with your password | yes |
| A session | `POST /v1/auth/sessions` with your email and password, for an app or a script | yes |
| A personal access token | `salli tokens create`, for scripts and CI | only if made with `--allow tax:activate` |
| An AI client over MCP | approved on Salli's consent page with your password | never |

## Configuration

Settings come from the environment. With compose, put them in a `.env` file
next to `compose.yaml` (start from [`.env.example`](../.env.example)) and run
`docker compose up -d` again. Every setting in `.env` reaches the server. None
is needed to start.

### compose.yaml

| Setting | Default | |
|---|---|---|
| `SALLI_PUBLIC_URL` | `http://localhost:8000` | The URL clients reach Salli at. With the `tls` profile, `https://<SALLI_DOMAIN>`. |
| `SALLI_BIND` | `127.0.0.1` | The interface the port is published on. `0.0.0.0` publishes it to your network: see [Security](#security). |
| `SALLI_PORT` | `8000` | The port on that interface. |
| `SALLI_DOMAIN` | none | The domain Caddy serves with HTTPS (the `tls` profile). |
| `SALLI_IMAGE` | `ghcr.io/leafmonkeylabs/salli:latest` | The image to run. Pin a version (`…/salli:0.1.0`) to upgrade only when you choose. |
| `FORWARDED_ALLOW_IPS` | `*` | Whose `X-Forwarded-For` to believe. See [Security](#security). |

### The server

| Setting | Default | |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | The server's own key. Every AI feature runs on it, unless a person brings their own key or ChatGPT plan. |
| `SALLI_DEFAULT_CURRENCY` | `USD` | The base currency for a new account when none is named (ISO 4217). |
| `ALLOWED_ORIGINS` | none | Web origins whose pages may call the API from a browser, comma-separated. The CLI, scripts and MCP clients need none. |
| `SALLI_SESSION_TTL_DAYS` | `30` | How long a session lasts from sign-in, however much it is used. |
| `SALLI_CHATGPT_PLAN_USAGE` | `true` | Whether people may run Salli's AI on their ChatGPT plan. |
| `TAVILY_API_KEY` | none | Web search for the agents. |
| `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | none, `salli` | Tracing. |
| `LOG_LEVEL` | `INFO` | |
| `ENVIRONMENT` | `production` in the image | `development` serves API docs at `/docs` and allows the development sign-in. Never on a server others can reach. |
| `MCP_CONSENT_URL` | Salli's own page | Where people approve an MCP connection, if you run your own web app for it. |
| `MCP_ACCESS_TOKEN_TTL_SECONDS` | `3600` | How long an OAuth access token lasts (the CLI's, an AI client's). |
| `MCP_REFRESH_TOKEN_TTL_SECONDS` | `2592000` | How long a refresh token lasts (30 days). |
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
| `CRON_SECRET` | generated | Lets a scheduler call `/v1/advisor/cron/run-due` and `/v1/bank-connections/cron/sync-due`. |
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

Two jobs run for every user who wants them: the daily advisor report, and
syncing connected banks. Run them from the host's crontab:

```cron
0 6 * * *   cd /path/to/salli && docker compose exec -T salli salli-server jobs run-advisor
0 */6 * * * cd /path/to/salli && docker compose exec -T salli salli-server jobs sync-banks
```

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
  that comes from `X-Forwarded-For`, which Salli believes from anything that
  reaches its port (`FORWARDED_ALLOW_IPS=*`): by default, only this machine
  and Caddy. If you publish port 8000 beyond this machine without a proxy, set
  `FORWARDED_ALLOW_IPS=127.0.0.1`.
- **Sessions and tokens** are opaque random strings, and only their SHA-256
  hashes are stored. Sessions expire after 30 days, and end on sign-out, on a
  password change (the others) and on a reset (all). Nothing uses cookies, so
  there is nothing for another site to forge a request with.
- **Wrong passwords and unknown emails** get the same answer, in about the
  same time.
- **CORS** trusts no web origin unless `ALLOWED_ORIGINS` names it.
- **AI connectors** never hold `tax:activate`, and their tokens are refused by
  the REST API. Only you, at your own terminal or with your own password, can
  make a tax rule set the one Salli computes with.
- **Updates.** The image is rebuilt for each release; pin a version with
  `SALLI_IMAGE` and upgrade on your own schedule.

Report a vulnerability as [SECURITY.md](../SECURITY.md) says.

## Troubleshooting

**`docker compose up` fails: "port is already allocated".** Something else
uses port 8000. Set `SALLI_PORT=8001` (and `SALLI_PUBLIC_URL` to match) in
`.env`.

**`salli` is unhealthy, or keeps restarting.** `docker compose logs salli`
says why. `docker compose exec salli salli-server doctor` checks the rest.

**"Too many failed sign-ins".** Wait for the time it gives, or have the owner
reset the password.

**The owner forgot their password.** Anyone who can run commands on the
server can reset it: `docker compose exec salli salli-server members
reset-password you@example.com`.

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

**AI features say no model is available.** Set `ANTHROPIC_API_KEY` in `.env`
and `docker compose up -d`, or add your own key: `salli llm-keys set
anthropic`.
