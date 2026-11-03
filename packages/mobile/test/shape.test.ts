import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = new URL('../src', import.meta.url).pathname;

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : /\.tsx?$/.test(name) ? [path] : [];
  });
}
const sources = files(SRC).map((path) => ({ path: path.slice(SRC.length + 1), text: readFileSync(path, 'utf8') }));

describe('one shape for every theme', () => {
  it('sets no corner but through shape() and the radius tokens', () => {
    // A corner is a token (radii.x) or shape(); a number or a theme value is a leak.
    const raw = sources.filter((s) => s.path !== 'theme.ts' && /\bborder(Top|Bottom)?(Left|Right)?Radius\s*:\s*(?!radii\.)/.test(s.text));
    expect(raw.map((s) => s.path)).toEqual([]);
  });

  it('has no theme shape left to branch on', () => {
    const branching = sources.filter((s) => /theme\.(radius|control|marker|iconCap|cardBorder\w*|offset|tile\w*|fieldBorder|chrome|work|rule)\b|Math\.min\(theme/.test(s.text));
    expect(branching.map((s) => s.path)).toEqual([]);
  });

  it('keeps every type size at 12 or more', () => {
    const small = sources.filter((s) => /fontSize:\s*(\d|1[01])(?![\d.])/.test(s.text));
    expect(small.map((s) => s.path)).toEqual([]);
  });
});

describe('the kit', () => {
  const kit = sources.find((s) => s.path === 'kit.tsx')?.text ?? '';
  it('has the parts screens are made from', () => {
    for (const part of ['Surface', 'Card', 'Section', 'Field', 'Chip', 'Tag', 'Badge', 'Segmented', 'Notice', 'Skeleton', 'Toggle', 'ProgressBar', 'Ring', 'Press', 'Button', 'RoundButton', 'Money']) {
      expect(kit, part).toMatch(new RegExp(`export (const|function) ${part}\\b`));
    }
  });

  it('is the only place a text input is drawn, but the AI composer capsule', () => {
    const inputs = sources.filter((s) => s.path !== 'kit.tsx' && s.path !== 'app/agent.tsx' && /<TextInput\b/.test(s.text));
    expect(inputs.map((s) => s.path)).toEqual([]);
  });

  it('draws icons with round caps and joins in every theme', () => {
    expect(kit).toContain("strokeLinecap: 'round'");
    expect(kit).toContain("strokeLinejoin: 'round'");
  });
});
