# The Salli app: your books on a phone

Status: **in development (October 2026).** M0, the server's sign-in for the
app, M1, the app's first screens (finding a server, signing in, Home from
the server's figures, signing out), M2, the four places (Cash, Books
with an account and an entry, adding an entry, Decide's reviews), and
servers and this phone (more than one server, Face ID, the app-switcher
cover), importing a statement and reviewing it, and Home when the server
is out of reach are built ([packages/mobile](../../packages/mobile/README.md)).
A statement shared from another app, and Android, come next.

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
| **Motion** | Calm and short, on the UI thread; opacity only with Reduce Motion. See [Motion](#motion). |
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
- **The API as the person, and MCP for the AI** the person sets up in the app
  (More → Your AI): a second sign-in on a page that asks to connect it by name
  (design 19), then an AI connection like any other: listed and ended with
  the others, and under the MCP switch. Never by device code.
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
  (`entries.parse`), shown as the entry it would book: its description,
  a plain sentence, the debit and credit lines with each account
  changeable in place, and a Total. "Enter it exactly instead" opens the
  hand-filled form, as does a server with no model (a 503). The app adds
  nothing to a draft. Entry draws its lines with the same table
  (`LinesTable`); as in the console, a Total shows only when each side is
  one line in one currency, so it is that line's amount, never a sum.
- **Decide:** the reviews due, each with what the chosen option projected
  against what happened, and a reflection to record. Templates and
  scenarios stay in the console.

## Household basics (built)

Designs HhAddDate, HhRecategorise, HhObOwe, HhDebts, HhBudget, HhBudgetEdit
and HhPush. Add's draft carries its day, picked in a sheet (no day after
today). An entry's category moves through `POST
/v1/entries/{id}/recategorise`, never an edit. First run's owe lines send
`rate` (typed in percent, sent as a fraction by moving the point) and
`minimum_payment`. Debts reads `GET /v1/baseline` (its total and each
debt's `paid_off`), Budget `GET /v1/budget/current` and `/trend`, its edit
`PUT /v1/budget/monthly` with every line. Notifications registers the
phone with `POST /v1/devices` and keeps the device id in the keychain; the
alerts' kinds and quiet hours are the server's, not chosen here yet. The
trend's bars are sized from each month's categories (pixel geometry); no
total is shown, since the app adds no money.

## Servers and this phone

- **Where the books live.** The first screen (and Add a server) offers
  Salli's server, by invitation during the pilot, or your own. An invitation
  link (`https://<host>/join?t=…`, from `salli-server members invite`) is
  pasted; its page opens in the secure browser sheet, where the person sets
  a password and two-step code, and the app then signs in to that host as to
  any other. A link opened outside the app opens the browser instead: a
  universal link would need every server to vouch for the app.
- **More than one server.** Each sign-in is its own keychain item
  (`salli.sign-in.` and the server's address, escaped to the characters a
  key takes); an index beside them (`salli.servers`, no secret in it) lists
  them and the one on screen. Home's server name opens the list; adding one
  goes through the same check and sign-in page. Reads are cached by server,
  so switching shows nothing of the other. Signing out ends the one on
  screen and shows the next; a sign-in the server ends is said once on
  Home. A server signed out of stays listed with only its address and who
  you are on it (your email and its currency, from `auth.me` and the
  profile; never a figure, never a token), to sign in to again in one tap,
  until you choose Forget it. The one sign-in an earlier version kept is
  moved into the index on launch.
- **Face ID, or the phone's unlock.** Off until the person turns it on in
  More, which asks to unlock first. On, the app asks when it opens and after
  a minute in the background. A phone with no passcode can't turn it on.
- **The app switcher shows a cover,** the wordmark on the bar's colour,
  whenever the app isn't active, unless the person turns on showing amounts.
  Nothing is locked or covered while signed out.
- These settings stay on the phone (`salli.phone`), and no server sees them.
- **More** lists the console's places (Tax, Attention, Independence,
  Settings: each opens the console's page until the app has it) and then
  **Servers and sign-in**: the servers, this phone's lock and discretion,
  and this sign-in with when it started (`auth.signIns.list`). Its
  switches are the kit's square `Toggle`, as the design draws them.

## Importing a statement

- **From the phone's files:** Books' "Import a file" chooses a statement
  (expo-document-picker) and the account it is for, and uploads it as it
  is (`statements.upload`); the server reads it, as it does for the console
  and `salli import`. The phone's fetch sends a file part only as
  expo-file-system's `File`, so the app builds that one form itself.
- **The review queue** in Books lists the statements waiting; Home's "review
  waiting" signal opens Books. A statement's review shows each transaction
  as Salli read it, in date order, with where the money came from or went:
  a rule's or the model's proposal (and how sure the model was), or a
  "Choose an account" that is kept at once (`statements.categorize`). A
  likely duplicate is said, to leave out or book anyway. "Post the N
  ready" posts what is complete after a confirmation (`statements.post`);
  "Discard all" and leaving one out ask first (`statements.discard`).
  Nothing is booked until posted, and nothing twice.
- **Not yet:** a statement shared to Salli from a bank's app (a share
  extension) and making a rule from a transaction (the console has both).

## When the server is out of reach

- **How the app knows:** from the reads it already makes, never a probe of
  its own (`useReach` in `src/api.tsx`). A server is out of reach when its
  latest read failed for want of an answer (`SalliNetworkError`, a timeout
  among them) after its last answer; an answer that refuses is still an
  answer. A read gives up after 12 seconds (an upload sets its own) and is
  tried once more, and a stale read runs again when the app comes back to
  the screen.
- **Home** says "Can't reach money.example.org", with the time it last
  answered when it did, keeps the figures it last sent marked "As of …,
  not since", says "Not known" where nothing came back (never "Nothing
  needs attention"), and turns off what writes (+ and Done) until it
  answers. "Try again" and pulling down read everything on screen again.
- **Every other place** shows why a read failed and "Try again", never a
  "Loading…" that waits forever (`Waiting` in `src/kit.tsx`).
- Nothing is kept on the phone between launches: the figures shown are the
  ones read since the app opened, as everywhere else. The widgets' snapshot
  (below) is the one exception, and it holds no figure unless asked.

## Widgets

Design 15's lock screen: two widgets, **Safe to spend** and **Waiting**, as
paper tiles on the Home Screen (`systemSmall`) and as the system tints them on
the lock screen (`accessoryRectangular`), where iOS draws no paper.
**Privacy mode:** on the lock screen Safe to spend masks its amount (`••••`)
and keeps only its label and date; the amount is in the app and on the Home
Screen tile.

- **What they show comes from the app.** After each read, the app writes a
  small snapshot to the app group `group.money.salli.app` (`src/glance.tsx`,
  worded by `glanceOf` in `src/lib/glance.ts` from the catalogue's `glance`
  words) and asks WidgetKit to draw again. The widget asks no server and
  holds no token; its only words of its own are the gallery's and "Open
  Salli", for a widget placed before the app has written anything.
- **Discretion.** Safe to spend says "Amount hidden" unless the person turned
  on Show amounts outside the app; then the figure and its currency. Waiting
  counts decisions to review, reminders due (today or before; a decision's
  own reminder counts once, as the decision), statements to review and cash
  below zero ahead (the `low_balance_ahead` signal at `high`), worded without
  a name, a question, a date or an amount. Two lines show, then "and 2 more".
- **Never stale.** A day after its newest read, each tile says "Open Salli to
  see what is current" instead of figures that may be wrong. Signing out of
  every server removes the snapshot. With several servers, it is the one on
  screen's, and Waiting names its host.
- **Built** with `@bacons/apple-targets`: the target is `targets/widget`
  (SwiftUI, Geist from its own copy under the OFL), added to the Xcode
  project at prebuild, its colours from `expo-target.config.js`. Android has
  no widgets yet.

## Automations (planned)

A bank's text message or email becomes a transaction waiting for review,
without anyone typing it. iOS lets no app read messages or mail; a Shortcuts
automation ("when I get a message from EXAMPLEBANK", "when I get an email from
alerts@bank.example") hands the text to an action of Salli's instead.

- **The app's actions** (App Intents): draft an entry from text, import a
  statement (a PDF or CSV attachment), add an expense, and safe to spend
  (read only, amount hidden unless amounts outside the app are on).
- **Matching rules stay on the phone:** a sender and a pattern that picks out
  the amount as written, the date, the payee and the bank's reference, and
  the account it is on. A message no rule matches is dropped at once and
  never leaves the phone: one-time codes and personal texts stay there. One
  from a watched sender that fits no pattern is read by the in-app agent's
  model, when one is set up, and waits for the person otherwise.
- **Drafts wait in core's review queue** (`POST /v1/statements/drafts`,
  `salli statements draft`): one batch per account while any of it waits,
  sorted by the person's rules and checked for duplicates as an import is.
  Only what the rule picked out is sent, never the message. The same
  message handled twice books once; when the month's statement brings the
  same transaction, it is flagged as a possible duplicate of the draft.
- Android, later: a notification listener (Play lets only the default SMS
  app read messages).
- **Built so far:** More → Automations lists the rules of the server on
  screen (kept in the keychain under that server, and forgotten with it) and
  drafts a pasted message on a tap. The editor tries the pattern on a sample
  as it is written. A template marks `{amount}`, `{payee}`, `{date}`, `{ref}`
  and `{skip}`; Advanced takes a regular expression with named groups, the
  date order and the decimal mark. Amounts are read as written and refused
  when ambiguous ("1,245.50" with a comma mark), never guessed
  (`src/lib/automations.ts`).
- **The Shortcuts action** "Draft from a bank's message" (`targets/intents`,
  an App Intents extension) only adds the message and its sender to a queue
  in the app group and returns; it sends nothing and reads no rule. Salli
  reads the queue with the rules of the server on screen when it opens, when
  it comes back to the screen, and when iOS gives it background time
  (`src/inbox.tsx`, `expo-background-task`). Every run goes through the
  signed-in session's own client: a background run with no app running
  waits, rather than refresh the sign-in a second way (a refresh token used
  twice ends the sign-in). Drafts go by account; one that can't be sent
  stays queued. A message no rule watches is dropped at once.
- **Not read:** a message from a watched sender that no pattern fits waits
  on the Automations page, in the keychain under its server (50 at most),
  to make a rule from or let go; each run reads them again, so a new rule
  picks them up.

## Your AI

An AI the person chooses, on their own key, that reads their books through
Salli's tools and asks before any change (designs 18 to 21). It lives only in
the app: core holds no key and runs no model for it.

- **Providers:** Anthropic, OpenAI, xAI, Meta (the Llama API) and OpenRouter,
  through the AI SDK (`ai`, `@ai-sdk/*`); the model is chosen from the
  provider's own list for the key. Keys are kept in the keychain, one per
  provider, and sent only to that provider.
- **Salli's tools** come from the server's MCP, on a sign-in of the AI's own
  (core: `salli-mobile` may ask for the MCP resource). The server's page asks
  "Connect the AI in the Salli app?" (design 19); the connection is then an
  AI connection like any other, ended from the app (Disconnect) or the
  console, and refused while MCP is off.
- **Instructions are core's:** each turn starts from the `talk_with_me` MCP
  prompt, which ends with Salli's guardrails (never compute, never rank,
  never name products), so the app holds no words of its own for the model.
- **Changes wait for the person:** a tool that only reads runs as the model
  asks (`readsOf` in `src/lib/ai.ts`: those the server's tool list marks
  `readOnlyHint`); any other, and any tool the server doesn't mark, shows
  on a card with Approve and Not now (design 21), and the conversation
  waits on it.
- **What leaves the phone:** the questions and what the tools return go to
  the chosen provider; the settings page says so in one line.
- **Conversations:** the last 20 per server, in a file of the app's own,
  never sent; deleted from Your AI, or with the server when it is forgotten.
- **Where it opens:** a square button floating above the bar on Home, Cash,
  Decide and Books (design 22), which opens the AI's page with three
  starters for that tab; before an AI is set up it opens More → Your AI.
  Each of those tabs leaves room below its last card so the button never
  covers it. Kept conversations open from More → Your AI. The page has no
  heading on screen; Back names the tab it came from.

## Motion

Built with Reanimated, gesture-handler and expo-haptics; the tokens are in
`packages/mobile/src/motion.ts`, and the app runs at 120 Hz where the phone
can (`CADisableMinimumFrameDurationOnPhone`).

- **Motion explains a change** of state or place; it never decorates.
- **A figure is never shown as a value it isn't:** no counting up, no
  rolling digits. An amount that changes cross-fades.
- **Things move to and from where they come from:** a sheet from the bottom
  edge, a row out of its own place in the list.
- **Calm and short:** 120–240 ms, critically damped springs, no bounce.
- **Nothing loops or invites:** no pulse, shimmer or celebration.
- **Reduce Motion is opacity only**, never no feedback at all.
- **On the UI thread, interruptible:** a gesture always wins over an
  animation running.

| Token | Motion | With Reduce Motion |
|---|---|---|
| Press | Scale 0.98 and opacity 0.85, 80 ms in, 120 ms out, ease-out. Unavailable is 0.45 and still, never what a press looks like. | Opacity only |
| Small change of state | 160 ms, cubic-bezier(0.2, 0, 0, 1) | None, or opacity over 100 ms |
| Row in or out of a list | The others settle on a spring (stiffness 400, damping 40, mass 1); a new row fades in over 160 ms, a leaving one out over 120 ms | Opacity over 120 ms, nothing moves |
| Sheet | Rises on a spring (stiffness 500, damping 50, mass 1; about 220 ms) while its scrim fades to 0.4 over 160 ms; leaves in 180 ms, cubic-bezier(0.3, 0, 1, 1), or faster with the drag. Dragged down past 30% of its height, or flicked faster than 800 pt/s, it closes. | Sheet and scrim fade over 150 ms |
| Screen push | The native stack's own | The system's |
| Number change | 140 ms cross-fade, the old out 4 px up, the new in 4 px up; never through the values between | Instant |
| Chart | The line drawn once over 280 ms; new data morphs over 200 ms | Opacity over 150 ms |
| Confirmation | Fades and rises 8 px over 200 ms, then holds | Opacity over 150 ms |
| Loading to content | 160 ms cross-fade, no shimmer | Instant |

**Haptics.** Booking an entry is the one success (`notificationAsync`
Success); a reversal booked is a Warning; marking a reminder done is a light
impact; a sheet's drag crossing its closing point, and picking a chip, date
or option, are a selection tick. Never for loading, refreshing, a tab,
an amount, a chart, an error reading, scrolling or anything repeating.
They follow the phone's own System Haptics switch.

**VoiceOver.** A sheet starts at its title (`SheetTitle`); after booking,
the confirmation; a reminder marked done is announced as it leaves, and
again if the server refuses it and it comes back.

Built: the sheet, the press, Home's and Attention's rows (marking done
removes the row at once and puts it back if the server refuses), booking's
confirmation. Still to do: Home's placeholders cross-fading to their
figures, the figure cross-fade, the chart's reveal, first run's steps and
the selection tick on chips and pickers.

## Later

Managed servers need no closed code in the app: one is another server, found
through its `/v1/meta` and signed in to on its own page.
