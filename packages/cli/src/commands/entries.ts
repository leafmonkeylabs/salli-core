/**
 * salli entries list | show | add | reverse | tag
 *
 * Posted entries are never edited: a mistake is corrected by reversing the
 * entry (a new entry that cancels it) and posting the right one.
 */
import type { Command } from '@commander-js/extra-typings';
import {
  entriesCreate,
  entriesGet,
  entriesList,
  entriesPostingsSetTags,
  entriesProvenance,
  entriesReverse,
  type AddEntryRequest,
  type JournalEntry,
  type Posting,
  type PostingRequest,
  type SalliClient,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import { singleLine } from '../output/text';
import { displayDate, displayRange, monthPeriod, parseDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { AccountBook, accountAmountArg, amountArg, collect, confirmAction, currencyArg, limitArg, tagArgs } from './shared';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** An entry by id or unique id prefix. */
export async function findEntry(api: SalliClient, query: string): Promise<JournalEntry> {
  if (UUID.test(query.trim())) return await api.call(entriesGet, { path: { entry_id: query.trim() } });
  return resolveById(await api.call(entriesList), query, 'entry');
}

/** One line about an entry's money: the amount, and from where to where. */
export function describeEntry(app: App, entry: JournalEntry, book: AccountBook): { amount: string; debit: string; credit: string } {
  const debits = entry.postings.filter((p) => p.direction > 0);
  const credits = entry.postings.filter((p) => p.direction < 0);
  const side = (postings: Posting[]): string =>
    postings.length === 0 ? '—' : postings.length === 1 ? book.name(postings[0]?.account_id) : `${book.name(postings[0]?.account_id)} +${postings.length - 1}`;
  const first = debits[0];
  return {
    amount: debits.length === 1 && first ? app.out.money(first.amount, first.currency) : `${debits.length} parts`,
    debit: side(debits),
    credit: side(credits),
  };
}

export function registerEntries(program: Command, app: App): void {
  const entries = program
    .command('entries')
    .alias('entry')
    .description('Journal entries: list, inspect, post, reverse and tag')
    .addHelpText(
      'after',
      `
An entry moves money between accounts: the debit side receives, the credit
side gives. Amounts are exact decimals; the server checks that they balance.

Examples:
  $ salli entries list --month 2026-10
  $ salli entries add --desc "Lunch" --debit groceries:12.50 --credit cash:12.50
  $ salli entries reverse 3fa85f64
  $ salli add "lunch 12.50 cash"          (let the AI draft it)`,
    );

  entries
    .command('list')
    .alias('ls')
    .description('List entries')
    .option('--from <date>', 'From this date (YYYY-MM-DD)')
    .option('--to <date>', 'Up to this date')
    .option('--month <yyyy-mm>', 'One calendar month')
    .option('--account <account>', 'Only entries touching this account')
    .option('--search <text>', 'Only entries whose description contains this')
    .option('--limit <n>', 'At most this many, the most recent (tables default to 30)', limitArg)
    .action(async (opts) => {
      if (opts.month && (opts.from || opts.to)) throw new UsageError('Pass --month, or --from/--to, not both.');
      const now = app.runtime.now();
      const range = opts.month
        ? monthPeriod(opts.month, now, app.out.locale)
        : {
            ...(opts.from ? { from: parseDate(opts.from, now, '--from') } : {}),
            ...(opts.to ? { to: parseDate(opts.to, now, '--to') } : {}),
          };
      const api = await app.api();
      const [all, book] = await Promise.all([
        api.call(entriesList, {
          query: { ...(range.from ? { from_date: range.from } : {}), ...(range.to ? { to_date: range.to } : {}) },
        }),
        AccountBook.load(api),
      ]);
      let list = all;
      const account = opts.account ? book.resolve(opts.account) : undefined;
      if (account) list = list.filter((e) => e.postings.some((p) => p.account_id === account.id));
      if (opts.search) {
        const needle = opts.search.toLowerCase();
        list = list.filter((e) => e.description.toLowerCase().includes(needle));
      }
      const sorted = [...list].sort((a, b) => a.entry_date.localeCompare(b.entry_date));
      const limit = opts.limit ?? (app.out.machine ? undefined : 30);
      const shown = limit !== undefined ? sorted.slice(-limit) : sorted;
      const narrowed = account !== undefined || opts.search !== undefined || opts.limit !== undefined;

      app.out.emit(narrowed ? shown : all, {
        human: () => {
          if (shown.length === 0) {
            app.out.note(all.length ? 'No entries match.' : 'No entries in this period.');
            return;
          }
          const c = app.out.colors;
          app.out.line(
            app.out.table(shown, [
              { header: 'DATE', get: (e) => displayDate(e.entry_date, app.out.locale) },
              {
                header: 'DESCRIPTION',
                get: (e) => e.description + (e.reversed_by ? '  (reversed)' : ''),
                shrink: true,
                style: (t, e) => (e.reversed_by ? c.dim(t) : t),
              },
              { header: 'AMOUNT', get: (e) => describeEntry(app, e, book).amount, align: 'right' },
              { header: 'DEBIT', get: (e) => describeEntry(app, e, book).debit, shrink: true },
              { header: 'CREDIT', get: (e) => describeEntry(app, e, book).credit, shrink: true },
              { header: 'ID', get: (e) => e.id.slice(0, 8), style: (t) => c.dim(t) },
            ]),
          );
          if (shown.length < list.length) app.out.note(`Showing the latest ${shown.length} of ${list.length}; use --limit or --month for more.`);
        },
      });
    });

  entries
    .command('show')
    .argument('<id>', 'Entry id (or the start of one)')
    .description('Show an entry: its postings, tags and where it came from')
    .action(async (query) => {
      const api = await app.api();
      const entry = await findEntry(api, query);
      const [provenance, book] = await Promise.all([
        api.call(entriesProvenance, { path: { entry_id: entry.id } }),
        AccountBook.load(api),
      ]);
      app.out.emit(
        { entry, provenance },
        {
          records: (d) => d.entry.postings,
          human: () => {
            const out = app.out;
            const c = out.colors;
            out.line(out.heading(entry.description));
            out.line(
              out.details([
                ['Date', displayDate(entry.entry_date, out.locale)],
                ['Source', entry.source],
                ['Reversed by', entry.reversed_by, c.yellow],
                ['ID', entry.id, c.dim],
              ]),
            );
            out.line();
            out.line(
              out.table(entry.postings, [
                { header: 'ACCOUNT', get: (p) => book.label(p.account_id), shrink: true },
                { header: 'DEBIT', get: (p) => (p.direction > 0 ? out.amount(p.amount, p.currency) : ''), align: 'right' },
                { header: 'CREDIT', get: (p) => (p.direction < 0 ? out.amount(p.amount, p.currency) : ''), align: 'right' },
                { header: 'CURRENCY', get: (p) => p.currency },
                { header: 'RATE', get: (p) => (p.fx_rate && p.fx_rate !== '1' && !/^1\.0*$/.test(p.fx_rate) ? p.fx_rate : ''), align: 'right' },
                { header: 'TAGS', get: (p) => Object.entries(p.tags ?? {}).map(([k, v]) => `${k}=${v}`).join(' '), shrink: true },
                { header: 'POSTING', get: (p) => p.id.slice(0, 8), style: (t) => c.dim(t) },
              ]),
            );
            const statement = provenance.statement;
            if (statement) {
              const s = statement.statement;
              out.line();
              out.line(
                `${c.dim('From a bank statement:')} “${singleLine(statement.raw_description)}” ${out.amount(statement.raw_amount, statement.currency)} on ${displayDate(statement.raw_date, out.locale)}` +
                  (s?.bank ? ` · ${singleLine(s.bank)}` : '') +
                  (s?.period_start ? ` · statement for ${displayRange(s.period_start, s.period_end, out.locale)}` : ''),
              );
            } else if (provenance.receipt) {
              out.line();
              out.line(`${c.dim('Receipt:')} ${singleLine(`${provenance.receipt.title} (${provenance.receipt.mime_type})`)} ${c.dim(singleLine(provenance.receipt.document_id))}`);
            }
          },
        },
      );
    });

  entries
    .command('add')
    .description('Post a balanced entry from ACCOUNT:AMOUNT pairs')
    .requiredOption('--desc <text>', 'What it was')
    .option('--date <date>', 'When (YYYY-MM-DD, today, yesterday)', 'today')
    .requiredOption('--debit <account:amount>', 'The receiving side (repeat to split)', collect)
    .requiredOption('--credit <account:amount>', 'The giving side (repeat to split)', collect)
    .option('--currency <code>', 'Currency of the amounts (default: your base currency)')
    .option('--fx-rate <rate>', 'Units of your base currency per unit of --currency (default: the published rate)')
    .option('--tag <axis=slug>', 'Tag the debit side, e.g. category=groceries (repeatable)', collect)
    .option('--receipt <document-id>', 'Attach a stored document (see `salli documents`)')
    .action(async (opts) => {
      const api = await app.api();
      const book = await AccountBook.load(api);
      const currency = opts.currency ? currencyArg(opts.currency) : undefined;
      const fxRate = opts.fxRate ? amountArg(opts.fxRate, '--fx-rate') : undefined;
      if (fxRate && !currency) throw new UsageError('--fx-rate needs --currency (the currency it converts from).');
      const tags = tagArgs(opts.tag ?? []);
      const posting = (value: string, direction: 1 | -1, flag: string): PostingRequest => {
        const { account, amount } = accountAmountArg(value, flag);
        const resolved = book.resolve(account);
        return {
          account_id: resolved.id,
          direction,
          amount,
          ...(currency ? { currency } : {}),
          ...(fxRate ? { fx_rate: fxRate } : {}),
          ...(direction > 0 && Object.keys(tags).length ? { tags } : {}),
        };
      };
      const body: AddEntryRequest = {
        entry_date: parseDate(opts.date, app.runtime.now(), '--date'),
        description: opts.desc,
        postings: [...opts.debit.map((d) => posting(d, 1, '--debit')), ...opts.credit.map((c) => posting(c, -1, '--credit'))],
        ...(opts.receipt ? { external_ref: opts.receipt } : {}),
      };
      const created = await api.call(entriesCreate, { body });
      if (app.out.machine) app.out.emit(created, { human: () => undefined });
      else app.out.success(`Posted “${body.description}” on ${displayDate(body.entry_date, app.out.locale)} ${app.out.errColors.dim(created.id)}`);
    });

  entries
    .command('reverse')
    .argument('<id>', 'Entry id (or the start of one)')
    .description('Cancel an entry by posting its reverse (entries are never edited)')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const entry = await findEntry(api, query);
      if (entry.reversed_by) throw new UsageError(`That entry is already reversed (by ${entry.reversed_by.slice(0, 8)}).`);
      const book = await AccountBook.load(api);
      const summary = describeEntry(app, entry, book);
      const ok = await confirmAction(
        app,
        opts.yes,
        `Reverse “${singleLine(entry.description)}” (${displayDate(entry.entry_date, app.out.locale)}, ${summary.amount})?`,
      );
      if (!ok) {
        app.out.note('Nothing changed.');
        return;
      }
      const reversal = await api.call(entriesReverse, { path: { entry_id: entry.id } });
      if (app.out.machine) app.out.emit(reversal, { human: () => undefined });
      else app.out.success(`Reversed “${singleLine(entry.description)}” with entry ${reversal.id.slice(0, 8)}.`);
    });

  entries
    .command('tag')
    .argument('<posting>', 'Posting id (or the start of one), from `salli entries show`')
    .argument('[tags...]', 'AXIS=SLUG pairs, e.g. category=groceries need=essential')
    .description('Replace a posting’s tags (the amounts never change)')
    .option('--clear', 'Remove all its tags')
    .action(async (query, pairs, opts) => {
      if (!opts.clear && pairs.length === 0) throw new UsageError('Give tags as AXIS=SLUG, or --clear to remove them.');
      const api = await app.api();
      const all = await api.call(entriesList);
      const postings = all.flatMap((e) => e.postings.map((p) => ({ ...p, entry: e })));
      const posting = resolveById(postings, query, 'posting');
      const tags = opts.clear ? {} : tagArgs(pairs);
      await api.call(entriesPostingsSetTags, { path: { posting_id: posting.id }, body: { tags } });
      app.out.done(
        { posting_id: posting.id, tags },
        Object.keys(tags).length
          ? `Tagged ${Object.entries(tags).map(([k, v]) => `${k}=${v}`).join(' ')} on “${singleLine(posting.entry.description)}”.`
          : `Cleared the tags on “${singleLine(posting.entry.description)}”.`,
      );
    });
}
