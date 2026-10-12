/**
 * salli notifications show | set | preview | log: your digest. Off until you
 * turn it on; then weekly or monthly, at your local hour, saying what is
 * waiting for you (kinds of thing, how many, dates), never what it is about.
 * Your server's notifier delivers it; Salli itself sends nothing.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  notificationsDeliveriesList,
  notificationsPreferencesGet,
  notificationsPreferencesUpdate,
  notificationsPreview,
  type NotificationPreferences,
  type NotificationPreferencesUpdate,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import { singleLine } from '../output/text';
import { displayDate } from '../util/dates';
import { countArg } from './shared';

type ItemKind = NotificationPreferences['items'][number];
type Weekday = NotificationPreferences['weekday'];

/** Every kind of item a digest can hold, in the order it lists them, with how people read it. */
export const DIGEST_ITEMS: Readonly<Record<ItemKind, string>> = {
  decision_review_due: 'decisions ready for review',
  reminder_due: 'your reminders due',
  filing_deadline: 'filing deadlines in the next 14 days',
  cash_below_zero_ahead: 'cash forecast below zero',
  transactions_to_review: 'transactions to review',
};
const KINDS = Object.keys(DIGEST_ITEMS) as ItemKind[];
const WEEKDAYS: readonly Weekday[] = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];

function itemsArg(value: string, previous: ItemKind[] = []): ItemKind[] {
  const chosen = [...previous];
  for (const part of value.split(',')) {
    const kind = part.trim() as ItemKind;
    if (!kind) continue;
    if (!KINDS.includes(kind)) throw new UsageError(`--items takes ${KINDS.join(', ')} (got "${part.trim()}").`);
    if (!chosen.includes(kind)) chosen.push(kind);
  }
  return chosen;
}

function dayArg(value: string): Weekday {
  const day = value.trim().toLowerCase();
  const found = WEEKDAYS.find((d) => d === day || d.slice(0, 3) === day);
  if (!found) throw new UsageError(`--day takes a weekday, like monday or mon (got "${value}").`);
  return found;
}

function hourArg(value: string): number {
  const hour = countArg('--hour')(value);
  if (hour > 23) throw new UsageError(`--hour is 0 to 23, on the 24-hour clock (got "${value}").`);
  return hour;
}

/** This computer's IANA time zone, when it has one. */
function localTimeZone(): string | undefined {
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return zone && zone.includes('/') ? zone : undefined;
}

const titleCase = (word: string): string => word.charAt(0).toUpperCase() + word.slice(1);

/** "2026-10-12T09:00:00+01:00" → "2026-10-12 09:00": the time as the person's own zone has it. */
function wallClock(moment: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(moment);
  return match ? `${match[1]} ${match[2]}` : moment;
}

function when(p: NotificationPreferences): string {
  const hour = `${String(p.hour).padStart(2, '0')}:00`;
  const day = titleCase(p.weekday);
  const rhythm = p.cadence === 'weekly' ? `weekly on ${day}` : `monthly on the first ${day}`;
  return `${rhythm} at ${hour}${p.time_zone ? ` (${singleLine(p.time_zone)})` : ''}`;
}

function showPreferences(app: App, p: NotificationPreferences): void {
  app.out.line(
    app.out.details([
      ['Digest', p.enabled ? `on, ${when(p)}` : 'off'],
      ['Next', p.next_at ? wallClock(p.next_at) : undefined],
      ['Holds', p.items.map((k) => DIGEST_ITEMS[k]).join(', ')],
      ['Time zone', p.time_zone ? singleLine(p.time_zone) : 'not set'],
    ]),
  );
  if (!p.sender_enabled) {
    app.out.warn('This server has no notifier enabled, so nothing is sent yet. Your choices are saved for when it has one.');
  }
}

export function registerNotifications(program: Command, app: App): void {
  const notifications = program
    .command('notifications')
    .alias('digest')
    .description('Your digest: what is waiting for you, weekly or monthly, at your hour')
    .addHelpText(
      'after',
      `
A digest says what is waiting (decisions to review, reminders, filing
deadlines, cash going below zero), how many and when, with a link. It never
holds an amount, a name or a question. Nothing goes when nothing is waiting,
and never more than one a week (or a month). Your server delivers it through
its notifier; without one, nothing is sent.

Examples:
  $ salli notifications set --on --time-zone Europe/Lisbon
  $ salli notifications set --monthly --day friday --hour 18
  $ salli notifications set --items decision_review_due,filing_deadline
  $ salli notifications preview
  $ salli notifications set --off`,
    );

  notifications
    .command('show', { isDefault: true })
    .alias('status')
    .description('Whether your digest is on, when it goes and what it holds')
    .action(async () => {
      const api = await app.api();
      const prefs = await api.call(notificationsPreferencesGet);
      app.out.emit(prefs, { human: (p) => showPreferences(app, p) });
    });

  notifications
    .command('set')
    .description('Turn your digest on or off, or change when it goes and what it holds')
    .addOption(new Option('--on', 'Turn it on (needs your time zone)').conflicts('off'))
    .addOption(new Option('--off', 'Turn it off'))
    .addOption(new Option('--weekly', 'Every week').conflicts('monthly'))
    .addOption(new Option('--monthly', 'Every month, on its first chosen weekday'))
    .option('--day <weekday>', 'The weekday it goes (default monday)', dayArg)
    .option('--hour <0-23>', 'The local hour it goes (default 9)', hourArg)
    .option('--time-zone <zone>', 'Your IANA time zone, like Europe/Lisbon; "local" for this computer\'s')
    .option('--items <kinds>', `What it holds, comma-separated: ${KINDS.join(', ')}`, itemsArg)
    .action(async (opts) => {
      const body: NotificationPreferencesUpdate = {};
      if (opts.on) body.enabled = true;
      if (opts.off) body.enabled = false;
      if (opts.weekly) body.cadence = 'weekly';
      if (opts.monthly) body.cadence = 'monthly';
      if (opts.day !== undefined) body.weekday = opts.day;
      if (opts.hour !== undefined) body.hour = opts.hour;
      if (opts.items !== undefined) body.items = opts.items;
      if (opts.timeZone !== undefined) {
        const zone = opts.timeZone.trim() === 'local' ? localTimeZone() : opts.timeZone.trim();
        if (!zone) throw new UsageError('This computer has no IANA time zone to use.', 'Name yours: --time-zone Europe/Lisbon');
        body.time_zone = zone;
      }
      if (!Object.keys(body).length) {
        throw new UsageError('Nothing to change.', 'Try --on --time-zone <zone>, --off, --monthly, --day, --hour or --items.');
      }
      const api = await app.api();
      if (body.enabled && body.time_zone === undefined) {
        const current = await api.call(notificationsPreferencesGet);
        if (!current.time_zone) {
          const here = localTimeZone();
          throw new UsageError(
            'A digest goes at your local hour, so turning it on needs your time zone.',
            here ? `salli notifications set --on --time-zone ${here}` : 'salli notifications set --on --time-zone Europe/Lisbon',
          );
        }
      }
      const saved = await api.call(notificationsPreferencesUpdate, { body });
      app.out.emit(saved, {
        human: (p) => {
          app.out.success(p.enabled ? `Your digest is on: ${when(p)}.` : 'Your digest is off.');
          showPreferences(app, p);
        },
      });
    });

  notifications
    .command('preview')
    .description('The digest that would go now, exactly as it would read. Sends nothing')
    .action(async () => {
      const api = await app.api();
      const preview = await api.call(notificationsPreview);
      app.out.emit(preview, {
        human: (p) => {
          if (p.digest) {
            app.out.line(app.out.heading(singleLine(p.digest.subject)));
            app.out.line('');
            for (const line of p.digest.text.trimEnd().split('\n')) app.out.line(singleLine(line));
            app.out.line('');
          }
          app.out.note(p.note);
        },
      });
    });

  notifications
    .command('log')
    .description('The digests delivered to you: when, and what they held')
    .option('--limit <n>', 'How many, newest first (default 50)', countArg('--limit'))
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(notificationsDeliveriesList, { query: opts.limit !== undefined ? { limit: opts.limit } : {} });
      app.out.emit(data, {
        records: (d) => d.deliveries,
        human: (d) => {
          if (!d.deliveries.length) return app.out.note('No digest has been delivered to you yet.');
          const c = app.out.colors;
          app.out.line(
            app.out.table(d.deliveries, [
              { header: 'PERIOD', get: (r) => r.period },
              { header: 'STATUS', get: (r) => r.status.replace('_', ' '), style: (t, r) => (r.status === 'sent' ? t : c.yellow(t)) },
              { header: 'TRIES', get: (r) => String(r.attempts) },
              { header: 'ITEMS', get: (r) => r.items.map((i) => `${i.count} ${DIGEST_ITEMS[i.kind]}`).join(', '), shrink: true },
              { header: 'SENT', get: (r) => (r.sent_at ? displayDate(r.sent_at, app.out.locale) : '') },
            ]),
          );
        },
      });
    });
}
