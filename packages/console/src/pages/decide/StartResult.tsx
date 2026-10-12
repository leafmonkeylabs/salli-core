/**
 * What `decisions.start` returns, laid out (docs/templates.md, "What starting
 * a decision returns"): the options Salli built and what each is, the
 * answers as used with where each came from, the comparison (side by side,
 * the trade, the sensitivity, the break-evens), the emergency fund's cover
 * or rent-or-buy's level reading, the principles kept and broken, the tax
 * and every placeholder. Stores nothing, and ranks nothing.
 */
import type { DecisionStart, DecisionTemplate } from '@leafmonkeylabs/salli-sdk';
import { displayDate } from '../../kit/dates';
import { Panel, Row, Rows, Section } from '../../kit/layout';
import { Money } from '../../kit/Money';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';
import { Basis } from './Basis';
import { Checks } from './Checks';
import { BreakEvens, Sensitivity, SideBySide, Trade } from './Comparison';
import { monthsOfSpending, monthText } from './format';

const l = labStrings;
const t = l.templates;

function shown(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

function Cover({ data }: { data: DecisionStart }) {
  const locale = useLocale();
  const cover = data.cover;
  if (!cover) return null;
  const rows = [{ option: l.baselineColumn, month: cover.baseline.month, months: cover.baseline.months }, ...cover.options];
  return (
    <Section label={t.cover} full>
      <Panel>
        <Rows>
          <Row label={t.coverTarget(monthsOfSpending(cover.target_months, locale), cover.basis === 'essential' ? t.essentialSpending : t.allSpending)}>
            {cover.target ? <Money amount={cover.target} currency={data.currency} variant="table" withCode /> : '—'}
          </Row>
          <Row label={t.coverNow}>{t.coverNowMonths(monthsOfSpending(cover.now, locale))}</Row>
        </Rows>
        <Table
          caption={t.cover}
          captionHidden
          rows={rows}
          rowKey={(r) => r.option}
          columns={[
            { key: 'option', header: l.compare.optionColumn, label: l.compare.optionColumn, render: (r) => r.option },
            { key: 'month', header: t.coverReached, label: t.coverReached, align: 'end', render: (r) => monthText(r.month, locale) },
            { key: 'months', header: t.coverMonths, label: t.coverMonths, align: 'end', render: (r) => (r.months === null ? '—' : String(r.months)) },
          ]}
        />
      </Panel>
    </Section>
  );
}

function Level({ data }: { data: DecisionStart }) {
  const locale = useLocale();
  const level = data.level;
  if (!level) return null;
  const code = data.currency.toUpperCase();
  const to = monthText(level.to, locale);
  return (
    <Section label={t.level} full>
      <Panel>
        <p>{t.levelCaption(level.against, monthText(level.from, locale), to)}</p>
        <Table
          caption={t.level}
          captionHidden
          rows={level.options}
          rowKey={(o) => o.option}
          columns={[
            { key: 'option', header: l.compare.optionColumn, label: l.compare.optionColumn, render: (o) => o.option },
            { key: 'month', header: t.levelFrom, label: t.levelFrom, align: 'end', render: (o) => (o.month ? monthText(o.month, locale) : t.notLevel(to)) },
            { key: 'months', header: t.levelMonths, label: t.levelMonths, align: 'end', render: (o) => (o.months === null ? '—' : String(o.months)) },
            {
              key: 'then',
              header: `${t.levelThen} (${code})`,
              label: t.levelThen,
              align: 'end',
              render: (o) => <Money amount={o.net_worth_then} currency={code} variant="table" signed />,
            },
            {
              key: 'horizon',
              header: `${t.levelAtHorizon(to)} (${code})`,
              label: t.levelAtHorizon(to),
              align: 'end',
              render: (o) => <Money amount={o.net_worth_at_horizon} currency={code} variant="table" signed />,
            },
          ]}
        />
      </Panel>
    </Section>
  );
}

export function StartResult({ data, template }: { data: DecisionStart; template: DecisionTemplate }) {
  const locale = useLocale();
  const comparison = data.comparison;
  const prompts = new Map(template.questions.map((q) => [q.id, q.prompt]));
  const tax = comparison.options.find((o) => o.tax.status === 'not_computed')?.tax ?? comparison.options.find((o) => o.tax.status === 'computed')?.tax;
  const asOf = l.basis.asOfHorizon(displayDate(data.as_of, locale), data.currency, l.figure.years(data.horizon_years));
  return (
    <div className="grid">
      <Section label={t.options} wide>
        <Panel>
          <p className="section-help">{t.optionsHelp}</p>
          <p>
            <span className="subhead">{t.question}: </span>
            {data.question}
          </p>
          <ul className="list">
            {data.options.map((o) => (
              <li key={o.label}>
                <p className="signal-title">{o.label}</p>
                <p className="muted">{o.describes}</p>
              </li>
            ))}
          </ul>
        </Panel>
      </Section>
      <Section label={l.basis.label}>
        <Basis asOf={asOf} placeholders={data.placeholders} isStale={data.is_stale} dataAsOf={data.data_as_of} tax={tax} notes={data.notes} />
      </Section>
      <Section label={l.compare.sideBySide} full>
        <Panel>
          <p className="section-help">{l.compare.sideBySideHelp}</p>
          <SideBySide runs={comparison.options} labels={comparison.labels} caption={l.compare.sideBySide} />
        </Panel>
      </Section>
      <Cover data={data} />
      <Level data={data} />
      <Section label={l.compare.trade} full>
        <Panel>
          <Trade data={comparison} />
        </Panel>
      </Section>
      <Section label={l.compare.sensitivity} full>
        <Panel>
          <Sensitivity data={comparison} />
        </Panel>
      </Section>
      <Section label={l.compare.breakEvens} full>
        <Panel>
          <BreakEvens items={comparison.break_evens} currency={data.currency} />
        </Panel>
      </Section>
      <Section label={l.checks.title} full>
        <Panel>
          <p className="section-help">{l.checks.help}</p>
          <Checks
            principles={data.principles.principles}
            columns={[{ label: l.baselineColumn, results: data.principles.baseline.results }, ...data.principles.options.map((o) => ({ label: o.label, results: o.results }))]}
          />
        </Panel>
      </Section>
      <Section label={t.used} full>
        <Panel>
          <Table
            caption={t.used}
            captionHidden
            rows={data.answers}
            rowKey={(a) => a.id}
            columns={[
              { key: 'answer', header: t.answer, label: t.answer, render: (a) => prompts.get(a.id) ?? a.id },
              { key: 'value', header: t.value, label: t.value, render: (a) => <span className="answer-value">{shown(a.value)}</span> },
              {
                key: 'from',
                header: t.from,
                label: t.from,
                render: (a) =>
                  a.source === 'placeholder' ? (
                    <span className="placeholder-tag">{a.note ?? t.sources.placeholder}</span>
                  ) : a.source === 'given' ? (
                    t.sources.given
                  ) : (
                    (a.note ?? t.sources[a.source] ?? a.source)
                  ),
              },
            ]}
          />
        </Panel>
      </Section>
      <p className="provenance section-full">{l.compare.noRanking}</p>
    </div>
  );
}
