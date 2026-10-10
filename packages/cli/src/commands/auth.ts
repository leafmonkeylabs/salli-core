/**
 * salli login | logout | whoami
 */
import type { Command } from '@commander-js/extra-typings';
import { authMe, type AuthIdentity } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { identityOf } from '../auth/credentials';
import { interactiveLogin, resolveLoginTarget, revokeCredentials, saveLoginContext, serverMeta, tokenLogin } from '../auth/login';
import { UsageError } from '../errors';
import { singleLine } from '../output/text';
import { readAllStdin } from '../util/stdin';

/** How the server says you signed in (`method` in /v1/auth/me). */
const SIGN_IN_METHODS: Record<AuthIdentity['method'], string> = {
  session: 'a web session',
  oauth: 'an OAuth sign-in',
  pat: 'a personal access token',
  dev: 'development sign-in (any token is a user id)',
};

function describeExpiry(expiresAt: number | undefined, now: Date): string | undefined {
  if (expiresAt === undefined) return undefined;
  const seconds = Math.round(expiresAt - now.getTime() / 1000);
  if (seconds <= 0) return 'expired (refreshed on the next request)';
  if (seconds < 90) return `in ${seconds} seconds`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 90) return `in ${minutes} minutes`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `in ${hours} hours` : `in ${Math.round(hours / 24)} days`;
}

export function registerAuth(program: Command, app: App): void {
  program
    .command('login')
    .description('Sign in to a Salli server')
    .option('--device', 'Sign in with a code, approved on another device')
    .option('--token <token>', 'Use a personal access token ("-" reads it from stdin)')
    .option('--no-browser', 'Print the sign-in link instead of opening a browser')
    .addHelpText(
      'after',
      `
Signs in to the current context's server, or to --server, saving the context.
A browser opens to approve the sign-in; where none can (over SSH, say), you
approve with a code on another device instead. Tokens are kept in your
system keychain. A personal access token (salli tokens create) suits scripts.

Examples:
  $ salli login
  $ salli login --server https://salli.example.com --context work
  $ salli login --device
  $ echo "$SALLI_PAT" | salli login --token -`,
    )
    .action(async (opts) => {
      if (opts.device && opts.token !== undefined) throw new UsageError('Pass --device or --token, not both.');
      const target = await resolveLoginTarget(app);
      const meta = await serverMeta(app, target.server);
      await saveLoginContext(app, target, { api_version: meta.api_version, checked_at: app.runtime.now().toISOString() });

      let credentials;
      if (opts.token !== undefined) {
        const token = opts.token === '-' ? await readAllStdin(app.runtime.stdin) : opts.token;
        credentials = await tokenLogin(app, target, token);
      } else {
        credentials = await interactiveLogin(app, target, meta, { device: opts.device === true, openBrowser: opts.browser });
      }
      await app.saveCredentials(target.name, credentials);

      const me = await app.client(target.server, { getToken: () => (credentials.kind === 'token' ? credentials.token : credentials.tokens.access_token) }).call(authMe);
      const { email, userId } = identityOf(me);
      const who = singleLine(email ?? userId) || undefined;
      const method = credentials.kind === 'token' ? 'token' : credentials.method;
      if (app.out.machine) {
        app.out.emit({ context: target.name, server: target.server, method, user: me }, { human: () => undefined });
      } else {
        app.out.success(
          `Signed in to ${app.out.errColors.bold(target.server)}${who ? ` as ${app.out.errColors.bold(who)}` : ''} (context "${target.name}").`,
        );
      }
      if (app.runtime.env.SALLI_TOKEN) {
        app.out.warn('SALLI_TOKEN is set, and is used instead of this sign-in until you unset it.');
      }
    });

  program
    .command('logout')
    .description('Sign out: revoke the tokens and forget them')
    .option('--all', 'Sign out of every context')
    .action(async (opts) => {
      const config = await app.config();
      const names = opts.all ? config.contexts.map((c) => c.name) : [(await app.context()).name];
      const results: Array<{ context: string; server?: string; signed_out: boolean; revoked: boolean; problem?: string }> = [];
      for (const name of names) {
        const credentials = await app.loadCredentials(name);
        if (!credentials) {
          results.push({ context: name, signed_out: false, revoked: false });
          continue;
        }
        const { revoked, problem } = await revokeCredentials(app, credentials);
        await app.deleteCredentials(name);
        results.push({ context: name, server: credentials.server, signed_out: true, revoked, ...(problem ? { problem } : {}) });
      }
      app.out.emit(results, {
        human: () => {
          for (const r of results) {
            if (!r.signed_out) app.out.note(`Not signed in to context "${r.context}".`);
            else {
              app.out.success(`Signed out of ${r.server} (context "${r.context}").`);
              if (r.problem) app.out.warn(`The server was not told to revoke the tokens: ${singleLine(r.problem)}`);
            }
          }
          if (app.runtime.env.SALLI_TOKEN) app.out.warn('SALLI_TOKEN is still set in your environment.');
        },
      });
    });

  program
    .command('whoami')
    .description('Show who you are signed in as, and where')
    .action(async () => {
      const ctx = await app.context();
      const auth = await app.auth(ctx);
      const api = await app.api();
      const me = await api.call(authMe);
      app.out.emit(me, {
        human: (data) => {
          const { email, userId } = identityOf(data);
          const credentials = auth.credentials;
          const via =
            auth.source === 'env'
              ? 'SALLI_TOKEN'
              : credentials?.kind === 'oauth'
                ? credentials.method === 'device'
                  ? 'device sign-in'
                  : 'browser sign-in'
                : 'access token';
          app.out.line(
            app.out.details([
              ['User', email && singleLine(email)],
              ['User id', singleLine(userId)],
              ['Context', ctx.name],
              ['Server', ctx.server],
              ['Signed in with', via],
              ['Server sees', SIGN_IN_METHODS[data.method]],
              ['Token expires', credentials?.kind === 'oauth' ? describeExpiry(credentials.tokens.expires_at, app.runtime.now()) : undefined],
            ]),
          );
        },
      });
    });
}
