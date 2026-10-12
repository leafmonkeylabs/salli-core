/**
 * salli password | sign-ins list | sign-ins revoke: your password, and every
 * way you are signed in with it: sessions (an app's, or a script's that
 * signed in with POST /v1/auth/sessions), the CLI on each machine and the
 * console in each browser tab (OAuth sign-ins through Salli's sign-in page,
 * which takes the same password). AI connections are under `salli mcp`.
 */
import type { Command } from '@commander-js/extra-typings';
import { authPasswordChange, authSignInsList, authSignInsRevoke, type SignIn } from '@leafmonkeylabs/salli-sdk';
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

  const signIns = program
    .command('sign-ins')
    .description('Every way you are signed in: sessions, the CLI, the console')
    .addHelpText(
      'after',
      `
Lists your sessions (what an app holds after you sign in to it with your
email and password), the salli CLI on each machine, and the console in each
browser tab. Ending one signs it out now. AI connections are under
\`salli mcp\`, personal access tokens under \`salli tokens\`.

Examples:
  $ salli sign-ins list
  $ salli sign-ins revoke 3fa85f64`,
    );

  signIns
    .command('list')
    .alias('ls')
    .description('Your sign-ins, newest first')
    .action(async () => {
      const api = await app.api();
      const list = await api.call(authSignInsList);
      app.out.emit(list, {
        human: (d) => {
          if (!d.length) return app.out.note('Nothing is signed in.');
          const c = app.out.colors;
          const locale = app.out.locale;
          app.out.line(
            app.out.table(d, [
              { header: 'ID', get: (s) => s.id.slice(0, 8), style: (t) => c.dim(t) },
              { header: 'KIND', get: (s) => KINDS[s.kind] },
              { header: 'CLIENT', get: (s) => describe(s) + (s.current ? ' (this one)' : ''), shrink: true },
              { header: 'STARTED', get: (s) => displayDate(s.started_at, locale) },
              { header: 'LAST USED', get: (s) => (s.last_used_at ? displayDate(s.last_used_at, locale) : 'never') },
              { header: 'ENDS', get: (s) => (s.expires_at ? displayDate(s.expires_at, locale) : '—') },
            ]),
          );
        },
      });
    });

  signIns
    .command('revoke')
    .argument('<sign-in>', 'Sign-in id (or its start)')
    .description('Sign it out now')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const signIn = resolveById(await api.call(authSignInsList), query, 'sign-in');
      const what = signIn.current ? 'this sign-in' : `the ${KINDS[signIn.kind]} sign-in (${describe(signIn)})`;
      if (!(await confirmAction(app, opts.yes, `Sign out ${what}?`))) return;
      await api.call(authSignInsRevoke, { path: { sign_in_id: signIn.id } });
      app.out.done({ id: signIn.id, revoked: true }, `Signed out ${what}.`);
    });
}

/** How each kind of sign-in reads. */
const KINDS: Record<SignIn['kind'], string> = {
  session: 'session',
  cli: 'CLI',
  console: 'console',
  app: 'app',
};

/** What signed in: the client's name, or what a session's User-Agent said. */
function describe(signIn: SignIn): string {
  return singleLine(signIn.client_name ?? signIn.user_agent ?? '—');
}
