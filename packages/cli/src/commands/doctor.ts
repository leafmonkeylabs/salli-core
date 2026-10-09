/**
 * salli doctor: is everything needed to use Salli in place?
 */
import type { Command } from '@commander-js/extra-typings';
import { authMe, SalliApiError, SalliNetworkError, SUPPORTED_API_VERSIONS } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { CliError, ExitCode, exitCodeFor, messageFor } from '../errors';
import { singleLine } from '../output/text';
import { VERSION } from '../version';

type Status = 'ok' | 'warn' | 'fail' | 'info';

interface Check {
  name: string;
  status: Status;
  detail: string;
  hint?: string;
}

function describeSkew(seconds: number): string {
  const abs = Math.abs(seconds);
  const amount = abs < 120 ? `${Math.round(abs)}s` : `${Math.round(abs / 60)} minutes`;
  return `${amount} ${seconds > 0 ? 'ahead of' : 'behind'} the server`;
}

export function registerDoctor(program: Command, app: App): void {
  program
    .command('doctor')
    .description('Check the server, the API version, your sign-in and your clock')
    .action(async () => {
      const checks: Check[] = [];
      let failure: number | undefined;
      const fail = (check: Check, code: number): void => {
        checks.push(check);
        failure ??= code;
      };

      checks.push({ name: 'CLI', status: 'info', detail: `salli ${VERSION} (${app.userAgent.replace(/^[^(]*\(|\)$/g, '')})` });
      const ctx = await app.context();
      checks.push({
        name: 'Context',
        status: 'info',
        detail: `${ctx.name} → ${ctx.server}${ctx.serverFrom === 'flag' ? ' (--server)' : ctx.serverFrom === 'env' ? ' (SALLI_SERVER)' : ''}`,
      });

      // Reachability, API version and clock, from one /v1/meta request.
      let reachable = false;
      try {
        const started = performance.now();
        const response = await app.runtime.fetch(`${ctx.server}/v1/meta`, {
          headers: { Accept: 'application/json', 'User-Agent': app.userAgent },
          signal: AbortSignal.any([AbortSignal.timeout(10_000), app.runtime.signal]),
        });
        const elapsed = performance.now() - started;
        const receivedAt = app.runtime.now().getTime();
        if (response.status === 404) {
          fail(
            { name: 'Server', status: 'fail', detail: `${ctx.server} answered, but has no /v1/meta`, hint: 'Is this a Salli server, and a current one?' },
            ExitCode.INCOMPATIBLE,
          );
        } else if (!response.ok) {
          fail({ name: 'Server', status: 'fail', detail: `${ctx.server} answered ${response.status}` }, ExitCode.ERROR);
        } else {
          reachable = true;
          const meta = (await response.json()) as { api_version?: unknown; server_version?: unknown };
          checks.push({
            name: 'Server',
            status: 'ok',
            detail: `${ctx.server} answered in ${Math.round(elapsed)} ms (Salli ${singleLine(String(meta.server_version ?? '?'))})`,
          });
          const version = String(meta.api_version ?? '?');
          if (SUPPORTED_API_VERSIONS.includes(version)) {
            checks.push({ name: 'API version', status: 'ok', detail: `${version} (this CLI speaks ${SUPPORTED_API_VERSIONS.join(', ')})` });
          } else {
            fail(
              {
                name: 'API version',
                status: 'fail',
                detail: `the server speaks ${singleLine(version)}; this CLI speaks ${SUPPORTED_API_VERSIONS.join(', ')}`,
                hint: 'Update salli, or use a server with a matching API version.',
              },
              ExitCode.INCOMPATIBLE,
            );
          }
          const date = response.headers.get('date');
          const serverTime = date ? Date.parse(date) : Number.NaN;
          if (Number.isFinite(serverTime)) {
            // The Date header is whole seconds, stamped about half a round trip ago.
            const skew = (receivedAt - elapsed / 2 - serverTime) / 1000;
            const abs = Math.abs(skew);
            if (abs <= 30) checks.push({ name: 'Clock', status: 'ok', detail: 'in step with the server' });
            else {
              checks.push({
                name: 'Clock',
                status: abs > 300 ? 'fail' : 'warn',
                detail: `your clock is ${describeSkew(skew)}`,
                hint: 'Sign-in tokens expire by the clock: turn on automatic time setting.',
              });
              if (abs > 300) failure ??= ExitCode.ERROR;
            }
          } else {
            checks.push({ name: 'Clock', status: 'info', detail: 'the server sent no Date header to compare with' });
          }
        }
      } catch (error) {
        const reason =
          (error as Error).name === 'TimeoutError'
            ? `${ctx.server} did not answer within 10s`
            : SalliNetworkError.fromFetchError(error, `${ctx.server}/v1/meta`).message;
        fail(
          {
            name: 'Server',
            status: 'fail',
            detail: reason,
            hint: 'Is the server running (`uv run salli serve`)? Check the address with `salli context current`.',
          },
          ExitCode.NETWORK,
        );
      }

      // Sign-in.
      const auth = await app.auth(ctx);
      if (!auth.provider) {
        fail(
          {
            name: 'Signed in',
            status: 'fail',
            detail: auth.mismatchedServer ? `signed in to ${auth.mismatchedServer}, not ${ctx.server}` : 'no',
            hint: 'Run `salli login`.',
          },
          ExitCode.NOT_SIGNED_IN,
        );
      } else if (reachable) {
        try {
          const me = (await app.client(ctx.server, auth.provider).call(authMe)) as { user_id?: unknown; email?: unknown } | undefined;
          const who = typeof me?.email === 'string' ? me.email : typeof me?.user_id === 'string' ? me.user_id : 'yes';
          const via = auth.source === 'env' ? ' (SALLI_TOKEN)' : auth.credentials?.kind === 'token' ? ' (access token)' : '';
          checks.push({ name: 'Signed in', status: 'ok', detail: `as ${who}${via}` });
        } catch (error) {
          const code = exitCodeFor(error);
          fail(
            {
              name: 'Signed in',
              status: 'fail',
              detail: error instanceof SalliApiError && error.status === 401 ? 'the server no longer accepts your sign-in' : messageFor(error),
              hint: 'Run `salli login`.',
            },
            code === ExitCode.NOT_FOUND ? ExitCode.ERROR : code,
          );
        }
      } else {
        checks.push({ name: 'Signed in', status: 'info', detail: 'credentials saved; not checked (server unreachable)' });
      }

      try {
        const store = await app.secretStore();
        checks.push({ name: 'Credentials', status: store.kind === 'file' ? 'warn' : 'info', detail: `kept in ${store.description}` });
      } catch (error) {
        checks.push({ name: 'Credentials', status: 'warn', detail: messageFor(error) });
      }

      const result = { ok: failure === undefined, checks };
      app.out.emit(result, {
        records: (r) => r.checks,
        human: () => {
          const c = app.out.colors;
          const mark: Record<Status, string> = { ok: c.green('✓'), warn: c.yellow('!'), fail: c.red('✗'), info: c.dim('•') };
          const width = Math.max(...checks.map((x) => x.name.length));
          for (const check of checks) {
            app.out.line(`${mark[check.status]} ${check.name.padEnd(width)}  ${check.detail}`);
            if (check.hint && check.status !== 'ok') app.out.line(`  ${' '.repeat(width)}  ${c.dim(check.hint)}`);
          }
        },
      });
      if (failure !== undefined) {
        // The checks above are the report; exit with the first failure's code.
        throw new CliError('Some checks failed.', { exitCode: failure, kind: 'doctor', quiet: true });
      }
    });
}
