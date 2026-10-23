/**
 * Digests (`notifications.preferences.get`, `.update`,
 * `notifications.preview`, `notifications.deliveries.list`; `salli
 * notifications`): whether and when a digest goes (weekly or monthly, the
 * day, the hour, in the person's time zone), what it says, the digest as it
 * would go now, and each one sent. Saving changes only what changed and
 * asks nothing: it can be changed back.
 */
import {
  notificationsDeliveriesList,
  notificationsPreferencesGet,
  notificationsPreferencesUpdate,
  notificationsPreview,
  type DigestDelivery,
  type NotificationPreferences,
  type NotificationPreferencesUpdate,
} from '@leafmonkeylabs/salli-sdk';
import { useState, type FormEvent } from 'react';
import { useRead, useWrite } from '../../api';
import { displayDate, displayMoment } from '../../kit/dates';
import { Button, CheckboxField, Field, RadioField, SelectField } from '../../kit/forms';
import { Blank, Empty, Grid, Loaded, Page, Panel, Section } from '../../kit/layout';
import { fieldErrors, ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { settingsStrings } from '../../settings-strings';
import { SettingsNav } from './nav';

const t = settingsStrings.digests;
type Item = NotificationPreferences['items'][number];
const ITEMS: Item[] = ['decision_review_due', 'reminder_due', 'filing_deadline', 'cash_below_zero_ahead', 'transactions_to_review'];
const WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const;
const HOURS = Array.from({ length: 24 }, (_, h) => h);
const DIGEST_READS = ['notifications.preferences.get', 'notifications.preview', 'profile.get'];

const hourText = (h: number): string => `${String(h).padStart(2, '0')}:00`;

function PreferencesForm({ saved, done, setDone }: { saved: NotificationPreferences; done: boolean; setDone: (done: boolean) => void }) {
  const locale = useLocale();
  const [enabled, setEnabled] = useState(saved.enabled);
  const [cadence, setCadence] = useState(saved.cadence);
  const [weekday, setWeekday] = useState(saved.weekday);
  const [hour, setHour] = useState(String(saved.hour));
  const [zone, setZone] = useState(saved.time_zone ?? '');
  const [items, setItems] = useState<ReadonlySet<Item>>(new Set(saved.items));
  const [local, setLocal] = useState<Record<string, string>>({});
  const write = useWrite<NotificationPreferencesUpdate, NotificationPreferences>(
    'notifications.preferences.update',
    (api, input) => api.call(notificationsPreferencesUpdate, { body: input }),
    { invalidate: DIGEST_READS, onSuccess: () => setDone(true) },
  );
  const zones = typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : [];

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setDone(false);
    const found: Record<string, string> = {};
    if (enabled && !zone.trim()) found.time_zone = t.timeZoneMissing;
    setLocal(found);
    if (Object.keys(found).length) return;
    const chosen = ITEMS.filter((i) => items.has(i));
    const hourValue = HOURS.find((h) => String(h) === hour) ?? saved.hour;
    const changes: NotificationPreferencesUpdate = {
      ...(enabled !== saved.enabled ? { enabled } : {}),
      ...(cadence !== saved.cadence ? { cadence } : {}),
      ...(weekday !== saved.weekday ? { weekday } : {}),
      ...(hourValue !== saved.hour ? { hour: hourValue } : {}),
      ...(zone.trim() && zone.trim() !== (saved.time_zone ?? '') ? { time_zone: zone.trim() } : {}),
      ...(chosen.join() !== saved.items.join() ? { items: chosen } : {}),
    };
    write.mutate(changes);
  };
  const server = write.isError ? fieldErrors(write.error) : {};
  const errors = { ...server, ...local };

  return (
    <form className="form form-wide" onSubmit={submit} noValidate>
      {!saved.sender_enabled ? <p className="muted">{t.noSender}</p> : null}
      <CheckboxField label={t.enabled} checked={enabled} onChange={setEnabled} error={errors.enabled} />
      <div className="field-grid">
        <RadioField
          label={t.cadence}
          value={cadence}
          onChange={(v) => setCadence(v as NotificationPreferences['cadence'])}
          options={['weekly', 'monthly'].map((c) => ({ value: c, label: t.cadences[c] ?? c }))}
          error={errors.cadence}
        />
        <SelectField
          label={t.weekday}
          description={t.weekdayHelp}
          value={weekday}
          onChange={(v) => setWeekday(v as NotificationPreferences['weekday'])}
          options={WEEKDAYS.map((d) => ({ value: d, label: t.weekdays[d] ?? d }))}
          error={errors.weekday}
        />
        <SelectField label={t.hour} value={hour} onChange={setHour} options={HOURS.map((h) => ({ value: String(h), label: hourText(h) }))} error={errors.hour} />
        <Field label={t.timeZone} description={t.timeZoneHelp} value={zone} onChange={setZone} error={errors.time_zone} inputProps={{ spellCheck: false, list: 'salli-digest-zones' }} />
        <datalist id="salli-digest-zones">
          {zones.map((z) => (
            <option key={z} value={z} />
          ))}
        </datalist>
      </div>
      <fieldset className="field choices-field">
        <legend className="field-label">{t.items}</legend>
        <div className="choices">
          {ITEMS.map((item) => (
            <label key={item} className="choice">
              <input
                type="checkbox"
                checked={items.has(item)}
                onChange={(event) => {
                  const on = event.currentTarget.checked;
                  setItems((now) => {
                    const next = new Set(now);
                    if (on) next.add(item);
                    else next.delete(item);
                    return next;
                  });
                }}
              />
              <span>{t.itemNames[item] ?? item}</span>
            </label>
          ))}
        </div>
        {errors.items ? <p className="field-error">{errors.items}</p> : null}
      </fieldset>
      <p className="provenance">{saved.next_at ? t.next(displayMoment(saved.next_at, locale)) : t.noNext}</p>
      {Object.keys(local).length ? (
        <p className="sr-only" role="alert">
          {Object.values(local).join(' ')}
        </p>
      ) : null}
      {write.isError ? <ProblemView error={write.error} compact /> : null}
      <div className="form-actions">
        <Button type="submit" isPending={write.isPending}>
          {write.isPending ? t.saving : t.save}
        </Button>
        <p role="status" className="quiet-success">
          {done ? (
            <>
              <span aria-hidden="true">✓</span> {t.saved}
            </>
          ) : null}
        </p>
      </div>
    </form>
  );
}

function Preview() {
  const query = useRead('notifications.preview', notificationsPreview);
  return (
    <Section label={t.preview} full>
      <Panel>
        <p className="section-help">{t.previewHelp}</p>
        <Loaded query={query}>
          {(preview) =>
            preview.digest ? (
              <div className="stack-tight">
                <p>
                  <span className="field-label">{t.subject}</span> {preview.digest.subject}
                </p>
                <pre className="digest-text">{preview.digest.text}</pre>
                <p className="provenance">{preview.note}</p>
              </div>
            ) : (
              <Empty>{preview.note || t.previewEmpty}</Empty>
            )
          }
        </Loaded>
      </Panel>
    </Section>
  );
}

function Log() {
  const locale = useLocale();
  const query = useRead('notifications.deliveries.list', notificationsDeliveriesList);
  return (
    <Section label={t.log} full>
      <Panel>
        <p className="section-help">{t.logHelp}</p>
        <Loaded query={query}>
          {({ deliveries }) =>
            deliveries.length ? (
              <Table<DigestDelivery>
                caption={t.log}
                captionHidden
                rows={deliveries}
                rowKey={(d) => d.id}
                columns={[
                  { key: 'period', header: t.period, label: t.period, render: (d) => d.period },
                  { key: 'status', header: t.status, label: t.status, render: (d) => t.statuses[d.status] ?? d.status },
                  {
                    key: 'what',
                    header: t.what,
                    label: t.what,
                    render: (d) =>
                      d.items
                        .map((i) => `${t.itemCount(i.count, t.itemNames[i.kind] ?? i.kind)}${i.date ? ` (${displayDate(i.date, locale)})` : ''}`)
                        .join('; '),
                  },
                  { key: 'sent', header: t.sentAt, label: t.sentAt, render: (d) => (d.sent_at ? displayMoment(d.sent_at, locale) : <Blank>{t.notSent}</Blank>) },
                  { key: 'attempts', header: t.attempts, label: t.attempts, align: 'end', render: (d) => d.attempts },
                ]}
              />
            ) : (
              <Empty>{t.noLog}</Empty>
            )
          }
        </Loaded>
      </Panel>
    </Section>
  );
}

export function Digests() {
  const query = useRead('notifications.preferences.get', notificationsPreferencesGet);
  // Kept here: the form starts afresh from what Salli saved.
  const [done, setDone] = useState(false);
  return (
    <Page title={t.title} description={t.description}>
      <SettingsNav />
      <Grid>
        <Section label={t.preferences} full>
          <Panel>
            <Loaded query={query}>{(saved) => <PreferencesForm key={JSON.stringify(saved)} saved={saved} done={done} setDone={setDone} />}</Loaded>
          </Panel>
        </Section>
        <Preview />
        <Log />
      </Grid>
    </Page>
  );
}

export default Digests;
