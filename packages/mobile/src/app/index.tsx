import { Redirect } from 'expo-router';
import { Splash } from '../kit';
import { useSession } from '../session';

/** Where the app opens: Home when signed in, otherwise the welcome; the logo meanwhile. */
export default function Index() {
  const { session } = useSession();
  return (
    <>
      <Splash />
      <Redirect href={session.status === 'signed-in' ? '/home' : '/welcome'} />
    </>
  );
}
