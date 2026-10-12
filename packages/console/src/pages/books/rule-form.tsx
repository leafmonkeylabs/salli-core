/**
 * A categorisation rule, as a form and in words: shared by Rules (add,
 * edit, a suggestion edited first) and the review queue (a rule made from a
 * transaction). The form tests the rule against what is already booked
 * (`rules.test`, nothing stored) and saves it (`rules.create`, or
 * `rules.update` for an edit); Salli's problems are shown at the fields
 * they are about. Amounts are typed in the locale's marks and sent as
 * decimal strings; the order is a whole number of plain digits.
 */
import {
  rulesCreate,
  rulesTest,
  rulesUpdate,
  type Ref,
  type RuleActions,
  type RuleCondition,
  type RuleDraft,
  type RuleTestResult,
} from '@leafmonkeylabs/salli-sdk';
import { useId, useState, type FormEvent } from 'react';
import { useApi, useWrite } from '../../api';
import { bookStrings } from '../../books-strings';
import { displayDate } from '../../kit/dates';
import { Button, CheckboxField, Field, RadioField, SelectField } from '../../kit/forms';
import { amountInput, wholeNumberInput } from '../../kit/inputs';
import { Money } from '../../kit/Money';
import { fieldErrors, ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import type { AccountBook } from './ledger';

const r = bookStrings.rules;

type Field_ = RuleCondition['field'];
type Operator = RuleCondition['operator'];

/** Which comparisons each thing a rule looks at allows. */
export const OPERATORS: Record<Field_, readonly Operator[]> = {
  description: ['contains', 'not_contains', 'equals', 'starts_with', 'ends_with', 'matches'],
  amount: ['equals', 'gt', 'gte', 'lt', 'lte', 'between'],
  direction: ['equals'],
  currency: ['equals'],
};

/** The reads a rule changes: the rules, what review shows as proposed. */
export const RULE_READS = ['rules.list', 'rules.suggestions'];

/** "The description contains FRESHMART". */
export function conditionWords(c: RuleCondition): string {
  const value = c.field === 'direction' ? (r.directions[c.value] ?? c.value) : c.value;
  const operator = c.field === 'direction' ? '' : `${r.operators[c.operator] ?? c.operator} `;
  const field = c.field === 'direction' ? '' : `${r.fields[c.field] ?? c.field} `;
  const tail = c.operator === 'between' && c.value2 ? ` ${r.value2.toLowerCase()} ${c.value2}` : '';
  return `${field}${operator}${value}${tail}`.trim();
}

/** "Goes to Groceries, category groceries, need essential". */
export function actionWords(actions: RuleActions, book: AccountBook | undefined): string {
  const parts: string[] = [];
  if (actions.account_id) parts.push(r.goesTo(book ? book.label(actions.account_id) : actions.account_id));
  if (actions.category) parts.push(r.categoryIs(actions.category));
  if (actions.need) parts.push(r.needIs((r.needs[actions.need] ?? actions.need).toLowerCase()));
  if (actions.description) parts.push(r.bookedAs(actions.description));
  return parts.join(', ');
}

interface ConditionDraft {
  field: Field_;
  operator: Operator;
  value: string;
  value2: string;
}

export interface RuleStart {
  /** The rule being edited, if one is. */
  id?: string;
  name: string;
  conditions: RuleCondition[];
  actions: RuleActions;
  priority?: number;
  match_all?: boolean;
  enabled?: boolean;
}

function draftOf(c: RuleCondition): ConditionDraft {
  return { field: c.field, operator: c.operator, value: c.value, value2: c.value2 ?? '' };
}

function TestResult({ result, book }: { result: RuleTestResult; book: AccountBook }) {
  const locale = useLocale();
  return (
    <div className="stack-tight">
      <p role="status">{r.tested(result.total, result.agreeing)}</p>
      {result.matches.length ? (
        <Table
          caption={r.testTable}
          rows={result.matches}
          rowKey={(m) => m.entry_id}
          columns={[
            { key: 'date', header: r.date, label: r.date, render: (m) => displayDate(m.entry_date, locale) },
            { key: 'description', header: r.description_, label: r.description_, render: (m) => m.description },
            { key: 'booked', header: r.bookedTo, label: r.bookedTo, render: (m) => book.label(m.account_id) },
            {
              key: 'amount',
              header: r.amount,
              label: r.amount,
              align: 'end',
              render: (m) => (
                <>
                  <Money amount={m.amount} currency={m.currency} variant="table" withCode /> {m.direction === 'out' ? bookStrings.review.out : bookStrings.review.in}
                </>
              ),
            },
          ]}
        />
      ) : null}
    </div>
  );
}

export function RuleForm({
  book,
  start,
  onSaved,
  onCancel,
}: {
  book: AccountBook;
  start: RuleStart;
  onSaved: (name: string, id: string) => void;
  onCancel?: () => void;
}) {
  const api = useApi();
  const locale = useLocale();
  const formId = useId();
  const [name, setName] = useState(start.name);
  const [matchAll, setMatchAll] = useState(start.match_all ?? true);
  const [conditions, setConditions] = useState<ConditionDraft[]>(start.conditions.length ? start.conditions.map(draftOf) : [{ field: 'description', operator: 'contains', value: '', value2: '' }]);
  const [account, setAccount] = useState(start.actions.account_id ?? '');
  const [category, setCategory] = useState(start.actions.category ?? '');
  const [need, setNeed] = useState<string>(start.actions.need ?? '');
  const [description, setDescription] = useState(start.actions.description ?? '');
  const [priority, setPriority] = useState(String(start.priority ?? 100));
  const [enabled, setEnabled] = useState(start.enabled ?? true);
  const [local, setLocal] = useState<Record<string, string>>({});
  const [test, setTest] = useState<{ pending: boolean; result?: RuleTestResult; error?: unknown }>({ pending: false });

  const save = useWrite<{ id?: string; draft: RuleDraft }, Ref>(
    'rules.save',
    (client, input) => (input.id ? client.call(rulesUpdate, { path: { rule_id: input.id }, body: input.draft }) : client.call(rulesCreate, { body: input.draft })),
    { invalidate: RULE_READS, onSuccess: (ref, input) => onSaved(input.draft.name, ref.id) },
  );

  const active = book.accounts.filter((a) => a.is_active);
  const set = (i: number, change: Partial<ConditionDraft>): void =>
    setConditions((list) =>
      list.map((c, j) => {
        if (j !== i) return c;
        const next = { ...c, ...change };
        if (change.field) {
          next.operator = OPERATORS[change.field][0] ?? 'equals';
          next.value = change.field === 'direction' ? 'out' : '';
          next.value2 = '';
        }
        return next;
      }),
    );

  /** The rule as the API takes it, or the problems found, by field. */
  const read = (): { draft?: RuleDraft; problems: Record<string, string> } => {
    const problems: Record<string, string> = {};
    if (!name.trim()) problems.name = r.nameMissing;
    const parsed: RuleCondition[] = conditions.map((c, i) => {
      let value = c.value.trim();
      let value2 = c.value2.trim();
      if (!value) problems[`conditions.${i}.value`] = r.valueMissing;
      if (c.field === 'amount') {
        const a = value ? amountInput(value, locale) : undefined;
        if (value && !a) problems[`conditions.${i}.value`] = r.amountInvalid;
        value = a ?? value;
        if (c.operator === 'between') {
          const b = value2 ? amountInput(value2, locale) : undefined;
          if (!b) problems[`conditions.${i}.value2`] = value2 ? r.amountInvalid : r.valueMissing;
          value2 = b ?? value2;
        }
      }
      if (c.field === 'currency') value = value.toUpperCase();
      return { field: c.field, operator: c.operator, value, ...(c.operator === 'between' ? { value2 } : {}) };
    });
    const order = wholeNumberInput(priority);
    if (order === undefined) problems.priority = r.priorityInvalid;
    const actions: RuleActions = {
      ...(account ? { account_id: account } : {}),
      ...(category.trim() ? { category: category.trim() } : {}),
      ...(need ? { need: need as NonNullable<RuleActions['need']> } : {}),
      ...(description.trim() ? { description: description.trim() } : {}),
    };
    if (Object.keys(problems).length) return { problems };
    return { draft: { name: name.trim(), conditions: parsed, actions, priority: order ?? 100, match_all: matchAll, enabled }, problems };
  };

  const runTest = async (): Promise<void> => {
    const { draft, problems } = read();
    setLocal(problems);
    if (!draft) return;
    setTest({ pending: true });
    try {
      setTest({ pending: false, result: await api.call(rulesTest, { body: draft }) });
    } catch (error) {
      setTest({ pending: false, error });
    }
  };

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const { draft, problems } = read();
    setLocal(problems);
    if (!draft) return;
    save.mutate({ ...(start.id ? { id: start.id } : {}), draft });
  };

  const server = save.isError ? fieldErrors(save.error) : test.error ? fieldErrors(test.error) : {};
  const errors: Record<string, string> = { ...server, ...local };
  const accountOptions = [{ value: '', label: r.accountNone }, ...active.map((a) => ({ value: a.id, label: `${a.code} ${a.name}` }))];

  return (
    <form className="form form-wide rule-form" onSubmit={submit} noValidate aria-describedby={`${formId}-help`}>
      <p id={`${formId}-help`} className="section-help">
        {r.formHelp}
      </p>
      <div className="field-grid">
        <Field label={r.name} value={name} onChange={setName} error={errors.name} isRequired />
        <RadioField
          label={r.matchAll}
          value={matchAll ? 'all' : 'any'}
          onChange={(v) => setMatchAll(v === 'all')}
          options={[
            { value: 'all', label: r.matchAllChoices.all ?? 'all' },
            { value: 'any', label: r.matchAllChoices.any ?? 'any' },
          ]}
        />
      </div>
      <ol className="conditions">
        {conditions.map((c, i) => (
          <li key={i} className="condition">
            <fieldset className="field-grid condition-fields">
              <legend className="subhead">{r.condition(i + 1)}</legend>
              <SelectField
                label={r.field}
                value={c.field}
                onChange={(v) => set(i, { field: v as Field_ })}
                options={(Object.keys(OPERATORS) as Field_[]).map((f) => ({ value: f, label: r.fields[f] ?? f }))}
              />
              {c.field === 'direction' ? (
                <SelectField
                  label={r.value}
                  value={c.value || 'out'}
                  onChange={(v) => set(i, { value: v })}
                  options={['in', 'out'].map((v) => ({ value: v, label: r.directions[v] ?? v }))}
                />
              ) : (
                <>
                  <SelectField
                    label={r.operator}
                    value={c.operator}
                    onChange={(v) => set(i, { operator: v as Operator })}
                    options={OPERATORS[c.field].map((o) => ({ value: o, label: r.operators[o] ?? o }))}
                  />
                  <Field
                    label={r.value}
                    value={c.value}
                    onChange={(v) => set(i, { value: v })}
                    error={errors[`conditions.${i}.value`] ?? errors[`conditions.${i}`]}
                    isRequired
                    inputProps={{ spellCheck: false, ...(c.field === 'amount' ? { inputMode: 'decimal' as const } : {}) }}
                  />
                  {c.operator === 'between' ? (
                    <Field
                      label={r.value2}
                      value={c.value2}
                      onChange={(v) => set(i, { value2: v })}
                      error={errors[`conditions.${i}.value2`]}
                      isRequired
                      inputProps={{ inputMode: 'decimal' }}
                    />
                  ) : null}
                </>
              )}
            </fieldset>
            {conditions.length > 1 ? (
              <Button variant="tertiary" onPress={() => setConditions((list) => list.filter((_, j) => j !== i))}>
                {r.removeCondition(i + 1)}
              </Button>
            ) : null}
          </li>
        ))}
      </ol>
      <div>
        <Button variant="secondary" onPress={() => setConditions((list) => [...list, { field: 'description', operator: 'contains', value: '', value2: '' }])}>
          {r.addCondition}
        </Button>
      </div>
      <div className="field-grid">
        <SelectField label={r.account} description={r.accountHelp} value={account} onChange={setAccount} options={accountOptions} error={errors['actions.account_id'] ?? errors.actions} />
        <Field label={r.category} description={r.categoryHelp} value={category} onChange={setCategory} error={errors['actions.category']} />
        <SelectField
          label={r.needField}
          value={need}
          onChange={setNeed}
          options={[{ value: '', label: r.needNone }, ...['essential', 'discretionary', 'savings'].map((n) => ({ value: n, label: r.needs[n] ?? n }))]}
        />
        <Field label={r.bookAs} description={r.bookAsHelp} value={description} onChange={setDescription} error={errors['actions.description']} />
        <Field label={r.priority} description={r.priorityHelp} value={priority} onChange={setPriority} error={errors.priority} inputProps={{ inputMode: 'numeric' }} />
        <CheckboxField label={r.enabled} checked={enabled} onChange={setEnabled} />
      </div>
      {Object.keys(local).length ? (
        <p className="sr-only" role="alert">
          {Object.values(local).join(' ')}
        </p>
      ) : null}
      {save.isError ? <ProblemView error={save.error} compact /> : null}
      {test.error ? <ProblemView error={test.error} compact /> : null}
      <div className="form-actions">
        <Button variant="secondary" onPress={() => void runTest()} isPending={test.pending}>
          {test.pending ? r.testing : r.test}
        </Button>
        <Button type="submit" isPending={save.isPending}>
          {save.isPending ? r.saving : r.save}
        </Button>
        {onCancel ? (
          <Button variant="tertiary" onPress={onCancel}>
            {r.stopEditing}
          </Button>
        ) : null}
      </div>
      {test.result ? <TestResult result={test.result} book={book} /> : null}
    </form>
  );
}
