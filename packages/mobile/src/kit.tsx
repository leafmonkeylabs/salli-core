/**
 * The app's parts, as the console's kit has them (docs/design/mobile.md):
 * square corners, hairline cards, 48 px to touch, the outlined-square label,
 * figures exactly as the server sent them. A theme other than Ledger changes
 * their corners, edges, markers and icon lines (theme.ts).
 */
import { SalliNetworkError } from '@leafmonkeylabs/salli-sdk';
import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type PressableProps, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';
import Animated, { ReduceMotion, useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import Svg, { Path, Rect, SvgXml } from 'react-native-svg';
import { LOGO_DARK, LOGO_LIGHT } from './brand/logo';
import { amountParts } from './lib/display';
import { press, useReducedMotion } from './motion';
import { strings } from './strings';
import { font, size, useTheme, type Theme } from './theme';

export function Logo({ height = 36 }: { height?: number }) {
  const theme = useTheme();
  // The file's viewBox is 472.214 × 137.829, its clear space inside it.
  return <SvgXml xml={theme.dark ? LOGO_DARK : LOGO_LIGHT} height={height} width={(height * 472.214) / 137.829} accessibilityLabel="Salli" />;
}

/** Sticker's offset shadow, drawn solid; nothing in other themes. */
export function offsetOf(theme: Theme): ViewStyle | null {
  return theme.offset ? { shadowColor: theme.shadow, shadowOpacity: 1, shadowRadius: 0, shadowOffset: { width: theme.offset, height: theme.offset } } : null;
}

/** A card's own corners and edge in the theme. */
export function cardOf(theme: Theme): ViewStyle {
  return { backgroundColor: theme.card, borderColor: theme.cardBorder, borderWidth: theme.cardBorderWidth < 1 ? StyleSheet.hairlineWidth : theme.cardBorderWidth, borderRadius: theme.radius, ...offsetOf(theme) };
}

export function Card({ children, style, tile }: { children: ReactNode; style?: ViewStyle; tile?: boolean }) {
  const theme = useTheme();
  const tileEdge = theme.offset ? { borderColor: theme.cardBorder, borderWidth: theme.cardBorderWidth } : null;
  return (
    <View style={[styles.card, tile ? { backgroundColor: theme.tile, borderRadius: theme.radius, ...tileEdge, ...offsetOf(theme) } : cardOf(theme), style]}>
      {children}
    </View>
  );
}

/** A section's label: a small outlined square, then tracked capitals. */
export function SectionLabel({ children, onTile }: { children: string; onTile?: boolean }) {
  const theme = useTheme();
  const colour = onTile ? theme.tileMuted : theme.muted;
  return (
    <View style={styles.label} accessibilityRole="header">
      <View style={[styles.square, { borderColor: colour }, theme.marker === 'dot' ? { borderRadius: 4 } : null]} />
      <Text style={[styles.labelText, { color: colour }]}>{children.toUpperCase()}</Text>
    </View>
  );
}

export function Title({ children }: { children: string }) {
  const theme = useTheme();
  return (
    <Text accessibilityRole="header" style={[styles.title, { color: theme.text }]}>
      {children}
    </Text>
  );
}

export function Body({ children, muted, small, style, alert }: { children: ReactNode; muted?: boolean; small?: boolean; style?: TextStyle; alert?: boolean }) {
  const theme = useTheme();
  return (
    <Text {...(alert ? { accessibilityRole: 'alert' as const, accessibilityLiveRegion: 'polite' as const } : {})} style={[small ? styles.small : styles.body, { color: muted ? theme.muted : theme.text }, style]}>{children}</Text>
  );
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

/**
 * Something to press, answering on the UI thread: it scales to 0.98 and
 * dims to 0.85 while held (Reduce Motion: it only dims). `dim` draws it
 * unavailable, at 0.45 and still: never what a press looks like.
 */
export function Press({ style, dim, onPressIn, onPressOut, ...rest }: Omit<PressableProps, 'style'> & { style?: StyleProp<ViewStyle>; dim?: boolean }) {
  const reduced = useReducedMotion();
  const held = useSharedValue(0);
  const answer = useAnimatedStyle(() => ({
    opacity: dim ? 0.45 : 1 - held.value * (1 - press.opacity),
    transform: [{ scale: reduced ? 1 : 1 - held.value * (1 - press.scale) }],
  }));
  const to = (value: number, duration: number) => (held.value = withTiming(value, { duration, easing: press.easing, reduceMotion: ReduceMotion.Never }));
  return (
    <AnimatedPressable
      {...rest}
      onPressIn={(e) => {
        to(1, press.in);
        onPressIn?.(e);
      }}
      onPressOut={(e) => {
        to(0, press.out);
        onPressOut?.(e);
      }}
      style={[style, answer]}
    />
  );
}

type ButtonKind = 'primary' | 'secondary' | 'tertiary';

export function Button({ label, kind = 'primary', busy, icon, ...rest }: { label: string; kind?: ButtonKind; busy?: boolean; icon?: IconName } & Omit<PressableProps, 'children' | 'style'>) {
  const theme = useTheme();
  // A secondary button that can't be used is drawn outlined and empty, as the design draws Done away from the server.
  const unavailable = kind === 'secondary' && !!rest.disabled && !busy;
  const fill = unavailable ? 'transparent' : kind === 'primary' ? theme.button : kind === 'secondary' ? theme.button2 : 'transparent';
  const colour = unavailable ? theme.muted : kind === 'primary' ? theme.buttonText : kind === 'secondary' ? theme.button2Text : theme.text;
  return (
    <Press
      accessibilityRole="button"
      accessibilityState={{ disabled: !!rest.disabled || !!busy, busy: !!busy }}
      dim={!unavailable && !!rest.disabled}
      style={[
        styles.button,
        { backgroundColor: fill, borderRadius: theme.control, borderColor: unavailable ? theme.fieldBorder : kind === 'secondary' ? theme.button2Border : 'transparent' },
        kind === 'tertiary' || unavailable ? null : offsetOf(theme),
      ]}
      {...rest}
    >
      {busy ? <ActivityIndicator color={colour} /> : null}
      <Text style={[styles.buttonText, { color: colour }, kind === 'tertiary' ? styles.underline : null]}>{label}</Text>
      {icon ? <Icon name={icon} size={18} colour={colour} /> : null}
    </Press>
  );
}

/**
 * An amount exactly as the server sent it: the code small before a key
 * figure, negatives in brackets (oxblood in tables), what a reader says
 * spelled out.
 */
export function Money({ amount, currency, figure, onTile, style }: { amount: string; currency: string; figure?: 'key' | 'hero'; onTile?: boolean; style?: TextStyle }) {
  const theme = useTheme();
  const parts = amountParts(amount, currency);
  const shown = parts.negative ? `(${parts.digits})` : parts.digits;
  const colour = onTile ? theme.tileText : parts.negative ? theme.negative : theme.text;
  if (!figure) {
    return (
      <Text accessibilityLabel={parts.spoken} style={[styles.figures, styles.body, { color: colour }, style]}>
        {shown}
      </Text>
    );
  }
  return (
    <View accessible accessibilityLabel={parts.spoken} style={styles.figureRow}>
      <Text style={[styles.code, { color: onTile ? theme.tileMuted : theme.muted }]}>{currency}</Text>
      <Text
        adjustsFontSizeToFit
        numberOfLines={1}
        minimumFontScale={0.6}
        style={[styles.figures, figure === 'hero' ? styles.hero : styles.keyFigure, { color: colour }, style]}
      >
        {shown}
      </Text>
    </View>
  );
}

/** A list row: a bullet, a title and a line under it, and what it opens. */
export function Row({ title, detail, onPress, action, last }: { title: string; detail?: string; onPress?: () => void; action?: ReactNode; last?: boolean }) {
  const theme = useTheme();
  const content = (
    <>
      <View style={[styles.bullet, { backgroundColor: theme.muted }, theme.marker === 'dot' ? { borderRadius: 3 } : null]} />
      <View style={styles.rowText}>
        <Body>{title}</Body>
        {detail ? <Body small muted>{detail}</Body> : null}
      </View>
      {action}
      {onPress ? <Icon name="chevron" size={16} colour={theme.muted} /> : null}
    </>
  );
  const style = [styles.row, last ? null : { borderBottomColor: theme.rule, borderBottomWidth: StyleSheet.hairlineWidth }];
  return onPress ? (
    <Press accessibilityRole="link" onPress={onPress} style={style}>
      {content}
    </Press>
  ) : (
    <View style={style}>{content}</View>
  );
}

/**
 * A ledger's row on one line, as the console's tables: a date, a name, the
 * amount at the end. What the line leaves out (the account, where it came
 * from) goes in `label`, which VoiceOver reads for the whole row.
 */
export function LedgerRow({ lead, title, amount, currency, note, label, onPress, last }: { lead?: string; title: string; amount?: string; currency: string; note?: string; label?: string; onPress?: () => void; last?: boolean }) {
  const theme = useTheme();
  const style = [styles.ledgerRow, last ? null : { borderBottomColor: theme.rule, borderBottomWidth: StyleSheet.hairlineWidth }];
  const content = (
    <>
      {lead ? <Text style={[styles.ledgerLead, { color: theme.muted }]}>{lead}</Text> : null}
      <Body style={styles.ledgerTitle}>{title}</Body>
      {amount !== undefined ? <Money amount={amount} currency={currency} /> : note ? <Body small muted>{note}</Body> : null}
    </>
  );
  return onPress ? (
    <Pressable accessibilityRole="link" accessibilityLabel={label} onPress={onPress} style={style}>
      {content}
    </Pressable>
  ) : (
    <View accessible accessibilityLabel={label} style={style}>
      {content}
    </View>
  );
}

/** A row with a figure at its end: a label, a line under it, the amount. */
export function AmountRow({ title, detail, amount, currency, onPress, last }: { title: string; detail?: string; amount: string; currency: string; onPress?: () => void; last?: boolean }) {
  const theme = useTheme();
  const style = [styles.amountRow, last ? null : { borderBottomColor: theme.rule, borderBottomWidth: StyleSheet.hairlineWidth }];
  const content = (
    <>
      <View style={styles.rowText}>
        <Body>{title}</Body>
        {detail ? (
          <Body small muted>
            {detail}
          </Body>
        ) : null}
      </View>
      <Money amount={amount} currency={currency} />
      {onPress ? <Icon name="chevron" size={16} colour={theme.muted} /> : null}
    </>
  );
  return onPress ? (
    <Pressable accessibilityRole="link" onPress={onPress} style={style}>
      {content}
    </Pressable>
  ) : (
    <View style={style}>{content}</View>
  );
}

/** A card's first line: its label, and a line saying what it holds. */
export function CardHead({ label, help, end }: { label: string; help?: string; end?: string }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 4, paddingBottom: 4 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <SectionLabel>{label}</SectionLabel>
        {end ? <Text style={[styles.labelText, { color: theme.muted }]}>{end}</Text> : null}
      </View>
      {help ? (
        <Body small muted>
          {help}
        </Body>
      ) : null}
    </View>
  );
}

export function Loading({ what }: { what: string }) {
  return (
    <Body small muted style={{ paddingVertical: 8 }}>
      {what}
    </Body>
  );
}

/**
 * A read on its way: "Loading…" while it is, and once it has failed, why,
 * with a way to ask again. A failed read never waits forever.
 */
export function Waiting({ query, what }: { query: { error: Error | null; isRefetching: boolean; refetch: () => unknown }; what: string }) {
  if (!query.error) return <Loading what={strings.home.loading(what)} />;
  return (
    <View style={{ gap: 8, paddingVertical: 8 }}>
      <Body alert>{query.error instanceof SalliNetworkError ? strings.reach.cantRead(what) : strings.reach.failed(what, query.error.message)}</Body>
      <View style={{ alignSelf: 'flex-start' }}>
        <Button kind="secondary" label={strings.reach.tryAgain} busy={query.isRefetching} disabled={query.isRefetching} onPress={() => void query.refetch()} />
      </View>
    </View>
  );
}

export interface Line {
  key: string;
  /** The account's name. */
  account: string;
  side: 'debit' | 'credit';
  amount: string;
  currency: string;
  /** Changes the account, where the lines are still a draft. */
  onChange?: () => void;
}

/**
 * An entry's lines as a ledger draws them: one head row (currency, debit,
 * credit), each line on its side, and a Total under a rule with a double
 * rule below. As the console's: the Total is shown only when each side is
 * one line in one currency, so it is that line's own amount, never a sum.
 */
export function LinesTable({ lines, currency, changeLabel, total = true }: { lines: readonly Line[]; currency: string; changeLabel?: (account: string) => string; total?: boolean }) {
  const theme = useTheme();
  const debits = lines.filter((l) => l.side === 'debit');
  const credits = lines.filter((l) => l.side === 'credit');
  const [debit] = debits;
  const [credit] = credits;
  const pair = total && debits.length === 1 && credits.length === 1 && debit && credit && debit.currency === credit.currency ? { debit, credit } : undefined;
  const head = [styles.linesHead, { color: theme.muted }];
  return (
    <View>
      <View style={[styles.linesRow, styles.linesHeadRow]}>
        <Text style={[head, styles.linesAccount]}>{currency}</Text>
        <Text style={[head, styles.linesFigure]}>{strings.entry.debit.toUpperCase()}</Text>
        <Text style={[head, styles.linesFigure]}>{strings.entry.credit.toUpperCase()}</Text>
      </View>
      {lines.map((line) => {
        const figure = <Money amount={line.amount} currency={line.currency} style={styles.linesRight} />;
        const name = line.onChange ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={changeLabel ? changeLabel(line.account) : line.account}
            onPress={line.onChange}
            style={styles.linesChange}
          >
            <Body>{line.account}</Body>
            <Icon name="down" size={14} colour={theme.muted} />
          </Pressable>
        ) : (
          <Body>{line.account}</Body>
        );
        return (
          <View key={line.key} style={[styles.linesRow, { borderTopColor: theme.rule, borderTopWidth: StyleSheet.hairlineWidth }]}>
            <View style={styles.linesAccount}>{name}</View>
            <View style={styles.linesFigure}>{line.side === 'debit' ? figure : null}</View>
            <View style={styles.linesFigure}>{line.side === 'credit' ? figure : null}</View>
          </View>
        );
      })}
      {pair ? (
        <View accessible style={[styles.linesRow, styles.linesTotal, { borderTopColor: theme.text, borderBottomColor: theme.text }]}>
          <Text style={[styles.linesTotalText, styles.linesAccount, { color: theme.text }]}>{strings.entry.total}</Text>
          <View style={styles.linesFigure}>
            <Money amount={pair.debit.amount} currency={pair.debit.currency} style={{ ...styles.linesRight, fontFamily: font.semibold }} />
          </View>
          <View style={styles.linesFigure}>
            <Money amount={pair.credit.amount} currency={pair.credit.currency} style={{ ...styles.linesRight, fontFamily: font.semibold }} />
          </View>
        </View>
      ) : null}
      {/* The double rule's second line. */}
      {pair ? <View style={[styles.linesDouble, { backgroundColor: theme.text }]} /> : null}
    </View>
  );
}

/** One of a few options, as a row of chips: a radio group under its label. */
export function Choice<V extends string | number>({ label, options, chosen, onPick }: { label: string; options: readonly { id: V; text: string }[]; chosen: V | undefined; onPick: (v: V) => void }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 8 }}>
      <Text style={[styles.choiceLabel, { color: theme.text }]}>{label}</Text>
      <View accessibilityRole="radiogroup" style={styles.choices}>
        {options.map((o) => {
          const on = o.id === chosen;
          return (
            <Pressable
              key={String(o.id)}
              accessibilityRole="radio"
              accessibilityState={{ checked: on }}
              onPress={() => onPick(o.id)}
              style={[styles.choice, { borderColor: on ? theme.text : theme.rule, backgroundColor: on ? theme.text : theme.card, borderRadius: Math.min(theme.control, 999) }]}
            >
              <Text style={[styles.choiceText, { color: on ? theme.work : theme.text }]}>{o.text}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

/**
 * A switch as the design draws it: square, ledger green with a paper knob
 * when on (sand and night on night), outlined with a stone knob when off. The
 * whole row is its target, and it is a switch to VoiceOver.
 */
export function Toggle({ label, help, value, disabled, onChange }: { label: string; help?: string; value: boolean; disabled?: boolean; onChange: (on: boolean) => void }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityLabel={label}
      {...(help ? { accessibilityHint: help } : {})}
      accessibilityState={{ checked: value, disabled: !!disabled }}
      disabled={disabled}
      onPress={() => onChange(!value)}
      style={[styles.toggleRow, disabled ? { opacity: 0.45 } : null]}
    >
      <View style={{ flex: 1, gap: 2 }}>
        <Body>{label}</Body>
        {help ? (
          <Body small muted>
            {help}
          </Body>
        ) : null}
      </View>
      <View style={[styles.track, { borderRadius: theme.control ? 999 : 0 }, value ? { backgroundColor: theme.button, justifyContent: 'flex-end' } : { backgroundColor: theme.card, borderColor: theme.muted, borderWidth: 1.5 }]}>
        <View style={[value ? [styles.knobOn, { backgroundColor: theme.buttonText }] : [styles.knobOff, { backgroundColor: theme.muted }], { borderRadius: theme.control ? 999 : 0 }]} />
      </View>
    </Pressable>
  );
}

/** A problem: what happened, then what to do. */
export function Problem({ title, body, mono, children }: { title: string; body: string; mono?: string; children?: ReactNode }) {
  // The address the app tried, set in mono wherever the body names it.
  const parts = mono ? body.split(mono) : [body];
  return (
    <Card style={{ gap: 10 }}>
      <Text accessibilityRole="header" style={[styles.heading, { color: useTheme().text }]}>
        {title}
      </Text>
      <Body>
        {parts.map((part, i) => (
          <Text key={i}>
            {part}
            {i < parts.length - 1 ? <Text style={styles.monoInline}>{mono}</Text> : null}
          </Text>
        ))}
      </Body>
      {children}
    </Card>
  );
}

const ICONS = {
  home: 'M4 11 12 4l8 7v9h-5v-6H9v6H4z',
  decide: 'M12 4v16M8 20h8M5 8h14M5 8l-2.5 6h5zM19 8l-2.5 6h5z',
  more: 'M4 7h16M4 12h16M4 17h16',
  plus: 'M12 5v14M5 12h14',
  chevron: 'M9 5l7 7-7 7',
  down: 'M6 9l6 6 6-6',
  back: 'M15 5l-7 7 7 7',
  external: 'M14 4h6v6M20 4l-9 9M18 14v6H4V6h6',
  upload: 'M12 16V5M7 10l5-5 5 5M5 20h14',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  up: 'M12 19V5M6 11l6-6 6 6',
  ai: 'M4 5h16v14H4zM8 10l2.5 2L8 14M12.5 14H16',
  scan: 'M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6M8 8h3v3H8zM13 13h3v3h-3zM13 8h3v3M8 13v3h3',
  tax: 'M6 3h9l3 3v15H6zM9 16l6-6M9 10h1.5M13.5 16H15',
  attention: 'M6 16v-5a6 6 0 0 1 12 0v5l2 2H4zM10 21h4',
  independence: 'M4 18l6-6 4 4 6-8M15 8h5v5',
  settings: 'M4 7h10M18 7h2M4 17h4M12 17h8M14 5h4v4h-4zM8 15h4v4H8z',
  server: 'M4 4h16v7H4zM4 13h16v7H4zM8 7.5h2M8 16.5h2',
  message: 'M4 5h16v11H10l-6 4zM8 9h8M8 12h5',
  // Your AI: a spark, a point with rays.
  spark: 'M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8M10.5 12a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0-3 0z',
  appearance: 'M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18zM12 3v18M12 8h4.5M12 12h6M12 16h4.5',
} as const;

export type IconName = keyof typeof ICONS | 'cash' | 'books';

/**
 * The console's icons: a 24 grid, 1.5 strokes, square caps, mitred joins;
 * other themes round them and change their weight. `fill` fills a closed
 * shape, as the bar does for the current place in some themes.
 */
export function Icon({ name, size: px = 24, colour, fill = 'none' }: { name: IconName; size?: number; colour: string; fill?: string }) {
  const theme = useTheme();
  const round = theme.iconCap === 'round';
  const stroke = { stroke: colour, strokeWidth: (theme.iconWidth * 24) / px, strokeLinecap: theme.iconCap, strokeLinejoin: round ? ('round' as const) : ('miter' as const), fill };
  const rx = round ? 3 : 0;
  return (
    <Svg width={px} height={px} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no">
      {name === 'cash' ? (
        <>
          <Rect x={3} y={7} width={18} height={10} rx={rx} {...stroke} />
          <Path d="M12 9.5v5M9.5 12h5" {...stroke} />
        </>
      ) : name === 'books' ? (
        <>
          <Rect x={4} y={4} width={16} height={16} rx={rx} {...stroke} />
          <Path d="M4 9h16M4 14h16M10 4v16" {...stroke} />
        </>
      ) : (
        <Path d={ICONS[name]} {...stroke} />
      )}
    </Svg>
  );
}

const styles = StyleSheet.create({
  choiceLabel: { fontFamily: font.medium, fontSize: size.small },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  choice: { borderWidth: 1, paddingHorizontal: 14, minHeight: 44, justifyContent: 'center' },
  choiceText: { fontFamily: font.regular, fontSize: size.body },
  monoInline: { fontFamily: font.mono, fontSize: size.small },
  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 64, paddingVertical: 8 },
  track: { width: 48, height: 28, padding: 3, flexDirection: 'row', alignItems: 'center' },
  knobOn: { width: 22, height: 22 },
  knobOff: { width: 19, height: 19 },
  ledgerRow: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 48, paddingVertical: 6 },
  ledgerLead: { width: 56, fontFamily: font.regular, fontSize: size.body },
  ledgerTitle: { flex: 1, minWidth: 0 },
  linesRow: { flexDirection: 'row', alignItems: 'center', minHeight: 48, gap: 8 },
  linesHeadRow: { minHeight: 28 },
  linesHead: { fontFamily: font.medium, fontSize: size.label, letterSpacing: size.label * 0.12 },
  linesAccount: { flex: 1, minWidth: 0 },
  linesFigure: { width: 84, alignItems: 'flex-end', textAlign: 'right' },
  linesRight: { textAlign: 'right' },
  linesChange: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start' },
  // A ledger's total: a rule above, a double rule below (React Native draws no double border: a second line under it).
  linesTotal: { borderTopWidth: 1, borderBottomWidth: 1, paddingVertical: 4 },
  linesDouble: { height: 1, marginTop: 2 },
  linesTotalText: { fontFamily: font.semibold, fontSize: size.body },
  card: { padding: 16, borderRadius: 0 },
  label: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 20 },
  square: { width: 8, height: 8, borderWidth: 1.5 },
  labelText: { fontFamily: font.medium, fontSize: size.label, letterSpacing: size.label * 0.12 },
  title: { fontFamily: font.semibold, fontSize: size.title, letterSpacing: -0.025 * size.title, lineHeight: size.title * 1.15 },
  heading: { fontFamily: font.medium, fontSize: size.heading, letterSpacing: -0.01 * size.heading, lineHeight: size.heading * 1.3 },
  body: { fontFamily: font.regular, fontSize: size.body, lineHeight: size.body * 1.45 },
  small: { fontFamily: font.regular, fontSize: size.small, lineHeight: size.small * 1.5 },
  button: { minHeight: size.target, paddingHorizontal: 18, flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center', borderRadius: 0, borderWidth: 1 },
  buttonText: { fontFamily: font.medium, fontSize: size.body },
  underline: { textDecorationLine: 'underline' },
  figureRow: { flexDirection: 'row', alignItems: 'baseline', gap: 6, flexWrap: 'wrap' },
  code: { fontFamily: font.mono, fontSize: 13 },
  figures: { fontVariant: ['tabular-nums'] },
  hero: { fontFamily: font.semibold, fontSize: size.figure, letterSpacing: -0.03 * size.figure, flexShrink: 1 },
  keyFigure: { fontFamily: font.medium, fontSize: size.keyFigure, letterSpacing: -0.01 * size.keyFigure, flexShrink: 1 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 64, paddingVertical: 8 },
  amountRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52, paddingVertical: 8 },
  bullet: { width: 6, height: 6 },
  rowText: { flex: 1, gap: 2 },
});
