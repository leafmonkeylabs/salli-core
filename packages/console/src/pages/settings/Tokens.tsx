/**
 * Personal access tokens (`tokens.list`, `tokens.create`, `tokens.revoke`;
 * `salli tokens`): every live token with what it may do, when it was made,
 * when it expires and when it was last used; revoking one after a
 * confirmation; and making one, optionally with `tax:activate`.
 *
 * - A token that may activate tax rules asks first, saying what it can do;
 *   a console sign-in holds `tax:activate` only within five minutes of its
 *   password (decision 6), so past that Salli asks for the password again
 *   on its own page and the token is made on return.
 * - The new token is shown once (`<Secret>`), with copy. It lives only in
 *   this page's state: the write is `secret: 'answer'`, so no cached answer
 *   outlives the page, and nothing writes it to storage or logs it.
 */
import { tokensCreate, tokensList, tokensRevoke, type NewPersonalAccessToken, type PersonalAccessToken } from '@leafmonkeylabs/salli-sdk';
import { useState, type FormEvent } from 'react';
import { useRead, useWrite } from '../../api';
import { displayDate, displayMoment } from '../../kit/dates';
import { Button, CheckboxField, Confirm, Field } from '../../kit/forms';
import { wholeNumberInput } from '../../kit/inputs';
import { Empty, Grid, Loaded, Page, Panel, Section } from '../../kit/layout';
import { fieldErrors, ProblemView } from '../../kit/Problem';
import { Secret } from '../../kit/Secret';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { settingsStrings } from '../../settings-strings';
import { SettingsNav } from './nav';

const t = settingsStrings.tokens;
const ACTIVATE = 'tax:activate';

interface MakeInput {
  name: string;
  expires_in_days?: number;
  permissions: string[];
}

function MakeToken() {
  const [name, setName] = useState('');
  const [days, setDays] = useState('');
  const [activate, setActivate] = useState(false);
  const [local, setLocal] = useState<Record<string, string>>({});
  const [asking, setAsking] = useState<MakeInput | null>(null);
  // The token made, shown once: only here, in this page's state.
  const [made, setMade] = useState<NewPersonalAccessToken | null>(null);
  const make = useWrite<MakeInput, NewPersonalAccessToken>(
    'tokens.create',
    (api, input) =>
      api.call(tokensCreate, {
        body: { name: input.name, permissions: input.permissions as Array<'tax:activate'>, ...(input.expires_in_days ? { expires_in_days: input.expires_in_days } : {}) },
      }),
    {
      secret: 'answer',
      invalidate: ['tokens.list'],
      onSuccess: (token) => {
        setAsking(null);
        setMade(token);
        setName('');
        setDays('');
        setActivate(false);
      },
    },
  );

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const found: Record<string, string> = {};
    const n = wholeNumberInput(days);
    if (!name.trim()) found.name = t.nameMissing;
    if (days.trim() && (n === undefined || n < 1 || n > 3650)) found.days = t.daysInvalid;
    setLocal(found);
    if (Object.keys(found).length) return;
    const input: MakeInput = { name: name.trim(), permissions: activate ? [ACTIVATE] : [], ...(n ? { expires_in_days: n } : {}) };
    setMade(null);
    if (activate) setAsking(input);
    else make.mutate(input);
  };

  const server = make.isError ? fieldErrors(make.error) : {};
  const errors = { ...(server.name ? { name: server.name } : {}), ...(server.expires_in_days ? { days: server.expires_in_days } : {}), ...local };

  return (
    <Section label={t.make} full>
      <Panel>
        {made ? (
          <div className="stack-tight">
            <p role="status" className="quiet-success">
              <span aria-hidden="true">✓</span> {t.made(made.name)}
            </p>
            <Secret
              label={t.newToken}
              value={made.token}
              words={settingsStrings.secret}
              onDone={() => {
                setMade(null);
                make.reset();
              }}
            />
          </div>
        ) : (
          <form className="form form-wide" onSubmit={submit} noValidate>
            <p className="section-help">{t.makeHelp}</p>
            <div className="field-grid">
              <Field label={t.nameField} value={name} onChange={setName} error={errors.name} isRequired />
              <Field label={t.days} description={t.daysHelp} value={days} onChange={setDays} error={errors.days} inputProps={{ inputMode: 'numeric' }} />
            </div>
            <CheckboxField label={t.activate} description={t.activateHelp} checked={activate} onChange={setActivate} />
            {Object.keys(local).length ? (
              <p className="sr-only" role="alert">
                {Object.values(local).join(' ')}
              </p>
            ) : null}
            {make.isError && !make.stepUpPending ? <ProblemView error={make.error} compact /> : null}
            <div className="form-actions">
              <Button type="submit" isPending={make.isPending}>
                {make.isPending ? t.submitting : t.submit}
              </Button>
              <p role="status" className="quiet-success">
                {make.stepUpPending ? t.stepUp : null}
              </p>
            </div>
          </form>
        )}
        <Confirm
          isOpen={asking !== null}
          onOpenChange={(open) => (open ? undefined : setAsking(null))}
          title={t.confirmTitle}
          confirmLabel={t.confirm}
          cancelLabel={t.cancel}
          isPending={make.isPending}
          onConfirm={() => (asking ? make.mutate(asking) : undefined)}
        >
          {asking ? (
            <>
              <p>{t.confirmBody(asking.name)}</p>
              <p>{t.confirmStepUp}</p>
            </>
          ) : null}
        </Confirm>
      </Panel>
    </Section>
  );
}

function List() {
  const locale = useLocale();
  const query = useRead('tokens.list', tokensList);
  const [revoking, setRevoking] = useState<PersonalAccessToken | null>(null);
  const [said, setSaid] = useState('');
  const revoke = useWrite<{ id: string; name: string }, unknown>('tokens.revoke', (api, input) => api.call(tokensRevoke, { path: { token_id: input.id } }), {
    invalidate: ['tokens.list'],
    onSuccess: (_, input) => {
      setRevoking(null);
      setSaid(t.revoked(input.name));
    },
  });
  return (
    <Section label={t.yours} full>
      <Panel>
        <Loaded query={query}>
          {(tokens) =>
            tokens.length ? (
              <Table<PersonalAccessToken>
                caption={t.yours}
                captionHidden
                rows={tokens}
                rowKey={(x) => x.id}
                columns={[
                  { key: 'name', header: t.name, label: t.name, render: (x) => x.name },
                  { key: 'prefix', header: t.shownAs, label: t.shownAs, render: (x) => <code className="mono">{x.prefix}…</code> },
                  { key: 'may', header: t.may, label: t.may, render: (x) => (x.permissions.includes(ACTIVATE) ? t.mayActivate : t.mayData) },
                  { key: 'created', header: t.created, label: t.created, render: (x) => displayDate(x.created_at, locale) },
                  { key: 'expires', header: t.expires, label: t.expires, render: (x) => (x.expires_at ? displayDate(x.expires_at, locale) : t.never) },
                  { key: 'used', header: t.lastUsed, label: t.lastUsed, render: (x) => (x.last_used_at ? displayMoment(x.last_used_at, locale) : t.notUsed) },
                  {
                    key: 'revoke',
                    header: <span className="sr-only">{t.revoke}</span>,
                    label: '',
                    align: 'end',
                    render: (x) => (
                      <Button
                        variant="tertiary"
                        aria-label={t.revokeLabel(x.name)}
                        onPress={() => {
                          setSaid('');
                          revoke.reset();
                          setRevoking(x);
                        }}
                      >
                        {t.revoke}
                      </Button>
                    ),
                  },
                ]}
              />
            ) : (
              <Empty>{t.none}</Empty>
            )
          }
        </Loaded>
        <p role="status" className="quiet-success">
          {said ? (
            <>
              <span aria-hidden="true">✓</span> {said}
            </>
          ) : null}
        </p>
        {revoke.isError ? <ProblemView error={revoke.error} compact /> : null}
        <Confirm
          isOpen={revoking !== null}
          onOpenChange={(open) => (open ? undefined : setRevoking(null))}
          title={t.revokeTitle}
          confirmLabel={t.revokeConfirm}
          cancelLabel={t.cancel}
          isPending={revoke.isPending}
          onConfirm={() => (revoking ? revoke.mutate({ id: revoking.id, name: revoking.name }) : undefined)}
        >
          {revoking ? <p>{t.revokeBody(revoking.name, revoking.prefix)}</p> : null}
        </Confirm>
      </Panel>
    </Section>
  );
}

export function Tokens() {
  return (
    <Page title={t.title} description={t.description}>
      <SettingsNav />
      <Grid>
        <List />
        <MakeToken />
      </Grid>
    </Page>
  );
}

export default Tokens;
