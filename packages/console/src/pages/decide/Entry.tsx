/**
 * One decision as recorded (`decisions.get`; docs/decisions.md): what was
 * chosen and why, in the person's own words; its hash and whether it still
 * matches; the options' figures and the principles as they stood; what it
 * rested on; its reviews and notes. From its review date on, the review:
 * what the chosen option projected beside what happened, and the person's
 * reflection, added after a confirmation. A note is added the same way.
 * Nothing in the entry ever changes; this page can't change it either.
 */
import {
  decisionsGet,
  decisionsMarkdown,
  decisionsNotesAdd,
  decisionsReview,
  decisionsReviewsDue,
  toJsonText,
  type Decision,
  type DecisionNote,
  type DecisionReview,
  type ReviewComparison,
} from '@leafmonkeylabs/salli-sdk';
import { Link, useParams } from '@tanstack/react-router';
import { useState, type FormEvent } from 'react';
import { useApi, useRead, useWrite } from '../../api';
import { displayDate, displayMonth, displayMoment } from '../../kit/dates';
import { saveText, textOf } from '../../kit/download';
import { Button, Confirm, TextAreaField } from '../../kit/forms';
import { Empty, Loaded, Page, Panel, Provenance, Row, Rows, Section } from '../../kit/layout';
import { Money } from '../../kit/Money';
import { ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { ThinkItThrough } from '../../kit/ThinkItThrough';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';
import { strings } from '../../strings';
import { Basis } from './Basis';
import { Checks } from './Checks';
import { monthsOfSpending, rateText } from './format';
import { LabNav } from './LabNav';

const e = labStrings.entry;
const j = labStrings.journal;
const INVALIDATE = ['decisions.get', 'decisions.list', 'decisions.reviews.due', 'decisions.export'];

/** A recorded figure as it was kept: an amount, months, a rate, a count, yes or no. */
function FigureValue({ value, name, currency }: { value: unknown; name: string; currency: string }) {
  const locale = useLocale();
  if (value === null || value === undefined) return <>—</>;
  if (typeof value === 'boolean') return <>{value ? e.yes : e.no}</>;
  if (typeof value === 'number') return <>{String(value)}</>;
  if (typeof value !== 'string') return <>—</>;
  if (name.includes('rate')) return <>{rateText(value, locale)}</>;
  if (name.includes('months')) return <>{monthsOfSpending(value, locale)}</>;
  return <Money amount={value} currency={currency} variant="table" />;
}

export function ProjectedAgainstActual({ comparison }: { comparison: ReviewComparison }) {
  const locale = useLocale();
  const code = comparison.currency.toUpperCase();
  type R = { key: string; label: string; projected: string | null; actual: string | null; difference: string | null };
  const rows: R[] = comparison.figures.map((f) => ({ key: f.figure, label: e.figureNames[f.figure] ?? f.figure, projected: f.projected, actual: f.actual, difference: f.difference }));
  const s = comparison.spending;
  const first = s.months[0];
  const last = s.months[s.months.length - 1];
  if (first && last && s.projected && s.actual) {
    rows.push({ key: 'spending', label: e.spending(displayMonth(first, locale), displayMonth(last, locale)), projected: s.projected, actual: s.actual, difference: s.difference });
  }
  const title = e.projectedFor(comparison.option, displayDate(comparison.at, locale));
  return (
    <div className="stack-tight">
      <p className="subhead">{title}</p>
      <Table<R>
        caption={title}
        captionHidden
        rows={rows}
        rowKey={(r) => r.key}
        columns={[
          { key: 'figure', header: labStrings.figureColumn, label: labStrings.figureColumn, render: (r) => r.label },
          { key: 'projected', header: `${e.projected} (${code})`, label: e.projected, align: 'end', render: (r) => <Money amount={r.projected} currency={code} variant="table" /> },
          { key: 'actual', header: `${e.actual} (${code})`, label: e.actual, align: 'end', render: (r) => <Money amount={r.actual} currency={code} variant="table" /> },
          { key: 'difference', header: `${e.difference} (${code})`, label: e.difference, align: 'end', render: (r) => <Money amount={r.difference} currency={code} variant="table" signed /> },
        ]}
      />
      <Provenance>{e.inCurrency(code)}</Provenance>
      {comparison.others.length ? (
        <>
          <p className="subhead">{e.others}</p>
          <p className="section-help">{e.othersHelp}</p>
          <Table
            caption={e.others}
            captionHidden
            rows={comparison.others}
            rowKey={(o) => o.option}
            columns={[
              { key: 'option', header: labStrings.compare.optionColumn, label: labStrings.compare.optionColumn, render: (o) => o.option },
              { key: 'cash', header: `${e.figureNames.cash} (${code})`, label: e.figureNames.cash ?? '', align: 'end', render: (o) => <Money amount={o.cash} currency={code} variant="table" /> },
              { key: 'owed', header: `${e.figureNames.owed} (${code})`, label: e.figureNames.owed ?? '', align: 'end', render: (o) => <Money amount={o.owed} currency={code} variant="table" /> },
              { key: 'nw', header: `${e.figureNames.net_worth} (${code})`, label: e.figureNames.net_worth ?? '', align: 'end', render: (o) => <Money amount={o.net_worth} currency={code} variant="table" /> },
            ]}
          />
        </>
      ) : null}
      {comparison.is_stale && comparison.data_as_of ? <p className="warn-line">{labStrings.basis.stale(displayDate(comparison.data_as_of, locale))}</p> : null}
      {comparison.notes.map((note, i) => (
        <Provenance key={i}>{note}</Provenance>
      ))}
    </div>
  );
}

/** Words added to the entry, asked first: a note, or a review's reflection. */
function AddWords({
  label,
  help,
  submit,
  title,
  body,
  needed,
  done,
  write,
}: {
  label: string;
  help: string;
  submit: string;
  title: string;
  body: string;
  needed: string;
  done: string;
  write: ReturnType<typeof useWrite<{ text: string }, unknown>>;
}) {
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [said, setSaid] = useState(false);
  const onSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setSaid(false);
    if (!text.trim()) {
      setError(needed);
      return;
    }
    setError('');
    setConfirming(true);
  };
  return (
    <form className="form" onSubmit={onSubmit} noValidate>
      <TextAreaField label={label} description={help} value={text} onChange={setText} error={error} isRequired />
      {error ? (
        <p className="sr-only" role="alert">
          {error}
        </p>
      ) : null}
      {write.isError && !write.stepUpPending ? <ProblemView error={write.error} compact /> : null}
      <div className="form-actions">
        <Button type="submit">{submit}</Button>
        <p role="status" className="quiet-success">
          {said ? (
            <>
              <span aria-hidden="true">✓</span> {done}
            </>
          ) : null}
        </p>
      </div>
      <Confirm
        isOpen={confirming}
        onOpenChange={setConfirming}
        title={title}
        confirmLabel={submit}
        cancelLabel={strings.settings.cancel}
        isPending={write.isPending}
        onConfirm={() =>
          write.mutate(
            { text: text.trim() },
            {
              onSuccess: () => {
                setConfirming(false);
                setText('');
                setSaid(true);
              },
            },
          )
        }
      >
        <p className="own-words">{text.trim()}</p>
        <p>{body}</p>
      </Confirm>
    </form>
  );
}

function Review({ decision }: { decision: Decision }) {
  const due = useRead('decisions.reviews.due', decisionsReviewsDue);
  const write = useWrite<{ text: string }, unknown>(
    'decisions.review',
    (api, input) => api.call(decisionsReview, { path: { decision_id: decision.id }, body: { reflection: input.text } }) as Promise<DecisionReview>,
    { invalidate: INVALIDATE },
  );
  const comparison = due.data?.reviews.find((r) => r.id === decision.id)?.comparison;
  if (decision.status !== 'review_due') return null;
  return (
    <Section label={e.review} full>
      <Panel>
        <p className="section-help">{e.reviewHelp}</p>
        <Loaded query={due}>{() => (comparison ? <ProjectedAgainstActual comparison={comparison} /> : null)}</Loaded>
        <AddWords
          label={e.reflection}
          help={e.reflectionHelp}
          submit={e.submitReview}
          title={e.reviewTitle}
          body={e.reviewBody}
          needed={e.needReflection}
          done={e.reviewed}
          write={write}
        />
      </Panel>
    </Section>
  );
}

function Notes({ decision }: { decision: Decision }) {
  const locale = useLocale();
  const write = useWrite<{ text: string }, unknown>(
    'decisions.notes.add',
    (api, input) => api.call(decisionsNotesAdd, { path: { decision_id: decision.id }, body: { text: input.text } }) as Promise<DecisionNote>,
    { invalidate: INVALIDATE },
  );
  return (
    <Section label={e.notes} wide>
      <Panel>
        {decision.notes.length ? (
          <ul className="list">
            {decision.notes.map((n) => (
              <li key={n.note.id}>
                <p className="provenance">{e.noteBy(displayMoment(n.note.at, locale), n.note.author === 'agent' ? (n.note.agent ?? e.anAgent) : e.you)}</p>
                <p className="own-words">{n.note.text}</p>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>{e.noNotes}</Empty>
        )}
        <h3 className="panel-title">{e.addNote}</h3>
        <AddWords label={e.note} help={e.noteHelp} submit={e.submitNote} title={e.noteTitle} body={e.noteBody} needed={e.needNote} done={e.noted} write={write} />
      </Panel>
    </Section>
  );
}

function Download({ decision }: { decision: Decision }) {
  const api = useApi();
  const [error, setError] = useState<unknown>(null);
  const name = `salli-decision-${decision.id.slice(0, 8)}`;
  const save = async (format: 'json' | 'markdown'): Promise<void> => {
    setError(null);
    try {
      if (format === 'json') saveText(`${name}.json`, `${toJsonText(await api.call(decisionsGet, { path: { decision_id: decision.id } }))}\n`, 'application/json');
      else saveText(`${name}.md`, textOf(await api.call(decisionsMarkdown, { path: { decision_id: decision.id }, parseAs: 'text' })), 'text/markdown');
    } catch (failure) {
      setError(failure);
    }
  };
  return (
    <Section label={e.download}>
      <Panel>
        <div className="form-actions">
          <button type="button" className="button button-secondary" onClick={() => void save('json')}>
            {e.downloadJson}
          </button>
          <button type="button" className="button button-secondary" onClick={() => void save('markdown')}>
            {e.downloadMarkdown}
          </button>
        </div>
        {error ? <ProblemView error={error} compact /> : null}
      </Panel>
    </Section>
  );
}

function EntryView({ decision }: { decision: Decision }) {
  const locale = useLocale();
  const entry = decision.entry;
  const code = entry.currency.toUpperCase();
  const via = entry.recorded_via.channel === 'mcp' ? ` ${e.viaAgent(entry.recorded_via.client ?? e.anAgent)}` : '';
  type K = { name: string; label: string };
  const keys: K[] = Object.entries(e.keyFigures).map(([name, label]) => ({ name, label }));
  return (
    <div className="grid">
      <Section label={e.summary} wide>
        <Panel>
          <Rows>
            <Row label={e.chosen}>{entry.chosen}</Row>
            <Row label={e.recorded}>
              {e.recordedOn(displayDate(entry.recorded_at, locale), displayDate(entry.as_of, locale))}
              {via}
            </Row>
            <Row label={e.reviewOn}>
              {displayDate(entry.review_on, locale)} · {j.statuses[decision.status] ?? decision.status}
            </Row>
            <Row label={e.hash}>
              <code className="hash">{decision.hash}</code>
            </Row>
          </Rows>
          {decision.verified ? (
            <p className="quiet-success">
              <span aria-hidden="true">✓</span> {e.verified}
            </p>
          ) : (
            <p className="warn-line" role="alert">
              <span className="warn-mark" aria-hidden="true">
                !
              </span>{' '}
              {e.notVerified}
            </p>
          )}
          <Provenance>
            {e.id} {decision.id}
          </Provenance>
        </Panel>
      </Section>
      <Section label={e.reasons}>
        <Panel>
          <p className="own-words">{entry.reasons}</p>
          {entry.agent_summary ? (
            <>
              <p className="subhead">{e.agentSummary(entry.agent_summary.agent ?? e.anAgent)}</p>
              <p className="own-words">{entry.agent_summary.text}</p>
            </>
          ) : null}
        </Panel>
      </Section>
      <Review decision={decision} />
      <Section label={e.options} full>
        <Panel>
          <p className="section-help">{e.optionsHelp}</p>
          <Table<K>
            caption={e.options}
            captionHidden
            rows={keys}
            rowKey={(k) => k.name}
            columns={[
              { key: 'figure', header: labStrings.figureColumn, label: labStrings.figureColumn, render: (k) => k.label },
              {
                key: 'baseline',
                header: `${labStrings.baselineColumn} (${code})`,
                label: labStrings.baselineColumn,
                align: 'end',
                render: (k) => <FigureValue value={entry.baseline.figures[k.name]} name={k.name} currency={code} />,
              },
              ...entry.options.map((o, i) => {
                const header = o.label === entry.chosen ? `${o.label} ${labStrings.chosenTag}` : o.label;
                return {
                  key: `o${i}`,
                  header: `${header} (${code})`,
                  label: header,
                  align: 'end' as const,
                  render: (k: K) => <FigureValue value={o.figures[k.name]} name={k.name} currency={code} />,
                };
              }),
            ]}
          />
        </Panel>
      </Section>
      <Section label={e.principles} full>
        <Panel>
          <Checks
            principles={entry.principles}
            columns={[{ label: labStrings.baselineColumn, results: entry.baseline.principles }, ...entry.options.map((o) => ({ label: o.label, results: o.principles }))]}
            caption={e.principles}
          />
        </Panel>
      </Section>
      {decision.reviews.length ? (
        <Section label={e.reviews} full>
          <Panel>
            <ul className="list">
              {decision.reviews.map((r) => (
                <li key={r.review.id} className="stack-tight">
                  <p className="provenance">{e.reviewedOn(displayMoment(r.review.at, locale), displayDate(r.review.comparison.at, locale))}</p>
                  <ProjectedAgainstActual comparison={r.review.comparison} />
                  <p className="subhead">{e.yourReflection}</p>
                  <p className="own-words">{r.review.reflection}</p>
                </li>
              ))}
            </ul>
          </Panel>
        </Section>
      ) : null}
      <Notes decision={decision} />
      <Section label={e.basis}>
        <Basis placeholders={entry.basis.placeholders} isStale={entry.basis.is_stale} dataAsOf={entry.basis.data_as_of} notes={[e.engine(entry.basis.versions.engine)]} />
      </Section>
      <Download decision={decision} />
    </div>
  );
}

export function Entry() {
  const params = useParams({ strict: false }) as { decision?: string };
  const id = params.decision ?? '';
  const query = useRead('decisions.get', decisionsGet, { path: { decision_id: id } });
  return (
    <Page
      title={query.data?.entry.question ?? j.title}
      actions={query.data ? <ThinkItThrough prompt={labStrings.prompts.entry(query.data.entry.question, query.data.id)} /> : undefined}
    >
      <LabNav />
      <p>
        <Link to="/decide/journal">{e.back}</Link>
      </p>
      <Loaded query={query} lines={8}>
        {(decision) => <EntryView decision={decision} />}
      </Loaded>
    </Page>
  );
}

export default Entry;
