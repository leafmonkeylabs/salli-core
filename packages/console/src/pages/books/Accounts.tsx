/**
 * The chart of accounts (`accounts.list`, `ledger.trialBalance`,
 * `reports.balanceSheet`; docs/design/console.md, section 5): every account
 * by type, with its balance in your base currency as the trial balance keeps
 * it, and, for an account held in another currency, its balance in that
 * currency (`accounts.overview`), as `salli accounts list --balances` and
 * `salli accounts show` give them. Above them, the balance sheet's totals.
 * Nothing here is added up by the console.
 */
import { accountsOverview, ledgerTrialBalance, reportsBalanceSheet, type Account, type TrialBalance } from '@leafmonkeylabs/salli-sdk';
import { useRead } from '../../api';
import { AccountChip } from '../../kit/chips';
import { KeyFigure, KeyFigures } from '../../kit/figures';
import { Empty, Grid, Loaded, Page, Panel, Provenance, Section } from '../../kit/layout';
import { Money } from '../../kit/Money';
import { Table } from '../../kit/Table';
import { whereStrings } from '../../where-strings';
import { accountPath, BooksActions, BooksFacts, BooksNav, useAccountBook } from './ledger';

const b = whereStrings.books;
const TYPES = ['asset', 'liability', 'equity', 'income', 'expense'] as const;

/** The balance sheet's totals, as key figures. */
function Standing() {
  const query = useRead('reports.balanceSheet', reportsBalanceSheet);
  return (
    <Loaded query={query}>
      {(sheet) => (
        <KeyFigures label={b.standing}>
          <KeyFigure label={b.assets} note={b.standingHelp}>
            <Money amount={sheet.total_assets} currency={sheet.currency} variant="figure" />
          </KeyFigure>
          <KeyFigure label={b.liabilities}>
            <Money amount={sheet.total_liabilities} currency={sheet.currency} variant="figure" />
          </KeyFigure>
          <KeyFigure label={b.netWorth}>
            <Money amount={sheet.net_worth} currency={sheet.currency} variant="figure" />
          </KeyFigure>
        </KeyFigures>
      )}
    </Loaded>
  );
}

/** An account's balance in its own currency, when that isn't the base: from its overview. */
function NativeBalance({ account }: { account: Account }) {
  const query = useRead('accounts.overview', accountsOverview, { path: { account_id: account.id } });
  if (!query.data) return null;
  const balance = query.data.balance;
  return balance === null ? <span className="muted">{b.unknownNative(account.currency)}</span> : <Money amount={balance} currency={account.currency} variant="table" withCode />;
}

function TypeTable({ type, accounts, trial }: { type: (typeof TYPES)[number]; accounts: readonly Account[]; trial: TrialBalance }) {
  const code = trial.currency.toUpperCase();
  const rows = accounts.filter((a) => a.type === type);
  const foreign = rows.some((a) => a.currency.toUpperCase() !== code);
  return (
    <Section label={b.types[type] ?? type} full>
      <Panel>
        {rows.length ? (
          <Table<Account>
            caption={b.types[type] ?? type}
            captionHidden
            rows={rows}
            rowKey={(a) => a.id}
            columns={[
              {
                key: 'account',
                header: b.account,
                label: b.account,
                render: (a) => (
                  <>
                    <AccountChip code={a.code} name={a.name} type={a.type} typeLabel={b.typeOne[a.type] ?? a.type} to={accountPath(a.id)} />
                    {a.is_active ? null : <span className="tag"> {b.inactive}</span>}
                  </>
                ),
              },
              ...(type === 'asset' ? [{ key: 'holds', header: b.holds, label: b.holds, render: (a: Account) => (a.asset_role ? (b.roles[a.asset_role] ?? a.asset_role) : '') }] : []),
              { key: 'currency', header: b.currency, label: b.currency, render: (a) => <span className="mono">{a.currency}</span> },
              ...(foreign
                ? [
                    {
                      key: 'native',
                      header: b.inItsCurrency,
                      label: b.inItsCurrency,
                      align: 'end' as const,
                      render: (a: Account) => (a.currency.toUpperCase() === code ? null : <NativeBalance account={a} />),
                    },
                  ]
                : []),
              {
                key: 'balance',
                header: b.balanceIn(code),
                label: b.balanceIn(code),
                align: 'end',
                render: (a) => <Money amount={trial.balances[a.id] ?? '0'} currency={code} variant="table" />,
              },
            ]}
          />
        ) : (
          <Empty>{b.noneOfType}</Empty>
        )}
      </Panel>
    </Section>
  );
}

export function Accounts() {
  const { query, book } = useAccountBook();
  const trial = useRead('ledger.trialBalance', ledgerTrialBalance);
  return (
    <Page title={b.title} description={b.description} facts={<BooksFacts />} actions={<BooksActions />}>
      <BooksNav />
      <Standing />
      <Provenance>{b.balancesNote}</Provenance>
      <Grid>
        <Loaded query={query}>
          {() => (
            <Loaded query={trial}>
              {(balances) =>
                book?.accounts.length ? (
                  <>
                    {TYPES.map((type) => (
                      <TypeTable key={type} type={type} accounts={book.accounts} trial={balances} />
                    ))}
                  </>
                ) : (
                  <Empty>{b.noAccounts}</Empty>
                )
              }
            </Loaded>
          )}
        </Loaded>
      </Grid>
    </Page>
  );
}

export default Accounts;
