/**
 * Attention (docs/design/console.md, section 5; `salli insights signals`,
 * `salli reminders`): what Salli has noticed, in the order it gives them,
 * each with its kind, its detail and where to look (the page that shows
 * it, or the decision in the journal); then the reminders, overdue, due
 * today and coming up, each one marked done (`reminders.markDone`) or
 * deleted (`reminders.delete`) after a confirmation that says what Salli
 * will do. A decision's review reminder opens the decision in the journal.
 */
import { insightsSignals, remindersDelete, remindersList, remindersMarkDone, type FinanceSignal, type Reminder } from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useState } from 'react';
import { useRead, useWrite } from '../../api';
import { displayDate, isoDate } from '../../kit/dates';
import { Button, Confirm } from '../../kit/forms';
import { Empty, Grid, Loaded, Page, Panel, Section } from '../../kit/layout';
import { Money } from '../../kit/Money';
import { ProblemView } from '../../kit/Problem';
import { useLocale } from '../../preferences';
import { whereStrings } from '../../where-strings';

const t = whereStrings.attention;
const INVALIDATE = ['reminders.list', 'insights.signals'];

/** Where a signal points: a part of Cash, or the decision it names in the journal. */
function actionPath(signal: FinanceSignal): string | undefined {
  switch (signal.action) {
    case 'see_forecast':
      return '/cash#forecast';
    case 'see_recurring':
      return '/cash#recurring';
    case 'see_spending':
      return '/cash#spending';
    case 'see_cash_flow':
      return '/cash#cash-flow';
    case 'review_decision':
      return signal.refs[0] ? `/decide/journal/${encodeURIComponent(signal.refs[0])}` : '/decide/journal';
    default:
      return undefined;
  }
}

function SignalItem({ signal }: { signal: FinanceSignal }) {
  const locale = useLocale();
  const path = actionPath(signal);
  return (
    <li className="signal">
      <p className="signal-title">
        {signal.severity === 'high' ? (
          <span className="warn-mark" aria-hidden="true">
            !
          </span>
        ) : null}{' '}
        {signal.title} <span className={signal.severity === 'info' ? 'tag' : 'tag tag-warn'}>{t.severity[signal.severity] ?? signal.severity}</span>
      </p>
      <p className="signal-detail">{signal.detail}</p>
      {signal.amount && signal.currency ? (
        <p>
          <Money amount={signal.amount} currency={signal.currency} />
          {signal.date ? ` · ${displayDate(signal.date, locale)}` : ''}
        </p>
      ) : null}
      <p>{path ? <Link to={path}>{t.actions[signal.action] ?? signal.action}</Link> : <span className="muted">{t.reviewStatements}</span>}</p>
    </li>
  );
}

function Signals() {
  const query = useRead('insights.signals', insightsSignals);
  return (
    <Section label={t.signals} full>
      <Panel>
        <Loaded query={query}>
          {({ signals }) =>
            signals.length ? (
              <>
                <p className="section-help">{t.signalsHelp}</p>
                <ul className="list">
                  {signals.map((signal, i) => (
                    <SignalItem key={`${signal.kind}-${i}`} signal={signal} />
                  ))}
                </ul>
              </>
            ) : (
              <Empty>{t.noSignals}</Empty>
            )
          }
        </Loaded>
      </Panel>
    </Section>
  );
}

type Ask = { kind: 'done' | 'delete'; reminder: Reminder } | null;

function ReminderItem({ reminder, today, onAsk }: { reminder: Reminder; today: string; onAsk: (ask: Ask) => void }) {
  const locale = useLocale();
  const overdue = reminder.status === 'pending' && reminder.due_date < today;
  const decision = reminder.source_domain === 'decision' && reminder.source_id ? reminder.source_id : null;
  return (
    <li className="dated reminder">
      <span className={overdue ? 'dated-date negative' : 'dated-date'}>{displayDate(reminder.due_date, locale)}</span>
      <span className="reminder-body">
        <span>
          {reminder.kind}
          {reminder.severity ? <span className="tag"> {t.alert[reminder.severity] ?? reminder.severity}</span> : null}
        </span>
        {decision ? (
          <Link to={`/decide/journal/${encodeURIComponent(decision)}`} className="reminder-link">
            {t.openDecision}
          </Link>
        ) : null}
        <span className="reminder-actions">
          {reminder.status === 'pending' ? (
            <Button variant="secondary" aria-label={t.markDoneLabel(reminder.kind)} onPress={() => onAsk({ kind: 'done', reminder })}>
              {t.markDone}
            </Button>
          ) : null}
          <Button variant="tertiary" aria-label={t.deleteLabel(reminder.kind)} onPress={() => onAsk({ kind: 'delete', reminder })}>
            {t.delete}
          </Button>
        </span>
      </span>
    </li>
  );
}

function Group({ label, empty, reminders, today, onAsk }: { label: string; empty: string; reminders: readonly Reminder[]; today: string; onAsk: (ask: Ask) => void }) {
  return (
    <div className="stack-tight">
      <h3 className="subhead">{label}</h3>
      {reminders.length ? (
        <ul className="list">
          {reminders.map((r) => (
            <ReminderItem key={r.id} reminder={r} today={today} onAsk={onAsk} />
          ))}
        </ul>
      ) : (
        <Empty>{empty}</Empty>
      )}
    </div>
  );
}

function Reminders() {
  const locale = useLocale();
  const today = isoDate(new Date());
  const query = useRead('reminders.list', remindersList);
  const [ask, setAsk] = useState<Ask>(null);
  const [said, setSaid] = useState('');
  const done = useWrite<{ id: string; what: string }, unknown>('reminders.markDone', (api, input) => api.call(remindersMarkDone, { path: { reminder_id: input.id } }), {
    invalidate: INVALIDATE,
    onSuccess: (_, input) => {
      setAsk(null);
      setSaid(t.markedDone(input.what));
    },
  });
  const remove = useWrite<{ id: string; what: string }, unknown>('reminders.delete', (api, input) => api.call(remindersDelete, { path: { reminder_id: input.id } }), {
    invalidate: INVALIDATE,
    onSuccess: (_, input) => {
      setAsk(null);
      setSaid(t.deleted(input.what));
    },
  });
  const write = ask?.kind === 'delete' ? remove : done;
  const open = (next: Ask): void => {
    done.reset();
    remove.reset();
    setSaid('');
    setAsk(next);
  };
  return (
    <Section label={t.reminders} full>
      <Panel>
        <Loaded query={query}>
          {({ reminders }) => {
            const byDate = [...reminders].sort((a, b) => a.due_date.localeCompare(b.due_date));
            const pending = byDate.filter((r) => r.status === 'pending');
            const finished = byDate.filter((r) => r.status !== 'pending');
            return (
              <div className="stack-tight">
                <Group label={t.overdue} empty={t.noneOverdue} reminders={pending.filter((r) => r.due_date < today)} today={today} onAsk={open} />
                <Group label={t.dueToday} empty={t.noneToday} reminders={pending.filter((r) => r.due_date === today)} today={today} onAsk={open} />
                <Group label={t.coming} empty={t.noneComing} reminders={pending.filter((r) => r.due_date > today)} today={today} onAsk={open} />
                <details className="disclosure">
                  <summary>{t.done(finished.length)}</summary>
                  {finished.length ? (
                    <ul className="list">
                      {finished.map((r) => (
                        <ReminderItem key={r.id} reminder={r} today={today} onAsk={open} />
                      ))}
                    </ul>
                  ) : (
                    <Empty>{t.noneDone}</Empty>
                  )}
                </details>
              </div>
            );
          }}
        </Loaded>
        <p role="status" className="quiet-success">
          {said ? (
            <>
              <span aria-hidden="true">✓</span> {said}
            </>
          ) : null}
        </p>
        {write.isError && !write.stepUpPending ? <ProblemView error={write.error} compact /> : null}
        <Confirm
          isOpen={ask !== null}
          onOpenChange={(isOpen) => (isOpen ? undefined : setAsk(null))}
          title={ask?.kind === 'delete' ? t.deleteTitle : t.doneTitle}
          confirmLabel={ask?.kind === 'delete' ? t.deleteConfirm : t.doneConfirm}
          cancelLabel={t.cancel}
          isPending={write.isPending}
          onConfirm={() => (ask ? write.mutate({ id: ask.reminder.id, what: ask.reminder.kind }) : undefined)}
        >
          {ask ? (
            <>
              <p>{ask.kind === 'delete' ? t.deleteBody(ask.reminder.kind, displayDate(ask.reminder.due_date, locale)) : t.doneBody(ask.reminder.kind, displayDate(ask.reminder.due_date, locale))}</p>
              {ask.kind === 'done' && ask.reminder.source_domain === 'decision' ? <p>{t.doneDecision}</p> : null}
              {ask.kind === 'delete' && ask.reminder.source_domain === 'tax_rules' ? <p>{t.deleteFiling}</p> : null}
            </>
          ) : null}
        </Confirm>
      </Panel>
    </Section>
  );
}

export function Attention() {
  return (
    <Page title={t.title} description={t.description}>
      <Grid>
        <Signals />
        <Reminders />
      </Grid>
    </Page>
  );
}

export default Attention;
