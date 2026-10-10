/**
 * Turning what someone typed into the id the API wants.
 *
 * Lists show the first eight characters of an id, so every command that
 * takes an id also takes any unique prefix of one. Accounts can also be
 * named by code or name.
 */
import { NotFoundError, UsageError } from '../errors';

interface WithId {
  id?: unknown;
}

function idOf(item: WithId): string {
  return typeof item.id === 'string' ? item.id : '';
}

/** The item whose id is `query`, or the only one whose id starts with it. */
export function resolveById<T extends WithId>(items: readonly T[], query: string, label: string): T {
  const wanted = query.trim();
  const exact = items.find((item) => idOf(item) === wanted);
  if (exact) return exact;
  const matches = wanted ? items.filter((item) => idOf(item).startsWith(wanted)) : [];
  if (matches.length === 1 && matches[0]) return matches[0];
  if (matches.length === 0) throw new NotFoundError(`No ${label} with id "${query}".`);
  throw new UsageError(
    `"${query}" matches ${matches.length} ${label}s.`,
    `Use more of the id: ${matches
      .slice(0, 4)
      .map((m) => idOf(m).slice(0, wanted.length + 4))
      .join(', ')}${matches.length > 4 ? ', …' : ''}`,
  );
}

export interface AccountLike {
  id: string;
  code: string;
  name: string;
  type?: string;
  is_active?: boolean;
}

/**
 * The account `query` names: its id (or a unique prefix), its code, or its
 * name (case-insensitive, or a unique prefix of it).
 */
export function resolveAccount<T extends AccountLike>(accounts: readonly T[], query: string): T {
  const q = query.trim();
  const lower = q.toLowerCase();
  const direct =
    accounts.find((a) => a.id === q) ??
    accounts.find((a) => a.code === q) ??
    accounts.find((a) => a.name.toLowerCase() === lower);
  if (direct) return direct;

  const byId = q.length >= 4 ? accounts.filter((a) => a.id.startsWith(q)) : [];
  if (byId.length === 1 && byId[0]) return byId[0];

  const byName = accounts.filter((a) => a.name.toLowerCase().startsWith(lower));
  const active = byName.filter((a) => a.is_active !== false);
  const candidates = active.length > 0 ? active : byName;
  if (candidates.length === 1 && candidates[0]) return candidates[0];
  if (candidates.length > 1) {
    throw new UsageError(
      `"${query}" matches ${candidates.length} accounts.`,
      `Use a code: ${candidates
        .slice(0, 5)
        .map((a) => `${a.code} (${a.name})`)
        .join(', ')}${candidates.length > 5 ? ', …' : ''}`,
    );
  }
  throw new NotFoundError(`No account matches "${query}".`, 'See `salli accounts list` for codes and names.');
}

/** "1000 Cash" — how an account is named in messages and tables. */
export function accountLabel(account: Pick<AccountLike, 'code' | 'name'> | undefined, fallbackId?: string): string {
  if (!account) return fallbackId ? fallbackId.slice(0, 8) : '—';
  return `${account.code} ${account.name}`;
}
