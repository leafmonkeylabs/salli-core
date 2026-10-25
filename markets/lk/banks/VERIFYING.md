# Verifying a bank's format

None of the formats here is verified yet (`"verified": false`). A format
is verified when a real statement from that bank reads in full and its
figures match the bank's own. This is what to collect from each pilot user,
and how to check it.

## What to ask each pilot user for

One statement **per bank and per kind of export** (CSV download, PDF
statement, Excel), of a current or savings account, covering a month with
at least ten transactions, including at least one each of: money in, money
out, a cheque (where the bank prints cheque numbers), and a fee or interest
line. Then, before it leaves their computer:

1. **Keep** the header row(s) exactly, every column (even empty ones), the
   date column(s) exactly as printed, the amount, debit/credit, Dr/Cr and
   balance columns exactly as printed (separators, signs, trailing CR/DR),
   and the balance brought forward and carried forward lines.
2. **Replace** names, account numbers, cheque numbers and references with
   `X`s of the same length, and every description with a short generic one
   (`SALARY`, `CARD PAYMENT`, `TRANSFER`).
3. **Do not change** any amount or balance: the check below needs them to
   add up. If the user won't share real amounts, ask them to run the check
   themselves (next section) and send only its output.

Keep the file as the bank produced it otherwise (same encoding, delimiter
and line endings): open and re-save it in a spreadsheet and the format may
change.

## How to check one

```bash
salli import check --format markets/lk/banks/ statement.csv
```

reads the file with every format here, imports nothing, and prints which
format it used, the rows read and not read, money in and out, and the
opening and closing balances. The format reads the file when:

- the transactions count matches the statement's,
- no row is reported as not read,
- money in and out match the statement's totals, where it prints them,
- the opening and closing balances match the statement's, and it says
  "Opening + in - out = closing".

Then set `"verified": true` in that bank's file, add a source note with the
date and the kind of export checked, and replace its sample in `samples/`
with the anonymised file. When the check fails, correct `columns`,
`date_format` or the separators from the file's header row and run it again.
