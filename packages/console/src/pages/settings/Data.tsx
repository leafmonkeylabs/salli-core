/**
 * Your data (`exports.beancount`, `exports.hledger`, `account.export`;
 * `salli export`): the books as plain text for Beancount or hledger, and
 * everything Salli keeps as one JSON file, each saved on this device as the
 * API answered it (amounts exact: the JSON is written with the SDK's exact
 * writer, never through a float). A blob URL, which the CSP allows, and
 * nothing sent anywhere. Everything, like deleting the account, needs the
 * password entered in the last five minutes: past that, the step-up, and the
 * file is saved on the way back. The JSON also takes the authenticator code
 * (`Salli-Two-Step`) when two-step sign-in is on, and always for the owner.
 */
import { accountExport, exportsBeancount, exportsHledger, toJsonText } from '@leafmonkeylabs/salli-sdk';
import { useState } from 'react';
import { useApi, useWrite } from '../../api';
import { isoDate } from '../../kit/dates';
import { saveText, textOf } from '../../kit/download';
import { Button, TextField } from '../../kit/forms';
import { Grid, Page, Panel, Section } from '../../kit/layout';
import { ProblemView } from '../../kit/Problem';
import { settingsStrings } from '../../settings-strings';
import { strings } from '../../strings';
import { SettingsNav } from './nav';

const t = settingsStrings.data;

type Kind = 'beancount' | 'hledger' | 'json';

export function Data() {
  const api = useApi();
  const [busy, setBusy] = useState<Kind | null>(null);
  const [saved, setSaved] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [code, setCode] = useState('');
  const today = isoDate(new Date());
  const everything = useWrite<null, string>(
    'account.export',
    async (client) => {
      const name = `salli-${isoDate(new Date())}.json`;
      const step = code.trim() ? { headers: { 'Salli-Two-Step': code.trim() } } : {};
      saveText(name, `${toJsonText(await client.call(accountExport, step))}\n`, 'application/json');
      return name;
    },
    { onSuccess: (name) => setSaved(t.savedFile(name)) },
  );

  const save = async (kind: Kind): Promise<void> => {
    setSaved('');
    setError(null);
    if (kind === 'json') {
      everything.mutate(null);
      return;
    }
    setBusy(kind);
    try {
      let name: string;
      if (kind === 'beancount') {
        name = `salli-${today}.beancount`;
        saveText(name, textOf(await api.call(exportsBeancount, { parseAs: 'text' })), 'text/plain');
      } else {
        name = `salli-${today}.journal`;
        saveText(name, textOf(await api.call(exportsHledger, { parseAs: 'text' })), 'text/plain');
      }
      setSaved(t.savedFile(name));
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Page title={t.title} description={t.description}>
      <SettingsNav />
      <Grid>
        <Section label={t.plain}>
          <Panel>
            <p className="section-help">{t.plainHelp}</p>
            <div className="form-actions">
              <Button variant="secondary" onPress={() => void save('beancount')} isPending={busy === 'beancount'}>
                {busy === 'beancount' ? t.saving : t.beancount}
              </Button>
              <Button variant="secondary" onPress={() => void save('hledger')} isPending={busy === 'hledger'}>
                {busy === 'hledger' ? t.saving : t.hledger}
              </Button>
            </div>
          </Panel>
        </Section>
        <Section label={t.everything}>
          <Panel>
            <p className="section-help">{t.everythingHelp}</p>
            <TextField
              label={t.code}
              description={t.codeHelp}
              value={code}
              onChange={setCode}
              inputProps={{ autoComplete: 'one-time-code', inputMode: 'numeric', spellCheck: false }}
            />
            <div className="form-actions">
              <Button variant="secondary" onPress={() => void save('json')} isPending={everything.isPending}>
                {everything.isPending ? t.saving : t.json}
              </Button>
            </div>
          </Panel>
        </Section>
        <div className="status-line">
          <p role="status" className="quiet-success">
            {saved ? (
              <>
                <span aria-hidden="true">✓</span> {saved}
              </>
            ) : everything.stepUpPending ? (
              strings.signIn.redirecting
            ) : null}
          </p>
          {error ? <ProblemView error={error} compact /> : null}
          {everything.isError && !everything.stepUpPending ? <ProblemView error={everything.error} compact /> : null}
        </div>
      </Grid>
    </Page>
  );
}

export default Data;
