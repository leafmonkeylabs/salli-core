import { describe, expect, it } from 'vitest';
import { lineChart } from '../src/lib/chart';
import { wholeDigits } from '../src/lib/display';

describe("Home's glance", () => {
  it('shows an amount in whole units, as the server wrote its digits', () => {
    expect(wholeDigits('18503.37', 'EUR')).toBe('18,503');
    expect(wholeDigits('-1230.50', 'EUR')).toBe('(1,230)');
    expect(wholeDigits('1500', 'JPY')).toBe('1,500');
  });

  it('draws a line inside its box', () => {
    const line = lineChart(['10', '30', '20'], 100, 40);
    expect(line.points).toHaveLength(3);
    expect(line.points.every((p) => p.x >= 0 && p.x <= 100 && p.y >= 0 && p.y <= 40)).toBe(true);
    expect(line.points[1]?.y).toBeLessThan(line.points[0]?.y ?? 0);
  });
});
