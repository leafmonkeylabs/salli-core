/**
 * The review queue (docs/design/console.md, section 5; `salli statements
 * pending`, `categorize`, `post`, `discard`): a statement's transactions
 * waiting for review (`statements.pending`), each as Salli read it, with
 * the account a rule or the model proposed and how sure it is, and a
 * warning where it looks like an entry already booked.
 *
 * - Changing where money came from or went is kept at once
 *   (`statements.categorize`): a choice can be made again.
 * - Posting and discarding work on a selection (`statements.post`,
 *   `statements.discard`, both taking many), each after a confirmation that
 *   says what Salli will do. Nothing is booked until it is posted; Salli
 *   skips one already posted or imported before, so nothing is booked twice.
 * - A rule can be made from a transaction, its form filled from it.
 */
import {
  rulesList,
  statementsCategorize,
  statementsDiscard,
  statementsList,
  statementsPending,
  statementsPost,
  type PostedStatementTransactions,
  type StatementTransaction,
} from '@leafmonkeylabs/salli-sdk';
import { Link, useParams } from '@tanstack/react-router';
import { useMemo, useState } from 'react';
import { useRead, useWrite } from '../../api';
import { bookStrings } from '../../books-strings';
import { displayDate } from '../../kit/dates';
import { Button, Confirm } from '../../kit/forms';
import { Blank, Empty, Grid, Loaded, Page, Panel, Section } from '../../kit/layout';
import { Money } from '../../kit/Money';
import { ProblemView } from '../../kit/Problem';
import { useLocale } from '../../preferences';
import { BooksActions, BooksFacts, BooksNav, entryPath, LEDGER_READS, useAccountBook, type AccountBook } from './ledger';
import { RuleForm, type RuleStart } from './rule-form';
import { periodOf, statementName } from './statements';

const t = bookStrings.review;
const REVIEW_READS = ['statements.pending', 'statements.list', 'insights.signals'];

type Txn = StatementTransaction;

/** The account the money moved in: the statement's own, or the side already chosen. */
const moneySide = (x: Txn): string | null => x.account_id ?? ((x.credit_flag ? x.debit_account_id : x.credit_account_id) || null);
/** Where the money came from (in) or went (out): what review chooses. */
const otherSide = (x: Txn): string => (x.credit_flag ? x.credit_account_id : x.debit_account_id) ?? '';
const isComplete = (x: Txn): boolean => Boolean(x.debit_account_id && x.credit_account_id);
const isClean = (x: Txn): boolean => isComplete(x) && x.dedup_status !== 'fuzzy_match';
const shown = (x: Txn): string => x.description_override || x.description;

function Who({ txn, rules }: { txn: Txn; rules: ReadonlyMap<string, string> }) {
  const locale = useLocale();
  if (!isComplete(txn)) return <span className="tag tag-warn">{t.needsAccount}</span>;
  if (txn.rule_id) {
    const name = rules.get(txn.rule_id);
    return <span className="muted">{name ? t.byRule(name) : t.byARule}</span>;
  }
  if (txn.confidence > 0 && txn.confidence < 1) {
    const sure = new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 0 }).format(txn.confidence);
    return <span className="muted">{t.byModel(sure)}</span>;
  }
  return <span className="muted">{t.yours}</span>;
}

function Item({
  txn,
  book,
  rules,
  selected,
  onSelect,
  onChoose,
  choosing,
  onRule,
}: {
  txn: Txn;
  book: AccountBook;
  rules: ReadonlyMap<string, string>;
  selected: boolean;
  onSelect: (on: boolean) => void;
  onChoose: (account: string) => void;
  choosing: boolean;
  onRule: () => void;
}) {
  const locale = useLocale();
  const money = moneySide(txn);
  const other = otherSide(txn);
  const way = txn.credit_flag ? 'in' : 'out';
  const date = displayDate(txn.date, locale);
  const options = [
    { value: '', label: t.chooseAccount },
    ...book.accounts.filter((a) => a.is_active && a.id !== money).map((a) => ({ value: a.id, label: `${a.code} ${a.name}` })),
  ];
  const otherField = (
    <label className="review-choice">
      <span className="field-label">{txn.credit_flag ? t.cameFrom : t.wentTo}</span>
      <select
        className="field-input field-select"
        value={other}
        disabled={!money || choosing}
        aria-label={t.otherLabel(shown(txn), way)}
        onChange={(event) => (event.currentTarget.value ? onChoose(event.currentTarget.value) : undefined)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.value === ''}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
  const moneyName = money ? book.label(money) : <Blank>{t.notChosen}</Blank>;
  return (
    <li className={['review-item', selected ? 'review-item-selected' : ''].filter(Boolean).join(' ')}>
      <div className="review-select">
        <input type="checkbox" checked={selected} onChange={(event) => onSelect(event.currentTarget.checked)} aria-label={t.select(shown(txn), date)} />
      </div>
      <div className="review-body">
        <p className="review-head">
          <span className="review-date">{date}</span> <span className="review-description">{shown(txn)}</span>
          <span className="review-amount">
            <Money amount={txn.amount} currency={txn.currency} /> {txn.credit_flag ? t.in : t.out}
          </span>
        </p>
        {txn.description_override ? <p className="muted">{t.asTheBankWrote(txn.description)}</p> : null}
        <div className="review-sides">
          {txn.credit_flag ? (
            <>
              {otherField}
              <p className="review-fixed">
                <span className="field-label">{t.to}</span> {moneyName}
              </p>
            </>
          ) : (
            <>
              <p className="review-fixed">
                <span className="field-label">{t.from}</span> {moneyName}
              </p>
              {otherField}
            </>
          )}
        </div>
        <p className="review-who">
          <Who txn={txn} rules={rules} />
          {txn.category ? <span className="muted"> · {t.category(txn.category)}</span> : null}
          {txn.need ? <span className="muted"> · {t.need[txn.need] ?? txn.need}</span> : null}
        </p>
        {!money ? <p className="warn-line">{t.noMoneySide}</p> : null}
        {txn.dedup_status === 'fuzzy_match' ? (
          <p className="warn-line">
            <span className="warn-mark" aria-hidden="true">
              !
            </span>{' '}
            {t.maybeDuplicate}
            {txn.duplicate_of ? (
              <>
                {' '}
                <Link to={entryPath(txn.duplicate_of)}>{t.openDuplicate}</Link>
              </>
            ) : null}
          </p>
        ) : null}
        <div>
          <Button variant="tertiary" aria-label={t.makeRuleLabel(shown(txn))} onPress={onRule}>
            {t.makeRule}
          </Button>
        </div>
      </div>
    </li>
  );
}

/** A rule's form started from a transaction: its words, and where it went. */
function ruleFrom(txn: Txn): RuleStart {
  const other = otherSide(txn);
  const words = txn.description.trim();
  return {
    name: words.length > 60 ? words.slice(0, 60) : words,
    conditions: [
      { field: 'description', operator: 'contains', value: words },
      { field: 'direction', operator: 'equals', value: txn.credit_flag ? 'in' : 'out' },
    ],
    actions: other ? { account_id: other } : {},
  };
}

type Ask = { kind: 'post' | 'discard'; ids: string[] } | null;

function Queue({ statementId, book, period }: { statementId: string; book: AccountBook; period: { from: string; to: string; account: string } | undefined }) {
  const query = useRead('statements.pending', statementsPending, { path: { statement_id: statementId } });
  const rulesQuery = useRead('rules.list', rulesList);
  const rules = useMemo(() => new Map((rulesQuery.data ?? []).map((r) => [r.id, r.name])), [rulesQuery.data]);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [ask, setAsk] = useState<Ask>(null);
  const [said, setSaid] = useState<{ text: string; posted?: boolean }>({ text: '' });
  const [rule, setRule] = useState<RuleStart | null>(null);
  const [choosingId, setChoosingId] = useState<string | null>(null);

  const choose = useWrite<{ id: string; account: string; what: string }, unknown>(
    'statements.categorize',
    (api, input) => api.call(statementsCategorize, { body: { choices: [{ transaction_id: input.id, account_id: input.account }] } }),
    {
      invalidate: REVIEW_READS,
      onSuccess: (_, input) => {
        setChoosingId(null);
        setSaid({ text: t.savedChoice(input.what) });
      },
    },
  );
  const post = useWrite<{ ids: string[] }, PostedStatementTransactions>(
    'statements.post',
    (api, input) => api.call(statementsPost, { path: { statement_id: statementId }, body: { approved_ids: input.ids }, timeoutMs: 120_000 }),
    {
      invalidate: [...REVIEW_READS, ...LEDGER_READS],
      onSuccess: (result) => {
        setAsk(null);
        setSelected(new Set());
        setSaid({ text: t.posted(result.posted), posted: result.posted > 0 });
      },
    },
  );
  const discard = useWrite<{ ids: string[] }, { discarded: number }>(
    'statements.discard',
    (api, input) => api.call(statementsDiscard, { path: { statement_id: statementId }, body: { ids: input.ids } }),
    {
      invalidate: REVIEW_READS,
      onSuccess: (result) => {
        setAsk(null);
        setSelected(new Set());
        setSaid({ text: t.discarded(result.discarded) });
      },
    },
  );
  const write = ask?.kind === 'discard' ? discard : post;
  const failed = [choose, post, discard].find((w) => w.isError);

  return (
    <>
      <Section label={t.waiting} full>
        <Panel>
          <p className="section-help">{t.waitingHelp}</p>
          <Loaded query={query}>
            {({ transactions }) => {
              if (!transactions.length) return <Empty>{t.nothing}</Empty>;
              const picked = transactions.filter((x) => selected.has(x.id));
              return (
                <div className="stack-tight">
                  <div className="review-bar">
                    <Button variant="secondary" onPress={() => setSelected(new Set(transactions.filter(isClean).map((x) => x.id)))}>
                      {t.selectClear}
                    </Button>
                    <Button variant="tertiary" onPress={() => setSelected(new Set())} isDisabled={!selected.size}>
                      {t.selectNone}
                    </Button>
                    <span className="muted" aria-live="polite">
                      {t.selected(picked.length)}
                    </span>
                  </div>
                  <ul className="list review-list">
                    {transactions.map((txn) => (
                      <Item
                        key={txn.id}
                        txn={txn}
                        book={book}
                        rules={rules}
                        selected={selected.has(txn.id)}
                        choosing={choose.isPending && choosingId === txn.id}
                        onSelect={(on) =>
                          setSelected((now) => {
                            const next = new Set(now);
                            if (on) next.add(txn.id);
                            else next.delete(txn.id);
                            return next;
                          })
                        }
                        onChoose={(account) => {
                          setSaid({ text: '' });
                          setChoosingId(txn.id);
                          choose.mutate({ id: txn.id, account, what: shown(txn) });
                        }}
                        onRule={() => setRule(ruleFrom(txn))}
                      />
                    ))}
                  </ul>
                  <div className="form-actions">
                    <Button isDisabled={!picked.length} onPress={() => setAsk({ kind: 'post', ids: picked.map((x) => x.id) })}>
                      {t.post}
                    </Button>
                    <Button variant="secondary" isDisabled={!picked.length} onPress={() => setAsk({ kind: 'discard', ids: picked.map((x) => x.id) })}>
                      {t.discard}
                    </Button>
                  </div>
                  <Confirm
                    isOpen={ask !== null}
                    onOpenChange={(open) => (open ? undefined : setAsk(null))}
                    title={ask?.kind === 'discard' ? t.discardTitle : t.postTitle}
                    confirmLabel={ask?.kind === 'discard' ? t.discardConfirm : t.postConfirm}
                    cancelLabel={t.cancel}
                    isPending={write.isPending}
                    onConfirm={() => (ask ? write.mutate({ ids: ask.ids }) : undefined)}
                  >
                    {ask ? (
                      <>
                        <p>{ask.kind === 'discard' ? t.discardBody(ask.ids.length) : t.postBody(ask.ids.length)}</p>
                        {ask.kind === 'post' && picked.some((x) => !isComplete(x)) ? <p>{t.postIncomplete(picked.filter((x) => !isComplete(x)).length)}</p> : null}
                        {ask.kind === 'post' && picked.some((x) => x.dedup_status === 'fuzzy_match') ? <p>{t.postDuplicate}</p> : null}
                        <ul className="list confirm-list">
                          {picked.map((x) => (
                            <li key={x.id}>
                              {shown(x)} · <Money amount={x.amount} currency={x.currency} /> {x.credit_flag ? t.in : t.out}
                            </li>
                          ))}
                        </ul>
                      </>
                    ) : null}
                  </Confirm>
                </div>
              );
            }}
          </Loaded>
          <p role="status" className="quiet-success">
            {said.text ? (
              <>
                <span aria-hidden="true">✓</span> {said.text}{' '}
                {said.posted && period ? (
                  <Link to="/books/entries" search={{ account: period.account, from: period.from, to: period.to }}>
                    {t.seePosted}
                  </Link>
                ) : null}
              </>
            ) : null}
          </p>
          {failed ? <ProblemView error={failed.error} compact /> : null}
        </Panel>
      </Section>
      {rule ? (
        <Section label={t.makeRule} full>
          <Panel>
            <RuleForm
              key={JSON.stringify(rule)}
              book={book}
              start={rule}
              onSaved={(name) => {
                setRule(null);
                setSaid({ text: bookStrings.rules.saved(name) });
              }}
              onCancel={() => setRule(null)}
            />
          </Panel>
        </Section>
      ) : null}
    </>
  );
}

export function Review() {
  const params = useParams({ strict: false }) as { statement?: string };
  const id = decodeURIComponent(params.statement ?? '');
  const locale = useLocale();
  const { query, book } = useAccountBook();
  const statements = useRead('statements.list', statementsList, { query: { limit: 200 } });
  const statement = statements.data?.statements.find((s) => s.id === id);
  const period = periodOf(statement ?? { period_start: null, period_end: null }, locale);
  const title = statement ? t.titleOf(statementName(statement, book), period ? `, ${period}` : '') : t.title;
  const range =
    statement?.period_start && statement.period_end && statement.account_id
      ? { from: statement.period_start, to: statement.period_end, account: statement.account_id }
      : undefined;
  return (
    <Page title={statements.isSuccess && !statement ? t.notFound : title} description={t.description} facts={<BooksFacts />} actions={<BooksActions />}>
      <BooksNav />
      <p>
        <Link to="/books/imports">{t.back}</Link>
      </p>
      <Grid>
        <Loaded query={query}>{() => (book ? <Queue statementId={id} book={book} period={range} /> : null)}</Loaded>
      </Grid>
    </Page>
  );
}

export default Review;
