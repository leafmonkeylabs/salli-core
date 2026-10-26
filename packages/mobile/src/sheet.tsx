/**
 * A sheet from the bottom over a scrim, for a confirmation that shows what
 * Salli will do before it does it (design 12). It rises on the sheet's spring
 * while its scrim fades in on its own (src/motion.ts), or both fade with
 * Reduce Motion on. It closes on the scrim, the back gesture, its own buttons
 * or a drag down past 30% of its height (or a quick flick), its grabber (a
 * button named Close, design SheetGrabber) and VoiceOver's escape; VoiceOver
 * starts at its title (`SheetTitle`).
 */
import * as Haptics from 'expo-haptics';
import { createContext, useContext, useEffect, useRef, useState, type ComponentRef, type ReactNode, type RefObject } from 'react';
import { AccessibilityInfo, Dimensions, KeyboardAvoidingView, Modal, Platform, Pressable, StyleSheet, Text, View, type StyleProp, type TextStyle } from 'react-native';
import { Gesture, GestureDetector, GestureHandlerRootView } from 'react-native-gesture-handler';
import Animated, { Easing, ReduceMotion, useAnimatedStyle, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { scheduleOnRN } from 'react-native-worklets';
import { sheet as motion, useReducedMotion } from './motion';
import { strings } from './strings';
import { size, useTheme } from './theme';

const TitleRef = createContext<RefObject<ComponentRef<typeof Text> | null> | null>(null);

/** A sheet's title: a header VoiceOver moves to as the sheet opens. */
export function SheetTitle({ children, style }: { children: ReactNode; style?: StyleProp<TextStyle> }) {
  const ref = useContext(TitleRef);
  return (
    <Text ref={ref} accessibilityRole="header" style={style}>
      {children}
    </Text>
  );
}

export function Sheet({ visible, onClose, label, children }: { visible: boolean; onClose: () => void; label: string; children: ReactNode }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const reduced = useReducedMotion();
  const title = useRef<ComponentRef<typeof Text>>(null);
  // Mounted from opening until its way out has finished.
  const [shown, setShown] = useState(visible);
  const leaving = useRef(false);
  const height = useSharedValue(0);
  // Below the screen until its height is known.
  const y = useSharedValue(Dimensions.get('window').height);
  const fade = useSharedValue(1);
  const scrim = useSharedValue(0);
  const past = useSharedValue(false);

  const gone = () => {
    leaving.current = false;
    height.value = 0;
    y.value = Dimensions.get('window').height;
    setShown(false);
  };
  // Out: down at the drag's own speed (never slower than 180 ms), or a fade.
  const leave = (velocity = 0) => {
    'worklet';
    const timing = { duration: motion.reduced, reduceMotion: ReduceMotion.Never };
    scrim.value = withTiming(0, reduced ? timing : { duration: motion.dismiss });
    if (reduced) {
      fade.value = withTiming(0, timing, (done) => (done ? scheduleOnRN(gone) : undefined));
      return;
    }
    const left = Math.max(height.value - y.value, 0);
    const duration = velocity > 0 ? Math.min(motion.dismiss, (left / velocity) * 1000) : motion.dismiss;
    y.value = withTiming(height.value, { duration, easing: motion.dismissEasing }, (done) => (done ? scheduleOnRN(gone) : undefined));
  };

  useEffect(() => {
    if (visible) {
      // Opened again on its way out: back in from where it is.
      if (leaving.current && height.value) enter();
      leaving.current = false;
      setShown(true);
    } else if (shown && !leaving.current) {
      leaving.current = true;
      leave();
    }
  }, [visible]);

  // In: from below on the spring with the scrim fading on its own, or both fade; then VoiceOver to its title.
  const enter = () => {
    if (reduced) {
      y.value = 0;
      fade.value = withTiming(1, { duration: motion.reduced, reduceMotion: ReduceMotion.Never });
      scrim.value = withTiming(1, { duration: motion.reduced, reduceMotion: ReduceMotion.Never });
    } else {
      fade.value = 1;
      y.value = withSpring(0, motion.present);
      scrim.value = withTiming(1, { duration: motion.scrim, easing: Easing.linear });
    }
    if (title.current) AccessibilityInfo.sendAccessibilityEvent(title.current, 'focus');
  };
  // Its height known the first time, it starts just below the screen's edge.
  const arrive = (measured: number) => {
    const first = height.value === 0;
    height.value = measured;
    if (!first || !visible) return;
    y.value = reduced ? 0 : measured;
    fade.value = reduced ? 0 : 1;
    scrim.value = 0;
    enter();
  };

  const drag = Gesture.Pan()
    .activeOffsetY(12)
    .failOffsetX([-24, 24])
    .onUpdate((e) => {
      y.value = Math.max(e.translationY, 0);
      const over = e.translationY > height.value * motion.threshold;
      if (over !== past.value) {
        past.value = over;
        scheduleOnRN(Haptics.selectionAsync);
      }
    })
    .onEnd((e) => {
      past.value = false;
      if (e.translationY > height.value * motion.threshold || e.velocityY > motion.velocity) {
        scheduleOnRN(dragged);
        leave(Math.max(e.velocityY, 0));
      } else {
        y.value = reduced ? 0 : withSpring(0, motion.present);
      }
    });
  function dragged() {
    leaving.current = true;
    onClose();
  }

  const panel = useAnimatedStyle(() => ({ opacity: fade.value, transform: [{ translateY: y.value }] }));
  const shade = useAnimatedStyle(() => ({ opacity: scrim.value }));

  if (!shown) return null;
  return (
    <Modal visible transparent animationType="none" onRequestClose={onClose} statusBarTranslucent>
      {/* A modal is outside the app's root view: gestures in it need their own. */}
      <GestureHandlerRootView style={styles.frame}>
        {/* It rises with the keyboard, so a field in it stays in view. */}
        <KeyboardAvoidingView style={styles.frame} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <Animated.View style={[StyleSheet.absoluteFill, shade]}>
            <Pressable accessibilityElementsHidden importantForAccessibility="no-hide-descendants" onPress={onClose} style={[StyleSheet.absoluteFill, { backgroundColor: theme.scrim }]} />
          </Animated.View>
          <GestureDetector gesture={drag}>
            <Animated.View
              accessibilityViewIsModal
              accessibilityLabel={label}
              onAccessibilityEscape={onClose}
              onLayout={(e) => arrive(e.nativeEvent.layout.height)}
              style={[styles.panel, { backgroundColor: theme.chrome, borderTopColor: theme.rule, paddingBottom: insets.bottom + 16 }, panel]}
            >
              <Pressable accessibilityRole="button" accessibilityLabel={strings.sheet.close} onPress={onClose} style={styles.grabber}>
                <View style={[styles.grip, { backgroundColor: theme.fieldBorder, borderRadius: theme.control ? 3 : 0 }]} />
              </Pressable>
              <TitleRef.Provider value={title}>{children}</TitleRef.Provider>
            </Animated.View>
          </GestureDetector>
        </KeyboardAvoidingView>
      </GestureHandlerRootView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  frame: { flex: 1, justifyContent: 'flex-end' },
  panel: { borderTopWidth: StyleSheet.hairlineWidth, paddingHorizontal: size.gutter, gap: 16 },
  // 120 × 44 to touch, a 40 × 5 bar to see; the title sits close under it.
  grabber: { alignSelf: 'center', width: 120, height: 44, alignItems: 'center', justifyContent: 'center', marginBottom: -14 },
  grip: { width: 40, height: 5 },
});
