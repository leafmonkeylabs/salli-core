/**
 * The `salli` command tree.
 */
import { Command, type OutputConfiguration } from '@commander-js/extra-typings';
import type { App } from './app';
import { registerCompletion } from './commands/completion';
import { registerConfig } from './commands/config';
import { registerContext } from './commands/context';
import { OUTPUT_FORMATS } from './config/config';
import { VERSION } from './version';

export function buildProgram(app: App, output: OutputConfiguration): Command {
  const program = new Command('salli')
    .description('Salli from the terminal: your ledger, budgets, plans and AI advisor, on your own server.')
    .version(VERSION, '-V, --version', 'Print the version')
    .helpOption('-h, --help', 'Show help')
    .helpCommand('help [command]', 'Show help for a command')
    .option('--json', 'Print the API response as JSON (same as --output json)')
    .option('-o, --output <format>', `Output format: ${OUTPUT_FORMATS.join(', ')}`)
    .option('--no-color', 'No colour (also: NO_COLOR=1)')
    .option('--context <name>', 'Use this context instead of the current one')
    .option('--server <url>', 'Talk to this server (overrides the context; SALLI_SERVER)')
    .option('--verbose', 'Log each request to stderr')
    .exitOverride()
    .configureOutput(output)
    .showSuggestionAfterError(true)
    .configureHelp({ showGlobalOptions: false });

  program.hook('preAction', async (_root, command) => {
    await app.init(command.optsWithGlobals());
  });

  program.addHelpText(
    'after',
    `
Output: tables for people; --json prints the API's JSON, -o ndjson|csv the records.
Exit codes: 0 ok, 1 error, 2 usage, 3 not signed in, 4 not found,
            5 refused by the server, 6 incompatible server, 7 network, 130 interrupted.

Start with:  salli login   then   salli status`,
  );

  program.commandsGroup('Settings:');
  registerContext(program, app);
  registerConfig(program, app);
  registerCompletion(program, app);

  return program as unknown as Command;
}
