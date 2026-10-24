import { describe, expect, it } from 'vitest';
import type { JournalEntry } from '@leafmonkeylabs/salli-sdk';
import { recentOf } from '../src/lib/entries';
import { filled, lineChart } from '../src/lib/chart';
import { sameDaysLastMonth, wholeDigits } from '../src/lib/display';

describe("Home's glance", () => {
  it('shows an amount in whole units, as the server wrote its digits', () => {
    expect(wholeDigits('18503.37', 'EUR')).toBe('18,503');
    expect(wholeDigits('-1230.50', 'EUR')).toBe('(1,230)');
    expect(wholeDigits('1500', 'JPY')).toBe('1,500');
  });

  it('compares with last month up to the same day', () => {
    expect(sameDaysLastMonth('2026-10-24')).toEqual({ from: '2026-09-01', to: '2026-09-24' });
    expect(sameDaysLastMonth('2026-03-31')).toEqual({ from: '2026-02-01', to: '2026-02-28' });
    expect(sameDaysLastMonth('2026-01-05')).toEqual({ from: '2025-12-01', to: '2025-12-05' });
  });

  it('fills a ring by the score', () => {
    expect(filled('61.37')).toBeCloseTo(0.6137);
    expect(filled('140')).toBe(1);
  });

  it('draws a line inside its box', () => {
    const line = lineChart(['10', '30', '20'], 100, 40);
    expect(line.points).toHaveLength(3);
    expect(line.points.every((p) => p.x >= 0 && p.x <= 100 && p.y >= 0 && p.y <= 40)).toBe(true);
    expect(line.points[1]?.y).toBeLessThan(line.points[0]?.y ?? 0);
  });
});

describe('Add', () => {
  it('offers the newest descriptions booked by hand, once each, without reversals', () => {
    const entry = (id: string, date: string, description: string, source: 'manual' | 'statement' = 'manual', reversed_by: string | null = null) =>
      ({ id, entry_date: date, description, source, external_ref: null, reversed_by, postings: [
        { account_id: 'a', amount: '12.50', currency: 'EUR', direction: 1 },
        { account_id: 'b', amount: '12.50', currency: 'EUR', direction: -1 },
      ] }) as unknown as JournalEntry;
    const recent = recentOf([
      entry('1', '2026-10-01', 'Lunch'),
      entry('2', '2026-10-03', 'Coffee'),
      entry('3', '2026-10-04', 'lunch'),
      entry('4', '2026-10-05', 'Rent', 'statement'),
      entry('5', '2026-10-06', 'Gym', 'manual', 'x'),
      entry('6', '2026-10-07', 'REVERSAL: Gym'),
      entry('7', '2026-10-02', 'Bus'),
    ]);
    expect(recent.map((r) => r.description)).toEqual(['lunch', 'Coffee', 'Bus']);
    expect(recent[0]?.amount).toBe('12.50');
  });
});
