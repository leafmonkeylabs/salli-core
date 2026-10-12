/**
 * The decision journal (`decisions.list`, `decisions.reviews.due`,
 * `decisions.export`, `decisions.exportMarkdown`; docs/decisions.md): what
 * the person decided, newest first, with each entry's status; what is due
 * for review; and the whole journal saved on this device, as JSON (every
 * document exactly as recorded, with its hash) or Markdown to read.
 */
import { decisionsExport, decisionsExportMarkdown, decisionsList, toJsonText, type DecisionSummary } from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useState } from 'react';
import { useApi, useRead } from '../../api';
import { displayDate, isoDate } from '../../kit/dates';
import { saveText, textOf } from '../../kit/download';
import { Empty, Loaded, Page, Panel, Section } from '../../kit/layout';
import { ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';
import { DueReviews } from './Due';
import { journalPath, LabNav } from './LabNav';

const j = labStrings.journal;

function Export() {
  const api = useApi();
  const [busy, setBusy] = useState<'json' | 'markdown' | null>(null);
  const [saved, setSaved] = useState('');
  const [error, setError] = useState<unknown>(null);
  const save = async (format: 'json' | 'markdown'): Promise<void> => {
    setBusy(format);
    setError(null);
    setSaved('');
    try {
      const day = isoDate(new Date());
      if (format === 'json') {
        const name = `salli-decisions-${day}.json`;
        saveText(name, `${toJsonText(await api.call(decisionsExport))}\n`, 'application/json');
        setSaved(j.exported(name));
      } else {
        const name = `salli-decisions-${day}.md`;
        saveText(name, textOf(await api.call(decisionsExportMarkdown, { parseAs: 'text' })), 'text/markdown');
        setSaved(j.exported(name));
      }
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(null);
    }
  };
  return (
    <Panel>
      <p className="section-help">{j.exportHelp}</p>
      <div className="form-actions">
        <button type="button" className="button button-secondary" onClick={() => void save('json')} disabled={busy !== null}>
          {busy === 'json' ? j.exporting : j.exportJson}
        </button>
        <button type="button" className="button button-secondary" onClick={() => void save('markdown')} disabled={busy !== null}>
          {busy === 'markdown' ? j.exporting : j.exportMarkdown}
        </button>
      </div>
      <p role="status" className="quiet-success">
        {saved ? (
          <>
            <span aria-hidden="true">✓</span> {saved}
          </>
        ) : null}
      </p>
      {error ? <ProblemView error={error} compact /> : null}
    </Panel>
  );
}

export function Journal() {
  const locale = useLocale();
  const query = useRead('decisions.list', decisionsList);
  return (
    <Page title={j.title} description={j.description}>
      <LabNav />
      <div className="grid">
        <Section label={j.entries} full>
          <Panel>
            <Loaded query={query}>
              {({ decisions }) =>
                decisions.length ? (
                  <Table<DecisionSummary>
                    caption={j.entries}
                    captionHidden
                    rows={decisions}
                    rowKey={(d) => d.id}
                    columns={[
                      {
                        key: 'question',
                        header: j.question,
                        label: j.question,
                        render: (d) => (
                          <>
                            <Link to={journalPath(d.id)}>{d.question}</Link>
                            {d.notes ? <span className="muted"> · {j.notesCount(d.notes)}</span> : null}
                          </>
                        ),
                      },
                      { key: 'recorded', header: j.recorded, label: j.recorded, render: (d) => displayDate(d.recorded_at, locale) },
                      { key: 'chosen', header: j.chosen, label: j.chosen, render: (d) => d.chosen },
                      { key: 'review', header: j.reviewOn, label: j.reviewOn, render: (d) => displayDate(d.review_on, locale) },
                      {
                        key: 'status',
                        header: j.status,
                        label: j.status,
                        render: (d) => <span className={d.status === 'review_due' ? 'tag tag-due' : 'tag'}>{j.statuses[d.status] ?? d.status}</span>,
                      },
                    ]}
                  />
                ) : (
                  <Empty>{j.none}</Empty>
                )
              }
            </Loaded>
          </Panel>
        </Section>
        <Section label={labStrings.dueTitle}>
          <Panel>
            <DueReviews />
          </Panel>
        </Section>
        <Section label={j.export} wide>
          <Export />
        </Section>
      </div>
    </Page>
  );
}

export default Journal;
