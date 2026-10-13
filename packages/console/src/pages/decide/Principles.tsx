/**
 * Principles (`principles.list`, `.figures`, `.check`, `.create`, `.update`,
 * `.archive`; docs/decisions.md, "Principles"): the person's own rules of
 * thumb, each with whether the baseline keeps it; adding and editing one,
 * with Salli's problems shown at their place in the check; archiving one,
 * asked first; and the figures a check may read. Salli parses and checks
 * every principle; the console only sends the words.
 */
import {
  accountsList,
  principlesArchive,
  principlesCheck,
  principlesCreate,
  principlesFigures,
  principlesList,
  principlesUpdate,
  type DecisionFigure,
  type Principle,
  type PrincipleChanges,
  type PrincipleIn,
  type PrinciplesCheck,
} from '@leafmonkeylabs/salli-sdk';
import { useState, type FormEvent } from 'react';
import { useRead, useWrite } from '../../api';
import { displayDate } from '../../kit/dates';
import { Button, Confirm, Field, SelectField } from '../../kit/forms';
import { Empty, Loaded, Page, Panel, Section } from '../../kit/layout';
import { fieldErrors, ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';
import { LabNav } from './LabNav';

const p = labStrings.principles;
const INVALIDATE = ['principles.list', 'principles.check'];

/** A problem in a check, with where it is: Salli's `snippet` marks the place with a caret. */
function snippets(error: unknown): string[] {
  const detail = (error as { detail?: unknown } | null)?.detail;
  if (!Array.isArray(detail)) return [];
  return (detail as Array<{ snippet?: unknown }>).flatMap((d) => (typeof d.snippet === 'string' && d.snippet ? [d.snippet] : []));
}

function useCashAccounts(): Array<{ value: string; label: string }> {
  const accounts = useRead('accounts.list', accountsList);
  return (accounts.data ?? []).filter((a) => a.type === 'asset' && a.is_active && a.asset_role === 'cash').map((a) => ({ value: a.id, label: a.name }));
}

interface PrincipleFormProps {
  initial?: Principle;
  onDone: (principle: Principle) => void;
  onCancel?: () => void;
}

function PrincipleForm({ initial, onDone, onCancel }: PrincipleFormProps) {
  const accounts = useCashAccounts();
  const [label, setLabel] = useState(initial?.label ?? '');
  const [check, setCheck] = useState(initial?.check ?? '');
  const [account, setAccount] = useState(initial?.account ?? '');
  const [note, setNote] = useState(initial?.note ?? '');
  const [local, setLocal] = useState<Record<string, string>>({});
  const add = useWrite<PrincipleIn, Principle>('principles.create', (api, body) => api.call(principlesCreate, { body }), { invalidate: INVALIDATE, onSuccess: onDone });
  const edit = useWrite<{ id: string; body: PrincipleChanges }, Principle>(
    'principles.update',
    (api, input) => api.call(principlesUpdate, { path: { principle_id: input.id }, body: input.body }),
    { invalidate: INVALIDATE, onSuccess: onDone },
  );
  const write = initial ? edit : add;
  const server = write.isError ? fieldErrors(write.error) : {};
  const errors = { ...server, ...local };
  const marks = write.isError ? snippets(write.error) : [];

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const found: Record<string, string> = {};
    if (!label.trim()) found.label = labStrings.templates.needed;
    if (!check.trim()) found.check = labStrings.templates.needed;
    setLocal(found);
    if (Object.keys(found).length) return;
    if (initial) {
      const body: PrincipleChanges = {};
      if (label.trim() !== initial.label) body.label = label.trim();
      if (check.trim() !== initial.check) body.check = check.trim();
      if ((account || null) !== initial.account) body.account = account || null;
      if ((note.trim() || null) !== initial.note) body.note = note.trim() || null;
      edit.mutate({ id: initial.id, body });
    } else {
      add.mutate({ label: label.trim(), check: check.trim(), ...(account ? { account } : {}), ...(note.trim() ? { note: note.trim() } : {}) });
    }
  };

  return (
    <form className="form" onSubmit={submit} noValidate>
      <Field label={p.label} description={p.labelHelp} value={label} onChange={setLabel} error={errors.label} isRequired />
      <Field label={p.check} description={p.checkHelp} value={check} onChange={setCheck} error={errors.check} isRequired inputProps={{ spellCheck: false, className: 'mono' }} />
      {marks.map((mark, i) => (
        <pre key={i} className="snippet" aria-hidden="true">
          {mark}
        </pre>
      ))}
      <SelectField label={p.accountField} description={p.accountHelp} value={account} onChange={setAccount} error={errors.account} options={[{ value: '', label: p.noAccount }, ...accounts]} />
      <Field label={p.note} value={note} onChange={setNote} error={errors.note} />
      {write.isError && !write.stepUpPending ? <ProblemView error={write.error} compact /> : null}
      <div className="form-actions">
        <Button type="submit" isPending={write.isPending}>
          {write.isPending ? p.keeping : initial ? p.save : p.keep}
        </Button>
        {onCancel ? (
          <Button variant="tertiary" onPress={onCancel}>
            {p.cancel}
          </Button>
        ) : null}
      </div>
    </form>
  );
}

function PrincipleItem({ principle, check, index, accountName, onSaved }: { principle: Principle; check: PrinciplesCheck | undefined; index: number; accountName: (id: string) => string; onSaved: (text: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const archive = useWrite<{ id: string }, Principle>('principles.archive', (api, input) => api.call(principlesArchive, { path: { principle_id: input.id } }), {
    invalidate: INVALIDATE,
    onSuccess: (done) => {
      setArchiving(false);
      onSaved(p.archived(done.label));
    },
  });
  const result = check?.baseline.results.find((r) => r.principle_id === principle.id) ?? check?.baseline.results[index];
  return (
    <li className="principle">
      {editing ? (
        <PrincipleForm
          initial={principle}
          onDone={(saved) => {
            setEditing(false);
            onSaved(p.saved(saved.label, saved.version));
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <>
          <p className="signal-title">{principle.label}</p>
          <p>
            <code className="check-code">{principle.check}</code>
            {principle.account ? <span className="muted"> · {p.account(accountName(principle.account))}</span> : null}
          </p>
          {principle.note ? <p className="muted">{principle.note}</p> : null}
          {result ? (
            <p className="provenance">
              {p.onBaseline}: {labStrings.checks.status[result.status] ?? result.status}. {result.reason}
            </p>
          ) : null}
          <p className="provenance">
            {p.version(principle.version)}
            {principle.author === 'agent' ? ` · ${p.byAgent(principle.agent ?? labStrings.entry.anAgent)}` : ''}
          </p>
          <div className="form-actions">
            <button type="button" className="button button-secondary" aria-label={p.editLabel(principle.label)} onClick={() => setEditing(true)}>
              {p.edit}
            </button>
            <button type="button" className="button-link" aria-label={p.archiveLabel(principle.label)} onClick={() => setArchiving(true)}>
              {p.archive}
            </button>
          </div>
          {archive.isError ? <ProblemView error={archive.error} compact /> : null}
          <Confirm
            isOpen={archiving}
            onOpenChange={setArchiving}
            title={p.archiveTitle}
            confirmLabel={p.archive}
            cancelLabel={p.cancel}
            onConfirm={() => archive.mutate({ id: principle.id })}
            isPending={archive.isPending}
          >
            <p>{p.archiveBody(principle.label)}</p>
          </Confirm>
        </>
      )}
    </li>
  );
}

function Figures() {
  const query = useRead('principles.figures', principlesFigures);
  return (
    <Loaded query={query}>
      {({ figures }) => (
        <>
          <p className="section-help">{p.figuresHelp(figures.length)}</p>
          <Table<DecisionFigure>
            caption={p.figures}
            captionHidden
            rows={figures}
            rowKey={(f) => f.name}
            columns={[
              { key: 'name', header: p.figureName, label: p.figureName, render: (f) => <code>{f.name}</code> },
              { key: 'unit', header: p.figureUnit, label: p.figureUnit, render: (f) => f.unit },
              { key: 'terms', header: p.figureMoney, label: p.figureMoney, render: (f) => p.terms[f.terms] ?? '' },
              { key: 'what', header: p.figureWhat, label: p.figureWhat, render: (f) => f.description },
            ]}
          />
        </>
      )}
    </Loaded>
  );
}

export function Principles() {
  const locale = useLocale();
  const list = useRead('principles.list', principlesList, { query: { include_archived: true } });
  const check = useRead('principles.check', principlesCheck, { body: { options: [] } });
  const accounts = useRead('accounts.list', accountsList);
  const [said, setSaid] = useState('');
  const [adding, setAdding] = useState(0);
  const accountName = (id: string): string => accounts.data?.find((a) => a.id === id)?.name ?? id;
  return (
    <Page title={p.title} description={p.description}>
      <LabNav />
      <div className="grid">
        <Section label={p.inUse} wide>
          <Panel>
            <p role="status" className="quiet-success">
              {said ? (
                <>
                  <span aria-hidden="true">✓</span> {said}
                </>
              ) : null}
            </p>
            <Loaded query={list}>
              {({ principles }) => {
                const active = principles.filter((x) => x.status === 'active');
                const archived = principles.filter((x) => x.status === 'archived');
                return (
                  <>
                    {active.length ? (
                      <ul className="list">
                        {active.map((principle, i) => (
                          <PrincipleItem key={principle.id} principle={principle} check={check.data} index={i} accountName={accountName} onSaved={setSaid} />
                        ))}
                      </ul>
                    ) : (
                      <Empty>{p.none}</Empty>
                    )}
                    {archived.length ? (
                      <details className="disclosure">
                        <summary>{p.archivedTitle(archived.length)}</summary>
                        <ul className="list">
                          {archived.map((principle) => (
                            <li key={principle.id}>
                              <p>{principle.label}</p>
                              <p>
                                <code className="check-code">{principle.check}</code>
                              </p>
                              {principle.archived_at ? <p className="provenance">{p.archivedOn(displayDate(principle.archived_at, locale))}</p> : null}
                            </li>
                          ))}
                        </ul>
                      </details>
                    ) : null}
                  </>
                );
              }}
            </Loaded>
          </Panel>
        </Section>
        <Section label={p.add}>
          <Panel>
            <PrincipleForm
              key={adding}
              onDone={(added) => {
                setAdding((n) => n + 1);
                setSaid(p.kept(added.label));
              }}
            />
          </Panel>
        </Section>
        <Section label={p.figures} full>
          <Panel>
            <Figures />
          </Panel>
        </Section>
      </div>
    </Page>
  );
}

export default Principles;
