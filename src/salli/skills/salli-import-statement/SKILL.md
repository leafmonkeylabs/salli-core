---
name: salli-import-statement
description: Import a bank or card statement (OFX/QFX, QIF, camt.053, MT940, CSV, PDF or XLSX) into the user's Salli ledger, review the extracted transactions with them, and post the approved ones. Use when the user shares a statement file or says "add this month's statement".
---

# Importing a statement

Read the `salli-cli` skill first.

## 1. Parse

    salli parse upload <path/to/statement.pdf> --bank "<bank name>" --json

Salli extracts the rows, flags likely duplicates of entries already in the
ledger, and suggests an account for each (an AI step; needs an API key).
Nothing is posted yet.

Salli tells the format from the file itself. Rows are in the currency the file
names; a file that names none (QIF, most CSVs) is in the user's base currency
unless you pass `--currency <ISO code>`. Tell the user about anything in
`errors`: rows Salli skipped, and guesses such as reading 01/02/2026 as day
first. If a date order was guessed wrong, parse again with
`--date-order DMY`, `MDY` or `YMD`, and from then on work only with the new
statement's transactions (its `statement_id`): the first parse's rows stay
pending, and must not be posted.

## 2. Review with the user

    salli parse pending --json

Present the transactions as a short table: date, description, amount,
suggested account, and whether it looks like a duplicate. Ask the user which
to post. Point out duplicates and anything whose suggested account looks
wrong. Don't post anything they haven't approved.

## 3. Post the approved ones

    salli parse post <id> <id> ... --json

Then confirm what was posted. If they want to recategorise one after posting,
use `salli entry reverse` and post it again (see `salli-record-transaction`).

## Afterwards

Suggest `salli reminders sync-alerts --json` to refresh budget and
subscription alerts now that new spending is in.
