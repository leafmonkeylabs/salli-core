/**
 * Reading a rule set's document (`salli.tax/1`, docs/taxrules.md) for
 * display: its sources and deadlines, each checked for its shape, since a
 * stored draft may be wrong; a value of the review's diff as text; and a
 * source's address as a link only when it is `https:` (decision 7).
 * Nothing here computes: every figure is shown as the rules write it.
 */
import { toJsonText } from '@leafmonkeylabs/salli-sdk';

export interface Source {
  id: string;
  url: string;
  title: string;
  retrieved: string | null;
}

export interface Deadline {
  key: string;
  label: string;
  date: string;
  source: string | null;
}

const record = (value: unknown): Record<string, unknown> | undefined =>
  typeof value === 'object' && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;
const text = (value: unknown): string => (typeof value === 'string' ? value : '');

function listOf(document: unknown, key: string): Record<string, unknown>[] {
  const found = record(document)?.[key];
  return Array.isArray(found) ? found.map(record).filter((r): r is Record<string, unknown> => r !== undefined) : [];
}

/** The sources a document cites, by id. */
export function sourcesOf(document: unknown): Source[] {
  return listOf(document, 'sources')
    .map((s) => ({ id: text(s.id), url: text(s.url), title: text(s.title) || text(s.id), retrieved: text(s.retrieved) || null }))
    .filter((s) => s.id);
}

/** The document's deadlines, in its order. */
export function deadlinesOf(document: unknown): Deadline[] {
  return listOf(document, 'deadlines')
    .map((d) => ({ key: text(d.key), label: text(d.label) || text(d.key), date: text(d.date), source: text(d.source) || null }))
    .filter((d) => d.key && d.date);
}

/** A diff's value as the rules write it: text as it is, anything else as exact JSON. */
export function shownValue(value: unknown): string {
  if (value === undefined || value === null) return '';
  if (typeof value === 'string') return value;
  return toJsonText(value, 0);
}

/** A source's address, when it may be a link: only https. */
export function httpsUrl(url: string): string | undefined {
  try {
    return new URL(url).protocol === 'https:' ? url : undefined;
  } catch {
    return undefined;
  }
}
