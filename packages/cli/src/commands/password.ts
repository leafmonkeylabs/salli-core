/**
 * salli password | sign-ins list | sign-ins revoke: your password, and the
 * sessions that signing in with it has started (an app's, or a script's that
 * signed in with POST /v1/auth/sessions). The CLI itself signs in through the
 * browser or device page, which takes the same password; its own sign-ins
 * are OAuth tokens, signed out with `salli logout`.
 */
import type { Command } from '@commander-js/extra-typings';
import { authPasswordChange, authSessionsList, authSessionsRevoke } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import type { InputStream } from '../runtime';
import { singleLine } from '../output/text';
import { displayDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { confirmAction } from './shared';

/** The first two lines of stdin, exactly as typed (a password may begin or end with a space). */
async function twoLines(stdin: InputStream): Promise<[string, string]> {
  const chunks: Buffer[] = [];
  for await (const chunk of stdin) chunks.push(typeof chunk === 'string' ? Buffer.from(chunk) : (chunk as Buffer));
  const [first = '', second = ''] = Buffer.concat(chunks).toString('utf8').split(/\r?\n/);
  return [first, second];
}

export function registerPassword(program: Command, app: App): void {
  program
    .command('password')
    .description('Change your password (your other sessions are signed out)')
    .option('--password-stdin', 'Read the current password, then the new one, from stdin, one per line')
    .addHelpText(
      'after',
      `
Asks for your current password, then the new one twice. The new one needs at
least 12 characters. Sessions other apps started with your password end; your
CLI sign-ins and personal access tokens keep working. Forgotten it? The
server's owner sets a new one: salli-server members reset-password <email>.

Examples:
  $ salli password
  $ printf '%s\\n%s\\n' "$OLD" "$NEW" | salli password --password-stdin`,
    )
    .action(async (opts) => {
      let current: string;
      let next: string;
      if (opts.passwordStdin) {
        [current, next] = await twoLines(app.runtime.stdin);
      } else {
        if (!app.prompter.interactive) {
          throw new UsageError('There is no terminal to ask for your password.', 'Pipe it in with --password-stdin.');
        }
        current = await app.prompter.password({ message: 'Current password' });
        next = await app.prompter.password({ message: 'New password (at least 12 characters)' });
        if ((await app.prompter.password({ message: 'New password again' })) !== next) {
          throw new UsageError('The new passwords did not match.');
        }
      }
      if (!current || !next) throw new UsageError('Give the current password and the new one.');
      const api = await app.api();
      const changed = await api.call(authPasswordChange, { body: { current_password: current, new_password: next } });
      const ended = changed.sessions_ended;
      app.out.done(changed, `Password changed.${ended ? ` ${ended} other session${ended === 1 ? '' : 's'} signed out.` : ''}`);
    });

  const sessions = program
    .command('sign-ins')
    .description('Where you are signed in with your password (sessions)')
    .addHelpText(
      'after',
      `
Sessions are what an app holds after you sign in to it with your email and
password. Your CLI sign-ins are not sessions: see \`salli whoami\`, and sign
out with \`salli logout\`. AI connectors are under \`salli mcp\`.

Examples:
  $ salli sign-ins list
  $ salli sign-ins revoke 3fa85f64`,
    );

  sessions
    .command('list')
    .alias('ls')
    .description('Your live sessions, newest first')
    .action(async () => {
      const api = await app.api();
      const list = await api.call(authSessionsList);
      app.out.emit(list, {
        human: (d) => {
          if (!d.length) return app.out.note('No sessions: nothing is signed in with your password.');
          const c = app.out.colors;
          const locale = app.out.locale;
          app.out.line(
            app.out.table(d, [
              { header: 'ID', get: (s) => s.id.slice(0, 8), style: (t) => c.dim(t) },
              { header: 'CLIENT', get: (s) => singleLine(s.user_agent ?? '—') + (s.current ? ' (this one)' : ''), shrink: true },
              { header: 'STARTED', get: (s) => displayDate(s.created_at, locale) },
              { header: 'LAST USED', get: (s) => (s.last_used_at ? displayDate(s.last_used_at, locale) : 'never') },
              { header: 'EXPIRES', get: (s) => displayDate(s.expires_at, locale) },
            ]),
          );
        },
      });
    });

  sessions
    .command('revoke')
    .argument('<session>', 'Session id (or its start)')
    .description('Sign a session out now')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const session = resolveById(await api.call(authSessionsList), query, 'session');
      const what = session.user_agent ? `the session from ${singleLine(session.user_agent)}` : 'that session';
      if (!(await confirmAction(app, opts.yes, `Sign out ${what}?`))) return;
      await api.call(authSessionsRevoke, { path: { session_id: session.id } });
      app.out.done({ id: session.id, revoked: true }, `Signed out ${what}.`);
    });
}
