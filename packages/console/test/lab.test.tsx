/**
 * The decision lab (docs/design/console.md, section 5, C3) on what the real
 * server answers for the golden household (fixtures/lab.ts): templates
 * asked and run, a decision recorded after a confirmation, scenarios run
 * and compared, principles kept and refused, the journal with its notes and
 * reviews. Every figure the server's, shown exactly; nothing ranked.
 */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { visibleAmount } from '../src/kit/Money';
import { MockApi } from './fixtures/api';
import * as lab from './fixtures/lab';
import { setup } from './harness';

const region = (name: string | RegExp): HTMLElement => screen.getByRole('region', { name });
const bodies = (api: MockApi, path: string, method = 'POST'): Array<Record<string, unknown>> =>
  api.to(path, method).map((r) => JSON.parse(r.body) as Record<string, unknown>);

async function click(element: HTMLElement): Promise<void> {
  await act(async () => {
    fireEvent.click(element);
  });
}

function type(element: HTMLElement, value: string): void {
  fireEvent.change(element, { target: { value } });
}

describe('the lab', () => {
  it('opens on the templates and what is due for review', async () => {
    await setup({ path: '/console/decide' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Decide' })).toBeTruthy();
    const due = region('Due for review');
    expect(await within(due).findByRole('link', { name: 'Review “Change anything?”' })).toBeTruthy();
    const templates = region('Templates');
    expect(await within(templates).findByRole('link', { name: 'Rent or buy' })).toBeTruthy();
    expect(screen.getByRole('navigation', { name: 'Decision lab' })).toBeTruthy();
  });
});

describe('a template', () => {
  it('asks its questions from the schema, with each default and where it comes from', async () => {
    await setup({ path: '/console/decide/templates/afford-it' });
    const answers = await screen.findByRole('region', { name: 'Your answers' });
    expect(within(answers).getByRole('textbox', { name: 'What does it cost?' })).toBeTruthy();
    // A default says what it is and where it comes from.
    expect(within(answers).getByText('Left out: The purchase, a plain name for it.')).toBeTruthy();
    expect(within(answers).getByText(/Left out: 2026-10-11, the as-of date/)).toBeTruthy();
    // The account is one of the person's cash accounts, by name.
    const account = within(answers).getByRole('combobox', { name: /Which cash account would it come out of\?/ });
    await waitFor(() => expect(within(account).getAllByRole('option').map((o) => o.textContent)).toEqual(['Your cash as a whole', 'Checking', 'Savings']));
    // A question asked only once another is answered.
    expect(within(answers).queryByRole('textbox', { name: 'At what yearly rate?' })).toBeNull();
    type(within(answers).getByRole('textbox', { name: /Over how many months\?/ }), '12');
    expect(await within(answers).findByRole('textbox', { name: 'At what yearly rate?' })).toBeTruthy();
  });

  it('finds what it can’t read before asking Salli, at each answer', async () => {
    const { api } = await setup({ path: '/console/decide/templates/afford-it' });
    const answers = await screen.findByRole('region', { name: 'Your answers' });
    type(within(answers).getByRole('textbox', { name: /Over how many months\?/ }), 'twelve');
    await click(within(answers).getByRole('button', { name: 'Build and compare the options' }));
    expect(await within(answers).findByRole('alert')).toBeTruthy();
    expect(within(answers).getAllByText('This one needs an answer.').length).toBe(2);
    expect(within(answers).getByText('Write a whole number, like 12.')).toBeTruthy();
    expect(api.to('/v1/decisions/start')).toHaveLength(0);
  });

  it('shows what Salli refused at each answer’s place', async () => {
    const api = new MockApi();
    api.overrides.push((r) => (r.path === '/v1/decisions/start' ? { status: 422, body: lab.START_REFUSED } : undefined));
    await setup({ api, path: '/console/decide/templates/afford-it' });
    const answers = await screen.findByRole('region', { name: 'Your answers' });
    type(within(answers).getByRole('textbox', { name: 'What does it cost?' }), '2400');
    await click(within(answers).getByRole('button', { name: 'Build and compare the options' }));
    expect((await within(answers).findAllByText('is required: What does it cost?')).length).toBeGreaterThan(0);
    // At the answer it is about.
    const price = within(answers).getByRole('textbox', { name: 'What does it cost?' });
    expect(price.getAttribute('aria-invalid')).toBe('true');
    expect(within(answers).getByText('Not answers Salli can build options from')).toBeTruthy();
  });

  it('sends the answers in the API’s formats, and lays out what Salli built', async () => {
    const { api } = await setup({ path: '/console/decide/templates/afford-it' });
    const answers = await screen.findByRole('region', { name: 'Your answers' });
    type(within(answers).getByRole('textbox', { name: 'What does it cost?' }), '2,400.00');
    type(within(answers).getByRole('textbox', { name: /What is it\?/ }), 'Laptop');
    type(within(answers).getByLabelText(/When would you pay\?/), '2026-11-02');
    fireEvent.change(within(answers).getByRole('combobox', { name: /Which cash account/ }), { target: { value: 'chk' } });
    type(within(answers).getByRole('textbox', { name: /Over how many months\?/ }), '12');
    type(await within(answers).findByRole('textbox', { name: 'At what yearly rate?' }), '6.9%');
    type(within(answers).getByRole('textbox', { name: /For how many months\?|Could you wait\?/ }), '6');
    type(await within(answers).findByRole('textbox', { name: /How much of your monthly surplus/ }), '400');
    type(within(answers).getByRole('textbox', { name: /How many years ahead/ }), '5');
    await click(within(answers).getByRole('button', { name: 'Build and compare the options' }));
    await screen.findByRole('heading', { name: 'What Salli built' });
    expect(bodies(api, '/v1/decisions/start')[0]).toEqual({
      template: 'afford-it',
      answers: {
        price: '2400.00',
        what: 'Laptop',
        date: '2026-11-02',
        account: 'chk',
        instalment_months: 12,
        instalment_rate: '0.069',
        wait_months: 6,
        save_monthly: '400',
        horizon_years: 5,
      },
    });
    // The options, in the template's order.
    const options = region('The options');
    expect(within(options).getAllByText(/^(Pay cash|Spread over 12 months|Wait 6 months)$/).map((e) => e.textContent)).toEqual([
      'Pay cash',
      'Spread over 12 months',
      'Wait 6 months',
    ]);
    // Side by side, exactly as the server computed.
    const side = region('Side by side');
    const lowest = lab.AFFORD_IT_START.comparison.options[0]?.cash.lowest.scenario;
    expect(lowest).toBe('11598.91');
    expect(within(side).getAllByText('11,598.91').length).toBeGreaterThan(0);
    // The trade, each pair once.
    const trade = region('What each gains and gives up');
    expect(within(trade).getByRole('heading', { name: 'Pay cash against Spread over 12 months' })).toBeTruthy();
    expect(within(trade).queryByRole('heading', { name: 'Spread over 12 months against Pay cash' })).toBeNull();
    // The break-evens, in Salli's words.
    const turns = region('Where the answer turns');
    expect(within(turns).getByText(/Pay cash ends the horizon with more net worth than Spread over 12 months/)).toBeTruthy();
    // Principles kept and broken, in words.
    const checks = region('Your principles');
    expect(within(checks).getAllByText(/Keeps|Breaks|Can’t tell/).length).toBeGreaterThan(0);
    // Placeholders, in view.
    expect(within(region('What these figures rest on')).getByText(/The real return \(a placeholder\)/)).toBeTruthy();
    // The answers as used, with where each came from.
    expect(within(region('The answers used')).getAllByText('your answer').length).toBe(9);
  });

  it('shows rent or buy’s level reading and the growth at which the answer turns', async () => {
    await setup({ path: '/console/decide/templates/rent-or-buy' });
    const answers = await screen.findByRole('region', { name: 'Your answers' });
    // Growth defaults are placeholders, labelled so.
    expect(within(answers).getAllByText(/a placeholder, not a forecast/).length).toBe(2);
    type(within(answers).getByRole('textbox', { name: 'What would the home cost?' }), '350000');
    type(within(answers).getByRole('textbox', { name: 'How much would you put down?' }), '70000');
    type(within(answers).getAllByRole('textbox', { name: 'Its yearly rate' })[0] as HTMLElement, '4.2%');
    type(within(answers).getAllByRole('textbox', { name: 'Its term, in months' })[0] as HTMLElement, '300');
    type(within(answers).getByRole('textbox', { name: /What would buying cost, once/ }), '9000');
    type(within(answers).getByRole('textbox', { name: /What would owning cost a month/ }), '250');
    type(within(answers).getByRole('textbox', { name: /What would selling the home cost/ }), '3%');
    fireEvent.change(within(answers).getByRole('combobox', { name: /Which of your recurring payments is your rent/ }), { target: { value: 'city' } });
    await click(within(answers).getByRole('button', { name: 'Build and compare the options' }));
    const level = await screen.findByRole('region', { name: 'When buying draws level' });
    expect(within(level).getByText('Nov 2031')).toBeTruthy();
    const turns = region('Where the answer turns');
    expect(within(turns).getAllByText(/a growth of -1.46% a year beyond inflation/).length).toBeGreaterThan(0);
    expect(within(region('What these figures rest on')).getByText(/An asset’s growth/)).toBeTruthy();
  });
});

describe('recording a decision', () => {
  it('asks for the person’s reasons and choice, confirms, records, and the journal shows it', async () => {
    const api = new MockApi();
    api.lab.withoutLaptop();
    await setup({ api, path: '/console/decide/templates/afford-it' });
    const answers = await screen.findByRole('region', { name: 'Your answers' });
    type(within(answers).getByRole('textbox', { name: 'What does it cost?' }), '2400');
    await click(within(answers).getByRole('button', { name: 'Build and compare the options' }));
    const record = await screen.findByRole('region', { name: 'Record what you choose' });
    // Nothing is offered as chosen: recording is asked for.
    await click(within(record).getByRole('button', { name: 'Record a decision' }));
    const radios = within(record).getAllByRole('radio') as HTMLInputElement[];
    expect(radios.map((r) => r.checked)).toEqual([false, false, false]);
    await click(within(record).getByRole('button', { name: 'Record it' }));
    expect(within(record).getByText('Choose the option you chose.')).toBeTruthy();
    expect(within(record).getByText('Write your reasons, in your own terms.')).toBeTruthy();
    expect(api.to('/v1/decisions', 'POST')).toHaveLength(0);

    await click(within(record).getByRole('radio', { name: 'Pay cash' }));
    type(within(record).getByRole('textbox', { name: /Why\? In your own words/ }), 'The old one is failing.');
    type(within(record).getByLabelText(/When do you want to look back on it\?/), '2027-04-30');
    await click(within(record).getByRole('button', { name: 'Record it' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Record this decision?' });
    expect(within(dialog).getByText('The old one is failing.')).toBeTruthy();
    expect(within(dialog).getByText(/can’t be edited or deleted afterwards/)).toBeTruthy();
    await click(within(dialog).getByRole('button', { name: 'Record' }));
    expect(await within(record).findByText(/Recorded\. Salli will remind you to review it on Apr 30, 2027\./)).toBeTruthy();
    const sent = bodies(api, '/v1/decisions')[0];
    expect(sent).toMatchObject({ chosen: 'Pay cash', reasons: 'The old one is failing.', review_on: '2027-04-30' });
    expect(sent?.options).toEqual(lab.AFFORD_IT_START.record.options);

    await click(within(record).getByRole('link', { name: 'Open it in your journal' }));
    expect(await screen.findByRole('heading', { level: 1, name: lab.AFFORD_IT_START.record.question })).toBeTruthy();
  });
});

describe('the journal', () => {
  it('lists the entries with their status, and what is due', async () => {
    await setup({ path: '/console/decide/journal' });
    const entries = await screen.findByRole('region', { name: 'Entries' });
    expect(await within(entries).findByRole('link', { name: 'Laptop: pay cash, spread it or wait?' })).toBeTruthy();
    expect(within(entries).getByText('Review due')).toBeTruthy();
    expect(within(entries).getByText('Awaiting review')).toBeTruthy();
  });

  it('downloads the journal on this device, as JSON and as Markdown', async () => {
    const saved: Array<{ name: string; type: string }> = [];
    const created = vi.spyOn(URL, 'createObjectURL').mockImplementation((blob) => {
      saved.push({ name: '', type: (blob as Blob).type });
      return 'blob:fixture';
    });
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    const clicked = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      const last = saved[saved.length - 1];
      if (last) last.name = this.download;
    });
    const { api } = await setup({ path: '/console/decide/journal' });
    const exporting = await screen.findByRole('region', { name: 'Export' });
    await click(within(exporting).getByRole('button', { name: 'Save as JSON' }));
    await waitFor(() => expect(saved).toHaveLength(1));
    await click(within(exporting).getByRole('button', { name: 'Save as Markdown' }));
    await waitFor(() => expect(saved).toHaveLength(2));
    expect(saved.map((s) => s.type)).toEqual(['application/json', 'text/markdown']);
    expect(saved.map((s) => s.name)).toEqual([expect.stringMatching(/^salli-decisions-\d{4}-\d{2}-\d{2}\.json$/), expect.stringMatching(/\.md$/)]);
    expect(api.to('/v1/decisions/export', 'GET')).toHaveLength(1);
    created.mockRestore();
    clicked.mockRestore();
  });

  it('shows an entry with its hash, reasons and notes, and adds a note after asking', async () => {
    const { api } = await setup({ path: `/console/decide/journal/${lab.DECISION.id}` });
    expect(await screen.findByRole('heading', { level: 1, name: lab.DECISION.entry.question })).toBeTruthy();
    const entry = region('The entry');
    expect(within(entry).getByText(lab.DECISION.hash)).toBeTruthy();
    expect(within(entry).getByText('Unchanged since it was recorded')).toBeTruthy();
    expect(within(region('Your reasons')).getByText(lab.DECISION.entry.reasons)).toBeTruthy();
    const notes = region('Notes');
    expect(within(notes).getByText('The shop held the price until November.')).toBeTruthy();
    type(within(notes).getByRole('textbox', { name: /The note/ }), 'Bought it on the 2nd.');
    await click(within(notes).getByRole('button', { name: 'Add the note' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Add this note?' });
    await click(within(dialog).getByRole('button', { name: 'Add the note' }));
    expect(await within(region('Notes')).findByText('Bought it on the 2nd.')).toBeTruthy();
    expect(bodies(api, `/v1/decisions/${lab.DECISION.id}/notes`)).toEqual([{ text: 'Bought it on the 2nd.' }]);
  });

  it('reviews a decision that is due: projected beside what happened, then the reflection', async () => {
    const { api } = await setup({ path: `/console/decide/journal/${lab.DECISION_DUE.id}` });
    const review = await screen.findByRole('region', { name: 'Look back on it' });
    const comparison = REVIEW_COMPARISON();
    expect((await within(review).findAllByText(new RegExp(`What ${comparison.option} projected for`))).length).toBeGreaterThan(0);
    type(within(review).getByRole('textbox', { name: /What do you make of how it turned out\?/ }), 'Nothing needed changing.');
    await click(within(review).getByRole('button', { name: 'Add my review' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Add this review?' });
    await click(within(dialog).getByRole('button', { name: 'Add my review' }));
    await waitFor(() => expect(bodies(api, `/v1/decisions/${lab.DECISION_DUE.id}/review`)).toEqual([{ reflection: 'Nothing needed changing.' }]));
    expect(await screen.findByRole('region', { name: 'Reviews' })).toBeTruthy();
  });
});

function REVIEW_COMPARISON() {
  const due = (lab.DECISION_REVIEWED.reviews[0]?.review.comparison ?? null) as { option: string } | null;
  if (!due) throw new Error('no review in the fixtures');
  return due;
}

describe('principles', () => {
  it('lists those in use with the baseline’s check, and the figures a check may read', async () => {
    await setup({ path: '/console/decide/principles' });
    const inUse = await screen.findByRole('region', { name: 'In use' });
    expect(await within(inUse).findByText('Six months of essentials in cash')).toBeTruthy();
    expect(within(inUse).getByText('Checking above 5,000')).toBeTruthy();
    expect(within(inUse).getByText(/1 archived/)).toBeTruthy();
    const figures = region('The figures a check may read');
    expect(await within(figures).findByText('emergency_months')).toBeTruthy();
    expect(within(figures).getByText(/33 figures/)).toBeTruthy();
  });

  it('shows Salli’s refusal of a check at the check, with where it fails', async () => {
    const api = new MockApi();
    api.overrides.push((r) => (r.method === 'POST' && r.path === '/v1/principles' ? { status: 422, body: lab.PRINCIPLE_REFUSED } : undefined));
    await setup({ api, path: '/console/decide/principles' });
    const add = await screen.findByRole('region', { name: 'Add a principle' });
    type(within(add).getByRole('textbox', { name: /The principle, in your words/ }), 'Half a year in cash');
    type(within(add).getByRole('textbox', { name: /Its check/ }), 'emergency_month >= 6');
    await click(within(add).getByRole('button', { name: 'Keep it' }));
    expect(await within(add).findAllByText(/There is no figure 'emergency_month'\. Did you mean emergency_months\?/)).toBeTruthy();
    const check = within(add).getByRole('textbox', { name: /Its check/ });
    expect(check.getAttribute('aria-invalid')).toBe('true');
  });

  it('adds, edits and archives (after asking)', async () => {
    const { api } = await setup({ path: '/console/decide/principles' });
    const add = await screen.findByRole('region', { name: 'Add a principle' });
    type(within(add).getByRole('textbox', { name: /The principle, in your words/ }), 'Never below 2,000 in checking');
    type(within(add).getByRole('textbox', { name: /Its check/ }), 'account_lowest >= 2000');
    fireEvent.change(within(add).getByRole('combobox', { name: /The cash account account_lowest reads/ }), { target: { value: 'chk' } });
    await click(within(add).getByRole('button', { name: 'Keep it' }));
    expect(await screen.findByText(/Kept “Never below 2,000 in checking”\./)).toBeTruthy();
    expect(bodies(api, '/v1/principles')).toEqual([{ label: 'Never below 2,000 in checking', check: 'account_lowest >= 2000', account: 'chk' }]);

    const inUse = region('In use');
    await click(within(inUse).getByRole('button', { name: 'Archive “Checking above 5,000”' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Archive this principle?' });
    await click(within(dialog).getByRole('button', { name: 'Archive' }));
    expect(await screen.findByText(/Archived “Checking above 5,000”/)).toBeTruthy();
  });
});

describe('scenarios', () => {
  it('builds an option from changes, runs it with its timelines, and draws them', async () => {
    const { api } = await setup({ path: '/console/decide/scenarios' });
    const form = (await screen.findAllByRole('group', { name: 'Option 1' }))[0] as HTMLElement;
    type(within(form).getByRole('textbox', { name: 'What to call it' }), 'Pay cash');
    fireEvent.change(within(form).getByRole('combobox', { name: 'Kind of change' }), { target: { value: 'one_off' } });
    await click(within(form).getByRole('button', { name: 'Add a change' }));
    const change = within(form).getByRole('group', { name: /Change 1/ });
    type(within(change).getByRole('textbox', { name: 'What to call it' }), 'Laptop');
    type(within(change).getByLabelText('On'), '2026-11-02');
    type(within(change).getByRole('textbox', { name: /Amount/ }), '-2400.00');
    fireEvent.change(within(change).getByRole('combobox', { name: /Cash account/ }), { target: { value: 'chk' } });
    type(screen.getByRole('textbox', { name: 'Years the long-run figures run' }), '5');
    await click(screen.getByRole('button', { name: 'Run it' }));
    await screen.findByRole('heading', { name: 'What it does', level: 2 });
    const run = api.to('/v1/scenarios/run', 'POST')[0];
    expect(run?.search).toBe('?timeline=true');
    expect(JSON.parse(run?.body ?? '{}')).toEqual({
      schema: 'salli.scenario/1',
      label: 'Pay cash',
      horizon_years: 5,
      changes: [{ type: 'one_off', label: 'Laptop', date: '2026-11-02', amount: '-2400.00', account: 'chk' }],
    });
    const cash = region('Cash, day by day');
    expect(within(cash).getAllByRole('img')[0]?.getAttribute('aria-label')).toContain('The baseline’s lowest is EUR 13,998.91');
    expect(region('Net worth, month by month')).toBeTruthy();
  });

  it('compares options, in the order added, with the trade and the sensitivity', async () => {
    const { api } = await setup({ path: '/console/decide/scenarios' });
    await screen.findAllByRole('group', { name: 'Option 1' });
    await click(screen.getByRole('button', { name: 'Add an option' }));
    expect(screen.getByRole('button', { name: 'Compare the 2 options' })).toBeTruthy();
    await click(screen.getByRole('button', { name: 'Compare the 2 options' }));
    await screen.findByRole('heading', { name: 'The options compared', level: 2 });
    expect(api.to('/v1/scenarios/compare', 'POST')[0]?.search).toBe('?timeline=true');
    expect(region('How the answer moves with the return')).toBeTruthy();
    expect(region('What each gains and gives up')).toBeTruthy();
  });

  it('runs a scenario document as written', async () => {
    const { api } = await setup({ path: '/console/decide/scenarios' });
    const form = (await screen.findAllByRole('group', { name: 'Option 1' }))[0] as HTMLElement;
    const doc = '{"schema": "salli.scenario/1", "label": "Doc", "changes": [{"type": "one_off", "date": "2026-11-02", "amount": "-2400.00", "label": "Laptop"}]}';
    type(within(form).getByRole('textbox', { name: 'Scenario document (JSON)' }), doc);
    await click(within(form).getByRole('button', { name: 'Use this document' }));
    await click(screen.getByRole('button', { name: 'Run it' }));
    await screen.findByRole('heading', { name: 'What it does', level: 2 });
    expect(JSON.parse(api.to('/v1/scenarios/run', 'POST')[0]?.body ?? '{}')).toEqual(JSON.parse(doc));
  });
});

describe('the baseline', () => {
  it('draws cash and net worth, and flags each placeholder', async () => {
    await setup({ path: '/console/decide/baseline' });
    const cash = await screen.findByRole('region', { name: 'Cash, the next twelve months' });
    const low = visibleAmount(lab.BASELINE.cash.lowest, 'EUR', 'prose', { locale: 'en-US' });
    expect(within(cash).getAllByRole('img')[0]?.getAttribute('aria-label')).toContain(`Lowest: ${low}`);
    const assumptions = region('Assumptions');
    // The years drawn down have no row: the withdrawal rate's source names them.
    expect(within(assumptions).getAllByText('Placeholder').length).toBe(lab.BASELINE.assumptions.placeholders.filter((p) => p !== 'drawdown_horizon').length);
    expect(region('Income and spending')).toBeTruthy();
  });
});
