/**
 * Home: `salli status` as a page (docs/design/console.md, section 5). Key
 * figures first (net worth, safe to spend, the month so far, the FI
 * score), then net worth by month with a month to read off, safe to spend
 * line by line, what needs attention (what Salli noticed, what's coming
 * up, decisions due for review), spending this month by account, and the
 * FI score's parts. Every figure is the API's, shown exactly, with where
 * it came from; the page computes nothing (a bar's length comes from the
 * geometry module, for pixels only). Each part loads, fails and retries
 * on its own, as `salli status` reports a part it couldn't read. Home
 * writes nothing.
 */
import {
  compareAmounts,
  decisionsReviewsDue,
  fiScoreGet,
  formatDecimal,
  formatRatio,
  insightsNetWorth,
  insightsSafeToSpend,
  insightsSignals,
  ledgerIncomeStatement,
  remindersList,
  reportsBalanceSheet,
  type FinanceSignal,
  type NetWorthByMonth,
  type Reminder,
} from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useState } from 'react';
import { useRead } from '../../api';
import { Bar } from '../../kit/chart/Bar';
import { amountScale } from '../../kit/chart/geometry';
import { Chip, Status } from '../../kit/chips';
import { displayDate, displayMonth, displayRange, isoDate, monthToDate } from '../../kit/dates';
import { KeyFigure, KeyFigures } from '../../kit/figures';
import { Icon } from '../../kit/Icon';
import { Empty, Grid, Loaded, Page, Panel, Provenance, Row, Rows, Section } from '../../kit/layout';
import { Money } from '../../kit/Money';
import { ThinkItThrough } from '../../kit/ThinkItThrough';
import { useLocale } from '../../preferences';
import { strings } from '../../strings';
import { NetWorthChart } from './NetWorthChart';

const s = strings.home;

/** The key figures: net worth, safe to spend, the month so far, the FI score. */
function Figures({ today, now }: { today: string; now: Date }) {
  const locale = useLocale();
  const period = monthToDate(now);
  const sheet = useRead('reports.balanceSheet', reportsBalanceSheet);
  const safe = useRead('insights.safeToSpend', insightsSafeToSpend);
  const month = useRead('ledger.incomeStatement', ledgerIncomeStatement, { query: { from_date: period.from, to_date: period.to } });
  const fi = useRead('fi.score.get', fiScoreGet);
  return (
    <KeyFigures>
      <KeyFigure
        label={s.netWorth}
        note={
          sheet.data ? (
            <>
              <span>
                {s.assets} <Money amount={sheet.data.total_assets} currency={sheet.data.currency} variant="table" withCode /> · {s.liabilities}{' '}
                <Money amount={sheet.data.total_liabilities} currency={sheet.data.currency} variant="table" withCode />
              </span>
              <span>{s.asOfToday(displayDate(today, locale))}</span>
            </>
          ) : null
        }
      >
        <Loaded query={sheet} what={s.loads.netWorth}>
          {(data) => <Money amount={data.net_worth} currency={data.currency} variant="figure" />}
        </Loaded>
      </KeyFigure>
      <KeyFigure label={s.safeToSpend} note={safe.data ? s.safeUntil(displayDate(safe.data.until, locale)) : null}>
        <Loaded query={safe} what={s.loads.safeToSpend}>
          {(data) => <Money amount={data.amount} currency={data.currency} variant="figure" />}
        </Loaded>
      </KeyFigure>
      <KeyFigure
        label={s.thisMonth(displayMonth(period.month, locale, 'long'))}
        note={
          month.data ? (
            <>
              <span>
                {s.income} <Money amount={month.data.total_income} currency={month.data.currency} variant="table" withCode /> · {s.spending}{' '}
                <Money amount={month.data.total_expenses} currency={month.data.currency} variant="table" withCode />
              </span>
              <span>{s.thisMonthRange(displayRange(month.data.from_date, month.data.to_date, locale))}</span>
            </>
          ) : null
        }
      >
        <Loaded query={month} what={s.loads.month}>
          {(data) => (
            <>
              <span className="sr-only">{s.netIncome} </span>
              <Money amount={data.net_income} currency={data.currency} variant="figure" />
            </>
          )}
        </Loaded>
      </KeyFigure>
      <KeyFigure
        label={s.fi}
        note={
          fi.data ? (
            <>
              <span>{s.fiNote(s.fiGrade(fi.data.grade))}</span>
              {fi.data.projected_fi_month ? (
                <span>
                  {s.fiBy} {displayMonth(fi.data.projected_fi_month, locale)}
                </span>
              ) : null}
            </>
          ) : null
        }
      >
        <Loaded query={fi} what={s.loads.fi}>
          {(data) => <span className="figure-number">{formatDecimal(data.overall_score, { locale })}</span>}
        </Loaded>
      </KeyFigure>
    </KeyFigures>
  );
}

/** The month a readout shows: picked from the list, or by a click on the chart. */
function MonthReadout({ data, selected, onSelect }: { data: NetWorthByMonth; selected: number; onSelect: (index: number) => void }) {
  const locale = useLocale();
  const point = data.points[selected];
  if (!point) return null;
  const code = data.currency.toUpperCase();
  return (
    <div className="readout">
      <label>
        <span className="sr-only">{s.pickMonth}</span>
        <select className="pager-select" value={point.month} onChange={(event) => onSelect(data.points.findIndex((p) => p.month === event.target.value))}>
          {data.points.map((p) => (
            <option key={p.month} value={p.month}>
              {displayMonth(p.month, locale)}
            </option>
          ))}
        </select>
      </label>
      <strong>
        <Money amount={point.net_worth} currency={code} />
      </strong>
      <span className="muted">
        {s.assets} <Money amount={point.assets} currency={code} variant="table" />
      </span>
      <span className="muted">
        {s.liabilities} <Money amount={point.liabilities} currency={code} variant="table" />
      </span>
    </div>
  );
}

function NetWorthOverTime() {
  const query = useRead('insights.netWorth', insightsNetWorth, { query: { months: 12 } });
  const [picked, setPicked] = useState<number | null>(null);
  return (
    <Section label={s.netWorthOverTime} wide>
      <Loaded query={query} lines={6} what={s.loads.netWorthOverTime}>
        {(data) => {
          const selected = picked ?? data.points.length - 1;
          return (
            <Panel>
              <MonthReadout data={data} selected={selected} onSelect={setPicked} />
              <NetWorthChart data={data} selected={selected} onSelect={setPicked} />
            </Panel>
          );
        }}
      </Loaded>
    </Section>
  );
}

/** Safe to spend, line by line: cash today, what is committed before the next income, the server's figure under a double rule. */
function SafeToSpend() {
  const locale = useLocale();
  const query = useRead('insights.safeToSpend', insightsSafeToSpend);
  return (
    <Section label={s.safeLines}>
      <Loaded query={query} what={s.loads.safeToSpend}>
        {(safe) => (
          <Panel>
            <p className="section-help">{s.safeUntil(displayDate(safe.until, locale))}</p>
            <Rows>
              <Row label={s.cashToday}>
                <Money amount={safe.cash_today} currency={safe.currency} variant="table" withCode />
              </Row>
              {safe.committed.map((flow, i) => (
                <Row key={`${flow.date}-${i}`} label={`${flow.description}, ${displayDate(flow.date, locale)}`}>
                  <Money amount={flow.amount} currency={flow.currency} variant="table" withCode />
                </Row>
              ))}
              <Row label={s.safeTotal} total>
                <Money amount={safe.amount} currency={safe.currency} variant="table" withCode />
              </Row>
            </Rows>
            {safe.committed.length ? null : <Provenance>{s.nothingCommitted}</Provenance>}
            {safe.next_income ? (
              <Rows>
                <Row label={`${s.nextIncome}: ${safe.next_income.description}, ${displayDate(safe.next_income.date, locale)}`}>
                  <Money amount={safe.next_income.amount} currency={safe.next_income.currency} variant="table" withCode />
                </Row>
              </Rows>
            ) : null}
            {(safe.fx ?? []).map((rate) =>
              rate.rate ? (
                <Provenance key={rate.currency}>{s.rate(rate.currency, rate.rate, rate.source ?? '', displayDate(rate.as_of, locale))}</Provenance>
              ) : null,
            )}
            {safe.notes.map((note, i) => (
              <Provenance key={i}>{note}</Provenance>
            ))}
          </Panel>
        )}
      </Loaded>
    </Section>
  );
}

function SignalItem({ signal }: { signal: FinanceSignal }) {
  const locale = useLocale();
  return (
    <li>
      <span className={signal.severity === 'high' ? 'waiting-icon waiting-icon-warn' : 'waiting-icon'} aria-hidden="true">
        {signal.severity === 'high' ? '!' : <Icon name="attention" small />}
      </span>
      <div className="waiting-body">
        <p className="signal-title">
          {signal.title}
          <span className="sr-only"> ({s.severity[signal.severity] ?? signal.severity})</span>
        </p>
        <p className="signal-detail">{signal.detail}</p>
        {signal.amount && signal.currency ? (
          <p className="waiting-meta">
            <Money amount={signal.amount} currency={signal.currency} />
            {signal.date ? ` · ${displayDate(signal.date, locale)}` : ''}
          </p>
        ) : null}
      </div>
    </li>
  );
}

/** "budget_overspend" → "Budget overspend", as `salli status` shows a reminder's kind. */
function humanize(kind: string): string {
  const text = kind.replace(/_/g, ' ').trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** What needs attention: what Salli noticed, what is coming up, and decisions due for review. */
function Attention({ today }: { today: string }) {
  const locale = useLocale();
  const signals = useRead('insights.signals', insightsSignals);
  const reminders = useRead('reminders.list', remindersList, { query: { status: 'pending' } });
  const reviews = useRead('decisions.reviews.due', decisionsReviewsDue);
  return (
    <Section label={s.attention}>
      <h3 className="subhead">{s.noticed}</h3>
      <Loaded query={signals} what={s.loads.noticed}>
        {({ signals: list }) =>
          list.length ? (
            <ul className="waiting">
              {list.map((signal, i) => (
                <SignalItem key={`${signal.kind}-${i}`} signal={signal} />
              ))}
            </ul>
          ) : (
            <Empty>{s.nothingNeedsAttention}</Empty>
          )
        }
      </Loaded>
      <h3 className="subhead">{s.comingUp}</h3>
      <Loaded query={reminders} what={s.loads.comingUp}>
        {({ reminders: list }) => {
          const pending = list.filter((r: Reminder) => r.status === 'pending').sort((a, b) => a.due_date.localeCompare(b.due_date));
          if (!pending.length) return <Empty>{s.nothingDue}</Empty>;
          return (
            <ul className="waiting">
              {pending.map((reminder) => {
                const overdue = reminder.due_date < today;
                return (
                  <li key={reminder.id}>
                    <span className="waiting-icon" aria-hidden="true">
                      <Icon name="attention" small />
                    </span>
                    <div className="waiting-body">
                      <p className="signal-title">{humanize(reminder.kind)}</p>
                      <p className="waiting-meta">
                        {overdue ? <Status kind="warn">{s.overdue}</Status> : null}
                        <span>{s.due(displayDate(reminder.due_date, locale))}</span>
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          );
        }}
      </Loaded>
      <h3 className="subhead">{s.reviews}</h3>
      <Loaded query={reviews} what={s.loads.reviews}>
        {({ reviews: list }) =>
          list.length ? (
            <ul className="waiting">
              {list.map((review) => (
                <li key={review.id}>
                  <span className="waiting-icon" aria-hidden="true">
                    <Icon name="decide" small />
                  </span>
                  <div className="waiting-body">
                    <p className="signal-title">
                      <Link to={`/decide/journal/${encodeURIComponent(review.id)}`}>{review.question}</Link>
                    </p>
                    <p className="waiting-meta">
                      <span>{s.reviewDue(displayDate(review.review_on, locale))}</span>
                      <span>· {review.chosen}</span>
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>{s.noReviews}</Empty>
          )
        }
      </Loaded>
    </Section>
  );
}

/** Spending this month by account, the largest first, each with a bar; the server's total under a double rule. */
function Spending({ now }: { now: Date }) {
  const locale = useLocale();
  const period = monthToDate(now);
  const query = useRead('ledger.incomeStatement', ledgerIncomeStatement, { query: { from_date: period.from, to_date: period.to } });
  return (
    <Section label={s.spentIn(displayMonth(period.month, locale, 'long'))}>
      <Loaded query={query} what={s.loads.spending}>
        {(statement) => {
          const spending = statement.lines.filter((line) => line.type === 'expense').sort((a, b) => compareAmounts(b.amount, a.amount));
          if (!spending.length) return <Empty>{s.nothingSpent}</Empty>;
          const x = amountScale(
            spending.map((line) => line.amount),
            [0, 100],
          );
          return (
            <Panel>
              <div className="bar-rows">
                {spending.map((line) => (
                  <div key={line.account_id} className="bar-row">
                    <span className="bar-row-label">{line.name}</span>
                    <Bar length={x(line.amount)} />
                    <Money amount={line.amount} currency={statement.currency} variant="table" withCode />
                  </div>
                ))}
                <div className="bar-row bar-row-total">
                  <span>{s.spending}</span>
                  <Money amount={statement.total_expenses} currency={statement.currency} variant="table" withCode />
                </div>
              </div>
              <Provenance>{s.thisMonthRange(displayRange(statement.from_date, statement.to_date, locale))}</Provenance>
            </Panel>
          );
        }}
      </Loaded>
    </Section>
  );
}

/** The FI score's parts, each with its bar, and where it stands. */
function FiParts() {
  const locale = useLocale();
  const query = useRead('fi.score.get', fiScoreGet);
  return (
    <Section label={s.fiParts}>
      <Loaded query={query} what={s.loads.fi}>
        {(fi) => {
          const x = amountScale([...fi.components.map((c) => c.score), '100'], [0, 100]);
          return (
            <Panel>
              {fi.components.length ? (
                <div className="bar-rows">
                  {fi.components.map((c) => (
                    <div key={c.key} className="bar-row">
                      <span className="bar-row-label">
                        {c.label}
                        {c.detail ? <span className="bar-row-detail">{c.detail}</span> : null}
                      </span>
                      <Bar length={x(c.score)} alt />
                      <span className="bar-row-figure">{formatDecimal(c.score, { locale })}</span>
                    </div>
                  ))}
                </div>
              ) : null}
              <p>{s.fiProgress(formatRatio(fi.progress_to_fi, { locale }))}</p>
              <Rows>
                <Row label={s.savingsRate}>{s.savingsRateOf(formatRatio(fi.savings_rate, { locale }))}</Row>
                {fi.projected_fi_month ? <Row label={s.fiBy}>{displayMonth(fi.projected_fi_month, locale)}</Row> : null}
              </Rows>
              {fi.assumptions ? (
                <Provenance>
                  {fi.assumptions.status === 'placeholder' ? <span className="placeholder-tag">{s.placeholders}</span> : s.ownAssumptions}{' '}
                  {fi.assumptions.message}
                  {fi.assumptions.status === 'placeholder' ? (
                    <>
                      {' '}
                      <Link to="/fi" hash="assumptions">
                        {s.setOwn}
                      </Link>
                    </>
                  ) : null}
                </Provenance>
              ) : null}
              {fi.as_of ? <Provenance>{s.fiScoreAsOf(displayDate(fi.as_of, locale))}</Provenance> : null}
              <p>
                <Link to="/fi" className="strong-link">
                  {s.fiMore}
                </Link>
              </p>
            </Panel>
          );
        }}
      </Loaded>
    </Section>
  );
}

export function Home() {
  const locale = useLocale();
  const now = new Date();
  const today = isoDate(now);
  const sheet = useRead('reports.balanceSheet', reportsBalanceSheet);
  return (
    <Page
      title={s.title}
      description={s.description}
      facts={
        <>
          <Chip>{s.asOf(displayDate(today, locale))}</Chip>
          {sheet.data ? <Chip mono>{sheet.data.currency.toUpperCase()}</Chip> : null}
        </>
      }
      actions={
        <>
          <ThinkItThrough prompt={s.prompt(today)} />
          <Link to="/decide" className="button button-primary">
            <Icon name="decide" />
            {s.thinkDecision}
          </Link>
        </>
      }
    >
      <Figures today={today} now={now} />
      <Grid>
        <NetWorthOverTime />
        <SafeToSpend />
        <Attention today={today} />
        <Spending now={now} />
        <FiParts />
      </Grid>
    </Page>
  );
}

export default Home;
