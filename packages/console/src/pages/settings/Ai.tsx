/**
 * AI connections (`mcp.enabled.get`, `.set`, `mcp.connections.list`,
 * `.revoke`, `llmKeys.list`, `.set`, `.delete`, `ai.settings.get`; `salli
 * mcp`, `salli llm-keys`): whether AI clients may use Salli over MCP at all
 * (turning it off asks first), each connected client with a way to revoke
 * it (asking first), and the person's own model keys.
 *
 * A key is typed into a password field, sent once and never shown again:
 * Salli answers only its last four characters. The write is `secret:
 * 'input'`: the key never waits in sessionStorage for a step-up, the field
 * is emptied once Salli has it, and no cached write outlives the page.
 */
import {
  aiSettingsGet,
  llmKeysDelete,
  llmKeysList,
  llmKeysSet,
  mcpConnectionsList,
  mcpConnectionsRevoke,
  mcpEnabledGet,
  mcpEnabledSet,
  type LlmKeyStatus,
  type McpConnection,
} from '@leafmonkeylabs/salli-sdk';
import { useEffect, useState, type FormEvent } from 'react';
import { useRead, useWrite } from '../../api';
import { displayDate, displayMoment } from '../../kit/dates';
import { Button, Confirm, Field } from '../../kit/forms';
import { Empty, Grid, Loaded, Page, Panel, Section } from '../../kit/layout';
import { ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { settingsStrings } from '../../settings-strings';
import { SettingsNav } from './nav';

const t = settingsStrings.ai;
type Provider = 'anthropic' | 'openai';
const PROVIDERS: Provider[] = ['anthropic', 'openai'];
const KEY_READS = ['llmKeys.list', 'ai.settings.get'];

function Mcp() {
  const query = useRead('mcp.enabled.get', mcpEnabledGet);
  const [asking, setAsking] = useState(false);
  const [said, setSaid] = useState('');
  const set = useWrite<{ enabled: boolean }, unknown>('mcp.enabled.set', (api, input) => api.call(mcpEnabledSet, { body: { enabled: input.enabled } }), {
    invalidate: ['mcp.enabled.get', 'profile.get'],
    onSuccess: (_, input) => {
      setAsking(false);
      setSaid(input.enabled ? t.turnedOn : t.turnedOff);
    },
  });
  return (
    <Section label={t.mcp}>
      <Panel>
        <p className="section-help">{t.mcpHelp}</p>
        <Loaded query={query}>
          {({ enabled }) => (
            <div className="stack-tight">
              <p className="signal-title">
                <span className={enabled ? 'tag' : 'tag tag-warn'}>{enabled ? t.mcpOn : t.mcpOff}</span>
              </p>
              <div className="form-actions">
                {enabled ? (
                  <Button
                    variant="secondary"
                    onPress={() => {
                      setSaid('');
                      setAsking(true);
                    }}
                  >
                    {t.turnOff}
                  </Button>
                ) : (
                  <Button
                    onPress={() => {
                      setSaid('');
                      set.mutate({ enabled: true });
                    }}
                    isPending={set.isPending}
                  >
                    {t.turnOn}
                  </Button>
                )}
                <p role="status" className="quiet-success">
                  {said ? (
                    <>
                      <span aria-hidden="true">✓</span> {said}
                    </>
                  ) : null}
                </p>
              </div>
            </div>
          )}
        </Loaded>
        {set.isError ? <ProblemView error={set.error} compact /> : null}
        <Confirm
          isOpen={asking}
          onOpenChange={setAsking}
          title={t.offTitle}
          confirmLabel={t.offConfirm}
          cancelLabel={t.cancel}
          isPending={set.isPending}
          onConfirm={() => set.mutate({ enabled: false })}
        >
          <p>{t.offBody}</p>
        </Confirm>
      </Panel>
    </Section>
  );
}

function Clients() {
  const locale = useLocale();
  const query = useRead('mcp.connections.list', mcpConnectionsList);
  const [revoking, setRevoking] = useState<McpConnection | null>(null);
  const [said, setSaid] = useState('');
  const revoke = useWrite<{ id: string; name: string }, unknown>('mcp.connections.revoke', (api, input) => api.call(mcpConnectionsRevoke, { path: { token_id: input.id } }), {
    invalidate: ['mcp.connections.list'],
    onSuccess: (_, input) => {
      setRevoking(null);
      setSaid(t.disconnected(input.name));
    },
  });
  return (
    <Section label={t.clients}>
      <Panel>
        <p className="section-help">{t.clientsHelp}</p>
        <Loaded query={query}>
          {({ connections }) =>
            connections.length ? (
              <Table<McpConnection>
                caption={t.clients}
                captionHidden
                rows={connections}
                rowKey={(c) => c.token_id}
                columns={[
                  { key: 'client', header: t.client, label: t.client, render: (c) => c.client_name },
                  { key: 'connected', header: t.connected, label: t.connected, render: (c) => displayMoment(c.connected_at, locale) },
                  { key: 'scope', header: t.scope, label: t.scope, render: (c) => <code className="mono">{c.scope}</code> },
                  {
                    key: 'revoke',
                    header: <span className="sr-only">{t.disconnect}</span>,
                    label: '',
                    align: 'end',
                    render: (c) => (
                      <Button
                        variant="tertiary"
                        aria-label={t.disconnectLabel(c.client_name)}
                        onPress={() => {
                          setSaid('');
                          revoke.reset();
                          setRevoking(c);
                        }}
                      >
                        {t.disconnect}
                      </Button>
                    ),
                  },
                ]}
              />
            ) : (
              <Empty>{t.noClients}</Empty>
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
          title={t.disconnectTitle}
          confirmLabel={t.disconnectConfirm}
          cancelLabel={t.cancel}
          isPending={revoke.isPending}
          onConfirm={() => (revoking ? revoke.mutate({ id: revoking.token_id, name: revoking.client_name }) : undefined)}
        >
          {revoking ? <p>{t.disconnectBody(revoking.client_name)}</p> : null}
        </Confirm>
      </Panel>
    </Section>
  );
}

/** One provider's key: what is stored (its last four), or a field to set one. */
function KeyRow({ provider, stored, onSaid }: { provider: Provider; stored: LlmKeyStatus | undefined; onSaid: (text: string) => void }) {
  const locale = useLocale();
  const label = t.providers[provider] ?? provider;
  // The key as typed: only in this field, emptied once Salli has it.
  const [key, setKey] = useState('');
  const [missing, setMissing] = useState('');
  const [removing, setRemoving] = useState(false);
  const save = useWrite<{ provider: Provider; key: string }, unknown>(
    'llmKeys.set',
    (api, input) => api.call(llmKeysSet, { path: { provider: input.provider }, body: { key: input.key } }),
    {
      secret: 'input',
      invalidate: KEY_READS,
      onSuccess: () => {
        setKey('');
        onSaid(t.saved(label));
      },
    },
  );
  const remove = useWrite<{ provider: Provider }, unknown>('llmKeys.delete', (api, input) => api.call(llmKeysDelete, { path: { provider: input.provider } }), {
    invalidate: KEY_READS,
    onSuccess: () => {
      setRemoving(false);
      onSaid(t.removed(label));
    },
  });
  // Once Salli has the key, forget the write that carried it.
  const { isSuccess, reset } = save;
  useEffect(() => {
    if (isSuccess) reset();
  }, [isSuccess, reset]);

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!key.trim()) {
      setMissing(t.keyMissing);
      return;
    }
    setMissing('');
    onSaid('');
    save.mutate({ provider, key: key.trim() });
  };

  return (
    <li className="stack-tight key-row">
      <h3 className="subhead">{label}</h3>
      {stored ? (
        <>
          <p>
            {t.stored(stored.last4)}, {stored.validated_at ? t.checked(displayDate(stored.validated_at, locale)) : t.notChecked}.
          </p>
          {!stored.readable ? <p className="warn-line">{t.unreadable}</p> : null}
          <div className="form-actions">
            <Button
              variant="tertiary"
              onPress={() => {
                onSaid('');
                setRemoving(true);
              }}
            >
              {t.remove(label)}
            </Button>
          </div>
        </>
      ) : (
        <p className="muted">{t.noKey}</p>
      )}
      <form className="form form-inline" onSubmit={submit} noValidate>
        <Field
          label={t.keyField(label)}
          description={t.keyHelp}
          type="password"
          value={key}
          onChange={setKey}
          error={missing}
          inputProps={{ autoComplete: 'off', spellCheck: false }}
        />
        <div className="form-actions">
          <Button type="submit" variant="secondary" isPending={save.isPending}>
            {save.isPending ? t.saving : t.save(label)}
          </Button>
        </div>
      </form>
      {save.isError ? <ProblemView error={save.error} compact /> : null}
      {remove.isError ? <ProblemView error={remove.error} compact /> : null}
      <Confirm
        isOpen={removing}
        onOpenChange={setRemoving}
        title={t.removeTitle(label)}
        confirmLabel={t.removeConfirm}
        cancelLabel={t.cancel}
        isPending={remove.isPending}
        onConfirm={() => remove.mutate({ provider })}
      >
        <p>{t.removeBody(label)}</p>
      </Confirm>
    </li>
  );
}

function Keys() {
  const keys = useRead('llmKeys.list', llmKeysList);
  const settings = useRead('ai.settings.get', aiSettingsGet);
  const [said, setSaid] = useState('');
  return (
    <Section label={t.keys} full>
      <Panel>
        <p className="section-help">{t.keysHelp}</p>
        <Loaded query={keys}>
          {(data) =>
            data.available ? (
              <div className="stack-tight">
                {settings.data ? (
                  <p>{t.using(t.providers[settings.data.active.provider] ?? settings.data.active.provider, t.sources[settings.data.active.source] ?? settings.data.active.source)}</p>
                ) : null}
                <ul className="list">
                  {PROVIDERS.map((provider) => (
                    <KeyRow key={provider} provider={provider} stored={data.keys.find((k) => k.provider === provider)} onSaid={setSaid} />
                  ))}
                </ul>
                <p role="status" className="quiet-success">
                  {said ? (
                    <>
                      <span aria-hidden="true">✓</span> {said}
                    </>
                  ) : null}
                </p>
              </div>
            ) : (
              <p className="muted">{t.keysUnavailable}</p>
            )
          }
        </Loaded>
      </Panel>
    </Section>
  );
}

export function Ai() {
  return (
    <Page title={t.title} description={t.description}>
      <SettingsNav />
      <Grid>
        <Mcp />
        <Clients />
        <Keys />
      </Grid>
    </Page>
  );
}

export default Ai;
