/**
 * The CLI's configuration: named contexts and a few settings.
 *
 * Like kubectl's or gh's, a context names a server you use (`home`, `work`);
 * one is current. Credentials are not kept here: they live in the system
 * keychain (see auth/store), keyed by context name.
 *
 * Location: $XDG_CONFIG_HOME/salli/config.json (~/.config/salli on Linux and
 * macOS), %APPDATA%\salli\config.json on Windows; SALLI_CONFIG_DIR overrides.
 */
import { chmod, mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { CliError, UsageError } from '../errors';

export const DEFAULT_SERVER = 'http://localhost:8000';
export const DEFAULT_CONTEXT = 'default';

export type OutputFormat = 'table' | 'json' | 'ndjson' | 'csv';
export const OUTPUT_FORMATS: readonly OutputFormat[] = ['table', 'json', 'ndjson', 'csv'];

export type ColorSetting = 'auto' | 'always' | 'never';

export interface ContextEntry {
  name: string;
  /** The server's base URL. */
  server: string;
  /** The OAuth client this CLI registered with the server (RFC 7591). */
  client_id?: string;
  /** The API version the server reported when last checked. */
  api_version?: string;
  /** When the server's `/v1/meta` was last checked (ISO 8601). */
  checked_at?: string;
}

export interface Settings {
  /** The default output format. */
  output?: OutputFormat;
  /** Whether to colour output: auto (when a terminal), always, never. */
  color?: ColorSetting;
  /** A BCP 47 locale for numbers and dates, e.g. en-GB. Default: the system's. */
  locale?: string;
}

export interface ConfigFile {
  version: 1;
  current_context?: string;
  contexts: ContextEntry[];
  settings: Settings;
  /** One-time notices already shown. */
  notices?: Record<string, boolean>;
}

/** The settings `salli config` knows, with what each accepts. */
export const SETTINGS: Record<keyof Settings, { describe: string; values?: readonly string[] }> = {
  output: { describe: 'Default output format', values: OUTPUT_FORMATS },
  color: { describe: 'Colour output (auto: only in a terminal)', values: ['auto', 'always', 'never'] },
  locale: { describe: 'Locale for amounts and dates (BCP 47, e.g. en-GB); default: the system locale' },
};

export function isSettingKey(key: string): key is keyof Settings {
  return Object.hasOwn(SETTINGS, key);
}

/** Checks a setting's value, returning it normalised. */
export function validateSetting(key: keyof Settings, value: string): string {
  const spec = SETTINGS[key];
  if (spec.values && !spec.values.includes(value)) {
    throw new UsageError(`${key} must be one of: ${spec.values.join(', ')} (got "${value}")`);
  }
  if (key === 'locale') {
    try {
      const [canonical] = Intl.getCanonicalLocales(value);
      if (!canonical) throw new Error('empty');
      return canonical;
    } catch {
      throw new UsageError(`Not a locale: "${value}" (try en-US, en-GB, de-DE)`);
    }
  }
  return value;
}

const CONTEXT_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;

export function validateContextName(name: string): string {
  if (!CONTEXT_NAME.test(name)) {
    throw new UsageError(
      `Not a valid context name: "${name}"`,
      'Use letters, digits, dot, dash and underscore (up to 64 characters).',
    );
  }
  return name;
}

/** Where the configuration lives. */
export function configDirectory(
  env: Record<string, string | undefined>,
  platform: NodeJS.Platform,
  home: string,
): string {
  if (env.SALLI_CONFIG_DIR) return env.SALLI_CONFIG_DIR;
  if (platform === 'win32') return join(env.APPDATA || join(home, 'AppData', 'Roaming'), 'salli');
  return join(env.XDG_CONFIG_HOME || join(home, '.config'), 'salli');
}

function emptyConfig(): ConfigFile {
  return { version: 1, contexts: [], settings: {} };
}

/** Reads and writes config.json in a directory. */
export class ConfigStore {
  readonly dir: string;
  readonly path: string;

  constructor(dir: string) {
    this.dir = dir;
    this.path = join(dir, 'config.json');
  }

  async load(): Promise<ConfigFile> {
    let text: string;
    try {
      text = await readFile(this.path, 'utf8');
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return emptyConfig();
      throw new CliError(`Could not read ${this.path}: ${(error as Error).message}`);
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      throw new CliError(`${this.path} is not valid JSON.`, {
        hint: 'Fix or delete the file; `salli context add` will recreate it.',
      });
    }
    const config = parsed as Partial<ConfigFile>;
    return {
      version: 1,
      ...(typeof config.current_context === 'string' ? { current_context: config.current_context } : {}),
      contexts: Array.isArray(config.contexts)
        ? config.contexts.filter((c): c is ContextEntry => typeof c?.name === 'string' && typeof c.server === 'string')
        : [],
      settings: typeof config.settings === 'object' && config.settings !== null ? config.settings : {},
      ...(config.notices ? { notices: config.notices } : {}),
    };
  }

  /** Writes the file atomically, readable only by its owner. */
  async save(config: ConfigFile): Promise<void> {
    await mkdir(this.dir, { recursive: true, mode: 0o700 });
    const temp = `${this.path}.${process.pid}.tmp`;
    await writeFile(temp, `${JSON.stringify(config, null, 2)}\n`, { mode: 0o600 });
    await rename(temp, this.path);
    await chmod(this.path, 0o600).catch(() => undefined);
  }

  async update(change: (config: ConfigFile) => void): Promise<ConfigFile> {
    const config = await this.load();
    change(config);
    await this.save(config);
    return config;
  }
}

export function findContext(config: ConfigFile, name: string): ContextEntry | undefined {
  return config.contexts.find((c) => c.name === name);
}
