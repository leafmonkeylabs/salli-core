/**
 * Home, on what the real server answers for the golden household
 * (fixtures/home.ts): `salli status` as a page, every figure the API's,
 * shown exactly, with its provenance; each section on its own.
 */
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MockApi, problem } from './fixtures/api';
import * as home from './fixtures/home';
import { setup } from './harness';

const section = (name: string): HTMLElement => screen.getByRole('region', { name });

describe('Home', () => {
  it('shows where the household stands, as the server computed it', async () => {
    await setup();
    expect(await screen.findByRole('heading', { level: 1, name: 'Home' })).toBeTruthy();

    const netWorth = section('Net worth');
    expect(home.BALANCE_SHEET.net_worth).toBe('344026.47');
    await waitFor(() => expect(within(netWorth).getByText('EUR 344,026.47')).toBeTruthy());
    expect(within(netWorth).getByText('As of Oct 11, 2026, from your ledger')).toBeTruthy();

    const safe = section('Safe to spend');
    await waitFor(() => expect(within(safe).getByText(`EUR 15,727.02`)).toBeTruthy());
    expect(within(safe).getByText('until Oct 25, 2026')).toBeTruthy();
    expect(within(safe).getByText('USD at 0.86, ecb, Oct 9, 2026')).toBeTruthy();

    const month = section('October 2026 so far');
    await waitFor(() => expect(within(month).getByText('Net income')).toBeTruthy());
    // A negative in a statement: in brackets, and read out with its sign.
    expect(within(month).getByText('EUR (1,750.99)')).toBeTruthy();
    expect(within(month).getByText('minus 1,750.99 euros')).toBeTruthy();
    expect(within(month).getByText('Most spent on')).toBeTruthy();

    const fi = section('Financial independence');
    await waitFor(() => expect(within(fi).getByText('60.08')).toBeTruthy());
    expect(within(fi).getByText(/Placeholder assumptions/)).toBeTruthy();
    expect(within(fi).getByText('5.9% of the way to financial independence')).toBeTruthy();

    const attention = section('Needs attention');
    await waitFor(() => expect(within(attention).getByText('A decision is ready for review')).toBeTruthy());

    const coming = section('Coming up');
    await waitFor(() => expect(within(coming).getByText('Send the landlord the signed lease')).toBeTruthy());
    // Oct 5 is before Oct 11: overdue, in words as well as colour.
    const lease = within(coming).getByText('Send the landlord the signed lease').closest('li') as HTMLElement;
    expect(within(lease).getByText('Overdue')).toBeTruthy();

    const reviews = section('Decisions to review');
    await waitFor(() => expect(within(reviews).getByText('Change anything?')).toBeTruthy());
  });

  it('asks for the month so far, and nothing it would have to compute', async () => {
    const { api } = await setup();
    await screen.findByText('Net income');
    const statement = api.to('/v1/ledger/income-statement');
    expect(statement.map((r) => r.search)).toContain('?from_date=2026-10-01&to_date=2026-10-11');
    expect(api.to('/v1/insights/net-worth')[0]?.search).toBe('?months=12');
    expect(api.requests.every((r) => r.method === 'GET' || r.path.startsWith('/mcp/oauth/'))).toBe(true);
  });

  it('draws net worth over time, and shows the same figures as a table', async () => {
    await setup();
    const chart = section('Net worth over time');
    const toggle = await within(chart).findByRole('button', { name: 'Show the figures' });
    const last = home.NET_WORTH.points[home.NET_WORTH.points.length - 1];
    expect(last?.net_worth).toBe('344026.47');
    expect(within(chart).getAllByRole('img')[0]?.getAttribute('aria-label')).toContain('EUR 344,026.47 in Oct 2026');
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    const table = within(chart).getByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(home.NET_WORTH.points.length + 1);
  });

  it('shows a section it could not read as the problem the server described, and the rest anyway', async () => {
    const api = new MockApi();
    api.overrides.push((r) =>
      r.path === '/v1/fi/score'
        ? { status: 503, body: problem(503, 'Scoring unavailable', { detail: 'The FI engine is busy. Try again in a minute.', request_id: 'req-42' }) }
        : undefined,
    );
    await setup({ api });
    const fi = section('Financial independence');
    expect(await within(fi).findByText('Scoring unavailable')).toBeTruthy();
    expect(within(fi).getByText('The FI engine is busy. Try again in a minute.')).toBeTruthy();
    expect(within(fi).getByText(/Request req-42/)).toBeTruthy();
    expect(within(fi).getByRole('button', { name: 'Try again' })).toBeTruthy();
    await waitFor(() => expect(within(section('Net worth')).getByText('EUR 344,026.47')).toBeTruthy());
  });

  it('says plainly when there is nothing yet', async () => {
    const api = new MockApi();
    api.reads['/v1/insights/signals'] = { signals: [] };
    api.reads['/v1/reminders/'] = { reminders: [] };
    api.reads['/v1/decisions/reviews'] = { as_of: '2026-10-11', reviews: [] };
    await setup({ api });
    expect(await within(section('Needs attention')).findByText('Nothing needs attention.')).toBeTruthy();
    expect(await within(section('Coming up')).findByText('Nothing due.')).toBeTruthy();
    expect(await within(section('Decisions to review')).findByText('No decision is due for review.')).toBeTruthy();
  });

  it('copies a prompt for your own AI, and sends nothing', async () => {
    const written: string[] = [];
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: async (text: string) => void written.push(text) }, configurable: true });
    const { api } = await setup();
    await within(section('Net worth')).findByText('EUR 344,026.47');
    const before = api.requests.length;
    fireEvent.click(screen.getByRole('button', { name: 'Think this through with your AI' }));
    await screen.findAllByText(/Copied\./);
    expect(written[0]).toContain('as of 2026-10-11');
    expect(written[0]).toContain('never compute');
    expect(api.requests.length).toBe(before);
  });
});
