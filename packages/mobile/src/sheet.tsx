/**
 * A sheet from the bottom over a scrim, for a confirmation that shows what
 * Salli will do before it does it (design 12). It slides in 120–200 ms, or
 * fades with Reduce Motion on, and closes on the scrim, the back gesture or
 * its own buttons.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { AccessibilityInfo, Modal, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { size, useTheme } from './theme';

function useReduceMotion(): boolean {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    void AccessibilityInfo.isReduceMotionEnabled().then(setReduce);
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduce);
    return () => subscription.remove();
  }, []);
  return reduce;
}

export function Sheet({ visible, onClose, label, children }: { visible: boolean; onClose: () => void; label: string; children: ReactNode }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  return (
    <Modal visible={visible} transparent animationType={reduceMotion ? 'fade' : 'slide'} onRequestClose={onClose} statusBarTranslucent>
      <View style={styles.frame}>
        <Pressable accessibilityElementsHidden importantForAccessibility="no-hide-descendants" onPress={onClose} style={[StyleSheet.absoluteFill, { backgroundColor: theme.scrim }]} />
        <View
          accessibilityViewIsModal
          accessibilityLabel={label}
          style={[styles.panel, { backgroundColor: theme.chrome, borderTopColor: theme.rule, paddingBottom: insets.bottom + 16 }]}
        >
          {children}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  frame: { flex: 1, justifyContent: 'flex-end' },
  panel: { borderTopWidth: StyleSheet.hairlineWidth, paddingHorizontal: size.gutter, paddingTop: 24, gap: 16 },
});
