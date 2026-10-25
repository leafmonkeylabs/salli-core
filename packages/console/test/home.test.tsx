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
const figure = (name: string): HTMLElement => screen.getByRole('group', { name });

describe('Home', () => {
  it('shows where the household stands, as the server computed it', async () => {
    await setup();
    expect(await screen.findByRole('heading', { level: 1, name: 'Home' })).toBeTruthy();

    // The key figures, each the server's.
    const netWorth = figure('Net worth');
    expect(home.BALANCE_SHEET.net_worth).toBe('335901.47');
    await waitFor(() => expect(within(netWorth).getByText('335,901.47')).toBeTruthy());
    expect(within(netWorth).getByText('335,901.47 euros')).toBeTruthy();
    expect(within(netWorth).getByText('As of Oct 11, 2026, from your ledger')).toBeTruthy();
    expect(within(netWorth).getByText('EUR 354,493.15')).toBeTruthy();

    const safeFigure = figure('Free until payday');
    await waitFor(() => expect(within(safeFigure).getByText('15,316.35')).toBeTruthy());
    expect(within(safeFigure).getByText('until Oct 25, 2026')).toBeTruthy();

    const month = figure('October 2026 so far');
    // A negative key figure: in brackets, as a statement shows it, and read out with its sign.
    await waitFor(() => expect(within(month).getByText('(1,750.99)')).toBeTruthy());
    expect(within(month).getByText('minus 1,750.99 euros')).toBeTruthy();

    const fiFigure = figure('Financial independence');
    await waitFor(() => expect(within(fiFigure).getByText('56.42')).toBeTruthy());
    expect(within(fiFigure).getByText('FI score · On track')).toBeTruthy();

    // Free until payday line by line: the server's figure under the double rule.
    const safe = section('Free until payday, line by line');
    await waitFor(() => expect(within(safe).getByText('EUR 15,801.47')).toBeTruthy());
    expect(within(safe).getByText('EUR (74.45)')).toBeTruthy();
    expect(within(safe).getByText('EUR 206.96')).toBeTruthy();
    expect(within(safe).getByText('EUR 203.71')).toBeTruthy();
    // Nothing is set aside for goals in this household: no line for it.
    expect(within(safe).queryByText('Less cash set aside for goals')).toBeNull();
    expect(within(safe).getByText('Free until payday').closest('.row-total')).toBeTruthy();
    expect(within(safe).getByText('USD at 0.86, ecb, Oct 9, 2026')).toBeTruthy();

    const spent = section('Spent in October 2026');
    await waitFor(() => expect(within(spent).getByText('Rent')).toBeTruthy());
    expect(within(spent).getByText('EUR 1,750.99')).toBeTruthy();

    const parts = section('What the FI score is made of');
    await waitFor(() => expect(within(parts).getByText(/Placeholder assumptions/)).toBeTruthy());
    expect(within(parts).getByText('3.5% of the way to financial independence')).toBeTruthy();
    // Each part says what it is on screen, not only on hover; placeholders link to where they are set.
    expect(within(parts).getByText('Saving 49.07% of income')).toBeTruthy();
    expect(within(parts).getByRole('link', { name: 'Set your own on Independence' }).getAttribute('href')).toBe('/console/fi#assumptions');

    const attention = section('Needs attention');
    await waitFor(() => expect(within(attention).getByText('A decision is ready for review')).toBeTruthy());
    await waitFor(() => expect(within(attention).getByText('Send the landlord the signed lease')).toBeTruthy());
    // Oct 5 is before Oct 11: overdue, in words as well as colour.
    const lease = within(attention).getByText('Send the landlord the signed lease').closest('li') as HTMLElement;
    expect(within(lease).getByText('Overdue')).toBeTruthy();
    await waitFor(() => expect(within(attention).getByText('Change anything?')).toBeTruthy());
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
    expect(last?.net_worth).toBe('335901.47');
    expect(within(chart).getAllByRole('img')[0]?.getAttribute('aria-label')).toContain('EUR 335,901.47 in Oct 2026');
    // A month read off the chart: the list picks it, the server's figures beside it.
    const months = within(chart).getByRole('combobox', { name: 'Month shown' }) as HTMLSelectElement;
    expect(months.value).toBe(last?.month);
    fireEvent.change(months, { target: { value: home.NET_WORTH.points[0]?.month } });
    expect(months.value).toBe(home.NET_WORTH.points[0]?.month);
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
    const fi = section('What the FI score is made of');
    expect(await within(fi).findByText('Scoring unavailable')).toBeTruthy();
    expect(within(fi).getByText('The FI engine is busy. Try again in a minute.')).toBeTruthy();
    expect(within(fi).getByText(/Request req-42/)).toBeTruthy();
    expect(within(fi).getByRole('button', { name: 'Try again' })).toBeTruthy();
    await waitFor(() => expect(within(figure('Net worth')).getByText('335,901.47')).toBeTruthy());
  });

  it('shows no FI score until two months of data are behind it', async () => {
    const api = new MockApi();
    api.overrides.push((r) => (r.path === '/v1/fi/score' ? { status: 200, body: { ...home.FI_SCORE, status: 'not_enough_data', months_observed: 1 } } : undefined));
    await setup({ api });
    const fiFigure = figure('Financial independence');
    expect(await within(fiFigure).findByText('Needs two months of data')).toBeTruthy();
    expect(within(fiFigure).queryByText('56.42')).toBeNull();
    expect(within(fiFigure).queryByText('FI score · On track')).toBeNull();
  });

  it('says plainly when there is nothing yet', async () => {
    const api = new MockApi();
    api.reads['/v1/insights/signals'] = { signals: [] };
    api.reads['/v1/reminders/'] = { reminders: [] };
    api.reads['/v1/decisions/reviews'] = { as_of: '2026-10-11', reviews: [] };
    await setup({ api });
    const attention = section('Needs attention');
    expect(await within(attention).findByText('Nothing needs attention.')).toBeTruthy();
    expect(await within(attention).findByText('Nothing due.')).toBeTruthy();
    expect(await within(attention).findByText('No decision is due for review.')).toBeTruthy();
  });

  it('copies a prompt for your own AI, and sends nothing', async () => {
    const written: string[] = [];
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: async (text: string) => void written.push(text) }, configurable: true });
    const { api } = await setup();
    await within(figure('Net worth')).findByText('335,901.47');
    const before = api.requests.length;
    fireEvent.click(screen.getByRole('button', { name: 'Copy a prompt for your AI' }));
    await screen.findAllByText(/Copied\./);
    expect(written[0]).toContain('as of 2026-10-11');
    expect(written[0]).toContain('never compute');
    expect(api.requests.length).toBe(before);
  });
});
