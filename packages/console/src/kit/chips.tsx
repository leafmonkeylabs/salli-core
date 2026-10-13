/**
 * Chips, marks and badges (C5): small facts beside a title or in a table.
 * A chip is a fact in a hairline box; an id chip is an id in Geist Mono,
 * its first eight characters as the salli command shows them; an account
 * chip is an account's code and name after a small square for its type; a
 * status badge is a word in capitals. None carries meaning by colour alone:
 * each says it in words too.
 */
import { Link } from '@tanstack/react-router';
import type { ReactNode } from 'react';

export function Chip({ children, mono, quiet, className }: { children: ReactNode; mono?: boolean; quiet?: boolean; className?: string }) {
  return <span className={['chip', mono ? 'chip-mono' : '', quiet ? 'chip-quiet' : '', className ?? ''].filter(Boolean).join(' ')}>{children}</span>;
}

/** An id, as the salli command shows it: its first eight characters, the whole id on hover. */
export function IdChip({ id }: { id: string }) {
  return (
    <span className="chip chip-id" title={id}>
      {id.slice(0, 8)}
    </span>
  );
}

export type AccountType = 'asset' | 'liability' | 'equity' | 'income' | 'expense';

/** An account's type as a small square: asset filled, liability hollow, income sand, spending graphite, equity brass. */
export function TypeMark({ type }: { type: string }) {
  return <span className={`type-mark type-${type}`} aria-hidden="true" />;
}

export interface AccountChipProps {
  code: string;
  name: string;
  type: string;
  /** The type in words, for the title and a screen reader. */
  typeLabel: string;
  /** Where the chip links to (the account's page), if anywhere. */
  to?: string;
}

/** An account: its type's mark, its code and its name; a link to its page when given one. */
export function AccountChip({ code, name, type, typeLabel, to }: AccountChipProps) {
  const inside = (
    <>
      <TypeMark type={type} />
      <span className="chip-code">{code}</span>
      <span className="chip-name">{name}</span>
      <span className="sr-only">, {typeLabel}</span>
    </>
  );
  const title = `${code} ${name}, ${typeLabel}`;
  return to ? (
    <Link to={to} className="chip chip-account" title={title}>
      {inside}
    </Link>
  ) : (
    <span className="chip chip-account" title={title}>
      {inside}
    </span>
  );
}

/** A word in capitals: posted, reversed (struck through), a reversal (ledger green), a warning (with its "!"). */
export function Status({ kind = 'plain', children }: { kind?: 'plain' | 'posted' | 'reversed' | 'reversal' | 'brand' | 'warn'; children: ReactNode }) {
  return (
    <span className={`status status-${kind}`}>
      {kind === 'warn' ? <span aria-hidden="true">!</span> : null}
      {children}
    </span>
  );
}

/** A count beside a place's name: the figure shown, its words for a screen reader. */
export function Count({ n, words }: { n: number; words: string }) {
  return (
    <>
      <span className="count" aria-hidden="true">
        {n}
      </span>
      <span className="sr-only">, {words}</span>
    </>
  );
}
