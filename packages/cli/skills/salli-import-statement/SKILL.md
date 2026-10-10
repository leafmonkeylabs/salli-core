---
name: salli-import-statement
description: Import a bank or card statement (OFX/QFX, QIF, camt.053, MT940, CSV, PDF or XLSX) into the user's Salli ledger, review the extracted transactions with them, and post the approved ones. Use when the user shares a statement file or says "add this month's statement".
---

# Importing a statement

Read the `salli-cli` skill first.

## 1. Parse

    salli parse upload <path/to/statement.pdf> --account <account code> --bank "<bank name>" --json

`--account` is the bank, cash or card account the statement is for (find it
with `salli accounts list --json`); ask the user if it isn't clear. It is the
money side of every transaction, so only the other side has to be decided.
Nothing is posted yet.

Salli tells the format from the file itself. Rows are in the currency the file
names; a file that names none (QIF, most CSVs) is in the account's currency.
A row in another currency than the account's is skipped.

Each row is then:

- checked against earlier imports and the ledger. `exact_duplicate` repeats
  an earlier import (`duplicate_of` is that transaction) and is never posted;
  `fuzzy_match` looks like an entry already booked, by hand perhaps
  (`duplicate_of` is the entry): ask the user before posting it.
- decided by the user's rules where one matches (`rule_id` says which),
- and otherwise given an account by the AI, which needs an API key. Without
  one, those rows come back with no account.

Tell the user about anything in `errors`: rows Salli skipped, how many still
need an account, and guesses such as reading 01/02/2026 as day first. If a
date order was guessed wrong, parse the file again with `--date-order DMY`,
`MDY` or `YMD` and `--replaces <statement_id>`: the earlier import's rows are
then not taken for duplicates, and those still in review are discarded.

A file holding several accounts (a QIF with a card register, an OFX with two
statements) is imported one account at a time. If `errors` lists the file's
accounts, ask the user which one this statement's `--account` is, and parse
again with `--source-account "<the file's account>"`; then once more for each
other account they want, with its own `--account`.

## 2. Review with the user

    salli parse pending <statement_id> --json

Each transaction has the API's fields: `description` is the bank's text and
`description_override` what it will be booked as, if set. Present them as a
short table: date, description (and the override), amount, the other
account, and `dedup_status`. Ask the user which to post. Point out
`fuzzy_match` rows (they look like something already booked or imported:
`duplicate_of` says what), rows with no account yet, and anything whose
account looks wrong. Exact duplicates of an earlier import are not listed
here: the upload's result counted them, and they are never posted. Don't
post anything they haven't approved.

Rows the user says are not real (a duplicate, a card authorisation that never
went through) are discarded, so they leave review for good:

    salli parse discard <statement_id> <id> <id> ... --json

## 3. Post the approved ones

    salli parse post <id> <id> ... --json

Then confirm what was posted: the result lists an entry id for each one. A
row with no account yet is not posted; say which. If they want to recategorise one after posting,
use `salli entry reverse` and post it again (see `salli-record-transaction`).
If the user keeps correcting the same kind of transaction, suggest a rule
(`salli rules suggest --json`).

## Afterwards

Suggest `salli reminders sync-alerts --json` to refresh budget and
subscription alerts now that new spending is in.
