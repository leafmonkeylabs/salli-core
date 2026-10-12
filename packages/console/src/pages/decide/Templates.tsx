/**
 * Decision templates (`decisions.templates.list`, `.get`, `decisions.start`;
 * docs/templates.md): the seven templates; a template's questions as a form
 * built from its question schema, with Salli's honest defaults and where
 * each comes from; then the options it builds, compared, with the
 * principles each keeps and breaks. Starting stores nothing; recording is a
 * step of its own, asked for and confirmed.
 */
import {
  accountsList,
  debtsList,
  decisionsStart,
  decisionsTemplatesGet,
  decisionsTemplatesList,
  holdingsList,
  insightsRecurring,
  SalliApiError,
  type DecisionStart,
  type DecisionStartIn,
  type DecisionTemplate,
} from '@leafmonkeylabs/salli-sdk';
import { Link, useParams } from '@tanstack/react-router';
import { useMemo, useRef, useState, type FormEvent } from 'react';
import { useRead, useWrite } from '../../api';
import { displayDate, isoDate } from '../../kit/dates';
import { Button, Field } from '../../kit/forms';
import { dateInput } from '../../kit/inputs';
import { Loaded, Page, Panel, Section } from '../../kit/layout';
import { ProblemView } from '../../kit/Problem';
import { ThinkItThrough } from '../../kit/ThinkItThrough';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';
import { answerPath, collect, initialState, type Errors, type FormState } from './answers';
import { LabNav, templatePath } from './LabNav';
import { Questions, type Names } from './Questions';
import { RecordDecision } from './Record';
import { StartResult } from './StartResult';

const l = labStrings;
const t = l.templates;

export function TemplateList() {
  const query = useRead('decisions.templates.list', decisionsTemplatesList);
  return (
    <Page title={t.title} description={t.description}>
      <LabNav />
      <Loaded query={query}>
        {({ templates }) => (
          <ul className="cards">
            {templates.map((template) => (
              <li key={template.id} className="panel card">
                <h2 className="card-title">
                  <Link to={templatePath(template.id)}>{template.title}</Link>
                </h2>
                <p>{template.summary}</p>
                <p className="provenance">{t.builds(template.builds.join(', '))}</p>
              </li>
            ))}
          </ul>
        )}
      </Loaded>
    </Page>
  );
}

/** The person's own names for the ids a template's questions take. */
function useNames(template: DecisionTemplate): Names {
  const types = new Set(template.questions.map((q) => q.type));
  const accounts = useRead('accounts.list', accountsList, undefined, { enabled: types.has('account') });
  const debts = useRead('debts.list', debtsList, { query: { active_only: true } }, { enabled: types.has('debt') || types.has('splits') });
  const holdings = useRead('holdings.list', holdingsList, { query: { active_only: true } }, { enabled: types.has('holding') });
  const payments = useRead('insights.recurring', insightsRecurring, undefined, { enabled: types.has('recurring') });
  return useMemo(
    () => ({
      accounts: Object.fromEntries((accounts.data ?? []).map((a) => [a.id, a.name])),
      debts: Object.fromEntries((debts.data?.debts ?? []).map((d) => [d.id, d.name])),
      holdings: Object.fromEntries((holdings.data?.holdings ?? []).map((h) => [h.id, [h.symbol, h.name].filter(Boolean).join(' · ')])),
      payments: Object.fromEntries((payments.data?.items ?? []).map((p) => [p.key, p.payee])),
    }),
    [accounts.data, debts.data, holdings.data, payments.data],
  );
}

/** Salli's problems with the answers, at their paths. */
function serverErrors(error: unknown): Errors {
  if (!(error instanceof SalliApiError)) return {};
  const detail = error.detail;
  const out: Errors = {};
  if (!Array.isArray(detail)) return out;
  for (const item of detail as Array<{ loc?: unknown; msg?: unknown }>) {
    if (!Array.isArray(item.loc) || typeof item.msg !== 'string') continue;
    const path = answerPath(item.loc as Array<string | number>);
    if (path && !(path in out)) out[path] = item.msg;
  }
  return out;
}

function TemplateForm({ template }: { template: DecisionTemplate }) {
  const locale = useLocale();
  const names = useNames(template);
  const todayIso = isoDate(new Date());
  const [state, setState] = useState<FormState>(() => initialState(template));
  const [asOf, setAsOf] = useState('');
  const [local, setLocal] = useState<Errors>({});
  const [result, setResult] = useState<DecisionStart | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const start = useWrite<DecisionStartIn, DecisionStart>('decisions.start', (api, input) => api.call(decisionsStart, { body: input }), {
    onSuccess: (data) => {
      setResult(data);
      requestAnimationFrame(() => resultRef.current?.focus());
    },
  });
  const set = (id: string, value: FormState[string]): void => setState((s) => ({ ...s, [id]: value }));
  const errors: Errors = { ...(start.isError ? serverErrors(start.error) : {}), ...local };

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const { answers, errors: found } = collect(template, state, locale);
    if (asOf.trim() && !dateInput(asOf)) found.as_of = t.notADate;
    setLocal(found);
    if (Object.keys(found).length) return;
    setResult(null);
    start.mutate({ template: template.id, answers, ...(asOf.trim() ? { as_of: asOf.trim() } : {}) });
  };

  const problems = Object.entries(local);
  return (
    <>
      <Section label={t.answers}>
        <Panel>
          <p className="section-help">{t.answersHelp}</p>
          <form className="form form-wide" onSubmit={submit} noValidate aria-describedby={problems.length ? 'answers-problems' : undefined}>
            <Questions template={template} state={state} set={set} errors={errors} names={names} asOf={todayIso} />
            <Field label={t.asOf} description={t.asOfHelp} type="date" value={asOf} onChange={setAsOf} error={errors.as_of} inputProps={{ placeholder: todayIso }} />
            {problems.length ? (
              <div id="answers-problems" className="problem" role="alert">
                <p className="problem-title">
                  <span className="warn-mark" aria-hidden="true">
                    !
                  </span>{' '}
                  {t.problems}
                </p>
                <p>{t.fixBelow}</p>
              </div>
            ) : null}
            {start.isError && !start.stepUpPending ? <ProblemView error={start.error} compact /> : null}
            <div className="form-actions">
              <Button type="submit" isPending={start.isPending}>
                {start.isPending ? t.building : t.build}
              </Button>
            </div>
          </form>
        </Panel>
      </Section>
      {result ? (
        <div ref={resultRef} tabIndex={-1} className="result" aria-labelledby="start-result">
          <h2 id="start-result" className="result-title">
            {t.result}
          </h2>
          <p className="provenance">{l.basis.asOf(displayDate(result.as_of, locale), result.currency)}</p>
          <StartResult data={result} template={template} />
          <Section label={l.record.title}>
            <RecordDecision key={JSON.stringify(result.record)} data={result} />
          </Section>
        </div>
      ) : null}
    </>
  );
}

export function Template() {
  const params = useParams({ strict: false }) as { template?: string };
  const id = params.template ?? '';
  const locale = useLocale();
  const query = useRead('decisions.templates.get', decisionsTemplatesGet, { path: { template_id: id } });
  const title = query.data?.title ?? t.title;
  const today = displayDate(isoDate(new Date()), locale);
  return (
    <Page
      title={title}
      description={query.data?.summary ?? t.description}
      actions={query.data ? <ThinkItThrough prompt={l.prompts.start(query.data.id, query.data.title, today)} /> : undefined}
    >
      <LabNav />
      <Loaded query={query}>
        {(template) => (
          <>
            {template.notes.map((note, i) => (
              <p key={i} className="provenance">
                {note}
              </p>
            ))}
            <TemplateForm key={template.id} template={template} />
          </>
        )}
      </Loaded>
    </Page>
  );
}

export default Template;
