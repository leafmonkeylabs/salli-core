/**
 * What a set of figures rests on, always in view (docs/design/console.md,
 * sections 4 and 10): the placeholders, how fresh the ledger is, and whether
 * tax was computed. Never folded away: a figure resting on a placeholder
 * says so beside it.
 */
import { Panel } from '../../kit/layout';
import { displayDate } from '../../kit/dates';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';
import { placeholderText } from './format';

const b = labStrings.basis;

export interface BasisProps {
  placeholders: readonly string[];
  isStale: boolean;
  dataAsOf: string | null;
  /** A scenario's tax, when any change is tagged with a tax role. */
  tax?: { status: 'computed' | 'not_computed' | 'none'; reason: string | null } | undefined;
  notes?: readonly string[];
  /** As of, in a currency, over a horizon: said first. */
  asOf?: string;
}

export function Basis({ placeholders, isStale, dataAsOf, tax, notes = [], asOf }: BasisProps) {
  const locale = useLocale();
  return (
    <Panel className="basis">
      {asOf ? <p className="provenance">{asOf}</p> : null}
      {isStale ? (
        <p className="warn-line">
          <span className="warn-mark" aria-hidden="true">
            !
          </span>{' '}
          {dataAsOf ? b.stale(displayDate(dataAsOf, locale)) : b.noEntries}
        </p>
      ) : dataAsOf ? (
        <p className="provenance">{b.fresh(displayDate(dataAsOf, locale))}</p>
      ) : null}
      {tax && tax.status === 'not_computed' ? (
        <p className="warn-line">
          <span className="warn-mark" aria-hidden="true">
            !
          </span>{' '}
          {b.taxNotComputed(tax.reason ?? '')}
        </p>
      ) : null}
      {tax && tax.status === 'computed' ? <p className="provenance">{b.taxComputed}</p> : null}
      {placeholders.length ? (
        <>
          <p className="basis-placeholders">{b.placeholders}</p>
          <ul className="basis-list">
            {placeholders.map((key) => (
              <li key={key}>{placeholderText(key)}</li>
            ))}
          </ul>
        </>
      ) : null}
      {notes.map((note, i) => (
        <p key={i} className="provenance">
          {note}
        </p>
      ))}
    </Panel>
  );
}
