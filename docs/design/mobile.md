# The Salli app: your books on a phone

Status: **in development (October 2026).** M0, the server's sign-in for the
app, M1, the app's first screens (finding a server, signing in, Home from
the server's figures, signing out), M2, the four places (Cash, Books
with an account and an entry, adding an entry, Decide's reviews), and
servers and this phone (more than one server, Face ID, the app-switcher
cover) are built ([packages/mobile](../../packages/mobile/README.md)).
Reviewing an import and Android come next.

## Why

The console already lays itself out for a phone, so the app has to earn its
place beyond it:

- **It stays signed in.** A console sign-in ends 12 hours after the password,
  or after 30 minutes without a click. The app signs in once on each phone and
  opens with Face ID or the phone's own unlock.
- **It adds in seconds.** Type "lunch 12.50 checking", check the draft and
  book it, without opening a browser.
- **It takes a statement from the bank's app,** through the phone's share
  sheet, straight into the review queue.
- **It holds more than one server:** your own books and a household member's
  side business, or a managed server later, side by side.
- **Digests could reach the phone** (planned: they need a push notifier,
  below).

Like the CLI and the console, it is a client of the API. It computes nothing,
does no arithmetic on money, adds no feature the API lacks and ranks nothing.
Every figure on screen is the server's, with the date it was true.

## Decisions

| | Decided |
|---|---|
| **Where** | `packages/mobile` in this repository, in the npm workspace, so it uses the SDK, the brand's tokens and the guards as the console does. |
| **Licence** | AGPL-3.0-only, as the console and the server. The SDK stays Apache-2.0. |
| **Identity** | Bundle and application id `money.salli.app`, the reverse of salli.money. |
| **Stack** | Expo (React Native), TypeScript. One codebase for iOS and Android. |
| **Places** | The console's phone bar, unchanged: Home, Cash, Decide, Books, More. Adding an entry is the + on Home and the first action in Books. |
| **Look** | The brand README, as the console builds it: paper bars, a bone work area, paper cards with a hairline, square corners. On night, night with deep-green cards. |
| **Touch** | Buttons and rows 48 px; nothing answers to less than 48 × 48. Text follows the phone's text size; rows grow rather than clip. |
| **Motion** | Energy 1, rhythm 1, motion 1: sheets and fades of 120–200 ms, none with Reduce Motion. |
| **Discretion** | No amounts in widgets or the app switcher unless the person asks. Digests never carry one. |

## What stays with the console and the CLI

Activating tax rules, drafting them, personal access tokens, categorisation
rules, connecting a bank (`salli banks`) and members (`salli-server members`).
The app shows them where it has a page for them, and doesn't change them.

## Signing in (M0, built)

The app signs in as Salli's third first-party OAuth client, `salli-mobile`,
seeded by `core_0022_mobile_client`:

- **The flow:** the authorization code with PKCE (S256) on Salli's own sign-in
  page, opened in the phone's secure browser sheet (`ASWebAuthenticationSession`
  on iOS, Custom Tabs on Android). The page reads "Sign in to Salli" with one
  button, as for the console. The app never sees the password.
- **The redirect:** one, stored and matched exactly:
  `money.salli.app:/oauth/callback`. It is a private-use URI scheme, the
  form RFC 8252 (section 7.1) gives native apps. A loopback redirect, as the
  CLI uses, isn't available on a phone, and a self-registered client
  (RFC 7591) may use only `http` and `https` redirects and is never first party.
- **The API only,** never MCP, and never by device code.
- **HTTPS, or localhost:** the console's rule. A password crosses a network
  only encrypted; a simulator reaches the developer's server at localhost.
- **No absolute end:** a sign-in on a phone lasts while its refresh token
  keeps rotating (30 days each). It ends as any grant does: signing out, ending
  it in the sign-ins list, or a rotated refresh token presented twice.
- **`tax:activate` only within 300 seconds of the password,** as the console's.
  The app doesn't activate rules; the limit keeps it from holding the power.
- **Found through `/v1/meta`:** `oauth.mobile_client_id` and
  `oauth.mobile_redirect_uri`, beside the CLI's and the console's.
- **Listed** in `GET /v1/auth/sign-ins` as `mobile` ("Salli app").

## Still needed in core

| What | Why |
|---|---|
| **A push notifier and a relay** | Apple's and Google's push keys belong to whoever publishes the app, so a self-hosted server can't push to it directly. It needs a notifier extension that keeps device tokens in its own tables, and a relay run by the publisher. The digest already carries no amounts. Core allows one notifier per deployment, so push can't sit beside email until that changes. |
| **Where an entry came from** | An entry keeps only its source (`manual`). Showing which app and which model drafted it, and what was typed, needs the parse note, the client and the model kept on the entry. |
| **The rule behind a draft** | `POST /v1/entries/parse` works out which rule booked a draft, but `ParsedEntryDraft` drops it. |
| **Pairing by a code** | `salli ui --qr`, or a console page showing a code to scan, so a phone needs no typed address. |

## Built with M1

- **Money under Hermes.** React Native's engine has an `Intl.NumberFormat`
  that refuses `signDisplay: 'negative'` and reads a decimal string as a
  float. The SDK now checks once whether the runtime formats a decimal
  string exactly (`intlFormatsExactly`) and, where it doesn't, writes the
  digits itself, taking only the locale's marks from Intl. Its tests run
  every case both ways against Node's exact Intl.

## Built with M2

- **Cash:** the next 60 days from `insights.forecast` as a step line, its
  lowest day marked and zero drawn only when the line reaches it; what's
  coming up, and each cash account's lowest. `src/lib/chart.ts` is the one
  place an amount becomes a number, for pixels, under the console's lint
  escape.
- **Books:** accounts by type with the trial balance's balances; an
  account's entries newest first with the running balance; an entry's
  lines, where it came from, and reversing it after a confirmation (an
  entry is never edited).
- **Adding an entry:** said in a line and drafted by the server's model
  (`entries.parse`; without a model, a 503, the fields are filled by hand),
  then checked and booked. The draft is shown in plain words before
  booking; the app adds nothing to it.
- **Decide:** the reviews due, each with what the chosen option projected
  against what happened, and a reflection to record. Templates and
  scenarios stay in the console.

## Servers and this phone

- **More than one server.** Each sign-in is its own keychain item
  (`salli.sign-in.` and the server's address, escaped to the characters a
  key takes); an index beside them (`salli.servers`, no secret in it) lists
  them and the one on screen. Home's server name opens the list; adding one
  goes through the same check and sign-in page. Reads are cached by server,
  so switching shows nothing of the other. Signing out ends the one on
  screen and shows the next; a sign-in the server ends is dropped from the
  phone and said once on Home. The one sign-in an earlier version kept is
  moved into the index on launch.
- **Face ID, or the phone's unlock.** Off until the person turns it on in
  More, which asks to unlock first. On, the app asks when it opens and after
  a minute in the background. A phone with no passcode can't turn it on.
- **The app switcher shows a cover,** the wordmark on the bar's colour,
  whenever the app isn't active, unless the person turns on showing amounts.
  Nothing is locked or covered while signed out.
- These settings stay on the phone (`salli.phone`), and no server sees them.

## Later

Managed servers need no closed code in the app: one is another server, found
through its `/v1/meta` and signed in to on its own page.
