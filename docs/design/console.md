# The Salli console: your books in a browser

Status: **approved (2026-10-12); C0, the server groundwork, and C1, the
console's foundations and Home, built.** The owner accepted every
recommended decision below. C2, C3 and C4 are next (C3 first if one at a
time). Each sub-phase is its own PR. What C0 and C1 built, and where they
depart from the text above, is in [As built (C0)](#as-built-c0) and
[As built (C1)](#as-built-c1).

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
later: C5 more pages · C6 the sign-in methods seam (with the closed edition) · chat, members
```

| Sub-phase | What | Depends on | Can run beside |
|---|---|---|---|
| **C0** Server groundwork | `salli-console` client and computed redirect; `/console` serving with its headers and settings; `console_url` in meta; grant ids, reuse detection, absolute lifetime, `authenticated_at` and step-up; the sign-ins routes and `salli sign-ins`; `Cache-Control: no-store` on the API; money fields as strings; the consent page in the brand, reading "Sign in to Salli" for the console; `salli ui`; the guard extensions; rewording the findings above. | nothing | nothing |
| **C1** Console foundations | The package, tokens, fonts, the kit (`<Money>`, tables, layout, forms, chart primitives), sign-in and sign-out, errors as problem details, `createConsole` with a test extension, the Dockerfile stage, CI with budget, axe and visual tests. Pages: Home; Settings' profile and sign-ins. | C0 | nothing |
| **C2** Where you stand | Accounts and ledger, Cash, Attention, Financial independence. | C1 | C3, C4 |
| **C3** The decision lab | Baseline, templates, scenarios, compare, principles, journal, reviews. | C1 | C2, C4 |
| **C4** Books, tax and settings | Imports and review, rules; Tax with step-up; the rest of Settings. v1 is complete. | C1 | C2, C3 |
| **C5** Later pages | Budgets and goals, debts, investments, insurance, subscriptions, the advisor, bank connections. | v1 | |
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
