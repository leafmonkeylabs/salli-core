import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { BriefingPrepared } from '@leafmonkeylabs/salli-sdk';
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
  runCli(args, { configDir: dir, ...options, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', ...options.env } });
const sent = (method: string, path: string) => mock.requestsTo(method, path).at(-1)?.json;

describe('onboarding', () => {
  it('says whether onboarding is done', async () => {
    mock.on('GET', '/v1/onboarding/status', () => ({ status: 200, body: { complete: false } }));
    expect((await run(['onboarding', 'status'])).stdout).toBe('Onboarding: not done yet\n');
    expect(JSON.parse((await run(['onboarding', 'status', '--json'])).stdout)).toEqual({ complete: false });
  });

  it('sends the profile with the goal amount as the decimal string typed', async () => {
    mock.on('POST', '/v1/onboarding/complete', () => ({
      status: 200,
      body: { memories_saved: ['name'], accounts_created: ['1000 Cash', '4100 Employment Income'], accounts_skipped: [] },
    }));
    const result = await run([
      'onboarding', 'complete', '--name', 'Sam Roe', '--base-currency', 'eur', '--tax-residency', 'gb',
      '--income', 'employment, rental', '--goal', 'home', '--goal-amount', '45,000.50', '--goal-year', '2031',
    ]);
    expect(result.code).toBe(0);
    expect(sent('POST', '/v1/onboarding/complete')).toEqual({
      name: 'Sam Roe',
      residency: 'resident',
      base_currency: 'EUR',
      tax_residency: 'GB',
      income_sources: ['employment', 'rental'],
      primary_goal: 'home',
      goal_target_amount: '45000.50',
      goal_target_year: '2031',
    });
    expect(result.stdout).toContain('1000 Cash');
  });

  it('sends the residency and generic tax ids, or asks where you are taxed', async () => {
    const done = () => ({ status: 200, body: { memories_saved: [], accounts_created: [], accounts_skipped: [] } });
    mock.on('POST', '/v1/onboarding/complete', done);
    const given = await run(['onboarding', 'complete', '--name', 'Sam', '--tax-residency', 'ke', '--tax-id', 'ke-pin=A001', '--tax-id', 'KE-X=7']);
    expect(given.code).toBe(0);
    expect(sent('POST', '/v1/onboarding/complete')).toEqual({
      name: 'Sam',
      residency: 'resident',
      tax_residency: 'KE',
      tax_ids: [
        { scheme: 'KE-PIN', value: 'A001' },
        { scheme: 'KE-X', value: '7' },
      ],
    });

    const prompter = new ScriptedPrompter(['br']);
    expect((await run(['onboarding', 'complete', '--name', 'Sam'], { prompter })).code).toBe(0);
    expect(prompter.asked[0]).toContain('Which country are you taxed in?');
    expect(sent('POST', '/v1/onboarding/complete')).toMatchObject({ tax_residency: 'BR' });

    // Not asked when nobody can answer, and never guessed: the reply says how to set it.
    const unattended = await run(['onboarding', 'complete', '--name', 'Sam']);
    expect(sent('POST', '/v1/onboarding/complete')).not.toHaveProperty('tax_residency');
    expect(unattended.stderr).toContain('salli profile set --tax-residency');

    for (const bad of [['--tax-residency', 'Kenya'], ['--tax-id', 'PIN=1'], ['--tax-id', 'KE-PIN=']]) {
      expect((await run(['onboarding', 'complete', '--name', 'Sam', ...bad])).code).toBe(2);
    }
  });

  it('refuses an income source the server would quietly ignore', async () => {
    const result = await run(['onboarding', 'complete', '--name', 'Sam', '--income', 'employment,lottery']);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('lottery');
    expect(mock.requestsTo('POST', '/v1/onboarding/complete')).toHaveLength(0);
  });
});

describe('the rest of the fact-find', () => {
  it('posts opening balances as strings, and refuses anything but an asset or a liability', async () => {
    mock.on('POST', '/v1/onboarding/balance-sheet', () => ({ status: 200, body: { entries_created: ['e1', 'e2'] } }));
    const result = await run(['profile', 'balance-sheet', '--balance', '1100:Checking:asset:2,500.00', '--balance', '2100:Car loan:liability:8400']);
    expect(result.code).toBe(0);
    expect(result.stderr).toContain('Posted 2 opening-balance entries.');
    expect(sent('POST', '/v1/onboarding/balance-sheet')).toEqual({
      balances: [
        { code: '1100', name: 'Checking', type: 'asset', amount: '2500.00' },
        { code: '2100', name: 'Car loan', type: 'liability', amount: '8400' },
      ],
    });
    expect((await run(['profile', 'balance-sheet', '--balance', '5000:Food:expense:10'])).code).toBe(2);
    expect((await run(['profile', 'balance-sheet', '--balance', '1100:Checking'])).code).toBe(2);
  });

  it('posts income sources, naming the deposit account only when asked', async () => {
    mock.on('POST', '/v1/onboarding/income', () => ({ status: 200, body: { entries_created: ['e1'] } }));
    await run(['profile', 'income', '--income', '4100:Salary:5000']);
    expect(sent('POST', '/v1/onboarding/income')).toEqual({ incomes: [{ code: '4100', name: 'Salary', amount: '5000' }] });
    await run(['profile', 'income', '--income', '4100:Salary:5000.25', '--deposit-code', '1100', '--deposit-name', 'Checking']);
    expect(sent('POST', '/v1/onboarding/income')).toEqual({
      incomes: [{ code: '4100', name: 'Salary', amount: '5000.25', deposit_account_code: '1100', deposit_account_name: 'Checking' }],
    });
  });

  it('submits the risk questionnaire and shows the score the server gave', async () => {
    mock.on('POST', '/v1/onboarding/risk-questionnaire', () => ({
      status: 200,
      body: {
        score: 14,
        category: 'balanced',
        breakdown: { time_horizon: 4, drawdown_reaction: 3, income_stability: 3, investment_experience: 2, dependents: 2 },
      },
    }));
    const result = await run(['profile', 'risk', '--horizon', '15', '--drawdown', 'hold', '--income-stability', 'stable', '--experience', 'some']);
    expect(sent('POST', '/v1/onboarding/risk-questionnaire')).toEqual({
      time_horizon_years: 15,
      drawdown_reaction: 'hold',
      income_stability: 'stable',
      investment_experience: 'some',
      dependents_count: 0,
    });
    expect(result.stdout).toContain('Risk score 14 (balanced)');
    expect((await run(['profile', 'risk', '--horizon', '15', '--drawdown', 'panic', '--income-stability', 'stable', '--experience', 'some'])).code).toBe(2);
  });
});

describe('deleting your account', () => {
  beforeEach(() => {
    mock.user = { user_id: 'user-123', email: 'sam@example.com' };
    mock.on('DELETE', '/v1/onboarding/account', () => ({ status: 200, body: { deleted: true, counts: { journal_entries: 12, accounts: 9 } } }));
  });

  it('needs the email typed out, and a script must pass it', async () => {
    const script = await run(['profile', 'delete-account']);
    expect(script.code).toBe(2);
    expect(script.stderr).toContain('--confirm-email');

    const typo = await run(['profile', 'delete-account'], { prompter: new ScriptedPrompter(['sam@exampel.com']) });
    expect(typo.code).toBe(2);
    expect(mock.requestsTo('DELETE', '/v1/onboarding/account')).toHaveLength(0);
  });

  it('deletes once the email matches, sending it for the server to check too', async () => {
    const result = await run(['profile', 'delete-account', '--confirm-email', 'Sam@Example.com', '--json']);
    expect(result.code).toBe(0);
    expect(sent('DELETE', '/v1/onboarding/account')).toEqual({ confirm_email: 'Sam@Example.com' });
    expect(JSON.parse(result.stdout)).toEqual({ deleted: true, counts: { journal_entries: 12, accounts: 9 } });
  });
});

describe('the monthly briefing', () => {
  const draft: BriefingPrepared = {
    thread_id: 'thread-1',
    error: '',
    briefing: {
      summary: 'A steady month.',
      fire_tier_assessment: 'Lean FI is 9 years away.',
      recommendations: [
        { title: 'Top up the emergency fund', rationale: 'Five months covered', category: 'savings', priority: 1, bucket_key: null, action: { type: 'none', label: '', due_in_days: null } },
      ],
    },
  };
  beforeEach(() => {
    mock.on('POST', '/v1/advisor/briefing/prepare', () => ({ status: 200, body: draft }));
    mock.on('POST', '/v1/advisor/briefing/resume', (req) => ({
      status: 200,
      body: (req.json as { decision: string }).decision === 'approve' ? { report: { id: 'report-123456789' }, error: '' } : { report: {}, error: 'Briefing not approved (decision: reject)' },
    }));
  });

  it('shows the draft and saves it when you approve', async () => {
    const prompter = new ScriptedPrompter(['approve']);
    const result = await run(['advisor', 'briefing'], { prompter });
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Top up the emergency fund');
    expect(result.stderr).toContain('Saved as advisor report report-1');
    expect(sent('POST', '/v1/advisor/briefing/resume')).toEqual({ thread_id: 'thread-1', decision: 'approve' });
  });

  it('gives a script the draft to decide on later, then decides without drafting again', async () => {
    const drafted = await run(['advisor', 'briefing', '--json']);
    expect(JSON.parse(drafted.stdout)).toEqual(draft);
    expect(mock.requestsTo('POST', '/v1/advisor/briefing/resume')).toHaveLength(0);

    const decided = await run(['advisor', 'briefing', '--thread', 'thread-1', '--decision', 'reject', '--json']);
    expect(decided.code).toBe(0);
    expect(mock.requestsTo('POST', '/v1/advisor/briefing/prepare')).toHaveLength(1);
    expect(sent('POST', '/v1/advisor/briefing/resume')).toEqual({ thread_id: 'thread-1', decision: 'reject' });
  });

  it('refuses a thread without a decision', async () => {
    expect((await run(['advisor', 'briefing', '--thread', 'thread-1'])).code).toBe(2);
  });
});
