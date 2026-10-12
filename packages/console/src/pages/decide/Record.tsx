/**
 * Recording a decision (`decisions.record`; docs/decisions.md, "The decision
 * journal"): asked for, never offered by default; the person's question,
 * the option they chose (none is chosen for them), their reasons in their
 * own words and when to look back. Then a confirmation saying what Salli
 * will do, because an entry can't be edited or deleted.
 */
import { decisionsRecord, type Decision, type DecisionIn, type DecisionStart } from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useState, type FormEvent } from 'react';
import { useWrite } from '../../api';
import { displayDate } from '../../kit/dates';
import { Button, Confirm, Field, RadioField, TextAreaField } from '../../kit/forms';
import { dateInput } from '../../kit/inputs';
import { Panel, Row, Rows } from '../../kit/layout';
import { ProblemView } from '../../kit/Problem';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';
import { strings } from '../../strings';
import { journalPath } from './LabNav';

const r = labStrings.record;

export function RecordDecision({ data }: { data: DecisionStart }) {
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState(data.record.question);
  const [chosen, setChosen] = useState('');
  const [reasons, setReasons] = useState('');
  const [reviewOn, setReviewOn] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);
  const [recorded, setRecorded] = useState<Decision | null>(null);
  const write = useWrite<DecisionIn, Decision>('decisions.record', (api, input) => api.call(decisionsRecord, { body: input }), {
    invalidate: ['decisions.list', 'decisions.reviews.due', 'decisions.export'],
    onSuccess: (decision) => {
      setConfirming(false);
      setRecorded(decision);
    },
  });

  if (recorded) {
    return (
      <Panel>
        <p role="status" className="quiet-success">
          <span aria-hidden="true">✓</span> {r.recorded(displayDate(recorded.entry.review_on, locale))}
        </p>
        <p>
          <Link to={journalPath(recorded.id)} className="strong-link">
            {r.openEntry}
          </Link>
        </p>
      </Panel>
    );
  }

  if (!open) {
    return (
      <Panel>
        <p className="section-help">{r.help}</p>
        <div>
          <Button variant="secondary" onPress={() => setOpen(true)}>
            {r.start}
          </Button>
        </div>
      </Panel>
    );
  }

  const input = (): DecisionIn => ({
    question: question.trim() || data.record.question,
    options: data.record.options,
    chosen,
    reasons: reasons.trim(),
    review_on: reviewOn,
  });

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const found: Record<string, string> = {};
    if (!data.record.labels.includes(chosen)) found.chosen = r.needChoice;
    if (!reasons.trim()) found.reasons = r.needReasons;
    if (!dateInput(reviewOn)) found.review_on = r.needDate;
    setErrors(found);
    if (!Object.keys(found).length) setConfirming(true);
  };

  const serverErrors = write.error ? fieldErrors(write.error) : {};
  const shownErrors = { ...serverErrors, ...errors };

  return (
    <Panel>
      <p className="section-help">{r.help}</p>
      <form className="form" onSubmit={submit} noValidate>
        <Field label={r.question} value={question} onChange={setQuestion} error={shownErrors.question} isRequired />
        <RadioField
          label={r.chosen}
          value={chosen}
          onChange={setChosen}
          error={shownErrors.chosen}
          isRequired
          options={data.record.labels.map((label) => ({ value: label, label }))}
        />
        <TextAreaField label={r.reasons} description={r.reasonsHelp} value={reasons} onChange={setReasons} error={shownErrors.reasons} isRequired />
        <Field
          label={r.reviewOn}
          description={r.reviewOnHelp(displayDate(data.record.earliest_review, locale))}
          type="date"
          value={reviewOn}
          onChange={setReviewOn}
          error={shownErrors.review_on}
          isRequired
          inputProps={{ min: data.record.earliest_review }}
        />
        {Object.keys(errors).length ? (
          <p className="sr-only" role="alert">
            {Object.values(errors).join(' ')}
          </p>
        ) : null}
        {write.isError && !write.stepUpPending ? <ProblemView error={write.error} compact /> : null}
        <div className="form-actions">
          <Button type="submit">{r.submit}</Button>
          <Button variant="tertiary" onPress={() => setOpen(false)}>
            {r.cancel}
          </Button>
        </div>
      </form>
      <Confirm
        isOpen={confirming}
        onOpenChange={setConfirming}
        title={r.confirmTitle}
        confirmLabel={r.confirm}
        cancelLabel={strings.settings.cancel}
        onConfirm={() => write.mutate(input())}
        isPending={write.isPending}
      >
        <Rows>
          <Row label={r.confirmQuestion}>{input().question}</Row>
          <Row label={r.confirmChosen}>{chosen}</Row>
          <Row label={r.confirmReviewOn}>{displayDate(reviewOn, locale)}</Row>
        </Rows>
        <p className="subhead">{r.confirmReasons}</p>
        <p className="own-words">{reasons.trim()}</p>
        <p>{r.confirmBody(displayDate(data.as_of, locale))}</p>
      </Confirm>
    </Panel>
  );
}

/** Salli's problems with a write, by the field they are about (`["body", "reasons"]` → `reasons`). */
export function fieldErrors(error: unknown): Record<string, string> {
  const detail = (error as { detail?: unknown } | null)?.detail;
  const out: Record<string, string> = {};
  if (!Array.isArray(detail)) return out;
  for (const item of detail as Array<{ loc?: unknown; msg?: unknown }>) {
    if (!Array.isArray(item.loc) || typeof item.msg !== 'string') continue;
    const loc = item.loc as Array<string | number>;
    const key = loc[0] === 'body' ? loc[1] : loc[0];
    if (typeof key === 'string' && !(key in out)) out[key] = item.msg;
  }
  return out;
}
