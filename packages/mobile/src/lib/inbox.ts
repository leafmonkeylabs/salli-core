/**
 * Messages a Shortcuts automation handed to Salli (targets/intents), waiting
 * on the phone to be read by the person's rules (src/lib/automations.ts).
 * Sorting them is pure: what to draft, on which account; what no rule reads;
 * what nobody watches, dropped at once.
 */
import { read, type AutomationRule, type Draft } from './automations';
import { todayIso } from './display';

/** As the action writes it to the app group, and as it waits when no rule reads it. */
export interface QueuedMessage {
  id: string;
  text: string;
  /** Who sent it, as the automation names them; empty when it didn't say. */
  sender: string;
  /** When it arrived, as an ISO time. */
  at: string;
}

export interface Sorted {
  /** Drafts by the account they are on, with the messages they came from. */
  drafts: Map<string, { ids: string[]; drafts: Draft[] }>;
  /** From a watched sender, but no rule's pattern fits: kept for the person. */
  unread: QueuedMessage[];
  /** From no one a rule watches: dropped, never kept. */
  ignored: string[];
}

/** The day a message arrived, on this phone's calendar: its date when the message names none. */
export function arrivalDay(message: QueuedMessage): string {
  const at = new Date(message.at);
  return Number.isNaN(at.getTime()) ? todayIso() : todayIso(at);
}

export function sortInbox(rules: readonly AutomationRule[], messages: readonly QueuedMessage[]): Sorted {
  const sorted: Sorted = { drafts: new Map(), unread: [], ignored: [] };
  for (const message of messages) {
    // A message without a sender was handed over by hand: every rule is tried.
    const reading = read(rules, message.sender ? { text: message.text, sender: message.sender } : { text: message.text }, arrivalDay(message));
    if (reading.kind === 'draft') {
      const group = sorted.drafts.get(reading.rule.accountId) ?? { ids: [], drafts: [] };
      group.ids.push(message.id);
      group.drafts.push(reading.draft);
      sorted.drafts.set(reading.rule.accountId, group);
    } else if (reading.kind === 'unread') {
      sorted.unread.push(message);
    } else {
      sorted.ignored.push(message.id);
    }
  }
  return sorted;
}

/** The queue as stored (a JSON array), read leniently: anything else is an empty queue. */
export function queueOf(text: string | null | undefined): QueuedMessage[] {
  if (!text) return [];
  try {
    const parsed: unknown = JSON.parse(text);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (m): m is QueuedMessage => typeof m === 'object' && m !== null && typeof m.id === 'string' && typeof m.text === 'string' && typeof m.at === 'string',
    ).map((m) => ({ ...m, sender: typeof m.sender === 'string' ? m.sender : '' }));
  } catch {
    return [];
  }
}

/** What waits unread on this phone: the newest kept, at most `limit`, each once. */
export function keepUnread(now: readonly QueuedMessage[], more: readonly QueuedMessage[], limit = 50): QueuedMessage[] {
  const byId = new Map<string, QueuedMessage>();
  for (const message of [...now, ...more]) byId.set(message.id, message);
  return [...byId.values()].sort((a, b) => b.at.localeCompare(a.at)).slice(0, limit);
}
