# Sri Lanka market pack

Salli's first market. Everything here is data: tax rule sets, planning
assumptions and the provident funds, each figure cited to the Inland Revenue
Department (IRD), the Acts, the Central Bank or the funds, as retrieved on
2026-10-25. See [../README.md](../README.md) for what a market pack is.

**Review status: not yet reviewed by a Sri Lankan chartered accountant.**
What a reviewer should check is [at the end](#for-the-reviewer).

## What's in it

| File | What it is |
|---|---|
| [`tax/2025-26.json`](tax/2025-26.json) | Resident individuals, year of assessment 2025/2026 (1 April 2025 to 31 March 2026). 10 worked examples. |
| [`tax/2024-25.json`](tax/2024-25.json) | The same for 2024/2025, whose relief, bands and interest AIT differ. 5 worked examples. |
| [`cma.json`](cma.json) | Capital-market assumptions (`salli.cma/1`): inflation, cash yield, four asset classes, correlations. |
| [`pensions.json`](pensions.json) | EPF and ETF (`salli.pensions/1`): contributions, payout, tax treatment, ledger postings. |
| [`banks/`](banks) | Statement layouts (`salli.bankformat/1`) for Commercial Bank, Sampath, Bank of Ceylon, HNB and NDB. |

### Bank statement formats

`salli import statement.csv --account <account> --format markets/lk/banks/`
tries every layout here and uses the one that reads the most rows; the
result says how many rows each read and failed to. They apply to CSV
exports and to the tables of PDF statements.

**None is verified** (`"verified": false` in each file). No bank publishes
its export layout or a sample statement, so the columns, date format and
debit/credit style come from the banks' online-banking pages and, for Bank
of Ceylon, one unofficial printed statement; each file cites what was seen.
Each has a synthetic sample in `banks/samples/` that the tests read. To
verify one, follow [banks/VERIFYING.md](banks/VERIFYING.md): what anonymised
sample to collect per bank, and `salli import check`, which reads it
without importing and checks the balances add up.

### The tax rule sets

Both years compute, for a salaried resident:

- **Assessable income**: employment (gross, the employee's 8% EPF not
  deducted), interest (gross of AIT), rent, other.
- **Reliefs**: rent relief (25% of rent), solar panels on the national grid
  (up to Rs 600,000), then the **personal relief**: Rs 1,800,000 for 2025/26
  (Act No. 2 of 2025, Fifth Schedule 2(a)(v)), Rs 1,200,000 for 2024/25. It
  never reaches gains on investment assets.
- **Qualifying payment**: donations to an approved charity, capped at
  Rs 75,000 and a quarter of assessable income.
- **Progressive bands**: 2025/26: 6% on the first Rs 1,000,000, then 18%,
  24%, 30% on each next 500,000, 36% above (Act No. 2 of 2025, First
  Schedule 1(1D)). 2024/25: 6%, 12%, 18%, 24%, 30% on each 500,000, 36% above.
- **Gains on realising investment assets** (`realised_gain`): 10% for
  individuals, with no personal relief. Tag only taxable gains (below).
- **Credits**: APIT deducted by employers, AIT on interest (10% from
  1 April 2025, 5% before), capital gains tax already paid, instalments.
- **Deadlines** (2025/26): instalments 15 Aug 2025, 15 Nov 2025, 15 Feb 2026,
  15 May 2026; final payment 30 Sep 2026; return 30 Nov 2026.
- **Form**: the individual return's schedules and cages, from the IRD's
  e-filing guide.

**APIT** is modelled as what it is for the return: a credit against the year's
tax. The worked examples are the IRD's APIT Table 1 formulas annualised: for
example Rs 300,000 a month is 24% less Rs 53,500, Rs 18,500 a month, Rs 222,000
a year, which the rule set computes from the annual bands.

**Tax roles**: `employment_income`, `interest_income`, `rent_income`,
`other_income`, `realised_gain`, `withdrawal` (exempt EPF payouts, listed on
the return as exempt income), `solar_expenditure`, `donations`,
`apit_withheld`, `interest_wht`, `cgt_paid`, `instalments_paid`.

**Not modelled** (tag nothing for them, and work them out separately):
terminal benefits (gratuity, ETF at retirement: 0% on the first Rs 10,000,000,
6% on the next, 12% above), business income, foreign-source income and
services at the 15% cap, dividends (a final 15% withholding, so they don't
enter the return's tax), the per-disposal exemption for small gains (a gain up
to Rs 50,000 when the year's gains are at most Rs 600,000), and the 10%
discount for paying an instalment a month early.

**Gains that are exempt** and must not carry the `realised_gain` role: shares
quoted on a licensed stock exchange, a principal residence owned for three
years and lived in for two, and the small gains above. A loss is never set off
against a gain. Capital gains tax is due with a return within 30 days after the
end of the month of the sale.

**After 2025/26.** The Inland Revenue (Amendment) Act, No. 11 of 2026
(certified 3 June 2026) raised individuals' rate on gains to 15% from
3 June 2026. That falls in 2026/27, which this pack does not cover yet.

### Capital-market assumptions

`cma.json` is a `salli.cma/1` pack (docs/baseline.md, "Capital-market
assumptions"): import it with `salli fi cma import markets/lk/cma.json` and
activate it with `salli fi cma activate <id>`. Each figure names its source;
the ones marked as an assumption are for the reviewer to replace. Its `mix`
(20% cash, 40% government securities, 25% local and 15% global equities) is
an assumption too: the real return a plan uses is the mix's.

| Asset class | Real return | Volatility | Basis |
|---|---|---|---|
| Rupee cash and deposits | 1.8% | 1% | Deposit rate 6.86% (April 2026) deflated by the 5% target: 1.0686 / 1.05 − 1 |
| Government securities | 3.3% | 5% | 1-year bill 8.49% (May 2026) deflated by the 5% target: 1.0849 / 1.05 − 1 |
| Local equities | 6% | 25% | Assumption |
| Global equities, USD | 5% | 16% | Assumption, in US-dollar terms |

Cash yield: 1.8%, the deposit rate deflated as above (every rate in the pack
says `"basis": "real"`). Inflation: 5%, the Central Bank's target. Every volatility and correlation is
an assumption.

### Pensions

EPF: employee 8%, employer 12% of total monthly earnings; a lump sum, exempt
from tax when paid by the approved fund. ETF: employer 3%; a lump sum taxed
as a terminal benefit. Neither guarantees an income, so the planning engine
should treat both as provident capital. `pensions.json` gives the ledger
postings (one payslip entry: Dr Bank net pay, Dr APIT deducted, Dr EPF 20%,
Dr ETF 3%; Cr Employment Income gross, Cr Employer Pension Contributions 15%).

### Bank statements

Salli's CSV importer detects a bank's layout from the file (English headers,
debit and credit columns, day-first dates). It has a stated-layout mapping
(`CsvMapping`), but no command or route takes one yet, so this pack ships no
mappings. The column layouts of the main banks' exports (Bank of Ceylon,
People's Bank, Commercial Bank, Sampath, HNB) are not publicly documented, and
none was confirmed. If detection gets one wrong, send a redacted sample with
an issue; a mapping can be added then.

## Loading it

```sh
# The tax rules: store, check, review and activate (activation is yours alone).
salli tax rules create markets/lk/tax/2025-26.json --note "market pack"
salli tax rules validate <set>
salli tax rules diff <set>
salli tax rules activate <set>

# The accounts the rules use; --apply adds the missing ones.
salli tax rules accounts <set> --apply
# An account you already have takes its role this way:
salli accounts update 4100 --tax-role employment_income

salli tax compute

# Planning assumptions: the capital-market pack.
salli fi cma import markets/lk/cma.json
salli fi cma activate <id>
```

## Sources

| Source | Used for |
|---|---|
| [Inland Revenue (Amendment) Act, No. 2 of 2025](https://www.ird.gov.lk/en/publications/Acts_Income%20Tax_2017/IR_Act_No_02-2025_E.pdf) | 2025/26 bands, relief, interest AIT 10% |
| [IRD Tax Chart 2025/2026](https://www.ird.gov.lk/en/publications/SitePages/tax_chart_2526.aspx?menuid=1404) | Reliefs, gains rate, WHT/AIT rates, terminal benefits |
| [IRD APIT Table 1, 2025/26](https://www.ird.gov.lk/en/publications/APIT_Tax_Tables/2025-2026/Table%20-%201/02.%20APIT_2526_Table_01_Text.pdf) and [2023/24](https://www.ird.gov.lk/en/publications/APIT_Tax_Tables/2023-2024/Table%20-%201/02.%20APIT_2324_Table_01_Text.pdf) | Worked examples |
| [IRD e-filing guide, Y/A 2024/2025](https://www.ird.gov.lk/en/Downloads/IT_Individuals_Doc/Guide_to_IIT_2425_E.pdf) | 2024/25 relief and bands, return layout, exemptions, qualifying payments |
| [IRD Capital Gain Tax](https://www.ird.gov.lk/en/Type%20of%20Taxes/SitePages/Capital%20Gain%20Tax%20(CGT).aspx?menuid=1208) | Gains rate by date, exemptions, 30-day return |
| [IRD Tax Calendar 2026](https://www.ird.gov.lk/en/publications/Tax%20Calendar_Documents/Tax_Calendar_2026_E.pdf) | 2025/26 deadlines |
| [CBSL Monetary Policy Review No. 3, 2026](https://www.cbsl.gov.lk/sites/default/files/cbslweb_documents/mpr_no_3_2026_press_presentation_e.pdf) | Inflation target, deposit and bill rates |
| [EPF FAQs for employers](https://epf.lk/?p=811) | EPF contribution rates |

## Not confirmed from a primary source

Those in the tax rule sets are marked `"provisional": true` there, with a
`note`; every computation lists them under `provisional`.

- The **ETF 3%** rate: from payroll guides; the ETF Board's pages retrieved
  don't state it.
- The **EPF crediting rate** (10.75% for 2025, 11% for 2024): from press
  reports of the Central Bank's review, said to await ministerial concurrence.
- **Deadlines for 2025/26's 1st and 2nd instalments** (15 Aug and 15 Nov
  2025) and **2024/25's final payment and return** (30 Sep and 30 Nov 2025):
  inferred from the 2026 calendar's pattern; the 2025 calendar wasn't
  retrievable.
- The **donation cap**: the IRD guide says "one fourth of the total assessable
  income (one third of the taxable income) or Rs. 75,000"; the rule set uses a
  quarter of assessable income. Check against the Act.
- Whether the **employer's EPF and ETF contributions** are outside employment
  income: the pack treats them so (the APIT tables don't list them), but no
  IRD text retrieved says it outright.
- **Cage numbers** come from the 2024/25 e-filing guide; the 2025/26 guide
  wasn't found.
- **Rounding**: the rule sets round the result to the cent; the IRD's own
  rounding was not found.
- **Expenditure relief**: the 2024/25 guide's Schedule 5 is titled
  "Qualifying payments & expenditure relief", but its list of reliefs names no
  expenditure relief; none is modelled.
- In `cma.json`: every **volatility**, every **correlation**, and the
  **expected returns of local and global equities** are assumptions.

## For the reviewer

Please check, and record the result here with your name and date:

1. The relief, bands and the gains rate for both years against the Acts.
2. That interest AIT is a credit for residents (not a final tax), and that
   dividends' 15% is final.
3. The donation cap, the order of reliefs (rent and solar before personal
   relief), and that reliefs can't reach gains.
4. The employer EPF/ETF treatment and the exemption of EPF payouts.
5. The deadlines, especially the inferred ones.
6. The return's cage numbers against the current year's form.
7. Whether the CMA figures are sensible for a long-run plan.
