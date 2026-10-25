/**
 * salli notifications show | set | preview | log: your digest. Off until you
 * turn it on; then weekly or monthly, at your local hour, saying what is
 * waiting for you (kinds of thing, how many, dates), never what it is about.
 * Your server's notifier delivers it; Salli itself sends nothing.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  devicesAdd,
  devicesList,
  devicesRemove,
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
import { resolveById } from '../util/resolve';
import { countArg } from './shared';

type ItemKind = NotificationPreferences['items'][number];
type PushItem = NotificationPreferences['push_items'][number];
type Weekday = NotificationPreferences['weekday'];

/** Every kind of item a digest can hold, in the order it lists them, with how people read it. */
export const DIGEST_ITEMS: Readonly<Record<ItemKind, string>> = {
  decision_review_due: 'decisions ready for review',
  reminder_due: 'your reminders due',
  filing_deadline: 'filing deadlines in the next 14 days',
  cash_below_zero_ahead: 'cash forecast below zero',
  transactions_to_review: 'transactions to review',
  budget_over: 'budgets over their limit',
};
const KINDS = Object.keys(DIGEST_ITEMS) as ItemKind[];
const PUSH_KINDS: readonly PushItem[] = ['reminder_due', 'cash_below_zero_ahead', 'budget_over'];

function pushArg(value: string): PushItem[] {
  if (value.trim() === 'none') return [];
  const chosen = value.split(',').map((p) => p.trim()).filter(Boolean) as PushItem[];
  const unknown = chosen.find((k) => !PUSH_KINDS.includes(k));
  if (unknown) throw new UsageError(`--push takes none or ${PUSH_KINDS.join(', ')} (got "${unknown}").`);
  return PUSH_KINDS.filter((k) => chosen.includes(k));
}

function quietArg(value: string): { start: string; end: string } | null {
  if (value.trim() === 'off') return null;
  const match = /^(\d{2}:\d{2})-(\d{2}:\d{2})$/.exec(value.trim());
  if (!match) throw new UsageError(`--quiet takes HH:MM-HH:MM, like 22:00-08:00, or off (got "${value}").`);
  return { start: match[1] as string, end: match[2] as string };
}
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
      ['Push alerts', p.push_items.length ? p.push_items.map((k) => DIGEST_ITEMS[k]).join(', ') : 'none'],
      ['Quiet hours', p.quiet_hours ? `${p.quiet_hours.start} to ${p.quiet_hours.end}` : 'none'],
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
  $ salli notifications set --push budget_over,reminder_due --quiet 22:00-08:00
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
    .option('--push <kinds>', `The push alerts your phones take, comma-separated (or none): ${PUSH_KINDS.join(', ')}`, pushArg)
    .option('--quiet <from-to>', 'Hours with no push alert, in your time zone, like 22:00-08:00; off for none', quietArg)
    .action(async (opts) => {
      const body: NotificationPreferencesUpdate = {};
      if (opts.on) body.enabled = true;
      if (opts.off) body.enabled = false;
      if (opts.weekly) body.cadence = 'weekly';
      if (opts.monthly) body.cadence = 'monthly';
      if (opts.day !== undefined) body.weekday = opts.day;
      if (opts.hour !== undefined) body.hour = opts.hour;
      if (opts.items !== undefined) body.items = opts.items;
      if (opts.push !== undefined) body.push_items = opts.push;
      if (opts.quiet !== undefined) body.quiet_hours = opts.quiet;
      if (opts.timeZone !== undefined) {
        const zone = opts.timeZone.trim() === 'local' ? localTimeZone() : opts.timeZone.trim();
        if (!zone) throw new UsageError('This computer has no IANA time zone to use.', 'Name yours: --time-zone Europe/Lisbon');
        body.time_zone = zone;
      }
      if (!Object.keys(body).length) {
        throw new UsageError('Nothing to change.', 'Try --on --time-zone <zone>, --off, --monthly, --day, --hour, --items, --push or --quiet.');
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

  const devices = program.command('devices').alias('device').description('Phones that take push alerts');

  devices
    .command('list')
    .alias('ls')
    .description('List your registered devices')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(devicesList);
      app.out.emit(data, {
        records: (d) => d.devices,
        human: (d) => {
          if (!d.push_enabled) app.out.note('This server sends no push alerts.');
          if (!d.devices.length) return app.out.note('No devices registered.');
          app.out.line(
            app.out.table(d.devices, [
              { header: 'ID', get: (r) => r.id.slice(0, 12) },
              { header: 'PLATFORM', get: (r) => r.platform },
              { header: 'ADDED', get: (r) => displayDate(r.created_at, app.out.locale) },
            ]),
          );
        },
      });
    });

  devices
    .command('add')
    .argument('<token>', 'The Expo push token')
    .description('Register a device for push alerts (the phone app does this itself)')
    .addOption(new Option('--platform <platform>', 'ios or android').choices(['ios', 'android'] as const).makeOptionMandatory())
    .action(async (token, opts) => {
      const api = await app.api();
      const device = await api.call(devicesAdd, { body: { token, platform: opts.platform } });
      app.out.done(device, `Registered the device (${device.id.slice(0, 12)}).`);
    });

  devices
    .command('remove')
    .alias('rm')
    .argument('<id>', 'Device id, from `salli devices list` (or the start of one)')
    .description('Stop push alerts to a device')
    .action(async (query) => {
      const api = await app.api();
      const { devices: all } = await api.call(devicesList);
      const device = resolveById(all, query, 'device');
      await api.call(devicesRemove, { path: { device_id: device.id } });
      app.out.done({ removed: device.id }, 'Removed the device.');
    });
}
