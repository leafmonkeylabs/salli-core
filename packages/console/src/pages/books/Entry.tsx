/**
 * An entry (`entries.get`, `entries.provenance`; `salli entries show`): its
 * lines, each amount in its own currency with the rate it was posted at
 * into the base currency; its tags; where it came from; and where it
 * stands: reversed (by which entry), a reversal (of which), or standing,
 * with **Reverse this entry**. Posted entries are never edited: the page
 * says so, and a correction is a reversal (`entries.reverse`), posted after
 * a confirmation that says what Salli will do.
 */
import { entriesGet, entriesList, entriesProvenance, entriesReverse, profileGet, type EntryProvenance, type JournalEntry, type Posting, type Ref } from '@leafmonkeylabs/salli-sdk';
import { Link, useParams } from '@tanstack/react-router';
import { useState } from 'react';
import { useRead, useWrite } from '../../api';
import { displayDate, displayRange } from '../../kit/dates';
import { Button, Confirm } from '../../kit/forms';
import { Grid, Loaded, Page, Panel, Provenance, Section } from '../../kit/layout';
import { Money, visibleAmount } from '../../kit/Money';
import { ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { whereStrings } from '../../where-strings';
import { accountPath, BooksNav, entryLine, entryPath, LEDGER_READS, reversedOf, useAccountBook, type AccountBook } from './ledger';

const x = whereStrings.entry;

/** A rate other than 1: the posting is in another currency than the base. */
function isConverted(p: Posting): boolean {
  return !/^1(\.0*)?$/.test(p.fx_rate.trim());
}

function Lines({ entry, book, base }: { entry: JournalEntry; book: AccountBook; base: string | undefined }) {
  const converted = entry.postings.some(isConverted);
  const tagged = entry.postings.some((p) => Object.keys(p.tags ?? {}).length > 0);
  return (
    <>
      <p className="section-help">{x.linesHelp}</p>
      <Table<Posting>
        caption={x.lines}
        captionHidden
        rows={entry.postings}
        rowKey={(p) => p.id}
        columns={[
          { key: 'account', header: x.account, label: x.account, render: (p) => <Link to={accountPath(p.account_id)}>{book.label(p.account_id)}</Link> },
          { key: 'debit', header: x.debit, label: x.debit, align: 'end', render: (p) => (p.direction > 0 ? <Money amount={p.amount} currency={p.currency} variant="table" withCode /> : null) },
          { key: 'credit', header: x.credit, label: x.credit, align: 'end', render: (p) => (p.direction < 0 ? <Money amount={p.amount} currency={p.currency} variant="table" withCode /> : null) },
          ...(converted
            ? [{ key: 'rate', header: x.rate, label: x.rate, align: 'end' as const, render: (p: Posting) => (isConverted(p) && base ? x.rateText(p.currency, p.fx_rate, base) : '—') }]
            : []),
          ...(tagged
            ? [
                {
                  key: 'tags',
                  header: x.tags,
                  label: x.tags,
                  render: (p: Posting) => {
                    const tags = Object.entries(p.tags ?? {});
                    return tags.length ? (
                      <span className="tags">
                        {tags.map(([axis, slug]) => (
                          <span key={axis} className="tag mono">
                            {axis}={slug}
                          </span>
                        ))}
                      </span>
                    ) : (
                      x.noTags
                    );
                  },
                },
              ]
            : []),
        ]}
      />
    </>
  );
}

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
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const reverse = useWrite<{ id: string }, Ref>('entries.reverse', (api, input) => api.call(entriesReverse, { path: { entry_id: input.id } }), {
    invalidate: LEDGER_READS,
    onSuccess: (ref) => {
      setConfirming(false);
      setDone(ref.id);
    },
  });
  const link = (other: JournalEntry | undefined, id: string) => (
    <Link to={entryPath(id)}>{other ? x.openIt(other.description, displayDate(other.entry_date, locale)) : id}</Link>
  );
  const reversal = entry.reversed_by;
  const original = reversedOf(entry, all);
  const line = entryLine(entry, book);
  return (
    <Panel>
      {reversal ? (
        <p>
          <span className="tag">{whereStrings.entries.reversed}</span> {x.reversedBy}: {link(all.find((o) => o.id === reversal), reversal)}
        </p>
      ) : null}
      {original ? (
        <p>
          <span className="tag">{whereStrings.entries.reversal}</span> {x.reverses}: {link(original, original.id)}
        </p>
      ) : null}
      <p className="section-help">{x.neverEdited}</p>
      {!reversal && !original ? (
        <div className="form-actions">
          <Button variant="secondary" onPress={() => setConfirming(true)}>
            {x.reverse}
          </Button>
        </div>
      ) : null}
      <p role="status" className="quiet-success">
        {done ? (
          <>
            <span aria-hidden="true">✓</span> {x.reversedNow} <Link to={entryPath(done)}>{x.openReversal}</Link>
          </>
        ) : null}
      </p>
      {reverse.isError && !reverse.stepUpPending ? <ProblemView error={reverse.error} compact /> : null}
      <Confirm
        isOpen={confirming}
        onOpenChange={setConfirming}
        title={x.confirmTitle}
        confirmLabel={reverse.isPending ? x.reversing : x.confirm}
        cancelLabel={x.cancel}
        isPending={reverse.isPending}
        onConfirm={() => reverse.mutate({ id: entry.id })}
      >
        <p>{x.confirmBody(entry.description, displayDate(entry.entry_date, locale))}</p>
        {line.amount ? (
          <p>
            <Money amount={line.amount.amount} currency={line.amount.currency} /> · {line.from} → {line.to}
          </p>
        ) : null}
      </Confirm>
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
    <Page title={entry.description} description={x.posted(displayDate(entry.entry_date, locale), x.sources[entry.source] ?? entry.source)}>
      <BooksNav />
      <Grid>
        <Section label={x.lines} wide>
          <Panel>
            <Loaded query={accounts}>{() => (book ? <Lines entry={entry} book={book} base={base} /> : null)}</Loaded>
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
