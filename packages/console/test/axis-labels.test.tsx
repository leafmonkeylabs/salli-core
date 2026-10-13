/**
 * No chart's axis labels overlap, on every chart the console draws from the
 * server's fixtures: Home's net worth, the decision lab's timelines,
 * baseline, sensitivity and break-evens, Cash's forecast and paired bars,
 * an account's balance, FI's projections.
 *
 * Each chart is drawn twice, a wide drawing (768 and 1280 px) and a phone's
 * (360 px, or any narrow column); both are in the page whatever the screen,
 * so both are checked. Positions and font sizes are in the drawing's own
 * units and the drawing scales as a whole, so labels apart in those units
 * are apart at every width. A label's width is the kit's estimate
 * (`labelWidth`); e2e/where.spec.ts measures the real text in a browser.
 */
import { act, fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { labelWidth } from '../src/kit/chart/ticks';
import { setup } from './harness';

/** The smallest gap between two labels on one line, in the drawing's units. */
const GAP = 4;

interface Extent {
  text: string;
  from: number;
  to: number;
}

function extent(text: SVGTextElement): Extent {
  const read = (name: string): number => JSON.parse(text.getAttribute(name) ?? '0') as number;
  const x = read('x');
  const width = labelWidth(text.textContent ?? '', read('font-size'));
  const anchor = text.getAttribute('text-anchor') ?? 'start';
  const from = anchor === 'middle' ? x - width / 2 : anchor === 'end' ? x - width : x;
  return { text: text.textContent ?? '', from, to: from + width };
}

/** Every pair of axis labels on one line of one drawing that come closer than GAP. */
function collisions(): string[] {
  const found: string[] = [];
  const drawings = [...document.querySelectorAll<SVGSVGElement>('svg.chart-svg')];
  for (const svg of drawings) {
    const lines = new Map<string, Extent[]>();
    for (const text of svg.querySelectorAll<SVGTextElement>('text.chart-tick')) {
      const y = text.getAttribute('y') ?? '';
      lines.set(y, [...(lines.get(y) ?? []), extent(text)]);
    }
    for (const labels of lines.values()) {
      const sorted = labels.sort((a, b) => a.from - b.from);
      sorted.slice(1).forEach((label, i) => {
        const before = sorted[i] as Extent;
        if (label.from < before.to + GAP) found.push(`${svg.getAttribute('aria-label')?.slice(0, 40) ?? svg.className.baseVal}: “${before.text}” and “${label.text}”`);
      });
    }
  }
  return found;
}

async function settle(): Promise<void> {
  await new Promise((r) => setTimeout(r, 50));
  expect(document.querySelectorAll('svg.chart-svg').length).toBeGreaterThan(0);
}

describe('axis labels', () => {
  it.each([
    ['Home', '/console/', 'Net worth over time'],
    ['the baseline', '/console/decide/baseline', 'Assumptions'],
    ['cash', '/console/cash', 'Cash flow by month'],
    ['an account', '/console/books/accounts/chk', 'Balance over time'],
    ['an account in dollars', '/console/books/accounts/usd', 'Balance over time'],
    ['a liability', '/console/books/accounts/card', 'Balance over time'],
    ['financial independence', '/console/fi', 'Projections'],
  ])('on %s never overlap', async (_name, path, section) => {
    await setup({ path });
    await screen.findByRole('region', { name: section });
    await screen.findAllByRole('img');
    await settle();
    expect(collisions()).toEqual([]);
  });

  it('on the lab’s compared timelines never overlap', async () => {
    await setup({ path: '/console/decide/scenarios' });
    await screen.findAllByRole('group', { name: 'Option 1' });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Add an option' }));
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Compare the 2 options' }));
    });
    await screen.findByRole('heading', { name: 'The options compared' });
    await settle();
    expect(collisions()).toEqual([]);
  });

  it('on a template’s sensitivity and break-evens never overlap', async () => {
    await setup({ path: '/console/decide/templates/rent-or-buy' });
    const form = await screen.findByRole('region', { name: 'Your answers' });
    const set = (name: string | RegExp, value: string): void => {
      fireEvent.change(within(form).getByRole('textbox', { name }), { target: { value } });
    };
    set('What would the home cost?', '350000');
    set('How much would you put down?', '70000');
    fireEvent.change(within(form).getAllByRole('textbox', { name: 'Its yearly rate' })[0] as HTMLElement, { target: { value: '0.042' } });
    fireEvent.change(within(form).getAllByRole('textbox', { name: 'Its term, in months' })[0] as HTMLElement, { target: { value: '300' } });
    set(/What would buying cost, once/, '9000');
    set(/What would owning cost a month/, '250');
    set(/What would selling the home cost/, '0.03');
    await act(async () => {
      fireEvent.click(within(form).getByRole('button', { name: 'Build and compare the options' }));
    });
    await screen.findByRole('heading', { name: 'What Salli built' });
    await settle();
    expect(collisions()).toEqual([]);
  });

  it('the check itself catches two labels on top of each other', () => {
    document.body.innerHTML =
      '<svg class="chart-svg" aria-label="test"><text class="chart-tick" x="100" y="10" font-size="12" text-anchor="start">Apr 2026</text><text class="chart-tick" x="130" y="10" font-size="12" text-anchor="start">May 2026</text></svg>';
    expect(collisions()).toHaveLength(1);
    document.body.innerHTML = '';
  });
});
