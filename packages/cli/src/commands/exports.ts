/**
 * salli export beancount | hledger: your whole ledger as plain-text
 * accounting, to check with bean-check or hledger, or to keep.
 */
import type { Command } from '@commander-js/extra-typings';
import { exportsBeancount, exportsHledger, type SalliClient } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { textOf, writeOutput } from '../util/files';

const FORMATS = {
  beancount: {
    description: 'Every account and entry as a Beancount file (check it with bean-check)',
    what: 'your ledger as Beancount',
    read: (api: SalliClient) => api.call(exportsBeancount, { timeoutMs: 5 * 60_000 }),
  },
  hledger: {
    description: 'Every account and entry as an hledger journal (Ledger reads it too)',
    what: 'your ledger as an hledger journal',
    read: (api: SalliClient) => api.call(exportsHledger, { timeoutMs: 5 * 60_000 }),
  },
} as const;

export function registerExports(program: Command, app: App): void {
  const exports = program
    .command('export')
    .description('Your whole ledger as plain-text accounting: Beancount or hledger')
    .addHelpText(
      'after',
      `
Examples:
  $ salli export beancount -o ledger.beancount && bean-check ledger.beancount
  $ salli export hledger | hledger -f - balance

Everything else Salli keeps about you, as JSON: salli profile export`,
    );

  for (const [name, format] of Object.entries(FORMATS)) {
    exports
      .command(name)
      .description(format.description)
      .option('-o, --out <file>', 'Write it to this file (default: stdout)')
      .action(async (opts) => {
        const api = await app.api();
        const text = textOf(await format.read(api));
        await writeOutput(app, text, opts.out, { format: name }, format.what, { private: true });
      });
  }
}
