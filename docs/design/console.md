# The Salli console: your books in a browser

Status: **approved (2026-10-12); v1 complete.** C0, the server
groundwork, C1, the console's foundations and Home, C2, where you stand,
C3, the decision lab, C4, books, tax and settings, and C5, the console's
look from the approved mockup, are built. The owner accepted every
recommended decision below. Each sub-phase is its own PR; C6 and the later
pages (C7) come later. What C0 to C5 built, and where they depart from the
text above, is in [As built (C0)](#as-built-c0),
[As built (C1)](#as-built-c1), [As built (C3)](#as-built-c3),
[As built (C2)](#as-built-c2), [As built (C4)](#as-built-c4) and
[As built (C5)](#as-built-c5).

## Why

Salli has a server, an API, a command line and an MCP server. To see where you
stand, you run `salli status`; to weigh a decision, you ask your AI or run
`salli decide`. That suits people who live in a terminal. It doesn't suit a
partner who wants to look at the household's cash forecast, or anyone who
wants to see a scenario's twenty years as a picture rather than a table.

Most self-hosted software ships a page in the browser for this. The owner's
direction:

> Ship `salli ui`, which opens a console in the browser where we can view
> things visually. For self-hosters this is enough. Firms get more (SSO and
> the like), and that is closed source.

So the console is:
- **open source**, for one self-hosted household: the owner and the members
  they add;
- **a client of the API**, like the CLI: it computes nothing, and it adds no
  feature the CLI lacks;
- **extensible**, so a closed edition can add firm-shaped pages and sign-in
  methods without core knowing about firms.

The rules it keeps are Salli's own:

- **Salli computes.** Every figure on screen is the server's, shown exactly.
  The console never does arithmetic on money, not even exact arithmetic.
- **Nothing ranks.** Options are shown side by side, never ordered as better
  or worse.
- **Only a person activates tax rules.** A console sign-in is a person's, and
  activation still needs that person's password, just entered.
- **Calm.** The brand's components, numbers and motion
  ([docs/brand/README.md](../brand/README.md)), with no count-ups, streaks or
  urgency.

## Who it's for

| Who | What they do in it | Edition |
|---|---|---|
| **A self-hoster** | Everything in v1: where they stand, the decision lab, imports, tax rules, settings. | Open |
| **A household member** | The same, on their own ledger. Each member has their own books ([docs/self-host.md](../self-host.md#who-can-sign-in)); there is no shared view. | Open |
| **An adviser in a paid pilot** | Watches the decision lab and the cockpit on a pilot instance: the demo. | Open, on a pilot instance |
| **A firm, later** | Organisations, adviser seats, client consent, SSO, audit export, white-labelling. | Closed, in `leafmonkeylabs/salli` |

The console is the demo vehicle for paid pilots: "import client records, see
the reconciled ledger, net worth, cash flow, investments and tax" and "weigh a
decision with Salli's figures" are both pages in v1.

## What the code says today

This survey of `main` (21f91c1) fixes what the console builds on, and what
constrains it.

**The API and its clients**

- **Everything goes through the API.** 229 operations in
  `openapi/openapi.json`, and every one has a `salli` command or a reason in
  `EXEMPT` (`packages/cli/test/api-coverage.test.ts`).
- **The SDK is generated** from that document (`packages/sdk/src/generated`)
  and wrapped by `createClient` (`packages/sdk/src/client.ts`): a bearer token
  from a `TokenProvider`, one refresh-and-retry on 401, errors as
  `SalliApiError` with RFC 9457 problem details. It has no Node-only imports,
  so it runs in a browser.
- **Money is a decimal string.** Responses carry amounts as strings; the SDK's
  `formatAmount` (`packages/sdk/src/money.ts`) formats them through
  `Intl.NumberFormat`'s decimal-string support, never a float, at the
  currency's own precision. `eslint.config.js` refuses `Number()`,
  `parseFloat`, `parseInt` and unary `+` across `packages/**`, with a
  "not money: <why>" escape.
- **Three gaps in the money path:**
  - six request fields accept a JSON number as well as a string
    (`AllocationRequest.allocated_amount`, `GoalRequest.target_amount`,
    `GoalUpdateRequest.target_amount`, `IncomeItem.amount`,
    `OpeningBalanceItem.amount`, `OnboardingRequest.goal_target_amount`, each
    `anyOf [number, string]`);
  - one response field is money as a JSON number:
    `FireStrategy.target_monthly_expenses`;
  - `normalizeAmountInput` reads `.` as the decimal point and `,` as grouping
    only, so `1.234,56` typed in a comma-decimal locale is refused.
- **`salli status`** reads six operations (`packages/cli/src/commands/status.ts`):
  `reports.balanceSheet`, `ledger.incomeStatement`, `fi.score.get`,
  `reminders.list`, `insights.safeToSpend` and `insights.signals`.

**Signing in**

- **Salli keeps its own accounts** (`application/services/login_service.py`):
  argon2id, throttled failures, opaque tokens stored as SHA-256 hashes.
- **`deps.get_principal`** accepts, in order: a personal access token
  (`salli_pat_`), a session (`salli_st_`), an OAuth token issued for the API
  resource, an extension's `IdentityProvider`, then the development fallback.
- **The CLI signs in as a first-party OAuth client,** `salli-cli`, seeded by
  `core_0011_first_party_clients` as a public client whose only redirect is
  `http://127.0.0.1/callback`; `_redirect_matches` accepts any port on a
  loopback host (RFC 8252). Clients that register themselves (RFC 7591) are
  never first party.
- **`tax:activate` follows from how you signed in**
  (`application/permissions.py`): yes for a session, the development sign-in
  and a first-party OAuth client; a personal access token only if made with
  it; never an MCP token. `require_permission(TAX_ACTIVATE)` guards
  `tax.ruleSets.versions.activate`, and the service checks again.
- **Refresh tokens rotate but don't detect reuse.**
  `McpOAuthService.exchange_refresh_token` revokes the used token and issues a
  new pair; a rotated token presented again is simply "invalid or expired",
  and the grant lives on. Each new refresh token runs
  `MCP_REFRESH_TOKEN_TTL_SECONDS` (30 days) from its own issue, so a grant has
  no absolute lifetime.
- **There is no grant id.** `revoke_token_by_value` revokes one token;
  `revoke_client_grant(user_id, client_id, resource)` revokes every grant a
  client has for that user, on every device.
- **Only sessions and MCP connections are listed.** `auth.sessions.list`
  lists `salli_st_` sessions; `mcp.connections.list` lists MCP grants only
  (`list_connections` filters to the MCP audience). The CLI's own sign-ins,
  OAuth grants for the API, appear in neither.
- **The consent and device pages** (`routers/mcp_consent_page.py`) are
  server-rendered with no script and no session: each decision carries the
  email and password. Their CSP is `default-src 'none'; style-src
  'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'`, with
  `X-Frame-Options: DENY`. Their colours (`#2E7D6B`, `#fafaf7`) aren't the
  brand's.
- **No cookie is set anywhere.** `routers/auth.py` says so, and
  [docs/self-host.md](../self-host.md#security) promises it: "Nothing uses
  cookies, so there is nothing for another site to forge a request with."
- **Members have no API.** The owner adds and resets members with
  `salli-server members` (`interfaces/cli`). `logins.is_owner` marks the
  owner, but no route exposes it.

**Serving**

- **CORS** trusts only `ALLOWED_ORIGINS`, none by default, with
  `allow_credentials=True` (`interfaces/api/main.py`).
- **The MCP app is mounted at `/`, last,** in the app's lifespan, so it
  catches any path no route matched. A console mounted in `create_app` comes
  before it.
- **Compose publishes the port on `127.0.0.1`** (`SALLI_BIND`); other machines
  reach Salli through the `tls` profile's Caddy.
- **The image is Python only.** The `Dockerfile` has a uv build stage and a
  slim run stage; `.github/workflows/image.yml` builds both platforms and runs
  compose end to end (up, set up an owner, sign in, health) on every pull
  request that touches it.
- **`GET /v1/meta`** is public and names the server version, the API version,
  the enabled extensions and the OAuth endpoints (`routers/meta.py`).

**Extending**

- **`ExtensionSpec`** (`src/salli/extensions.py`) adds API routers,
  `salli-server` command groups and its own migrations; `build` returns an
  `Extension` with at most one usage meter, entitlement policy, ChatGPT plan
  policy, identity provider and notifier.
- **`IdentityProvider.verify(token)`** returns an `ExternalIdentity(user_id,
  email)` for a bearer token that is none of Salli's own. The principal it
  makes signs in as `session`, so it holds `tax:activate`.
- **`test_no_commercial_vocabulary.py`** scans `src/salli` only, not
  `packages/`.

**Findings outside the console's scope, but in its way**

- `routers/mcp_oauth.py` says "MCP is available on every tier, Free
  included": plan vocabulary the guard's patterns miss.
- `domain/agents/tools.py` speaks of "tenant isolation", and
  `routers/agent.py` describes its personas as "Pro Mode" and "the mobile
  app's Buddy Mode", from the retired hosted product.
- `FireStrategy.target_monthly_expenses` is money as a JSON number (above).

The console's first sub-phase rewords the first two and fixes the third.

## 1. Where it lives, and how `salli ui` works

### The options

- **(a) Served by the server.** The console is static files built into the
  image and served at `{SALLI_PUBLIC_URL}/console`. `salli ui` opens that URL.
- **(b) Bundled in the CLI.** The npm package carries the console. `salli ui`
  starts a server on `127.0.0.1` that serves it and forwards API calls with the
  CLI's stored token, then opens the browser there.
- **(c) A separate package or image.** A `salli-console` container (or static
  files) run beside the server, behind the same proxy.

| | (a) Served by the server | (b) In the CLI | (c) Separate |
|---|---|---|---|
| **A remote server** | The server's URL, from any browser that reaches it. | Works: the local proxy forwards to it. | Needs a proxy rule putting it on the server's origin, or CORS. |
| **Phones and tablets** | Yes, over the `tls` profile. | No: nothing runs on the phone. | Yes, if proxied. |
| **Household members** | Open a URL; no install. | Each needs Node.js 22 and the CLI. | Open a URL. |
| **Upgrades** | Comes with the image: one upgrade. | Comes with the CLI, on the CLI's schedule. | A second thing to upgrade. |
| **Version skew** | None: built and shipped with the server it talks to. | A CLI release meets servers of any version. | Two versions to keep in step. |
| **Attack surface** | Static files and one more first-party client, on the origin the API already has. | A local proxy holding a token that may activate tax rules: any local process or web page can reach a loopback port, so it needs a per-launch secret, Host checks against DNS rebinding and Origin checks. | Another service to harden and patch. |
| **Tokens in the browser** | Yes, in memory (section 2). | No: the proxy keeps them. | Yes. |
| **Offline** | Works wherever the server is reachable, internet or not: it makes no third-party request. | The same. | The same. |
| **Closed pages** | The closed image serves its own build. | A closed CLI build. | A closed console image. |
| **Cost** | A Node build stage; the final image gains only the built files. | The CLI package grows by the console; a long-running process in a CLI. | A second image, its CI and release. |

### Recommendation: (a), served by the server

It is the only option that reaches phones and household members without an
install, it removes version skew entirely, and it puts the console on the
origin the API already has, so CORS stays at "nothing by default". (b)'s one
real advantage, that tokens never reach the browser, costs a local proxy that
is harder to secure than the browser storage it avoids, and it rules out
every device that can't run the CLI.

### How `salli ui` works

```
$ salli ui
Opening https://money.example.org/console
```

1. Read the current context's server (`salli login` stored it), or
   `--server`, as every command does.
2. `GET /v1/meta`. Its new `console_url` field is the console's address, or
   null when the server has none (an older server, or `SALLI_CONSOLE=false`):
   then say so, and how to get one.
3. Open the browser at `console_url` with the CLI's own launcher
   (`packages/cli/src/auth/browser.ts`), and print the URL. `--no-open`
   prints it only: for SSH, or to type it into a phone.

The CLI hands the browser nothing: no token in a URL, no shared session. The
browser signs in itself, on the server's sign-in page (section 2). With a
password manager that is one step.

### Serving it

- **Path:** `/console`, and everything under it. Deep links
  (`/console/decisions/…`) return the console's `index.html`; hashed assets
  under `/console/assets/` are served as files. Plain `StaticFiles` won't do
  the first, so it is a small route of its own, mounted in `create_app`, which
  is before the MCP app's catch-all at `/`.
- **Settings:** `SALLI_CONSOLE` (default `true`) switches it off: no route, and
  the console's OAuth client refuses to authorise. `SALLI_CONSOLE_DIR` is where
  the built files are; the image sets it. A source checkout without a built
  console serves none, and `salli-server doctor` says so. Both go in the
  settings table in [docs/self-host.md](../self-host.md#configuration).
- **Caching:** `index.html` with `Cache-Control: no-cache`; hashed assets
  `public, max-age=31536000, immutable`, served precompressed (brotli and
  gzip files from the build) when the browser accepts them.
- **API responses** gain `Cache-Control: no-store`, so no browser or proxy
  keeps a page of someone's ledger.
- **A secure context is required.** PKCE's S256 needs `crypto.subtle`
  (`packages/sdk/src/oauth.ts`), which browsers offer only over HTTPS or on
  `localhost`. So the console works at `http://localhost:8000/console` on the
  server's own machine, and over the `tls` profile from anywhere else. Over
  plain HTTP on a LAN address it refuses to start and says why. That matches
  the security advice already given: passwords should only cross a network
  over HTTPS.
- **One origin.** The console checks that it was opened at
  `SALLI_PUBLIC_URL`'s origin (from `/v1/meta`) and, if not, moves there
  before signing in, since OAuth tokens are bound to that URL.
- **Development:** the console's Vite server proxies `/v1`, `/mcp/oauth` and
  `/.well-known` to a local server started with `SALLI_PUBLIC_URL` set to
  Vite's address, so development is same-origin too.

## 2. Signing in, and keeping it safe in a browser

### What has to hold

1. **Nothing other sites can ride on.** Today no cookie is set; a request is
   only as good as the bearer token it carries.
2. **CORS stays at nothing by default.** `ALLOWED_ORIGINS` stays empty.
3. **A person is a person.** A console sign-in is the person's own, like the
   CLI's, so it may do what only they may.
4. **An agent can't activate tax rules.** That includes an AI agent driving
   a browser in which the console is open.
5. **Signing out ends it,** and the person can see and end every sign-in.

### The options

| | (A) OAuth code + PKCE, first-party `salli-console` | (B) A cookie session | (C) A `salli_st_` session |
|---|---|---|---|
| **How** | The console redirects to `/mcp/oauth/authorize`; the person signs in on Salli's own page; the console exchanges the code for tokens. | The server sets an `HttpOnly`, `Secure`, `SameSite=Strict` cookie after sign-in (a backend for the frontend). | The console posts the email and password to `POST /v1/auth/sessions` and keeps the token. |
| **Where the password is typed** | Only on Salli's server-rendered page, never in the console's script. | Depends: a console form, or the server page. | In the console's script. |
| **Token theft by injected script** | It can read in-memory tokens. Mitigated by short access tokens, rotating refresh tokens with reuse detection, an absolute lifetime and the CSP. | Can't read the cookie, but can send requests while the page is open. | Can read a 30-day token that doesn't rotate. |
| **Cross-site requests** | None possible: no cookie. | The cookie needs CSRF defences on every route (SameSite, an Origin check, a custom header), and the promise "nothing uses cookies" ends. | None possible. |
| **`tax:activate`** | Yes, as a first-party client; step-up below. | Yes. | Yes (sessions are first-party). |
| **Sign-in methods a closed edition adds (SSO)** | Fit the existing sign-in page (section 7). | Need their own cookie path. | Don't fit: a session needs a password. |
| **New server work** | A seeded client, a computed redirect, grant ids, reuse detection, an absolute lifetime. | A server-side session store, CSRF middleware, cookie scoping. | Almost none. |

### Recommendation: (A), with the tokens in the tab

(A) keeps every property Salli has today: no cookie, no CORS, the password
typed only on the server's own page, and the same OAuth the CLI uses. (B)
hides tokens from script but gives up the "no cookie" promise and brings CSRF
back to every route. (C) is simplest, and the weakest: a password form in the
console's own script, and a 30-day token that never rotates.

How (A) works:

- **The client.** `salli-console`, seeded as first party by a migration like
  `core_0011`. Its one redirect is `{SALLI_PUBLIC_URL}/console/callback`,
  computed from the setting rather than stored, since every deployment's URL
  differs, and matched exactly (no loopback rule). `/v1/meta` advertises it as
  `oauth.console_client_id`.
- **The flow.** Authorisation code with PKCE (S256) from the SDK's `oauth`
  module, as the CLI's sign-in uses, with `resource` the API's (`{base}/v1`);
  `state` and the verifier wait in `sessionStorage` across the redirect.
- **The sign-in page.** The existing consent page, which already reads "…is
  asking to sign in to your Salli account as you" for an API client. For the
  console it reads plainly as **Sign in to Salli**, with one button. The
  console has no sign-in form of its own.
- **The access token** stays in memory (`MCP_ACCESS_TOKEN_TTL_SECONDS`, an
  hour by default), handed to the SDK through a `TokenProvider`.
- **The refresh token** stays in memory and in the tab's `sessionStorage`,
  so a reload keeps the sign-in and closing the tab ends it. Each tab is its
  own sign-in. A tab opened with "duplicate" inherits a copy; on start it asks
  over a `BroadcastChannel` whether another tab holds that grant, and if so
  drops its copy and signs in afresh, so two tabs never rotate one token.
- **Rotation, with reuse detection.** Tokens carry a grant id through
  rotation. A rotated refresh token presented again revokes its whole grant:
  a thief and the person can't both keep going, and the person finds out by
  being signed out. This applies to every client, the CLI's included.
- **An absolute lifetime.** A console grant ends `SALLI_CONSOLE_SIGN_IN_HOURS`
  (default 12) after its sign-in, however often it refreshes. The CLI keeps
  its present behaviour.
- **Idle.** After 30 minutes without a key or a click, the console signs out
  and says so. It doesn't stop a thief; it protects a shared screen.

### `tax:activate`: a person, just now

A console sign-in is first party, so it holds `tax:activate`: a person signed
in to the console is a person. But a browser is a place agents now work, and
a page that renders rule sets an agent drafted from the open web is where
injected script would aim. The CLI's protection, a terminal an agent can't
fake, has no browser equivalent.

So the console's sign-in holds `tax:activate` **only within five minutes of
its password check**:

- tokens record `authenticated_at`, when the password (or a closed edition's
  sign-in method) was checked, carried through rotation;
- a first-party client may set how recent a sign-in its powerful permissions
  need: 300 seconds for `salli-console`, none for `salli-cli`;
- `permissions_for` takes the sign-in's age, so the rule lives where every
  other permission rule lives, and `require_permission`'s 403 says to sign in
  again.

In the console, **Activate** first shows what the CLI shows (the diff, the
source behind each changed figure, every worked example's result), then sends
the person through the sign-in page again, keeping their place, and activates
on return. The same applies to **making a personal access token with
`tax:activate`**, which `may_grant` already limits to permissions the sign-in
holds: otherwise a script could mint itself a token that activates.

An agent driving the browser would need the person's password typed on
Salli's own page. That is the same bar as the consent page sets for MCP.

### Injected script, and the CSP

Injected script is the console's main risk. The console shows text an agent
or a bank wrote: payees, rule-set labels and sources, decision notes. So:

- **React's escaping only.** No `dangerouslySetInnerHTML`, no `innerHTML`, no
  Markdown rendered to HTML, no `eval` or `new Function`: lint rules refuse
  them, with no escape hatch.
- **Links** to sources a rule set cites open with `rel="noopener noreferrer"`,
  and only `https:` URLs become links; anything else shows as text.
- **Headers on every `/console` response:**

  ```
  Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self';
    img-src 'self'; font-src 'self'; connect-src 'self'; manifest-src 'self';
    base-uri 'none'; form-action 'self'; frame-ancestors 'none';
    require-trusted-types-for 'script'; trusted-types 'none'
  Cross-Origin-Opener-Policy: same-origin
  Cross-Origin-Resource-Policy: same-origin
  Referrer-Policy: no-referrer
  X-Content-Type-Options: nosniff
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
  ```

  No inline script, no third-party origin and no framing. Where the browser
  supports Trusted Types, having no policy means a sink like `innerHTML`
  throws even if a dependency tries one. C1 checks the libraries chosen against this policy; one that needs
  `'unsafe-inline'` is replaced, not accommodated.
- **The sign-in page** keeps its own stricter policy and `frame-ancestors
  'none'`, so the console can't frame it either.

### CORS

Unchanged. The console is on the API's origin, so it needs no CORS at all,
and `ALLOWED_ORIGINS` stays empty by default. The token endpoint is a
same-origin form post. A self-hoster who builds their own app on another
origin still names it in `ALLOWED_ORIGINS`, as today.

### Signing out, and the list of sign-ins

- **Sign out** revokes the tab's grant (`POST /mcp/oauth/revoke`, which with
  grant ids revokes the grant, not one token) and clears the tab.
- **Sign-ins** in Settings lists every way in: sessions, the CLI on each
  machine, the console in each tab, with when each began and was last used,
  and which is this one. Each can be ended. Today's lists can't show this
  (above), so this needs `GET /v1/auth/sign-ins` and `DELETE
  /v1/auth/sign-ins/{id}`, replacing `auth.sessions.list` and
  `auth.sessions.revoke` outright, as phase 3 replaced what it changed; and
  `salli sign-ins list` and `revoke` move to them, keeping the CLI-first rule.
- **AI connections** stay their own list (`mcp.connections.list`,
  `mcp.connections.revoke`), as in the CLI.

### The consent and device pages

They stay what they are: server-rendered, script-free, password with every
decision, usable when the console is switched off. Two changes:

- **The brand.** They take the brand's colours, type (system fonts, as now,
  so the page has no font request) and voice. Their inline styles stay
  inline, under their own CSP.
- **Sign-in methods.** A closed edition can add a button to them (section 7).

The console doesn't reimplement either page; the device page stays for the
CLI's `salli login --device`.

## 3. Licence

| | AGPL-3.0-only, like the server | Apache-2.0, like the CLI and SDK |
|---|---|---|
| **For self-hosters** | No difference: they run it as shipped. | No difference. |
| **For someone who modifies it and serves it** | Must offer their changes' source to their users, as for the server. | May keep their changes closed. |
| **For a firm or OEM that wants a branded console** | Takes a commercial licence, or publishes its changes. White-labelling stays a closed feature. | May rebrand and extend it freely; white-labelling is given away. |
| **For an OEM building its own UI** | Uses the Apache SDK, as today; the console is only a reference. | The same. |
| **For the closed edition** | Leaf Monkey Labs holds the rights through the CLA ([CLA.md](../../CLA.md)), so its own closed build is not bound by the AGPL. Third parties' extensions are. | No difference. |
| **Consistency** | The console is part of the product and ships in the AGPL image. | Matches the npm packages beside it. |

**Recommendation: AGPL-3.0-only.** The console is part of the product the
server serves, not a library others embed: the SDK already is that, under
Apache-2.0. The AGPL keeps a branded, extended console as something firms
license, which is the dual-licence model the commercial plan relies on,
while every self-hoster gets the whole console. `packages/console` carries
its own `LICENSE` and `NOTICE` (Geist and Geist Mono are OFL), and the README's
licence section and badges name it.

## 4. How it's built

### The stack

| | React + Vite | Preact + Vite | Astro islands |
|---|---|---|---|
| **Fit** | An app behind a sign-in, every page data from the API at run time. | The same, with a runtime of a few kilobytes rather than tens. | Made for content sites; pre-rendering buys nothing when every page is a person's data. |
| **Accessible widgets** | React Aria (Adobe, Apache-2.0): combobox, dialog, date field, table, built to WAI-ARIA practice. | React Aria through `preact/compat`, not supported by its makers. | Islands would each pull in a framework anyway. |
| **The closed edition** | Imports the open console as a package (section 7). | The same. | Composition across islands is awkward. |
| **Contributors** | The most familiar. | Close to React. | Familiar from the site. |

**Recommendation: React and Vite, in TypeScript, as `packages/console`** in
the existing npm workspace, with:
- React Aria Components for the widgets that are hard to make accessible;
- a small typed router (TanStack Router), so filters and as-of dates live in
  the URL and a page can be shared or reloaded;
- TanStack Query for fetching and for refreshing what a write changed;
- nothing else at run time without a reason written in the PR.

If the bundle budget (below) is missed, Preact is the fallback.

### Data: the SDK only

Every call goes through `@leafmonkeylabs/salli-sdk`'s `createClient` and its
generated functions. The console calls no URL by hand and defines no response
type of its own: when the API changes, `npm run check:generated` and the
console's type check fail together. The SDK gains a browser `TokenProvider`
(memory, `sessionStorage`, refresh under a Web Lock) beside the CLI's.

### Money: never a float

The CLI's rule, extended to the browser:

- **Amounts stay decimal strings** from the response to the screen, formatted
  by `formatAmount`. The console does no arithmetic on money: no totals, no
  differences, no conversions. A figure the console wants, the server
  computes. That is why v1's entry form takes one amount moving between two
  accounts (section 5): a split entry would want a running difference.
- **Input** goes through `normalizeAmountInput`, extended to read the
  locale's decimal and grouping marks (`1.234,56` in a comma-decimal locale),
  by rewriting the text, never parsing it into a number.
- **Requests send strings.** The six fields that accept a number are narrowed
  to strings in the API, so the generated types refuse a number.
- **The lint rules apply** to `packages/console` as they do to the CLI,
  under the browser's globals.
- **One exception, for drawing.** A chart has to place a point. One module,
  `chart/geometry.ts`, may turn a decimal string into a number, only to
  compute a pixel position; what it returns is never shown, sent or compared.
  Every label on a chart is `formatAmount` of the original string. The lint
  escape there reads `-- not money: pixel geometry`, and a test fails if the
  escape appears in any other file.

### Charts

Hand-drawn SVG components, not a chart library. The website already draws
its diagrams this way, from the same tokens (`site/src/components/diagrams`
and `site/src/lib/svg.ts` in `leafmonkeylabs/salli`), and the console needs
only a few shapes:

| Chart | Where | Shape |
|---|---|---|
| **Daily cash** | Cash; a scenario's first year | A step line with the low point labelled, a shortfall shaded oxblood at 12% |
| **The monthly timeline** | Decision lab; FI | Lines in today's money, the baseline and each option, labelled at their ends |
| **Net worth by role** | Home; ledger | Stacked bars: cash, investments, other assets, debts below the line |
| **Cash flow** | Cash | Paired monthly bars, income and spending, net as a figure |
| **Sensitivity** | Compare | Each option's figure at the conservative, base and growth returns |
| **Break-evens** | Compare; rent or buy | A line with the value where the answer turns, marked and labelled |

Rules, from the brand and from WCAG:
- 1.5 px lines; hairline gridlines; figures labelled on the chart; no 3D, no
  pie charts, no animation into place (a line is exact from its first frame).
- **Each chart is a `<figure>`** with a caption saying what it shows and its
  key figure ("Lowest: USD 120.00 on Nov 2, 2026"), an SVG with
  `role="img"`, and **Show the figures**, which shows the same data as a table:
  the table is the accessible way in.
- **Contrast.** The brand puts comparisons in brass or sand, but brass is
  2.4:1 on paper (the brand's own table), below WCAG's 3:1 for graphics that
  carry meaning. The console draws the baseline in ink, options in ledger
  green and graphite, told apart by dash pattern and end labels as well as
  colour; brass and sand only decorate. On night, sand-on-dark and
  muted-on-dark take their places. Decision 11 asks the owner to accept this
  departure, and the brand README would record it.
- **Phones** get their own layouts: fewer ticks, labels below the plot,
  options stacked rather than overlaid.

### Accessibility

WCAG 2.2 AA, checked at 360, 768 and 1280 px, light and dark.

- **Keyboard:** every action reachable, with a visible focus ring; a skip
  link; dialogs that trap and return focus; no keyboard traps. The brand's
  forms call for a 2 px brass focus ring, but brass is 2.4:1 on paper, below
  the 3:1 a focus indicator needs. The ring is ledger green on light and
  sand-on-dark on dark, as the website's tokens already have it
  (`--c-focus`); decision 11 covers this with the chart colours.
- **Screen readers:** landmarks, one `h1` per page, tables with headers,
  live regions for "Saved" and errors, never colour alone.
- **Money read out properly.** `(370.00)` in oxblood reads as "370.00" to a
  screen reader, losing its sign. Each `<Money>` has a visually hidden
  reading, "minus 370.00 US dollars": the currency as a word, from
  `formatAmount`'s `display: 'name'`, and the sign as a word rather than a
  hyphen some screen readers skip.
- **Motion:** fades and short slides of 120–200 ms, easing out, and none
  with `prefers-reduced-motion`.
- **Targets** at least 24 by 24 px (WCAG 2.2's 2.5.8), 40 px buttons as the
  brand sets.

### Themes and layout

- **Light and dark** from the brand's tokens, following the system, with a
  light, dark or system choice kept on the device.
- **Tokens in one file,** `packages/console/src/styles/tokens.css`, the code
  copy of the brand README's tables, mirrored by the site. The brand README's
  "change the tokens together" note gains this file.
- **The brand's components:** 12 columns, bone panels with hairline borders,
  sticky table headers, figures right-aligned in tabular figures, totals with
  a hairline above and a double rule below, section labels after a small
  outlined square.
- **Phones:** a bottom bar with five places (Home, Cash, Decide, Books,
  More); tables become lists of rows that keep their figures right-aligned.

### Numbers, dates and language

- **Amounts** as the CLI shows them: the currency code, the currency's own
  precision, never rounded unless it says so; in tables the code in the
  column header.
- **Locale** for separators and dates: the browser's, with an override kept
  on the device. The server has no locale setting, and none is needed.
- **Dates** as the CLI's `displayDate` shows them (`Nov 1, 2026` in English),
  ISO in anything copied or exported.
- **Provenance** beside every figure that has one: *as of*, *placeholder
  assumptions*, *computed by XA 2026, version 1*.
- **Language:** British English only in v1, with every string in one
  catalogue so a translation can follow.

### Budget, and nothing from elsewhere

- **JavaScript:** at most 150 kB compressed for the shell and Home; at most
  75 kB for each later page's chunk; at most 500 kB in all.
- **CSS:** at most 40 kB compressed.
- **Fonts:** Geist and Geist Mono, self-hosted from fontsource as the site
  does. The wordmark is the outlined SVG, so Source Serif is never loaded.
- **No third-party request, no telemetry, no error reporting service, no
  analytics, no service worker.** The CSP enforces the first. The console
  keeps nothing on disk but the tab's sign-in and display choices.

CI fails a pull request over budget.

## 5. Version 1, page by page

"Writes" are what the page may change; everything else is read-only. Each
write confirms first, saying what will happen in Salli's words.

| Page | What you see | Writes | API operations | In v1 |
|---|---|---|---|---|
| **Home** | `salli status` as a page: net worth, safe to spend, the month so far, the FI score and date, what needs attention, what's coming up, decisions due for review, net worth over time. | None. | `reports.balanceSheet`, `ledger.incomeStatement`, `fi.score.get`, `reminders.list`, `insights.safeToSpend`, `insights.signals`, `decisions.reviews.due`, `insights.netWorth` | Yes |
| **Accounts and ledger** | Accounts by type with balances; an account's entries; an entry with its postings, rate and provenance. | Add an entry (one amount, from one account to another); reverse an entry; set posting tags. | `accounts.list`, `accounts.overview`, `entries.list`, `entries.get`, `entries.provenance`, `entries.create`, `entries.reverse`, `entries.postings.setTags`, `tags.list`, `ledger.trialBalance` | Yes |
| **Imports and review** | Uploaded statements; a statement's transactions with the entries Salli proposes and which rule proposed each. | Upload a statement; sort with rules or the model; approve, change or skip each; post; discard; make a rule from a choice. | `statements.upload`, `statements.list`, `statements.pending`, `statements.categorize`, `statements.post`, `statements.discard`, `rules.list`, `rules.suggestions`, `rules.test`, `rules.create` | Yes |
| **Cash** | The daily forecast to its low point, safe to spend until payday, cash flow by month, spending by category, recurring payments. | None. | `insights.forecast`, `insights.safeToSpend`, `insights.cashFlow`, `insights.spending`, `insights.recurring` | Yes |
| **Attention** | Signals, and reminders by due date. | Mark a reminder done. | `insights.signals`, `reminders.list`, `reminders.markDone` | Yes |
| **Decision lab** (below) | The baseline, scenarios, templates, principles, the journal, reviews. | Run and compare (nothing stored); keep principles; record decisions, notes and reviews. | below | Yes |
| **Financial independence** | The FI score and its history, projections in today's money at three returns, the assumptions with their sources and which are placeholders. | Set or clear an assumption, with its source. | `fi.score.get`, `fi.score.history`, `fi.projections`, `fi.assumptions`, `fi.assumptions.set` | Yes |
| **Tax** | The tax year, the last computation line by line, each line's explanation; rule sets, versions, validation, diffs. | Compute now (stored); validate; propose; activate, with step-up. | `tax.currentYear`, `tax.latest`, `tax.compute`, `tax.explain`, `tax.ruleSets.list`, `tax.ruleSets.get`, `tax.ruleSets.versions.get`, `tax.ruleSets.versions.validate`, `tax.ruleSets.versions.propose`, `tax.ruleSets.diff`, `tax.ruleSets.versions.activate`, `tax.ruleSets.versions.export` | Yes |
| **Settings** | Profile (name, currency, residency, time zone); sign-ins; personal access tokens; AI connections and model keys; digests and a preview; your data. | Edit the profile (the base currency only while it can change); change password; end sign-ins; make and revoke tokens (with `tax:activate` behind step-up); switch MCP, revoke connections; set model keys; set digest preferences; download exports. | `profile.get`, `profile.update`, `auth.me`, `auth.password.change`, the new sign-ins routes, `tokens.list`, `tokens.create`, `tokens.revoke`, `mcp.enabled.get`, `mcp.enabled.set`, `mcp.connections.list`, `mcp.connections.revoke`, `llmKeys.list`, `llmKeys.set`, `llmKeys.delete`, `ai.settings.get`, `notifications.preferences.get`, `notifications.preferences.update`, `notifications.preview`, `notifications.deliveries.list`, `exports.beancount`, `exports.hledger`, `account.export` | Yes |
| **Budgets and goals** | Budgets against spending; goals and their progress. | Create and edit. | `budgets.*`, `goals.*`, `reports.goalProgress` | Later |
| **Debts** | Debts, the payoff plan. | Create and edit. | `debts.*` | Later |
| **Investments** | Holdings, lots, prices, performance. | Record transactions and prices; link a holding to its account. | `holdings.*`, `portfolio.*` | Later |
| **Insurance, subscriptions, the advisor, bank connections** | | | `insurance.*`, `subscriptions.*`, `advisor.*`, `bankConnections.*` | Later |

### The decision lab

The heart of v1 and of the demo. It shows what Salli computes, and never
ranks.

| View | What you see | Writes | API operations |
|---|---|---|---|
| **Baseline** | The model every figure starts from: monthly income and expenses, balances by role at the as-of rate, debts counted once, holdings, notes and placeholders. | None. | `baseline.get` |
| **Templates** | The seven templates; a template's questions with Salli's honest defaults; the options it builds, compared; principles kept or broken; when buying draws level with renting. | None (`decisions.start` stores nothing). | `decisions.templates.list`, `decisions.templates.get`, `decisions.start`, plus `accounts.list`, `debts.list`, `holdings.list` for the questions that pick one of yours |
| **Scenarios** | A scenario built from changes, each a form for its `salli.scenario/1` type; its timelines against the baseline. | None (`scenarios.run` stores nothing). | `scenarios.run` |
| **Compare** | Two to five options side by side: what each gains and gives up, sensitivity at three returns, break-evens marked. Never in an order of merit: in the order the person added them. | None. | `scenarios.compare`, `principles.check` |
| **Principles** | Your rules of thumb, the 33 figures a check may read, which each option keeps or breaks. | Add, edit, archive. | `principles.list`, `principles.figures`, `principles.create`, `principles.update`, `principles.archive`, `principles.check` |
| **Journal** | Decisions as recorded, with their hashes and whether each still matches; notes; reviews; export. | Record a decision from a start or a comparison, with reasons in the person's words; add a note. | `decisions.list`, `decisions.get`, `decisions.markdown`, `decisions.record`, `decisions.notes.add`, `decisions.export`, `decisions.exportMarkdown` |
| **Reviews** | Decisions due: what the chosen option projected beside what happened. | Record a review. | `decisions.reviews.due`, `decisions.review` |

### What the console adds to the API

The console is a client like the CLI and adds no feature only it has. What it
needs from the server:

| Change | Why | Its `salli` command |
|---|---|---|
| `GET /v1/meta` gains `console_url` and `oauth.console_client_id` | `salli ui`, and the console's sign-in | `salli ui` |
| `GET /v1/auth/sign-ins`, `DELETE /v1/auth/sign-ins/{id}` (replacing the sessions list and revoke) | One list of every way in, CLI and console included | `salli sign-ins list` and `revoke` |
| Grant ids, reuse detection, the console's absolute lifetime, `authenticated_at` and step-up | Section 2 | none (OAuth plumbing) |
| The six number-or-string request fields become strings; `FireStrategy.target_monthly_expenses` a string | Money never a float | none (shapes only) |

## 6. An AI in the console?

The console shows Salli's figures. Should it also hold a chat with an AI?

| | No chat; point to your AI | A chat drawer on the in-app agent | "Explain this" buttons |
|---|---|---|---|
| **What it is** | Each page offers "Think this through with your AI": it copies a short prompt naming what's on screen (a decision's id, a scenario's question) for the person's own AI client over MCP. Nothing is sent from the console. | A side panel streaming `agent.chat` (`routers/agent.py`): tool calls shown as they happen, the `approval_required` gate as a console dialog. | Buttons that ask the model to explain one figure. |
| **"The LLM never computes"** | Held by MCP's guardrails, as today. | The agent's text can carry numbers no tool returned. Tool results can be rendered as Salli's own components, so the person can tell Salli's figures from the model's words, but the words remain. | Deterministic explanations already exist: provenance, `tax.explain`, assumptions with sources, break-evens. |
| **Fits MCP-first** | Yes: the person's AI is the one they already use. | It is a second chat beside the one in their AI client. | Partly. |
| **Needs a model on the server** | No. | Yes, and metered (`services.usage.charge`). | Yes. |
| **Risk** | None. | Model output rendered in the console widens what injected content can reach; the approval gate must be impossible to confuse with Salli's own confirmations. | Paraphrase passed off as explanation. |

**Recommendation: no chat in v1.** The console is the "Salli computes" half;
the person's own AI, over MCP, is the "your AI explains" half. Explanations in
the console are Salli's deterministic ones. "Think this through with your AI"
connects the two without the console sending anything. A chat drawer on the
in-app agent can come later, as its own design, if self-hosters ask for it.

## 7. Open and closed

### The line

| Open: salli-core | Closed: `leafmonkeylabs/salli` |
|---|---|
| The household console: every page above, for one person's own ledger | Organisations, and members within them |
| Salli's own sign-in, password-based | SSO: SAML and OIDC sign-in methods |
| The person's own sign-ins, tokens and AI connections | SCIM provisioning |
| The decision journal, its hashes and exports | Adviser seats, and roles within a firm (RBAC) |
| The person's own data exports | Client consent: an adviser seeing a client's books |
| Light and dark themes | Firm-wide audit-log export |
| The extension points below | Multi-tenancy |
| | White-labelling: a firm's name, mark and colours |

A test for which side something falls: if it exists because one person keeps
their own books, it is open; if it exists because one party acts for another,
or an organisation governs people, it is closed. Sharing between household
members, if it ever comes, is open and designed on its own, so that it doesn't
turn into the closed client-consent feature under another name.

### How a closed edition adds to the console

| | Build-time composition | Runtime plugin manifests | Module federation |
|---|---|---|---|
| **How** | The closed edition is a small app that imports the open console as a package and passes its extensions to `createConsole({ extensions })`, building one bundle. | The server lists console plugins in `/v1/meta`; the console imports each one's module from `/console/ext/…` at run time. | A bundler plugin shares modules between separately built bundles. |
| **Shared dependencies** | One React, one router, checked by the type checker. | The host must expose React and the kit to plugins (an import map), and versions must agree at run time. | Configured per bundle; mismatches fail at run time. |
| **Type safety** | Full. | At a boundary, by convention. | Partial. |
| **CSP** | `script-src 'self'` as it is. | Still `'self'`, but code arrives that the console's build never saw. | The same. |
| **Moving parts** | None at run time. | A loader, a manifest, versioning. | A bundler plugin and its own runtime. |

**Recommendation: build-time composition.** It is the simplest thing that
works and has no moving parts at run time. The closed edition builds its own
console, against the same version of the open one, and ships it in its own
image (built `FROM` Salli's, adding its extension) with `SALLI_CONSOLE_DIR`
pointing at it.

The open console is built the same way from day one, with no extensions, so
the seam is exercised in every build, and a test extension in the console's
tests adds a page, a navigation item and a settings panel.

What `createConsole` takes:

```ts
interface ConsoleExtension {
  /** The server extension it belongs to: shown only when /v1/meta lists it. */
  requires: string;
  routes?: ConsoleRoute[];           // pages, under /console/<path>
  navigation?: NavigationItem[];     // where each appears, and its label
  settingsPanels?: SettingsPanel[];  // panels in Settings
  theme?: ThemeTokens;               // the brand tokens, replaced whole
}
```

- **`requires`** ties a console extension to its server half: a page appears
  only when `/v1/meta.extensions` names that extension, so a closed console
  on a server without it shows the open console.
- **The console kit** (the `<Money>` component, tables, charts, page layout,
  forms) is exported from the package, so closed pages look and read like the
  rest, and keep the money rules.
- **No branching on who someone is.** Neither edition's console decides what
  a person may see; it shows what the API returns, and an `EntitlementPolicy`
  shapes that on the server, as today.

### The server half: sign-in methods

SSO happens where signing in happens: the server-rendered sign-in page. The
existing `IdentityProvider` seam verifies a bearer token from elsewhere; it
can't put a button on that page. So a new, generic seam:

- `Extension.sign_in_methods`: each with an id, a label, and a `start(rt)`
  that returns where to send the browser;
- the extension's own router handles the provider's return, checks the person
  is a member, and completes the pending authorisation through core's
  `complete_consent(rt, user_id, approve=True)`, recording `authenticated_at`;
- the sign-in page shows each method's label as a button beside the password
  form; with no extension, there are none.

The console doesn't change: it still receives a code for `salli-console`.
Step-up works the same, through whichever method the person signed in with.
This seam is built when the closed edition starts, not in v1.

### Acting for someone else: out of scope

Client consent means an adviser reading and working on a client's books.
Core's principal is one person (`Principal.user_id`), and an
`IdentityProvider` identity is recorded as that person's own sign-in, with
`tax:activate`. A delegate needs to be recorded as themselves, acting for the
client, without the client's permissions. That is a core change, the one firm
features need from core, and it gets its own design with the closed edition.
The console's part is small: its pages already take whose books they show
from the token.

### Guards

- **No billing words in the console.** `test_no_commercial_vocabulary.py`
  scans `packages/*/src` as well as `src/salli`, with `.ts`, `.tsx` and
  `.css`.
- **No firm words in open code.** A new `test_no_firm_vocabulary.py` over the
  same paths fails on `firm`, `tenant`, `organisation`/`organization`,
  `adviser`, `seat`, `SAML`, `SCIM`, `SSO`, `white-label` and `RBAC`.
  - It leaves out `advisor` (the Wealth Advisor is Salli's own) and `OIDC`
    (the `IdentityProvider` seam names it as an example).
  - Design records under `docs/design/` are not scanned, as the country guard
    already exempts them.
  - The "tenant isolation" comment is reworded rather than allowed.

## 8. Tests

| Kind | What it checks | Tooling |
|---|---|---|
| **Component** | Each component and page against fixtures: states for loading, empty, error, placeholders. | Vitest and Testing Library, in the workspace's `npm test` |
| **Fixtures from the real server** | The console's fixtures are what the API answers on the golden households (`tests/golden/`), written by the server as `tests/cli_fixtures.py` writes the CLI's; a contract test fails while they differ. | pytest (`tests/contract`) |
| **End to end** | Against compose, as `image.yml` already runs it: sign in on the server's page, reload, sign out; a second tab; reuse detection signing a stolen refresh token's grant out; step-up before activating; recording a decision; importing a statement; every page loads. | Playwright |
| **Accessibility** | Every page in both themes at 360, 768 and 1280 px, with no violations; keyboard-only runs of sign-in, compare and record; money's spoken reading. | `@axe-core/playwright`; a manual pass with VoiceOver and NVDA per sub-phase |
| **Visual regression** | Every page and chart at three widths, light and dark, on the golden households at their fixed dates. | Playwright screenshots, compared in CI |
| **No float touches money** | Fixtures carry amounts a float can't hold (`9007199254740993.01`, `0.30000000000000004`, three-decimal and zero-decimal currencies); every page must show them digit for digit. Every request body's amount fields must be decimal strings. `Number()` and friends appear only in `chart/geometry.ts`. | Vitest over the rendered DOM; a request interceptor; the lint rules and a test of their escapes |
| **Security headers** | The CSP and headers on every `/console` response; no third-party request in any end-to-end run; no `innerHTML`, `dangerouslySetInnerHTML` or `eval` in the source. | pytest for the headers; Playwright's request log; lint |
| **Guardrails** | No ranking word or field in the console's strings, as `tests/guardrails.py` holds the API's results. | A test over the string catalogue |
| **Budget** | The sizes in section 4. | A size check in CI |

## 9. Release and packaging

- **Where:** `packages/console` (`@leafmonkeylabs/salli-console`,
  AGPL-3.0-only), in the npm workspace beside the SDK and CLI.
- **Built into the image:** a Node stage in the `Dockerfile` builds the
  console from `package-lock.json` (`npm ci`), and the final stage copies only
  the built files. The final image gains a few megabytes of static files and
  no Node.js.
- **Versioned with the server:** the console's version is the server's, and
  a `server-v*` tag releases both. It is published to npm at that version so
  the closed edition can build against exactly the open console its base
  image carries.
- **Upgrades:** an open tab checks `/v1/meta.server_version` when it regains
  focus and on each navigation; when it differs, it says "Salli was updated.
  Reload to continue." A page chunk that fails to load after an upgrade leads
  to the same message, never to a blank page.
- **CI:** the workspace's `typecheck`, `lint`, `test` and `build` cover the
  console; the size check, axe and visual regression join them; `image.yml`
  runs the end-to-end tests against the compose stack it already starts.
- **Docs:**
  - the README gains `salli ui` in the quickstart and the "Using it" table;
  - [docs/self-host.md](../self-host.md) gains the console: settings, HTTPS or
    localhost, phones;
  - `packages/console/README.md` covers contributing;
  - CLAUDE.md gains the console's rules (a client of the API, no arithmetic on
    money, no firm words);
  - the brand README gains the chart contrast note and the tokens file.

## 10. Risks

- **Injected script with a person's sign-in.** The main risk of any browser
  client. Mitigated by escaping only, a strict CSP with Trusted Types, short
  access tokens, rotating refresh tokens with reuse detection, an absolute
  lifetime, and step-up for the two powerful actions. Not eliminated: a page
  open in a compromised browser can do what the person can, until it is
  closed.
- **Browser agents.** An AI driving the browser can click anything the person
  can. Step-up keeps activation and minting activating tokens behind the
  password on Salli's own page; every other write is something the person's
  MCP connection could do anyway.
- **Scope.** 229 operations invite a page for each. v1 is the pages above;
  each later page needs its own reason.
- **False precision in charts.** A smooth line looks more certain than a
  placeholder deserves. Placeholders are labelled on the chart and in its
  caption, and break-evens sit beside the lines they qualify.
- **The demo pulling design.** A pilot's wishes can push firm features into
  the open console. The open/closed test (section 7) and the vocabulary guard
  hold the line.
- **Per-tab sign-in friction.** Signing in for each new tab may annoy people.
  If it does, a shared sign-in across tabs (stored once, refreshed under a Web
  Lock) is a contained change; it trades a little exposure for convenience,
  and is the owner's call.
- **Maintenance.** A second client to keep in step with the API. The generated
  SDK and the fixtures written by the server make drift fail CI rather than
  production.

## 11. The order of building

```
C0  server groundwork ──► C1  console foundations and Home ──┬──► C3  decision lab
                                                              ├──► C2  where you stand
                                                              └──► C4  books, tax and settings ──► v1
then: C5 the look from the approved mockup
later: C6 the sign-in methods seam (with the closed edition) · C7 more pages · chat, members
```

| Sub-phase | What | Depends on | Can run beside |
|---|---|---|---|
| **C0** Server groundwork | `salli-console` client and computed redirect; `/console` serving with its headers and settings; `console_url` in meta; grant ids, reuse detection, absolute lifetime, `authenticated_at` and step-up; the sign-ins routes and `salli sign-ins`; `Cache-Control: no-store` on the API; money fields as strings; the consent page in the brand, reading "Sign in to Salli" for the console; `salli ui`; the guard extensions; rewording the findings above. | nothing | nothing |
| **C1** Console foundations | The package, tokens, fonts, the kit (`<Money>`, tables, layout, forms, chart primitives), sign-in and sign-out, errors as problem details, `createConsole` with a test extension, the Dockerfile stage, CI with budget, axe and visual tests. Pages: Home; Settings' profile and sign-ins. | C0 | nothing |
| **C2** Where you stand | Accounts and ledger, Cash, Attention, Financial independence. | C1 | C3, C4 |
| **C3** The decision lab | Baseline, templates, scenarios, compare, principles, journal, reviews. | C1 | C2, C4 |
| **C4** Books, tax and settings | Imports and review, rules; Tax with step-up; the rest of Settings. v1 is complete. | C1 | C2, C3 |
| **C5** The console's look | The shell, the kit and every page from the owner's approved mockup (As built (C5)). Planned here as the later pages, which moved to C7 when the owner asked for the look first. | v1 | |
| **C7** Later pages | Budgets and goals, debts, investments, insurance, subscriptions, the advisor, bank connections. | v1 | |
| **C6** Sign-in methods seam | `Extension.sign_in_methods` on the server's pages; built with the closed edition's first SSO method. | C0 | anything |

If one sub-phase runs at a time after C1, C3 comes first: the decision lab is
the heart of the console and of the demo.

## Decisions (2026-10-12)

The owner accepted each recommendation as it stands; the sections above give
the options that were weighed.

| # | Question | Decision |
|---|---|---|
| 1 | Where the console lives | Served by the server at `/console`, static files built into the image. Not in the CLI, not a separate image. |
| 2 | How `salli ui` works | Reads `console_url` from `/v1/meta` for the current context's server, opens it, and prints it (`--no-open` prints only). The CLI hands the browser nothing. |
| 3 | How the console signs in | OAuth authorisation code with PKCE as a first-party public client, `salli-console`, whose one redirect is `{SALLI_PUBLIC_URL}/console/callback`, computed from the setting and matched exactly. The password is typed only on Salli's own sign-in page. Not cookies, not `salli_st_` sessions. |
| 4 | Where tokens live | The access token in memory; the refresh token in memory and the tab's `sessionStorage`. One sign-in per tab; a reload keeps it; closing the tab ends it; a duplicated tab drops its copy. |
| 5 | Refresh-token hardening | Grant ids carried through rotation; a reused refresh token revokes its grant, for every client. A console grant ends 12 hours after sign-in (`SALLI_CONSOLE_SIGN_IN_HOURS`); the CLI's lifetime is unchanged. The console signs out after 30 minutes idle. |
| 6 | `tax:activate` in the console | Held, as a first-party sign-in, but only within five minutes of the password check: activating a rule set, or making a personal access token with `tax:activate`, sends the person through Salli's sign-in page again first. |
| 7 | Browser hardening and CORS | The CSP and headers in section 2, with Trusted Types; no HTML rendering of stored text; lint bans on `innerHTML`, `dangerouslySetInnerHTML` and `eval`. CORS unchanged: `ALLOWED_ORIGINS` stays empty by default. HTTPS or localhost is required. |
| 8 | Sign-ins | One list of every way in (sessions, the CLI per machine, the console per tab) at `GET /v1/auth/sign-ins` and `DELETE /v1/auth/sign-ins/{id}`, replacing the sessions routes outright, with `salli sign-ins` moved to them. |
| 9 | The licence | AGPL-3.0-only, like the server; the SDK stays Apache-2.0 for anyone building their own UI. |
| 10 | The stack | React, Vite and TypeScript in `packages/console`; React Aria Components; TanStack Router and Query; hand-drawn SVG charts; data through the generated SDK only. Preact if the budget is missed. |
| 11 | Chart colours and the focus ring | Baseline in ink, options in ledger green and graphite, told apart by dash and labels; brass and sand only as decoration, since brass is 2.4:1. The focus ring is ledger green (sand-on-dark on dark), not brass. The brand README records both for the app. |
| 12 | Money in the browser | Decimal strings end to end; no arithmetic on money in the console, exact or not; one geometry module may turn a string into a number for pixel positions only; amount inputs read the locale's marks by rewriting text; the API's number-or-string amount fields become strings. |
| 13 | Language and locale | British English only in v1, strings in one catalogue; numbers and dates in the browser's locale, overridable on the device. |
| 14 | The budget | 150 kB compressed JavaScript for the shell and Home, 75 kB per later page, 500 kB in all, 40 kB CSS; self-hosted fonts; no third-party request, telemetry or service worker. Enforced in CI. |
| 15 | v1's pages | Home, accounts and ledger, imports and review, cash, attention, the decision lab, financial independence, tax, settings, as in section 5. Budgets and goals, debts, investments and the rest come later. |
| 16 | Entering transactions in v1 | One amount from one account to another. Split entries stay in the CLI until the server can return a draft's balance, so the console never sums. |
| 17 | Members in the console | Not in v1: the owner keeps `salli-server members`. An owner-only members API is a later, separate design. |
| 18 | An AI in the console | No chat in v1. Deterministic explanations in the pages; "Think this through with your AI" copies a prompt for the person's own client. A chat drawer on the in-app agent is a later design, if wanted. |
| 19 | How closed features plug in | Build-time composition: `createConsole({ extensions })`, each extension tied by `requires` to a server extension in `/v1/meta`; the closed image ships its own build through `SALLI_CONSOLE_DIR`. The open console is built through the same seam. |
| 20 | SSO's seam | A generic `Extension.sign_in_methods` that adds buttons to Salli's sign-in page and completes the pending authorisation; built with the closed edition, not in v1. |
| 21 | Acting for another person | Out of scope here; the core change client consent needs gets its own design with the closed edition. |
| 22 | Guards | The commercial-vocabulary guard scans `packages/*/src` too; a new firm-vocabulary guard over open code; the "tenant", "tier" and "Pro Mode" wording in core is reworded. |
| 23 | Switching it off | `SALLI_CONSOLE=false` removes the route and refuses the console's client; on by default. `SALLI_CONSOLE_DIR` names the built files. |
| 24 | Versions and upgrades | The console ships in the image at the server's version, is published to npm at the same version, and asks an open tab to reload after an upgrade. |
| 25 | Tests | Component tests on fixtures the server writes from the golden households; Playwright end to end against compose; axe; visual regression at three widths in both themes; the exactness test; header and request checks. |
| 26 | The order | C0, then C1; then C2, C3 and C4 in any order or together (C3 first if one at a time); C5 and C6 after. |

## As built (C0)

C0 is the server side of the console: everything it needs from the server,
and nothing of the console itself.

**Signing in (decisions 3, 5, 6).**
- `salli-console` is seeded by `core_0021_console_sign_in` as a first-party
  public client with `step_up_seconds` 300 and no stored redirect: its one
  redirect, `{SALLI_PUBLIC_URL}/console/callback`, is computed from the
  setting (`McpOAuthService(console_redirect_uri=…)`) and matched exactly.
  It signs in to the API only (`resource {base}/v1`), never with the device
  grant, and only where `SALLI_PUBLIC_URL` is HTTPS or loopback/localhost
  (`config.is_secure_origin`); otherwise authorise says why.
- `oauth_grants` holds one row per sign-in, and every access and refresh
  token belongs to one (`grant_id`). Tokens issued before core_0021 get one
  grant per user, client and resource. A refresh rotates within the grant;
  the used refresh token is claimed with one conditional UPDATE, so of two
  requests racing with it, one is the reuse. A rotated refresh token
  presented again revokes the whole grant, for every client, and says so
  (`invalid_grant`, "already used"). Revoking any token of a grant
  (`/mcp/oauth/revoke`) revokes the grant.
- A grant records `authenticated_at` (from the code or device approval: when
  the password was checked) and, for the console, `expires_at` =
  `authenticated_at` + `SALLI_CONSOLE_SIGN_IN_HOURS` (default 12, 1 to 168).
  Access and refresh tokens never outlive it. The CLI's grants have none.
- `permissions_for` takes `sign_in_age` and `fresh_within` (the client's
  `step_up_seconds`): within 300 seconds (inclusive) the console holds
  `tax:activate`; after, `require_permission` and `POST /v1/tokens` (for a
  token asking for `tax:activate`) answer 403
  `/problems/step-up-required` with `max_age: 300` and RFC 9470's
  `WWW-Authenticate: Bearer error="insufficient_user_authentication",
  max_age=300`. `needs_step_up` is true only where signing in again would
  give the permission, so an MCP token, another application or a token made
  without it never get a step-up answer. The re-authentication flow is the
  same authorise with `prompt=login` (or any `max_age`): the sign-in page
  reads **Confirm it's you**, asks for the password, and starts a new grant
  whose `authenticated_at` is now. The console replaces its grant with the
  new one (C1).
- The sign-in page reads **Sign in to Salli** for the console, with one
  button; consent and device pages are restyled in the brand (paper, ink,
  ledger green, sand; night on dark; system fonts; the focus ring ledger
  green or sand-on-dark per decision 11, not brass).
- `GET /v1/auth/sign-ins` (`auth.signIns.list`) lists sessions and the API's
  live grants as `kind` `session`, `cli`, `console` or `app`, with
  `started_at`, `last_used_at` (a grant's is written at most once a minute as
  its access tokens are used), `expires_at` and `current`; `DELETE
  /v1/auth/sign-ins/{id}` (`auth.signIns.revoke`) ends one. They replace
  `auth.sessions.list` and `auth.sessions.revoke`; `auth.sessions.create`
  and `auth.sessions.signOut` stay. `salli sign-ins list|revoke` use them.

**Serving (decisions 1, 2, 7, 23).** `interfaces/api/console.py`: `/console`
and everything under it, registered in `create_app` (so before the MCP
catch-all) only when `SALLI_CONSOLE` is on and `SALLI_CONSOLE_DIR` holds an
`index.html`; a deep link returns `index.html`, `/console/assets/…` are files
(`immutable`, precompressed `.br`/`.gz` when accepted), anything resolving
outside the directory, through `..`, a dot file, a backslash, a NUL or a
symbolic link, is a 404. Every response carries the CSP and headers of
section 2 (plus `X-Frame-Options: DENY`). Every other response gets
`Cache-Control: no-store` unless it set its own. `/v1/meta` gains
`console_url` (null with no console) and `oauth.console_client_id`.
`salli ui` opens and prints `console_url` (`--no-open` prints only; `--json`
gives `{console_url, opened}`). `salli-server doctor` reports the console:
switched off, none built, served, or served where a browser can't sign in.

**Money (decision 12).** `contract.AmountIn` and `DecimalIn` refuse a JSON
number with a 422 that says to send a decimal string, and the six fields of
the survey use `AmountIn`. `FireStrategy.target_monthly_expenses` is a
decimal string, in `GET /v1/fi/strategy` and the generation stream's `done`
event. `normalizeAmountInput(input, { locale })` reads a comma-decimal
locale's marks by rewriting the text; the CLI passes the locale only when
set (`SALLI_LOCALE` or `salli config set locale`).

**Guards (decision 22).** The commercial-vocabulary guard scans
`packages/*/src` (`.ts`, `.tsx`, `.css`) too and also catches "every tier",
"Free included" and "plan gate"; `test_no_firm_vocabulary.py` is new. The
"tier"/"Free" wording in `routers/mcp_oauth.py` and `McpOAuthService`, "tenant
isolation" in `domain/agents/tools.py`, and "Pro Mode" and the retired
"mobile app" in `routers/agent.py`, `adapters/db/models.py`,
`domain/agents/buddy_agent.py`, `routers/statements.py`, `ports.py`,
`routers/accounts.py` and `interfaces/cli/main.py` are reworded.

**Departures from the text above, and why.**
1. **A seventh request field and two rates.** The survey names six request
   amounts; `OnboardingGoalItem.target_amount` was a seventh, and
   `IncomeItem.fx_rate` and `OpeningBalanceItem.fx_rate` took numbers too.
   All are strings now. `AmountIn` and `DecimalIn` (budgets, debts,
   insurance, holdings, subscriptions, assumptions) already said "string" in
   the API document but read a JSON number at run time; they now refuse one.
2. **`POST /mcp/oauth/consent` never approves a first-party client.** It
   checks no password (a deployment's own consent screen, holding a
   sign-in), so any sign-in, a personal access token without
   `tax:activate` included, could approve a `salli-cli` or `salli-console`
   request it started itself and take the code from the JSON answer: a sign-in
   that holds `tax:activate`. That was so for the CLI before C0, and #53
   fixed it on main while C0 was being built: `complete_consent` takes
   `password_checked`, which only the sign-in page sets, and refuses a
   first-party or unknown client without it. C0 keeps that one mechanism, and
   the console is first party, so it too signs in on Salli's own page only.
3. **The CLI takes turns refreshing.** With reuse detection, two `salli`
   commands refreshing one sign-in at once would sign it out. The SDK's
   `createOAuthTokenProvider` takes a `lock`, and the CLI holds a lock
   directory beside its config while it reloads, refreshes and saves (the
   console's Web Lock in C1 is the same seam).
4. **No console is served yet.** The image gains its Node stage and sets
   `SALLI_CONSOLE_DIR` in C1, with the console; until then `/console` is a 404
   like any unknown path, `console_url` is null and `salli ui` says the server
   has none. The design prefers serving none to a placeholder page.
5. **The idle sign-out** is the console's alone (C1); the server needs nothing
   for it.
6. **Documented errors are problems.** An error response a route describes
   in words only (the new 403s) is documented as a Problem, as every other
   error already was, so a few existing responses in the API document gained
   their content.


## As built (C1)

C1 is the console's foundations and its first pages: `packages/console`
(`@leafmonkeylabs/salli-console`, AGPL-3.0-only, with `LICENSE` and
`NOTICE`), served by the image at `/console`.

**The stack (decision 10).** React 19.3.0, React DOM 19.3.0, React Aria
Components 1.21.1, TanStack Router 1.170.40 and Query 5.104.0, Geist
(`@fontsource-variable/geist` 5.3.0) and Geist Mono (`@fontsource/geist-mono`
5.3.0); built with Vite 8.3.4, tested with Vitest, jsdom 30.1.1, Testing
Library, Playwright 1.63.0 and `@axe-core/playwright` 4.13.0. Every version
is exact (a test holds it). Data comes only through the workspace's SDK.

**Signing in (decisions 3 to 6), `src/auth/`.**
- PKCE (S256) as `salli-console` through Salli's sign-in page, back to
  `/console/callback`; the state and verifier wait in sessionStorage. The
  console first moves to `SALLI_PUBLIC_URL`'s origin, and refuses to start
  outside a secure context, saying why.
- The access token in memory; the refresh token in memory and the tab's
  sessionStorage, through the SDK's new `oauth.createBrowserTokenProvider`,
  which refreshes under a Web Lock (`oauth.webLock`; the SDK is 0.4.0).
- One sign-in per tab: the tab holds a Web Lock named for its sign-in while
  it lives; a duplicated tab finds it held and drops its copy, and signs in
  afresh.
- Step-up: a write answered `/problems/step-up-required` (`useWrite` in
  `src/api.tsx`) sends the person through the sign-in page with
  `prompt=login`, keeping their place and the write (its name and JSON
  input). On return the console asks `auth.me` who signed in: the same
  person, and it revokes the old grant, keeps the new one and retries the
  write once (a second step-up answer is shown, not followed); anyone else,
  and it revokes what they started, keeps the sign-in that asked and says
  nothing was changed.
- Sign-out revokes the grant (`/mcp/oauth/revoke`) and clears the tab and
  the query cache; a 401 the refresh can't mend says the sign-in has ended.
- Idle sign-out after 30 minutes without a key or a click, checked again
  when the tab is shown; a test may shorten it (never lengthen it) with
  `salli-console:idle-seconds` in sessionStorage.

**Money (decision 12).** `<Money>` formats the decimal string with
`formatAmount` in the device's locale: `USD -370.00` in prose, `(370.00)`
in oxblood in tables, read out as "minus 370.00 US dollars". Only
`src/kit/chart/geometry.ts` turns an amount into a number, for pixel
positions; which value is highest is decided on the strings. The money lint
covers `.tsx` under the browser's globals; a test fails on the escape
anywhere but there, and on any amount a float can't hold not shown digit
for digit (`9007199254740993.01`, `0.30000000000000004`, KWD, JPY).

**The kit and pages.** Tokens (`src/styles/tokens.css`) in light and dark
through `light-dark()`, with the device's light, dark or system choice;
layout, sections, rows, tables (lists on a phone), forms, problem details,
`ChartFigure` with **Show the figures**, and the outlined logo. Home is
`salli status` as a page, with decisions due for review and net worth over
time (the design's Home row); Settings has the profile, sign-ins and this
device's display choices. Every string is in `src/strings.ts` (British
English), and a test holds it to the voice: nothing ranks or urges.
**Think this through with your AI** copies a prompt; there is no chat.

**`createConsole({ extensions })` (decision 19).** The open console's
`main.tsx` is `createConsole().mount(root)`. An extension's routes (a
component, or a loader for its own chunk), navigation and settings panels
appear only when `/v1/meta.extensions` lists its `requires`; a test
extension adds all three, and on a server without it the console is the
open one.

**Serving, the CSP and the budget (decisions 7 and 14).** The Dockerfile's
Node stage builds the console on the builder's platform (`npm ci`, no
install scripts) and the final image copies `dist` to `/opt/salli-console`
(`SALLI_CONSOLE_DIR`): 1.5 MB more image, no Node.js. Under the server's
CSP and Trusted Types no violation is reported on any page (the browser
runs fail on one). The budget, checked by every build (gzip level 9, the
larger of what the server sends; brotli beside it):

| | gzip | brotli | limit |
|---|---|---|---|
| Shell and Home | 128.5 kB | 111.6 kB | 150 kB |
| Settings | 18.0 kB | 16.2 kB | 75 kB |
| All JavaScript | 146.4 kB | 127.9 kB | 500 kB |
| CSS | 4.6 kB | 4.1 kB | 40 kB |

**Tests and CI (decision 25).** Component tests on fixtures the server
writes (`tests/console_fixtures.py`, a sibling of `tests/cli_fixtures.py`,
with `tests/contract/test_console_fixtures.py` failing while they differ);
Playwright on the built console under the server's headers (a server test
holds `e2e/console-headers.json` to `CONSOLE_HEADERS`): axe and visual
regression on Home, Settings, its confirmation and the signed-out page at
360, 768 and 1280 px in both themes, with CSP violations, script errors and
requests to another origin as failures; and Playwright end to end against
compose in `image.yml`. CI's `console` job runs the browser checks in
Playwright's image, where the screenshots are made.

**Departures from the text above, and why.**
1. **A held Web Lock, not a BroadcastChannel question, finds a duplicated
   tab.** Asking races when two tabs start together; holding a lock named
   for the sign-in, for the page's life, cannot. A reload waits up to 1.5
   seconds for the old page's lock.
2. **The end-to-end step-up is triggered by substitution.** Only activating
   tax rules and minting a token that may are behind step-up, and neither
   is a C1 page. The compose run answers one profile save with the server's
   exact problem; the sign-in page asking again, the identity check, the
   grant swap and the retry are the real server's. C4 can trigger it for
   real.
3. **React Aria, checked against the CSP, needed two changes.** Its press
   handling adds a `<style>` unless one with its id exists: the rule is in
   `kit.css` and `createConsole` marks it present. Its modal adds one on
   iOS to stop scrolling, so the confirmation is the browser's own modal
   `<dialog>` instead. Its live announcer clears with `innerHTML = ''`,
   which Trusted Types refuses; none of the components C1 uses announces.
   C2 to C4 must check each new React Aria component the same way.
4. **The profile's time zone** is saved through
   `notifications.preferences.update`, the one operation that sets it.
5. **The sign-in fixtures are written by hand** (`test/fixtures/auth.ts`),
   typed by the SDK: who is signed in, the profile and the sign-ins are not
   a golden household's books.
6. **The warning mark is oxblood on light.** Clay is 2.0:1 on paper; the
   words say it too.
7. **Square corners.** The owner changed the design system during C1: every
   radius token is 0, and only dots and radio indicators are round. The
   brand README records it with decision 11's chart and focus-ring change.
8. **The npm package is the console's source**, which an edition's Vite
   build compiles, and depends on the SDK at an exact version (0.4.0), which
   must be released first; `release.yml` stops a `server-v` tag until it is.
9. **`playwright-core` is pinned** (and overridden at the root) so
   `@axe-core/playwright`'s peer resolves to Playwright's own version.

## As built (C3)

C3 is the decision lab: `/console/decide` and the six views under it, each
a chunk of its own, with **Decide** among the console's places (after Home,
on a phone's bottom bar too). Every figure is the server's, shown exactly;
nothing is ranked, and every option keeps the order it was given in.

**The pages.**
- **Overview** (`/decide`): the decisions due for review, the seven
  templates and the other views.
- **Baseline** (`baseline.get`): cash day by day for the as-of month and
  the twelve after it (a step line, the low point labelled) and net worth
  month by month to the horizon, drawn; income and spending as averaged;
  balances by role and by account; debts counted once; the assumptions,
  each placeholder flagged; the exchange rates; the fingerprint.
- **Templates** (`decisions.templates.list`, `.get`, `decisions.start`,
  with `accounts.list`, `debts.list`, `holdings.list` and
  `insights.recurring` for the names): a template's questions as a form
  built from its question schema (an input for each type, the lists of
  amounts, loans and splits, the questions that depend on another), each
  default with where it comes from, problems at their paths, the form's own
  and Salli's. The result: the options and what each is; what the figures
  rest on (placeholders, the ledger's freshness, the tax computed or not
  and why); the options side by side; the emergency fund's cover; rent or
  buy's level reading; the trade for each two options; the sensitivity at
  three returns, drawn; the break-evens, each on the range Salli searched
  (the house-price growth among them); the principles kept and broken; the
  answers as used, with where each came from. **Recording** is asked for:
  the question in the person's words, the option they chose (none is chosen
  for them), their reasons, the review date from the earliest the server
  allows, then a confirmation saying the entry can't be changed;
  `decisions.record` with `record.options`.
- **Scenarios** (`scenarios.run`, `scenarios.compare`,
  `principles.check`): options built from changes, a form for each of the
  ten `salli.scenario/1` types, or a scenario document pasted or loaded
  from a file; one runs, two to five compare. Cash day by day and net worth
  month by month are drawn for the baseline and each option, with the
  break-evens beside them; then the figures side by side, the trade, the
  sensitivity and the principles. An option can be saved on the device as
  a document (`salli whatif --file` runs it).
- **Principles** (`principles.list`, `.figures`, `.check`, `.create`,
  `.update`, `.archive`): those in use, each with whether the baseline keeps
  it; add and edit, Salli's problem shown at the check with its caret;
  archive after a confirmation; the archived kept below; the 33 figures.
- **The journal** (`decisions.list`, `.get`, `.reviews.due`, `.notes.add`,
  `.review`, `.export`, `.exportMarkdown`, `.markdown`): entries with their
  status; what is due; the journal saved on the device as JSON (every
  document exactly as recorded, with its hash) or Markdown. An entry: what
  was chosen, when and how, the review date, the hash and whether it still
  matches; the person's reasons and any agent's summary, marked as the
  agent's; the options' figures as recorded; the principles as they stood;
  notes; reviews, each projected beside actual with the reflection; from
  the review date, the review itself, its reflection added after a
  confirmation; the entry saved as JSON or Markdown.

**What the API gained.** `?timeline=true` on `POST /v1/scenarios/run` and
`/compare` adds `timeline` to each result: every day of the cash forecast
and every point of the monthly timeline from the as-of date to the horizon,
baseline and scenario. The figures and the hash are the same either way;
without it `timeline` is null, and MCP's results are unchanged.
`salli whatif --timeline` and `salli compare --timeline` ask for it in the
JSON, so the console still adds nothing the CLI lacks. The OpenAPI
document, the SDK (still 0.4.0, unreleased) and the CLI's fixtures were
written again; docs/scenarios.md says what comes back.

**The kit grew; nothing forked.** `LineChart`, `RangeChart` and `DotChart`
beside `ChartFigure`, which now makes its table only when opened; the
geometry module's `indexScale`, `stepPath` and `spread`, and `amountScale`
may leave zero out (still the one place an amount becomes a number);
`Field`, `TextAreaField`, `SelectField` and `RadioField`, each taking its
error from the caller; `inputs.ts` (amounts in the locale's marks, a rate
typed as 6.9% turned into 0.069 by moving the point in the text, whole
numbers read only as plain digits); `saveText` for files saved on the
device; `<Money signed>` for a change's plus; `Loaded` from Home. All are
exported for editions.

**Rules, as tests.** `test/lab-guards.test.tsx` reads `RANKING_WORDS` and
`NEGATED` from tests/guardrails.py and holds the lab's catalogue, and what
its pages render from the fixtures (three template results, a comparison,
the journal, an entry, a review, the principles, the baseline, with every
chart's figures opened), to them. The fixtures (`test/fixtures/lab.ts`) are
written by tests/console_fixtures.py on Home's household, after the
person's own writes, with the answers to the console's writes made after
every read; the generator fails if the lab's reviews due differ from
Home's, and the contract test holds both files to the server.

**The budget** (gzip level 9, brotli beside it):

| | gzip | brotli | limit |
|---|---|---|---|
| Shell and Home | 131.8 kB | 115.5 kB | 150 kB |
| Settings | 18.9 kB | 17.1 kB | 75 kB |
| Overview | 9.0 kB | 7.9 kB | 75 kB |
| Templates (the list and a template) | 36.8 kB | 33.0 kB | 75 kB |
| Scenarios | 36.8 kB | 33.1 kB | 75 kB |
| Principles | 28.8 kB | 25.8 kB | 75 kB |
| Journal | 9.9 kB | 8.6 kB | 75 kB |
| An entry | 29.4 kB | 26.3 kB | 75 kB |
| Baseline | 13.5 kB | 12.0 kB | 75 kB |
| All JavaScript | 188.4 kB | 166.3 kB | 500 kB |
| CSS | 5.9 kB | 5.3 kB | 40 kB |

**Tests.** Component tests for every view on the fixtures; Playwright on
the built console under the server's CSP: axe, screenshots at 360, 768 and
1280 px in light and dark, the CSP and request watch, and no page wider
than the screen, for every lab page (with each chart's figures opened for
axe too); a decision recorded by keyboard alone; the journal saved as files
under the CSP. Against compose: a template run, the decision recorded after
its confirmation, found in the journal, a note added and read back; every
lab page loaded from the real server.

**Departures from the text above, and why.**
1. **The decision lab's words are a catalogue of their own**
   (`src/lab-strings.ts`), loaded with its pages: in `strings.ts` they put
   the shell 7 kB nearer its 150. The catalogue tests cover both.
2. **A template's result has no timelines.** `decisions.start` doesn't
   carry them, and adding them there too seemed more than the console
   needed; the result draws the sensitivity and the break-evens. The
   Scenarios page draws both lines for options built there; handing a
   template's options to it is left for later.
3. **Compare is part of Scenarios,** two to five options on one page, not
   a view of its own; **reviews are on each entry,** with the reviews due
   listed on the overview and the journal, not a page of their own.
4. **The sensitivity is a dot plot** (each option a row, a mark at each
   return) and a break-even a value on the range Salli searched; the
   design names the charts, not their shape.
5. **Charts are drawn for the room they have,** by container queries
   rather than the screen's width, so a chart in a narrow column on a wide
   screen gets the phone's drawing. Home's chart looks as it did.
6. **What asks first:** recording, a note, a review and archiving a
   principle confirm; adding or editing a principle doesn't (an edit is
   versioned, and recorded decisions keep the old one), as C1's profile
   save doesn't.
7. **Not in the console yet:** answers to tax rules' questions
   (`tax_answers`, a scenario's `tax.answers`; `salli decide --tax-answer`
   has them) and a sale's named lots (`lots`; a sale is first in, first
   out). A document carrying them runs as written.
8. **No new React Aria component.** Selects, radios and dates are the
   browser's own; the text area is React Aria's `TextArea` inside its
   `TextField`, already checked in C1. Nothing announces through React
   Aria's live announcer (C1's warning); the browser runs report no CSP or
   Trusted Types violation on any lab page.
9. **A whole number** (months, years, a term) is read with `JSON.parse`
   from plain digits, so the money lint's one escape stays in the
   geometry module; it is never an amount.
10. **The fixtures are large** (`lab.ts`, about 0.8 MB): the lines of two
    timelines for each option are what the charts draw.

## As built (C2)

C2 is where you stand: the books, cash, attention and financial
independence, each page a chunk of its own, with their words in a
catalogue of their own (`src/where-strings.ts`). Every figure is the
server's, shown exactly; the console adds, converts and projects nothing.

**The places.** Home, Cash, Decide, Books, Attention, Independence and
Settings across the top (an edition's places before Settings), on a second
row under the logo between 721 and 1080 px. A phone's bar holds the
design's five: Home, Cash, Decide, Books and More; **More** (`/more`) lists
Attention, Independence, an edition's places and Settings, and is the
current place on any page the bar doesn't name.

**The pages.**
- **Books** (`/books`; `accounts.list`, `ledger.trialBalance`,
  `reports.balanceSheet`, `accounts.overview`): the balance sheet's totals,
  then every account by type, each balance in the base currency as the
  trial balance keeps it (debits as they are, credits in brackets, said in
  words), and for an account held in another currency its balance in that
  currency too, from its overview (as `salli accounts list --balances` and
  `salli accounts show`).
- **An account** (`/books/accounts/$account`; `accounts.overview`): its
  balance in its own currency and, if that isn't the base, in the base at
  the rates its entries recorded (or that its own is unknown); what it is;
  its balance after each day with an entry, drawn as steps placed by their
  dates, from zero; its entries newest first with the balance after each.
- **Entries** (`/books/entries`; `entries.list`): narrowed by date at the
  server (`from_date`, `to_date`) and by account and words picked from what
  it sent (as the CLI's `--account` and `--search`), in the address so a
  list can be reloaded or shared; newest first, the latest 50 until asked
  for all; each with its amount (its one debit's, or how many parts), from
  where to where, and whether it is reversed or a reversal.
- **An entry** (`/books/entries/$entry`; `entries.get`,
  `entries.provenance`): its lines, each amount in its own currency with
  the rate into the base; its tags; where it came from; and where it
  stands: reversed by which entry, the reversal of which (found by the
  ledger's own `reversed_by`), or standing, with **Reverse this entry**.
  The page says plainly that posted entries are never edited; reversing
  asks first, saying what Salli will post (`entries.reverse`).
- **Add an entry** (`/books/entries/new`; `entries.create`, decision 16):
  one amount from one account to another, the same decimal string on both
  lines, so the entry balances with nothing added up. Its currency is the
  base or one of the two accounts' own (an account's own is offered first);
  in another, the rate field says Salli uses the published rate for the day
  unless the bank's is given, and once posted the page reads the entry back
  and says which rate Salli used. A warning says when a currency would
  leave an account's own balance unknown. It asks before posting, saying
  that a posted entry is corrected by reversing it. Problems are shown at
  their fields: the form's own, Salli's at their paths, and "no published
  rate" at the rate.
- **Cash** (`/cash`; `insights.forecast`, `.safeToSpend`, `.cashFlow`,
  `.spending`, `.recurring`): the next 60 days as a step line with its low
  point labelled (a shortfall would be shaded); safe to spend until money
  next comes in, and what it is committed to before then; each cash
  account today, at its lowest and at the forecast's end, in its own
  currency; what is expected to come and go; cash flow by month as paired
  bars, income and spending, with what was left under each and the monthly
  average; spending by category; recurring payments. The rates and notes
  the server gives are shown beside the figures they qualify.
- **Attention** (`/attention`; `insights.signals`, `reminders.list`,
  `.markDone`, `.delete`): each signal in the order Salli gives it, with
  its kind, its detail and where to look (a part of Cash by its anchor, or
  the decision in the journal; imported transactions to review point to
  `salli statements pending` until C4); reminders overdue, due today and
  coming up, the done ones folded away, each marked done or deleted after a
  confirmation; a decision's review reminder opens the decision in C3's
  journal.
- **Financial independence** (`/fi`; `fi.score.get`, `fi.projections`,
  `fi.assumptions`, `fi.assumptions.set`, `fi.score.history`,
  `fi.strategy.get`): where you are (the FI number, invested now, the way
  there, the FI month, the savings rate, the monthly figures, the emergency
  fund); the invested money projected at the three real returns, drawn
  against the FI number, with the month each reaches it (and each year in
  its own money too once inflation is set); the score's parts; the
  assumptions, each with where it came from, every placeholder flagged,
  and setting your own (real return, inflation, withdrawal rate, share of
  surplus invested, nominal return) with its source and a note, or
  clearing yours; the score over time; and the FIRE strategy when there is
  one, its rationale marked as the AI's words.

**The kit grew; nothing forked.** `SubNav` (the lab's row of places now
uses it); `fieldErrors` moved to the kit, by field and by whole path;
`BarChart`, paired bars with the server's figure under each pair and a
partial month drawn lighter; `LineChart` gained a reference level (the FI
number), points placed by their days (`dayScale` in the geometry module,
still the one place an amount becomes a number), no shortfall shading for a
balance below zero by nature, and axis dates kept inside the plot; the time
axis's ticks moved to `kit/chart/ticks.ts`, which also fits every chart's
axis labels (`fitTicks`: each label's width estimated generously from its
characters at the chart's font size, in the drawing's own units so it holds
at any width; one near an edge hangs from that edge; a label closer than a
font size to the one before is dropped, keeping the first and last where
both fit), used by `LineChart`, `BarChart` and Home's net worth; a `Section` another page can
link to. All are exported for editions.

**No API change.** Every page reads and writes through operations the CLI
already has.

**Rules, as tests.** `test/where-guards.test.tsx` holds C2's catalogue,
and what its pages render from the fixtures with every chart's figures
opened, to `tests/guardrails.py`'s words; `score` is allowed on the FI page
only, as the FI score's name. `test/guards.test.ts` holds the catalogue to
the voice and British English. Amounts a float can't hold are shown digit
for digit in the books and in cash, and every amount sent is a decimal
string. The fixtures (`test/fixtures/where.ts`) are written by
tests/console_fixtures.py on Home's household, after one reminder of the
person's own is marked done, with the answers to C2's writes made after
every read; the generator fails if what Home also reads differs from
Home's, and the contract test holds all three files to the server.

**The budget** (gzip level 9, brotli beside it):

| | gzip | brotli | limit |
|---|---|---|---|
| Shell and Home | 135.0 kB | 118.5 kB | 150 kB |
| Books (the accounts) | 7.7 kB | 6.7 kB | 75 kB |
| An account | 9.8 kB | 8.6 kB | 75 kB |
| Entries | 25.3 kB | 22.6 kB | 75 kB |
| Add an entry | 25.9 kB | 23.2 kB | 75 kB |
| An entry | 25.0 kB | 22.4 kB | 75 kB |
| Cash | 11.4 kB | 10.1 kB | 75 kB |
| Attention | 23.9 kB | 21.4 kB | 75 kB |
| Financial independence | 27.7 kB | 24.9 kB | 75 kB |
| More | 0.4 kB | 0.3 kB | 75 kB |
| All JavaScript | 215.7 kB | 190.9 kB | 500 kB |
| CSS | 6.1 kB | 5.4 kB | 40 kB |

**Tests.** Component tests for every page on the fixtures, writes and
refusals included; Playwright on the built console under the server's CSP
for every C2 page at 360, 768 and 1280 px in light and dark (axe, with
each chart's figures opened too; screenshots; no page wider than the
screen; the CSP and request watch), and an entry added and reversed by
keyboard alone. No two axis labels overlap on any chart: a component test
checks the estimated extents in both drawings of every chart on the
fixtures, and a browser run measures the real text at 360, 768 and 1280
px. The places changed every page's frame, so C1's and C3's
screenshots were written again. Against compose: an entry posted between
two of the owner's accounts after its confirmation, found in the ledger and
in the account's balance, reversed after confirming with both entries
kept; the real return set with its source and its placeholder flag gone,
then cleared; every C2 page loaded with no problem shown.

**Departures from the text above, and why.**
1. **Reminders can be deleted** as well as marked done, after a
   confirmation that says a deleted one can't be brought back
   (`reminders.delete`, which `salli reminders delete` already makes); the
   Attention row lists only marking done.
2. **Posting tags are shown, not set.** An entry's page shows each line's
   tags; changing them (`entries.postings.setTags`, `tags.list`) stays with
   `salli entries tag` for now.
3. **What asks first:** posting an entry, reversing one, and marking a
   reminder done or deleting it confirm; setting or clearing an FI
   assumption doesn't (it can be set again, as C3's principle edits and
   C1's profile save don't).
4. **The chart of accounts reads the trial balance's signs** (credits in
   brackets, as `salli accounts list --balances` shows them), with the
   balance sheet's totals beside them; the console turns no sign round.
   An account held in another currency costs one `accounts.overview` read
   for its own balance.
5. **A reversal's link back** to the entry it reverses is found in the
   entries list (the original's `reversed_by`): the server's reversal
   carries no reference of its own.
6. **The cash forecast is 60 days**, as `salli insights forecast` asks by
   default; cash flow is six full months and this one; spending is by
   category over three months.
7. **Spending by category is a table** (the server's order, largest
   first, with each share); the design's charts table names no shape for
   it.
8. **No new React Aria component.** Selects and dates are the browser's
   own, confirmations the browser's modal `<dialog>`; nothing announces
   through React Aria's live announcer, and the browser runs report no CSP
   or Trusted Types violation on any C2 page.
9. **The FI score's history is a table**, not a chart: a score is kept
   only when its inputs change, so there are often too few points to draw.

## As built (C4)

C4 is books, tax and settings: imports and the review queue, rules, tax
with its rule sets and activation, and the rest of Settings. With it, v1
is complete: every page of section 5 marked for v1 is built. Every figure
is the server's, shown exactly; the console adds, converts and computes
nothing. The words are in three catalogues of their own, loaded with
their pages (`src/books-strings.ts`, `src/tax-strings.ts`,
`src/settings-strings.ts`).

**The places.** **Tax** joins the places after Books (eight across the
top; on a phone's bar it is under More). Books gains **Imports** and
**Rules** among its own places. Settings gains places of its own: the
profile and sign-ins (C1), tokens, AI connections, digests and your data.
There are no members' pages (decision 17: the owner keeps `salli-server
members`), and nobody acts for another person (decision 21): every page
is the signed-in person's own books.

**The pages.**
- **Imports** (`/books/imports`; `statements.upload`, `statements.list`,
  `accounts.list`, `bankConnections.list`): a statement file from this
  device (OFX/QFX, QIF, camt.053, MT940, CSV, Excel, PDF, up to 10 MB),
  with the account it is for (the money side of every row), its currency
  for a file that names none, how its dates are written, and, folded
  away, the bank, which account in a file holding several, and an earlier
  import it replaces; then what Salli read and noted, nothing booked yet,
  and the way to review it. Every statement, with whether it waits for
  review. Each bank connection with its accounts, their balances at the
  bank and when it last synced; connecting, mapping and syncing stay with
  `salli banks`.
- **The review queue** (`/books/imports/$statement`; `statements.pending`,
  `statements.categorize`, `statements.post`, `statements.discard`,
  `rules.list`, `rules.create`): each transaction as Salli read it (the
  bank's words beside a rule's tidier ones), its amount in or out, the
  statement's account and the other side, and who proposed that (a rule
  by its name, the model and how sure, or the person); a warning, with
  the entry, where it looks like something already booked. Choosing where
  money came from or went is kept at once. A selection (or every complete
  one that isn't a possible duplicate) is posted, or discarded, after a
  confirmation listing it; then the posted entries open in the ledger. The
  page says plainly that nothing is booked until it is posted, and
  nothing twice. A rule can be made from a transaction, its form filled
  from it.
- **Rules** (`/books/rules`; `rules.list`, `.create`, `.update`,
  `.delete`, `.test`, `.suggestions`): the rules in the order they are
  tried, each in words with what it has decided and when; a form for a
  rule's conditions (what it looks at, how, the value; amounts in the
  locale's marks, sent as decimal strings) and what it books, tested
  against what is already booked before saving if the person wants;
  deleting after a confirmation; the suggestions the person's own
  bookkeeping implies, each made a rule as it is or edited first.
- **Tax** (`/tax`; `tax.currentYear`, `tax.latest`, `tax.compute`,
  `tax.explain`, `tax.ruleSets.list`, `tax.ruleSets.versions.get`): whose
  rules and which year (or, plainly, that there is no residency or no
  active rules, and how to add them); the last computation for the year
  Salli computes (net, payable, refund, when, and the version with its
  content hash), what it took from the books by role, every line with its
  expression and source, each explained on request (the expression, where
  it is written, the source it cites, what it uses, its bands, what uses
  it; nothing stored); computing again; the active rules' deadlines;
  every rule set with its active and newest versions.
- **A rule set** (`/tax/rules/$ruleSet`; `tax.ruleSets.get`): every
  version with its status, who wrote it (the person, or an agent by its
  client's name), its note and when.
- **A version** (`/tax/rules/$ruleSet/versions/$version`;
  `tax.ruleSets.versions.get`, `tax.ruleSets.get`, `tax.ruleSets.diff`,
  `.validate`, `.propose`, `.activate`, `.export`): what `salli tax rules
  activate` reviews, as a page. What is new against the active version
  (or that it is the first), each change with its path, before and after,
  whether it is a figure, and the source it cites, linked; every worked
  example passing or failing, with each mismatch; any error or warning
  the validator found, at its path; the sources (links only to `https:`,
  opening apart, `noopener noreferrer`) and deadlines; the canonical
  document saved on this device. **Activating** a version that compiles
  and whose examples pass asks first, saying what Salli will compute with
  from now on, what stays as history and who wrote it. Checking a version
  again and proposing one are there too. Every tax page says that only a
  person activates, never an AI.
- **Tokens** (`/settings/tokens`; `tokens.list`, `.create`, `.revoke`):
  each live token with its first characters, what it may do, when it was
  made, expires and was last used; revoking after a confirmation; making
  one, with an expiry, and with `tax:activate` after a confirmation that
  says what such a token can do.
- **AI connections** (`/settings/ai`; `mcp.enabled.get`, `.set`,
  `mcp.connections.list`, `.revoke`, `llmKeys.list`, `.set`, `.delete`,
  `ai.settings.get`): MCP on or off (off only after a confirmation); each
  connected client, revoked after a confirmation; which provider Salli's
  own features use and with whose key; each provider's key (its last four
  characters and when the provider accepted it), set, replaced or removed
  after a confirmation, or why this server can't keep keys.
- **Digests** (`/settings/digests`; `notifications.preferences.get`,
  `.update`, `notifications.preview`, `notifications.deliveries.list`):
  whether, how often, on which day and at what hour, in which time zone
  (the profile's too), and what a digest says; when the next goes; the
  digest as it would go now; each one sent, with what it said.
- **Your data** (`/settings/data`; `exports.beancount`, `exports.hledger`,
  `account.export`): the books as Beancount or hledger, and everything as
  one JSON file written exactly (the SDK's `toJsonText`), each saved on
  this device through a blob URL, which the CSP allows.

**The step-up, for real (decision 6).** C1 triggered it by substitution;
C4 triggers it with tax activation. Against compose, the run signs in,
reviews a proposed version of the fictional XA 2031, waits out the five
minutes the console's sign-in holds `tax:activate` for (no setting
shortens a client's `step_up_seconds`, C0 and C1 offer no test-only way
to, and none was added), then activates: the server answers 403
`/problems/step-up-required`, Salli's page asks "Confirm it's you", the
console checks it is the same person, swaps its grant (the old one
revoked) and activates on return, once. The run sees the server's 403 and
then its 200, the version active, and the tab's sign-in replaced; a token
with `tax:activate` is then made at once, the password being fresh. The
component tests drive the same path with the server's own answer, which
the fixtures record from a console sign-in six minutes old, through the
callback; a second step-up answer on the retry is said, not followed.
Making a token with `tax:activate` goes through the same path.

**Secrets.** A token is shown once, by `<Secret>`: a read-only field,
**Copy it** through the clipboard API and, where that is refused, the
text selected for the keyboard. A key is typed into a password field and
the field emptied once Salli has it; only its last four characters come
back. `useWrite` gains `secret`: `'answer'` (a token) or `'input'` (a
key) makes TanStack forget the write once nothing shows it, and
`'input'` also keeps the key out of sessionStorage, where a step-up would
keep a write's input (a step-up answer to it is shown, not followed).
Tests check that neither is anywhere once the page is left: the page,
sessionStorage, localStorage, the query cache and the mutation cache.

**The kit grew; nothing forked.** `FileField` (the browser's own file
input), `CheckboxField`, `Secret`, `Field` taking a password type and a
list of suggestions, and `useWrite`'s `secret`; all exported for editions.
Every checkbox is drawn square in `kit.css`, since the browser's own box is
rounded; a radio stays the browser's, a circle by meaning, and with forced
colours the system draws the checkbox again.

**No API change.** Every page reads and writes through operations the CLI
already has.

**Rules, as tests.** `test/c4-guards.test.tsx` holds C4's catalogues, and
what its pages render from the fixtures (an explanation and the
activation's confirmation open), to `tests/guardrails.py`'s words;
`test/guards.test.ts` holds them to the voice and British English. The
fixtures (`test/fixtures/books.ts`, `tax.ts`, `settings.ts`) are written
by `tests/console_c4_fixtures.py`, part of `tests/console_fixtures.py` and
held by its contract test, over in-memory storage (`tests/console_fakes.py`)
with every id and clock fixed: imports, the queue and rules on Home's
household; the fictional XA 2031 (`tests/golden/rules/xa2031.json`, with a
deadline added) on the taxed household, version 1 the person's and
active, version 2 an agent's proposal raising the relief with the budget
it cites, version 3 an agent's draft whose example fails; tokens, a key,
a digest sent, and the plain-text exports on Home's household. No secret
in them opens anything.

**The budget** (gzip level 9, brotli beside it):

| | gzip | brotli | limit |
|---|---|---|---|
| Shell and Home | 135.7 kB | 118.4 kB | 150 kB |
| Settings (the profile and sign-ins) | 19.6 kB | 17.7 kB | 75 kB |
| Imports | 29.8 kB | 26.5 kB | 75 kB |
| The review queue | 33.5 kB | 29.9 kB | 75 kB |
| Rules | 31.9 kB | 28.5 kB | 75 kB |
| Tax | 22.7 kB | 20.5 kB | 75 kB |
| A rule set | 4.0 kB | 3.5 kB | 75 kB |
| A version | 23.0 kB | 20.7 kB | 75 kB |
| Tokens | 22.7 kB | 20.4 kB | 75 kB |
| AI connections | 22.1 kB | 19.8 kB | 75 kB |
| Digests | 22.2 kB | 19.9 kB | 75 kB |
| Your data | 21.1 kB | 18.9 kB | 75 kB |
| All JavaScript | 250.6 kB | 221.3 kB | 500 kB |
| CSS | 6.5 kB | 5.8 kB | 40 kB |

**Tests.** Component tests for every page on the fixtures, writes and
refusals included; Playwright on the built console under the server's
CSP for every C4 page (and Tax with a line explained) at 360, 768 and
1280 px in light and dark: axe, screenshots, no page wider than the
screen, the CSP and request watch; axe on the activation's, a discard's
and MCP's confirmations in both themes; a statement file uploaded from
the device (its bytes reach the server) and downloads saved, under the
CSP; the review queue and an activation by keyboard alone; a token shown
once and gone from the page and storage once left. The places changed
every page's frame at 768 and 1280 px, and the books' and Settings' at
360, so those screenshots were made again. Against compose: a rule made,
a CSV statement imported for a new account, an account chosen in review,
both posted after the confirmation and found in the ledger and the
account's balance; a token made, used, revoked and refused after; MCP
turned off after confirming and on again; a tax rule set activated
through the real step-up; every C4 page loaded with no problem shown.

**Departures from the text above, and why.**
1. **Settings is six pages**, each a chunk of its own under Settings'
   places, rather than one page: the profile and sign-ins as C1 built
   them, then one page each for tokens, AI connections, digests and your
   data.
2. **A CSV's columns are read by the server.** No API operation takes a
   column mapping (the parsing service can take one; no route or command
   passes it), so the console sends what the API takes (the account, the
   currency, the date order, the bank, the file's account, what it
   replaces) and says that the columns are read from the file. A mapping
   in the console waits for one in the API and the CLI.
3. **Sorting is the upload's.** Rules, then the model when there is a key,
   sort a statement as it is imported, as `salli import` does; no
   operation sorts it again. The queue says who proposed each account.
4. **A choice is kept at once** (`statements.categorize`), not held until
   posting as the CLI's interactive review holds it: it can be made again,
   and a reload keeps it. Posting and discarding confirm; choosing
   doesn't.
5. **Bank connections: where they stand only.** The design puts them
   later; Imports shows each, and points to `salli banks` to connect, map
   and sync.
6. **What asks first:** posting, discarding, deleting a rule, activating,
   a token that may activate, revoking a token or a client, removing a
   key, and turning MCP off. Choosing an account, saving a rule (tested
   first if wanted), making a suggestion a rule, computing (it keeps a
   computation and changes nothing else), checking or proposing a
   version, saving a key or digest preferences, and turning MCP on don't.
   Back from a step-up, the activation (or the token) runs without asking
   again: the person confirmed before Salli's page.
7. **What is new** lists every change the server's diff gives, a source
   added or changed as well as figures, as the CLI's review does; a
   change whose source isn't in the version's own document is found in
   the diff's sources.
8. **Drafting rules stays with agents and the CLI.** The console doesn't
   create, import or edit a rule document (section 5's Tax row lists no
   such write); the version's page saves the canonical document for
   that.
9. **AI settings are read, not changed.** The provider Salli's own
   features use is shown; choosing a provider or models, and a ChatGPT
   plan, stay with `salli ai`.
10. **Two fixtures are written by hand,** typed by the SDK, as C1 wrote
    the sign-ins: the AI clients connected over MCP (a way in, not the
    books) and a cut-down "my data" (`account.export` reads every
    service a household has; the copy carries an amount a float can't
    hold, to check the file is saved digit for digit). The tax fixtures
    are the taxed household's, in 2031; the pages show them unchanged on
    the console's date.
11. **jsdom's fetch leaves a file's bytes out of a multipart body**, so
    the component tests check the upload's shape and the browser run
    checks its bytes.
12. **The places take a row of their own up to 1180 px** (C2 had 1080):
    eight places beside who is signed in need it; Sign out no longer
    wraps.
13. **No new React Aria component, and no new chart.** File inputs,
    checkboxes and selects are the browser's own; the secret's field is a
    native read-only input; confirmations the browser's modal `<dialog>`.
    Nothing announces through React Aria's live announcer; the browser
    runs report no CSP or Trusted Types violation on any C4 page, and file
    inputs and downloads work under the CSP.
14. **The fixtures name tax lines** (`income_tax.band_1.amount`) that
    gitleaks' generic rule takes for keys; `.gitleaksignore` lists those
    findings by fingerprint, as it lists the CLI's.
15. **Changing the password stays with `salli password`.** Section 5's
    Settings row lists it, but decision 3 types the password only on
    Salli's own sign-in page, never into the console's script, and a
    change needs the current one and the new. Settings says where it is
    changed instead.

## As built (C5)

C5 is the console's look, from the mockup the owner approved ("I like it.
Lets get them to the console"): the shell, the kit and every C1 to C4 page
moved onto them. Nothing new is computed and no API changed: every page
reads and writes what it did, through the same operations.

**The shell.** A 56 px top bar on paper: the outlined logo (Source Serif
is never loaded; the wordmark is the outlined file), the server's address
and version as a chip (`/v1/meta`'s `server_version`), a theme switch
(light or dark, the other way from how the page looks; Settings keeps "as
the system"), and who is signed in (their initial and name, from
`profile.get`) opening a panel with Settings and Sign out. Under it, a
side menu on paper: Home and Cash; Books, Decide and Tax; Attention, with
a count of the signals Salli gives (`insights.signals`, the count beside
the name, its words for a screen reader), and Independence; an edition's
places; Settings at the foot; "Self-hosted · AGPL-3.0". The current
place's own places are listed under it. The menu folds to a rail of
icons, each keeping its name; it is open from 1081 px and a rail below
until the person chooses, and the choice is kept on the device beside
the theme (`salli-console:side`). A bar over the page holds the menu's
switch, the way back (to the crumb before), and where you are: the place,
its own place, anything a page names between (a rule set above its
version), then the page (`src/shell/places.ts`, one list for the menu,
the crumbs, the page's tile and each place's row of places). The working
area is bone; every section a paper card.

**Phones** keep the design's bottom bar of five places (Home, Cash,
Decide, Books, More), decided in section 4 and unchanged: the side menu
and its switch are not shown at 720 px and below, and the top bar keeps
the logo, the theme and who is signed in.

**The kit grew; nothing forked**, all exported for editions:
- `Page` gains its header card: the place's tile (or `icon`), the one h1,
  `facts` as chips, the description, `actions`; and `trail` for the
  crumbs. A `Section` is a card with its label inside, and `aside` puts a
  control at its head (a chart's range); a `Panel` in a section is the
  card's body.
- `SubNav` is a segmented row on a bone track.
- `Icon` (24 px grid, 1.5 px strokes, square caps); `Chip`, `IdChip` (an
  id's first eight characters, as the salli command shows them, the
  whole id on hover), `AccountChip` and `TypeMark` (asset filled,
  liability hollow, income sand, spending graphite, equity brass, the
  type in words too), `Status` (Posted, Reversed struck through, Reversal
  in the brand's colour, a warning with its "!"), `Count`.
- `Popover`, a disclosure (not a modal, and not React Aria's): the panel
  takes the focus, Escape gives it back to the button, a click or the
  focus outside closes it.
- `KeyFigures` and `KeyFigure` (a labelled group, not a region: a figure
  often shares its name with the section that details it), `Segmented`.
- `Pagination` and `usePages`: what is shown of how many, 15, 25 or 50
  rows, the page before and after. It counts rows, never money.
- `Sheet`: one thing from a list beside it, a complementary region whose
  title takes the focus, closed by Escape or Close with the focus given
  back; over the list's far edge from 1081 px, under it below.
- `Bar`: a bar beside a figure, its length from the geometry module
  (`amountScale`), still the one place an amount becomes a number.
- `Table` gains cell classes, `aria-sort` and a selected row, and a table
  wider than its card takes the focus, named by its caption, so the
  keyboard can scroll it. `<Money variant="figure">` shows its code small
  in Geist Mono before the figure, and a negative in brackets, as a
  statement does.
- New token roles in `tokens.css` and `theme.ts`: `chrome`, `work`,
  `card`, `well`, `hover`, `selected`, `tile`, `tile-text`, `dash` and the
  five `type-*`. The tile is ledger green with paper-on-dark (sand with
  night on dark).

**The pages.**
- **Home:** key figures (net worth with its assets and liabilities, safe
  to spend until when, the month so far with its income and spending,
  the FI score with its grade and FI month); net worth by month with a
  month to read off, picked from a list or by a click on the chart, the
  picked month outlined; safe to spend line by line, cash today and each
  commitment above the server's figure under a double rule, then the
  next income and the rates; what needs attention in one card (what
  Salli noticed, what is coming up with Overdue as a badge and the due
  date, decisions due for review); spending this month by account with
  bars and the server's total; the FI score's parts with bars, the way
  there, the savings rate, the assumptions, and a link to the FI page.
  The header offers "Think this through with your AI" and "Think a
  decision through" (the decision lab).
- **Every books page** carries the books' facts (the base currency, how
  many accounts, and "Trial balance nets 0.00" with a tick, the server's
  `ledger.trialBalance.net`, ticked only when its digits say zero) and its
  actions, Import a statement and Add an entry. Add an entry left the row
  of places (Accounts, Entries, Imports, Rules) for the header.
- **Accounts:** the balance sheet's totals as key figures; each account an
  account chip.
- **Entries:** a toolbar (Filters, a dashed button counting what is on,
  opening the dates and the account; each filter a chip that removes it;
  words searched as they are typed, kept in the address; Export; a
  Columns menu for the id, the source and the status); the table (id
  chips, the date sortable newest or oldest first, the description,
  from and to as account chips with "+1" for more, the amount with the
  currency in the header when the page shares one, the source, the
  status, and an eye); a page at a time. The eye opens the entry in a
  sheet: its lines, debit and credit, a total row only where each side is
  one line in one currency (so it is that line's own amount), "Debits
  equal credits in your base currency: Salli posts no entry that doesn't
  balance", its id, date, source and lines, Reverse after the same
  confirmation, and its own page, which still works as before.
- **An entry:** facts (id, date, source, lines), its lines as the sheet
  shows them with the rate column, its standing and Reverse.
- **An account:** facts (code, type, role, currency, entries), key figures
  (its balance, in the base too when held in another currency, how many
  entries since the first, the latest), the balance chart with a range
  (the last 90 days, six months, all), its details, its entries with the
  balance after each, a page at a time.
- **Every other page** (cash, attention, independence, the decision lab,
  tax, settings, More) has the header card with its place's tile, its
  sections as cards and its row of places segmented. A tax version's
  status is a badge among its facts and its rule set a crumb; Your data's
  status line is no longer an empty card; More lists its places in one.

**Rules, as tests.** Component tests cover the key figures, the month
read off the chart, the toolbar (the filters' popover, removing a chip,
words as typed), pages, the columns menu and the sheet; the money test
holds a key figure's digits exact. In the browser, for the filters' and
who-is-signed-in popovers and an entry's sheet at 360, 768 and 1280 px in
both themes: axe, the focus moving in and back, no page wider than the
screen, screenshots; the side menu folding to a rail, kept after a
reload, and the breadcrumb's way back. The shell changed every page's
frame, so every screenshot was made again in Playwright's image.

**The budget** (gzip level 9, brotli beside it):

| | gzip | brotli | limit |
|---|---|---|---|
| Shell and Home | 140.4 kB | 122.2 kB | 150 kB |
| Settings (the profile and sign-ins) | 19.6 kB | 17.7 kB | 75 kB |
| Overview (the lab) | 9.3 kB | 8.1 kB | 75 kB |
| Templates | 36.5 kB | 32.7 kB | 75 kB |
| Scenarios | 37.2 kB | 33.4 kB | 75 kB |
| Principles | 27.3 kB | 24.4 kB | 75 kB |
| Journal | 10.1 kB | 8.8 kB | 75 kB |
| A journal entry | 29.8 kB | 26.6 kB | 75 kB |
| Baseline | 13.0 kB | 11.5 kB | 75 kB |
| Books (the accounts) | 8.7 kB | 7.6 kB | 75 kB |
| An account | 12.0 kB | 10.6 kB | 75 kB |
| Entries | 30.5 kB | 27.3 kB | 75 kB |
| Add an entry | 27.1 kB | 24.3 kB | 75 kB |
| An entry | 27.0 kB | 24.1 kB | 75 kB |
| Cash | 12.4 kB | 10.9 kB | 75 kB |
| Attention | 24.6 kB | 22.0 kB | 75 kB |
| Financial independence | 28.5 kB | 25.5 kB | 75 kB |
| More | 0.4 kB | 0.3 kB | 75 kB |
| Imports | 30.8 kB | 27.4 kB | 75 kB |
| The review queue | 34.5 kB | 30.8 kB | 75 kB |
| Rules | 32.9 kB | 29.4 kB | 75 kB |
| Tax | 22.7 kB | 20.5 kB | 75 kB |
| A rule set | 3.9 kB | 3.4 kB | 75 kB |
| A version | 23.0 kB | 20.7 kB | 75 kB |
| Tokens | 22.7 kB | 20.4 kB | 75 kB |
| AI connections | 22.1 kB | 19.9 kB | 75 kB |
| Digests | 22.2 kB | 19.9 kB | 75 kB |
| Your data | 21.1 kB | 19.0 kB | 75 kB |
| All JavaScript | 260.3 kB | 229.5 kB | 500 kB |
| CSS | 9.4 kB | 8.4 kB | 40 kB |

**Departures from the mockup, and why.** The rules above win over it.
1. **No single-key hints.** The mockup's segmented rows show A, E, T. The
   console has no single-key shortcuts, and WCAG 2.1.4 would need them to
   be switched off, remapped or active only on focus; it shows no hints
   rather than hints that do nothing.
2. **No arithmetic, so some figures are not there.** The account's "In,
   last 30 days", "Out, last 30 days" and "Lowest, last 90 days", Home's
   change "since Sep 30" and "Spent … · no income yet" would be sums,
   differences or a window the server doesn't compute: the account shows
   its balance (and in the base), how many entries and the latest instead,
   and Home the server's income and spending for the month. The account's
   entries have no amount column and no money in or out filter: the
   server gives the balance after each, not the movement.
3. **No "Show in EUR" switch.** Converting an entry's amount into the base
   currency would be arithmetic; the amount column names the currency in
   its header when the page shares one, and each amount carries its code
   when not.
4. **An entry's total** is a row only where each side is one line in one
   currency; with more lines the console would have to add them. Every
   entry says what Salli checks of it instead.
5. **No Trial balance or Exports tab.** Neither is a page: the trial
   balance's net is a fact on every books page and its balances are the
   accounts', and Export opens Settings, Your data (Beancount, hledger,
   JSON), where the exports are. The account's own tabs (Overview,
   Entries, Imports, Details) are one page, under the books' row.
6. **Reversing asks in the console's confirmation dialog** (the browser's
   modal `<dialog>`, as every write does), not inline in the sheet.
7. **The server chip is not a switch.** A console belongs to the server
   that serves it; it shows the address and version only. The wordmark is
   the outlined logo, not live Source Serif.
8. **Home writes nothing**, as section 5 has it: reminders are marked done
   on Attention, not from Home, and a decision due opens the journal.
9. **Status words** say Overdue and the due date, not "6 days overdue": a
   message gives a date, not a count of days (tests/guardrails.py).
10. **The net worth chart keeps its bars** (what you own above the line,
    what you owe below) with the line over them; a month is picked from a
    list (the keyboard's way) or by a click, rather than by buttons drawn
    on the chart, which would sit inside its `role="img"`.
11. **The side menu's foot** says "Self-hosted · AGPL-3.0" only: "Your data
    stays on this server" isn't so once a model key or an AI client is
    connected.
12. **Key figures are groups, not regions**, and the crumb bar is a
    navigation landmark (axe's region rule).
13. **Tax** joins the side menu after Books and Decide; the mockup's menu
    predates it.

**Not done, because neither the API nor the CLI does it:** the ⌘K command
search, an "as of" date picker, pinning a page to Home, a help button, and
editing an account from its details. A density switch (the mockup's
compact rows) is left out as a display choice nobody asked for.

**Against compose.** The run's selectors follow the shell (Sign out under
who is signed in, the key figures, the pager's count); all fourteen pass
against the image this change builds, the real step-up among them.
