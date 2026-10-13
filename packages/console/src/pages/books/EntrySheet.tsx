/**
 * An entry opened beside the ledger's list: its lines, what Salli checks
 * of every entry, when and where from, how it stands, reversing it after a
 * confirmation, and its own page.
 */
import { profileGet, type JournalEntry } from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useRead } from '../../api';
import { IdChip, Status } from '../../kit/chips';
import { displayDate } from '../../kit/dates';
import { Icon } from '../../kit/Icon';
import { Sheet } from '../../kit/Sheet';
import { useLocale } from '../../preferences';
import { whereStrings } from '../../where-strings';
import { EntryLines, ReverseEntry } from './entry-parts';
import { entryPath, type AccountBook } from './ledger';

const e = whereStrings.entries;
const x = whereStrings.entry;

export function EntrySheet({ entry, original, book, onClose }: { entry: JournalEntry; original: JournalEntry | undefined; book: AccountBook; onClose: () => void }) {
  const locale = useLocale();
  const base = useRead('profile.get', profileGet).data?.base_currency ?? undefined;
  const status = entry.reversed_by ? (
    <Status kind="reversed">{e.reversed}</Status>
  ) : original ? (
    <Status kind="reversal">{e.reversal}</Status>
  ) : (
    <Status kind="posted">{e.posted}</Status>
  );
  return (
    <Sheet
      kicker={e.sheet}
      badge={<IdChip id={entry.id} />}
      title={entry.description}
      onClose={onClose}
      meta={
        <>
          <span>{displayDate(entry.entry_date, locale)}</span>
          <span aria-hidden="true">·</span>
          <span>{e.sourceShort[entry.source] ?? entry.source}</span>
          <span aria-hidden="true">·</span>
          {status}
        </>
      }
    >
      <h3 className="section-label">{x.linesLabel}</h3>
      <EntryLines entry={entry} book={book} base={base} compact />
      <dl className="details">
        <dt>{e.id}</dt>
        <dd className="mono">{entry.id}</dd>
        <dt>{x.date}</dt>
        <dd>{displayDate(entry.entry_date, locale)}</dd>
        <dt>{x.source}</dt>
        <dd>{x.sources[entry.source] ?? entry.source}</dd>
        <dt>{x.linesLabel}</dt>
        <dd>{x.lineCount(entry.postings.length)}</dd>
        {entry.reversed_by ? (
          <>
            <dt>{x.reversedBy}</dt>
            <dd>
              <Link to={entryPath(entry.reversed_by)}>{entry.reversed_by.slice(0, 8)}</Link>
            </dd>
          </>
        ) : null}
        {original ? (
          <>
            <dt>{x.reverses}</dt>
            <dd>
              <Link to={entryPath(original.id)}>{x.openIt(original.description, displayDate(original.entry_date, locale))}</Link>
            </dd>
          </>
        ) : null}
      </dl>
      {!original ? <ReverseEntry entry={entry} book={book} /> : null}
      <p>
        <Link to={entryPath(entry.id)} className="button button-line">
          {e.openPage}
          <Icon name="right" small />
        </Link>
      </p>
    </Sheet>
  );
}
