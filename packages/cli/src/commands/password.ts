/**
 * salli password | sign-ins list | sign-ins revoke | totp: your password,
 * every way you are signed in with it: sessions (an app's, or a script's that
 * signed in with POST /v1/auth/sessions), the CLI on each machine and the
 * console in each browser tab (OAuth sign-ins through Salli's sign-in page,
 * which takes the same password), and two-step sign-in, a code from an
 * authenticator app after the password. AI connections are under `salli mcp`.
 * salli support-access: every time the server's operator could read your
 * books, and ending one.
 */
import type { Command } from '@commander-js/extra-typings';
import {
  authMe,
  authPasswordChange,
  authSignInsList,
  authSignInsRevoke,
  authSupportAccessEnd,
  authSupportAccessList,
  authTotpBegin,
  authTotpConfirm,
  authTotpDisable,
  type SignIn,
} from '@leafmonkeylabs/salli-sdk';
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
    .option('--code <code>', 'With two-step sign-in on: the authenticator app\'s code, or a recovery code')
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
      const changed = await api.call(authPasswordChange, {
        body: { current_password: current, new_password: next, ...(opts.code ? { code: opts.code } : {}) },
      });
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

/** salli support-access: the operator's support sessions on your books. */
export function registerSupportAccess(program: Command, app: App): void {
  const support = program
    .command('support-access')
    .description("When the server's operator could read your books, and why")
    .addHelpText(
      'after',
      `
The operator of this server can read your books only through a support
session: opened on the server for a reason, read-only, for at most four
hours, with every read listed here. You may end an open one.

Examples:
  $ salli support-access
  $ salli support-access end 3fa85f64`,
    );

  support
    .command('list', { isDefault: true })
    .alias('ls')
    .description('Every support session on your books, newest first')
    .action(async () => {
      const api = await app.api();
      const list = await api.call(authSupportAccessList);
      app.out.emit(list, {
        human: (d) => {
          if (!d.length) return app.out.note('No one has had support access to your books.');
          const c = app.out.colors;
          const locale = app.out.locale;
          app.out.line(
            app.out.table(d, [
              { header: 'ID', get: (s) => s.id.slice(0, 8), style: (t) => c.dim(t) },
              { header: 'REASON', get: (s) => singleLine(s.reason), shrink: true },
              { header: 'OPENED', get: (s) => displayDate(s.opened_at, locale) },
              { header: 'STATE', get: (s) => (s.open ? 'open' : `ended (${s.ended_by ?? 'expiry'})`) },
              { header: 'READS', get: (s) => String(s.reads.length) },
            ]),
          );
        },
      });
    });

  support
    .command('end')
    .argument('<id>', 'Support session id (or its start)')
    .description('End an open support session now')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const open = (await api.call(authSupportAccessList)).filter((s) => s.open);
      const session = resolveById(open, query, 'open support session');
      if (!(await confirmAction(app, opts.yes, `End the support session "${singleLine(session.reason)}"?`))) return;
      await api.call(authSupportAccessEnd, { path: { session_id: session.id } });
      app.out.done({ id: session.id, ended: true }, 'Ended the support session.');
    });
}

/** salli totp: two-step sign-in, a code from an authenticator app after the password. */
export function registerTotp(program: Command, app: App): void {
  const totp = program
    .command('totp')
    .description('Two-step sign-in: a code from an authenticator app after your password')
    .addHelpText(
      'after',
      `
Once it is on, every sign-in with your password (the sign-in page, salli
login, the console, the app) also asks for the six-digit code your
authenticator app shows, or one of ten recovery codes, each good once.
Lost both? The server's owner can turn it off:
salli-server members reset-password <email> --clear-totp.

Examples:
  $ salli totp status
  $ salli totp enable
  $ salli totp disable`,
    );

  totp
    .command('status')
    .description('Whether two-step sign-in is on')
    .action(async () => {
      const api = await app.api();
      const me = await api.call(authMe);
      app.out.done({ totp_enabled: me.totp_enabled ?? false }, me.totp_enabled ? 'Two-step sign-in is on.' : 'Two-step sign-in is off.');
    });

  totp
    .command('enable')
    .description('Turn it on: add the secret to your authenticator app, then enter a code')
    .action(async () => {
      const api = await app.api();
      const begun = await api.call(authTotpBegin);
      if (app.out.machine) {
        app.out.emit(begun, { human: () => undefined });
        return;
      }
      app.out.info('Add this to your authenticator app (open the link, or type the secret in):');
      app.out.line(begun.uri);
      app.out.line(begun.secret);
      if (!app.prompter.interactive) {
        app.out.note('Then: salli totp confirm <code>');
        return;
      }
      const code = await app.prompter.text({ message: 'The code your app shows now' });
      await confirm(app, code);
    });

  totp
    .command('confirm')
    .argument('<code>', 'The code your authenticator app shows now')
    .description('Finish turning it on, with a code from the new secret')
    .action(async (code) => confirm(app, code));

  totp
    .command('disable')
    .description('Turn it off (your password and a code)')
    .option('--password-stdin', 'Read your password from stdin')
    .option('--code <code>', 'The authenticator app\'s code, or a recovery code')
    .action(async (opts) => {
      let password: string;
      if (opts.passwordStdin) {
        [password] = await twoLines(app.runtime.stdin);
      } else {
        if (!app.prompter.interactive) {
          throw new UsageError('There is no terminal to ask for your password.', 'Pipe it in with --password-stdin.');
        }
        password = await app.prompter.password({ message: 'Password' });
      }
      let code = opts.code;
      if (!code && app.prompter.interactive && !opts.passwordStdin) {
        code = await app.prompter.text({ message: 'Authenticator code, or a recovery code' });
      }
      if (!password) throw new UsageError('Give your password.');
      const api = await app.api();
      await api.call(authTotpDisable, { body: { password, ...(code ? { code } : {}) } });
      app.out.done({ totp_enabled: false }, 'Two-step sign-in is off. Your recovery codes no longer work.');
    });
}

async function confirm(app: App, code: string): Promise<void> {
  const api = await app.api();
  const enabled = await api.call(authTotpConfirm, { body: { code: code.trim() } });
  if (app.out.machine) {
    app.out.emit(enabled, { human: () => undefined });
    return;
  }
  app.out.success('Two-step sign-in is on. Every sign-in with your password now asks for a code.');
  app.out.info('Recovery codes, each good once in place of a code. Keep them somewhere safe:');
  for (const recovery of enabled.recovery_codes) app.out.line(recovery);
  app.out.warn('This is the only time they are shown.');
}

/** How each kind of sign-in reads. */
const KINDS: Record<SignIn['kind'], string> = {
  session: 'session',
  cli: 'CLI',
  console: 'console',
  mobile: 'phone app',
  app: 'app',
};

/** What signed in: the client's name, or what a session's User-Agent said. */
function describe(signIn: SignIn): string {
  return singleLine(signIn.client_name ?? signIn.user_agent ?? '—');
}
