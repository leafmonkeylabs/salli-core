import { describe, expect, it } from 'vitest';
import { bandChart } from '../src/lib/chart';
import { fractionOf, percentOf, scoreShown } from '../src/lib/fi';

describe('independence', () => {
  it('shows a score only with enough months behind it', () => {
    expect(scoreShown({ status: 'not_enough_data' })).toBe(false);
    expect(scoreShown({ status: 'ok' })).toBe(true);
    expect(scoreShown({})).toBe(true); // a server from before the status
  });

  it('reads and writes rates as percentages, exactly', () => {
    expect(percentOf('0.04')).toBe('4');
    expect(percentOf('0.035')).toBe('3.5');
    expect(percentOf('1')).toBe('100');
    expect(percentOf('0.6')).toBe('60');
    expect(percentOf('0.0025')).toBe('0.25');
    expect(fractionOf('4')).toBe('0.04');
    expect(fractionOf('3.5 %')).toBe('0.035');
    expect(fractionOf('60')).toBe('0.6');
    expect(fractionOf('100')).toBe('1');
    expect(fractionOf('0.25')).toBe('0.0025');
    expect(fractionOf('soon')).toBeUndefined();
  });

  it('draws the projection, its band and the target on one scale', () => {
    const chart = bandChart([{ low: '10', base: '20', high: '30' }, { low: '40', base: '60', high: '80' }], '100', 200, 100);
    expect(chart.base.startsWith('M')).toBe(true);
    expect(chart.band.endsWith('Z')).toBe(true);
    expect(chart.target).toBeGreaterThanOrEqual(0);
    expect(chart.target).toBeLessThan(10);
  });
});
