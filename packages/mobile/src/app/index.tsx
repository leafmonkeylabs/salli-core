import { Redirect } from 'expo-router';
import { useSession } from '../session';

/** Where the app opens: Home when signed in, otherwise the welcome. */
export default function Index() {
  const { session } = useSession();
  return <Redirect href={session.status === 'signed-in' ? '/home' : '/welcome'} />;
}
