/**
 * Leaving a form with something typed in it (design DiscardDraft): Cancel,
 * Back, a swipe down or back all ask "Discard this draft?" first, as an
 * action sheet. `done()` lets the form go without asking, once what it held
 * is saved.
 */
import { useNavigation, usePreventRemove } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActionSheetIOS, Alert, Platform } from 'react-native';
import { strings } from './strings';

const t = strings.draft;

export function useKeepDraft(dirty: boolean): { done: () => void } {
  const navigation = useNavigation();
  const saved = useRef(false);
  // The way out once it is allowed: the guard comes off first, then the action goes again.
  const [leaving, setLeaving] = useState<Parameters<typeof navigation.dispatch>[0] | null>(null);
  useEffect(() => {
    if (leaving) navigation.dispatch(leaving);
  }, [leaving]);
  usePreventRemove(dirty && !leaving, ({ data }) => {
    const go = () => setLeaving(data.action);
    if (saved.current) return go();
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions({ title: t.title, options: [t.discard, t.keep], destructiveButtonIndex: 0, cancelButtonIndex: 1 }, (i) => (i === 0 ? go() : undefined));
    } else {
      Alert.alert(t.title, undefined, [
        { text: t.keep, style: 'cancel' },
        { text: t.discard, style: 'destructive', onPress: go },
      ]);
    }
  });
  return { done: () => void (saved.current = true) };
}
