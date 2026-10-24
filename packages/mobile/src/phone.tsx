/**
 * This phone (docs/design/mobile.md, "Discretion"): whether Salli opens with
 * Face ID or the phone's own unlock, and whether its figures may show in the
 * app switcher. Kept on the phone, never sent to a server; nothing is locked
 * or covered while signed out, when there is nothing of the person's to see.
 */
import * as LocalAuthentication from 'expo-local-authentication';
import * as SecureStore from 'expo-secure-store';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AppState, Platform, StyleSheet, Text, View } from 'react-native';
import { Body, Button, Logo } from './kit';
import { lockDue } from './lib/servers';
import { useSession } from './session';
import { strings } from './strings';
import { font, size, useTheme } from './theme';

const t = strings.phone;
const KEY = 'salli.phone';

export interface PhoneSettings {
  /** Open with Face ID, Touch ID or the passcode. */
  lock: boolean;
  /** Let the app switcher show the screen rather than a cover. */
  showAmounts: boolean;
}

const DEFAULTS: PhoneSettings = { lock: false, showAmounts: false };

/** What this phone unlocks with, as the person knows it; undefined when no passcode is set. */
export type UnlockWith = 'face' | 'fingerprint' | 'biometric' | 'passcode';

interface PhoneApi {
  settings: PhoneSettings;
  unlockWith: UnlockWith | undefined;
  /** Turning the lock on asks to unlock first, so no one locks themselves out. */
  setLock(on: boolean): Promise<void>;
  setShowAmounts(on: boolean): void;
}

const PhoneContext = createContext<PhoneApi | null>(null);

export function usePhone(): PhoneApi {
  const api = useContext(PhoneContext);
  if (!api) throw new Error('usePhone outside PhoneProvider');
  return api;
}

async function unlockWithOf(): Promise<UnlockWith | undefined> {
  const level = await LocalAuthentication.getEnrolledLevelAsync();
  if (level === LocalAuthentication.SecurityLevel.NONE) return undefined;
  if (level === LocalAuthentication.SecurityLevel.SECRET) return 'passcode';
  if (Platform.OS !== 'ios') return 'biometric';
  const kinds = await LocalAuthentication.supportedAuthenticationTypesAsync();
  return kinds.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION) ? 'face' : 'fingerprint';
}

async function unlocked(): Promise<boolean> {
  const result = await LocalAuthentication.authenticateAsync({ promptMessage: t.prompt, cancelLabel: t.cancel });
  return result.success;
}

export function PhoneProvider({ children }: { children: ReactNode }) {
  const theme = useTheme();
  const { session } = useSession();
  const [settings, setSettings] = useState<PhoneSettings | undefined>(undefined);
  const [unlockWith, setUnlockWith] = useState<UnlockWith | undefined>(undefined);
  const [locked, setLocked] = useState(true);
  const [away, setAway] = useState(AppState.currentState !== 'active');
  const leftAt = useRef<number | undefined>(undefined);
  const lockOn = useRef(false);
  const asking = useRef(false);

  useEffect(() => {
    void Promise.all([SecureStore.getItemAsync(KEY), unlockWithOf()]).then(([text, how]) => {
      let found = DEFAULTS;
      try {
        found = text ? { ...DEFAULTS, ...(JSON.parse(text) as Partial<PhoneSettings>) } : DEFAULTS;
      } catch {
        // Unreadable settings are the defaults.
      }
      // A lock with nothing to unlock with would keep the person out.
      if (!how) found = { ...found, lock: false };
      lockOn.current = found.lock;
      setUnlockWith(how);
      setLocked(found.lock);
      setSettings(found);
    });
  }, []);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => {
      setAway(state !== 'active');
      if (state === 'background') leftAt.current = Date.now();
      // What the phone unlocks with may have changed in its Settings meanwhile.
      if (state === 'active') void unlockWithOf().then(setUnlockWith);
      if (state === 'active' && leftAt.current !== undefined) {
        if (lockDue(lockOn.current, Date.now() - leftAt.current)) setLocked(true);
        leftAt.current = undefined;
      }
    });
    return () => subscription.remove();
  }, []);

  const store = useCallback((next: PhoneSettings) => {
    lockOn.current = next.lock;
    setSettings(next);
    void SecureStore.setItemAsync(KEY, JSON.stringify(next));
  }, []);

  const unlock = useCallback(async () => {
    if (asking.current) return;
    asking.current = true;
    if (await unlocked()) setLocked(false);
    asking.current = false;
  }, []);

  const signedIn = session.status === 'signed-in';
  const showLock = signedIn && !!settings?.lock && locked;
  // Asked once as the lock comes up, then by the button: a cancel isn't asked again.
  const asked = useRef(false);
  useEffect(() => {
    if (!showLock) {
      asked.current = false;
      return;
    }
    if (away || asked.current) return;
    asked.current = true;
    void unlock();
  }, [showLock, away, unlock]);

  const setLock = useCallback(
    async (on: boolean) => {
      if (!settings) return;
      if (on && !(await unlocked())) return;
      setLocked(false);
      store({ ...settings, lock: on });
    },
    [settings, store],
  );
  const setShowAmounts = useCallback((on: boolean) => settings && store({ ...settings, showAmounts: on }), [settings, store]);

  const value = useMemo(() => ({ settings: settings ?? DEFAULTS, unlockWith, setLock, setShowAmounts }), [settings, unlockWith, setLock, setShowAmounts]);
  // Until the settings are read, cover what the person may have asked to hide.
  const cover = signedIn && (!settings || (away && !settings.showAmounts));
  const hidden = showLock || cover;
  const how = t.how[unlockWith ?? 'passcode'];

  return (
    <PhoneContext.Provider value={value}>
      <View style={{ flex: 1 }} accessibilityElementsHidden={hidden} importantForAccessibility={hidden ? 'no-hide-descendants' : 'auto'}>
        {children}
      </View>
      {showLock ? (
        <View style={[StyleSheet.absoluteFill, styles.screen, { backgroundColor: theme.chrome }]}>
          <Logo height={40} />
          <View style={{ gap: 8, alignItems: 'center' }}>
            <Text accessibilityRole="header" style={[styles.title, { color: theme.text }]}>
              {t.locked}
            </Text>
            <Body muted>{t.lockedBody}</Body>
          </View>
          <View style={{ alignSelf: 'stretch' }}>
            <Button label={t.unlock(how)} onPress={() => void unlock()} />
          </View>
        </View>
      ) : cover ? (
        <View style={[StyleSheet.absoluteFill, styles.screen, { backgroundColor: theme.chrome }]}>
          <Logo height={40} />
        </View>
      ) : null}
    </PhoneContext.Provider>
  );
}

const styles = StyleSheet.create({
  screen: { alignItems: 'center', justifyContent: 'center', gap: 32, padding: size.gutter },
  title: { fontFamily: font.medium, fontSize: size.heading },
});
