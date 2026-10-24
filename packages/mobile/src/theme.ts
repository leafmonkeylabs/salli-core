/**
 * The brand's colours and type for a phone (docs/brand/README.md), with the
 * console's roles for light and night (packages/console/src/styles/tokens.css):
 * paper bars, a bone work area, paper cards; on night, night with deep-green
 * cards. Ledger is the brand's; the other themes (Appearance, designs 23 to
 * 25) change colours, corners, type and icons, never layout or words.
 * Colours come only from here.
 */
import * as SecureStore from 'expo-secure-store';
import { createContext, useContext } from 'react';
import { useColorScheme } from 'react-native';
import { APPEARANCE_KEY, appearanceOf, DEFAULT_APPEARANCE, isNight, typeOf, type Appearance, type ThemeId } from './lib/appearance';

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
  /** A card's corners, and a button's or a field's. */
  radius: number;
  control: number;
  /** A card's edge: a hairline, or Sticker's outline. */
  cardBorder: string;
  cardBorderWidth: number;
  /** Sticker's offset shadow under cards and buttons. */
  offset?: number;
  /** A section label's marker: the brand's outlined square, or a dot. */
  marker: 'square' | 'dot';
  /** The current place in the bar, and what fills its icon. */
  current: string;
  currentFill?: string;
  /** Icons' line: its ends, and its width on a 24 grid. */
  iconCap: 'square' | 'round';
  iconWidth: number;
  /** Aurora's two lights behind the page. */
  glow?: [string, string];
}

const ledgerShape = {
  radius: 0,
  control: 0,
  cardBorderWidth: 0.5,
  marker: 'square',
  iconCap: 'square',
  iconWidth: 1.5,
} as const;

const roundedShape = { ...ledgerShape, radius: 16, control: 999, marker: 'dot', iconCap: 'round' } as const;

export const light: Theme = {
  ...ledgerShape,
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
  cardBorder: brand.hairline,
  current: brand.ink,
};

export const night: Theme = {
  ...ledgerShape,
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
  cardBorder: 'rgba(242, 236, 223, 0.16)',
  current: brand.paperOnDark,
};

/** Bold: black, lime and big figures; always dark. */
const bold: Theme = {
  dark: true,
  chrome: '#0B0B0C',
  work: '#0B0B0C',
  card: '#1C1C1F',
  rule: '#2C2C30',
  text: '#F5F5F0',
  muted: '#A3A39C',
  input: '#1C1C1F',
  fieldBorder: '#76766F',
  button: '#D4FF3A',
  buttonText: '#0B0B0C',
  button2: '#2C2C30',
  button2Text: '#F5F5F0',
  button2Border: 'transparent',
  // The key figure stands on the page itself, in lime.
  tile: '#0B0B0C',
  tileText: '#D4FF3A',
  tileMuted: '#A3A39C',
  negative: '#FF8A7A',
  chart: '#D4FF3A',
  focus: '#D4FF3A',
  scrim: 'rgba(0, 0, 0, 0.6)',
  shadow: '#000000',
  radius: 24,
  control: 999,
  cardBorder: 'transparent',
  cardBorderWidth: 0,
  marker: 'dot',
  current: '#D4FF3A',
  iconCap: 'round',
  iconWidth: 2,
};

/** Sticker: cream, black outlines with offset shadows, bright fills; always light. */
const sticker: Theme = {
  dark: false,
  chrome: '#FFFFFF',
  work: '#FFF3D6',
  card: '#FFFFFF',
  rule: '#E3D6B8',
  text: '#111111',
  muted: '#4A4336',
  input: '#FFFFFF',
  fieldBorder: '#111111',
  button: '#111111',
  buttonText: '#FFFFFF',
  button2: '#FF8FB1',
  button2Text: '#111111',
  button2Border: '#111111',
  tile: '#FFD23F',
  tileText: '#111111',
  tileMuted: '#3D3420',
  negative: '#B3261E',
  chart: '#111111',
  focus: '#111111',
  scrim: 'rgba(17, 17, 17, 0.45)',
  shadow: '#111111',
  radius: 16,
  control: 12,
  cardBorder: '#111111',
  cardBorderWidth: 2,
  offset: 4,
  marker: 'dot',
  current: '#111111',
  currentFill: '#FFD23F',
  iconCap: 'round',
  iconWidth: 2.2,
};

/** Aurora: dark navy, glass cards and two lights behind; always dark. */
const aurora: Theme = {
  dark: true,
  chrome: '#0D1226',
  work: '#0A0E1F',
  card: 'rgba(255, 255, 255, 0.07)',
  rule: 'rgba(255, 255, 255, 0.12)',
  text: '#F2F4FF',
  muted: '#B4BBDA',
  input: 'rgba(255, 255, 255, 0.06)',
  fieldBorder: '#7C84A8',
  button: '#5EEAD4',
  buttonText: '#0A0E1F',
  button2: 'rgba(255, 255, 255, 0.1)',
  button2Text: '#F2F4FF',
  button2Border: 'rgba(255, 255, 255, 0.16)',
  tile: 'rgba(255, 255, 255, 0.07)',
  tileText: '#5EEAD4',
  tileMuted: '#B4BBDA',
  negative: '#FCA5A5',
  chart: '#5EEAD4',
  focus: '#5EEAD4',
  scrim: 'rgba(5, 7, 16, 0.6)',
  shadow: '#000000',
  radius: 22,
  control: 999,
  cardBorder: 'rgba(255, 255, 255, 0.12)',
  cardBorderWidth: 1,
  marker: 'dot',
  current: '#5EEAD4',
  currentFill: 'rgba(94, 234, 212, 0.18)',
  iconCap: 'round',
  iconWidth: 1.6,
  glow: ['#2DD4BF', '#8B5CF6'],
};

/** A theme's look on its day and night sides. */
export function themeOf(id: ThemeId, nightSide: boolean): Theme {
  switch (id) {
    case 'ledger':
      return nightSide ? night : light;
    case 'ledgerRounded':
      return nightSide ? { ...night, ...roundedShape } : { ...light, ...roundedShape };
    case 'bold':
      return bold;
    case 'sticker':
      return sticker;
    case 'aurora':
      return aurora;
  }
}

export const AppearanceContext = createContext<Appearance>(DEFAULT_APPEARANCE);

export function useTheme(): Theme {
  const appearance = useContext(AppearanceContext);
  const phoneDark = useColorScheme() === 'dark';
  return themeOf(appearance.theme, isNight(appearance, phoneDark));
}

/** Each theme's type for the roles; Geist Mono for ids, codes and addresses in every theme. */
export const TYPE = {
  geist: { regular: 'Geist_400Regular', medium: 'Geist_500Medium', semibold: 'Geist_600SemiBold' },
  bold: { regular: 'SpaceGrotesk_400Regular', medium: 'SpaceGrotesk_500Medium', semibold: 'SpaceGrotesk_700Bold' },
  sticker: { regular: 'BricolageGrotesque_400Regular', medium: 'BricolageGrotesque_600SemiBold', semibold: 'BricolageGrotesque_800ExtraBold' },
  aurora: { regular: 'PlusJakartaSans_400Regular', medium: 'PlusJakartaSans_500Medium', semibold: 'PlusJakartaSans_700Bold' },
} as const;

/**
 * The theme the app opened with. Styles are made once, as the app opens, so
 * the type is the one stored then: a theme picked later brings its type the
 * next time the app opens (its colours and shapes come at once).
 */
export const openedWith = appearanceOf(SecureStore.getItem(APPEARANCE_KEY)).theme;

/** Geist for everything read in Ledger, the theme's own type in the others; Geist Mono for ids, codes and addresses. */
export const font = { ...TYPE[typeOf(openedWith)], mono: 'GeistMono_400Regular' } as const;

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
