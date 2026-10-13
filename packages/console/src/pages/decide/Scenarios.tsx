/**
 * Scenarios (`scenarios.run`, `scenarios.compare`, `principles.check`;
 * docs/scenarios.md): options built from changes, each a form for its
 * `salli.scenario/1` type, or loaded from a scenario document. One option
 * runs against the baseline; two to five are compared side by side, in the
 * order the person added them. Both timelines are drawn (`?timeline=true`)
 * with the break-evens beside them, and the person's principles checked.
 * Nothing is stored.
 */
import {
  accountsList,
  debtsList,
  holdingsList,
  insightsRecurring,
  parseJsonExact,
  principlesCheck,
  SalliApiError,
  scenariosCompare,
  scenariosRun,
  type PrinciplesCheck,
  type Scenario,
  type ScenarioComparison,
  type ScenarioRun,
} from '@leafmonkeylabs/salli-sdk';
import { useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { useRead, useWrite } from '../../api';
import { displayDate, isoDate } from '../../kit/dates';
import { saveText } from '../../kit/download';
import { Button, Field, SelectField, TextAreaField } from '../../kit/forms';
import { wholeNumberInput } from '../../kit/inputs';
import { Page, Panel, Section } from '../../kit/layout';
import { ProblemView } from '../../kit/Problem';
import { ThinkItThrough } from '../../kit/ThinkItThrough';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';
import { Basis } from './Basis';
import { buildOption, CHANGE_FIELDS, CHANGE_TYPES, scenarioErrors, type ChangeState, type ChangeType, type FieldSpec, type OptionState, type ScenarioErrors } from './changes';
import { Checks } from './Checks';
import { BreakEvens, Sensitivity, SideBySide, Trade } from './Comparison';
import { LabNav } from './LabNav';
import { CashLines, NetWorthLines } from './Timelines';

const l = labStrings;
const sc = l.scenarios;

let nextId = 1;
const newId = (): number => nextId++;

function emptyOption(): OptionState {
  return { id: newId(), label: '', changes: [] };
}

interface Choices {
  accounts: Array<{ value: string; label: string }>;
  debts: Array<{ value: string; label: string }>;
  holdings: Array<{ value: string; label: string }>;
  payments: Array<{ value: string; label: string }>;
}

function useChoices(): Choices {
  const accounts = useRead('accounts.list', accountsList);
  const debts = useRead('debts.list', debtsList, { query: { active_only: true } });
  const holdings = useRead('holdings.list', holdingsList, { query: { active_only: true } });
  const payments = useRead('insights.recurring', insightsRecurring);
  return {
    accounts: (accounts.data ?? []).filter((a) => a.type === 'asset' && a.is_active && a.asset_role === 'cash').map((a) => ({ value: a.id, label: a.name })),
    debts: (debts.data?.debts ?? []).map((d) => ({ value: d.id, label: d.name })),
    holdings: (holdings.data?.holdings ?? []).map((h) => ({ value: h.id, label: [h.symbol, h.name].filter(Boolean).join(' · ') })),
    payments: (payments.data?.items ?? []).map((p) => ({ value: p.key, label: p.payee })),
  };
}

function ChangeField({ spec, value, onChange, error, choices }: { spec: FieldSpec; value: string; onChange: (v: string) => void; error: string | undefined; choices: Choices }) {
  const label = `${sc.fields[spec.label ?? spec.key] ?? spec.key}${spec.required ? '' : ` (${l.templates.optional.toLowerCase()})`}`;
  const pick = (options: Array<{ value: string; label: string }>, none: string) => (
    <SelectField label={label} value={value} onChange={onChange} error={error} isRequired={spec.required} options={[{ value: '', label: none }, ...options]} />
  );
  switch (spec.kind) {
    case 'account':
      return pick(choices.accounts, l.templates.cashAsAWhole);
    case 'debt':
      return pick(choices.debts, choices.debts.length ? l.templates.chooseDebt : sc.noDebts);
    case 'holding':
      return pick(choices.holdings, choices.holdings.length ? l.templates.leaveOut : sc.noHoldingsToSell);
    case 'recurring':
      return pick(choices.payments, choices.payments.length ? l.templates.leaveOut : sc.noRecurring);
    case 'cadence':
      return pick(
        Object.entries(sc.cadences).map(([v, text]) => ({ value: v, label: text })),
        l.templates.leaveOut,
      );
    default:
      return (
        <Field
          label={label}
          value={value}
          onChange={onChange}
          error={error}
          isRequired={spec.required}
          {...(spec.kind === 'date' ? { type: 'date' as const } : {})}
          {...(spec.kind === 'role' ? { description: sc.fields.tax_roleHelp } : {})}
          inputProps={{
            inputMode: spec.kind === 'whole' ? 'numeric' : ['signed', 'positive', 'fees', 'rate', 'growth'].includes(spec.kind) ? 'decimal' : 'text',
            ...(spec.kind === 'role' ? { spellCheck: false } : {}),
          }}
        />
      );
  }
}

function ChangeForm({
  change,
  index,
  option,
  errors,
  choices,
  onChange,
  onRemove,
}: {
  change: ChangeState;
  index: number;
  option: number;
  errors: ScenarioErrors;
  choices: Choices;
  onChange: (values: Record<string, string>) => void;
  onRemove: () => void;
}) {
  const path = `${option}.changes.${index}`;
  return (
    <fieldset className="group-item change">
      <legend className="subhead">
        {sc.change(index + 1)}: {sc.types[change.type] ?? change.type}
      </legend>
      {errors[path] ? <p className="field-error">{errors[path]}</p> : null}
      <div className="field-grid">
        {CHANGE_FIELDS[change.type].map((spec) => (
          <ChangeField
            key={spec.key}
            spec={spec}
            value={change.values[spec.key] ?? ''}
            onChange={(v) => onChange({ ...change.values, [spec.key]: v })}
            error={errors[`${path}.${spec.key}`]}
            choices={choices}
          />
        ))}
      </div>
      <button type="button" className="button-link" onClick={onRemove}>
        {sc.removeChange(index + 1)}
      </button>
    </fieldset>
  );
}

function DocumentLoader({ onLoad }: { onLoad: (doc: Record<string, unknown>) => void }) {
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const use = (raw: string): void => {
    try {
      const doc = parseJsonExact(raw);
      if (typeof doc !== 'object' || doc === null || Array.isArray(doc) || (doc as { schema?: unknown }).schema !== 'salli.scenario/1') throw new Error('not a scenario');
      setError('');
      onLoad(doc as Record<string, unknown>);
    } catch {
      setError(sc.documentInvalid);
    }
  };
  const fromFile = async (event: ChangeEvent<HTMLInputElement>): Promise<void> => {
    const file = event.currentTarget.files?.[0];
    if (!file) return;
    const raw = await file.text();
    setText(raw);
    use(raw);
  };
  return (
    <details className="disclosure">
      <summary>{sc.document}</summary>
      <div className="stack-tight">
        <p className="field-help">{sc.documentHelp}</p>
        <TextAreaField label={sc.documentPaste} value={text} onChange={setText} error={error} rows={6} />
        <div className="form-actions">
          <button type="button" className="button button-secondary" onClick={() => use(text)}>
            {sc.documentUse}
          </button>
          <label className="button button-tertiary file-button">
            {sc.documentFile}
            <input type="file" accept="application/json,.json" className="sr-only" onChange={(event) => void fromFile(event)} />
          </label>
        </div>
      </div>
    </details>
  );
}

function OptionForm({
  option,
  index,
  count,
  errors,
  choices,
  update,
  remove,
}: {
  option: OptionState;
  index: number;
  count: number;
  errors: ScenarioErrors;
  choices: Choices;
  update: (next: OptionState) => void;
  remove: () => void;
}) {
  const [adding, setAdding] = useState<ChangeType | ''>('');
  const name = option.label.trim() || sc.option(index + 1);
  return (
    <fieldset className="panel option-form">
      <legend className="option-legend">{name}</legend>
      <Field label={sc.optionLabel} value={option.label} onChange={(v) => update({ ...option, label: v })} error={errors[`${index}.label`]} inputProps={{ placeholder: sc.option(index + 1) }} />
      {option.document ? (
        <div className="stack-tight">
          <p className="provenance">{sc.documentInUse}</p>
          <pre className="snippet document-preview">{JSON.stringify(option.document, null, 2)}</pre>
          <button type="button" className="button-link" onClick={() => update({ id: option.id, label: option.label, changes: option.changes })}>
            {sc.documentEdit}
          </button>
        </div>
      ) : (
        <>
          <p className="subhead">{sc.changes}</p>
          {option.changes.length ? null : <p className="empty">{sc.noChanges}</p>}
          {option.changes.map((change, j) => (
            <ChangeForm
              key={change.id}
              change={change}
              index={j}
              option={index}
              errors={errors}
              choices={choices}
              onChange={(values) => update({ ...option, changes: option.changes.map((c) => (c.id === change.id ? { ...c, values } : c)) })}
              onRemove={() => update({ ...option, changes: option.changes.filter((c) => c.id !== change.id) })}
            />
          ))}
          <div className="add-change">
            <SelectField
              label={sc.changeType}
              value={adding}
              onChange={(v) => setAdding(v as ChangeType | '')}
              options={[{ value: '', label: sc.chooseKind }, ...CHANGE_TYPES.map((type) => ({ value: type, label: sc.types[type] ?? type }))]}
            />
            <button
              type="button"
              className="button button-secondary"
              disabled={!adding}
              onClick={() => {
                if (!adding) return;
                update({ ...option, changes: [...option.changes, { id: newId(), type: adding, values: {} }] });
                setAdding('');
              }}
            >
              {sc.addChange}
            </button>
          </div>
          <DocumentLoader onLoad={(doc) => update({ ...option, document: doc, label: option.label || (typeof doc.label === 'string' ? doc.label : '') })} />
        </>
      )}
      {count > 1 ? (
        <button type="button" className="button-link" onClick={remove}>
          {sc.removeOption(name)}
        </button>
      ) : null}
    </fieldset>
  );
}

type Outcome = { kind: 'run'; run: ScenarioRun; check: PrinciplesCheck } | { kind: 'compare'; comparison: ScenarioComparison; check: PrinciplesCheck };

function Result({ outcome }: { outcome: Outcome }) {
  const locale = useLocale();
  const runs = outcome.kind === 'run' ? [outcome.run] : outcome.comparison.options;
  const labels = outcome.kind === 'run' ? [outcome.run.label ?? sc.option(1)] : outcome.comparison.labels;
  const first = runs[0];
  if (!first) return null;
  const placeholders = [...new Set(runs.flatMap((r) => r.placeholders))];
  const tax = runs.find((r) => r.tax.status === 'not_computed')?.tax ?? runs.find((r) => r.tax.status === 'computed')?.tax;
  const notes = [...new Set(runs.flatMap((r) => r.notes))];
  const breakEvens = outcome.kind === 'run' ? outcome.run.break_evens : outcome.comparison.break_evens;
  const check = outcome.check;
  return (
    <div className="grid">
      <Section label={l.lines.cash} wide>
        <Panel>
          <CashLines runs={runs} labels={labels} />
        </Panel>
      </Section>
      <Section label={l.basis.label}>
        <Basis
          asOf={l.basis.asOfHorizon(displayDate(first.as_of, locale), first.currency, l.figure.years(first.horizon_years))}
          placeholders={placeholders}
          isStale={first.is_stale}
          dataAsOf={first.data_as_of}
          tax={tax}
          notes={notes}
        />
      </Section>
      <Section label={l.lines.netWorth} wide>
        <Panel>
          <NetWorthLines runs={runs} labels={labels} />
        </Panel>
      </Section>
      <Section label={l.compare.breakEvens}>
        <Panel>
          <BreakEvens items={breakEvens} currency={first.currency} />
        </Panel>
      </Section>
      <Section label={sc.figures} full>
        <Panel>
          <SideBySide runs={runs} labels={labels} caption={sc.figures} />
        </Panel>
      </Section>
      {outcome.kind === 'compare' ? (
        <>
          <Section label={l.compare.trade} full>
            <Panel>
              <Trade data={outcome.comparison} />
            </Panel>
          </Section>
          <Section label={l.compare.sensitivity} full>
            <Panel>
              <Sensitivity data={outcome.comparison} />
            </Panel>
          </Section>
        </>
      ) : null}
      <Section label={l.checks.title} full>
        <Panel>
          <p className="section-help">{l.checks.help}</p>
          <Checks
            principles={check.principles}
            columns={[{ label: l.baselineColumn, results: check.baseline.results }, ...check.options.map((o) => ({ label: o.label, results: o.results }))]}
          />
        </Panel>
      </Section>
      <p className="provenance section-full">{l.compare.noRanking}</p>
    </div>
  );
}

export function Scenarios() {
  const locale = useLocale();
  const choices = useChoices();
  const [options, setOptions] = useState<OptionState[]>(() => [emptyOption()]);
  const [horizon, setHorizon] = useState('');
  const [asOf, setAsOf] = useState('');
  const [local, setLocal] = useState<ScenarioErrors>({});
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const compared = options.length > 1;
  const write = useWrite<{ docs: Scenario[] }, Outcome>(
    'scenarios.run',
    async (api, { docs }) => {
      if (docs.length === 1) {
        const run = await api.call(scenariosRun, { body: docs[0] as Scenario, query: { timeline: true } });
        return { kind: 'run', run, check: await api.call(principlesCheck, { body: { options: docs } }) };
      }
      const comparison = await api.call(scenariosCompare, { body: { options: docs }, query: { timeline: true } });
      return { kind: 'compare', comparison, check: await api.call(principlesCheck, { body: { options: docs } }) };
    },
    {
      onSuccess: (result) => {
        setOutcome(result);
        requestAnimationFrame(() => resultRef.current?.focus());
      },
    },
  );
  const server = write.error instanceof SalliApiError ? scenarioErrors(write.error.detail, compared) : {};
  const errors = { ...server, ...local };

  const docs = (): { docs: Scenario[]; errors: ScenarioErrors } => {
    const found: ScenarioErrors = {};
    const years = horizon.trim() ? wholeNumberInput(horizon) : undefined;
    if (horizon.trim() && years === undefined) found.horizon_years = l.templates.notAWholeNumber;
    const out = options.map((option, i) => {
      const built = buildOption(option, i, { horizon: years, asOf: asOf.trim() || undefined }, locale);
      Object.assign(found, built.errors);
      return built.doc;
    });
    return { docs: out, errors: found };
  };

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const built = docs();
    setLocal(built.errors);
    if (Object.keys(built.errors).length) return;
    setOutcome(null);
    write.mutate({ docs: built.docs });
  };

  const save = (index: number): void => {
    const option = options[index];
    if (!option) return;
    const built = buildOption(option, index, { horizon: wholeNumberInput(horizon), asOf: asOf.trim() || undefined }, locale);
    const name = (option.label.trim() || sc.option(index + 1)).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'scenario';
    saveText(`${name}.json`, `${JSON.stringify(built.doc, null, 2)}\n`, 'application/json');
  };

  const problems = Object.keys(local).length;
  return (
    <Page title={sc.title} description={sc.description} actions={<ThinkItThrough prompt={l.prompts.scenarios(isoDate(new Date()))} />}>
      <LabNav />
      <form className="scenario-form" onSubmit={submit} noValidate>
        <div className="options">
          {options.map((option, i) => (
            <div key={option.id} className="option-cell">
              <OptionForm
                option={option}
                index={i}
                count={options.length}
                errors={errors}
                choices={choices}
                update={(next) => setOptions((all) => all.map((o) => (o.id === option.id ? next : o)))}
                remove={() => setOptions((all) => all.filter((o) => o.id !== option.id))}
              />
              <button type="button" className="button-link" onClick={() => save(i)}>
                {sc.save}
              </button>
            </div>
          ))}
        </div>
        <div className="form-actions">
          {options.length < 5 ? (
            <button type="button" className="button button-secondary" onClick={() => setOptions((all) => [...all, emptyOption()])}>
              {sc.addOption}
            </button>
          ) : null}
        </div>
        <div className="field-row shared-fields">
          <Field label={sc.horizon} description={sc.horizonHelp} value={horizon} onChange={setHorizon} error={errors.horizon_years} inputProps={{ inputMode: 'numeric', placeholder: '20' }} />
          <Field label={sc.asOf} description={l.templates.asOfHelp} type="date" value={asOf} onChange={setAsOf} error={errors.as_of} />
        </div>
        {problems ? (
          <div className="problem" role="alert">
            <p className="problem-title">
              <span className="warn-mark" aria-hidden="true">
                !
              </span>{' '}
              {sc.problems}
            </p>
            <p>{l.templates.fixBelow}</p>
          </div>
        ) : null}
        {write.isError && !write.stepUpPending ? <ProblemView error={write.error} compact /> : null}
        <div className="form-actions">
          <Button type="submit" isPending={write.isPending}>
            {write.isPending ? sc.running : compared ? sc.compare(options.length) : sc.run}
          </Button>
        </div>
      </form>
      {outcome ? (
        <div ref={resultRef} tabIndex={-1} className="result" aria-labelledby="scenario-result">
          <h2 id="scenario-result" className="result-title">
            {outcome.kind === 'run' ? sc.result : sc.resultCompare}
          </h2>
          <Result outcome={outcome} />
        </div>
      ) : null}
    </Page>
  );
}

export default Scenarios;
