import 'react-native-url-polyfill/auto';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { YourAIProvider } from '../ai/store';
import { AppearanceProvider } from '../appearance';
import { ApiProvider } from '../api';
import { Glance } from '../glance';
import { Inbox } from '../inbox';
import { PhoneProvider } from '../phone';
import { SessionProvider, useSession } from '../session';
import { useTheme } from '../theme';

void SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AppearanceProvider>
        <SessionProvider>
          <PhoneProvider>
            <ApiProvider>
              <YourAIProvider>
                <Navigator />
              </YourAIProvider>
            </ApiProvider>
          </PhoneProvider>
        </SessionProvider>
      </AppearanceProvider>
    </SafeAreaProvider>
  );
}

function Navigator() {
  const { session } = useSession();
  const theme = useTheme();
  const signedIn = session.status === 'signed-in';

  useEffect(() => {
    if (session.status !== 'loading') void SplashScreen.hideAsync();
  }, [session.status]);

  if (session.status === 'loading') return null;
  return (
    <>
      <StatusBar style={theme.dark ? 'light' : 'dark'} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.work } }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="oauth/callback" />
        <Stack.Protected guard={signedIn}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="account/[id]" />
          <Stack.Screen name="entry/[id]" />
          <Stack.Screen name="add" options={{ presentation: 'modal' }} />
          <Stack.Screen name="servers" options={{ presentation: 'modal' }} />
          <Stack.Screen name="import" options={{ presentation: 'modal' }} />
          <Stack.Screen name="review/[id]" />
          <Stack.Screen name="entries" />
          <Stack.Screen name="sign-ins" />
          <Stack.Screen name="automations" />
          <Stack.Screen name="automation/[id]" />
          <Stack.Screen name="ai" />
          <Stack.Screen name="agent" />
          <Stack.Screen name="appearance" />
          <Stack.Screen name="attention" />
          <Stack.Screen name="filing" />
          <Stack.Screen name="first-run" options={{ gestureEnabled: false }} />
        </Stack.Protected>
        {/* Signed out, the way in; signed in, the way to add another server. */}
        <Stack.Screen name="welcome" />
        <Stack.Screen name="connect" />
      </Stack>
      <Glance />
      <Inbox />
    </>
  );
}
