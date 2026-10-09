/**
 * salli portfolio transactions | lots | prices | performance
 *
 * A holding tracked by its transactions: buys, sales, income, splits and
 * transfers in, the lots they open and close, the prices you record (there
 * is no market feed), and performance over any period. Every figure is the
 * server's.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  holdingsList,
  holdingsLots,
  holdingsPerformance,
  holdingsTransactionsCreate,
  holdingsTransactionsDelete,
  holdingsTransactionsGet,
  holdingsTransactionsList,
  holdingsTransactionsUpdate,
  portfolioPerformance,
  portfolioPricesDelete,
  portfolioPricesList,
  portfolioPricesSet,
  type Holding,
  type HoldingTransaction,
  type HoldingTransactionRequest,
  type LotPickRequest,
  type PerformanceFigures,
  type SalliClient,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { NotFoundError, UsageError } from '../errors';
import type { Output } from '../output/output';
import { singleLine } from '../output/text';
import { displayDate, parseDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { renderRecord } from './records';
import { amountArg, collect, confirmAction, currencyArg } from './shared';

const KINDS = ['buy', 'sell', 'dividend', 'interest', 'split', 'transfer_in'] as const;

/** A holding by symbol (case does not matter) or id (or its start). */
export async function resolveHolding(api: SalliClient, query: string): Promise<Holding> {
  const { holdings } = await api.call(holdingsList, { query: { active_only: false } });
  const bySymbol = holdings.filter((h) => h.symbol.toLowerCase() === query.trim().toLowerCase());
  const [only] = bySymbol;
  if (bySymbol.length === 1 && only) return only;
  return resolveById(holdings, query, 'holding');
}

/** `LOT:QUANTITY`, for a sale that names its lots. */
function lotArg(value: string): LotPickRequest {
  const at = value.lastIndexOf(':');
  if (at <= 0) throw new UsageError(`--lot takes LOT_ID:QUANTITY (got "${value}").`);
  return { lot_id: value.slice(0, at), quantity: amountArg(value.slice(at + 1), '--lot') };
}

interface TransactionFlags {
  date?: string;
  quantity?: string;
  price?: string;
  fees?: string;
  amount?: string;
  withholdingTax?: string;
  ratio?: string;
  lot?: string[];
  fxRate?: string;
  note?: string;
}

/** The fields a transaction's flags set, as the API takes them. */
function transactionFields(app: App, flags: TransactionFlags): Omit<HoldingTransactionRequest, 'kind' | 'date'> & { date?: string } {
  const now = app.runtime.now();
  return {
    ...(flags.date ? { date: parseDate(flags.date, now, '--date') } : {}),
    ...(flags.quantity ? { quantity: amountArg(flags.quantity, '--quantity') } : {}),
    ...(flags.price ? { price: amountArg(flags.price, '--price') } : {}),
    ...(flags.fees ? { fees: amountArg(flags.fees, '--fees') } : {}),
    ...(flags.amount ? { amount: amountArg(flags.amount, '--amount') } : {}),
    ...(flags.withholdingTax ? { withholding_tax: amountArg(flags.withholdingTax, '--withholding-tax') } : {}),
    ...(flags.ratio ? { ratio: flags.ratio.trim() } : {}),
    ...(flags.lot?.length ? { lots: flags.lot.map(lotArg) } : {}),
    ...(flags.fxRate ? { fx_rate: amountArg(flags.fxRate, '--fx-rate') } : {}),
    ...(flags.note ? { note: flags.note } : {}),
  };
}

/** Options shared by `transactions add` and `update`. */
function withTransactionOptions<T extends Command<[string, ...unknown[]]>>(command: T): T {
  return command
    .option('--quantity <n>', 'Units, for a buy, sale or transfer in')
    .option('--price <amount>', 'Per unit, for a buy or sale')
    .option('--fees <amount>', 'Fees, in the holding’s currency')
    .option('--amount <amount>', 'Gross income (dividend, interest), or a transfer’s total cost')
    .option('--withholding-tax <amount>', 'Tax withheld from income')
    .option('--ratio <new:old>', 'A split’s new units to old, e.g. 2:1')
    .option('--lot <lot:quantity>', 'For a sale: a lot to sell from (repeatable; default: oldest first)', collect)
    .option('--fx-rate <rate>', 'Base currency per unit of the holding’s, as the broker used')
    .option('--note <text>', 'A note') as unknown as T;
}

function transactionTable(out: Output, list: readonly HoldingTransaction[]): string {
  return out.table(list, [
    { header: 'DATE', get: (t) => displayDate(t.date, out.locale) },
    { header: 'KIND', get: (t) => t.kind.replace('_', ' ') },
    { header: 'QUANTITY', get: (t) => t.quantity ?? (t.ratio ? `split ${t.ratio}` : ''), align: 'right' },
    { header: 'PRICE', get: (t) => (t.price ? out.amount(t.price, t.currency) : ''), align: 'right' },
    { header: `TOTAL`, get: (t) => (t.total ? out.money(t.total, t.currency) : ''), align: 'right' },
    { header: 'NOTE', get: (t) => t.note ?? '', shrink: true },
    { header: 'ID', get: (t) => t.id.slice(0, 8), style: (s) => out.colors.dim(s) },
  ]);
}

function figuresRows(out: Output, f: PerformanceFigures): Array<readonly [string, string]> {
  const m = (v: string): string => out.money(v, f.currency);
  return [
    ['Value', `${m(f.opening_value)} → ${m(f.closing_value)}`],
    ['Paid in / taken out', `${m(f.paid_in)} / ${m(f.taken_out)}`],
    ['Realised gain', m(f.realised_gain)],
    ['Unrealised gain', m(f.unrealised_gain)],
    ['Income', `${m(f.net_income)} (dividends ${m(f.dividends)}, interest ${m(f.interest)}, tax ${m(f.withholding_tax)})`],
    ['Total return', m(f.total_return)],
    ['Time-weighted', f.twr === null ? '—' : `${out.percent(f.twr, 2)}${f.twr_annualised ? ` (${out.percent(f.twr_annualised, 2)} a year)` : ''}`],
    ['Money-weighted (XIRR)', f.xirr === null ? '—' : out.percent(f.xirr, 2)],
  ];
}

export function registerInvestments(portfolio: Command, app: App): void {
  portfolio
    .command('performance')
    .argument('[holding]', 'One holding (symbol or id); default: the whole portfolio')
    .description('Gains, income and returns over a period (default: this year so far)')
    .option('--from <date>', 'From this date (YYYY-MM-DD)')
    .option('--to <date>', 'Up to this date (default: today)')
    .action(async (query, opts) => {
      const now = app.runtime.now();
      const period = {
        ...(opts.from ? { from_date: parseDate(opts.from, now, '--from') } : {}),
        ...(opts.to ? { to_date: parseDate(opts.to, now, '--to') } : {}),
      };
      const api = await app.api();
      const holding = query ? await resolveHolding(api, query) : undefined;
      const data = holding
        ? await api.call(holdingsPerformance, { path: { holding_id: holding.id }, query: period })
        : await api.call(portfolioPerformance, { query: period });
      app.out.emit(data, {
        records: (d) => d.holdings,
        human: (d) => {
          const out = app.out;
          out.line(`${out.heading(holding ? `${holding.symbol} performance` : 'Portfolio performance')} ${out.colors.dim(`${displayDate(d.start, out.locale)} – ${displayDate(d.end, out.locale)} · ${d.days} days`)}`);
          out.line(out.details(figuresRows(out, d.portfolio)));
          if (!holding && d.holdings.length) {
            out.line();
            out.line(
              out.table(d.holdings, [
                { header: 'HOLDING', get: (h) => `${h.symbol} ${h.name}`, shrink: true },
                { header: `VALUE (${d.base_currency})`, get: (h) => out.amount(h.base.closing_value, h.base.currency), align: 'right' },
                { header: 'TOTAL RETURN', get: (h) => out.amount(h.base.total_return, h.base.currency), align: 'right', style: (t, h) => out.signed(t, h.base.total_return) },
                { header: 'TWR', get: (h) => (h.base.twr === null ? '—' : out.percent(h.base.twr, 1)), align: 'right' },
              ]),
            );
          }
          for (const note of d.notes) out.note(singleLine(note));
        },
      });
    });

  portfolio
    .command('lots')
    .argument('<holding>', 'Symbol or id')
    .description('A holding’s lots, open and closed, and the sales that consumed them')
    .action(async (query) => {
      const api = await app.api();
      const holding = await resolveHolding(api, query);
      const data = await api.call(holdingsLots, { path: { holding_id: holding.id } });
      app.out.emit(data, {
        records: (d) => d.lots,
        human: (d) => {
          const out = app.out;
          out.line(`${out.heading(`${holding.symbol} lots`)} ${out.colors.dim(`${d.quantity} held, cost ${out.money(d.cost, d.currency)}`)}`);
          if (!d.lots.length) return out.note('No lots yet: record a buy with `salli portfolio transactions add`.');
          out.line(
            out.table(d.lots, [
              { header: 'OPENED', get: (l) => displayDate(l.opened_on, out.locale) },
              { header: 'KIND', get: (l) => l.kind.replace('_', ' ') },
              { header: 'OPENED WITH', get: (l) => l.opened_quantity, align: 'right' },
              { header: 'HELD', get: (l) => l.quantity, align: 'right', style: (t, l) => (l.is_open ? t : out.colors.dim(t)) },
              { header: `COST (${d.currency})`, get: (l) => out.amount(l.cost, d.currency), align: 'right' },
              { header: 'PER UNIT', get: (l) => (l.cost_per_unit ? out.amount(l.cost_per_unit, d.currency) : ''), align: 'right' },
              { header: 'LOT', get: (l) => l.id.slice(0, 8), style: (t) => out.colors.dim(t) },
            ]),
          );
          if (d.sales.length) {
            out.line();
            out.line(out.heading('Sales'));
            out.line(
              out.table(d.sales, [
                { header: 'DATE', get: (s) => displayDate(s.date, out.locale) },
                { header: 'QUANTITY', get: (s) => s.quantity, align: 'right' },
                { header: `PROCEEDS (${d.currency})`, get: (s) => out.amount(s.proceeds, d.currency), align: 'right' },
                { header: 'GAIN', get: (s) => out.amount(s.gain, d.currency), align: 'right', style: (t, s) => out.signed(t, s.gain) },
                { header: `GAIN (${d.base_currency})`, get: (s) => out.amount(s.gain_base, d.base_currency), align: 'right' },
              ]),
            );
          }
        },
      });
    });

  const prices = portfolio.command('prices').alias('price').description('Prices you record for your holdings (there is no market feed)');

  prices
    .command('list')
    .alias('ls')
    .description('Recorded prices, newest first')
    .option('--symbol <symbol>', 'Only this symbol')
    .option('--from <date>', 'From this date')
    .option('--to <date>', 'Up to this date')
    .action(async (opts) => {
      const now = app.runtime.now();
      const api = await app.api();
      const data = await api.call(portfolioPricesList, {
        query: {
          ...(opts.symbol ? { symbol: opts.symbol } : {}),
          ...(opts.from ? { from_date: parseDate(opts.from, now, '--from') } : {}),
          ...(opts.to ? { to_date: parseDate(opts.to, now, '--to') } : {}),
        },
      });
      app.out.emit(data, {
        records: (d) => d.prices,
        human: (d) => {
          const out = app.out;
          if (!d.prices.length) return out.note('No prices recorded. Record one with `salli portfolio prices set`.');
          out.line(
            out.table(d.prices, [
              { header: 'SYMBOL', get: (p) => p.symbol },
              { header: 'DATE', get: (p) => displayDate(p.date, out.locale) },
              { header: 'CLOSE', get: (p) => out.money(p.close, p.currency), align: 'right' },
              { header: 'SOURCE', get: (p) => p.source },
              { header: 'ID', get: (p) => p.id.slice(0, 8), style: (t) => out.colors.dim(t) },
            ]),
          );
        },
      });
    });

  prices
    .command('set')
    .argument('<symbol>', 'e.g. VTI')
    .argument('<close>', 'The closing price')
    .description('Record a price (replaces the one for that day)')
    .option('--date <date>', 'The day it was quoted (default: today)')
    .option('--currency <code>', 'Its currency (default: your holdings’ with this symbol)')
    .action(async (symbol, close, opts) => {
      const api = await app.api();
      const created = await api.call(portfolioPricesSet, {
        body: {
          symbol,
          close: amountArg(close, 'close'),
          ...(opts.date ? { date: parseDate(opts.date, app.runtime.now(), '--date') } : {}),
          ...(opts.currency ? { currency: currencyArg(opts.currency) } : {}),
        },
      });
      app.out.done(created, `Recorded ${singleLine(symbol)} at ${close}.`);
    });

  prices
    .command('delete')
    .argument('<price>', 'Price id (or its start), from `salli portfolio prices list`')
    .description('Delete a recorded price')
    .action(async (query) => {
      const api = await app.api();
      const price = resolveById((await api.call(portfolioPricesList)).prices, query, 'price');
      await api.call(portfolioPricesDelete, { path: { quote_id: price.id } });
      app.out.done({ id: price.id, deleted: true }, `Deleted the ${singleLine(price.symbol)} price of ${displayDate(price.date, app.out.locale)}.`);
    });

  const transactions = portfolio
    .command('transactions')
    .alias('transaction')
    .description('A holding’s buys, sales, income, splits and transfers in');

  transactions
    .command('list')
    .alias('ls')
    .argument('<holding>', 'Symbol or id')
    .description('A holding’s transactions, in the order they take effect')
    .action(async (query) => {
      const api = await app.api();
      const holding = await resolveHolding(api, query);
      const data = await api.call(holdingsTransactionsList, { path: { holding_id: holding.id } });
      app.out.emit(data, {
        records: (d) => d.transactions,
        human: (d) => {
          if (!d.transactions.length) return app.out.note(`No transactions for ${singleLine(holding.symbol)} yet.`);
          app.out.line(transactionTable(app.out, d.transactions));
        },
      });
    });

  withTransactionOptions(
    transactions
      .command('add')
      .argument('<holding>', 'Symbol or id')
      .argument('<kind>', KINDS.join(', '))
      .description('Record a transaction: its lots and the holding’s figures follow from it')
      .option('--date <date>', 'When (YYYY-MM-DD; default today)'),
  )
    .addHelpText(
      'after',
      `
Examples:
  $ salli portfolio transactions add VTI buy --quantity 10 --price 240.15 --fees 1
  $ salli portfolio transactions add VTI dividend --amount 18.40 --withholding-tax 2.76
  $ salli portfolio transactions add VTI split --ratio 2:1 --date 2026-06-01
  $ salli portfolio transactions add VTI sell --quantity 5 --price 260 --lot 3fa85f64:5`,
    )
    .action(async (query, kind, opts) => {
      if (!(KINDS as readonly string[]).includes(kind)) throw new UsageError(`A transaction is one of: ${KINDS.join(', ')} (got "${kind}").`);
      const fields = transactionFields(app, opts as TransactionFlags);
      const api = await app.api();
      const holding = await resolveHolding(api, query);
      const created = await api.call(holdingsTransactionsCreate, {
        path: { holding_id: holding.id },
        body: { kind: kind as HoldingTransactionRequest['kind'], date: fields.date ?? parseDate('today', app.runtime.now()), ...fields },
      });
      app.out.done(created, `Recorded a ${kind.replace('_', ' ')} of ${singleLine(holding.symbol)}.`);
    });

  const resolveTransaction = async (api: SalliClient, holding: Holding, query: string): Promise<HoldingTransaction> =>
    resolveById((await api.call(holdingsTransactionsList, { path: { holding_id: holding.id } })).transactions, query, 'transaction');

  transactions
    .command('show')
    .argument('<holding>', 'Symbol or id')
    .argument('<transaction>', 'Transaction id (or its start)')
    .description('One transaction in full')
    .action(async (query, txnQuery) => {
      const api = await app.api();
      const holding = await resolveHolding(api, query);
      const found = await resolveTransaction(api, holding, txnQuery);
      const data = await api.call(holdingsTransactionsGet, { path: { holding_id: holding.id, transaction_id: found.id } });
      app.out.emit(data, {
        human: (d) => app.out.line(renderRecord(app, d, { money: ['price', 'fees', 'amount', 'withholding_tax', 'total'], hide: ['lots', 'holding_id'] })),
      });
    });

  withTransactionOptions(
    transactions
      .command('update')
      .argument('<holding>', 'Symbol or id')
      .argument('<transaction>', 'Transaction id (or its start)')
      .description('Change a transaction')
      .addOption(new Option('--kind <kind>', 'New kind').choices(KINDS))
      .option('--date <date>', 'New date'),
  ).action(async (query, txnQuery, opts) => {
    const flags = opts as TransactionFlags & { kind?: (typeof KINDS)[number] };
    const body = { ...(flags.kind ? { kind: flags.kind } : {}), ...transactionFields(app, flags) };
    if (!Object.keys(body).length) throw new UsageError('Nothing to change.', 'See `salli portfolio transactions update --help`.');
    const api = await app.api();
    const holding = await resolveHolding(api, query);
    const found = await resolveTransaction(api, holding, txnQuery);
    const result = await api.call(holdingsTransactionsUpdate, { path: { holding_id: holding.id, transaction_id: found.id }, body });
    app.out.done(result, 'Transaction updated.');
  });

  transactions
    .command('delete')
    .argument('<holding>', 'Symbol or id')
    .argument('<transaction>', 'Transaction id (or its start)')
    .description('Delete a transaction (its lots and the figures follow)')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, txnQuery, opts) => {
      const api = await app.api();
      const holding = await resolveHolding(api, query);
      const found = await resolveTransaction(api, holding, txnQuery);
      if (!found) throw new NotFoundError(`No transaction "${txnQuery}".`);
      if (!(await confirmAction(app, opts.yes, `Delete the ${found.kind.replace('_', ' ')} of ${displayDate(found.date, app.out.locale)}?`))) return;
      await api.call(holdingsTransactionsDelete, { path: { holding_id: holding.id, transaction_id: found.id } });
      app.out.done({ id: found.id, deleted: true }, 'Transaction deleted.');
    });
}
