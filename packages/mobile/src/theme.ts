/**
 * The brand's colours and type for a phone (docs/brand/README.md), with the
 * console's roles for light and night (packages/console/src/styles/tokens.css):
 * paper bars, a bone work area, paper cards; on night, night with deep-green
 * cards. Colours come only from here.
 */
import { useColorScheme } from 'react-native';

const brand = {
  paper: '#F6F3EC',
  bone: '#ECE6D9',
  hairline: '#DCD4C4',
  ink: '#1C1B19',
  graphite: '#57524A',
  stone: '#8A8378',
  ledgerGreen: '#173B33',
  deepGreen: '#0F2924',
  sand: '#D8CBAE',
  oxblood: '#6B2620',
  night: '#0E1513',
  paperOnDark: '#F2ECDF',
  mutedOnDark: '#9AAAA2',
  sandOnDark: '#CDBF9F',
  clay: '#E2A58F',
} as const;

export interface Theme {
  dark: boolean;
  /** The bars at the top and bottom. */
  chrome: string;
  /** Behind the cards. */
  work: string;
  card: string;
  rule: string;
  text: string;
  muted: string;
  /** Inputs' fill and their 3:1 border. */
  input: string;
  fieldBorder: string;
  button: string;
  buttonText: string;
  button2: string;
  button2Text: string;
  /** A secondary button's edge: none on paper, where sand stands out; on night, where it sits on cards, a hairline. */
  button2Border: string;
  /** The one key figure's tile. */
  tile: string;
  tileText: string;
  tileMuted: string;
  /** Negative figures and warnings. */
  negative: string;
  /** A chart's line: ledger green, sand on night. */
  chart: string;
  focus: string;
  /** Behind a sheet. */
  scrim: string;
  /** Under what floats over the page: the AI button. */
  shadow: string;
}

export const light: Theme = {
  dark: false,
  chrome: brand.paper,
  work: brand.bone,
  card: brand.paper,
  rule: brand.hairline,
  text: brand.ink,
  muted: brand.graphite,
  input: brand.bone,
  fieldBorder: brand.stone,
  button: brand.ledgerGreen,
  buttonText: brand.paper,
  button2: brand.sand,
  button2Text: brand.ink,
  button2Border: 'transparent',
  tile: brand.ledgerGreen,
  tileText: brand.paperOnDark,
  tileMuted: brand.sand,
  negative: brand.oxblood,
  chart: brand.ledgerGreen,
  focus: brand.ledgerGreen,
  scrim: 'rgba(14, 21, 19, 0.4)',
  shadow: brand.night,
};

export const night: Theme = {
  dark: true,
  chrome: brand.night,
  work: brand.night,
  card: brand.deepGreen,
  rule: 'rgba(242, 236, 223, 0.16)',
  text: brand.paperOnDark,
  muted: brand.mutedOnDark,
  input: brand.night,
  fieldBorder: brand.mutedOnDark,
  button: brand.sandOnDark,
  buttonText: brand.night,
  // Night, not deep green: a deep-green button vanishes on a deep-green card.
  button2: brand.night,
  button2Text: brand.paperOnDark,
  button2Border: 'rgba(242, 236, 223, 0.16)',
  tile: brand.sandOnDark,
  tileText: brand.night,
  tileMuted: brand.deepGreen,
  negative: brand.clay,
  chart: brand.sandOnDark,
  focus: brand.sandOnDark,
  scrim: 'rgba(14, 21, 19, 0.6)',
  shadow: '#000000',
};

export function useTheme(): Theme {
  return useColorScheme() === 'dark' ? night : light;
}

/** Geist for everything read, Geist Mono for ids, codes and addresses. */
export const font = {
  regular: 'Geist_400Regular',
  medium: 'Geist_500Medium',
  semibold: 'Geist_600SemiBold',
  mono: 'GeistMono_400Regular',
} as const;

/** The phone's scale (docs/design/mobile.md): 48 px to touch, 16 px gutters. */
export const size = {
  target: 48,
  gutter: 16,
  gap: 12,
  title: 28,
  heading: 20,
  body: 16,
  small: 14,
  label: 12,
  figure: 40,
  keyFigure: 20,
} as const;
