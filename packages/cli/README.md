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
Safe to spend   USD 1,234.56 until Nov 1, 2026, when Salary comes in

October 2026 so far (Oct 1 – 9, 2026)
  Income        USD 5,000.00
  Spending      USD 2,212.35
  Net income    USD 2,787.65
  Most on       Rent 1,800.00 · Groceries 412.35

FI score        72.5 (B) · 1.9% of the way to financial independence
  Savings rate  55.8% of income
  FI by         Oct 9, 2040

Needs attention
  ! Checking runs short on Nov 2
    It is forecast to reach USD -370.00 before payday.

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
npm install --global salli
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
salli login --device                         # approve with a code on another device
salli login --token -  < token.txt           # a personal access token, from stdin
salli whoami
salli logout
```

`salli login` reads the server's sign-in endpoints from `/v1/meta`, registers
itself once (the client id is kept in the context), and signs in with OAuth 2.1:
the authorization code flow with PKCE, your browser coming back to a one-off
listener on `127.0.0.1`. Where no browser can open (over SSH, on a server with
no display) it uses the device authorization grant instead, as `--device` does:
open the link it prints, on any device, and enter the code. `--no-browser` prints
the link without opening it. The tokens are for the server's API (the
`api_resource` it names); a token an AI client got for MCP does not work here.

For scripts, CI and other machines, make a personal access token and sign in
with it there, or set it as `SALLI_TOKEN`:

```bash
salli tokens create "backup job" --expires-in-days 90   # printed once
salli tokens list
salli tokens revoke 3fa85f64
```

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
| Import a bank statement | `salli import september.ofx --account checking` |
| Fetch from your bank instead | `salli banks connect`, `salli banks map …`, `salli banks sync` |
| Book the same payee the same way | `salli rules add Uber --if "description contains uber" --account transport` |
| See accounts and balances | `salli accounts list --balances`, `salli accounts show checking` |
| Reports | `salli ledger income-statement --month 2026-09`, `salli reports balance-sheet` |
| Where it goes, where it is heading | `salli insights spending`, `salli insights forecast`, `salli insights safe-to-spend` |
| Ask the AI | `salli ask "how much did I spend on groceries?"`, or `salli chat` |
| Ask about a document | `salli ask "what is this charge?" --attach receipt.pdf` |
| Budgets, debts | `salli budgets summary <id>`, `salli debts payoff-plan` |
| Investments | `salli portfolio`, `salli portfolio transactions add VTI buy --quantity 10 --price 240`, `salli portfolio performance` |
| Financial independence | `salli fi score`, `salli fi assumptions`, `salli fi afford 2400 --months 12` |
| Tax | `salli tax year`, `salli tax compute`, `salli profile set --tax-residency LK` |
| Choose what powers the AI | `salli ai status`, `salli ai connect chatgpt`, `salli llm-keys set openai` |
| Take your ledger elsewhere | `salli export beancount -o ledger.beancount`, `salli export hledger` |
| Everything Salli keeps about you | `salli profile export` (JSON, readable only by you) |
| Everything else | `salli --help`, and `--help` on any command |

Accounts are named by code (`1000`), name (`Cash`, or any unique start of it) or
id. Every other id can be shortened to a unique prefix: lists show the first eight
characters.

`salli add` asks the AI to draft an entry from your sentence, shows you the draft,
and lets you post it, change an account, the amount, the description or the date,
or cancel. It posts nothing you have not seen unless you pass `--yes`.
`salli import` reads a statement on the server (CSV, OFX/QFX, QIF, camt.053,
MT940, PDF or Excel) into the account you name with `--account`, and walks you
through each transaction: approve it, change where the money came from or went,
skip it, or discard it. Your changes are sent to the server before posting;
transactions imported before are skipped. With `--yes` it posts only what is
complete and not a possible duplicate (`--allow-possible-duplicates` adds those),
and leaves the rest pending for `salli statements pending`, `statements
categorize`, `statements post` and `statements discard`. `--replaces` imports a
statement again on purpose. Bank connections (`salli banks`) queue new
transactions the same way.

Rules book imported transactions before any AI is asked: `--if` takes a
condition (`description contains uber`, `amount between 10 50`, `direction
equals out`, `currency equals USD`; repeat it for more), and `--account`,
`--category`, `--need` and `--rename` say what to do. `salli rules test` shows
what a rule would match among what you have booked, and `salli rules suggest`
the rules your own bookkeeping implies, each with the command that adds it.

`salli ai connect chatgpt` lets Salli's AI use your ChatGPT plan: run it where
your browser is, choose "Continue with ChatGPT", and the sign-in goes straight to
the server, which keeps and renews it. Using the plan counts toward its usage
limits (https://chatgpt.com/settings/usage). Nothing is kept on your computer and
no token is printed. Your own Anthropic or OpenAI key works too (`salli
llm-keys set`), and `salli ai use` chooses between them.

`salli chat` streams the AI's reply as it is written and shows the tools and
specialists it uses. Before the AI changes anything it says what and asks; nothing
is written unless you approve. `salli ask` asks once; without a terminal to ask in,
a change it proposes is declined.

## The output contract

Data goes to stdout, everything else to stderr: progress, confirmations,
warnings and errors. stdout is only ever the result.

| `--output` | Prints |
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
salli accounts list --type expense --output csv

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

[Apache-2.0](LICENSE), like the SDK, so you can script it and build on it freely.
The Salli server it talks to is [AGPL-3.0-only](../../LICENSE).
