import { describe, expect, it, vi } from 'vitest';

vi.mock('react-native', () => ({ useColorScheme: () => 'light' }));
vi.mock('expo-secure-store', () => ({ getItem: () => null }));

const { elevation, light, night, radii, shape, size, space, themeOf } = await import('../src/theme');

/** WCAG relative luminance of #RRGGBB. */
function luminance(hex: string): number {
  const channel = (i: number) => {
    const v = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(0) + 0.7152 * channel(1) + 0.0722 * channel(2);
}
const contrast = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
};

describe('the v2 palette', () => {
  it('has the board\'s roles on each side', () => {
    expect(light).toMatchObject({ ground: '#F3F2EF', surface: '#FFFFFF', fill: '#EFEEEA', line: '#ECEBE7', text: '#18201C', muted: '#5F6661', green: '#2E6A55', greenTint: '#E4EFE9', red: '#A8483A', redTint: '#F8E9E5', button: '#18201C' });
    expect(night).toMatchObject({ ground: '#0E1110', surface: '#171B19', fill: '#232825', text: '#ECEFEC', muted: '#9BA39D', green: '#7CC0A5', greenTint: '#1F3A30', red: '#E58E7C', redTint: '#3B2622' });
    expect(night.line).toBe('rgba(255, 255, 255, 0.07)');
  });

  it('keeps the retired colours out', () => {
    const keys = [...Object.keys(light), ...Object.keys(night)].join(' ');
    expect(keys).not.toMatch(/tile|bone|sand|oxblood|chrome|work|card|rule|radius|control|marker|iconCap|offset/i);
  });

  it('reads at the contrast the board states', () => {
    for (const t of [light, night]) {
      expect(contrast(t.text, t.surface)).toBeGreaterThanOrEqual(7);
      expect(contrast(t.muted, t.surface)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(t.muted, t.ground)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(t.green, t.surface)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(t.green, t.greenTint)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(t.red, t.surface)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(t.red, t.redTint)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('gives every theme the same roles and only night a highlight instead of shadow', () => {
    const roles = Object.keys(light).filter((k) => k !== 'highlight' && k !== 'glow');
    for (const id of ['ledger', 'bold', 'aurora'] as const) {
      const t = themeOf(id, true);
      for (const role of roles) expect(t).toHaveProperty(role);
    }
    expect(light.highlight).toBeUndefined();
    expect(night.highlight).toBeDefined();
  });
});

describe('shape', () => {
  it('is one scale, 6 to 32 and a pill', () => {
    expect(Object.values(radii)).toEqual([6, 10, 14, 20, 26, 32, 999]);
  });

  it('adds the continuous curve to a radius', () => {
    expect(shape(radii.card)).toEqual({ borderRadius: 20, borderCurve: 'continuous' });
    expect(shape(radii.pill)).toEqual({ borderRadius: 999, borderCurve: 'continuous' });
  });
});

describe('elevation', () => {
  it('is nothing when flat, and a shadow by depth on day', () => {
    expect(elevation(light, 'flat')).toEqual({});
    const card = elevation(light, 'card');
    const floating = elevation(light, 'floating');
    expect(card.shadowOpacity).toBeGreaterThan(0);
    expect(floating.shadowRadius).toBeGreaterThan(card.shadowRadius ?? 0);
    expect((elevation(light, 'sheet').shadowOffset?.height ?? 0)).toBeLessThan(0);
  });

  it('draws no shadow on night, where a surface is lighter with a highlight', () => {
    expect(elevation(night, 'card')).toEqual({});
    expect(elevation(night, 'sheet')).toEqual({});
  });
});

describe('spacing and type', () => {
  it('keeps 20 from the edges, 20 inside a card and nothing under 12', () => {
    expect(size.gutter).toBe(20);
    expect(size.pad).toBe(20);
    expect(size.padKey).toBe(24);
    expect(size.gap).toBe(12);
    expect(size.section).toBe(28);
    expect(Object.values(space)).toEqual([4, 8, 12, 16, 20, 24, 32, 40]);
    expect(size.caption).toBeGreaterThanOrEqual(12);
    expect(size.target).toBe(48);
    expect(size.control).toBe(52);
  });
});
