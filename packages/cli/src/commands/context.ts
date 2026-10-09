/**
 * salli context list | current | use | add | remove
 */
import type { Command } from '@commander-js/extra-typings';
import { normalizeServerUrl } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { DEFAULT_CONTEXT, findContext, validateContextName, type ContextEntry } from '../config/config';
import { NotFoundError, UsageError } from '../errors';

export function registerContext(program: Command, app: App): void {
  const context = program
    .command('context')
    .description('Manage contexts: the Salli servers you use, and which is current')
    .addHelpText(
      'after',
      `
A context names a server, like a kubectl context. Each has its own sign-in.

Examples:
  $ salli context add work https://salli.example.com
  $ salli context use work
  $ salli --context home status`,
    );

  context
    .command('list')
    .alias('ls')
    .description('List contexts')
    .action(async () => {
      const config = await app.config();
      const active = await app.context();
      const rows = await Promise.all(
        config.contexts.map(async (c) => {
          const credentials = await app.loadCredentials(c.name).catch(() => undefined);
          return {
            name: c.name,
            server: c.server,
            current: c.name === active.name,
            signed_in: !!credentials && credentials.server === normalizeServerUrl(c.server),
          };
        }),
      );
      app.out.emit(rows, {
        human: (list) => {
          if (list.length === 0) {
            app.out.note(`No contexts yet. \`salli login\` creates one ("${DEFAULT_CONTEXT}", for ${active.server}).`);
            return;
          }
          app.out.line(
            app.out.table(list, [
              { header: '', get: (r) => (r.current ? '*' : ''), style: (t) => app.out.colors.green(t) },
              { header: 'NAME', get: (r) => r.name, style: (t, r) => (r.current ? app.out.colors.bold(t) : t) },
              { header: 'SERVER', get: (r) => r.server, shrink: true },
              { header: 'SIGNED IN', get: (r) => (r.signed_in ? 'yes' : 'no'), style: (t, r) => (r.signed_in ? t : app.out.colors.dim(t)) },
            ]),
          );
        },
      });
    });

  context
    .command('current')
    .description('Show the context in use and its server')
    .action(async () => {
      const ctx = await app.context();
      const result = { name: ctx.name, server: ctx.server, saved: !!ctx.entry, server_from: ctx.serverFrom };
      app.out.emit(result, {
        human: () => {
          app.out.line(`${app.out.colors.bold(ctx.name)}  ${ctx.server}`);
          if (ctx.serverFrom === 'flag') app.out.note('(server from --server)');
          else if (ctx.serverFrom === 'env') app.out.note('(server from SALLI_SERVER)');
          else if (!ctx.entry) app.out.note('(not saved yet: `salli login` saves it)');
        },
      });
    });

  context
    .command('use')
    .argument('<name>', 'Context to switch to')
    .description('Switch the current context')
    .action(async (name) => {
      validateContextName(name);
      const config = await app.config();
      const entry = findContext(config, name);
      if (!entry) {
        throw new NotFoundError(`No context named "${name}".`, 'See `salli context list`, or add it with `salli context add`.');
      }
      await app.updateConfig((c) => {
        c.current_context = name;
      });
      app.out.done({ current_context: name, server: entry.server }, `Now using "${name}" (${entry.server}).`);
    });

  context
    .command('add')
    .argument('<name>', 'A short name, e.g. home or work')
    .argument('<server>', 'The server address, e.g. https://salli.example.com')
    .option('--use', 'Make it the current context')
    .description('Add a context (then `salli login` to sign in)')
    .action(async (name, serverUrl, opts) => {
      validateContextName(name);
      let server: string;
      try {
        server = normalizeServerUrl(serverUrl);
      } catch (error) {
        throw new UsageError((error as Error).message);
      }
      const config = await app.config();
      if (findContext(config, name)) {
        throw new UsageError(`A context named "${name}" already exists.`, `Remove it first: salli context remove ${name}`);
      }
      const entry: ContextEntry = { name, server };
      await app.updateConfig((c) => {
        c.contexts.push(entry);
        if (opts.use || !c.current_context) c.current_context = name;
      });
      const current = (await app.config()).current_context === name;
      app.out.done(
        { name, server, current },
        `Added "${name}" (${server})${current ? ', now current' : ''}. Sign in with: salli --context ${name} login`,
      );
    });

  context
    .command('remove')
    .alias('rm')
    .argument('<name>', 'Context to remove')
    .description('Remove a context and sign out of it')
    .action(async (name) => {
      validateContextName(name);
      const config = await app.config();
      if (!findContext(config, name)) throw new NotFoundError(`No context named "${name}".`);
      const removedCredentials = await app.deleteCredentials(name).catch(() => false);
      await app.updateConfig((c) => {
        c.contexts = c.contexts.filter((x) => x.name !== name);
        if (c.current_context === name) {
          if (c.contexts[0]) c.current_context = c.contexts[0].name;
          else delete c.current_context;
        }
      });
      app.out.done(
        { name, removed: true, signed_out: removedCredentials },
        `Removed "${name}"${removedCredentials ? ' and its sign-in' : ''}.`,
      );
    });
}
