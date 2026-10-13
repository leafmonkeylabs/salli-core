/**
 * The token roles an extension's theme replaces (tokens.css names them).
 * A theme is set on <html> through the CSSOM, never as an inline style
 * attribute, so the CSP's `style-src 'self'` holds.
 */
export const TOKEN_NAMES = [
  'page',
  'panel',
  'input',
  'rule',
  'text',
  'muted',
  'brand',
  'mark',
  'wordmark',
  'negative',
  'warn',
  'button',
  'button-text',
  'button-2',
  'button-2-text',
  'mark-square',
  'decoration',
  'focus',
  'chart-baseline',
  'chart-1',
  'chart-2',
  'chart-grid',
  'chart-shortfall',
  'chrome',
  'work',
  'card',
  'well',
  'hover',
  'selected',
  'tile',
  'tile-text',
  'dash',
  'type-asset',
  'type-liability',
  'type-income',
  'type-expense',
  'type-equity',
] as const;

export type TokenName = (typeof TOKEN_NAMES)[number];

/** Applies a theme's tokens to `root` as `--c-<name>: light-dark(light, dark)`. */
export function applyThemeTokens(theme: Record<TokenName, { light: string; dark: string }>, root: HTMLElement = document.documentElement): void {
  for (const name of TOKEN_NAMES) {
    const value = theme[name];
    root.style.setProperty(`--c-${name}`, `light-dark(${value.light}, ${value.dark})`);
  }
}
