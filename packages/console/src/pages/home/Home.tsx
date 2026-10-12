/**
 * Home: `salli status` as a page (docs/design/console.md, section 5). Net
 * worth, safe to spend, the month so far, the FI score and date, what needs
 * attention, what's coming up, decisions due for review and net worth over
 * time. Every figure is the API's, shown exactly, with where it came from;
 * the page computes nothing. Each section loads, fails and retries on its
 * own, as `salli status` reports a part it couldn't read.
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
  type Reminder,
} from '@leafmonkeylabs/salli-sdk';
import type { UseQueryResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useRead } from '../../api';
import { displayDate, displayMonth, displayRange, isoDate, monthToDate } from '../../kit/dates';
import { Empty, Grid, Loading, Page, Panel, Provenance, Row, Rows, Section } from '../../kit/layout';
import { Money } from '../../kit/Money';
import { ProblemView } from '../../kit/Problem';
import { ThinkItThrough } from '../../kit/ThinkItThrough';
import { useLocale } from '../../preferences';
import { strings } from '../../strings';
import { NetWorthChart } from './NetWorthChart';

const s = strings.home;

/** A section's query: loading, its problem with a retry, or its content. */
function Loaded<T>({ query, children, lines }: { query: UseQueryResult<T, Error>; children: (data: T) => ReactNode; lines?: number }) {
  if (query.isPending) return <Loading {...(lines ? { lines } : {})} />;
  if (query.isError) return <ProblemView error={query.error} compact onRetry={() => void query.refetch()} />;
  return <>{children(query.data)}</>;
}

function NetWorth({ today }: { today: string }) {
  const locale = useLocale();
  const query = useRead('reports.balanceSheet', reportsBalanceSheet);
  return (
    <Section label={s.netWorth}>
      <Loaded query={query}>
        {(sheet) => (
          <Panel>
            <p className="figure">
              <Money amount={sheet.net_worth} currency={sheet.currency} variant="figure" />
            </p>
            <Rows>
              <Row label={s.assets}>
                <Money amount={sheet.total_assets} currency={sheet.currency} variant="table" withCode />
              </Row>
              <Row label={s.liabilities}>
                <Money amount={sheet.total_liabilities} currency={sheet.currency} variant="table" withCode />
              </Row>
            </Rows>
            <Provenance>{s.asOfToday(displayDate(today, locale))}</Provenance>
          </Panel>
        )}
      </Loaded>
    </Section>
  );
}

function SafeToSpend() {
  const locale = useLocale();
  const query = useRead('insights.safeToSpend', insightsSafeToSpend);
  return (
    <Section label={s.safeToSpend}>
      <Loaded query={query}>
        {(safe) => (
          <Panel>
            <p className="figure">
              <Money amount={safe.amount} currency={safe.currency} variant="figure" />{' '}
              <span className="figure-note">{s.safeUntil(displayDate(safe.until, locale))}</span>
            </p>
            <Rows>
              <Row label={s.cashToday}>
                <Money amount={safe.cash_today} currency={safe.currency} variant="table" withCode />
              </Row>
              {safe.next_income ? (
                <Row label={`${s.nextIncome}, ${displayDate(safe.next_income.date, locale)}`}>
                  <Money amount={safe.next_income.amount} currency={safe.next_income.currency} variant="table" withCode />
                </Row>
              ) : null}
            </Rows>
            {safe.committed.length ? (
              <details className="disclosure">
                <summary>{s.committed}</summary>
                <Rows>
                  {safe.committed.map((flow, i) => (
                    <Row key={`${flow.date}-${i}`} label={`${displayDate(flow.date, locale)} · ${flow.description}`}>
                      <Money amount={flow.amount} currency={flow.currency} variant="table" withCode />
                    </Row>
                  ))}
                </Rows>
              </details>
            ) : (
              <Provenance>{s.nothingCommitted}</Provenance>
            )}
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

function ThisMonth({ now }: { now: Date }) {
  const locale = useLocale();
  const period = monthToDate(now);
  const query = useRead('ledger.incomeStatement', ledgerIncomeStatement, { query: { from_date: period.from, to_date: period.to } });
  return (
    <Section label={s.thisMonth(displayMonth(period.month, locale, 'long'))}>
      <Loaded query={query}>
        {(statement) => {
          if (!statement.lines.length) return <Empty>{s.nothingThisMonth}</Empty>;
          const spending = statement.lines.filter((line) => line.type === 'expense').sort((a, b) => compareAmounts(b.amount, a.amount));
          return (
            <Panel>
              <Rows>
                <Row label={s.income}>
                  <Money amount={statement.total_income} currency={statement.currency} variant="table" withCode />
                </Row>
                <Row label={s.spending}>
                  <Money amount={statement.total_expenses} currency={statement.currency} variant="table" withCode />
                </Row>
                <Row label={s.netIncome} total>
                  <Money amount={statement.net_income} currency={statement.currency} variant="table" withCode />
                </Row>
              </Rows>
              {spending.length ? (
                <>
                  <p className="subhead">{s.mostOn}</p>
                  <Rows>
                    {spending.slice(0, 3).map((line) => (
                      <Row key={line.account_id} label={line.name} indent>
                        <Money amount={line.amount} currency={statement.currency} variant="table" withCode />
                      </Row>
                    ))}
                  </Rows>
                </>
              ) : null}
              <Provenance>{s.thisMonthRange(displayRange(statement.from_date, statement.to_date, locale))}</Provenance>
            </Panel>
          );
        }}
      </Loaded>
    </Section>
  );
}

function Fi() {
  const locale = useLocale();
  const query = useRead('fi.score.get', fiScoreGet);
  return (
    <Section label={s.fi}>
      <Loaded query={query}>
        {(fi) => (
          <Panel>
            <p className="figure">
              <span className="figure-number">{formatDecimal(fi.overall_score, { locale })}</span>{' '}
              <span className="figure-note">
                {s.fiScore} · {s.fiGrade(fi.grade)}
              </span>
            </p>
            <p>{s.fiProgress(formatRatio(fi.progress_to_fi, { locale }))}</p>
            <Rows>
              <Row label={s.savingsRate}>{s.savingsRateOf(formatRatio(fi.savings_rate, { locale }))}</Row>
              {fi.projected_fi_month ? <Row label={s.fiBy}>{displayMonth(fi.projected_fi_month, locale)}</Row> : null}
            </Rows>
            {fi.assumptions ? (
              <Provenance>
                {fi.assumptions.status === 'placeholder' ? <span className="placeholder-tag">{s.placeholders}</span> : s.ownAssumptions}{' '}
                {fi.assumptions.message}
              </Provenance>
            ) : null}
            {fi.as_of ? <Provenance>{s.fiScoreAsOf(displayDate(fi.as_of, locale))}</Provenance> : null}
          </Panel>
        )}
      </Loaded>
    </Section>
  );
}

function SignalItem({ signal }: { signal: FinanceSignal }) {
  const locale = useLocale();
  return (
    <li className="signal">
      <p className="signal-title">
        {signal.severity === 'high' ? (
          <span className="warn-mark" aria-hidden="true">
            !
          </span>
        ) : null}{' '}
        {signal.title}
        <span className="sr-only">
          {' '}
          ({s.severity[signal.severity] ?? signal.severity})
        </span>
      </p>
      <p className="signal-detail">{signal.detail}</p>
      {signal.amount && signal.currency ? (
        <p>
          <Money amount={signal.amount} currency={signal.currency} />
          {signal.date ? ` · ${displayDate(signal.date, locale)}` : ''}
        </p>
      ) : null}
    </li>
  );
}

function Attention() {
  const query = useRead('insights.signals', insightsSignals);
  return (
    <Section label={s.attention}>
      <Loaded query={query}>
        {({ signals }) =>
          signals.length ? (
            <ul className="list">
              {signals.map((signal, i) => (
                <SignalItem key={`${signal.kind}-${i}`} signal={signal} />
              ))}
            </ul>
          ) : (
            <Empty>{s.nothingNeedsAttention}</Empty>
          )
        }
      </Loaded>
    </Section>
  );
}

/** "budget_overspend" → "Budget overspend", as `salli status` shows a reminder's kind. */
function humanize(kind: string): string {
  const text = kind.replace(/_/g, ' ').trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function ComingUp({ today }: { today: string }) {
  const locale = useLocale();
  const query = useRead('reminders.list', remindersList, { query: { status: 'pending' } });
  return (
    <Section label={s.comingUp}>
      <Loaded query={query}>
        {({ reminders }) => {
          const pending = reminders.filter((r: Reminder) => r.status === 'pending').sort((a, b) => a.due_date.localeCompare(b.due_date));
          if (!pending.length) return <Empty>{s.nothingDue}</Empty>;
          return (
            <ul className="list">
              {pending.map((reminder) => {
                const overdue = reminder.due_date < today;
                return (
                  <li key={reminder.id} className="dated">
                    <span className={overdue ? 'dated-date negative' : 'dated-date'}>{displayDate(reminder.due_date, locale)}</span>
                    <span>
                      {humanize(reminder.kind)}
                      {overdue ? <span className="tag tag-warn"> {s.overdue}</span> : null}
                    </span>
                  </li>
                );
              })}
            </ul>
          );
        }}
      </Loaded>
    </Section>
  );
}

function Reviews() {
  const locale = useLocale();
  const query = useRead('decisions.reviews.due', decisionsReviewsDue);
  return (
    <Section label={s.reviews}>
      <Loaded query={query}>
        {({ reviews }) =>
          reviews.length ? (
            <ul className="list">
              {reviews.map((review) => (
                <li key={review.id} className="dated">
                  <span className="dated-date">{displayDate(review.review_on, locale)}</span>
                  <span>
                    {review.question} <span className="muted">· {review.chosen}</span>
                  </span>
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

function NetWorthOverTime() {
  const query = useRead('insights.netWorth', insightsNetWorth, { query: { months: 12 } });
  return (
    <Section label={s.netWorthOverTime} wide>
      <Loaded query={query} lines={6}>
        {(data) => (
          <Panel>
            <NetWorthChart data={data} />
          </Panel>
        )}
      </Loaded>
    </Section>
  );
}

export function Home() {
  const now = new Date();
  const today = isoDate(now);
  return (
    <Page title={s.title} description={s.description} actions={<ThinkItThrough prompt={s.prompt(today)} />}>
      <Grid>
        <NetWorth today={today} />
        <SafeToSpend />
        <ThisMonth now={now} />
        <Fi />
        <Attention />
        <ComingUp today={today} />
        <NetWorthOverTime />
        <Reviews />
      </Grid>
    </Page>
  );
}

export default Home;
