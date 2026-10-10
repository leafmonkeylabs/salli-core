---
name: salli-tax
description: Answer questions about the user's income tax position from their Salli ledger — estimated tax, bands, credits and what they still owe — in countries Salli has a tax pack for (so far Sri Lanka: APIT, AIT, foreign tax credits). Use for "how much tax will I pay", "what's my APIT credit", or preparing a return.
---

# Tax

Read the `salli-cli` skill first.

**Salli's tax engine computes tax; you never do.** Report the engine's
figures exactly, and explain them. Don't recompute, round differently, or
"adjust" them.

    salli tax year --json              # the tax year today, and the latest one Salli can compute
    salli tax packs --json             # which rule packs exist (country, year, version)
    salli tax compute --year 2025/26 --json
    salli tax latest --json            # the last stored computation

Explain the result from the output: taxable income after personal relief, tax
per band, credits (APIT, AIT, foreign tax credit), and the balance payable or
refundable. Quote the pack version from the output when you state a figure.

If income or credits look missing, the ledger is probably missing entries or
an account lacks its tax role. Help the user record them (see
`salli-record-transaction`) and compute again.

Always add: this is an estimate from the user's own records, not tax advice,
and the tax pack has not been reviewed by a chartered accountant.
