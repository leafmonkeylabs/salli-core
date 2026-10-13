/**
 * Adding an entry (`entries.create`; decision 16): one amount from one
 * account to another, as `salli entries add --debit to:amount --credit
 * from:amount` posts it. The amount is the same on both lines, so the
 * entry balances without the console adding anything up; an entry split
 * across several accounts stays in the CLI, and the page says so.
 *
 * The currency is the base, or one of the two accounts' own; in another
 * than the base, Salli uses the rate published for the day unless the bank's
 * is given, and the page says which it used once the entry is read back.
 * Before posting, a confirmation says what Salli will post and that a
 * posted entry is corrected by reversing it, never edited.
 */
import { describeDetail, entriesCreate, entriesGet, profileGet, type AddEntryRequest, type PostingRequest, type Ref } from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useMemo, useState, type FormEvent } from 'react';
import { problemOf, useRead, useWrite } from '../../api';
import { displayDate, isoDate } from '../../kit/dates';
import { Button, Confirm, Field, SelectField } from '../../kit/forms';
import { dateInput, positiveAmountInput } from '../../kit/inputs';
import { Grid, Loaded, Page, Panel, Provenance, Row, Rows, Section } from '../../kit/layout';
import { Money, visibleAmount } from '../../kit/Money';
import { fieldErrors, ProblemView } from '../../kit/Problem';
import { useLocale } from '../../preferences';
import { whereStrings } from '../../where-strings';
import { BooksNav, entryPath, LEDGER_READS, useAccountBook, type AccountBook } from './ledger';

const f = whereStrings.add;

interface Draft {
  date: string;
  description: string;
  from: string;
  to: string;
  amount: string;
  currency: string;
  rate: string;
}

/** The currencies an entry between these two accounts may be posted in: the base, then each account's own. */
function currenciesFor(base: string, draft: Draft, book: AccountBook): string[] {
  const own = [draft.from, draft.to].map((id) => book.byId.get(id)?.currency.toUpperCase()).filter((c): c is string => Boolean(c));
  return [...new Set([base.toUpperCase(), ...own])];
}

/** The currency to offer first: an account's own when one isn't held in the base, else the base. */
function defaultCurrency(base: string, from: string, to: string, book: AccountBook): string {
  const foreign = [from, to].map((id) => book.byId.get(id)?.currency.toUpperCase()).find((c) => c && c !== base.toUpperCase());
  return foreign ?? base.toUpperCase();
}

/** The posted entry, read back: the rate Salli used, when it isn't the base. */
function Posted({ id, base }: { id: string; base: string }) {
  const query = useRead('entries.get', entriesGet, { path: { entry_id: id } });
  const converted = query.data?.postings.find((p) => p.currency.toUpperCase() !== base.toUpperCase());
  return (
    <>
      <span aria-hidden="true">✓</span> {f.posted}{' '}
      {converted ? <>{f.postedAt(whereStrings.entry.rateText(converted.currency, converted.fx_rate, base))} </> : null}
      <Link to={entryPath(id)}>{f.open}</Link>
    </>
  );
}

function EntryForm({ book, base }: { book: AccountBook; base: string }) {
  const locale = useLocale();
  const today = isoDate(new Date());
  const empty: Draft = { date: today, description: '', from: '', to: '', amount: '', currency: base.toUpperCase(), rate: '' };
  const [draft, setDraft] = useState<Draft>(empty);
  const [local, setLocal] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);
  const [body, setBody] = useState<AddEntryRequest | null>(null);
  const [posted, setPosted] = useState<string | null>(null);
  const write = useWrite<AddEntryRequest, Ref>('entries.create', (api, input) => api.call(entriesCreate, { body: input }), {
    invalidate: LEDGER_READS,
    onSuccess: (ref) => {
      setConfirming(false);
      setPosted(ref.id);
      setDraft({ ...empty, date: draft.date });
    },
  });
  const active = useMemo(() => book.accounts.filter((a) => a.is_active), [book]);
  const options = [{ value: '', label: f.choose }, ...active.map((a) => ({ value: a.id, label: `${a.code} ${a.name}` }))];
  const currencies = currenciesFor(base, draft, book);
  const foreign = draft.currency !== base.toUpperCase();
  const set = (field: keyof Draft) => (value: string) => {
    setPosted(null);
    setDraft((d) => {
      const next = { ...d, [field]: value };
      if (field === 'from' || field === 'to') next.currency = defaultCurrency(base, next.from, next.to, book);
      if (next.currency === base.toUpperCase()) next.rate = '';
      return next;
    });
  };

  const server = write.isError ? fieldErrors(write.error) : {};
  // No published rate for the day: the rate field is where to answer it.
  const refused = write.isError ? problemOf(write.error) : undefined;
  const noRate = refused?.kind === 'fx-rate-unavailable' ? describeDetail(refused.detail) : '';
  const errors: Record<string, string> = {
    ...(server.entry_date ? { date: server.entry_date } : {}),
    ...(server.description ? { description: server.description } : {}),
    ...(server['postings.0.amount'] || server['postings.1.amount'] ? { amount: server['postings.0.amount'] ?? server['postings.1.amount'] ?? '' } : {}),
    ...(server['postings.0.fx_rate'] ? { rate: server['postings.0.fx_rate'] } : {}),
    ...(noRate ? { rate: noRate } : {}),
    ...local,
  };

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setPosted(null);
    const found: Record<string, string> = {};
    const date = dateInput(draft.date);
    const amount = positiveAmountInput(draft.amount, locale);
    const rate = draft.rate.trim() ? positiveAmountInput(draft.rate, locale) : undefined;
    if (!date) found.date = draft.date ? f.badDate : f.needed;
    if (!draft.description.trim()) found.description = f.needed;
    if (!draft.from) found.from = f.needed;
    if (!draft.to) found.to = f.needed;
    if (draft.from && draft.from === draft.to) found.to = f.sameAccount;
    if (!amount) found.amount = draft.amount.trim() ? f.badAmount : f.needed;
    if (foreign && draft.rate.trim() && !rate) found.rate = f.badRate;
    setLocal(found);
    if (Object.keys(found).length || !date || !amount) return;
    const line = (account: string, direction: 1 | -1): PostingRequest => ({
      account_id: account,
      direction,
      amount,
      ...(foreign ? { currency: draft.currency } : {}),
      ...(foreign && rate ? { fx_rate: rate } : {}),
    });
    setBody({ entry_date: date, description: draft.description.trim(), postings: [line(draft.to, 1), line(draft.from, -1)] });
    setConfirming(true);
  };

  const warnings = [draft.from, draft.to].flatMap((id) => {
    const account = book.byId.get(id);
    if (!account) return [];
    const own = account.currency.toUpperCase();
    return own !== draft.currency && own !== base.toUpperCase() ? [f.unknownBalance(account.name, own, draft.currency)] : [];
  });
  const amountShown = body?.postings[0]?.amount;

  return (
    <form className="form form-wide" onSubmit={submit} noValidate>
      <div className="field-grid">
        <Field label={f.date} type="date" value={draft.date} onChange={set('date')} error={errors.date} isRequired />
        <Field label={f.description_} description={f.descriptionHelp} value={draft.description} onChange={set('description')} error={errors.description} isRequired />
      </div>
      <div className="field-grid">
        <SelectField label={f.from} description={f.fromHelp} value={draft.from} onChange={set('from')} error={errors.from} options={options} isRequired />
        <SelectField label={f.to} description={f.toHelp} value={draft.to} onChange={set('to')} error={errors.to} options={options} isRequired />
      </div>
      <div className="field-grid">
        <Field
          label={f.amount}
          description={f.amountHelp(visibleAmount('1234.50', draft.currency, 'table', { locale }))}
          value={draft.amount}
          onChange={set('amount')}
          error={errors.amount}
          isRequired
          inputProps={{ inputMode: 'decimal' }}
        />
        <SelectField
          label={f.currency}
          description={f.currencyHelp}
          value={draft.currency}
          onChange={set('currency')}
          options={currencies.map((c) => ({ value: c, label: c }))}
        />
        {foreign ? (
          <Field
            label={f.rate(base.toUpperCase(), draft.currency)}
            description={f.rateHelp(displayDate(dateInput(draft.date) ?? today, locale))}
            value={draft.rate}
            onChange={set('rate')}
            error={errors.rate}
            inputProps={{ inputMode: 'decimal' }}
          />
        ) : null}
      </div>
      {warnings.map((w) => (
        <p key={w} className="warn-line">
          <span className="warn-mark" aria-hidden="true">
            !
          </span>{' '}
          {w}
        </p>
      ))}
      {Object.keys(local).length ? (
        <p className="sr-only" role="alert">
          {Object.values(local).join(' ')}
        </p>
      ) : null}
      {write.isError && !write.stepUpPending ? <ProblemView error={write.error} compact /> : null}
      <div className="form-actions">
        <Button type="submit" isPending={write.isPending}>
          {write.isPending ? f.posting : f.submit}
        </Button>
        <p role="status" className="quiet-success">
          {posted ? <Posted id={posted} base={base} /> : null}
        </p>
      </div>
      <Confirm
        isOpen={confirming}
        onOpenChange={setConfirming}
        title={f.confirmTitle}
        confirmLabel={f.submit}
        cancelLabel={f.cancel}
        isPending={write.isPending}
        onConfirm={() => (body ? write.mutate(body) : undefined)}
      >
        {body ? (
          <Rows>
            <Row label={f.rows.date}>{displayDate(body.entry_date, locale)}</Row>
            <Row label={f.rows.description}>{body.description}</Row>
            <Row label={f.rows.from}>{book.label(draft.from)}</Row>
            <Row label={f.rows.to}>{book.label(draft.to)}</Row>
            <Row label={f.rows.amount}>{amountShown ? <Money amount={amountShown} currency={draft.currency} /> : null}</Row>
            {foreign ? <Row label={f.rows.rate}>{body.postings[0]?.fx_rate ? whereStrings.entry.rateText(draft.currency, body.postings[0].fx_rate, base.toUpperCase()) : f.publishedRate}</Row> : null}
          </Rows>
        ) : null}
        <p>{f.confirmBody}</p>
      </Confirm>
    </form>
  );
}

export function AddEntry() {
  const { query, book } = useAccountBook();
  const profile = useRead('profile.get', profileGet);
  return (
    <Page title={f.title} description={f.description}>
      <BooksNav />
      <Grid>
        <Section label={f.form} full>
          <Panel>
            <Loaded query={query}>
              {() => <Loaded query={profile}>{(p) => (book ? <EntryForm book={book} base={p.base_currency} /> : null)}</Loaded>}
            </Loaded>
            <Provenance>{f.neverEdited}</Provenance>
          </Panel>
        </Section>
      </Grid>
    </Page>
  );
}

export default AddEntry;
