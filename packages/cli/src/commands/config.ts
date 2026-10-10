/**
 * salli config get | set | unset | list | path
 */
import type { Command } from '@commander-js/extra-typings';
import type { App } from '../app';
import { isSettingKey, SETTINGS, validateSetting, type Settings } from '../config/config';
import { UsageError } from '../errors';

function settingKey(key: string): keyof Settings {
  if (!isSettingKey(key)) {
    throw new UsageError(`Unknown setting "${key}".`, `Settings: ${Object.keys(SETTINGS).join(', ')}`);
  }
  return key;
}

export function registerConfig(program: Command, app: App): void {
  const config = program
    .command('config')
    .description('Read and change settings (output format, colour, locale)')
    .addHelpText(
      'after',
      `
Settings:
${Object.entries(SETTINGS)
  .map(([key, spec]) => `  ${key.padEnd(8)} ${spec.describe}${spec.values ? ` (${spec.values.join(' | ')})` : ''}`)
  .join('\n')}

Examples:
  $ salli config set output json
  $ salli config set locale en-GB
  $ salli config unset color`,
    );

  config
    .command('list')
    .description('Show every setting')
    .action(async () => {
      const { settings } = await app.config();
      const rows = Object.entries(SETTINGS).map(([key, spec]) => ({
        key,
        value: settings[key as keyof Settings] ?? null,
        description: spec.describe,
      }));
      app.out.emit(settings, {
        records: () => rows,
        human: () => {
          app.out.line(
            app.out.table(rows, [
              { header: 'SETTING', get: (r) => r.key },
              { header: 'VALUE', get: (r) => r.value ?? '(default)', style: (t, r) => (r.value === null ? app.out.colors.dim(t) : t) },
              { header: 'DESCRIPTION', get: (r) => r.description, shrink: true },
            ]),
          );
          app.out.note(`Stored in ${app.configStore.path}`);
        },
      });
    });

  config
    .command('get')
    .argument('<key>', 'Setting name')
    .description('Print one setting')
    .action(async (key) => {
      const name = settingKey(key);
      const value = (await app.config()).settings[name] ?? null;
      app.out.emit(
        { [name]: value },
        { human: () => app.out.line(value === null ? app.out.colors.dim('(default)') : String(value)) },
      );
    });

  config
    .command('set')
    .argument('<key>', 'Setting name')
    .argument('<value>', 'New value')
    .description('Change a setting')
    .action(async (key, value) => {
      const name = settingKey(key);
      const normalized = validateSetting(name, value);
      await app.updateConfig((c) => {
        (c.settings as Record<string, string>)[name] = normalized;
      });
      app.out.done({ [name]: normalized }, `${name} = ${normalized}`);
    });

  config
    .command('unset')
    .argument('<key>', 'Setting name')
    .description('Return a setting to its default')
    .action(async (key) => {
      const name = settingKey(key);
      await app.updateConfig((c) => {
        delete c.settings[name];
      });
      app.out.done({ [name]: null }, `${name} is back to its default.`);
    });

  config
    .command('path')
    .description('Print where the configuration file is')
    .action(() => {
      app.out.emit({ path: app.configStore.path }, { human: () => app.out.line(app.configStore.path) });
    });
}
