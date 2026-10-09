/**
 * The state one invocation of `salli` works with: its runtime, the parsed
 * global options, the configuration, the active context, its credentials,
 * and a client for the server.
 */
import {
  createClient,
  normalizeServerUrl,
  oauth,
  SalliApiError,
  SUPPORTED_API_VERSIONS,
  type Meta,
  type SalliClient,
  type TokenProvider,
} from '@leafmonkeylabs/salli-sdk';
import { parseCredentials, serializeCredentials, type StoredCredentials } from './auth/credentials';
import { openSecretStore, type SecretStore, type StoreChoice } from './auth/store';
import {
  ConfigStore,
  configDirectory,
  DEFAULT_CONTEXT,
  DEFAULT_SERVER,
  findContext,
  OUTPUT_FORMATS,
  validateContextName,
  type ConfigFile,
  type ContextEntry,
  type OutputFormat,
} from './config/config';
import { IncompatibleServerError, NotSignedInError, UsageError } from './errors';
import { createColors, shouldColor } from './output/colors';
import { Output } from './output/output';
import type { Runtime } from './runtime';
import { parseWholeNumber } from './util/numbers';
import { ClackPrompter, type Prompter } from './util/prompts';
import { VERSION } from './version';

export interface GlobalOptions {
  json?: boolean;
  output?: string;
  /** false when --no-color was passed. */
  color?: boolean;
  context?: string;
  server?: string;
  verbose?: boolean;
}

export interface ActiveContext {
  name: string;
  /** The server's normalised base URL. */
  server: string;
  /** The saved context, if this one is saved. */
  entry: ContextEntry | undefined;
  /** Where the server address came from. */
  serverFrom: 'flag' | 'env' | 'context' | 'default';
}

export type AuthSource = 'env' | 'token' | 'oauth' | 'none';

export interface ResolvedAuth {
  provider?: TokenProvider;
  source: AuthSource;
  credentials?: StoredCredentials;
  /** Credentials exist for this context, but for a different server. */
  mismatchedServer?: string;
}

/** How long a server's API version check is trusted before checking again. */
const CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000;

export class App {
  readonly runtime: Runtime;
  readonly configStore: ConfigStore;
  readonly prompter: Prompter;
  out: Output;
  globals: GlobalOptions = {};
  private configCache: ConfigFile | undefined;
  private storeChoice: Promise<StoreChoice> | undefined;
  private contextCache: ActiveContext | undefined;

  constructor(runtime: Runtime) {
    this.runtime = runtime;
    this.configStore = new ConfigStore(configDirectory(runtime.env, runtime.platform, runtime.homedir));
    this.prompter = runtime.prompter ?? new ClackPrompter(runtime.stdin, runtime.stderr, runtime.env);
    this.out = this.makeOutput('table', undefined, undefined);
  }

  get userAgent(): string {
    const bun = (globalThis as { Bun?: { version?: string } }).Bun?.version;
    return `salli-cli/${VERSION} (${this.runtime.platform}; ${bun ? `bun ${bun}` : `node ${process.version}`})`;
  }

  /** Applies the global options; runs before every command. */
  async init(globals: GlobalOptions): Promise<void> {
    this.globals = globals;
    this.contextCache = undefined;
    const config = await this.config();
    let format: OutputFormat = config.settings.output ?? 'table';
    if (globals.output !== undefined) {
      if (!OUTPUT_FORMATS.includes(globals.output as OutputFormat)) {
        throw new UsageError(`--output must be one of: ${OUTPUT_FORMATS.join(', ')} (got "${globals.output}")`);
      }
      format = globals.output as OutputFormat;
    }
    if (globals.json) {
      if (globals.output !== undefined && globals.output !== 'json') {
        throw new UsageError(`--json and --output ${globals.output} ask for different formats; pass one.`);
      }
      format = 'json';
    }
    this.out = this.makeOutput(format, config.settings.color, config.settings.locale);
  }

  private makeOutput(format: OutputFormat, color: ConfigFile['settings']['color'], locale: string | undefined): Output {
    const { env, stdout, stderr } = this.runtime;
    const decision = { flag: this.globals.color !== false, setting: color, env };
    const columns = parseWholeNumber(env.COLUMNS);
    return new Output(this.runtime, {
      format,
      colors: createColors(shouldColor(stdout, decision)),
      errColors: createColors(shouldColor(stderr, decision)),
      width: columns ?? (stdout.isTTY ? (stdout.columns ?? 80) : Number.POSITIVE_INFINITY),
      locale: env.SALLI_LOCALE || locale || undefined,
    });
  }

  // ── Configuration ──────────────────────────────────────────────────────────

  async config(): Promise<ConfigFile> {
    this.configCache ??= await this.configStore.load();
    return this.configCache;
  }

  async saveConfig(config: ConfigFile): Promise<void> {
    await this.configStore.save(config);
    this.configCache = config;
    this.contextCache = undefined;
  }

  async updateConfig(change: (config: ConfigFile) => void): Promise<ConfigFile> {
    const config = await this.configStore.load();
    change(config);
    await this.saveConfig(config);
    return config;
  }

  /** The context this command uses: --context, then SALLI_CONTEXT, then the current one. */
  async context(): Promise<ActiveContext> {
    if (this.contextCache) return this.contextCache;
    const config = await this.config();
    const { env } = this.runtime;
    const named = this.globals.context ?? (env.SALLI_CONTEXT || undefined);
    let entry: ContextEntry | undefined;
    let name: string;
    if (named !== undefined) {
      validateContextName(named);
      entry = findContext(config, named);
      if (!entry) {
        throw new UsageError(`No context named "${named}".`, 'See `salli context list`, or add it with `salli context add`.');
      }
      name = named;
    } else {
      entry = config.current_context ? findContext(config, config.current_context) : undefined;
      entry ??= config.contexts.length === 1 ? config.contexts[0] : undefined;
      name = entry?.name ?? DEFAULT_CONTEXT;
    }

    let server: string;
    let serverFrom: ActiveContext['serverFrom'];
    try {
      if (this.globals.server) {
        server = normalizeServerUrl(this.globals.server);
        serverFrom = 'flag';
      } else if (env.SALLI_SERVER) {
        server = normalizeServerUrl(env.SALLI_SERVER);
        serverFrom = 'env';
      } else if (entry) {
        server = normalizeServerUrl(entry.server);
        serverFrom = 'context';
      } else {
        server = DEFAULT_SERVER;
        serverFrom = 'default';
      }
    } catch (error) {
      throw new UsageError((error as Error).message);
    }
    this.contextCache = { name, server, entry, serverFrom };
    return this.contextCache;
  }

  // ── Credentials ────────────────────────────────────────────────────────────

  async secretStore(): Promise<SecretStore> {
    this.storeChoice ??= openSecretStore({
      env: this.runtime.env,
      platform: this.runtime.platform,
      configDir: this.configStore.dir,
    });
    const choice = await this.storeChoice;
    return choice.store;
  }

  /** Tells the user, once, that credentials went to a file rather than a keychain. */
  private async noticeFileStore(): Promise<void> {
    const choice = await this.storeChoice;
    if (!choice?.fallbackReason) return;
    const config = await this.configStore.load();
    if (config.notices?.file_credentials) return;
    this.out.warn(
      `Saving credentials to ${choice.store.description}: ${choice.fallbackReason}. ` +
        'Set SALLI_CREDENTIAL_STORE=keyring to require a keychain.',
    );
    config.notices = { ...config.notices, file_credentials: true };
    await this.saveConfig(config);
  }

  async loadCredentials(contextName: string): Promise<StoredCredentials | undefined> {
    const store = await this.secretStore();
    return parseCredentials(await store.get(contextName));
  }

  async saveCredentials(contextName: string, credentials: StoredCredentials): Promise<void> {
    const store = await this.secretStore();
    await store.set(contextName, serializeCredentials(credentials));
    await this.noticeFileStore();
  }

  async deleteCredentials(contextName: string): Promise<boolean> {
    const store = await this.secretStore();
    return store.delete(contextName);
  }

  /** The token this context sends: SALLI_TOKEN, else what `salli login` stored. */
  async auth(ctx: ActiveContext): Promise<ResolvedAuth> {
    const envToken = this.runtime.env.SALLI_TOKEN?.trim();
    if (envToken) return { provider: { getToken: () => envToken }, source: 'env' };

    const credentials = await this.loadCredentials(ctx.name);
    if (!credentials) return { source: 'none' };
    // A token only ever goes to the server that issued it.
    if (credentials.server !== ctx.server) return { source: 'none', mismatchedServer: credentials.server };
    if (credentials.kind === 'token') {
      const token = credentials.token;
      return { provider: { getToken: () => token }, source: 'token', credentials };
    }
    const provider = oauth.createOAuthTokenProvider({
      tokens: credentials.tokens,
      tokenEndpoint: credentials.token_endpoint,
      clientId: credentials.client_id,
      ...(credentials.resource ? { resource: credentials.resource } : {}),
      fetch: this.runtime.fetch,
      now: () => this.runtime.now().getTime(),
      save: async (tokens) => {
        await this.saveCredentials(ctx.name, { ...credentials, tokens });
      },
      reload: async () => {
        const latest = await this.loadCredentials(ctx.name);
        return latest?.kind === 'oauth' && latest.server === credentials.server ? latest.tokens : undefined;
      },
    });
    return { provider, source: 'oauth', credentials };
  }

  // ── Clients ────────────────────────────────────────────────────────────────

  /** A client for `server` sending `auth` (none for public endpoints). */
  client(server: string, auth?: TokenProvider, timeoutMs?: number): SalliClient {
    const verbose = this.globals.verbose || this.runtime.env.SALLI_DEBUG === '1';
    return createClient({
      server,
      ...(auth ? { auth } : {}),
      fetch: this.runtime.fetch,
      userAgent: this.userAgent,
      ...(timeoutMs !== undefined ? { timeoutMs } : {}),
      ...(verbose
        ? {
            onResponse: (log) => {
              const path = log.url.replace(server, '');
              const outcome = log.status ?? (log.error instanceof Error ? log.error.name : 'error');
              this.out.errLine(this.out.errColors.dim(`${log.method} ${path} → ${outcome} (${Math.round(log.durationMs)} ms)`));
            },
          }
        : {}),
    });
  }

  /** Fetches `/v1/meta` and refuses a server whose API version this CLI does not speak. */
  async checkServer(ctx: ActiveContext): Promise<Meta> {
    let meta: Meta;
    try {
      meta = await this.client(ctx.server, undefined, 10_000).meta();
    } catch (error) {
      if (error instanceof SalliApiError && error.status === 404) {
        throw new IncompatibleServerError(
          `${ctx.server} has no /v1/meta: it is not a Salli server, or one older than this CLI.`,
          'Upgrade the server, or check the address with `salli context current`.',
        );
      }
      throw error;
    }
    assertCompatible(meta, ctx.server);
    if (ctx.entry && ctx.serverFrom === 'context') {
      const checkedAt = this.runtime.now().toISOString();
      await this.updateConfig((config) => {
        const entry = findContext(config, ctx.name);
        if (entry) {
          entry.api_version = meta.api_version;
          entry.checked_at = checkedAt;
        }
      });
    }
    return meta;
  }

  private needsCheck(ctx: ActiveContext): boolean {
    const entry = ctx.entry;
    if (!entry || ctx.serverFrom !== 'context' || !entry.checked_at || !entry.api_version) return true;
    if (!SUPPORTED_API_VERSIONS.includes(entry.api_version)) return true;
    const last = Date.parse(entry.checked_at);
    return !Number.isFinite(last) || this.runtime.now().getTime() - last > CHECK_INTERVAL_MS;
  }

  /** A signed-in client for the active context, on a server this CLI can talk to. */
  async api(): Promise<SalliClient> {
    const ctx = await this.context();
    const auth = await this.auth(ctx);
    if (!auth.provider) {
      if (auth.mismatchedServer) {
        throw new NotSignedInError(
          `You are signed in to ${auth.mismatchedServer} in context "${ctx.name}", not to ${ctx.server}.`,
          `Sign in to ${ctx.server} with \`salli login --server ${ctx.server}\`, or set SALLI_TOKEN.`,
        );
      }
      throw new NotSignedInError(
        `Not signed in to ${ctx.server}${ctx.entry ? ` (context "${ctx.name}")` : ''}.`,
        ctx.entry || ctx.serverFrom !== 'default'
          ? 'Run `salli login` to sign in, or set SALLI_TOKEN.'
          : 'Run `salli login` to sign in (it asks for your server), or set SALLI_SERVER and SALLI_TOKEN.',
      );
    }
    if (this.needsCheck(ctx)) await this.checkServer(ctx);
    return this.client(ctx.server, auth.provider);
  }
}

/** Throws unless the server's API version is one this CLI speaks. */
export function assertCompatible(meta: Meta, server: string): void {
  if (!SUPPORTED_API_VERSIONS.includes(String(meta.api_version))) {
    throw new IncompatibleServerError(
      `${server} speaks API version ${meta.api_version}; this salli (${VERSION}) speaks ${SUPPORTED_API_VERSIONS.join(', ')}.`,
      'Update salli, or use a server with a matching API version.',
    );
  }
}
