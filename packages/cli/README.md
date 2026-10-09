# salli

Your money from the terminal: the command line for [Salli](../../README.md),
the open-source personal finance platform. Your ledger, budgets, debts,
investments, insurance, tax and financial-independence planning, and an AI
that explains it all, in tables made for reading and JSON made for scripts.

> **Beta.** `salli` is a client of a running Salli server, over HTTP. Start one
> with `uv run salli serve` (see the [quickstart](../../README.md#quickstart-about-10-minutes)),
> or point it at a server someone runs for you. It speaks Salli's API version 1.

```console
$ salli status
Salli · home · http://localhost:8000

Net worth       USD 14,034.50
  Assets        USD 15,234.50
  Liabilities   USD  1,200.00

October 2026 so far (Oct 1 – 9, 2026)
  Net income    USD 2,787.65
  Income        Salary 5,000.00
  Spending      Rent 1,800.00 · Groceries 412.35

FI score        72.5 (B) · 1.9% of the way to financial independence
  Savings rate  55.8% of income
  FI by         Oct 9, 2040

Coming up
! Oct 9, 2026   Budget overspend            warning
  Nov 30, 2026  Return due 2025/26
```

It never does arithmetic on money. Amounts arrive from the server as exact
decimal strings, each with its currency, and are formatted for display
without passing through a floating-point number: totals, balances and
conversions are the server's.

## Install

With Node.js 22.12 or later:

```bash
npm install --global @leafmonkeylabs/salli
salli --version
```

Or a standalone executable, with nothing else to install, from a release:
`salli-darwin-arm64`, `salli-darwin-x64`, `salli-linux-x64`, `salli-linux-arm64`
or `salli-windows-x64.exe`. Check it against `SHA256SUMS`, make it executable,
and put it on your `PATH`:

```bash
shasum -a 256 -c SHA256SUMS --ignore-missing
chmod +x salli-darwin-arm64 && mv salli-darwin-arm64 /usr/local/bin/salli
```

To build them yourself (needs [Bun](https://bun.sh) 1.3): `npm run build`, then
`npm run binaries` (every platform) or `npm run binaries -- --host`.

## Sign in

```bash
salli login                                  # http://localhost:8000, in your browser
salli login --server https://salli.example.com
salli login --device                         # no browser here: approve on another device
salli login --token -  < token.txt           # a personal access token, from stdin
salli whoami
salli logout
```

`salli login` reads the server's sign-in endpoints from `/v1/meta`, registers
itself once (the client id is kept in the context), and signs in with OAuth 2.1:
the authorization code flow with PKCE, your browser coming back to a one-off
listener on `127.0.0.1`. `--device` uses the device authorization grant instead:
open the link it prints, on any device, and enter the code. `--no-browser` prints
the link without opening it.

Tokens are kept in your system keychain (macOS Keychain, Windows Credential
Manager, the Secret Service on Linux) and refreshed when they expire. Where there
is no keychain, they go to `credentials.json` next to the config, readable only by
you, and `salli` says so once. `SALLI_CREDENTIAL_STORE=keyring|command|file`
chooses: `command` uses the OS's own tool (`security` on macOS, `secret-tool` on
Linux), which is what a standalone binary for another platform falls back to.

`SALLI_TOKEN` overrides whatever is stored, for CI and scripts. A stored token is
only ever sent to the server that issued it.

## Contexts

Like kubectl's, a context names a server; one is current, and each has its own
sign-in.

```bash
salli context add work https://salli.example.com
salli context list
salli context use work
salli --context home status          # one command, another context
salli context current
salli context remove work            # and sign out of it
```

`--server <url>` and `SALLI_SERVER` override the current context's server;
`--context <name>` and `SALLI_CONTEXT` pick another context. The configuration
lives in `$XDG_CONFIG_HOME/salli/config.json` (`~/.config/salli` on Linux and
macOS, `%APPDATA%\salli` on Windows; `SALLI_CONFIG_DIR` moves it).

## Using it

| You want to… | Run |
|---|---|
| See where you stand | `salli status` |
| Record a transaction, in your words | `salli add "lunch 12.50 cash"` |
| Record one exactly | `salli entries add --desc Lunch --debit groceries:12.50 --credit cash:12.50` |
| Correct one | `salli entries reverse <id>`, then add the right one |
| Import a bank statement | `salli import september.pdf` |
| See accounts and balances | `salli accounts list --balances`, `salli accounts show checking` |
| Reports | `salli ledger income-statement --month 2026-09`, `salli reports balance-sheet` |
| Ask the AI | `salli ask "how much did I spend on groceries?"`, or `salli chat` |
| Budgets, debts, investments | `salli budgets summary <id>`, `salli debts payoff-plan`, `salli portfolio` |
| Financial independence | `salli fi score`, `salli fi afford 2400 --months 12` |
| Tax | `salli tax compute` |
| Everything else | `salli --help`, and `--help` on any command |

Accounts are named by code (`1000`), name (`Cash`, or any unique start of it) or
id. Every other id can be shortened to a unique prefix: lists show the first eight
characters.

`salli add` asks the AI to draft an entry from your sentence, shows you the draft,
and lets you post it, change an account, the amount, the description or the date,
or cancel. It posts nothing you have not seen unless you pass `--yes`.
`salli import` reads a statement on the server and walks you through each
transaction (approve, skip, change an account); duplicates of what is already in
your ledger are skipped. With `--yes` it posts only what is unique and has both
accounts, and leaves the rest pending for `salli statements pending`.

`salli chat` streams the AI's reply as it is written and shows the tools and
specialists it uses. Before the AI changes anything it says what and asks; nothing
is written unless you approve. `salli ask` asks once; without a terminal to ask in,
a change it proposes is declined.

## The output contract

Data goes to stdout, everything else to stderr: progress, confirmations,
warnings and errors. stdout is only ever the result.

| `--output` (`-o`) | Prints |
|---|---|
| `table` (default) | Tables and summaries for people. Colour in a terminal only. |
| `json` (`--json`) | The API's JSON, exactly as the server sent it (re-indented; numbers keep their text). |
| `ndjson` | One JSON value per line: each record of a list, or the result. `ask` streams the agent's events. |
| `csv` | The records, a row each, fields as columns, quoted per RFC 4180. |

A few commands combine several API calls and print one object holding each
response (`status`, `entries show`). An operation with no content (`delete`,
`deactivate`) prints a small object saying what was done. Client-side filters
(`--type`, `--search`, `--limit`) narrow the list the API returned. Make a format
your default with `salli config set output json`.

Errors are [RFC 9457 problem details](https://www.rfc-editor.org/rfc/rfc9457) from
the server, shown as one line:

```console
$ salli entries add --desc Paris --currency EUR --debit groceries:10 --credit cash:10
✗ No exchange rate: No EUR→USD rate for that date. Send the exchange rate (fx_rate) with the amount.
```

With `--json`, the problem goes to stderr as JSON, with the exit code added:

```json
{"type":"/problems/fx-rate-unavailable","title":"No exchange rate","status":422,"detail":"…","exit_code":5}
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | An error: the server failed, or something unexpected |
| 2 | Usage: a bad command, flag or argument |
| 3 | Not signed in, or the session expired (`salli login`) |
| 4 | Not found |
| 5 | The server refused the request: validation, a conflict (a 4xx with problem details) |
| 6 | The server speaks an API version this CLI does not |
| 7 | Network: the server could not be reached |
| 130 | Interrupted (Ctrl-C) |

### Colour

Off when `NO_COLOR` is set, with `--no-color`, when output is not a terminal, or
for `TERM=dumb`; on with `FORCE_COLOR`. `salli config set color never|always`
overrides the default.

## Scripting

```bash
# Net worth, as a number to compare in your own tooling
salli reports balance-sheet --json | jq -r '.net_worth'

# Every expense account's code and name
salli accounts list --type expense -o csv

# Post from a script, failing on any refusal
salli entries add --date 2026-10-01 --desc "Rent" \
  --debit rent:1800 --credit checking:1800 --json || echo "refused: exit $?"

# The agent's answer, from its event stream
salli ask "what is my savings rate?" --json | jq -r 'select(.type=="token") | .content' | tr -d '\n'
```

Amounts you pass are exact decimals: `1500`, `1234.50`, or `1,234.50` (commas as
thousands separators only). Rates take a fraction or a percentage: `0.18` or `18%`.

## Settings and environment

| Setting (`salli config set`) | |
|---|---|
| `output` | Default output format: `table`, `json`, `ndjson`, `csv` |
| `color` | `auto` (default), `always`, `never` |
| `locale` | For amounts and dates, e.g. `en-GB`; default: the system's |

| Variable | |
|---|---|
| `SALLI_SERVER` | The server to talk to (overrides the context) |
| `SALLI_TOKEN` | A token to send (overrides the stored sign-in) |
| `SALLI_CONTEXT` | The context to use |
| `SALLI_CONFIG_DIR` | Where the configuration lives |
| `SALLI_CREDENTIAL_STORE` | `keyring`, `command` or `file` |
| `SALLI_LOCALE` | Like the `locale` setting |
| `NO_COLOR`, `FORCE_COLOR` | Colour off, or on |
| `SALLI_DEBUG=1` | Log each request to stderr (also `--verbose`) |

`salli doctor` checks the lot: the server answers, speaks a compatible API
version, accepts your sign-in, and agrees with your clock (tokens expire by it).

## Shell completion

```bash
salli completion bash > ~/.local/share/bash-completion/completions/salli
salli completion zsh > "${fpath[1]}/_salli"
salli completion fish > ~/.config/fish/completions/salli.fish
```

The scripts are generated from the command tree, so they always match the CLI
that printed them.

## Developing

The CLI lives in `packages/cli`, on the SDK in `packages/sdk`
(`@leafmonkeylabs/salli-sdk`), both npm workspaces at the repository root:

```bash
npm install
npm run generate     # regenerate the SDK from openapi/openapi.json
npm run typecheck
npm run lint         # includes the money guard: no Number()/parseFloat() on an amount
npm test             # unit tests, and the real CLI against an in-process mock server
npm run build        # packages/cli/dist/salli.js, one file
node packages/cli/dist/salli.js --help
```

The SDK's operations are generated from the committed OpenAPI document, so a new or
newly typed API operation reaches the CLI by running `npm run generate`. Response
shapes the document does not describe yet are written out in
`src/api-types.ts`, and give way to the generated types automatically once it
does.

## License

[AGPL-3.0-only](../../LICENSE), like the rest of Salli.
