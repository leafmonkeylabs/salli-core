---
name: salli-import-statement
description: Import a bank or card statement (PDF, XLSX or CSV) into the user's Salli ledger, review the extracted transactions with them, and post the approved ones. Use when the user shares a statement file or says "add this month's statement".
---

# Importing a statement

Read the `salli-cli` skill first.

## 1. Parse

    salli parse upload <path/to/statement.pdf> --bank "<bank name>" --json

Salli extracts the rows, flags likely duplicates of entries already in the
ledger, and suggests an account for each (an AI step; needs an API key).
Nothing is posted yet.

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
