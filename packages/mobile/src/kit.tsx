/**
 * The app's parts (docs/design/mobile.md, Components board): one shape scale,
 * depth from soft shadow, filled fields, capsule buttons and bars, 48 to
 * touch, 20 from every edge, figures exactly as the server sent them. Screens
 * are made only from these. A theme changes their colours and type, never
 * their shapes (theme.ts).
 */
import { SalliNetworkError } from '@leafmonkeylabs/salli-sdk';
import { forwardRef, useEffect, useRef, useState, type ComponentRef, type ReactNode } from 'react';
import { ActivityIndicator, Keyboard, Platform, Pressable, StyleSheet, Text, TextInput, View, useWindowDimensions, type LayoutChangeEvent, type PressableProps, type StyleProp, type TextInputProps, type TextStyle, type ViewStyle } from 'react-native';
import Animated, { Easing, ReduceMotion, cancelAnimation, useAnimatedStyle, useSharedValue, withRepeat, withSequence, withSpring, withTiming } from 'react-native-reanimated';
import Svg, { Circle, Path, Rect, SvgXml } from 'react-native-svg';
import { LOGO_DARK, LOGO_LIGHT } from './brand/logo';
import { amountParts } from './lib/display';
import { haptic, press, useReducedMotion } from './motion';
import { strings } from './strings';
import { elevation, font, radii, shape, size, useTheme, type Elevation } from './theme';

export { radii, shape };

/**
 * The phone's text size (Dynamic Type), as the layouts answer it: from xxxL
 * (a font scale of about 1.35) rows stack their title over their details and
 * tiles go one to a row; from the accessibility sizes (AX1, about 1.65) a
 * ledger's columns stack too. Text is never shrunk to fit.
 */
export function useLargeText(from: 'large' | 'ax' = 'large'): boolean {
  const { fontScale } = useWindowDimensions();
  return fontScale >= (from === 'ax' ? 1.6 : 1.3);
}

export function Logo({ height = 36 }: { height?: number }) {
  const theme = useTheme();
  // The file's viewBox is 472.214 × 137.829, its clear space inside it.
  return <SvgXml xml={theme.dark ? LOGO_DARK : LOGO_LIGHT} height={height} width={(height * 472.214) / 137.829} accessibilityLabel="Salli" />;
}

type SurfaceKind = 'card' | 'key' | 'inset';

/**
 * Where things sit: a white surface lifted by a soft shadow (on night a
 * lighter surface with a 1 px highlight along its top), never outlined.
 * `key` is the key figure's card (26 corners, 24 inside); `inset` is a
 * quiet fill inside a card. `pad={false}` for a list whose rows pad themselves.
 */
export function Surface({ children, kind = 'card', pad = true, level, style }: { children?: ReactNode; kind?: SurfaceKind; pad?: boolean; level?: Elevation; style?: StyleProp<ViewStyle> }) {
  const theme = useTheme();
  const r = kind === 'key' ? radii.key : kind === 'inset' ? radii.field : radii.card;
  const inner = kind === 'key' ? size.padKey : size.pad;
  return (
    <View
      style={[
        shape(r),
        { backgroundColor: kind === 'inset' ? theme.fill : theme.surface },
        kind === 'inset' ? null : elevation(theme, level ?? 'card'),
        pad ? { padding: kind === 'inset' ? size.gap + 4 : inner } : null,
        style,
      ]}
    >
      {kind !== 'inset' && theme.highlight ? <View pointerEvents="none" style={[styles.highlight, { backgroundColor: theme.highlight, left: r, right: r }]} /> : null}
      {children}
    </View>
  );
}

/** A card: the surface with 20 inside (`style` may set its gap). */
export function Card({ children, style, pad }: { children?: ReactNode; style?: ViewStyle; pad?: boolean }) {
  return (
    <Surface {...(pad === undefined ? {} : { pad })} {...(style ? { style } : {})}>
      {children}
    </Surface>
  );
}

/** A section's heading, outside its card, in sentence case with no marker (design Main, Type). */
export function SectionLabel({ children }: { children: string }) {
  const theme = useTheme();
  return (
    <Text accessibilityRole="header" maxFontSizeMultiplier={1.7} style={[styles.headline, { color: theme.text, flexShrink: 1 }]}>
      {children}
    </Text>
  );
}

/** A heading, a link at its end ("See all"), and what it heads, 10 apart. */
export function Section({ title, action, children }: { title: string; action?: { label: string; onPress: () => void; hint?: string }; children?: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={{ gap: size.heading }}>
      <View style={styles.sectionHead}>
        <SectionLabel>{title}</SectionLabel>
        {action ? (
          <Press accessibilityRole="link" {...(action.hint ? { accessibilityHint: action.hint } : {})} hitSlop={8} onPress={action.onPress} style={styles.sectionLink}>
            <Text maxFontSizeMultiplier={1.5} style={[styles.linkText, { color: theme.green }]}>
              {action.label}
            </Text>
          </Press>
        ) : null}
      </View>
      {children}
    </View>
  );
}

/** A place's title: 32 and large, growing with the text size to half again, so a long word never breaks. */
export function Title({ children }: { children: string }) {
  const theme = useTheme();
  return (
    <Text accessibilityRole="header" maxFontSizeMultiplier={1.5} style={[styles.title, { color: theme.text }]}>
      {children}
    </Text>
  );
}

/** Text in the body's size; `max` caps how far it grows with the text size (a bar's buttons, as iOS's own). */
export function Body({ children, muted, small, style, alert, max }: { children: ReactNode; muted?: boolean; small?: boolean; style?: TextStyle; alert?: boolean; max?: number }) {
  const theme = useTheme();
  return (
    <Text {...(alert ? { accessibilityRole: 'alert' as const, accessibilityLiveRegion: 'polite' as const } : {})} {...(max ? { maxFontSizeMultiplier: max } : {})} style={[small ? styles.small : styles.body, { color: muted ? theme.muted : theme.text }, style]}>{children}</Text>
  );
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

/**
 * Something to press, answering on the UI thread: it settles to 0.98 and dims
 * to 0.85 while held (Reduce Motion: it only dims). With `highlight`, a row
 * instead takes the fill behind it, which Reduce Motion keeps. Something
 * unavailable is drawn as such by its owner, never dimmed.
 */
export function Press({ style, onPressIn, onPressOut, highlight, ...rest }: Omit<PressableProps, 'style'> & { style?: StyleProp<ViewStyle>; highlight?: boolean }) {
  const theme = useTheme();
  const reduced = useReducedMotion();
  const held = useSharedValue(0);
  const [down, setDown] = useState(false);
  const answer = useAnimatedStyle(() => ({
    opacity: highlight ? 1 : 1 - held.value * (1 - press.opacity),
    transform: [{ scale: reduced || highlight ? 1 : 1 - held.value * (1 - press.scale) }],
  }));
  const to = (value: number, duration: number) => (held.value = withTiming(value, { duration, easing: press.easing, reduceMotion: ReduceMotion.Never }));
  return (
    <AnimatedPressable
      {...rest}
      onPressIn={(e) => {
        to(1, press.in);
        if (highlight) setDown(true);
        onPressIn?.(e);
      }}
      onPressOut={(e) => {
        to(0, press.out);
        if (highlight) setDown(false);
        onPressOut?.(e);
      }}
      style={[style, highlight && down ? [{ backgroundColor: theme.fill }, shape(radii.tile)] : null, answer]}
    />
  );
}

type ButtonKind = 'primary' | 'secondary' | 'tertiary';

/**
 * A capsule, 52 tall (or `sm`, 40 with a 48 target): the main one in ink, a
 * quiet one on the fill, a link in green. One that can't be used is filled and
 * muted, never dimmed, and its owner says what it waits for.
 */
export function Button({ label, kind = 'primary', busy, icon, small, ...rest }: { label: string; kind?: ButtonKind; busy?: boolean; icon?: IconName; small?: boolean } & Omit<PressableProps, 'children' | 'style'>) {
  const theme = useTheme();
  const unavailable = !!rest.disabled && !busy;
  const fill = kind === 'tertiary' ? 'transparent' : unavailable ? theme.fill : kind === 'primary' ? theme.button : theme.fill;
  const colour = unavailable ? theme.muted : kind === 'primary' ? theme.buttonText : kind === 'secondary' ? theme.text : theme.green;
  return (
    <Press
      accessibilityRole="button"
      accessibilityState={{ disabled: !!rest.disabled || !!busy, busy: !!busy }}
      hitSlop={small ? 4 : undefined}
      style={[styles.button, shape(radii.pill), small ? styles.buttonSmall : null, { backgroundColor: fill }, kind === 'tertiary' ? styles.buttonLink : null]}
      {...rest}
    >
      {busy ? <ActivityIndicator color={colour} /> : null}
      <Text maxFontSizeMultiplier={1.6} style={[styles.buttonText, { color: colour }]}>
        {label}
      </Text>
      {icon ? <Icon name={icon} size={18} colour={colour} /> : null}
    </Press>
  );
}

/** A round 40 button for the header (the AI, +): a 48 target around it. */
export function RoundButton({ icon, label, onPress, tone = 'fill' }: { icon: IconName; label: string; onPress: () => void; tone?: 'fill' | 'ink' }) {
  const theme = useTheme();
  return (
    <Press accessibilityRole="button" accessibilityLabel={label} hitSlop={4} onPress={onPress} style={[styles.round, shape(radii.pill), { backgroundColor: tone === 'ink' ? theme.button : theme.surface }, tone === 'ink' ? null : elevation(theme, 'card')]}>
      <Icon name={icon} size={20} colour={tone === 'ink' ? theme.buttonText : theme.text} />
    </Press>
  );
}

/**
 * An amount exactly as the server sent it: the code small before a key
 * figure, negatives in brackets, what a reader says spelled out. A `hero`
 * figure is 46, its decimals at half size and muted (the figure is still
 * exactly the server's). Ink always; `tone="red"` only for a fact that needs
 * the person: cash below zero, a budget over.
 */
export function Money({ amount, currency, figure, tone, style }: { amount: string; currency: string; figure?: 'key' | 'hero'; tone?: 'red'; style?: TextStyle }) {
  const theme = useTheme();
  const parts = amountParts(amount, currency);
  const shown = parts.negative ? `(${parts.digits})` : parts.digits;
  const colour = tone === 'red' ? theme.red : theme.text;
  if (!figure) {
    return (
      <Text accessibilityLabel={parts.spoken} style={[styles.figures, styles.body, { color: colour }, style]}>
        {shown}
      </Text>
    );
  }
  // Decimals after the last full stop, where there is one and it is the only one.
  const cut = /^([^.]+)(\.\d{1,3})(\)?)$/.exec(shown);
  return (
    <View accessible accessibilityLabel={parts.spoken} style={styles.figureRow}>
      <Text style={[styles.code, { color: theme.muted }]}>{currency}</Text>
      {/* Never shrunk to fit: the hero grows to 1.4 times at most, and any figure wraps rather than shrinks. */}
      <Text maxFontSizeMultiplier={figure === 'hero' ? 1.4 : undefined} style={[styles.figures, figure === 'hero' ? styles.hero : styles.keyFigure, { color: colour }, style]}>
        {figure === 'hero' && cut ? (
          <>
            {cut[1]}
            <Text style={{ fontSize: size.keyFigure / 2, color: theme.muted, letterSpacing: 0 }}>{cut[2]}</Text>
            {cut[3]}
          </>
        ) : (
          shown
        )}
      </Text>
    </View>
  );
}

/**
 * A list row: a dot, a title and a line under it, and what it opens. At
 * large text the title comes first and whole, its action under it.
 */
export function Row({ title, detail, hint, onPress, action, last, icon }: { title: string; detail?: string; hint?: string; onPress?: () => void; action?: ReactNode; last?: boolean; icon?: IconName }) {
  const theme = useTheme();
  const large = useLargeText();
  const content = (
    <>
      {icon && !large ? <IconTile name={icon} /> : large || icon ? null : <View style={[styles.bullet, shape(radii.pill), { backgroundColor: theme.muted }]} />}
      <View style={styles.rowText}>
        <Body>{title}</Body>
        {detail ? <Body small muted>{detail}</Body> : null}
        {large && action ? <View style={styles.under}>{action}</View> : null}
      </View>
      {large ? null : action}
      {onPress ? <Icon name="chevron" size={16} colour={theme.muted} /> : null}
    </>
  );
  const style = [styles.row, last ? null : { borderBottomColor: theme.line, borderBottomWidth: StyleSheet.hairlineWidth }];
  return onPress ? (
    <Press highlight accessibilityRole="button" {...(hint ? { accessibilityHint: hint } : {})} onPress={onPress} style={style}>
      {content}
    </Press>
  ) : (
    <View style={style}>{content}</View>
  );
}

/** An icon on a 40 tile in the tint, 10 corners: the leading mark of a row or a grouped list. */
export function IconTile({ name, tone = 'green' }: { name: IconName; tone?: 'green' | 'red' | 'fill' }) {
  const theme = useTheme();
  const bg = tone === 'red' ? theme.redTint : tone === 'fill' ? theme.fill : theme.greenTint;
  const fg = tone === 'red' ? theme.red : tone === 'fill' ? theme.text : theme.green;
  return (
    <View style={[styles.iconTile, shape(radii.tile), { backgroundColor: bg }]}>
      <Icon name={name} size={20} colour={fg} />
    </View>
  );
}

/** A row of Home's kind: the ledger's, on one line (a date, a name, the amount at the end), or its amount under it at large text. What the line leaves out goes in `label`, which VoiceOver reads for the whole row. */
export function LedgerRow({ lead, title, amount, currency, note, label, onPress, last }: { lead?: string; title: string; amount?: string; currency: string; note?: string; label?: string; onPress?: () => void; last?: boolean }) {
  const theme = useTheme();
  const large = useLargeText();
  const style = [styles.ledgerRow, last ? null : { borderBottomColor: theme.line, borderBottomWidth: StyleSheet.hairlineWidth }];
  const figure = amount !== undefined ? <Money amount={amount} currency={currency} style={large ? styles.linesRight : undefined} /> : note ? <Body small muted>{note}</Body> : null;
  const content = large ? (
    <>
      <View style={styles.rowText}>
        {lead ? <Text style={[styles.ledgerLead, styles.ledgerLeadLarge, { color: theme.muted }]}>{lead}</Text> : null}
        {title ? <Body>{title}</Body> : null}
        {figure}
      </View>
      {onPress ? <Icon name="chevron" size={16} colour={theme.muted} /> : null}
    </>
  ) : (
    <>
      {lead ? <Text style={[styles.ledgerLead, { color: theme.muted }]}>{lead}</Text> : null}
      <Body style={styles.ledgerTitle}>{title}</Body>
      {figure}
    </>
  );
  return onPress ? (
    <Press highlight accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={style}>
      {content}
    </Press>
  ) : (
    <View accessible accessibilityLabel={label} style={style}>
      {content}
    </View>
  );
}

/** A row with a figure at its end: a label, a line under it, the amount. At large text the label is whole on its line, the line and the amount under it. */
export function AmountRow({ title, detail, amount, currency, onPress, last, tone }: { title: string; detail?: string; amount: string; currency: string; onPress?: () => void; last?: boolean; tone?: 'red' }) {
  const theme = useTheme();
  const large = useLargeText();
  const style = [styles.amountRow, last ? null : { borderBottomColor: theme.line, borderBottomWidth: StyleSheet.hairlineWidth }];
  const content = large ? (
    <>
      <View style={styles.rowText}>
        <Body>{title}</Body>
        <View style={styles.stacked}>
          <Body small muted style={styles.stackedLabel}>
            {detail ?? ''}
          </Body>
          <Money amount={amount} currency={currency} {...(tone ? { tone } : {})} style={styles.stackedFigure} />
        </View>
      </View>
      {onPress ? <Icon name="chevron" size={16} colour={theme.muted} /> : null}
    </>
  ) : (
    <>
      <View style={styles.rowText}>
        <Body>{title}</Body>
        {detail ? (
          <Body small muted>
            {detail}
          </Body>
        ) : null}
      </View>
      <Money amount={amount} currency={currency} {...(tone ? { tone } : {})} />
      {onPress ? <Icon name="chevron" size={16} colour={theme.muted} /> : null}
    </>
  );
  return onPress ? (
    <Press highlight accessibilityRole="button" onPress={onPress} style={style}>
      {content}
    </Press>
  ) : (
    <View style={style}>{content}</View>
  );
}

/** A card's first line: its heading, and a line saying what it holds. */
export function CardHead({ label, help, end }: { label: string; help?: string; end?: string }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 4, paddingBottom: 4 }}>
      {/* Its end goes under the label when the two don't fit on one line. */}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', columnGap: 12 }}>
        <SectionLabel>{label}</SectionLabel>
        {end ? (
          <Text maxFontSizeMultiplier={1.7} style={[styles.labelText, { color: theme.muted }]}>
            {end}
          </Text>
        ) : null}
      </View>
      {help ? (
        <Body small muted>
          {help}
        </Body>
      ) : null}
    </View>
  );
}

/** A shape where a figure will land, at its final size, softly pulsing (still under Reduce Motion), so nothing jumps when the figures arrive. */
export function Skeleton({ width = '100%', height = 16, radius = radii.tile, style }: { width?: number | `${number}%`; height?: number; radius?: number; style?: StyleProp<ViewStyle> }) {
  const theme = useTheme();
  const reduced = useReducedMotion();
  const pulse = useSharedValue(1);
  useEffect(() => {
    if (reduced) {
      pulse.value = 0.7;
      return;
    }
    pulse.value = withRepeat(withSequence(withTiming(0.45, { duration: 900, easing: Easing.inOut(Easing.quad) }), withTiming(1, { duration: 900, easing: Easing.inOut(Easing.quad) })), -1);
    return () => cancelAnimation(pulse);
  }, [reduced, pulse]);
  const animated = useAnimatedStyle(() => ({ opacity: pulse.value }));
  return <Animated.View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={[{ width, height, backgroundColor: theme.fill }, shape(radius), animated, style]} />;
}

export function Loading({ what }: { what: string }) {
  return (
    <View accessible accessibilityLabel={what} style={{ gap: 10, paddingVertical: 8 }}>
      <Skeleton width="60%" height={14} />
      <Skeleton height={14} />
    </View>
  );
}

/**
 * A read on its way: shapes while it is, and once it has failed, why,
 * with a way to ask again. A failed read never waits forever.
 */
export function Waiting({ query, what }: { query: { error: Error | null; isRefetching: boolean; refetch: () => unknown }; what: string }) {
  if (!query.error) return <Loading what={strings.home.loading(what)} />;
  return (
    <View style={{ gap: 12, paddingVertical: 8 }}>
      <Notice tone="warn">{query.error instanceof SalliNetworkError ? strings.reach.cantRead(what) : strings.reach.failed(what, query.error.message)}</Notice>
      <View style={{ alignSelf: 'flex-start' }}>
        <Button kind="secondary" small label={strings.reach.tryAgain} busy={query.isRefetching} disabled={query.isRefetching} onPress={() => void query.refetch()} />
      </View>
    </View>
  );
}

type NoticeTone = 'info' | 'warn' | 'good' | 'neutral';

/** A note in a tint with an icon and no outline: green for what is fine or only to know, red for a fact that needs the person. */
export function Notice({ tone = 'info', icon, children, action }: { tone?: NoticeTone; icon?: IconName; children: ReactNode; action?: ReactNode }) {
  const theme = useTheme();
  const bg = tone === 'warn' ? theme.redTint : tone === 'neutral' ? theme.fill : theme.greenTint;
  const fg = tone === 'warn' ? theme.red : tone === 'neutral' ? theme.muted : theme.green;
  const mark: IconName = icon ?? (tone === 'warn' ? 'info' : tone === 'good' ? 'check' : 'info');
  return (
    <View {...(tone === 'warn' ? { accessibilityRole: 'alert' as const } : {})} style={[styles.notice, shape(radii.field), { backgroundColor: bg }]}>
      <View style={styles.noticeRow}>
        <View style={styles.noticeIcon}>
          <Icon name={mark} size={20} colour={fg} />
        </View>
        <View style={{ flex: 1, gap: 8 }}>
          {typeof children === 'string' ? <Body small>{children}</Body> : children}
          {action}
        </View>
      </View>
    </View>
  );
}

/** A small fact about a thing: draft, a rule, "By hand". Capitals never; 6 corners. */
export function Tag({ children, tone = 'neutral' }: { children: string; tone?: 'neutral' | 'green' | 'red' }) {
  const theme = useTheme();
  const bg = tone === 'green' ? theme.greenTint : tone === 'red' ? theme.redTint : theme.fill;
  const fg = tone === 'green' ? theme.green : tone === 'red' ? theme.red : theme.muted;
  return (
    <View style={[styles.tag, shape(radii.tag), { backgroundColor: bg }]}>
      <Text maxFontSizeMultiplier={1.6} style={[styles.tagText, { color: fg }]}>
        {children}
      </Text>
    </View>
  );
}

/** A count in a capsule, 22 at least. */
export function Badge({ count, label }: { count: number; label?: string }) {
  const theme = useTheme();
  return (
    <View accessible={!!label} {...(label ? { accessibilityLabel: label } : {})} style={[styles.badge, shape(radii.pill), { backgroundColor: theme.greenTint }]}>
      <Text maxFontSizeMultiplier={1.4} style={[styles.badgeText, { color: theme.green }]}>
        {count}
      </Text>
    </View>
  );
}

/** A choice or a filter as a capsule: on the fill, and in the green tint when chosen. A light tap of haptics. */
export function Chip({ label, selected, onPress, icon, role = 'radio' }: { label: string; selected?: boolean; onPress: () => void; icon?: IconName; role?: 'radio' | 'button' | 'checkbox' }) {
  const theme = useTheme();
  const colour = selected ? theme.green : theme.text;
  return (
    <Press
      accessibilityRole={role}
      accessibilityState={role === 'button' ? {} : role === 'checkbox' ? { checked: !!selected } : { checked: !!selected }}
      hitSlop={{ top: 4, bottom: 4 }}
      onPress={() => {
        haptic.select();
        onPress();
      }}
      style={[styles.chip, shape(radii.pill), { backgroundColor: selected ? theme.greenTint : theme.fill }]}
    >
      {icon ? <Icon name={icon} size={16} colour={colour} /> : null}
      <Text maxFontSizeMultiplier={1.6} style={[styles.chipText, { color: colour, fontFamily: selected ? font.medium : font.regular }]}>
        {label}
      </Text>
    </Press>
  );
}

/**
 * A few options in a capsule track with a thumb that slides to the chosen one
 * (Reduce Motion: it moves at once), a light haptic on each pick.
 */
export function Segmented<V extends string>({ options, value, onChange, label }: { options: readonly { id: V; text: string }[]; value: V; onChange: (v: V) => void; label: string }) {
  const theme = useTheme();
  const reduced = useReducedMotion();
  const [width, setWidth] = useState(0);
  const index = Math.max(0, options.findIndex((o) => o.id === value));
  const each = options.length ? Math.max(0, width - 6) / options.length : 0;
  const x = useSharedValue(index * each);
  useEffect(() => {
    x.value = reduced ? withTiming(index * each, { duration: 0 }) : withSpring(index * each, { stiffness: 500, damping: 40, mass: 1 });
  }, [index, each, reduced, x]);
  const thumb = useAnimatedStyle(() => ({ transform: [{ translateX: x.value }] }));
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={label} onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)} style={[styles.segmented, shape(radii.pill), { backgroundColor: theme.fill }]}>
      {each > 0 ? <Animated.View style={[styles.thumb, shape(radii.pill), { width: each, backgroundColor: theme.surface }, elevation(theme, 'card'), thumb]} /> : null}
      {options.map((o) => (
        <Pressable
          key={o.id}
          accessibilityRole="radio"
          accessibilityState={{ checked: o.id === value }}
          onPress={() => {
            if (o.id === value) return;
            haptic.select();
            onChange(o.id);
          }}
          style={styles.segment}
        >
          <Text maxFontSizeMultiplier={1.4} numberOfLines={1} style={[styles.chipText, { color: theme.text, fontFamily: o.id === value ? font.medium : font.regular }]}>
            {o.text}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

export type FieldProps = Omit<TextInputProps, 'style'> & {
  label?: string;
  help?: string;
  /** Says what is wrong in words, under the field, with a red ring. */
  error?: string;
  /** An address, an id or a code: in Geist Mono. */
  mono?: boolean;
  /** An amount: a large centred figure. */
  amount?: boolean;
  /** Something at the field's end: a unit, an icon. */
  end?: ReactNode;
  style?: StyleProp<ViewStyle>;
};

/**
 * The one text field: filled, borderless, 14 corners, 52 tall, a ring in
 * green while it is being typed in (red when it is wrong). Its label sits
 * above and names it to VoiceOver.
 */
export const Field = forwardRef<ComponentRef<typeof TextInput>, FieldProps>(function Field({ label, help, error, mono, amount, end, multiline, style, onFocus, onBlur, ...rest }, ref) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  const ring = error ? theme.red : focused ? theme.green : 'transparent';
  return (
    <View style={[{ gap: 6 }, style]}>
      {label ? (
        <Text maxFontSizeMultiplier={1.7} style={[styles.fieldLabel, { color: theme.text }]}>
          {label}
        </Text>
      ) : null}
      <View style={[styles.field, shape(radii.field), multiline ? styles.fieldMulti : null, amount ? styles.fieldAmount : null, { backgroundColor: theme.fill, borderColor: ring }]}>
        <TextInput
          ref={ref}
          accessibilityLabel={rest.accessibilityLabel ?? label}
          multiline={multiline}
          placeholderTextColor={theme.muted}
          selectionColor={theme.green}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
          {...rest}
          style={[styles.input, { color: theme.text, fontFamily: mono ? font.mono : amount ? font.medium : font.regular }, amount ? styles.inputAmount : null, multiline ? styles.inputMulti : null]}
        />
        {end}
      </View>
      {error ? (
        <Text accessibilityRole="alert" maxFontSizeMultiplier={1.7} style={[styles.fieldHelp, { color: theme.red }]}>
          {error}
        </Text>
      ) : help ? (
        <Text maxFontSizeMultiplier={1.7} style={[styles.fieldHelp, { color: theme.muted }]}>
          {help}
        </Text>
      ) : null}
    </View>
  );
});

/**
 * One of a few options under its label: a row of chips, or with `list` a
 * list of `Option` rows, the chosen one with a checkmark.
 */
export function Choice<V extends string | number>({ label, options, chosen, onPick, list }: { label: string; options: readonly { id: V; text: string }[]; chosen: V | undefined; onPick: (v: V) => void; list?: boolean }) {
  const theme = useTheme();
  return (
    <View style={{ gap: list ? 6 : 8 }}>
      <Text maxFontSizeMultiplier={1.7} style={[styles.fieldLabel, { color: theme.text }]}>{label}</Text>
      <View accessibilityRole="radiogroup" accessibilityLabel={label} style={list ? null : styles.choices}>
        {options.map((o) =>
          list ? <Option key={String(o.id)} label={o.text} chosen={o.id === chosen} onPress={() => onPick(o.id)} /> : <Chip key={String(o.id)} label={o.text} selected={o.id === chosen} onPress={() => onPick(o.id)} />,
        )}
      </View>
    </View>
  );
}

/**
 * One row of a list to choose one from: its name, a line under it, and a
 * checkmark at its end when chosen, as iOS lists mark it (never a radio circle).
 */
export function Option({ label, detail, end, chosen, disabled, onPress, accessibilityLabel, last }: { label: string; detail?: string; end?: ReactNode; chosen: boolean; disabled?: boolean; onPress: () => void; accessibilityLabel?: string; last?: boolean }) {
  const theme = useTheme();
  return (
    <Press
      highlight
      accessibilityRole="radio"
      accessibilityState={{ checked: chosen, disabled: !!disabled }}
      {...(accessibilityLabel ? { accessibilityLabel } : {})}
      disabled={disabled}
      onPress={onPress}
      style={[styles.option, last ? null : { borderBottomColor: theme.line, borderBottomWidth: StyleSheet.hairlineWidth }]}
    >
      <View style={styles.rowText}>
        <Body style={chosen ? { fontFamily: font.medium } : undefined}>{label}</Body>
        {detail ? (
          <Body small muted>
            {detail}
          </Body>
        ) : null}
      </View>
      {end}
      {chosen ? <Icon name="check" size={20} colour={theme.green} /> : null}
    </Press>
  );
}

/**
 * A switch as iOS draws it: a capsule, green when on, a white knob that
 * slides (Reduce Motion: at once) with a light tap. The whole row is its
 * target, and it is a switch to VoiceOver.
 */
export function Toggle({ label, help, value, disabled, onChange }: { label: string; help?: string; value: boolean; disabled?: boolean; onChange: (on: boolean) => void }) {
  const theme = useTheme();
  const reduced = useReducedMotion();
  const on = useSharedValue(value ? 1 : 0);
  useEffect(() => {
    on.value = withTiming(value ? 1 : 0, { duration: reduced ? 0 : 160, easing: Easing.out(Easing.quad), reduceMotion: ReduceMotion.Never });
  }, [value, reduced, on]);
  const knob = useAnimatedStyle(() => ({ transform: [{ translateX: on.value * 20 }] }));
  const fillOn = useAnimatedStyle(() => ({ opacity: on.value }));
  return (
    <Press
      highlight
      accessibilityRole="switch"
      accessibilityLabel={label}
      {...(help ? { accessibilityHint: help } : {})}
      accessibilityState={{ checked: value, disabled: !!disabled }}
      disabled={disabled}
      onPress={() => {
        haptic.select();
        onChange(!value);
      }}
      style={styles.toggleRow}
    >
      {/* Unavailable, it is said in the muted ink, never dimmed. */}
      <View style={{ flex: 1, gap: 2 }}>
        <Body muted={!!disabled}>{label}</Body>
        {help ? (
          <Body small muted>
            {help}
          </Body>
        ) : null}
      </View>
      <View style={[styles.track, shape(radii.pill), { backgroundColor: theme.fill }]}>
        <View style={[StyleSheet.absoluteFill, shape(radii.pill), { backgroundColor: theme.muted, opacity: 0.3 }]} />
        <Animated.View style={[StyleSheet.absoluteFill, shape(radii.pill), { backgroundColor: theme.green }, fillOn]} />
        <Animated.View style={[styles.knob, shape(radii.pill), { backgroundColor: '#FFFFFF' }, knob]} />
      </View>
    </Press>
  );
}

/** A capsule bar for a share of something: `ratio` is 0 to 1 and comes from the server's own percentage; never worked out from money here. */
export function ProgressBar({ ratio, tone = 'green', height = 8, label }: { ratio: number; tone?: 'green' | 'red'; height?: number; label?: string }) {
  const theme = useTheme();
  const share = Math.max(0, Math.min(1, ratio));
  return (
    <View accessible={!!label} accessibilityRole="progressbar" {...(label ? { accessibilityLabel: label } : {})} style={[{ height, backgroundColor: theme.fill, overflow: 'hidden' }, shape(radii.pill)]}>
      {share > 0 ? <View style={[{ height, width: `${share * 100}%`, backgroundColor: tone === 'red' ? theme.red : theme.green }, shape(radii.pill)]} /> : null}
    </View>
  );
}

/** A ring with round ends for a share, 0 to 1; what it holds goes in the middle. */
export function Ring({ ratio, diameter = 56, stroke = 6, tone = 'green', children }: { ratio: number; diameter?: number; stroke?: number; tone?: 'green' | 'red'; children?: ReactNode }) {
  const theme = useTheme();
  const share = Math.max(0, Math.min(1, ratio));
  const r = (diameter - stroke) / 2;
  const whole = 2 * Math.PI * r;
  return (
    <View style={{ width: diameter, height: diameter, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={diameter} height={diameter} style={StyleSheet.absoluteFill} accessibilityElementsHidden importantForAccessibility="no">
        <Circle cx={diameter / 2} cy={diameter / 2} r={r} stroke={theme.fill} strokeWidth={stroke} fill="none" />
        {share > 0 ? (
          <Circle cx={diameter / 2} cy={diameter / 2} r={r} stroke={tone === 'red' ? theme.red : theme.green} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={`${whole * share} ${whole}`} fill="none" rotation={-90} originX={diameter / 2} originY={diameter / 2} />
        ) : null}
      </Svg>
      {children}
    </View>
  );
}

/** A problem: what happened, then what to do. */
export function Problem({ title, body, mono, children }: { title: string; body: string; mono?: string; children?: ReactNode }) {
  // The address the app tried, set in mono wherever the body names it.
  const parts = mono ? body.split(mono) : [body];
  return (
    <Card style={{ gap: 12 }}>
      <Text accessibilityRole="header" style={[styles.headline, { color: useTheme().text }]}>
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
 * The figure columns grow with the text size; at the accessibility sizes
 * each line stacks, its account over its side and figure (design LargeLedger).
 */
export function LinesTable({ lines, currency, changeLabel, total = true }: { lines: readonly Line[]; currency: string; changeLabel?: (account: string) => string; total?: boolean }) {
  const theme = useTheme();
  const { fontScale } = useWindowDimensions();
  const stacked = useLargeText('ax');
  const debits = lines.filter((l) => l.side === 'debit');
  const credits = lines.filter((l) => l.side === 'credit');
  const [debit] = debits;
  const [credit] = credits;
  const pair = total && debits.length === 1 && credits.length === 1 && debit && credit && debit.currency === credit.currency ? { debit, credit } : undefined;
  const head = [styles.linesHead, { color: theme.muted }];
  const column = { minWidth: Math.round(84 * Math.max(1, fontScale)) };
  const sideName = (side: Line['side']) => (side === 'debit' ? strings.entry.debit : strings.entry.credit);
  const nameOf = (line: Line) =>
    line.onChange ? (
      <Pressable accessibilityRole="button" accessibilityLabel={changeLabel ? changeLabel(line.account) : line.account} onPress={line.onChange} style={styles.linesChange}>
        <Body>{line.account}</Body>
        <Icon name="down" size={14} colour={theme.muted} />
      </Pressable>
    ) : (
      <Body>{line.account}</Body>
    );
  const bold = { ...styles.linesRight, fontFamily: font.semibold };
  if (stacked) {
    return (
      <View>
        <Text style={[head, styles.linesHeadRow]}>{currency}</Text>
        {lines.map((line) => (
          <View key={line.key} style={[styles.linesStack, { borderTopColor: theme.line, borderTopWidth: StyleSheet.hairlineWidth }]}>
            {nameOf(line)}
            <View style={styles.stacked}>
              <Body small muted style={styles.stackedLabel}>
                {sideName(line.side)}
              </Body>
              <Money amount={line.amount} currency={line.currency} style={styles.stackedFigure} />
            </View>
          </View>
        ))}
        {pair ? (
          <View accessible style={[styles.linesStack, styles.linesTotal, { borderTopColor: theme.text, borderBottomColor: theme.text }]}>
            <Text style={[styles.linesTotalText, { color: theme.text }]}>{strings.entry.total}</Text>
            {[pair.debit, pair.credit].map((line) => (
              <View key={line.side} style={styles.stacked}>
                <Text style={[styles.linesTotalSide, styles.stackedLabel, { color: theme.text }]}>{sideName(line.side)}</Text>
                <Money amount={line.amount} currency={line.currency} style={{ ...styles.stackedFigure, fontFamily: font.semibold }} />
              </View>
            ))}
          </View>
        ) : null}
        {pair ? <View style={[styles.linesDouble, { backgroundColor: theme.text }]} /> : null}
      </View>
    );
  }
  return (
    <View>
      <View style={[styles.linesRow, styles.linesHeadRow]}>
        <Text style={[head, styles.linesAccount]}>{currency}</Text>
        <Text style={[head, styles.linesFigure, column]}>{strings.entry.debit}</Text>
        <Text style={[head, styles.linesFigure, column]}>{strings.entry.credit}</Text>
      </View>
      {lines.map((line) => {
        const figure = <Money amount={line.amount} currency={line.currency} style={styles.linesRight} />;
        return (
          <View key={line.key} style={[styles.linesRow, { borderTopColor: theme.line, borderTopWidth: StyleSheet.hairlineWidth }]}>
            <View style={styles.linesAccount}>{nameOf(line)}</View>
            <View style={[styles.linesFigure, column]}>{line.side === 'debit' ? figure : null}</View>
            <View style={[styles.linesFigure, column]}>{line.side === 'credit' ? figure : null}</View>
          </View>
        );
      })}
      {pair ? (
        <View accessible style={[styles.linesRow, styles.linesTotal, { borderTopColor: theme.text, borderBottomColor: theme.text }]}>
          <Text style={[styles.linesTotalText, styles.linesAccount, { color: theme.text }]}>{strings.entry.total}</Text>
          <View style={[styles.linesFigure, column]}>
            <Money amount={pair.debit.amount} currency={pair.debit.currency} style={bold} />
          </View>
          <View style={[styles.linesFigure, column]}>
            <Money amount={pair.credit.amount} currency={pair.credit.currency} style={bold} />
          </View>
        </View>
      ) : null}
      {/* The double rule's second line. */}
      {pair ? <View style={[styles.linesDouble, { backgroundColor: theme.text }]} /> : null}
    </View>
  );
}

/**
 * The bar over a form's keyboard (design KeypadDone), shared by every number
 * pad: Previous and Next between the form's fields, in the order they are
 * drawn, and Done to put the keyboard away. Each field takes `field(key)`;
 * the screen draws `bar` once, as its last child. On a screen whose bottom
 * is the window's it rides on the keyboard; in a sheet (`inSheet`), which
 * rises with the keyboard, it sits at the sheet's foot. iOS only: Android's
 * keyboards have their own.
 */
export function useDoneBar(inSheet = false) {
  const theme = useTheme();
  const inputs = useRef(new Map<string, ComponentRef<typeof TextInput>>());
  // The fields in the order the last render drew them; this render's list is kept once it is drawn.
  const order = useRef<string[]>([]);
  const drawn: string[] = [];
  useEffect(() => {
    order.current = drawn;
  });
  const [focused, setFocused] = useState<string | undefined>(undefined);
  const [keyboard, setKeyboard] = useState(0);
  useEffect(() => {
    if (Platform.OS !== 'ios') return;
    const shown = Keyboard.addListener('keyboardWillShow', (e) => setKeyboard(e.endCoordinates.height));
    const hidden = Keyboard.addListener('keyboardWillHide', () => setKeyboard(0));
    return () => {
      shown.remove();
      hidden.remove();
    };
  }, []);
  const field = (key: string) => {
    drawn.push(key);
    return {
      ref: (input: ComponentRef<typeof TextInput> | null) => void (input ? inputs.current.set(key, input) : inputs.current.delete(key)),
      onFocus: () => setFocused(key),
      onBlur: () => setFocused((now) => (now === key ? undefined : now)),
    };
  };
  const go = (step: number) => {
    const keys = order.current;
    const next = keys[keys.indexOf(focused ?? '') + step];
    if (focused && next) inputs.current.get(next)?.focus();
  };
  const at = order.current.indexOf(focused ?? '');
  const key = (label: string, icon: IconName, step: number, off: boolean) => (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: off }} disabled={off} onPress={() => go(step)} style={styles.doneKey}>
      <Icon name={icon} colour={off ? theme.muted : theme.text} />
    </Pressable>
  );
  const bar =
    Platform.OS === 'ios' && keyboard > 0 && focused !== undefined ? (
      <View accessibilityRole="toolbar" style={[styles.doneBar, { bottom: inSheet ? 0 : keyboard, backgroundColor: theme.ground, borderTopColor: theme.line }]}>
        {key(strings.keys.previous, 'raise', -1, at <= 0)}
        {key(strings.keys.next, 'down', 1, at < 0 || at >= order.current.length - 1)}
        <Pressable accessibilityRole="button" onPress={() => Keyboard.dismiss()} style={[styles.doneKey, { marginLeft: 'auto', paddingHorizontal: 12 }]}>
          <Text maxFontSizeMultiplier={1.5} style={[styles.doneText, { color: theme.green }]}>
            {strings.keys.done}
          </Text>
        </Pressable>
      </View>
    ) : null;
  return { field, bar };
}

const ICONS = {
  home: 'M4 11.2 11.2 4.6a1.2 1.2 0 0 1 1.6 0L20 11.2V19a1.5 1.5 0 0 1-1.5 1.5H15V15a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v5.5H5.5A1.5 1.5 0 0 1 4 19z',
  decide: 'M12 4v16M8 20h8M5 8h14M5 8l-2.5 6a2.5 2.5 0 0 0 5 0zM19 8l-2.5 6a2.5 2.5 0 0 0 5 0z',
  more: 'M5 7h14M5 12h14M5 17h14',
  plus: 'M12 5v14M5 12h14',
  chevron: 'M9.5 5.5l6.5 6.5-6.5 6.5',
  down: 'M6 9.5l6 6 6-6',
  back: 'M14.5 5.5L8 12l6.5 6.5',
  external: 'M14 4.5h5.5V10M19.5 4.5l-9 9M17.5 14v4a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 18V8A1.5 1.5 0 0 1 6 6.5h4',
  upload: 'M12 16V5M7.5 9.5L12 5l4.5 4.5M5 15v3a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 18v-3',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  up: 'M12 19V5M6.5 10.5L12 5l5.5 5.5',
  ai: 'M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9L12 17.5l-1.9-5.1L5 10.5l5.1-1.9zM18.5 16.5v3M17 18h3',
  scan: 'M4 8.5V6a2 2 0 0 1 2-2h2.5M15.5 4H18a2 2 0 0 1 2 2v2.5M20 15.5V18a2 2 0 0 1-2 2h-2.5M8.5 20H6a2 2 0 0 1-2-2v-2.5M8 9.5h3v3H8zM13 12.5h3v3h-3zM13 9.5h3M8 14v1.5h3',
  tax: 'M7 3.5h7.5L18.5 7.5V19a1.5 1.5 0 0 1-1.5 1.5H7A1.5 1.5 0 0 1 5.5 19V5A1.5 1.5 0 0 1 7 3.5zM9.5 15.5l5-5M9.5 10.5h.01M14.5 15.5h.01',
  attention: 'M6 16v-5a6 6 0 0 1 12 0v5l1.5 1.5a.5.5 0 0 1-.4.8H4.9a.5.5 0 0 1-.4-.8zM10 20.5h4',
  independence: 'M4.5 18l5.5-5.5 3.5 3.5 6-7.5M15.5 8.5H20V13',
  settings: 'M4 7h9M17 7h3M4 17h3M11 17h9M15 5a2 2 0 1 1 0 4a2 2 0 0 1 0-4zM9 15a2 2 0 1 1 0 4a2 2 0 0 1 0-4z',
  server: 'M6 4.5h12A1.5 1.5 0 0 1 19.5 6v4A1.5 1.5 0 0 1 18 11.5H6A1.5 1.5 0 0 1 4.5 10V6A1.5 1.5 0 0 1 6 4.5zM6 12.5h12a1.5 1.5 0 0 1 1.5 1.5v4a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 18v-4A1.5 1.5 0 0 1 6 12.5zM8 8h.01M8 16h.01',
  message: 'M6 5h12a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-6.5L7.5 19.5V16H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zM8.5 9.5h7M8.5 12.5h4',
  raise: 'M6.5 14.5L12 9l5.5 5.5',
  info: 'M12 3.5a8.5 8.5 0 1 0 0 17a8.5 8.5 0 0 0 0-17zM12 11v5M12 8h.01',
  silent: 'M6 16v-5a6 6 0 0 1 9.2-5.1M18 10.5V16l1.5 1.5H8.5M10 20.5h4M4.5 4.5l15 15',
  // Your AI: a spark, a point with rays.
  spark: 'M12 3.5v3M12 17.5v3M3.5 12h3M17.5 12h3M6 6l2 2M16 16l2 2M6 18l2-2M16 8l2-2M10.5 12a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0-3 0z',
  appearance: 'M12 3.5a8.5 8.5 0 1 0 0 17a8.5 8.5 0 0 0 0-17zM12 3.5v17M12 8h4M12 12h5M12 16h4',
  close: 'M6.5 6.5l11 11M17.5 6.5l-11 11',
  search: 'M10.5 4.5a6 6 0 1 0 0 12a6 6 0 0 0 0-12zM15 15l4.5 4.5',
  calendar: 'M7 3.5v3M17 3.5v3M6 5.5h12A1.5 1.5 0 0 1 19.5 7v11.5A1.5 1.5 0 0 1 18 20H6a1.5 1.5 0 0 1-1.5-1.5V7A1.5 1.5 0 0 1 6 5.5zM4.5 10h15',
} as const;

export type IconName = keyof typeof ICONS | 'cash' | 'books';

/**
 * Icons on a 24 grid with round caps and joins and inner corners of 2.5 to
 * 3.5; the stroke is the theme's. `fill` fills a closed shape.
 */
export function Icon({ name, size: px = 24, colour, fill = 'none' }: { name: IconName; size?: number; colour: string; fill?: string }) {
  const theme = useTheme();
  const stroke = { stroke: colour, strokeWidth: (theme.iconWidth * 24) / px, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, fill };
  return (
    <Svg width={px} height={px} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no">
      {name === 'cash' ? (
        <>
          <Rect x={3} y={6.5} width={18} height={11} rx={3.5} {...stroke} />
          <Path d="M12 9.5v5M9.5 12h5" {...stroke} />
        </>
      ) : name === 'books' ? (
        <>
          <Rect x={4} y={4} width={16} height={16} rx={3.5} {...stroke} />
          <Path d="M4 9.5h16M4 14.5h16M10 4v16" {...stroke} />
        </>
      ) : (
        <Path d={ICONS[name]} {...stroke} />
      )}
    </Svg>
  );
}

const styles = StyleSheet.create({
  highlight: { position: 'absolute', top: 0, height: 1 },
  headline: { fontFamily: font.semibold, fontSize: size.headline, letterSpacing: -0.01 * size.headline, lineHeight: size.headline * 1.3 },
  sectionHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', columnGap: 12, minHeight: 24 },
  sectionLink: { minHeight: 32, justifyContent: 'center' },
  linkText: { fontFamily: font.medium, fontSize: size.small },
  title: { fontFamily: font.semibold, fontSize: size.largeTitle, letterSpacing: -0.025 * size.largeTitle, lineHeight: size.largeTitle * 1.15 },
  body: { fontFamily: font.regular, fontSize: size.body, lineHeight: size.body * 1.45 },
  small: { fontFamily: font.regular, fontSize: size.small, lineHeight: size.small * 1.5 },
  button: { minHeight: size.control, paddingHorizontal: 24, flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' },
  buttonSmall: { minHeight: 40, paddingHorizontal: 18 },
  buttonLink: { paddingHorizontal: 8 },
  buttonText: { fontFamily: font.medium, fontSize: size.body },
  round: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  figureRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' },
  code: { fontFamily: font.mono, fontSize: size.label },
  figures: { fontVariant: ['tabular-nums'] },
  hero: { fontFamily: font.medium, fontSize: size.keyFigure, letterSpacing: -0.03 * size.keyFigure, flexShrink: 1 },
  keyFigure: { fontFamily: font.medium, fontSize: size.figure, letterSpacing: -0.01 * size.figure, flexShrink: 1 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 64, paddingVertical: 8 },
  amountRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingVertical: 8 },
  iconTile: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  bullet: { width: 6, height: 6 },
  rowText: { flex: 1, gap: 2 },
  under: { alignSelf: 'flex-start', marginTop: 6 },
  ledgerRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingVertical: 6 },
  ledgerLead: { width: 56, fontFamily: font.regular, fontSize: size.body },
  ledgerLeadLarge: { width: undefined },
  ledgerTitle: { flex: 1, minWidth: 0 },
  // A label and its figure on one line, the figure on its own line, at the end, when both don't fit.
  stacked: { flexDirection: 'row', alignItems: 'baseline', columnGap: 12, flexWrap: 'wrap' },
  stackedLabel: { flexGrow: 1, flexShrink: 0 },
  stackedFigure: { flexGrow: 1, textAlign: 'right' },
  labelText: { fontFamily: font.medium, fontSize: size.label },
  notice: { paddingVertical: 14, paddingHorizontal: 16 },
  noticeRow: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  noticeIcon: { paddingTop: 1 },
  tag: { alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3 },
  tagText: { fontFamily: font.medium, fontSize: size.caption },
  badge: { minWidth: 22, height: 22, paddingHorizontal: 7, alignItems: 'center', justifyContent: 'center' },
  badgeText: { fontFamily: font.semibold, fontSize: size.caption },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 40, paddingHorizontal: 16, justifyContent: 'center' },
  chipText: { fontSize: size.small },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  segmented: { flexDirection: 'row', padding: 3, minHeight: 50 },
  thumb: { position: 'absolute', top: 3, bottom: 3, left: 3 },
  segment: { flex: 1, minHeight: 44, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6 },
  fieldLabel: { fontFamily: font.medium, fontSize: size.small },
  fieldHelp: { fontFamily: font.regular, fontSize: size.label, lineHeight: size.label * 1.4 },
  field: { flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: size.control, paddingHorizontal: 16, borderWidth: 1.5 },
  fieldMulti: { alignItems: 'flex-start', minHeight: 120, paddingVertical: 12 },
  fieldAmount: { minHeight: 72, justifyContent: 'center' },
  input: { flex: 1, minWidth: 0, fontSize: size.body, minHeight: size.target, paddingVertical: 0 },
  inputMulti: { textAlignVertical: 'top', minHeight: 96 },
  inputAmount: { fontSize: 34, textAlign: 'center', letterSpacing: -0.02 * 34, fontVariant: ['tabular-nums'], minHeight: 64 },
  monoInline: { fontFamily: font.mono, fontSize: size.small },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: size.target, paddingVertical: 8 },
  doneBar: { position: 'absolute', left: 0, right: 0, flexDirection: 'row', alignItems: 'center', minHeight: size.target, paddingHorizontal: 4, borderTopWidth: StyleSheet.hairlineWidth },
  doneKey: { minWidth: size.target, minHeight: size.target, alignItems: 'center', justifyContent: 'center' },
  doneText: { fontFamily: font.semibold, fontSize: size.body },
  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 64, paddingVertical: 8 },
  track: { width: 52, height: 32, padding: 2, justifyContent: 'center', overflow: 'hidden' },
  knob: { width: 28, height: 28, shadowColor: '#000000', shadowOpacity: 0.2, shadowRadius: 2, shadowOffset: { width: 0, height: 1 } },
  linesRow: { flexDirection: 'row', alignItems: 'center', minHeight: 48, gap: 8 },
  linesHeadRow: { minHeight: 28 },
  linesHead: { fontFamily: font.medium, fontSize: size.caption },
  linesAccount: { flex: 1, minWidth: 0 },
  linesFigure: { flexShrink: 0, alignItems: 'flex-end', textAlign: 'right' },
  linesStack: { paddingVertical: 8, gap: 2 },
  linesTotalSide: { fontFamily: font.semibold, fontSize: size.small },
  linesRight: { textAlign: 'right' },
  linesChange: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start' },
  // A ledger's total: a rule above, a double rule below (React Native draws no double border: a second line under it). The only double rule in the app.
  linesTotal: { borderTopWidth: 1, borderBottomWidth: 1, paddingVertical: 4 },
  linesDouble: { height: 1, marginTop: 2 },
  linesTotalText: { fontFamily: font.semibold, fontSize: size.body },
});
