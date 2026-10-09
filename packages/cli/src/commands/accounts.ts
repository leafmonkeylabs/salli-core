/**
 * salli accounts list | show | add | update | deactivate | reactivate
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  accountsCreate,
  accountsDeactivate,
  accountsOverview,
  accountsReactivate,
  accountsUpdate,
  ledgerTrialBalance,
  type Account,
  type AddAccountRequest,
  type UpdateAccountRequest,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import { singleLine } from '../output/text';
import { displayDate, parseDate } from '../util/dates';
import { AccountBook, currencyArg } from './shared';

const TYPES = ['asset', 'liability', 'equity', 'income', 'expense'] as const;
const TAX_ROLES = ['apit_credit', 'ait_credit', 'foreign_tax_credit', 'qualifying_payment', 'fsi_income'] as const;
type AccountType = (typeof TYPES)[number];
type TaxRole = (typeof TAX_ROLES)[number];

function accountType(value: string): AccountType {
  const type = value.trim().toLowerCase();
  if (!(TYPES as readonly string[]).includes(type)) {
    throw new UsageError(`An account type is one of: ${TYPES.join(', ')} (got "${value}").`);
  }
  return type as AccountType;
}

export function registerAccounts(program: Command, app: App): void {
  const accounts = program
    .command('accounts')
    .alias('account')
    .description('Your chart of accounts: list, inspect, add and change accounts')
    .addHelpText(
      'after',
      `
Accounts can be named by code (1000), name (Cash, or a unique start of it) or id.

Examples:
  $ salli accounts list --type expense
  $ salli accounts show checking
  $ salli accounts add 1300 Brokerage asset --currency USD`,
    );

  accounts
    .command('list')
    .alias('ls')
    .description('List accounts')
    .addOption(new Option('--type <type>', 'Only this type').choices(TYPES))
    .option('--active', 'Only active accounts')
    .option('--balances', 'Add each account’s balance (in your base currency)')
    .action(async (opts) => {
      const api = await app.api();
      const book = await AccountBook.load(api);
      let list = book.accounts;
      if (opts.type) list = list.filter((a) => a.type === opts.type);
      if (opts.active) list = list.filter((a) => a.is_active);
      const filtered = opts.type !== undefined || opts.active === true;
      const trial = opts.balances ? await api.call(ledgerTrialBalance) : undefined;
      const data = trial ? { accounts: filtered ? list : book.accounts, trial_balance: trial } : filtered ? list : book.accounts;

      app.out.emit(data, {
        records: () => list.map((a) => (trial ? { ...a, balance: trial.balances[a.id] ?? '0', balance_currency: trial.currency } : a)),
        human: () => {
          if (list.length === 0) {
            app.out.note(book.accounts.length ? 'No accounts match.' : 'No accounts yet. Add one with `salli accounts add`.');
            return;
          }
          const c = app.out.colors;
          app.out.line(
            app.out.table(list, [
              { header: 'CODE', get: (a) => a.code },
              { header: 'NAME', get: (a) => a.name, shrink: true, style: (t, a) => (a.is_active ? t : c.dim(t)) },
              { header: 'TYPE', get: (a) => a.type },
              { header: 'CURRENCY', get: (a) => a.currency },
              ...(trial
                ? [
                    {
                      header: `BALANCE (${trial.currency})`,
                      get: (a: Account) => app.out.amount(trial.balances[a.id] ?? '0', trial.currency),
                      align: 'right' as const,
                    },
                  ]
                : []),
              { header: 'STATUS', get: (a) => (a.is_active ? '' : 'inactive'), style: (t) => c.dim(t) },
              { header: 'ID', get: (a) => a.id.slice(0, 8), style: (t) => c.dim(t) },
            ]),
          );
          if (trial) app.out.note('Balances as the trial balance keeps them: debits positive, credits (what you owe, income) negative.');
        },
      });
    });

  accounts
    .command('show')
    .argument('<account>', 'Code, name or id')
    .description('Show an account: its balance and transactions')
    .option('--from <date>', 'Transactions from this date (YYYY-MM-DD)')
    .option('--to <date>', 'Transactions up to this date')
    .action(async (query, opts) => {
      const api = await app.api();
      const account = (await AccountBook.load(api)).resolve(query);
      const now = app.runtime.now();
      const overview = await api.call(accountsOverview, {
        path: { account_id: account.id },
        query: {
          ...(opts.from ? { from_date: parseDate(opts.from, now, '--from') } : {}),
          ...(opts.to ? { to_date: parseDate(opts.to, now, '--to') } : {}),
        },
      });
      app.out.emit(overview, {
        records: (o) => o.transactions,
        human: (o) => {
          const out = app.out;
          const c = out.colors;
          const a = o.account;
          const foreign = a.currency !== o.base_currency;
          out.line(out.heading(`${a.code} ${a.name}`));
          out.line(
            out.details([
              ['Type', a.type + (a.tax_role ? ` (tax: ${a.tax_role})` : '')],
              ['Currency', a.currency],
              ['Status', a.is_active ? 'active' : 'inactive', a.is_active ? undefined : c.yellow],
              ['Balance', foreign ? out.money(o.balance, a.currency) : out.money(o.current_balance, o.base_currency)],
              foreign ? ['Book value', `${out.money(o.current_balance, o.base_currency)} (at the rates its entries recorded)`] : false,
              ['ID', a.id, c.dim],
            ]),
          );
          out.line();
          if (o.transactions.length === 0) {
            out.note('No transactions in this period.');
            return;
          }
          const native = foreign && o.transactions.every((t) => t.running_balance_native !== null);
          const shownIn = native ? a.currency : o.base_currency;
          out.line(
            out.table(o.transactions, [
              { header: 'DATE', get: (t) => displayDate(t.entry_date, out.locale) },
              { header: 'DESCRIPTION', get: (t) => t.description, shrink: true },
              { header: 'SOURCE', get: (t) => t.source, style: (s) => c.dim(s) },
              {
                header: `BALANCE (${shownIn})`,
                get: (t) => out.amount(native ? t.running_balance_native : t.running_balance, shownIn),
                align: 'right',
              },
              { header: 'ENTRY', get: (t) => t.entry_id.slice(0, 8), style: (s) => c.dim(s) },
            ]),
          );
        },
      });
    });

  accounts
    .command('add')
    .argument('[code]', 'Account code, e.g. 1300')
    .argument('[name]', 'Account name, e.g. Brokerage')
    .argument('[type]', `One of: ${TYPES.join(', ')}`)
    .description('Add an account')
    .option('--currency <code>', 'Currency it is held in (default: your base currency)')
    .option('--parent <account>', 'Parent account (code, name or id)')
    .addOption(new Option('--tax-role <role>', 'How the tax engine treats it').choices(TAX_ROLES))
    .action(async (codeArg, nameArg, typeArg, opts) => {
      let [code, name, type] = [codeArg, nameArg, typeArg];
      if (!code || !name || !type) {
        if (!app.prompter.interactive) {
          throw new UsageError('accounts add needs a code, a name and a type.', 'e.g. salli accounts add 1300 Brokerage asset');
        }
        code ??= await app.prompter.text({ message: 'Code', placeholder: '1300', validate: (v) => (v.trim() ? undefined : 'A code is required') });
        name ??= await app.prompter.text({ message: 'Name', placeholder: 'Brokerage', validate: (v) => (v.trim() ? undefined : 'A name is required') });
        type ??= await app.prompter.select({
          message: 'Type',
          options: TYPES.map((t) => ({ value: t, label: t })),
        });
      }
      const api = await app.api();
      const body: AddAccountRequest = { code: code.trim(), name: name.trim(), type: accountType(type) };
      if (opts.currency) body.currency = currencyArg(opts.currency);
      if (opts.parent) body.parent_id = (await AccountBook.load(api)).resolve(opts.parent).id;
      if (opts.taxRole) body.tax_role = opts.taxRole as TaxRole;
      const created = await api.call(accountsCreate, { body });
      if (app.out.machine) app.out.emit(created, { human: () => undefined });
      else app.out.success(`Added ${body.code} ${body.name} (${body.type}${body.currency ? `, ${body.currency}` : ''}) ${app.out.errColors.dim(created.id)}`);
    });

  accounts
    .command('update')
    .argument('<account>', 'Code, name or id')
    .description('Change an account’s code, name, type, currency or tax role')
    .option('--code <code>', 'New code')
    .option('--name <name>', 'New name')
    .addOption(new Option('--type <type>', 'New type').choices(TYPES))
    .option('--currency <code>', 'New currency (only while it has no entries)')
    .addOption(new Option('--tax-role <role>', 'New tax role').choices(TAX_ROLES))
    .option('--no-tax-role', 'Clear its tax role')
    .action(async (query, opts) => {
      const api = await app.api();
      const account = (await AccountBook.load(api)).resolve(query);
      const changingTaxRole = typeof opts.taxRole === 'string';
      const clearingTaxRole = opts.taxRole === false;
      if (!opts.code && !opts.name && !opts.type && !opts.currency && !changingTaxRole && !clearingTaxRole) {
        throw new UsageError('Nothing to change.', 'Pass --code, --name, --type, --currency, --tax-role or --no-tax-role.');
      }
      // The API replaces code, name and type together, so unchanged ones are sent as they are.
      const body: UpdateAccountRequest = {
        code: opts.code ?? account.code,
        name: opts.name ?? account.name,
        type: (opts.type as AccountType | undefined) ?? account.type,
      };
      if (opts.currency) body.currency = currencyArg(opts.currency);
      if (changingTaxRole) body.tax_role = opts.taxRole as TaxRole;
      if (clearingTaxRole) body.tax_role = null;
      const updated = await api.call(accountsUpdate, { path: { account_id: account.id }, body });
      if (app.out.machine) app.out.emit(updated, { human: () => undefined });
      else app.out.success(`Updated ${body.code} ${body.name}.`);
    });

  accounts
    .command('deactivate')
    .argument('<account>', 'Code, name or id')
    .description('Hide an account from use (its history stays; reactivate any time)')
    .action(async (query) => {
      const api = await app.api();
      const account = (await AccountBook.load(api)).resolve(query);
      await api.call(accountsDeactivate, { path: { account_id: account.id } });
      app.out.done({ id: account.id, is_active: false }, `Deactivated ${singleLine(`${account.code} ${account.name}`)}.`);
    });

  accounts
    .command('reactivate')
    .argument('<account>', 'Code, name or id')
    .description('Bring a deactivated account back')
    .action(async (query) => {
      const api = await app.api();
      const account = (await AccountBook.load(api)).resolve(query);
      const result = await api.call(accountsReactivate, { path: { account_id: account.id } });
      if (app.out.machine) app.out.emit(result, { human: () => undefined });
      else app.out.success(`Reactivated ${singleLine(`${account.code} ${account.name}`)}.`);
    });
}
