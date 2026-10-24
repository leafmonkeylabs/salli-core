import type { JournalEntry } from '@leafmonkeylabs/salli-sdk';

/** An entry's one amount, where it has one: one debit and one credit line in one currency. Picked, never summed. */
export function amountOf(entry: JournalEntry): { amount: string; currency: string } | undefined {
  const debits = entry.postings.filter((p) => p.direction > 0);
  const credits = entry.postings.filter((p) => p.direction < 0);
  const [debit] = debits;
  const [credit] = credits;
  return debits.length === 1 && credits.length === 1 && debit && credit && debit.currency === credit.currency ? { amount: debit.amount, currency: debit.currency } : undefined;
}

/** How a reversal's description starts, as the app writes it (strings.entry.reversalOf). */
const REVERSAL = /^REVERSAL: /;

/**
 * What the person booked by hand most recently, newest first, each
 * description once: what Add offers to say again. Reversed entries and
 * reversals are left out.
 */
export function recentOf(entries: readonly JournalEntry[], count = 3): { description: string; amount: string | undefined }[] {
  const seen = new Set<string>();
  const out: { description: string; amount: string | undefined }[] = [];
  const newest = [...entries].reverse().sort((a, b) => b.entry_date.localeCompare(a.entry_date));
  for (const entry of newest) {
    const key = entry.description.trim().toLowerCase();
    if (entry.source !== 'manual' || entry.reversed_by || REVERSAL.test(entry.description) || !key || seen.has(key)) continue;
    seen.add(key);
    out.push({ description: entry.description.trim(), amount: amountOf(entry)?.amount });
    if (out.length === count) break;
  }
  return out;
}
