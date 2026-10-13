/**
 * Your data (`exports.beancount`, `exports.hledger`, `account.export`;
 * `salli export`): the books as plain text for Beancount or hledger, and
 * everything Salli keeps as one JSON file, each saved on this device as the
 * API answered it (amounts exact: the JSON is written with the SDK's exact
 * writer, never through a float). A blob URL, which the CSP allows, and
 * nothing sent anywhere.
 */
import { accountExport, exportsBeancount, exportsHledger, toJsonText } from '@leafmonkeylabs/salli-sdk';
import { useState } from 'react';
import { useApi } from '../../api';
import { isoDate } from '../../kit/dates';
import { saveText, textOf } from '../../kit/download';
import { Button } from '../../kit/forms';
import { Grid, Page, Panel, Section } from '../../kit/layout';
import { ProblemView } from '../../kit/Problem';
import { settingsStrings } from '../../settings-strings';
import { SettingsNav } from './nav';

const t = settingsStrings.data;

type Kind = 'beancount' | 'hledger' | 'json';

export function Data() {
  const api = useApi();
  const [busy, setBusy] = useState<Kind | null>(null);
  const [saved, setSaved] = useState('');
  const [error, setError] = useState<unknown>(null);
  const today = isoDate(new Date());

  const save = async (kind: Kind): Promise<void> => {
    setBusy(kind);
    setSaved('');
    setError(null);
    try {
      let name: string;
      if (kind === 'json') {
        name = `salli-${today}.json`;
        saveText(name, `${toJsonText(await api.call(accountExport))}\n`, 'application/json');
      } else if (kind === 'beancount') {
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
            <div className="form-actions">
              <Button variant="secondary" onPress={() => void save('json')} isPending={busy === 'json'}>
                {busy === 'json' ? t.saving : t.json}
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
            ) : null}
          </p>
          {error ? <ProblemView error={error} compact /> : null}
        </div>
      </Grid>
    </Page>
  );
}

export default Data;
