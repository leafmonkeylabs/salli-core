/**
 * The automations inbox (docs/design/mobile.md, "Automations"): messages the
 * Shortcuts action (targets/intents) queued in the app group, read by the
 * rules of the server on screen when Salli runs: on opening, on coming back
 * to the screen, and when iOS gives it background time.
 *
 * Every run goes through the signed-in session's own client: a second one
 * would refresh the sign-in on its own, and a refresh token presented twice
 * ends the sign-in on the server. So the background task only runs the
 * runner the app registered; with none (the app not running), messages wait.
 */
import { ExtensionStorage } from '@bacons/apple-targets';
import { statementsDraft, type SalliClient } from '@leafmonkeylabs/salli-sdk';
import { useQueryClient } from '@tanstack/react-query';
import * as BackgroundTask from 'expo-background-task';
import * as SecureStore from 'expo-secure-store';
import * as TaskManager from 'expo-task-manager';
import { useCallback, useEffect, useSyncExternalStore } from 'react';
import { AppState, Platform } from 'react-native';
import { loadRules } from './automations';
import { keepUnread, queueOf, sortInbox, type QueuedMessage } from './lib/inbox';
import { storeKeyOf } from './lib/servers';
import { useSession } from './session';
import { strings } from './strings';

const GROUP = 'group.money.salli.app';
const QUEUE = 'inbox';
const TASK = 'salli.automations.inbox';
const storage = new ExtensionStorage(GROUP);

/** The run the app registered for the server on screen; none while signed out or not running. */
let runner: (() => Promise<void>) | undefined;

if (Platform.OS === 'ios') {
  TaskManager.defineTask(TASK, async () => {
    try {
      await runner?.();
      return BackgroundTask.BackgroundTaskResult.Success;
    } catch {
      return BackgroundTask.BackgroundTaskResult.Failed;
    }
  });
}

// What waits unread, for the page that lists it: read from the keychain, told of each change.
const listeners = new Set<() => void>();
let unread: { server: string; messages: readonly QueuedMessage[] } = { server: '', messages: [] };
function setUnread(server: string, messages: readonly QueuedMessage[]) {
  unread = { server, messages };
  for (const listener of listeners) listener();
}

async function loadUnread(server: string): Promise<QueuedMessage[]> {
  return queueOf(await SecureStore.getItemAsync(storeKeyOf(server, 'unread')));
}
async function saveUnread(server: string, messages: readonly QueuedMessage[]): Promise<void> {
  await SecureStore.setItemAsync(storeKeyOf(server, 'unread'), JSON.stringify(messages));
  setUnread(server, messages);
}

/** Takes `ids` off the queue, reading it again first: the action may have added to it meanwhile. */
function dequeue(ids: ReadonlySet<string>) {
  if (!ids.size) return;
  const left = queueOf(storage.get(QUEUE)).filter((m) => !ids.has(m.id));
  if (left.length) storage.set(QUEUE, JSON.stringify(left));
  else storage.remove(QUEUE);
}

/**
 * One run: the queue and what waited unread, read by the server's rules.
 * Drafts go to the server by account; a draft that can't be sent (the server
 * out of reach) stays queued for the next run. Returns how many were drafted.
 */
async function run(server: string, client: SalliClient): Promise<number> {
  const rules = await loadRules(server);
  const queued = queueOf(storage.get(QUEUE));
  const waiting = await loadUnread(server);
  if (!queued.length && !waiting.length) return 0;
  // Rules may have changed since: what waited unread is read again.
  const sorted = sortInbox(rules, [...waiting, ...queued]);
  const failed = new Set<string>();
  let drafted = 0;
  for (const [accountId, group] of sorted.drafts) {
    try {
      const result = await client.call(statementsDraft, {
        body: { account_id: accountId, source: strings.automations.source, transactions: group.drafts },
      });
      drafted += result.drafted;
    } catch {
      // Out of reach, or refused: these wait for the next run.
      for (const id of group.ids) failed.add(id);
    }
  }
  // Off the queue: all but the drafts that failed. A queued draft that failed stays
  // queued; one that had waited unread waits on with the unread.
  dequeue(new Set(queued.filter((m) => !failed.has(m.id)).map((m) => m.id)));
  await saveUnread(server, keepUnread(sorted.unread, waiting.filter((m) => failed.has(m.id))));
  return drafted;
}

/** Runs the inbox for the server on screen while signed in: mounted once, beside the screens. */
export function Inbox() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const server = session.status === 'signed-in' ? session.server : '';
  const client = session.status === 'signed-in' ? session.client : undefined;

  useEffect(() => {
    if (!server || !client || Platform.OS !== 'ios') return;
    let busy: Promise<void> | undefined;
    const once = async () => {
      // One run at a time: a second waits for the first rather than send twice.
      busy ??= run(server, client)
        .then((drafted) => {
          if (drafted) void queryClient.invalidateQueries({ queryKey: [server] });
        })
        .catch(() => undefined)
        .finally(() => {
          busy = undefined;
        });
      return busy;
    };
    runner = once;
    void loadUnread(server).then((messages) => setUnread(server, messages));
    void once();
    void BackgroundTask.registerTaskAsync(TASK, { minimumInterval: 15 }).catch(() => undefined);
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') void once();
    });
    return () => {
      subscription.remove();
      if (runner === once) runner = undefined;
    };
  }, [server, client, queryClient]);
  return null;
}

/** What waits unread on this phone for the server on screen, and a way to let one go. */
export function useUnread(): { messages: readonly QueuedMessage[]; discard: (id: string) => Promise<void>; readAgain: () => Promise<void> } {
  const { session } = useSession();
  const server = session.status === 'signed-in' ? session.server : '';
  const subscribe = useCallback((changed: () => void) => {
    listeners.add(changed);
    return () => listeners.delete(changed);
  }, []);
  const now = useSyncExternalStore(subscribe, () => unread);
  const messages = now.server === server ? now.messages : [];
  const discard = useCallback(
    async (id: string) => {
      if (!server) return;
      await saveUnread(server, (await loadUnread(server)).filter((m) => m.id !== id));
    },
    [server],
  );
  const readAgain = useCallback(async () => {
    await runner?.();
  }, []);
  return { messages, discard, readAgain };
}
