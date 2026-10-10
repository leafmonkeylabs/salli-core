/**
 * Runs one `salli` command and returns its exit code. The process entry
 * (bin.ts) and the tests both call this, with different runtimes.
 */
import { CommanderError } from '@commander-js/extra-typings';
import { App } from './app';
import { CliError, ExitCode, exitCodeFor, hintFor, messageFor, problemFor, UsageError } from './errors';
import { singleLine } from './output/text';
import { buildProgram } from './program';
import type { Runtime } from './runtime';

function wantsJson(argv: readonly string[]): boolean {
  return argv.some(
    (arg, i) =>
      arg === '--json' ||
      arg === '--output=json' ||
      arg === '--output=ndjson' ||
      (arg === '--output' && (argv[i + 1] === 'json' || argv[i + 1] === 'ndjson')),
  );
}

/** Program options that take a value, so their value is not a command. */
const ROOT_VALUE_OPTIONS = new Set(['--output', '--context', '--server']);

/**
 * `--version` is the program's own flag (`salli --version`), and Commander
 * claims it wherever it appears; but after a command it is that command's
 * option (`salli tax rules show XA --version 3`). So, after the command, a
 * `--version <value>` is passed on as `--version=<value>`, which the program's
 * flag (taking no value) leaves to the command.
 */
export function routeVersionOption(argv: readonly string[]): string[] {
  const args = [...argv];
  let i = 0;
  while (i < args.length && args[i]?.startsWith('-') && args[i] !== '--') {
    i += ROOT_VALUE_OPTIONS.has(args[i] ?? '') ? 2 : 1;
  }
  for (let j = i + 1; j < args.length; j += 1) {
    if (args[j] === '--') break;
    const value = args[j + 1];
    if (args[j] === '--version' && value !== undefined && !value.startsWith('-')) {
      args.splice(j, 2, `--version=${value}`);
    }
  }
  return args;
}

export async function main(argv: readonly string[], runtime: Runtime): Promise<number> {
  const app = new App(runtime);
  const json = (): boolean => app.out.json || wantsJson(argv);

  const report = (error: unknown): number => {
    const code = exitCodeFor(error);
    if (error instanceof CliError && error.quiet) return code;
    if (json()) {
      runtime.stderr.write(`${JSON.stringify(problemFor(error))}\n`);
      return code;
    }
    const c = app.out.errColors;
    // A problem's title and detail come from the server: no escape sequences.
    runtime.stderr.write(`${c.red('✗')} ${singleLine(messageFor(error))}\n`);
    const hint = hintFor(error);
    if (hint) runtime.stderr.write(`  ${c.dim(singleLine(hint))}\n`);
    const unexpected = code === ExitCode.ERROR && !(error instanceof Error && 'status' in error);
    if (unexpected && error instanceof Error && (app.globals.verbose || runtime.env.SALLI_DEBUG === '1')) {
      runtime.stderr.write(`${c.dim(error.stack ?? '')}\n`);
    }
    return code;
  };

  // Set before any command is added, so every subcommand inherits them.
  const program = buildProgram(app, {
    writeOut: (text) => runtime.stdout.write(text),
    writeErr: (text) => runtime.stderr.write(text),
    outputError: (text) => {
      const message = text.trim().replace(/^error:\s*/i, '');
      report(new UsageError(message.charAt(0).toUpperCase() + message.slice(1), 'Add --help to the command for its usage.'));
    },
  });

  if (argv.length === 0) {
    runtime.stdout.write(program.helpInformation());
    return ExitCode.OK;
  }

  try {
    await program.parseAsync(routeVersionOption(argv), { from: 'user' });
    return ExitCode.OK;
  } catch (error) {
    if (error instanceof CommanderError) {
      // Help and --version end parsing with exit code 0; anything else
      // Commander raises is a usage error it has already reported.
      return error.exitCode === 0 ? ExitCode.OK : ExitCode.USAGE;
    }
    return report(error);
  }
}
