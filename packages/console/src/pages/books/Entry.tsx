/**
 * An entry (`entries.get`, `entries.provenance`; `salli entries show`): its
 * lines, each amount in its own currency with the rate it was posted at
 * into the base currency; its tags; where it came from; and where it
 * stands: reversed (by which entry), a reversal (of which), or standing,
 * with **Reverse this entry**. Posted entries are never edited: the page
 * says so, and a correction is a reversal (`entries.reverse`), posted after
 * a confirmation that says what Salli will do.
 */
import { entriesGet, entriesList, entriesProvenance, profileGet, type EntryProvenance, type JournalEntry } from '@leafmonkeylabs/salli-sdk';
import { Link, useParams } from '@tanstack/react-router';
import { useRead } from '../../api';
import { Chip, IdChip, Status } from '../../kit/chips';
import { displayDate, displayRange } from '../../kit/dates';
import { Grid, Loaded, Page, Panel, Provenance, Section } from '../../kit/layout';
import { visibleAmount } from '../../kit/Money';
import { ProblemView } from '../../kit/Problem';
import { useLocale } from '../../preferences';
import { whereStrings } from '../../where-strings';
import { EntryLines, ReverseEntry } from './entry-parts';
import { BooksActions, BooksNav, entryPath, reversedOf, useAccountBook, type AccountBook } from './ledger';

const x = whereStrings.entry;
const e = whereStrings.entries;

function Origin({ provenance }: { provenance: EntryProvenance }) {
  const locale = useLocale();
  const s = provenance.statement;
  const lines: string[] = [];
  if (s) {
    lines.push(x.statement(s.raw_description, visibleAmount(s.raw_amount, s.currency, 'prose', { locale }), displayDate(s.raw_date, locale)));
    if (s.statement?.bank && s.statement.period_start && s.statement.period_end) {
      lines.push(x.statementFile(s.statement.bank, displayRange(s.statement.period_start, s.statement.period_end, locale)));
    }
  }
  if (provenance.receipt) lines.push(x.receipt(provenance.receipt.title, provenance.receipt.mime_type));
  if (provenance.possible_subscriptions.length) lines.push(x.subscription(provenance.possible_subscriptions.map((p) => p.name).join(', ')));
  if (provenance.external_ref && !s && !provenance.receipt) lines.push(x.externalRef(provenance.external_ref));
  return (
    <Panel>
      <p>{x.sources[provenance.source] ?? provenance.source}</p>
      {lines.length ? lines.map((line, i) => <Provenance key={i}>{line}</Provenance>) : <Provenance>{x.nothingMore}</Provenance>}
    </Panel>
  );
}

function Standing({ entry, all, book }: { entry: JournalEntry; all: readonly JournalEntry[]; book: AccountBook }) {
  const locale = useLocale();
  const link = (other: JournalEntry | undefined, id: string) => (
    <Link to={entryPath(id)}>{other ? x.openIt(other.description, displayDate(other.entry_date, locale)) : id}</Link>
  );
  const reversal = entry.reversed_by;
  const original = reversedOf(entry, all);
  return (
    <Panel>
      {reversal ? (
        <p>
          <Status kind="reversed">{e.reversed}</Status> {x.reversedBy}: {link(all.find((o) => o.id === reversal), reversal)}
        </p>
      ) : null}
      {original ? (
        <p>
          <Status kind="reversal">{e.reversal}</Status> {x.reverses}: {link(original, original.id)}
        </p>
      ) : null}
      <p className="section-help">{x.neverEdited}</p>
      {!original ? <ReverseEntry entry={entry} book={book} /> : null}
    </Panel>
  );
}

function EntryPage({ entry }: { entry: JournalEntry }) {
  const locale = useLocale();
  const { query: accounts, book } = useAccountBook();
  const provenance = useRead('entries.provenance', entriesProvenance, { path: { entry_id: entry.id } });
  const all = useRead('entries.list', entriesList);
  const base = useRead('profile.get', profileGet).data?.base_currency ?? undefined;
  return (
    <Page
      title={entry.description}
      description={x.posted(displayDate(entry.entry_date, locale), x.sources[entry.source] ?? entry.source)}
      facts={
        <>
          <IdChip id={entry.id} />
          <Chip>{displayDate(entry.entry_date, locale)}</Chip>
          <Chip>{e.sourceShort[entry.source] ?? entry.source}</Chip>
          <Chip>{x.lineCount(entry.postings.length)}</Chip>
        </>
      }
      actions={<BooksActions />}
    >
      <BooksNav />
      <Grid>
        <Section label={x.lines} wide>
          <Panel>
            <p className="section-help">{x.linesHelp}</p>
            <Loaded query={accounts}>{() => (book ? <EntryLines entry={entry} book={book} base={base} /> : null)}</Loaded>
          </Panel>
        </Section>
        <Section label={x.standing}>
          <Loaded query={all}>{(entries) => (book ? <Standing entry={entry} all={entries} book={book} /> : null)}</Loaded>
        </Section>
        <Section label={x.provenance} wide>
          <Loaded query={provenance}>{(p) => <Origin provenance={p} />}</Loaded>
        </Section>
      </Grid>
      <Provenance>
        <span className="mono">{x.id(entry.id)}</span>
      </Provenance>
    </Page>
  );
}

export function Entry() {
  const params = useParams({ strict: false }) as { entry?: string };
  const id = params.entry ?? '';
  const query = useRead('entries.get', entriesGet, { path: { entry_id: id } });
  if (query.isError) {
    return (
      <Page title={x.notFound}>
        <BooksNav />
        <ProblemView error={query.error} onRetry={() => void query.refetch()} />
      </Page>
    );
  }
  return <Loaded query={query} lines={8}>{(entry) => <EntryPage entry={entry} />}</Loaded>;
}

export default Entry;
