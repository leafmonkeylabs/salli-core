# The books

How Salli keeps the ledger an accountant would sign: where the books start,
how currencies balance, reconciling with the bank, imports, and how long
documents are kept. Every figure here is computed by Salli; nothing is
guessed.

## Where the books start

The profile's `books_start` (`salli profile set --books-start 2031-01-01`,
`PATCH /v1/onboarding/profile`) is the day the books start. Opening balances
(`POST /v1/onboarding/balance-sheet`) are posted on it, converted at that
day's rate; declaring them without one starts the books today and says so on
the profile. It can be no later than the first entry already booked. A report
for a time before it (the balance sheet as of an earlier day, an income
statement from an earlier day) says in its `notes` that the books don't
cover it.

## More than one currency

Every posting carries its value in the base currency, rounded to the base
currency's minor units as the ledger stores it, and every entry balances
exactly in those units (the database checks it at commit). Rounding each
posting can leave an entry a unit or so out; Salli posts that difference, at
most one minor unit a posting, to the `fx_rounding` account (an expense
account in the base currency, opened the first time one is needed). A larger
difference is an entry that doesn't balance, and is refused.

### Unrealised exchange gains and losses

An asset or liability account held in another currency is worth its balance
at the day's rate; it cost the base amounts its postings were booked at. The
difference is an unrealised gain (or loss), **computed, never posted** unless
you ask:

- `GET /v1/ledger/unrealised-fx?as_of=…` (`salli ledger unrealised-fx`): each
  account's balance, cost, value and gain, the total, what is already posted
  and what isn't. The balance sheet (`as_of`, default today) carries it as
  `unrealised_fx`; the income statement carries the change in what is not
  posted over its period, outside its totals.
- `POST /v1/ledger/fx-revaluation` (`salli ledger revalue 2031-03-31`), at a
  month's last day before today: posts what isn't posted yet to the
  `unrealised_fx` income account against the `fx_revaluation` equity
  adjustment. The foreign-currency accounts keep their own amounts, and net
  worth (which already counts them at the day's rate) doesn't move.

## Reconciling with the bank

A statement to reconcile is one of an asset or liability account, for a
period, with the bank's opening and closing balance, in the account's
currency and its normal direction (held for an asset, owed for a card). An
MT940 or camt.053 import carries them and becomes one; any other statement is
typed in (`salli reconcile add`, `POST /v1/reconciliation/statements`).

You clear the account's postings in the period that the statement shows
(`salli reconcile clear`). The cleared total is the opening balance plus the
cleared postings; the difference is the closing balance less that. A
reconciliation completes (`salli reconcile complete`) only at a difference of
zero, recording who completed it and when; its postings then stay as they
are. Clearing is the one change a posting in closed books still takes
(core_0038). An AI reads the state with `get_reconciliation`.

## Imports

- **Bank formats.** Salli works out most statement layouts itself. When it
  can't, or to be certain, a bank's layout can be written down as a
  `salli.bankformat/1` JSON document and given with the import (`salli import
  statement.csv --format bank.json`, or `--format <directory>` to try every
  format in it; the `formats` form field of `POST /v1/statements/upload`).
  It states the columns (by header or 0-based position: `date`,
  `description`, and `amount`, or `debit` and `credit`, or `amount` with a
  `direction` column; `currency`, `reference`), `date_format` (strptime) or
  `date_order`, `decimal_separator`, `thousands_separator`, `delimiter` and
  `invert_sign`; `sources`, `verified` and `notes` are for the people who keep
  it. It applies to CSV files and to the tables of PDF and Excel statements.
  With several formats, each is tried and the one that reads the most rows
  is used; the result's `formats` says, for each, how many rows it read and
  how many it could not, and which was used. Market packs keep their banks'
  formats in `markets/<country>/banks/`.
- **The bank's base amount.** A row may carry its amount in your base
  currency as the bank gave it (`base_amount`, on a drafted transaction or a
  feed's row): the rate posted is derived from it (source `bank`) rather than
  looked up.
- **Splits.** A transaction for several things is split across accounts in
  review (`splits` on `POST /v1/statements/categorize`, `salli statements
  categorize <id> --split groceries:20 --split household:12.50`): two parts or
  more, each with its own category and need, adding up to the transaction's
  amount. It posts as one entry.

## Documents

Choose how many years a document is kept (`salli profile set
--retention-years 7`); each document saved from then on carries
`retain_until`, and can't be deleted before it. A document an entry cites as
its evidence (a receipt) can't be deleted while it has no retention period
that has passed. There is none by default.

## Plain-text exports

`GET /v1/exports/beancount` and `/hledger` write the ledger for Beancount and
hledger; CI checks both with `bean-check` and `hledger check`.
