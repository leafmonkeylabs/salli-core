import { Redirect } from 'expo-router';

/**
 * The sign-in's redirect, `money.salli.app:/oauth/callback`. The browser
 * sheet reads the code itself; on Android the redirect also arrives as a
 * link, which lands here and goes on to where the app opens.
 */
export default function Callback() {
  return <Redirect href="/" />;
}
