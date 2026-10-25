/**
 * salli access grant | list | revoke: let another member of this server read
 * your books, and read theirs where they let you (`salli --books <id>`).
 */
import type { Command } from '@commander-js/extra-typings';
import { accessGrant, accessList, accessRevoke } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { singleLine } from '../output/text';
import { displayDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { confirmAction } from './shared';

export function registerAccess(program: Command, app: App): void {
  const access = program
    .command('access')
    .description("Read-only access to your books, given to another member, or theirs to you")
    .addHelpText(
      'after',
      `
A member you give access may read your books (accounts, entries, reports,
plans) and change nothing; either of you may end it. Every read they make is
in your audit log. To read books you were given, name them:

Examples:
  $ salli access grant partner@example.com
  $ salli access list
  $ salli --books <member-id> ledger trial-balance
  $ salli access revoke 3fa85f64`,
    );

  access
    .command('grant')
    .argument('<email>', 'The email the other member signs in with')
    .description('Let another member of this server read your books')
    .action(async (email) => {
      const api = await app.api();
      const granted = await api.call(accessGrant, { body: { email } });
      app.out.done(granted, `${singleLine(granted.member_email ?? granted.member_id)} may now read your books.`);
    });

  access
    .command('list')
    .alias('ls')
    .description('Who may read your books, and whose you may read')
    .action(async () => {
      const api = await app.api();
      const grants = await api.call(accessList);
      app.out.emit(grants, {
        human: (d) => {
          const rows = [
            ...d.given.map((g) => ({ ...g, way: 'reads yours' })),
            ...d.received.map((g) => ({ ...g, way: 'yours to read' })),
          ];
          if (!rows.length) return app.out.note('No access given or received. Give it with `salli access grant <email>`.');
          const c = app.out.colors;
          app.out.line(
            app.out.table(rows, [
              { header: 'ID', get: (g) => g.id.slice(0, 8), style: (s) => c.dim(s) },
              { header: 'MEMBER', get: (g) => g.member_email ?? '—', shrink: true },
              { header: 'MEMBER ID', get: (g) => g.member_id, style: (s) => c.dim(s) },
              { header: 'BOOKS', get: (g) => g.way },
              { header: 'SINCE', get: (g) => displayDate(g.created_at, app.out.locale) },
            ]),
          );
        },
      });
    });

  access
    .command('revoke')
    .argument('<id>', 'The access id (or its start)')
    .description('End access you gave, or were given')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const grants = await api.call(accessList);
      const grant = resolveById([...grants.given, ...grants.received], query, 'access');
      const who = singleLine(grant.member_email ?? grant.member_id);
      if (!(await confirmAction(app, opts.yes, `End the access between you and ${who}?`))) return;
      await api.call(accessRevoke, { path: { grant_id: grant.id } });
      app.out.done({ id: grant.id, revoked: true }, `Ended the access between you and ${who}.`);
    });
}
