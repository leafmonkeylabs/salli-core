/**
 * A panel, drawn (`salli.panel/1`): sections of text, link, action and form
 * rows, then the document's note. It renders only what the server sent: a
 * link opens in a new tab, an action asks first when the server gave words to
 * ask with, a form sends what was typed, and a refusal shows in the row that
 * asked. What an action does afterwards (`then`) is the page's to carry out.
 */
import { formBody, missingFields, type Panel, type PanelField, type PanelRow, type PanelSection } from '@leafmonkeylabs/salli-sdk';
import { useState } from 'react';
import { useWrite } from '../api';
import { strings } from '../strings';
import { Button, Confirm, Field, SelectField } from './forms';
import { Panel as Card, Section } from './layout';
import { ProblemView } from './Problem';

type After = (then: 'refresh' | 'close') => void;
const t = strings.panel;
const READS = ['panels.get', 'panels.list'];

export function PanelView({ panel, after }: { panel: Panel; after: After }) {
  return (
    <>
      <div className="grid">
        {panel.sections.map((section, i) => (
          <PanelSectionView key={i} section={section} after={after} />
        ))}
      </div>
      {panel.note ? <p className="panel-note">{panel.note}</p> : null}
    </>
  );
}

function PanelSectionView({ section, after }: { section: PanelSection; after: After }) {
  if (!section.rows.length && !section.heading) return null;
  const rows = (
    <Card>
      <ul className="list panel-rows">
        {section.rows.map((row, i) => (
          <li key={i}>
            <RowView row={row} after={after} />
          </li>
        ))}
      </ul>
      {section.footnote ? <p className="muted">{section.footnote}</p> : null}
    </Card>
  );
  return section.heading ? (
    <Section label={section.heading}>{rows}</Section>
  ) : (
    <section className="section">{rows}</section>
  );
}

function RowView({ row, after }: { row: PanelRow; after: After }) {
  switch (row.kind) {
    case 'text':
      return (
        <p className="panel-text">
          <span>{row.label}</span>
          {row.value ? <span className="muted">{row.value}</span> : null}
        </p>
      );
    case 'link':
      return (
        <a className="strong-link" href={row.url} target="_blank" rel="noopener noreferrer">
          {row.label}
          <span className="sr-only"> ({t.opensNewTab})</span>
          {row.detail ? <span className="muted panel-detail">{row.detail}</span> : null}
        </a>
      );
    case 'action':
      return <ActionRow row={row} after={after} />;
    case 'form':
      return <FormRow row={row} after={after} />;
  }
}

type Send = { method: 'POST' | 'DELETE'; path: string; body?: Record<string, unknown> };

function useSend(then: 'refresh' | 'close', after: After) {
  return useWrite<Send, unknown>('panels.act', (api, input) => api.send(input), { invalidate: READS, onSuccess: () => after(then) });
}

function ActionRow({ row, after }: { row: Extract<PanelRow, { kind: 'action' }>; after: After }) {
  const send = useSend(row.action.then, after);
  const [asking, setAsking] = useState(false);
  const go = (): void => {
    setAsking(false);
    send.mutate({ method: row.action.method, path: row.action.path, ...(row.action.body ? { body: row.action.body } : {}) });
  };
  return (
    <div className="panel-action">
      {row.detail ? <p>{row.detail}</p> : null}
      <Button variant={row.action.method === 'DELETE' ? 'secondary' : 'primary'} isPending={send.isPending} onPress={() => (row.confirm ? setAsking(true) : go())}>
        {row.label}
      </Button>
      {send.isError ? <ProblemView error={send.error} compact onRetry={() => (row.confirm ? setAsking(true) : go())} /> : null}
      {row.confirm ? (
        <Confirm isOpen={asking} onOpenChange={setAsking} title={row.confirm} confirmLabel={row.label} cancelLabel={t.notNow} onConfirm={go} isPending={send.isPending}>
          {null}
        </Confirm>
      ) : null}
    </div>
  );
}

function FormRow({ row, after }: { row: Extract<PanelRow, { kind: 'form' }>; after: After }) {
  const send = useSend(row.submit.then, after);
  const [values, setValues] = useState<Record<string, string>>({});
  const [tried, setTried] = useState(false);
  const missing = missingFields(row.fields, values);
  return (
    <form
      className="form"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        setTried(true);
        if (missing.length) return;
        send.mutate({ method: row.submit.method, path: row.submit.path, body: formBody(row.fields, values) });
      }}
    >
      <h3 className="panel-form-title">{row.label}</h3>
      {row.fields.map((field) => (
        <FieldView
          key={field.name}
          field={field}
          value={values[field.name] ?? ''}
          onChange={(v) => setValues((now) => ({ ...now, [field.name]: v }))}
          error={tried && missing.includes(field.name) ? t.required : undefined}
        />
      ))}
      <Button type="submit" isPending={send.isPending}>
        {row.submit.label}
      </Button>
      {send.isError ? <ProblemView error={send.error} compact /> : null}
    </form>
  );
}

function FieldView({ field, value, onChange, error }: { field: PanelField; value: string; onChange: (value: string) => void; error: string | undefined }) {
  if (field.type === 'select') {
    return (
      <SelectField
        label={field.label}
        value={value}
        onChange={onChange}
        isRequired={field.required}
        error={error}
        options={[{ value: '', label: t.choose }, ...(field.options ?? []).map((o) => ({ value: o, label: o }))]}
      />
    );
  }
  return <Field label={field.label} value={value} onChange={onChange} isRequired={field.required} error={error} inputProps={field.type === 'number' ? { inputMode: 'decimal' } : {}} />;
}
