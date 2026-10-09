import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { uid } from './helpers/fixtures';
import { MockSalli } from './helpers/mock-server';
import { runCli, ScriptedPrompter, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
  mock = await MockSalli.start();
});
afterEach(async () => {
  await mock.close();
  await cleanup();
});

const run = (args: string[], options: Partial<RunOptions> = {}) =>
  runCli(args, {
    configDir: dir,
    ...options,
    env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', ...options.env },
  });

describe('salli status', () => {
  it('shows net worth, the month so far, the FI score and what is due', async () => {
    const result = await run(['status']);
    expect(result.code).toBe(0);
    expect(result.stdout.replace(mock.url, 'http://salli.test')).toMatchInlineSnapshot(`
      "Salli · default · http://salli.test

      Net worth       USD 14,034.50
        Assets        USD 15,234.50
        Liabilities   USD  1,200.00

      October 2026 so far (Oct 1 – 9, 2026)
        Net income    USD 2,787.65
        Income        Salary USD 5,000.00
        Spending      Rent USD 1,800.00 · Groceries USD 412.35

      FI score        72.5 (B) · 1.9% of the way to financial independence
        Savings rate  55.8% of income
        FI by         Oct 9, 2040

      Coming up
      ! Oct 9, 2026   Budget overspend            warning
        Nov 30, 2026  Return due 2025/26
      "
    `);
    const statement = mock.requestsTo('GET', '/v1/ledger/income-statement')[0];
    expect(statement?.query.get('from_date')).toBe('2026-10-01');
    expect(statement?.query.get('to_date')).toBe('2026-10-09');
  });

  it('prints every API response as JSON', async () => {
    const result = await run(['status', '--json']);
    expect(result.stdout.replaceAll(mock.url, 'http://salli.test')).toMatchInlineSnapshot(`
      "{
        "context": "default",
        "server": "http://salli.test",
        "period": {
          "from": "2026-10-01",
          "to": "2026-10-09"
        },
        "balance_sheet": {
          "currency": "USD",
          "assets": [
            {
              "account_id": "00000001-5a11-4000-8000-000000000001",
              "code": "1000",
              "name": "Cash",
              "balance": "250.00"
            },
            {
              "account_id": "00000002-5a11-4000-8000-000000000002",
              "code": "1100",
              "name": "Checking",
              "balance": "12784.50"
            },
            {
              "account_id": "00000003-5a11-4000-8000-000000000003",
              "code": "1200",
              "name": "Euro Savings",
              "balance": "2200.00"
            }
          ],
          "liabilities": [
            {
              "account_id": "00000004-5a11-4000-8000-000000000004",
              "code": "2000",
              "name": "Credit Card",
              "balance": "1200.00"
            }
          ],
          "equity": [],
          "total_assets": "15234.50",
          "total_liabilities": "1200.00",
          "total_equity": "0.00",
          "net_worth": "14034.50"
        },
        "income_statement": {
          "from_date": "2026-10-01",
          "to_date": "2026-10-09",
          "currency": "USD",
          "income": {
            "Salary": "5000.00"
          },
          "expenses": {
            "Groceries": "412.35",
            "Rent": "1800.00"
          },
          "net_income": "2787.65"
        },
        "fi_score": {
          "pack_version": "1",
          "overall_score": "72.5",
          "grade": "B",
          "monthly_income": "5000.00",
          "monthly_expenses": "2212.35",
          "monthly_surplus": "2787.65",
          "savings_rate": "0.5575",
          "swr": "0.04",
          "annual_expenses": "26548.20",
          "fi_number": "663705.00",
          "net_worth": "14034.50",
          "fi_asset_base": "12834.50",
          "progress_to_fi": "0.0193",
          "emergency_fund_months": "5.8",
          "debt_to_asset": "0.0788",
          "projected_fi_years": "14",
          "currency": "USD",
          "components": [
            {
              "key": "savings_rate",
              "label": "Savings rate",
              "score": "90",
              "weight": "0.3",
              "detail": "56% of income saved"
            },
            {
              "key": "emergency_fund",
              "label": "Emergency fund",
              "score": "80",
              "weight": "0.2",
              "detail": "5.8 months covered"
            }
          ],
          "projected_fi_date": "2040-10-09",
          "inputs_hash": "abc"
        },
        "reminders": {
          "reminders": [
            {
              "id": "0000012d-5a11-4000-8000-000000000301",
              "kind": "budget_overspend",
              "due_date": "2026-10-09",
              "status": "pending",
              "alert_type": "budget_overspend",
              "source_domain": "budget",
              "source_id": "00000191-5a11-4000-8000-000000000401",
              "severity": "warning",
              "created_at": "2026-10-08T09:00:00+00:00"
            },
            {
              "id": "0000012e-5a11-4000-8000-000000000302",
              "kind": "return_due_2025/26",
              "due_date": "2026-11-30",
              "status": "pending",
              "alert_type": null,
              "source_domain": null,
              "source_id": null,
              "severity": null,
              "created_at": "2026-04-01T09:00:00+00:00"
            }
          ]
        }
      }
      "
    `);
    const data = JSON.parse(result.stdout);
    expect(Object.keys(data)).toEqual(['context', 'server', 'period', 'balance_sheet', 'income_statement', 'fi_score', 'reminders']);
    expect(data.balance_sheet.net_worth).toBe('14034.50');
    expect(data.fi_score.grade).toBe('B');
  });

  it('still shows what it can when one part fails', async () => {
    mock.on('GET', '/v1/fi/score', () => ({ status: 503, body: { type: 'about:blank', title: 'Service Unavailable', status: 503, detail: 'AI is off' } }));
    const result = await run(['status', '--json']);
    expect(result.code).toBe(0);
    const data = JSON.parse(result.stdout);
    expect(data.fi_score).toBeNull();
    expect(data.unavailable.fi_score).toMatchObject({ status: 503, exit_code: 1 });
  });
});

describe('salli accounts', () => {
  it('lists accounts as a table, and the API JSON exactly', async () => {
    const table = await run(['accounts', 'list']);
    expect(table.stdout).toMatchInlineSnapshot(`
      "CODE  NAME          TYPE       CURRENCY  STATUS    ID
      1000  Cash          asset      USD                 00000001
      1100  Checking      asset      USD                 00000002
      1200  Euro Savings  asset      EUR                 00000003
      2000  Credit Card   liability  USD                 00000004
      4000  Salary        income     USD                 00000005
      5000  Groceries     expense    USD                 00000006
      5100  Rent          expense    USD                 00000007
      5900  Old Expenses  expense    USD       inactive  00000008
      "
    `);
    const json = await run(['accounts', 'list', '--type', 'asset', '--json']);
    expect(json.stdout).toMatchInlineSnapshot(`
      "[
        {
          "id": "00000001-5a11-4000-8000-000000000001",
          "code": "1000",
          "name": "Cash",
          "type": "asset",
          "currency": "USD",
          "parent_id": null,
          "is_active": true,
          "tax_role": null
        },
        {
          "id": "00000002-5a11-4000-8000-000000000002",
          "code": "1100",
          "name": "Checking",
          "type": "asset",
          "currency": "USD",
          "parent_id": null,
          "is_active": true,
          "tax_role": null
        },
        {
          "id": "00000003-5a11-4000-8000-000000000003",
          "code": "1200",
          "name": "Euro Savings",
          "type": "asset",
          "currency": "EUR",
          "parent_id": null,
          "is_active": true,
          "tax_role": null
        }
      ]
      "
    `);
    expect(JSON.parse((await run(['accounts', 'list', '--json'])).stdout)).toHaveLength(8);
    expect(json.stdout).toContain('"tax_role": null');
  });

  it('filters, and streams records as NDJSON and CSV', async () => {
    const ndjson = await run(['accounts', 'list', '--type', 'expense', '--active', '-o', 'ndjson']);
    expect(ndjson.stdout.trim().split('\n').map((l) => JSON.parse(l).code)).toEqual(['5000', '5100']);
    const csv = await run(['accounts', 'list', '--type', 'asset', '-o', 'csv']);
    expect(csv.stdout).toMatchInlineSnapshot(`
      "id,code,name,type,currency,parent_id,is_active,tax_role
      00000001-5a11-4000-8000-000000000001,1000,Cash,asset,USD,,true,
      00000002-5a11-4000-8000-000000000002,1100,Checking,asset,USD,,true,
      00000003-5a11-4000-8000-000000000003,1200,Euro Savings,asset,EUR,,true,
      "
    `);
  });

  it('adds balances from the trial balance', async () => {
    const result = await run(['accounts', 'list', '--balances', '--type', 'asset']);
    expect(result.stdout).toMatchInlineSnapshot(`
      "CODE  NAME          TYPE   CURRENCY  BALANCE (USD)  STATUS  ID
      1000  Cash          asset  USD              250.00          00000001
      1100  Checking      asset  USD           12,784.50          00000002
      1200  Euro Savings  asset  EUR                0.00          00000003
      "
    `);
  });

  it('shows an account found by name, code or id prefix', async () => {
    const byName = await run(['accounts', 'show', 'check']);
    expect(byName.code).toBe(0);
    expect(byName.stdout).toMatchInlineSnapshot(`
      "1100 Checking
      Type      asset
      Currency  USD
      Status    active
      Balance   USD 12,784.50
      ID        00000002-5a11-4000-8000-000000000002

      DATE         DESCRIPTION       SOURCE  BALANCE (USD)  ENTRY
      Oct 1, 2026  October salary    manual      14,584.50  000000c9
      Oct 3, 2026  Rent for October  manual      12,784.50  000000ca
      "
    `);
    expect((await run(['accounts', 'show', '1100'])).code).toBe(0);
    expect((await run(['accounts', 'show', uid(2).slice(0, 8)])).code).toBe(0);

    const foreign = await run(['accounts', 'show', 'euro']);
    expect(foreign.stdout).toContain('Balance     EUR 2,000.00');
    expect(foreign.stdout).toContain('Book value  USD 2,200.00 (at the rates its entries recorded)');
  });

  it('says which accounts an ambiguous name matches', async () => {
    const result = await run(['accounts', 'show', 'c']);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('"c" matches 3 accounts');
    expect(result.stderr).toContain('1000 (Cash)');
  });

  it('adds, updates, deactivates and reactivates', async () => {
    const added = await run(['accounts', 'add', '1300', 'Brokerage', 'asset', '--currency', 'usd', '--json']);
    expect(added.code).toBe(0);
    expect(JSON.parse(added.stdout)).toEqual({ id: expect.any(String) });
    expect(mock.requestsTo('POST', '/v1/accounts/')[0]?.json).toEqual({ code: '1300', name: 'Brokerage', type: 'asset', currency: 'USD' });

    const updated = await run(['accounts', 'update', 'brokerage', '--name', 'Brokerage (Vanguard)']);
    expect(updated.code).toBe(0);
    expect(updated.stderr).toContain('Updated 1300 Brokerage (Vanguard).');
    // Unchanged fields are sent as they were; the tax role is left alone.
    expect(mock.requestsTo('PATCH', '/v1/accounts/')[0]?.json).toEqual({ code: '1300', name: 'Brokerage (Vanguard)', type: 'asset' });

    const off = await run(['accounts', 'deactivate', '1300', '--json']);
    expect(JSON.parse(off.stdout)).toEqual({ id: expect.any(String), is_active: false });
    const on = await run(['accounts', 'reactivate', '1300', '--json']);
    expect(JSON.parse(on.stdout)).toEqual({ id: expect.any(String), is_active: true });
  });

  it('refuses a bad type before calling the server', async () => {
    const result = await run(['accounts', 'add', '1300', 'Brokerage', 'savings']);
    expect(result.code).toBe(2);
    expect(mock.requestsTo('POST', '/v1/accounts/')).toHaveLength(0);
  });
});

describe('salli entries', () => {
  it('lists entries with their amounts and accounts', async () => {
    const result = await run(['entries', 'list', '--month', '2026-10']);
    expect(result.stdout).toMatchInlineSnapshot(`
      "DATE         DESCRIPTION                     AMOUNT  DEBIT         CREDIT       ID
      Oct 1, 2026  October salary            USD 5,000.00  Checking      Salary       000000c9
      Oct 3, 2026  Rent for October          USD 1,800.00  Rent          Checking     000000ca
      Oct 5, 2026  Weekly groceries            USD 412.35  Groceries     Credit Card  000000cb
      Oct 6, 2026  Split dinner  (reversed)       2 parts  Groceries +1  Cash         000000cc
      "
    `);
    const request = mock.requestsTo('GET', '/v1/entries/')[0];
    expect(request?.query.get('from_date')).toBe('2026-10-01');
    expect(request?.query.get('to_date')).toBe('2026-10-31');
  });

  it('filters by account and text', async () => {
    const result = await run(['entries', 'list', '--account', 'groceries', '--search', 'weekly', '--json']);
    expect(JSON.parse(result.stdout).map((e: { description: string }) => e.description)).toEqual(['Weekly groceries']);
  });

  it('shows an entry with its postings, tags and provenance', async () => {
    const result = await run(['entries', 'show', uid(203).slice(0, 8)]);
    expect(result.code).toBe(0);
    expect(result.stdout).toMatchInlineSnapshot(`
      "Weekly groceries
      Date    Oct 5, 2026
      Source  statement
      ID      000000cb-5a11-4000-8000-000000000203

      ACCOUNT            DEBIT  CREDIT  CURRENCY  RATE  TAGS                               POSTING
      5000 Groceries    412.35          USD             category=groceries need=essential  00000069
      2000 Credit Card          412.35  USD                                                0000006a

      From a bank statement: “SUPERMARKET 123” 412.35 on Oct 5, 2026 · Acme Bank · statement for Oct 1 – 31, 2026
      "
    `);
    const shown = await run(['entries', 'show', uid(203), '--json']);
    expect(shown.stdout).toMatchInlineSnapshot(`
      "{
        "entry": {
          "id": "000000cb-5a11-4000-8000-000000000203",
          "entry_date": "2026-10-05",
          "description": "Weekly groceries",
          "source": "statement",
          "external_ref": "00000385-5a11-4000-8000-000000000901",
          "reversed_by": null,
          "postings": [
            {
              "id": "00000069-5a11-4000-8000-000000000105",
              "tags": {
                "category": "groceries",
                "need": "essential"
              },
              "account_id": "00000006-5a11-4000-8000-000000000006",
              "direction": 1,
              "amount": "412.35",
              "currency": "USD",
              "fx_rate": "1"
            },
            {
              "id": "0000006a-5a11-4000-8000-000000000106",
              "tags": {},
              "account_id": "00000004-5a11-4000-8000-000000000004",
              "direction": -1,
              "amount": "412.35",
              "currency": "USD",
              "fx_rate": "1"
            }
          ]
        },
        "provenance": {
          "entry_id": "000000cb-5a11-4000-8000-000000000203",
          "entry_date": "2026-10-05",
          "description": "Weekly groceries",
          "source": "statement",
          "external_ref": "00000385-5a11-4000-8000-000000000901",
          "statement": {
            "parsed_transaction_id": "00000385-5a11-4000-8000-000000000901",
            "raw_description": "SUPERMARKET 123",
            "raw_amount": "412.35",
            "raw_date": "2026-10-05",
            "bank_ref": "REF9",
            "statement": {
              "id": "00000321-5a11-4000-8000-000000000801",
              "bank": "Acme Bank",
              "period_start": "2026-10-01",
              "period_end": "2026-10-31"
            }
          },
          "receipt": null
        }
      }
      "
    `);
    const json = JSON.parse(shown.stdout);
    expect(Object.keys(json)).toEqual(['entry', 'provenance']);
    expect(json.provenance.statement.raw_description).toBe('SUPERMARKET 123');
  });

  it('posts a balanced entry from ACCOUNT:AMOUNT pairs, amounts as exact strings', async () => {
    const result = await run([
      'entries',
      'add',
      '--desc',
      'Dinner',
      '--date',
      'yesterday',
      '--debit',
      'groceries:1,234.50',
      '--credit',
      'cash:1234.5',
      '--tag',
      'category=dining',
      '--json',
    ]);
    expect(result.code).toBe(0);
    expect(JSON.parse(result.stdout)).toEqual({ id: expect.any(String) });
    expect(mock.data.created[0]).toEqual({
      entry_date: '2026-10-08',
      description: 'Dinner',
      postings: [
        { account_id: uid(6), direction: 1, amount: '1234.50', tags: { category: 'dining' } },
        { account_id: uid(1), direction: -1, amount: '1234.5' },
      ],
    });
  });

  it('passes the server’s refusal through as problem details (exit 5)', async () => {
    const result = await run(['entries', 'add', '--desc', 'Paris', '--currency', 'eur', '--debit', 'groceries:10', '--credit', 'cash:10']);
    expect(result.code).toBe(5);
    expect(result.stderr).toContain('No exchange rate: No EUR→USD rate for that date. Send the exchange rate (fx_rate) with the amount.');
  });

  it('rejects amounts that are not plain decimals', async () => {
    const result = await run(['entries', 'add', '--desc', 'x', '--debit', 'groceries:1.234,50', '--credit', 'cash:10']);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('--debit must be a number like 1500 or 1234.50');
  });

  it('reverses only after confirmation', async () => {
    const noTty = await run(['entries', 'reverse', uid(202).slice(0, 8)]);
    expect(noTty.code).toBe(2);
    expect(noTty.stderr).toContain('Pass --yes to confirm.');

    const prompter = new ScriptedPrompter([true]);
    const confirmed = await run(['entries', 'reverse', uid(202)], { prompter });
    expect(confirmed.code).toBe(0);
    expect(prompter.asked[0]).toBe('Reverse “Rent for October” (Oct 3, 2026, USD 1,800.00)?');
    expect(confirmed.stderr).toContain('Reversed “Rent for October”');

    const again = await run(['entries', 'reverse', uid(202), '--yes']);
    expect(again.code).toBe(2);
    expect(again.stderr).toContain('already reversed');
  });

  it('retags a posting', async () => {
    const result = await run(['entries', 'tag', uid(105), 'category=groceries', 'need=essential', '--json']);
    expect(JSON.parse(result.stdout)).toEqual({ posting_id: uid(105), tags: { category: 'groceries', need: 'essential' } });
    expect(mock.data.taggings).toEqual([{ posting: uid(105), tags: { category: 'groceries', need: 'essential' } }]);
  });
});

describe('salli add (quick add)', () => {
  it('posts the AI draft with --yes', async () => {
    const result = await run(['add', 'lunch', '12.50', 'cash', '--yes']);
    expect(result.code).toBe(0);
    expect(result.stderr).toContain('Posted “Lunch”: USD 12.50 from Cash to Groceries');
    expect(mock.requestsTo('POST', '/v1/entries/parse')[0]?.json).toEqual({ text: 'lunch 12.50 cash' });
    expect(mock.data.created[0]).toEqual({
      entry_date: '2026-10-09',
      description: 'Lunch',
      postings: [
        { account_id: uid(6), direction: 1, amount: '12.50', currency: 'USD' },
        { account_id: uid(1), direction: -1, amount: '12.50', currency: 'USD' },
      ],
    });
  });

  it('shows the draft only with --dry-run, as the API JSON', async () => {
    const result = await run(['add', 'lunch 12.50 cash', '--dry-run', '--json']);
    expect(JSON.parse(result.stdout)).toMatchObject({ entry_type: 'expense', amount: '12.50', currency: 'USD' });
    expect(mock.data.created).toHaveLength(0);
  });

  it('refuses --yes when the draft is missing an account', async () => {
    mock.parseDraft = { ...mock.parseDraft, debit_account_id: null, debit_account_hint: { name: 'Dining', type: 'expense' } };
    const result = await run(['add', 'dinner 40 cash', '--yes']);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('The draft has no debit account (it suggests a new one: Dining, expense).');
    const fixed = await run(['add', 'dinner 40 cash', '--yes', '--debit', 'groceries']);
    expect(fixed.code).toBe(0);
  });

  it('lets you change the draft before posting', async () => {
    const prompter = new ScriptedPrompter(['amount', '15', 'credit', uid(4), 'post']);
    const result = await run(['add', 'lunch 12.50 cash'], { prompter });
    expect(result.code).toBe(0);
    expect(prompter.asked).toEqual([
      'Post this entry?',
      'Amount (USD)',
      'Post this entry?',
      'Which account paid? (From)',
      'Post this entry?',
    ]);
    expect(mock.data.created[0]).toMatchObject({
      postings: [
        { account_id: uid(6), amount: '15' },
        { account_id: uid(4), amount: '15', direction: -1 },
      ],
    });
  });

  it('can create the new account the AI suggests', async () => {
    mock.parseDraft = { ...mock.parseDraft, debit_account_id: null, debit_account_hint: { name: 'Dining', type: 'expense' } };
    const prompter = new ScriptedPrompter(['debit', '__new__', '5300', 'post']);
    const result = await run(['add', 'dinner 40 cash'], { prompter });
    expect(result.code).toBe(0);
    expect(mock.requestsTo('POST', '/v1/accounts/')[0]?.json).toEqual({ code: '5300', name: 'Dining', type: 'expense' });
    expect(result.stderr).toContain('Added 5300 Dining.');
  });

  it('needs a terminal or --yes', async () => {
    const result = await run(['add', 'lunch 12.50 cash']);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('Pass --yes to post it as drafted, or --dry-run to see it.');
  });
});

describe('salli ledger and tags', () => {
  it('prints the trial balance', async () => {
    const result = await run(['ledger', 'trial-balance']);
    expect(result.stdout).toMatchInlineSnapshot(`
      "CODE  ACCOUNT      BALANCE (USD)
      1000  Cash                250.00
      1100  Checking         12,784.50
      2000  Credit Card      -1,200.00
      4000  Salary          -11,834.50
            Net                   0.00
      "
    `);
  });

  it('prints the income statement for a month', async () => {
    const result = await run(['ledger', 'income-statement', '--month', '2026-09']);
    expect(result.stdout).toMatchInlineSnapshot(`
      "Income statement · Sep 1 – 30, 2026 · USD
      Income
        Salary      5,000.00
      Expenses
        Rent        1,800.00
        Groceries     412.35

      Net income    2,787.65
      "
    `);
    expect(mock.requestsTo('GET', '/v1/ledger/income-statement')[0]?.query.toString()).toBe('from_date=2026-09-01&to_date=2026-09-30');
  });

  it('lists tags, and their records as CSV', async () => {
    expect((await run(['tags'])).stdout).toMatchInlineSnapshot(`
      "AXIS      SLUG       NAME
      category  groceries  Groceries
      need      essential  Essential  built-in
      "
    `);
    expect((await run(['tags', 'list', '--kind', 'need', '-o', 'csv'])).stdout).toMatchInlineSnapshot(`
      "id,slug,name,kind,color,is_system
      000001f6-5a11-4000-8000-000000000502,essential,Essential,need,,true
      "
    `);
  });
});
