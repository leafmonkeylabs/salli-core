/**
 * Imports (docs/design/console.md, section 5; `salli import`, `salli
 * statements list`, `salli banks list`): a statement file uploaded from this
 * device (`statements.upload`), read on the server, with the account it is
 * for, its currency and how its dates are written; what Salli read and
 * noted, and a way to the review queue; every statement imported, with
 * whether it waits for review; and where each bank connection stands
 * (`bankConnections.list`), connecting one staying with `salli banks`.
 *
 * Nothing is booked here: importing proposes, and review posts.
 */
import {
  bankConnectionsList,
  statementsList,
  statementsUpload,
  type BankConnection,
  type BankStatement,
  type StatementUpload,
} from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useMemo, useState, type FormEvent } from 'react';
import { useRead, useWrite } from '../../api';
import { bookStrings } from '../../books-strings';
import { displayDate, displayMoment, displayRange } from '../../kit/dates';
import { Button, Field, FileField, SelectField } from '../../kit/forms';
import { Blank, Empty, Grid, Loaded, Page, Panel, Section } from '../../kit/layout';
import { Money } from '../../kit/Money';
import { fieldErrors, ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { BooksActions, BooksFacts, BooksNav, useAccountBook, type AccountBook } from './ledger';
import { periodOf, reviewPath, statementName } from './statements';

const t = bookStrings.imports;

/** What a statement file can be, as the server reads them. */
const ACCEPT = '.ofx,.qfx,.qif,.xml,.sta,.mt940,.940,.txt,.csv,.tsv,.xlsx,.xls,.pdf';
const MAX_BYTES = 10 * 1024 * 1024;
const STATEMENT_READS = ['statements.list', 'statements.pending', 'rules.list', 'insights.signals'];

interface UploadInput {
  file: File;
  account: string;
  currency: string;
  dateOrder: '' | 'DMY' | 'MDY' | 'YMD';
  bank: string;
  sourceAccount: string;
  replaces: string;
}

function Uploaded({ result }: { result: StatementUpload }) {
  const locale = useLocale();
  const range = result.period_start && result.period_end ? t.forPeriod(displayRange(result.period_start, result.period_end, locale)) : '';
  return (
    <div className="stack-tight">
      <p>
        <span aria-hidden="true">✓</span> {t.read(t.transactions(result.parsed), result.bank || t.theFile, range)}{' '}
        {result.statement_id ? <Link to={reviewPath(result.statement_id)}>{t.reviewThem}</Link> : null}
      </p>
      {result.errors.length ? (
        <>
          <p className="subhead">{t.readNotes}</p>
          <ul className="list notes">
            {result.errors.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}

function UploadForm({ book, statements }: { book: AccountBook; statements: readonly BankStatement[] }) {
  const locale = useLocale();
  const [file, setFile] = useState<File | undefined>();
  const [account, setAccount] = useState('');
  const [currency, setCurrency] = useState('');
  const [dateOrder, setDateOrder] = useState<UploadInput['dateOrder']>('');
  const [bank, setBank] = useState('');
  const [sourceAccount, setSourceAccount] = useState('');
  const [replaces, setReplaces] = useState('');
  const [local, setLocal] = useState<Record<string, string>>({});
  const write = useWrite<UploadInput, StatementUpload>(
    'statements.upload',
    (api, input) =>
      api.call(statementsUpload, {
        body: { file: input.file },
        query: {
          ...(input.account ? { account_id: input.account } : {}),
          ...(input.currency ? { currency: input.currency } : {}),
          ...(input.dateOrder ? { date_order: input.dateOrder } : {}),
          ...(input.bank ? { bank: input.bank } : {}),
          ...(input.sourceAccount ? { source_account: input.sourceAccount } : {}),
          ...(input.replaces ? { replaces: input.replaces } : {}),
        },
        timeoutMs: 5 * 60_000,
      }),
    { invalidate: STATEMENT_READS },
  );
  // Money accounts only: the statement's account is the money side.
  const money = useMemo(() => book.accounts.filter((a) => a.is_active && (a.type === 'asset' || a.type === 'liability')), [book]);
  const server = write.isError ? fieldErrors(write.error) : {};
  const errors: Record<string, string> = { ...(server.currency ? { currency: server.currency } : {}), ...local };

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const found: Record<string, string> = {};
    const code = currency.trim().toUpperCase();
    if (!file) found.file = t.fileMissing;
    else if (file.size > MAX_BYTES) found.file = t.fileTooLarge;
    if (code && !/^[A-Z]{3}$/.test(code)) found.currency = t.currencyInvalid;
    setLocal(found);
    if (Object.keys(found).length || !file) return;
    write.mutate({ file, account, currency: code, dateOrder, bank: bank.trim(), sourceAccount: sourceAccount.trim(), replaces });
  };

  return (
    <form className="form form-wide" onSubmit={submit} noValidate>
      <p className="section-help">{t.uploadHelp}</p>
      <div className="field-grid">
        <FileField label={t.file} description={t.fileHelp} accept={ACCEPT} onChange={setFile} error={errors.file} isRequired />
        <SelectField
          label={t.account}
          description={t.accountHelp}
          value={account}
          onChange={setAccount}
          options={[{ value: '', label: t.noAccount }, ...money.map((a) => ({ value: a.id, label: `${a.code} ${a.name}` }))]}
        />
      </div>
      <div className="field-grid">
        <Field label={t.currency} description={t.currencyHelp} value={currency} onChange={setCurrency} error={errors.currency} inputProps={{ spellCheck: false }} />
        <SelectField
          label={t.dateOrder}
          description={t.dateOrderHelp}
          value={dateOrder}
          onChange={(v) => setDateOrder(v as UploadInput['dateOrder'])}
          options={['', 'DMY', 'MDY', 'YMD'].map((v) => ({ value: v, label: t.dateOrders[v] ?? v }))}
        />
      </div>
      <p className="field-help">{t.csvNote}</p>
      <details className="disclosure">
        <summary>{t.more}</summary>
        <div className="field-grid">
          <Field label={t.bank} description={t.bankHelp} value={bank} onChange={setBank} />
          <Field label={t.sourceAccount} description={t.sourceAccountHelp} value={sourceAccount} onChange={setSourceAccount} />
          <SelectField
            label={t.replaces}
            description={t.replacesHelp}
            value={replaces}
            onChange={setReplaces}
            options={[
              { value: '', label: t.replacesNone },
              ...statements.map((s) => ({ value: s.id, label: `${statementName(s, book)} ${periodOf(s, locale)}`.trim() })),
            ]}
          />
        </div>
      </details>
      {Object.keys(local).length ? (
        <p className="sr-only" role="alert">
          {Object.values(local).join(' ')}
        </p>
      ) : null}
      {write.isError ? <ProblemView error={write.error} compact /> : null}
      <div className="form-actions">
        <Button type="submit" isPending={write.isPending}>
          {write.isPending ? t.submitting : t.submit}
        </Button>
      </div>
      <div role="status" className="quiet-success">
        {write.isSuccess && write.data ? <Uploaded result={write.data} /> : null}
      </div>
    </form>
  );
}

function Statements({ statements, book }: { statements: readonly BankStatement[]; book: AccountBook }) {
  const locale = useLocale();
  if (!statements.length) return <Empty>{t.noStatements}</Empty>;
  return (
    <Table<BankStatement>
      caption={t.statements}
      captionHidden
      rows={[...statements]}
      rowKey={(s) => s.id}
      columns={[
        { key: 'imported', header: t.imported, label: t.imported, render: (s) => displayDate(s.created_at, locale) },
        { key: 'bank', header: t.statementBank, label: t.statementBank, render: (s) => statementName(s, book) },
        { key: 'account', header: t.statementAccount, label: t.statementAccount, render: (s) => (s.account_id ? book.label(s.account_id) : <Blank>{t.noAccount}</Blank>) },
        { key: 'period', header: t.period, label: t.period, render: (s) => periodOf(s, locale) },
        {
          key: 'status',
          header: t.status,
          label: t.status,
          render: (s) => <span className={s.status === 'pending' ? 'tag tag-due' : 'tag'}>{t.statuses[s.status] ?? s.status}</span>,
        },
        {
          key: 'review',
          header: <span className="sr-only">{t.review}</span>,
          label: '',
          align: 'end',
          render: (s) => (
            <Link to={reviewPath(s.id)} aria-label={t.reviewLabel(`${statementName(s, book)} ${periodOf(s, locale)}`.trim())}>
              {t.review}
            </Link>
          ),
        },
      ]}
    />
  );
}

function Banks({ book }: { book: AccountBook | undefined }) {
  const locale = useLocale();
  const query = useRead('bankConnections.list', bankConnectionsList);
  return (
    <Section label={t.banks} full>
      <Panel>
        <p className="section-help">{t.banksHelp}</p>
        <Loaded query={query}>
          {(data) => (
            <div className="stack-tight">
              {!data.available ? <p className="muted">{t.banksUnavailable}</p> : null}
              {data.connections.length ? (
                <ul className="list">
                  {data.connections.map((c: BankConnection) => (
                    <li key={c.id} className="stack-tight">
                      <p className="signal-title">
                        {c.name} <span className={c.status === 'error' ? 'tag tag-warn' : 'tag'}>{t.bankStatus[c.status] ?? c.status}</span>
                      </p>
                      <p className="muted">{c.last_synced_at ? t.lastSynced(displayMoment(c.last_synced_at, locale)) : t.neverSynced}</p>
                      {c.last_error ? <p className="warn-line">{c.last_error}</p> : null}
                      {c.warnings?.map((w) => (
                        <p key={w} className="warn-line">
                          {w}
                        </p>
                      ))}
                      <Table
                        caption={c.name}
                        captionHidden
                        rows={c.accounts}
                        rowKey={(a) => a.remote_id}
                        columns={[
                          { key: 'bank', header: t.bankAccount, label: t.bankAccount, render: (a) => a.name },
                          { key: 'salli', header: t.salliAccount, label: t.salliAccount, render: (a) => (a.account_id ? (book?.label(a.account_id) ?? a.account_id) : t.notMapped) },
                          {
                            key: 'balance',
                            header: t.bankBalance,
                            label: t.bankBalance,
                            align: 'end',
                            render: (a) => (a.balance ? <Money amount={a.balance} currency={a.currency} variant="table" withCode /> : <Blank>{t.noBalance}</Blank>),
                          },
                        ]}
                      />
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>{t.noBanks}</Empty>
              )}
            </div>
          )}
        </Loaded>
      </Panel>
    </Section>
  );
}

export function Imports() {
  const { query, book } = useAccountBook();
  const statements = useRead('statements.list', statementsList, { query: { limit: 200 } });
  return (
    <Page title={t.title} description={t.description} facts={<BooksFacts />} actions={<BooksActions />}>
      <BooksNav />
      <Grid>
        <Section label={t.upload} full>
          <Panel>
            <Loaded query={query}>{() => <Loaded query={statements}>{(data) => (book ? <UploadForm book={book} statements={data.statements} /> : null)}</Loaded>}</Loaded>
          </Panel>
        </Section>
        <Section label={t.statements} full>
          <Panel>
            <p className="section-help">{t.statementsHelp}</p>
            <Loaded query={query}>{() => <Loaded query={statements}>{(data) => (book ? <Statements statements={data.statements} book={book} /> : null)}</Loaded>}</Loaded>
          </Panel>
        </Section>
        <Banks book={book} />
      </Grid>
    </Page>
  );
}

export default Imports;
