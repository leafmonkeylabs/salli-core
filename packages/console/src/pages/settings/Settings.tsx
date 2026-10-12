/**
 * Settings, as C1 builds them: the profile (what the API lets a person
 * change: name, base currency while it can change, tax residency, time
 * zone), every sign-in with a way to end each (`GET`/`DELETE
 * /v1/auth/sign-ins`), what this device shows, and the panels extensions
 * add. Each write confirms or reports in Salli's words. The rest of
 * Settings (C4: tokens, AI connections, digests, your data) are pages of
 * their own, under Settings' own places (nav.tsx).
 */
import {
  authSignInsList,
  authSignInsRevoke,
  notificationsPreferencesUpdate,
  profileGet,
  profileUpdate,
  type Profile,
  type ProfileIdentityRequest,
  type SignIn,
} from '@leafmonkeylabs/salli-sdk';
import { useState, type FormEvent } from 'react';
import { Form } from 'react-aria-components';
import { useRead, useSession, useWrite } from '../../api';
import { useConsoleExtensions } from '../../console-context';
import { displayMoment } from '../../kit/dates';
import { Button, Confirm, TextField } from '../../kit/forms';
import { Empty, Loading, Page, Panel, Section } from '../../kit/layout';
import { visibleAmount } from '../../kit/Money';
import { ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { isLocale, usePreferences, type Theme } from '../../preferences';
import { strings } from '../../strings';
import { SettingsNav } from './nav';

const s = strings.settings;

interface ProfileInput {
  profile: ProfileIdentityRequest;
  time_zone?: string;
}

function ProfileForm({ profile, saved, setSaved }: { profile: Profile; saved: boolean; setSaved: (saved: boolean) => void }) {
  const [name, setName] = useState(profile.display_name ?? '');
  const [currency, setCurrency] = useState(profile.base_currency ?? '');
  const [residency, setResidency] = useState(profile.tax_residency ?? '');
  const [zone, setZone] = useState(profile.time_zone ?? '');
  const write = useWrite<ProfileInput, void>(
    'profile.update',
    async (api, input) => {
      if (Object.keys(input.profile).length) await api.call(profileUpdate, { body: input.profile });
      if (input.time_zone !== undefined) await api.call(notificationsPreferencesUpdate, { body: { time_zone: input.time_zone } });
    },
    { invalidate: ['profile.get'], onSuccess: () => setSaved(true) },
  );

  const zones = typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : [];
  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setSaved(false);
    const changes: ProfileIdentityRequest = {};
    if (name.trim() !== (profile.display_name ?? '')) changes.display_name = name.trim();
    if (currency.trim().toUpperCase() !== profile.base_currency) changes.base_currency = currency.trim().toUpperCase();
    if (residency.trim().toUpperCase() !== (profile.tax_residency ?? '') && residency.trim()) changes.tax_residency = residency.trim().toUpperCase();
    const input: ProfileInput = { profile: changes };
    if (zone.trim() && zone.trim() !== (profile.time_zone ?? '')) input.time_zone = zone.trim();
    write.mutate(input);
  };

  return (
    <Form className="form" onSubmit={submit} validationBehavior="native">
      <dl className="rows">
        <div className="row">
          <dt>{s.email}</dt>
          <dd>{profile.email ?? strings.notSet}</dd>
        </div>
      </dl>
      <TextField label={s.displayName} value={name} onChange={setName} inputProps={{ autoComplete: 'name' }} />
      <TextField
        label={s.baseCurrency}
        description={s.baseCurrencyHelp}
        value={currency}
        onChange={setCurrency}
        isRequired
        pattern="[A-Za-z]{3}"
        errorMessage={s.invalidCurrency}
        inputProps={{ autoComplete: 'off', spellCheck: false }}
      />
      <TextField
        label={s.taxResidency}
        description={s.taxResidencyHelp}
        value={residency}
        onChange={setResidency}
        pattern="[A-Za-z]{2}"
        errorMessage={s.invalidCountry}
        inputProps={{ autoComplete: 'off', spellCheck: false }}
      />
      <TextField
        label={s.timeZone}
        description={s.timeZoneHelp}
        value={zone}
        onChange={setZone}
        inputProps={{ list: 'salli-time-zones', autoComplete: 'off', spellCheck: false }}
      />
      <datalist id="salli-time-zones">
        {zones.map((z) => (
          <option key={z} value={z} />
        ))}
      </datalist>
      <div className="form-actions">
        <Button type="submit" isPending={write.isPending}>
          {write.isPending ? s.saving : s.save}
        </Button>
        <p role="status" className="quiet-success">
          {saved ? (
            <>
              <span aria-hidden="true">✓</span> {s.saved}
            </>
          ) : write.stepUpPending ? (
            strings.signIn.redirecting
          ) : null}
        </p>
      </div>
      {write.isError && !write.stepUpPending ? <ProblemView error={write.error} compact /> : null}
    </Form>
  );
}

function ProfileSection() {
  const query = useRead('profile.get', profileGet);
  // Kept here: the form starts afresh from what Salli saved.
  const [saved, setSaved] = useState(false);
  return (
    <Section label={s.profile}>
      <Panel>
        <p className="section-help">{s.profileHelp}</p>
        {query.isPending ? <Loading lines={4} /> : null}
        {query.isError ? <ProblemView error={query.error} compact onRetry={() => void query.refetch()} /> : null}
        {query.data ? <ProfileForm key={JSON.stringify(query.data)} profile={query.data} saved={saved} setSaved={setSaved} /> : null}
      </Panel>
    </Section>
  );
}

function describe(signIn: SignIn): string {
  const kind = s.kind[signIn.kind] ?? signIn.kind;
  const detail = signIn.client_name && signIn.kind === 'app' ? signIn.client_name : signIn.user_agent;
  return detail ? `${kind} · ${detail}` : kind;
}

function SignInsSection() {
  const session = useSession();
  const { locale } = usePreferences();
  const query = useRead('auth.signIns.list', authSignInsList);
  const [ending, setEnding] = useState<SignIn | null>(null);
  const [ended, setEnded] = useState(false);
  const revoke = useWrite<{ id: string; current: boolean }, void>(
    'auth.signIns.revoke',
    async (api, input) => {
      if (input.current) {
        await session.signOut('signed-out');
        return;
      }
      await api.call(authSignInsRevoke, { path: { sign_in_id: input.id } });
    },
    {
      invalidate: ['auth.signIns.list'],
      onSuccess: () => {
        setEnding(null);
        setEnded(true);
      },
    },
  );
  const when = (value: string | null): string => (value ? displayMoment(value, locale) : '');
  return (
    <Section label={s.signIns}>
      <Panel>
        <p className="section-help">{s.signInsHelp}</p>
        {query.isPending ? <Loading lines={3} /> : null}
        {query.isError ? <ProblemView error={query.error} compact onRetry={() => void query.refetch()} /> : null}
        {query.data && query.data.length === 0 ? <Empty>{s.noSignIns}</Empty> : null}
        {query.data && query.data.length ? (
          <Table<SignIn>
            caption={s.signIns}
            captionHidden
            rows={query.data}
            rowKey={(row) => row.id}
            columns={[
              {
                key: 'what',
                header: s.what,
                label: s.what,
                render: (row) => (
                  <>
                    {describe(row)}
                    {row.current ? <span className="tag"> {s.thisOne}</span> : null}
                  </>
                ),
              },
              { key: 'started', header: s.started, label: s.started, render: (row) => when(row.started_at) },
              { key: 'used', header: s.lastUsed, label: s.lastUsed, render: (row) => (row.last_used_at ? when(row.last_used_at) : s.never) },
              { key: 'ends', header: s.ends, label: s.ends, render: (row) => (row.expires_at ? when(row.expires_at) : s.noEnd) },
              {
                key: 'end',
                header: <span className="sr-only">{s.end}</span>,
                // On a phone the button says it: no label beside it.
                label: '',
                align: 'end',
                render: (row) => (
                  <Button variant="tertiary" aria-label={s.endLabel(describe(row), when(row.started_at))} onPress={() => setEnding(row)}>
                    {s.end}
                  </Button>
                ),
              },
            ]}
          />
        ) : null}
        <p role="status" className="quiet-success">
          {ended ? (
            <>
              <span aria-hidden="true">✓</span> {s.ended}
            </>
          ) : null}
        </p>
        {revoke.isError && !revoke.stepUpPending ? <ProblemView error={revoke.error} compact /> : null}
      </Panel>
      <Confirm
        isOpen={ending !== null}
        onOpenChange={(open) => {
          if (!open) setEnding(null);
        }}
        title={s.confirmEndTitle}
        confirmLabel={s.end}
        cancelLabel={s.cancel}
        isPending={revoke.isPending}
        onConfirm={() => {
          if (ending) {
            setEnded(false);
            revoke.mutate({ id: ending.id, current: ending.current });
          }
        }}
      >
        {ending ? (
          <>
            <p>{s.confirmEnd(describe(ending), when(ending.started_at))}</p>
            {ending.current ? <p>{s.confirmEndThis}</p> : null}
          </>
        ) : null}
      </Confirm>
    </Section>
  );
}

function DeviceSection() {
  const { theme, setTheme, locale, setLocale } = usePreferences();
  const [draft, setDraft] = useState(locale ?? '');
  const [invalid, setInvalid] = useState(false);
  const example = `${visibleAmount('1234.56', 'EUR', 'prose', { locale })}`;
  return (
    <Section label={s.device}>
      <Panel>
        <p className="section-help">{s.deviceHelp}</p>
        <fieldset className="choices">
          <legend className="field-label">{s.theme}</legend>
          {(['system', 'light', 'dark'] as Theme[]).map((option) => (
            <label key={option} className="choice">
              <input type="radio" name="theme" value={option} checked={theme === option} onChange={() => setTheme(option)} />
              {s.themes[option]}
            </label>
          ))}
        </fieldset>
        <form
          className="form form-inline"
          onSubmit={(event) => {
            event.preventDefault();
            const tag = draft.trim();
            if (tag && !isLocale(tag)) {
              setInvalid(true);
              return;
            }
            setInvalid(false);
            setLocale(tag || undefined);
          }}
        >
          <TextField
            label={s.locale}
            description={s.localeHelp(example)}
            value={draft}
            onChange={setDraft}
            isInvalid={invalid}
            errorMessage={s.localeInvalid}
            inputProps={{ autoComplete: 'off', spellCheck: false, placeholder: 'en-GB' }}
          />
          <div className="form-actions">
            <Button type="submit" variant="secondary">
              {s.localeSave}
            </Button>
            {locale ? (
              <Button
                variant="tertiary"
                onPress={() => {
                  setDraft('');
                  setLocale(undefined);
                }}
              >
                {s.localeReset}
              </Button>
            ) : null}
          </div>
        </form>
      </Panel>
    </Section>
  );
}

export function Settings() {
  const { settingsPanels } = useConsoleExtensions();
  return (
    <Page title={s.title} description={s.description}>
      <SettingsNav />
      <div className="stack">
        <ProfileSection />
        <SignInsSection />
        <DeviceSection />
        {settingsPanels.map((panel) => (
          <Section key={panel.id} label={panel.title}>
            <Panel>
              <panel.component />
            </Panel>
          </Section>
        ))}
      </div>
    </Page>
  );
}

export default Settings;
