/**
 * What an entry's page and its sheet beside the ledger share: its lines,
 * each amount in its own currency, a debit or a credit; and reversing it,
 * with a reason, after a confirmation that says what Salli will post. A total row is shown
 * only when each side is one line in one currency, so it is that line's
 * own amount, never a sum the console made.
 */
import { entriesReverse, type JournalEntry, type Posting, type Ref } from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useState } from 'react';
import { useWrite } from '../../api';
import { Button, Confirm, TextField } from '../../kit/forms';
import { Icon } from '../../kit/Icon';
import { Money } from '../../kit/Money';
import { ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { Blank } from '../../kit/layout';
import { whereStrings } from '../../where-strings';
import { AccountChipOf, entryLine, entryPath, LEDGER_READS, type AccountBook } from './ledger';

const x = whereStrings.entry;

/** A rate other than 1: the posting is in another currency than the base. */
export function isConverted(p: Posting): boolean {
  return !/^1(\.0*)?$/.test(p.fx_rate.trim());
}

/** The one debit and the one credit, when each side is a single line in one currency. */
function single(entry: JournalEntry): { debit: Posting; credit: Posting } | undefined {
  const debits = entry.postings.filter((p) => p.direction > 0);
  const credits = entry.postings.filter((p) => p.direction < 0);
  const [debit] = debits;
  const [credit] = credits;
  if (debits.length !== 1 || credits.length !== 1 || !debit || !credit) return undefined;
  return debit.currency.toUpperCase() === credit.currency.toUpperCase() ? { debit, credit } : undefined;
}

export function EntryLines({ entry, book, base, compact }: { entry: JournalEntry; book: AccountBook; base: string | undefined; compact?: boolean }) {
  const converted = entry.postings.some(isConverted);
  const tagged = !compact && entry.postings.some((p) => Object.keys(p.tags ?? {}).length > 0);
  const codes = new Set(entry.postings.map((p) => p.currency.toUpperCase()));
  const code = codes.size === 1 ? [...codes][0] : undefined;
  const pair = single(entry);
  return (
    <>
      <Table<Posting>
        caption={x.lines}
        captionHidden
        rows={entry.postings}
        rowKey={(p) => p.id}
        columns={[
          {
            key: 'account',
            header: x.account,
            label: x.account,
            render: (p) => (
              <>
                <AccountChipOf id={p.account_id} book={book} />
                {compact && isConverted(p) && base ? <span className="field-help fx-line">{x.rateText(p.currency, p.fx_rate, base)}</span> : null}
              </>
            ),
          },
          {
            key: 'debit',
            header: code ? x.debitIn(code) : x.debit,
            label: code ? x.debitIn(code) : x.debit,
            align: 'end',
            render: (p) => (p.direction > 0 ? <Money amount={p.amount} currency={p.currency} variant="table" withCode={!code} /> : null),
          },
          {
            key: 'credit',
            header: code ? x.creditIn(code) : x.credit,
            label: code ? x.creditIn(code) : x.credit,
            align: 'end',
            render: (p) => (p.direction < 0 ? <Money amount={p.amount} currency={p.currency} variant="table" withCode={!code} /> : null),
          },
          ...(converted && !compact
            ? [{ key: 'rate', header: x.rate, label: x.rate, align: 'end' as const, render: (p: Posting) => (isConverted(p) && base ? x.rateText(p.currency, p.fx_rate, base) : <Blank>{x.baseCurrency}</Blank>) }]
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
                      <Blank>{x.noTags}</Blank>
                    );
                  },
                },
              ]
            : []),
        ]}
        {...(pair
          ? {
              total: {
                label: x.total,
                cells: {
                  debit: <Money amount={pair.debit.amount} currency={pair.debit.currency} variant="table" withCode={!code} />,
                  credit: <Money amount={pair.credit.amount} currency={pair.credit.currency} variant="table" withCode={!code} />,
                },
              },
            }
          : {})}
      />
      <p className="ok-line">
        <Icon name="check" small />
        <span>{x.balanced}</span>
      </p>
    </>
  );
}

/** **Reverse this entry**, with a reason, after a confirmation; then where the reversal is. */
export function ReverseEntry({ entry, book }: { entry: JournalEntry; book: AccountBook }) {
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState('');
  const [done, setDone] = useState<string | null>(null);
  const reverse = useWrite<{ id: string; reason: string }, Ref>(
    'entries.reverse',
    (api, input) => api.call(entriesReverse, { path: { entry_id: input.id }, body: { reason: input.reason } }),
    {
      invalidate: LEDGER_READS,
      onSuccess: (ref) => {
        setConfirming(false);
        setDone(ref.id);
      },
    },
  );
  const line = entryLine(entry, book);
  return (
    <>
      {!done && !entry.reversed_by ? (
        <div className="form-actions">
          <Button variant="secondary" onPress={() => setConfirming(true)}>
            <Icon name="reverse" />
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
        isDisabled={!reason.trim()}
        onConfirm={() => reverse.mutate({ id: entry.id, reason: reason.trim() })}
      >
        <p>{x.confirmBody(entry.description)}</p>
        {line.amount ? (
          <p>
            <Money amount={line.amount.amount} currency={line.amount.currency} /> · {line.from} → {line.to}
          </p>
        ) : null}
        <TextField label={x.reason} description={x.reasonHelp} value={reason} onChange={setReason} isRequired maxLength={200} />
      </Confirm>
    </>
  );
}
