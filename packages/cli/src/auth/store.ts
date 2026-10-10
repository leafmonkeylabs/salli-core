/**
 * Where tokens are kept: the operating system's keychain when there is one.
 *
 *   keyring          @napi-rs/keyring: macOS Keychain, Windows Credential
 *                    Manager, the Secret Service on Linux
 *   keychain         macOS `security`, for a standalone binary that cannot
 *                    load the native keyring module
 *   secret-service   Linux `secret-tool`, likewise
 *   file             credentials.json beside the config, mode 0600, when
 *                    there is no keychain (a headless server, a container)
 *
 * Every backend stores one secret per context: service "salli", account =
 * the context name. SALLI_CREDENTIAL_STORE picks one: keyring, command
 * (security / secret-tool), or file.
 */
import { spawn } from 'node:child_process';
import { chmod, mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { CliError } from '../errors';

export const KEYCHAIN_SERVICE = 'salli';

export type StoreKind = 'keyring' | 'keychain' | 'secret-service' | 'file';

export interface SecretStore {
  readonly kind: StoreKind;
  /** For `salli doctor`: where secrets go. */
  readonly description: string;
  get(account: string): Promise<string | undefined>;
  set(account: string, secret: string): Promise<void>;
  delete(account: string): Promise<boolean>;
}

// ── @napi-rs/keyring ─────────────────────────────────────────────────────────

interface KeyringEntry {
  getPassword(): Promise<string | undefined>;
  setPassword(password: string): Promise<void>;
  deletePassword(): Promise<boolean>;
}
type KeyringModule = { AsyncEntry: new (service: string, account: string) => KeyringEntry };

async function loadKeyring(): Promise<KeyringModule | undefined> {
  try {
    // Kept out of the npm bundle (it is a native module, installed with the
    // package); a standalone binary embeds it if bun can.
    const mod = (await import('@napi-rs/keyring')) as Partial<KeyringModule> & { default?: Partial<KeyringModule> };
    const AsyncEntry = mod.AsyncEntry ?? mod.default?.AsyncEntry;
    return AsyncEntry ? { AsyncEntry } : undefined;
  } catch {
    return undefined;
  }
}

class NativeKeyringStore implements SecretStore {
  readonly kind = 'keyring';
  readonly description: string;
  constructor(
    private readonly keyring: KeyringModule,
    platform: NodeJS.Platform,
  ) {
    this.description =
      platform === 'darwin'
        ? 'macOS Keychain'
        : platform === 'win32'
          ? 'Windows Credential Manager'
          : 'the Secret Service (GNOME Keyring / KWallet)';
  }
  private entry(account: string): KeyringEntry {
    return new this.keyring.AsyncEntry(KEYCHAIN_SERVICE, account);
  }
  async get(account: string): Promise<string | undefined> {
    return (await this.entry(account).getPassword()) ?? undefined;
  }
  async set(account: string, secret: string): Promise<void> {
    await this.entry(account).setPassword(secret);
  }
  async delete(account: string): Promise<boolean> {
    return this.entry(account).deletePassword();
  }
}

// ── OS commands (standalone binaries) ────────────────────────────────────────

interface Run {
  code: number;
  stdout: string;
  stderr: string;
}

function run(command: string, args: string[], input?: string): Promise<Run> {
  return new Promise((resolve) => {
    let child;
    try {
      child = spawn(command, args, { stdio: ['pipe', 'pipe', 'pipe'] });
    } catch (error) {
      resolve({ code: -1, stdout: '', stderr: String(error) });
      return;
    }
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d: Buffer) => (stdout += d.toString('utf8')));
    child.stderr.on('data', (d: Buffer) => (stderr += d.toString('utf8')));
    child.on('error', (error) => resolve({ code: -1, stdout, stderr: String(error) }));
    child.on('close', (code) => resolve({ code: code ?? -1, stdout, stderr }));
    child.stdin.end(input ?? '');
  });
}

const SAFE_ACCOUNT = /^[A-Za-z0-9._-]+$/;

function checkAccount(account: string): string {
  if (!SAFE_ACCOUNT.test(account)) throw new CliError(`Not a valid context name: ${account}`);
  return account;
}

/** macOS `security`. The secret goes in on stdin (`security -i`), never in argv. */
class MacKeychainStore implements SecretStore {
  readonly kind = 'keychain';
  readonly description = 'macOS Keychain (via security)';

  async get(account: string): Promise<string | undefined> {
    const result = await run('security', ['find-generic-password', '-s', KEYCHAIN_SERVICE, '-a', checkAccount(account), '-w']);
    if (result.code === 0) return result.stdout.replace(/\n$/, '');
    if (result.code === 44) return undefined; // errSecItemNotFound
    throw new CliError(`Could not read the keychain: ${result.stderr.trim() || `security exited ${result.code}`}`);
  }

  async set(account: string, secret: string): Promise<void> {
    const hex = Buffer.from(secret, 'utf8').toString('hex');
    const command = `add-generic-password -U -s ${KEYCHAIN_SERVICE} -a ${checkAccount(account)} -l "Salli CLI (${account})" -X ${hex}\n`;
    const result = await run('security', ['-i'], command);
    if (result.code !== 0 || /error/i.test(result.stderr)) {
      throw new CliError(`Could not write to the keychain: ${result.stderr.trim() || `security exited ${result.code}`}`);
    }
  }

  async delete(account: string): Promise<boolean> {
    const result = await run('security', ['delete-generic-password', '-s', KEYCHAIN_SERVICE, '-a', checkAccount(account)]);
    return result.code === 0;
  }
}

/** Linux `secret-tool` (libsecret). Attributes match @napi-rs/keyring's. */
class SecretToolStore implements SecretStore {
  readonly kind = 'secret-service';
  readonly description = 'the Secret Service (via secret-tool)';

  async get(account: string): Promise<string | undefined> {
    const result = await run('secret-tool', ['lookup', 'service', KEYCHAIN_SERVICE, 'username', checkAccount(account)]);
    if (result.code === 0) return result.stdout.replace(/\n$/, '') || undefined;
    if (result.code === 1 && !result.stderr.trim()) return undefined;
    throw new CliError(`Could not read the Secret Service: ${result.stderr.trim() || `secret-tool exited ${result.code}`}`);
  }

  async set(account: string, secret: string): Promise<void> {
    const result = await run(
      'secret-tool',
      ['store', `--label=Salli CLI (${checkAccount(account)})`, 'service', KEYCHAIN_SERVICE, 'username', account],
      secret,
    );
    if (result.code !== 0) {
      throw new CliError(`Could not write to the Secret Service: ${result.stderr.trim() || `secret-tool exited ${result.code}`}`);
    }
  }

  async delete(account: string): Promise<boolean> {
    const result = await run('secret-tool', ['clear', 'service', KEYCHAIN_SERVICE, 'username', checkAccount(account)]);
    return result.code === 0;
  }
}

// ── A file, readable only by its owner ───────────────────────────────────────

export class FileStore implements SecretStore {
  readonly kind = 'file';
  readonly path: string;
  readonly description: string;

  constructor(private readonly dir: string) {
    this.path = join(dir, 'credentials.json');
    this.description = `${this.path} (readable only by you)`;
  }

  private async read(): Promise<Record<string, string>> {
    try {
      const parsed = JSON.parse(await readFile(this.path, 'utf8')) as unknown;
      return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, string>) : {};
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return {};
      throw new CliError(`Could not read ${this.path}: ${(error as Error).message}`);
    }
  }

  private async write(all: Record<string, string>): Promise<void> {
    await mkdir(this.dir, { recursive: true, mode: 0o700 });
    const temp = `${this.path}.${process.pid}.tmp`;
    await writeFile(temp, `${JSON.stringify(all, null, 2)}\n`, { mode: 0o600 });
    await rename(temp, this.path);
    await chmod(this.path, 0o600).catch(() => undefined);
  }

  async get(account: string): Promise<string | undefined> {
    const value = (await this.read())[account];
    return typeof value === 'string' ? value : undefined;
  }

  async set(account: string, secret: string): Promise<void> {
    const all = await this.read();
    all[account] = secret;
    await this.write(all);
  }

  async delete(account: string): Promise<boolean> {
    const all = await this.read();
    if (!(account in all)) return false;
    delete all[account];
    await this.write(all);
    return true;
  }
}

// ── Choosing one ─────────────────────────────────────────────────────────────

export interface StoreChoice {
  store: SecretStore;
  /** Why a keychain was not used, when the file store was chosen by fallback. */
  fallbackReason?: string;
}

const PROBE_ACCOUNT = 'salli-probe';

/** Picks the best store this machine offers. */
export async function openSecretStore(options: {
  env: Record<string, string | undefined>;
  platform: NodeJS.Platform;
  configDir: string;
}): Promise<StoreChoice> {
  const wanted = options.env.SALLI_CREDENTIAL_STORE?.trim().toLowerCase();
  const file = new FileStore(options.configDir);
  if (wanted === 'file') return { store: file };
  if (wanted === 'command') {
    if (options.platform === 'darwin') return { store: new MacKeychainStore() };
    if (options.platform === 'linux') return { store: new SecretToolStore() };
    throw new CliError('SALLI_CREDENTIAL_STORE=command needs macOS (security) or Linux (secret-tool).');
  }

  const keyring = await loadKeyring();
  if (keyring) {
    const store = new NativeKeyringStore(keyring, options.platform);
    try {
      await store.get(PROBE_ACCOUNT);
      return { store };
    } catch (error) {
      if (wanted === 'keyring') throw new CliError(`The system keychain is not usable: ${(error as Error).message}`);
      return { store: file, fallbackReason: `the system keychain is not usable (${(error as Error).message})` };
    }
  }
  if (wanted === 'keyring') throw new CliError('The keyring module could not be loaded on this platform.');

  // A standalone binary cannot load the native module; use the OS's own tool.
  if (options.platform === 'darwin') {
    const store = new MacKeychainStore();
    const probe = await run('security', ['find-generic-password', '-s', KEYCHAIN_SERVICE, '-a', PROBE_ACCOUNT]);
    if (probe.code === 0 || probe.code === 44) return { store };
  }
  if (options.platform === 'linux') {
    const store = new SecretToolStore();
    const probe = await run('secret-tool', ['lookup', 'service', KEYCHAIN_SERVICE, 'username', PROBE_ACCOUNT]);
    if (probe.code === 0 || (probe.code === 1 && !probe.stderr.trim())) return { store };
  }
  return { store: file, fallbackReason: 'no system keychain is available' };
}
