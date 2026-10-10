/**
 * salli tokens create | list | revoke: personal access tokens, for scripts,
 * CI and other machines (`salli login --token -`, or SALLI_TOKEN).
 */
import type { Command } from '@commander-js/extra-typings';
import { tokensCreate, tokensList, tokensRevoke } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { singleLine } from '../output/text';
import { displayDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { confirmAction, countArg } from './shared';

export function registerTokens(program: Command, app: App): void {
  const tokens = program
    .command('tokens')
    .alias('token')
    .description('Personal access tokens, for scripts and other machines')
    .addHelpText(
      'after',
      `
A token acts as you, with everything you can do. It is shown once, when it
is made; Salli keeps only a fingerprint of it.

Examples:
  $ salli tokens create "backup job" --expires-in-days 90
  $ salli tokens create ci | gh secret set SALLI_TOKEN
  $ salli tokens revoke 3fa85f64`,
    );

  tokens
    .command('create')
    .argument('<name>', 'What it is for, e.g. "laptop" or "backup job"')
    .description('Make a token. It is printed once: store it now')
    .option('--expires-in-days <n>', 'Stop working after this many days (default: never)', countArg('--expires-in-days'))
    .action(async (name, opts) => {
      const api = await app.api();
      const created = await api.call(tokensCreate, {
        body: { name, ...(opts.expiresInDays !== undefined ? { expires_in_days: opts.expiresInDays } : {}) },
      });
      if (app.out.machine) {
        app.out.emit(created, { human: () => undefined });
        return;
      }
      // The token alone on stdout, so it can be piped; the rest is for people.
      app.out.success(
        `Created the token “${singleLine(created.name)}”` +
          (created.expires_at ? `, good until ${displayDate(created.expires_at, app.out.locale)}` : '') +
          ` ${app.out.errColors.dim(created.id)}`,
      );
      app.out.line(singleLine(created.token));
      app.out.warn('This is the only time it is shown. Use it with `salli login --token -` or as SALLI_TOKEN.');
    });

  tokens
    .command('list')
    .alias('ls')
    .description('Your tokens (never the tokens themselves)')
    .action(async () => {
      const api = await app.api();
      const list = await api.call(tokensList);
      app.out.emit(list, {
        human: (d) => {
          if (!d.length) return app.out.note('No tokens. Make one with `salli tokens create <name>`.');
          const c = app.out.colors;
          const locale = app.out.locale;
          app.out.line(
            app.out.table(d, [
              { header: 'ID', get: (t) => t.id.slice(0, 8), style: (s) => c.dim(s) },
              { header: 'NAME', get: (t) => t.name, shrink: true },
              { header: 'TOKEN', get: (t) => `${t.prefix}…`, style: (s) => c.dim(s) },
              { header: 'CREATED', get: (t) => displayDate(t.created_at, locale) },
              { header: 'EXPIRES', get: (t) => (t.expires_at ? displayDate(t.expires_at, locale) : 'never') },
              { header: 'LAST USED', get: (t) => (t.last_used_at ? displayDate(t.last_used_at, locale) : 'never') },
            ]),
          );
        },
      });
    });

  tokens
    .command('revoke')
    .argument('<token>', 'Token id (or its start)')
    .description('Revoke a token: anything using it stops working now')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const token = resolveById(await api.call(tokensList), query, 'token');
      const credentials = (await app.auth(await app.context())).credentials;
      const own = credentials?.kind === 'token' && credentials.token.startsWith(token.prefix);
      const question = own
        ? `Revoke “${singleLine(token.name)}”? It is the token this context signs in with, so you will be signed out.`
        : `Revoke “${singleLine(token.name)}”?`;
      if (!(await confirmAction(app, opts.yes, question))) return;
      await api.call(tokensRevoke, { path: { token_id: token.id } });
      app.out.done({ id: token.id, revoked: true }, `Revoked the token “${singleLine(token.name)}”.`);
      if (own) app.out.warn('This context signed in with that token; sign in again with `salli login`.');
    });
}
