/**
 * salli banks list | connect | map | sync | disconnect
 *
 * Bank connections: the server fetches transactions from a provider (such
 * as SimpleFIN) and queues them for review like an imported statement.
 */
import type { Command } from '@commander-js/extra-typings';
import {
  bankConnectionsConnect,
  bankConnectionsDisconnect,
  bankConnectionsList,
  bankConnectionsMapAccount,
  bankConnectionsSync,
  SalliApiError,
  type BankConnection,
  type BankSync,
  type SalliClient,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { CliError, ExitCode, UsageError } from '../errors';
import { singleLine } from '../output/text';
import { displayDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { readAllStdin } from '../util/stdin';
import { AccountBook, confirmAction } from './shared';

async function resolveConnection(api: SalliClient, query: string): Promise<BankConnection> {
  return resolveById((await api.call(bankConnectionsList)).connections, query, 'bank connection');
}

export function registerBanks(program: Command, app: App): void {
  const banks = program
    .command('banks')
    .alias('bank')
    .description('Bank connections: fetch transactions straight from your bank, for review')
    .addHelpText(
      'after',
      `
Connect once, map each bank account to a Salli account, then sync: new
transactions wait in review (salli statements pending) until you post them.

Examples:
  $ salli banks connect                     (asks for the SimpleFIN setup token)
  $ salli banks map 3fa85f64 ACT-123 --account checking
  $ salli banks sync`,
    );

  banks
    .command('list')
    .alias('ls')
    .description('Your bank connections, their accounts, and where each is imported')
    .action(async () => {
      const api = await app.api();
      const [data, book] = await Promise.all([api.call(bankConnectionsList), AccountBook.load(api)]);
      app.out.emit(data, {
        records: (d) => d.connections.flatMap((conn) => conn.accounts.map((a) => ({ connection_id: conn.id, ...a }))),
        human: (d) => {
          const out = app.out;
          const c = out.colors;
          if (!d.available) out.warn('Bank connections are off on this server: they need an encryption key and real sign-in.');
          if (!d.connections.length) return out.note('No banks connected. Use `salli banks connect`.');
          for (const [i, conn] of d.connections.entries()) {
            if (i) out.line();
            const synced = conn.last_synced_at ? displayDate(conn.last_synced_at, out.locale) : 'never';
            const status = conn.status === 'error' ? c.red(conn.status) : conn.status === 'attention' ? c.yellow(conn.status) : conn.status;
            out.line(`${out.heading(conn.name)} ${c.dim(`${singleLine(conn.provider)} · ${conn.id.slice(0, 8)} · synced ${synced}`)} ${status}`);
            if (conn.last_error) out.line(c.yellow(`  ${singleLine(conn.last_error)}`));
            for (const warning of conn.warnings ?? []) out.line(c.yellow(`  ${singleLine(warning)}`));
            if (!conn.accounts.length) continue;
            out.line(
              out.table(conn.accounts, [
                { header: 'BANK ACCOUNT', get: (a) => (a.institution ? `${a.institution} · ${a.name}` : a.name), shrink: true },
                { header: 'ID', get: (a) => a.remote_id, style: (t) => c.dim(t) },
                { header: 'BALANCE', get: (a) => (a.balance === null ? a.currency : out.money(a.balance, a.currency)), align: 'right' },
                {
                  header: 'IMPORTED INTO',
                  get: (a) => (a.account_id ? book.label(a.account_id) : 'not mapped') + (a.notes ? ` (${a.notes})` : ''),
                  shrink: true,
                  style: (t, a) => (a.account_id ? t : c.yellow(t)),
                },
              ]),
            );
          }
        },
      });
    });

  banks
    .command('connect')
    .description('Connect a bank: for SimpleFIN, the setup token from the SimpleFIN Bridge')
    .option('--provider <provider>', 'Which provider', 'simplefin')
    .option('--name <name>', 'What to call it (default: the bank’s name)')
    .option('--setup-token <token>', 'The provider’s one-time setup token ("-" reads it from stdin; asked for when omitted)')
    .action(async (opts) => {
      let token = opts.setupToken === '-' ? await readAllStdin(app.runtime.stdin) : (opts.setupToken ?? app.runtime.env.SALLI_BANK_SETUP_TOKEN);
      if (!token) {
        if (!app.prompter.interactive) throw new UsageError('No setup token.', 'Pass --setup-token -, and pipe it in.');
        token = await app.prompter.password({ message: 'Setup token' });
      }
      token = token.trim();
      if (!token) throw new UsageError('The setup token is empty.');
      const api = await app.api();
      const connected = await api.call(bankConnectionsConnect, {
        body: { provider: opts.provider, setup_token: token, ...(opts.name ? { name: opts.name } : {}) },
        timeoutMs: 120_000,
      });
      if (app.out.machine) {
        app.out.emit(connected, { human: () => undefined });
        return;
      }
      app.out.success(`Connected ${app.out.errColors.dim(connected.id)}`);
      for (const warning of connected.warnings) app.out.warn(singleLine(warning));
      if (connected.error) {
        app.out.warn(`Its accounts could not be read yet: ${singleLine(connected.error)} The connection is kept; \`salli banks sync\` tries again.`);
        return;
      }
      app.out.note('Next: map each bank account to a Salli account with `salli banks map`, then `salli banks sync`.');
    });

  banks
    .command('map')
    .argument('<connection>', 'Connection id (or its start)')
    .argument('<remote-id>', 'The bank account’s id, from `salli banks list`')
    .description('Choose where a bank account’s transactions are imported')
    .option('--account <account>', 'Import into this account (code, name or id)')
    .option('--create', 'Create an account for it')
    .option('--unmap', 'Stop importing it')
    .action(async (query, remoteId, opts) => {
      if ([opts.account !== undefined, opts.create === true, opts.unmap === true].filter(Boolean).length !== 1) {
        throw new UsageError('Give exactly one of --account, --create or --unmap.');
      }
      const api = await app.api();
      const connection = await resolveConnection(api, query);
      const account = opts.account ? (await AccountBook.load(api)).resolve(opts.account) : undefined;
      const mapped = await api.call(bankConnectionsMapAccount, {
        path: { connection_id: connection.id, remote_id: remoteId },
        body: opts.create ? { create: true } : { account_id: account?.id ?? null },
      });
      app.out.done(mapped, mapped.account_id ? 'Mapped.' : 'Unmapped.');
    });

  banks
    .command('sync')
    .argument('[connection]', 'Connection id (or its start); default: every connection')
    .description('Fetch new transactions and queue them for review')
    .action(async (query) => {
      const api = await app.api();
      const ids = query ? [(await resolveConnection(api, query)).id] : (await api.call(bankConnectionsList)).connections.map((conn) => conn.id);
      const results: Array<({ id: string } & BankSync) | { id: string; error: string }> = [];
      for (const id of ids) {
        try {
          results.push({ id, ...(await api.call(bankConnectionsSync, { path: { connection_id: id }, timeoutMs: 5 * 60_000 })) });
        } catch (error) {
          if (!(error instanceof SalliApiError)) throw error;
          results.push({ id, error: error.message });
        }
      }
      const failed = results.filter((r) => 'error' in r);
      app.out.emit(results, {
        human: () => {
          const out = app.out;
          if (!results.length) return out.note('No banks connected. Use `salli banks connect`.');
          for (const r of results) {
            if ('error' in r) {
              out.warn(`${r.id.slice(0, 8)}: ${singleLine(r.error)}`);
              continue;
            }
            for (const a of r.accounts) {
              out.line(`${singleLine(a.name)}: ${a.queued ?? 0} new to review, ${a.duplicates ?? 0} seen before`);
              for (const note of a.notes ?? []) out.line(out.colors.dim(`  ${singleLine(note)}`));
            }
            for (const name of r.unmapped) out.note(`${singleLine(name)}: not mapped, skipped`);
            for (const warning of r.warnings) out.warn(singleLine(warning));
          }
          if (results.some((r) => !('error' in r) && r.accounts.some((a) => a.queued))) out.note('Review them with `salli statements pending`.');
        },
      });
      if (failed.length) throw new CliError(`${failed.length} of ${results.length} could not sync.`, { exitCode: ExitCode.ERROR, quiet: true });
    });

  banks
    .command('disconnect')
    .argument('<connection>', 'Connection id (or its start)')
    .description('Forget a connection and its credential (what was booked from it stays)')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const connection = await resolveConnection(api, query);
      if (!(await confirmAction(app, opts.yes, `Disconnect “${singleLine(connection.name)}”?`))) return;
      await api.call(bankConnectionsDisconnect, { path: { connection_id: connection.id } });
      app.out.done({ disconnected: connection.id }, `Disconnected “${singleLine(connection.name)}”.`);
    });
}
