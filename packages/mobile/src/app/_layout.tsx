import 'react-native-url-polyfill/auto';
import { Geist_400Regular, Geist_500Medium, Geist_600SemiBold } from '@expo-google-fonts/geist';
import { GeistMono_400Regular } from '@expo-google-fonts/geist-mono';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { ApiProvider } from '../api';
import { PhoneProvider } from '../phone';
import { SessionProvider, useSession } from '../session';
import { useTheme } from '../theme';

void SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [fontsLoaded] = useFonts({ Geist_400Regular, Geist_500Medium, Geist_600SemiBold, GeistMono_400Regular });
  return (
    <SafeAreaProvider>
      <SessionProvider>
        <PhoneProvider>
          <ApiProvider>{fontsLoaded ? <Navigator /> : null}</ApiProvider>
        </PhoneProvider>
      </SessionProvider>
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
        </Stack.Protected>
        {/* Signed out, the way in; signed in, the way to add another server. */}
        <Stack.Screen name="welcome" />
        <Stack.Screen name="connect" />
      </Stack>
    </>
  );
}
