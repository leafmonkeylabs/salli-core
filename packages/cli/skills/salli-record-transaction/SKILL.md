---
name: salli-record-transaction
description: Record a purchase, income, transfer or other transaction in the user's Salli ledger, or correct one already recorded. Use when the user says things like "I spent 2,500 on groceries", "add my salary", "I paid the credit card", or "that entry was wrong".
---

# Recording a transaction

Read the `salli-cli` skill first for the ground rules (`--json`, confirm before
writing, never edit a posted entry).

## 1. Find the accounts

    salli accounts list --json

Every entry moves money between two or more accounts: what increased gets the
**debit**, where the money came from gets the **credit**. Spending 2,500 on
groceries from cash: debit the groceries (expense) account, credit Cash.

If no suitable account exists, propose one and, once the user agrees:

    salli accounts add <code> "<name>" <asset|liability|equity|income|expense> --json

## 2. Draft it

For free text, Salli can draft the entry (an AI feature):

    salli add "groceries 2500 cash yesterday" --dry-run --json

`--dry-run` posts nothing. Use the draft, or build the entry yourself.

## 3. Confirm, then post

Show the user the date, description, and each debit and credit line. On yes:

    salli entries add --date 2026-10-08 --desc "Groceries" \
      --debit groceries:2500 --credit cash:2500 --json

`--debit` and `--credit` take `ACCOUNT:AMOUNT` and repeat to split. Debits
must equal credits. Salli rejects an unbalanced entry; don't work around it,
fix the amounts. An amount in another currency needs `--currency` (and
`--fx-rate` if the user knows the rate their bank used).

## Correcting a mistake

    salli entries show <id> --json          # check what was posted
    salli entries reverse <id> --yes --json # cancels it with an opposite entry

Then post the correct entry. Tell the user both happened.
