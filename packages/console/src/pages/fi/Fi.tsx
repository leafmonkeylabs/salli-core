/**
 * Financial independence (docs/design/console.md, section 5; `salli fi
 * score`, `projections`, `assumptions`, `history`): the FI
 * number and how far along you are, the savings rate and the month you
 * would get there; your invested money projected at three real returns,
 * drawn against the FI number; the parts the score is made of; the
 * assumptions every figure rests on, each placeholder flagged, and setting
 * your own (`fi.assumptions.set`) with where each comes from; the score
 * over time. Every figure is the server's: the console neither projects nor converts.
 */
import {
  fiAssumptions,
  fiAssumptionsSet,
  fiProjections,
  fiScoreGet,
  fiScoreHistory,
  formatDecimal,
  formatRatio,
  type FiAssumption,
  type FiAssumptions,
  type FiAssumptionsReport,
  type FiAssumptionsUpdate,
  type FiOwnAssumption,
  type FiProjectionPoint,
  type FiProjections,
  type FiScore,
  type FiScoreComponent,
  type FiScoreSnapshot,
} from '@leafmonkeylabs/salli-sdk';
import { useState, type FormEvent } from 'react';
import { problemOf, useRead, useWrite } from '../../api';
import { LineChart } from '../../kit/chart/LineChart';
import { displayDate, displayMonth } from '../../kit/dates';
import { Button, Field } from '../../kit/forms';
import { rateInput } from '../../kit/inputs';
import { Empty, Grid, Loaded, Page, Panel, Provenance, Row, Rows, Section } from '../../kit/layout';
import { Money, visibleAmount } from '../../kit/Money';
import { ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { whereStrings } from '../../where-strings';

const f = whereStrings.fi;
/** The reads an assumption changes: every FI figure, the baseline's and Home's. */
const INVALIDATE = ['fi.assumptions', 'fi.score.get', 'fi.projections', 'fi.score.history', 'baseline.get'];
const SCENARIOS = ['base', 'conservative', 'growth'] as const;
/** The assumptions a person can set, as the API names them, in the order the page shows them. */
const KEYS = ['real_return', 'inflation', 'safe_withdrawal_rate', 'surplus_invested', 'nominal_return'] as const;
type Key = (typeof KEYS)[number];

/** A yearly rate or a share as a percentage, to a hundredth of a point: "3.5%". */
function rate(value: string | number | null | undefined, locale: string | undefined): string {
  return value === null || value === undefined ? f.none : formatRatio(value, { locale, maximumFractionDigits: 2 });
}

function PlaceholderTag() {
  return (
    <span className="placeholder-tag">
      <span className="warn-mark" aria-hidden="true">
        !
      </span>{' '}
      {f.placeholder}
    </span>
  );
}

function Basis({ assumptions }: { assumptions: FiAssumptions | null | undefined }) {
  if (!assumptions) return null;
  return (
    <Provenance>
      {assumptions.status === 'placeholder' ? (
        <span className="placeholder-tag">
          <span className="warn-mark" aria-hidden="true">
            !
          </span>{' '}
          {f.placeholders}.
        </span>
      ) : (
        `${f.own}.`
      )}{' '}
      {assumptions.message}
      {assumptions.cash_yield?.origin === 'placeholder' ? ` ${assumptions.cash_yield.source}` : null}
    </Provenance>
  );
}

function Where({ score }: { score: FiScore }) {
  const locale = useLocale();
  const cur = score.currency;
  return (
    <Panel>
      <p className="figure">
        <span className="figure-number">{formatDecimal(score.overall_score, { locale })}</span>{' '}
        <span className="figure-note">
          {f.score} · {f.grade(score.grade)}
        </span>
      </p>
      <Rows>
        <Row label={f.fiNumber}>
          <Money amount={score.fi_number} currency={cur} variant="table" withCode />
          {score.headline_status ? (
            <span className={score.headline_status === 'placeholder' ? 'placeholder-tag' : undefined} title={score.headline ?? undefined}>
              {' '}
              {score.headline_status === 'placeholder' ? (
                <span className="warn-mark" aria-hidden="true">
                  !
                </span>
              ) : null}{' '}
              {f.headline[score.headline_status]}
            </span>
          ) : null}
        </Row>
        {score.headline ? <Provenance>{score.headline}</Provenance> : null}
        {score.fi_asset_base ? (
          <Row label={f.investedNow}>
            <Money amount={score.fi_asset_base} currency={cur} variant="table" withCode />
          </Row>
        ) : null}
        <Row label={f.progress}>{rate(score.progress_to_fi, locale)}</Row>
        <Row label={f.fiBy}>{score.projected_fi_month ? displayMonth(score.projected_fi_month, locale) : f.notInReach}</Row>
        <Row label={f.netWorth}>
          <Money amount={score.net_worth} currency={cur} variant="table" withCode />
        </Row>
        <Row label={f.income}>
          <Money amount={score.monthly_income} currency={cur} variant="table" withCode />
        </Row>
        <Row label={f.spending}>
          <Money amount={score.monthly_expenses} currency={cur} variant="table" withCode />
        </Row>
        <Row label={f.surplus}>
          <Money amount={score.monthly_surplus} currency={cur} variant="table" withCode />
        </Row>
        <Row label={f.savingsRate}>{rate(score.savings_rate, locale)}</Row>
        <Row label={f.emergency}>{f.months(formatDecimal(score.emergency_fund_months, { locale }))}</Row>
      </Rows>
      {score.swr ? <Provenance>{f.fiNumberHelp(rate(score.swr, locale))}</Provenance> : null}
      <Basis assumptions={score.assumptions} />
      {score.as_of ? <Provenance>{f.asOf(displayDate(score.as_of, locale))}</Provenance> : null}
    </Panel>
  );
}

function ProjectionChart({ data }: { data: FiProjections }) {
  const locale = useLocale();
  const points = data.points ?? [];
  const code = (data.currency ?? '').toUpperCase();
  const last = points[points.length - 1];
  if (!last || !code) return <Empty>{f.projectionsEmpty}</Empty>;
  const returns = data.real_returns;
  const name = (s: (typeof SCENARIOS)[number]): string => (returns?.[s] ? f.scenarioAt(f.scenario[s] ?? s, rate(returns[s], locale)) : (f.scenario[s] ?? s));
  const years = (y: number | null | undefined): string => (!y ? f.now : f.inYears(y));
  const step = points.length > 25 ? 10 : 5;
  const ticks = points.flatMap((p, i) => ((p.year ?? 0) % step === 0 ? [i] : []));
  const nominal = data.terms === 'real_and_nominal';
  const caption = f.projectionsCaption(
    years(last.year).toLowerCase().replace(/^in /, ''),
    visibleAmount(last.base ?? '', code, 'prose', { locale }),
    visibleAmount(data.fi_number ?? '', code, 'prose', { locale }),
  );
  return (
    <LineChart
      caption={caption}
      currency={code}
      at={points.map((p) => years(p.year))}
      ticks={{ wide: ticks, narrow: ticks.filter((_, k) => k % 2 === 0) }}
      series={SCENARIOS.map((s) => ({ label: name(s), values: points.map((p) => p[s] ?? null) }))}
      {...(data.fi_number ? { reference: { value: data.fi_number, label: f.fiNumber } } : {})}
      figures={
        <Table<FiProjectionPoint>
          caption={caption}
          captionHidden
          rows={points}
          rowKey={(p) => String(p.year)}
          columns={[
            { key: 'year', header: f.year, label: f.year, render: (p) => years(p.year) },
            ...SCENARIOS.map((s) => ({
              key: s,
              header: `${f.scenario[s] ?? s} (${code})`,
              label: f.scenario[s] ?? s,
              align: 'end' as const,
              render: (p: FiProjectionPoint) => <Money amount={p[s]} currency={code} variant="table" />,
            })),
            ...(nominal
              ? [
                  {
                    key: 'then',
                    header: `${f.then(f.scenario.base ?? 'Base')} (${code})`,
                    label: f.then(f.scenario.base ?? 'Base'),
                    align: 'end' as const,
                    render: (p: FiProjectionPoint) => <Money amount={p.nominal?.base} currency={code} variant="table" />,
                  },
                  {
                    key: 'fi-then',
                    header: `${f.fiNumberThen} (${code})`,
                    label: f.fiNumberThen,
                    align: 'end' as const,
                    render: (p: FiProjectionPoint) => <Money amount={p.nominal?.fi_number} currency={code} variant="table" />,
                  },
                ]
              : []),
          ]}
        />
      }
    />
  );
}

function Projections() {
  const locale = useLocale();
  const query = useRead('fi.projections', fiProjections);
  return (
    <Section label={f.projections} wide>
      <Loaded query={query} lines={6}>
        {(data) => (
          <Panel>
            <ProjectionChart data={data} />
            {data.fi_by ? (
              <>
                <p className="subhead">{f.fiDates}</p>
                <Rows>
                  {(['conservative', 'base', 'growth'] as const).map((s) => (
                    <Row key={s} label={data.real_returns?.[s] ? f.scenarioAt(f.scenario[s] ?? s, rate(data.real_returns[s], locale)) : (f.scenario[s] ?? s)}>
                      {data.fi_by?.[s].month ? displayMonth(data.fi_by[s].month, locale) : f.notInReach}
                    </Row>
                  ))}
                </Rows>
              </>
            ) : null}
            <Provenance>{data.terms === 'real_and_nominal' ? f.nominalNote(rate(data.inflation, locale)) : f.realNote}</Provenance>
            <Basis assumptions={data.assumptions} />
          </Panel>
        )}
      </Loaded>
    </Section>
  );
}

function Components({ score }: { score: FiScore }) {
  const locale = useLocale();
  return (
    <Panel>
      <p className="section-help">{f.componentsHelp}</p>
      <Table<FiScoreComponent>
        caption={f.components}
        captionHidden
        rows={score.components}
        rowKey={(c) => c.key}
        columns={[
          { key: 'part', header: f.part, label: f.part, render: (c) => c.label },
          { key: 'score', header: f.partScore, label: f.partScore, align: 'end', render: (c) => formatDecimal(c.score, { locale }) },
          { key: 'weight', header: f.weight, label: f.weight, align: 'end', render: (c) => rate(c.weight, locale) },
          { key: 'why', header: f.why, label: f.why, render: (c) => c.detail },
        ]}
      />
    </Panel>
  );
}

/** One assumption: what is in use and where it came from, then setting your own. */
function Assumption({
  name,
  applied,
  own,
  onSaved,
}: {
  name: Key;
  applied: FiAssumption | null | undefined;
  own: FiOwnAssumption | null | undefined;
  onSaved: (text: string) => void;
}) {
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(own ? rate(own.value, locale) : '');
  const [source, setSource] = useState(own?.source ?? '');
  const [note, setNote] = useState(own?.note ?? '');
  const [local, setLocal] = useState('');
  const label = f.names[name] ?? name;
  const write = useWrite<{ body: FiAssumptionsUpdate; cleared: boolean }, FiAssumptionsReport>('fi.assumptions.set', (api, input) => api.call(fiAssumptionsSet, { body: input.body }), {
    invalidate: INVALIDATE,
    onSuccess: (_, input) => {
      setOpen(false);
      onSaved(input.cleared ? f.cleared(label) : f.saved(label));
    },
  });
  // Salli's refusal names the assumption; it belongs at this one's value.
  const refused = write.isError ? problemOf(write.error) : undefined;
  const error = local || (refused && refused.status === 422 ? String(refused.toProblem().detail ?? refused.message) : '');
  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    onSaved('');
    const parsed = value.trim() ? rateInput(value, locale) : undefined;
    if (!parsed) {
      setLocal(value.trim() ? f.badRate : f.needed);
      return;
    }
    setLocal('');
    write.mutate({ body: { [name]: { value: parsed, source: source.trim() || null, note: note.trim() || null } }, cleared: false });
  };
  const origin = applied ? (applied.origin === 'placeholder' ? <PlaceholderTag /> : applied.origin === 'derived' ? f.derived : f.you) : f.notSet;
  return (
    <li className="assumption">
      <div className="assumption-head">
        <p className="panel-title">{label}</p>
        <p className="assumption-value">{applied ? rate(applied.value, locale) : f.notSet}</p>
      </div>
      <p className="section-help">{f.meaning[name]}</p>
      <Rows>
        <Row label={f.setBy}>{origin}</Row>
        {own?.set_at ? <Row label={f.when}>{f.setOn(displayDate(own.set_at, locale))}</Row> : null}
      </Rows>
      {applied?.source ? <Provenance>{`${f.source}: ${applied.source}`}</Provenance> : null}
      {applied?.note ? <Provenance>{`${f.note}: ${applied.note}`}</Provenance> : null}
      {open ? (
        <form className="form" onSubmit={submit} noValidate aria-label={`${f.setYours}: ${label}`}>
          <Field
            label={`${label}: ${f.value}`}
            description={name === 'surplus_invested' ? f.shareHelp : f.valueHelp(name === 'inflation' ? '2.5% or 0.025' : '3.5% or 0.035')}
            value={value}
            onChange={setValue}
            error={error}
            isRequired
            inputProps={{ inputMode: 'decimal' }}
          />
          <Field label={f.sourceField} description={f.sourceHelp} value={source} onChange={setSource} />
          {!source.trim() ? <p className="warn-line">{f.noSource}</p> : null}
          <Field label={f.note} value={note} onChange={setNote} />
          {write.isError && !write.stepUpPending && !(refused && refused.status === 422) ? <ProblemView error={write.error} compact /> : null}
          <div className="form-actions">
            <Button type="submit" isPending={write.isPending}>
              {write.isPending ? f.saving : f.save}
            </Button>
            <Button variant="tertiary" onPress={() => setOpen(false)}>
              {whereStrings.attention.cancel}
            </Button>
          </div>
        </form>
      ) : (
        <div className="form-actions">
          <Button variant="secondary" onPress={() => setOpen(true)} aria-label={`${own ? f.change : f.setYours}: ${label}`}>
            {own ? f.change : f.setYours}
          </Button>
          {own ? (
            <Button variant="tertiary" onPress={() => write.mutate({ body: { [name]: null }, cleared: true })} isPending={write.isPending}>
              {write.isPending ? f.clearing : f.clear}
            </Button>
          ) : null}
        </div>
      )}
      {error && !open ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </li>
  );
}

function Assumptions() {
  const locale = useLocale();
  const [said, setSaid] = useState('');
  const query = useRead('fi.assumptions', fiAssumptions);
  return (
    <Section label={f.assumptions} full anchor="assumptions">
      <Loaded query={query}>
        {(report) => {
          return (
            <Panel>
              <p className="section-help">{f.assumptionsHelp}</p>
              <Basis assumptions={report.applied} />
              <ul className="list assumptions">
                {KEYS.map((key) => (
                  <Assumption key={`${key}-${report.own[key]?.set_at ?? ''}`} name={key} applied={report.applied[key]} own={report.own[key]} onSaved={setSaid} />
                ))}
              </ul>
              <p role="status" className="quiet-success">
                {said ? (
                  <>
                    <span aria-hidden="true">✓</span> {said}
                  </>
                ) : null}
              </p>
              <Provenance>{f.spread(rate(report.scenario_spread, locale))}</Provenance>
            </Panel>
          );
        }}
      </Loaded>
    </Section>
  );
}

function History() {
  const locale = useLocale();
  const query = useRead('fi.score.history', fiScoreHistory);
  return (
    <Section label={f.history}>
      <Loaded query={query}>
        {(data) =>
          data.history.length ? (
            <Panel>
              <p className="section-help">{f.historyHelp}</p>
              <Table<FiScoreSnapshot>
                caption={f.history}
                captionHidden
                rows={data.history}
                rowKey={(h) => `${h.created_at}-${String(h.score)}`}
                columns={[
                  { key: 'when', header: f.when, label: f.when, render: (h) => displayDate(h.created_at, locale) },
                  { key: 'score', header: f.score, label: f.score, align: 'end', render: (h) => formatDecimal(h.score, { locale }) },
                  {
                    key: 'nw',
                    header: `${f.netWorth} (${data.currency})`,
                    label: f.netWorth,
                    align: 'end',
                    render: (h) => <Money amount={h.net_worth} currency={data.currency} variant="table" />,
                  },
                ]}
              />
            </Panel>
          ) : (
            <Empty>{f.noHistory}</Empty>
          )
        }
      </Loaded>
    </Section>
  );
}

export function Fi() {
  const score = useRead('fi.score.get', fiScoreGet);
  return (
    <Page title={f.title} description={f.description}>
      <Grid>
        <Section label={f.where}>
          <Loaded query={score}>{(data) => <Where score={data} />}</Loaded>
        </Section>
        <Projections />
        <Assumptions />
        <Section label={f.components} wide>
          <Loaded query={score}>{(data) => <Components score={data} />}</Loaded>
        </Section>
        <History />
      </Grid>
    </Page>
  );
}

export default Fi;
