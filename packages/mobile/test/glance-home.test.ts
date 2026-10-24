import { describe, expect, it } from 'vitest';
import { filled, lineChart, shares } from '../src/lib/chart';
import { previousMonthOf, wholeDigits } from '../src/lib/display';

describe("Home's glance", () => {
  it('shows an amount in whole units, as the server wrote its digits', () => {
    expect(wholeDigits('18503.37', 'EUR')).toBe('18,503');
    expect(wholeDigits('-1230.50', 'EUR')).toBe('(1,230)');
    expect(wholeDigits('1500', 'JPY')).toBe('1,500');
  });

  it('takes the whole month before', () => {
    expect(previousMonthOf('2026-10-24')).toEqual({ from: '2026-09-01', to: '2026-09-30' });
    expect(previousMonthOf('2026-01-05')).toEqual({ from: '2025-12-01', to: '2025-12-31' });
    expect(previousMonthOf('2028-03-01')).toEqual({ from: '2028-02-01', to: '2028-02-29' });
  });

  it('draws a line, bars and a ring inside their box', () => {
    const line = lineChart(['10', '30', '20'], 100, 40);
    expect(line.points).toHaveLength(3);
    expect(line.points.every((p) => p.x >= 0 && p.x <= 100 && p.y >= 0 && p.y <= 40)).toBe(true);
    expect(line.points[1]?.y).toBeLessThan(line.points[0]?.y ?? 0);
    expect(shares(['50', '100'])).toEqual([0.5, 1]);
    expect(shares(['0', '0'])).toEqual([0, 0]);
    expect(filled('61.37')).toBeCloseTo(0.6137);
    expect(filled('140')).toBe(1);
  });
});
