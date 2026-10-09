/**
 * salli add "<what happened>": the AI drafts an entry from a sentence, you
 * check it (and change anything), then it is posted like any other entry.
 * The model only reads the sentence; the amount posted is the one you see.
 */
import type { Command } from '@commander-js/extra-typings';
import { accountsCreate, entriesCreate, entriesParse, type Account, type ParsedEntryDraft } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import { singleLine } from '../output/text';
import { displayDate, isoDate, parseDate } from '../util/dates';
import type { Choice } from '../util/prompts';
import { AccountBook, amountArg } from './shared';

interface Draft {
  amount: string;
  currency: string;
  description: string;
  date: string;
  debitId: string | null;
  creditId: string | null;
}

type Side = 'debit' | 'credit';

const NEW = '__new__';

async function pickAccount(app: App, book: AccountBook, side: Side, parsed: ParsedEntryDraft, current: string | null): Promise<string> {
  const hint = side === 'debit' ? parsed.debit_account_hint : parsed.credit_account_hint;
  const options: Choice<string>[] = book.accounts
    .filter((a) => a.is_active)
    .map((a) => ({ value: a.id, label: `${a.code} ${a.name}`, hint: a.type }));
  if (hint) options.unshift({ value: NEW, label: `New account: ${hint.name}`, hint: hint.type });
  const chosen = await app.prompter.search({
    message: side === 'debit' ? 'Which account received it? (To)' : 'Which account paid? (From)',
    options,
    placeholder: 'Type to search',
    ...(current ? { initialValue: current } : {}),
  });
  if (chosen !== NEW || !hint) return chosen;

  const code = await app.prompter.text({
    message: `Code for the new ${hint.type} account “${hint.name}”`,
    validate: (v) => (!v.trim() ? 'A code is required' : book.accounts.some((a) => a.code === v.trim()) ? 'That code is taken' : undefined),
  });
  const api = await app.api();
  const created = await api.call(accountsCreate, { body: { code: code.trim(), name: hint.name, type: hint.type } });
  const account: Account = {
    id: created.id,
    code: code.trim(),
    name: hint.name,
    type: hint.type,
    currency: parsed.currency,
    parent_id: null,
    is_active: true,
  };
  book.accounts.push(account);
  app.out.success(`Added ${singleLine(`${account.code} ${account.name}`)}.`);
  return created.id;
}

function describe(app: App, book: AccountBook, draft: Draft, parsed: ParsedEntryDraft): string {
  const c = app.out.errColors;
  const side = (id: string | null, hint: ParsedEntryDraft['debit_account_hint']): string =>
    id ? book.label(id) : hint ? `${c.yellow('new')} ${singleLine(`${hint.name} (${hint.type})`)}` : c.yellow('not chosen');
  return [
    `  ${c.bold(singleLine(draft.description))}`,
    `  ${c.bold(app.out.money(draft.amount, draft.currency))} · ${parsed.entry_type} · ${displayDate(draft.date, app.out.locale)}`,
    `  ${c.dim('From')}  ${side(draft.creditId, parsed.credit_account_hint)}`,
    `  ${c.dim('To  ')}  ${side(draft.debitId, parsed.debit_account_hint)}`,
    c.dim(`  The AI is ${app.out.percent(parsed.confidence ?? 0, 0)} sure of this reading.`),
  ].join('\n');
}

export function registerQuickAdd(program: Command, app: App): void {
  program
    .command('add')
    .argument('<text...>', 'What happened, in your words')
    .description('Record a transaction from a sentence: the AI drafts it, you confirm')
    .option('--date <date>', 'When it happened (default: today)')
    .option('--debit <account>', 'The account that received it ("To")')
    .option('--credit <account>', 'The account that paid ("From")')
    .option('-y, --yes', 'Post the draft without asking (needs both accounts)')
    .option('--dry-run', 'Only show the draft')
    .addHelpText(
      'after',
      `
Examples:
  $ salli add "lunch 12.50 cash"
  $ salli add "rent 1800 from checking" --date 2026-10-01
  $ salli add "coffee 4.50" --credit card --yes
  $ salli add "salary 5000 into checking" --dry-run --json`,
    )
    .action(async (words, opts) => {
      const text = words.join(' ').trim();
      if (!text) throw new UsageError('Say what happened, e.g. salli add "lunch 12.50 cash".');
      const api = await app.api();
      const now = app.runtime.now();
      const [parsed, book] = await Promise.all([api.call(entriesParse, { body: { text } }), AccountBook.load(api)]);

      const draft: Draft = {
        amount: parsed.amount,
        currency: parsed.currency,
        description: parsed.description,
        date: opts.date ? parseDate(opts.date, now, '--date') : isoDate(now),
        debitId: opts.debit ? book.resolve(opts.debit).id : (parsed.debit_account_id ?? null),
        creditId: opts.credit ? book.resolve(opts.credit).id : (parsed.credit_account_id ?? null),
      };
      // Ids the model picked must be real accounts.
      if (draft.debitId && !book.get(draft.debitId)) draft.debitId = null;
      if (draft.creditId && !book.get(draft.creditId)) draft.creditId = null;

      if (opts.dryRun) {
        app.out.emit(parsed, { human: () => app.out.line(describe(app, book, draft, parsed)) });
        return;
      }

      if (opts.yes) {
        if (!draft.debitId || !draft.creditId) {
          const missing = !draft.debitId ? 'debit' : 'credit';
          const hint = missing === 'debit' ? parsed.debit_account_hint : parsed.credit_account_hint;
          throw new UsageError(
            `The draft has no ${missing} account${hint ? ` (it suggests a new one: ${hint.name}, ${hint.type})` : ''}.`,
            `Pass --${missing} <account>${hint ? ', or create it with `salli accounts add`' : ''}.`,
          );
        }
      } else {
        if (!app.prompter.interactive) {
          throw new UsageError('Checking the draft needs a terminal.', 'Pass --yes to post it as drafted, or --dry-run to see it.');
        }
        for (;;) {
          app.out.info(describe(app, book, draft, parsed));
          const ready = Boolean(draft.debitId && draft.creditId);
          const action = await app.prompter.select<string>({
            message: ready ? 'Post this entry?' : 'Choose the missing account',
            options: [
              ...(ready ? [{ value: 'post', label: 'Post it' }] : []),
              { value: 'credit', label: 'Change “From” (the account that paid)' },
              { value: 'debit', label: 'Change “To” (the account that received)' },
              { value: 'amount', label: 'Change the amount' },
              { value: 'description', label: 'Change the description' },
              { value: 'date', label: 'Change the date' },
              { value: 'cancel', label: 'Cancel' },
            ],
            initialValue: ready ? 'post' : draft.creditId ? 'debit' : 'credit',
          });
          if (action === 'post') break;
          if (action === 'cancel') {
            app.out.note('Nothing posted.');
            return;
          }
          if (action === 'debit') draft.debitId = await pickAccount(app, book, 'debit', parsed, draft.debitId);
          if (action === 'credit') draft.creditId = await pickAccount(app, book, 'credit', parsed, draft.creditId);
          if (action === 'amount') {
            draft.amount = amountArg(
              await app.prompter.text({
                message: `Amount (${draft.currency})`,
                initialValue: draft.amount,
                validate: (v) => {
                  try {
                    amountArg(v);
                    return undefined;
                  } catch (error) {
                    return (error as Error).message;
                  }
                },
              }),
            );
          }
          if (action === 'description') {
            draft.description = await app.prompter.text({ message: 'Description', initialValue: draft.description });
          }
          if (action === 'date') {
            draft.date = parseDate(
              await app.prompter.text({
                message: 'Date (YYYY-MM-DD)',
                initialValue: draft.date,
                validate: (v) => {
                  try {
                    parseDate(v, now);
                    return undefined;
                  } catch (error) {
                    return (error as Error).message;
                  }
                },
              }),
              now,
            );
          }
        }
      }

      const created = (await api.call(entriesCreate, {
        body: {
          entry_date: draft.date,
          description: draft.description,
          postings: [
            { account_id: draft.debitId as string, direction: 1, amount: draft.amount, currency: draft.currency },
            { account_id: draft.creditId as string, direction: -1, amount: draft.amount, currency: draft.currency },
          ],
        },
      })) as { id: string };
      if (app.out.machine) {
        app.out.emit({ draft: parsed, entry: created }, { human: () => undefined });
      } else {
        app.out.success(
          `Posted “${singleLine(draft.description)}”: ${app.out.money(draft.amount, draft.currency)} from ${book.name(draft.creditId)} to ${book.name(draft.debitId)} ${app.out.errColors.dim(created.id.slice(0, 8))}`,
        );
      }
    });
}
