/**
 * The phone's look, v2 (docs/design/mobile.md): quiet warm neutrals, one calm
 * green for where you are and what is on track, red only for a fact that needs
 * you. One shape for every theme: a radius scale with continuous corners, and
 * depth from soft shadow (a lighter surface with a top highlight on night),
 * never an outline. Themes differ in colour and type only. Colours, radii,
 * shadows and spacing come only from here.
 */
import * as SecureStore from 'expo-secure-store';
import { createContext, useContext } from 'react';
import { useColorScheme, type ViewStyle } from 'react-native';
import { APPEARANCE_KEY, appearanceOf, DEFAULT_APPEARANCE, isNight, typeOf, type Appearance, type ThemeId } from './lib/appearance';

export interface Theme {
  dark: boolean;
  /** Behind the cards. */
  ground: string;
  /** Cards, sheets, bars. */
  surface: string;
  /** Fields, chips, quiet buttons, the tracks of bars. */
  fill: string;
  /** Between rows only. */
  line: string;
  text: string;
  muted: string;
  /** Where you are, what is on track, links and the forecast line. */
  green: string;
  /** Behind the current tab, and notes. */
  greenTint: string;
  /** Below zero, over budget, overdue. */
  red: string;
  redTint: string;
  /** The main button: ink. */
  button: string;
  buttonText: string;
  /** Behind a sheet. */
  scrim: string;
  /** Under what floats. */
  shadow: string;
  /** Night's lighter surface is lifted by a 1 px highlight along its top edge, in place of a shadow. */
  highlight?: string;
  /** The tint of the blur behind the tab bar. */
  blur: 'light' | 'dark';
  /** Icons' line width on a 24 grid. */
  iconWidth: number;
  /** Aurora's two lights behind the page. */
  glow?: [string, string];
}

export const light: Theme = {
  dark: false,
  ground: '#F3F2EF',
  surface: '#FFFFFF',
  fill: '#EFEEEA',
  line: '#ECEBE7',
  text: '#18201C',
  muted: '#5F6661',
  green: '#2E6A55',
  greenTint: '#E4EFE9',
  red: '#A8483A',
  redTint: '#F8E9E5',
  button: '#18201C',
  buttonText: '#FFFFFF',
  scrim: 'rgba(14, 17, 16, 0.4)',
  shadow: '#18201C',
  blur: 'light',
  iconWidth: 1.75,
};

export const night: Theme = {
  dark: true,
  ground: '#0E1110',
  surface: '#171B19',
  fill: '#232825',
  line: 'rgba(255, 255, 255, 0.07)',
  text: '#ECEFEC',
  muted: '#9BA39D',
  green: '#7CC0A5',
  greenTint: '#1F3A30',
  red: '#E58E7C',
  redTint: '#3B2622',
  button: '#ECEFEC',
  buttonText: '#0E1110',
  scrim: 'rgba(0, 0, 0, 0.6)',
  shadow: '#000000',
  highlight: 'rgba(255, 255, 255, 0.07)',
  blur: 'dark',
  iconWidth: 1.75,
};

/** Bold: black, lime and big figures; always dark. */
const bold: Theme = {
  ...night,
  ground: '#0B0B0C',
  surface: '#1C1C1F',
  fill: '#2C2C30',
  text: '#F5F5F0',
  muted: '#A3A39C',
  green: '#D4FF3A',
  greenTint: 'rgba(212, 255, 58, 0.14)',
  red: '#FF8A7A',
  redTint: 'rgba(255, 138, 122, 0.16)',
  button: '#D4FF3A',
  buttonText: '#0B0B0C',
  iconWidth: 2,
};

/** Aurora: dark navy, glass surfaces and two lights behind; always dark. */
const aurora: Theme = {
  ...night,
  ground: '#0A0E1F',
  surface: 'rgba(255, 255, 255, 0.07)',
  fill: 'rgba(255, 255, 255, 0.09)',
  line: 'rgba(255, 255, 255, 0.12)',
  text: '#F2F4FF',
  muted: '#B4BBDA',
  green: '#5EEAD4',
  greenTint: 'rgba(94, 234, 212, 0.16)',
  red: '#FCA5A5',
  redTint: 'rgba(252, 165, 165, 0.14)',
  button: '#5EEAD4',
  buttonText: '#0A0E1F',
  scrim: 'rgba(5, 7, 16, 0.6)',
  highlight: 'rgba(255, 255, 255, 0.12)',
  iconWidth: 1.6,
  glow: ['#2DD4BF', '#8B5CF6'],
};

/** A theme's look on its day and night sides. */
export function themeOf(id: ThemeId, nightSide: boolean): Theme {
  switch (id) {
    case 'ledger':
      return nightSide ? night : light;
    case 'bold':
      return bold;
    case 'aurora':
      return aurora;
  }
}

/** Every corner in the app, from one scale. */
export const radii = { tag: 6, tile: 10, field: 14, card: 20, key: 26, sheet: 32, pill: 999 } as const;

/**
 * A corner: the radius and iOS's continuous curve. The only way a style sets
 * one (test/shape.test.ts fails on a raw borderRadius elsewhere).
 */
export function shape(r: number): Pick<ViewStyle, 'borderRadius' | 'borderCurve'> {
  return { borderRadius: r, borderCurve: 'continuous' };
}

export type Elevation = 'flat' | 'card' | 'floating' | 'sheet';

/**
 * Soft shadow by depth, as Main's Depth board: a card's two layers are drawn
 * as the one that reads (React Native takes a single shadow). Night has none:
 * its surfaces are lighter and carry a highlight (Surface draws it).
 */
export function elevation(theme: Theme, level: Elevation): ViewStyle {
  if (level === 'flat' || theme.dark) return {};
  const base = { shadowColor: theme.shadow, shadowOffset: { width: 0, height: 4 } };
  switch (level) {
    case 'card':
      return { ...base, shadowOpacity: 0.07, shadowRadius: 7, elevation: 1 };
    case 'floating':
      return { shadowColor: theme.shadow, shadowOffset: { width: 0, height: 6 }, shadowOpacity: 0.16, shadowRadius: 9, elevation: 6 };
    case 'sheet':
      return { shadowColor: theme.shadow, shadowOffset: { width: 0, height: -8 }, shadowOpacity: 0.08, shadowRadius: 10, elevation: 12 };
  }
}

/** Night's floating things have no shadow to separate them: a deeper shadow on black still reads. */
export function floating(theme: Theme): ViewStyle {
  return theme.dark ? { shadowColor: '#000000', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.5, shadowRadius: 12, elevation: 6 } : elevation(theme, 'floating');
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
  aurora: { regular: 'PlusJakartaSans_400Regular', medium: 'PlusJakartaSans_500Medium', semibold: 'PlusJakartaSans_700Bold' },
} as const;

/**
 * The theme the app opened with. Styles are made once, as the app opens, so
 * the type is the one stored then: a theme picked later brings its type the
 * next time the app opens (its colours come at once).
 */
export const openedWith = appearanceOf(SecureStore.getItem(APPEARANCE_KEY)).theme;

/** Geist for everything read in Ledger, the theme's own type in the others; Geist Mono for ids, codes and addresses. */
export const font = { ...TYPE[typeOf(openedWith)], mono: 'GeistMono_400Regular' } as const;

/** Spacing: these eight and nothing else. */
export const space = { s4: 4, s8: 8, s12: 12, s16: 16, s20: 20, s24: 24, s32: 32, s40: 40 } as const;

/** The phone's scale (docs/design/mobile.md): 48 to touch, 20 from every edge, nothing under 12. */
export const size = {
  target: 48,
  /** Buttons and fields. */
  control: 52,
  /** From the screen's edge. */
  gutter: 20,
  /** Inside a card, and the key figure's. */
  pad: 20,
  padKey: 24,
  /** Between cards, between sections, from a heading to its card. */
  gap: 12,
  section: 28,
  heading: 10,
  largeTitle: 32,
  title: 22,
  headline: 17,
  body: 16,
  small: 14,
  label: 13,
  caption: 12,
  keyFigure: 46,
  /** A figure in a row or tile. */
  figure: 22,
} as const;
