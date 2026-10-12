/**
 * A template's questions as a form, built from its question schema
 * (`decisions.templates.get`): each question a labelled input of its type,
 * its help and its default with where the default comes from, and any
 * problem at its path, Salli's or the form's. Questions that depend on
 * another appear once it is answered so.
 */
import type { DecisionTemplate, TemplateQuestion } from '@leafmonkeylabs/salli-sdk';
import type { ReactNode } from 'react';
import { Field, RadioField, SelectField } from '../../kit/forms';
import { labStrings } from '../../lab-strings';
import { allowed, applies, emptyLoan, emptySplit, type Errors, type FormState, type LoanState, type SplitState } from './answers';

const t = labStrings.templates;

/** What the person's own debts, accounts, holdings and recurring payments are called. */
export interface Names {
  accounts: Record<string, string>;
  debts: Record<string, string>;
  holdings: Record<string, string>;
  payments: Record<string, string>;
}

function defaultNote(q: TemplateQuestion): string | null {
  if (!q.default) return null;
  return t.defaultFrom(String(q.default.value), q.default.note);
}

function Help({ q }: { q: TemplateQuestion }) {
  const note = defaultNote(q);
  return (
    <>
      {q.help}
      {note ? (
        <>
          {' '}
          <span className={q.default?.source === 'placeholder' ? 'placeholder-tag' : 'default-note'}>{note}</span>
        </>
      ) : null}
    </>
  );
}

function label(q: TemplateQuestion): string {
  return q.required && q.default === null ? q.prompt : `${q.prompt} (${t.optional.toLowerCase()})`;
}

function inputModeOf(q: TemplateQuestion): 'decimal' | 'numeric' | 'text' {
  if (q.type === 'months' || q.type === 'years') return 'numeric';
  if (['amount', 'amount_or_zero', 'signed_amount', 'number', 'rate', 'growth'].includes(q.type)) return 'decimal';
  return 'text';
}

interface QuestionProps {
  q: TemplateQuestion;
  template: DecisionTemplate;
  state: FormState;
  set: (id: string, value: FormState[string]) => void;
  errors: Errors;
  names: Names;
  asOf: string;
}

function ListControls({ count, most, onAdd, addLabel }: { count: number; most: number; onAdd: () => void; addLabel: string }) {
  return count < most ? (
    <button type="button" className="button button-secondary" onClick={onAdd}>
      {addLabel}
    </button>
  ) : null;
}

function Remove({ onRemove, label: text }: { onRemove: () => void; label: string }) {
  return (
    <button type="button" className="button-link" onClick={onRemove}>
      {text}
    </button>
  );
}

function Amounts({ q, state, set, errors }: QuestionProps) {
  const items = (state[q.id] as string[] | undefined) ?? [''];
  const least = Math.max(1, q.min_items ?? 1);
  const most = q.max_items ?? 5;
  return (
    <fieldset className="field group">
      <legend className="field-label">{label(q)}</legend>
      <p className="field-help">
        <Help q={q} />
      </p>
      {errors[q.id] ? <p className="field-error">{errors[q.id]}</p> : null}
      {items.map((item, i) => (
        <div key={i} className="group-item">
          <Field
            label={t.amountItem(i + 1)}
            value={item}
            onChange={(v) => set(q.id, items.map((x, k) => (k === i ? v : x)))}
            error={errors[`${q.id}[${i}]`]}
            inputProps={{ inputMode: 'decimal' }}
          />
          {items.length > least ? <Remove label={t.remove(t.amountItem(i + 1).toLowerCase())} onRemove={() => set(q.id, items.filter((_, k) => k !== i))} /> : null}
        </div>
      ))}
      <ListControls count={items.length} most={most} addLabel={t.add(t.anAmount)} onAdd={() => set(q.id, [...items, ''])} />
    </fieldset>
  );
}

function Loans({ q, state, set, errors }: QuestionProps) {
  const loans = (state[q.id] as LoanState[] | undefined) ?? [emptyLoan()];
  const least = Math.max(1, q.min_items ?? 1);
  const most = q.max_items ?? 4;
  const change = (i: number, patch: Partial<LoanState>) => set(q.id, loans.map((x, k) => (k === i ? { ...x, ...patch } : x)));
  return (
    <fieldset className="field group">
      <legend className="field-label">{label(q)}</legend>
      <p className="field-help">{q.help}</p>
      {errors[q.id] ? <p className="field-error">{errors[q.id]}</p> : null}
      {loans.map((loan, i) => (
        <fieldset key={i} className="group-item">
          <legend className="subhead">{t.loanItem(i + 1)}</legend>
          <div className="field-row">
            <Field label={t.loanRate} description={t.loanRateHelp} value={loan.rate} onChange={(v) => change(i, { rate: v })} error={errors[`${q.id}[${i}].annual_rate`]} isRequired inputProps={{ inputMode: 'decimal' }} />
            <Field label={t.loanTerm} value={loan.term} onChange={(v) => change(i, { term: v })} error={errors[`${q.id}[${i}].term_months`]} isRequired inputProps={{ inputMode: 'numeric' }} />
          </div>
          <Field label={t.loanLabel} value={loan.label} onChange={(v) => change(i, { label: v })} error={errors[`${q.id}[${i}].label`]} />
          {loans.length > least ? <Remove label={t.remove(t.loanItem(i + 1).toLowerCase())} onRemove={() => set(q.id, loans.filter((_, k) => k !== i))} /> : null}
        </fieldset>
      ))}
      <ListControls count={loans.length} most={most} addLabel={t.add(t.aLoan)} onAdd={() => set(q.id, [...loans, emptyLoan()])} />
    </fieldset>
  );
}

function Splits({ q, template, state, set, errors, names }: QuestionProps) {
  const splits = (state[q.id] as SplitState[] | undefined) ?? [emptySplit()];
  const least = Math.max(1, q.min_items ?? 2);
  const most = q.max_items ?? 5;
  const debts = allowed(template, [q.id, '[]', 'debts', '[]', 'debt']) ?? [];
  const change = (i: number, patch: Partial<SplitState>) => set(q.id, splits.map((x, k) => (k === i ? { ...x, ...patch } : x)));
  return (
    <fieldset className="field group">
      <legend className="field-label">{label(q)}</legend>
      <p className="field-help">{q.help}</p>
      {errors[q.id] ? <p className="field-error">{errors[q.id]}</p> : null}
      {splits.map((split, i) => (
        <fieldset key={i} className="group-item">
          <legend className="subhead">{t.splitItem(i + 1)}</legend>
          <Field label={t.splitLabel} value={split.label} onChange={(v) => change(i, { label: v })} error={errors[`${q.id}[${i}].label`]} isRequired />
          {debts.map((debt) => (
            <Field
              key={debt}
              label={t.splitOnto(names.debts[debt] ?? debt)}
              value={split.debts[debt] ?? ''}
              onChange={(v) => change(i, { debts: { ...split.debts, [debt]: v } })}
              error={errors[`${q.id}[${i}].debts.${debt}`]}
              inputProps={{ inputMode: 'decimal' }}
            />
          ))}
          <Field label={t.splitInvest} value={split.invest} onChange={(v) => change(i, { invest: v })} error={errors[`${q.id}[${i}].invest`]} inputProps={{ inputMode: 'decimal' }} />
          {splits.length > least ? <Remove label={t.remove(t.splitItem(i + 1).toLowerCase())} onRemove={() => set(q.id, splits.filter((_, k) => k !== i))} /> : null}
        </fieldset>
      ))}
      <ListControls count={splits.length} most={most} addLabel={t.add(t.aSplit)} onAdd={() => set(q.id, [...splits, emptySplit()])} />
    </fieldset>
  );
}

function Picker({ q, template, state, set, errors, names }: QuestionProps): ReactNode {
  const ids = allowed(template, [q.id]) ?? [];
  const value = (state[q.id] as string | undefined) ?? '';
  const help = <Help q={q} />;
  const named = (id: string): string =>
    (q.type === 'account' ? names.accounts[id] : q.type === 'debt' ? names.debts[id] : q.type === 'holding' ? names.holdings[id] : q.type === 'recurring' ? names.payments[id] : id) ?? id;
  if (q.type === 'tax_role' && !ids.length) {
    return (
      <div className="field">
        <p className="field-label">{label(q)}</p>
        <p className="field-help">{t.noTaxRoles}</p>
      </div>
    );
  }
  if (q.type === 'holding' && !ids.length) {
    return (
      <div className="field">
        <p className="field-label">{label(q)}</p>
        <p className="field-help">{t.noHoldings}</p>
      </div>
    );
  }
  const none =
    q.type === 'account'
      ? t.cashAsAWhole
      : q.type === 'holding'
        ? t.investmentsAsAWhole
        : q.type === 'recurring'
          ? t.notInLedger
          : q.type === 'tax_role'
            ? t.takeHome
            : q.type === 'debt'
              ? t.chooseDebt
              : t.leaveOut;
  return (
    <SelectField
      label={label(q)}
      description={help}
      value={value}
      onChange={(v) => set(q.id, v)}
      error={errors[q.id]}
      isRequired={q.required && q.default === null}
      options={[{ value: '', label: none }, ...ids.map((id) => ({ value: id, label: named(id) }))]}
    />
  );
}

export function Question(props: QuestionProps) {
  const { q, state, set, errors } = props;
  if (q.type === 'amounts') return <Amounts {...props} />;
  if (q.type === 'loans') return <Loans {...props} />;
  if (q.type === 'splits') return <Splits {...props} />;
  if (['account', 'debt', 'holding', 'recurring', 'tax_role'].includes(q.type)) return <>{Picker(props)}</>;
  const value = (state[q.id] as string | undefined) ?? '';
  if (q.type === 'choice') {
    return (
      <RadioField
        label={label(q)}
        description={<Help q={q} />}
        value={value}
        onChange={(v) => set(q.id, v)}
        error={errors[q.id]}
        options={q.choices.map((c) => ({ value: c.value, label: c.label }))}
      />
    );
  }
  return (
    <Field
      label={label(q)}
      description={<Help q={q} />}
      value={value}
      onChange={(v) => set(q.id, v)}
      error={errors[q.id]}
      isRequired={q.required && q.default === null}
      name={q.id}
      {...(q.type === 'date' ? { type: 'date' as const } : {})}
      inputProps={{
        inputMode: inputModeOf(q),
        ...(q.type === 'date' ? { min: props.asOf } : {}),
        ...(q.default ? { placeholder: String(q.default.value) } : {}),
      }}
    />
  );
}

/** Every question the answers so far make apply, in the template's order. */
export function Questions(props: Omit<QuestionProps, 'q'>) {
  return (
    <>
      {props.template.questions
        .filter((q) => applies(q, props.state, props.template))
        .map((q) => (
          <Question key={q.id} q={q} {...props} />
        ))}
    </>
  );
}
