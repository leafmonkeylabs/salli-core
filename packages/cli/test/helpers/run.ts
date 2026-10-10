/**
 * Runs the real `salli` entry point in-process, with its own streams,
 * environment and config directory, and returns what it printed.
 */
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { PassThrough, Readable, Writable } from 'node:stream';
import { main } from '../../src/main';
import type { Runtime } from '../../src/runtime';
import type { Choice, Prompter, Spinner } from '../../src/util/prompts';

export interface RunResult {
  code: number;
  stdout: string;
  stderr: string;
  /** URLs the CLI asked to open in a browser. */
  opened: string[];
}

export interface RunOptions {
  configDir: string;
  env?: Record<string, string | undefined>;
  stdin?: string | Readable;
  stdinIsTTY?: boolean;
  /** Pretend stdout is a terminal this wide. */
  tty?: number;
  prompter?: Prompter;
  /** What opening a URL does. Default: follow it like a browser would. */
  openUrl?: (url: string) => Promise<boolean>;
  /** Whether a browser can open at all (default: yes). */
  browser?: boolean;
  now?: Date;
  signal?: AbortSignal;
  /** The working directory (default: the config directory). */
  cwd?: string;
}

export const FIXED_NOW = new Date('2026-10-09T10:00:00Z');

class Capture extends Writable {
  text = '';
  isTTY?: boolean;
  columns?: number;
  override _write(chunk: Buffer | string, _enc: BufferEncoding, done: () => void): void {
    this.text += chunk.toString();
    done();
  }
}

/** A browser that follows the sign-in redirects to the loopback callback. */
export async function followInBrowser(url: string): Promise<boolean> {
  void fetch(url, { redirect: 'follow' })
    .then((r) => r.text())
    .catch(() => undefined);
  return true;
}

export async function runCli(args: string[], options: RunOptions): Promise<RunResult> {
  const stdout = new Capture();
  const stderr = new Capture();
  if (options.tty) {
    stdout.isTTY = true;
    stdout.columns = options.tty;
  }
  const stdin =
    options.stdin instanceof Readable ? options.stdin : Readable.from(options.stdin === undefined ? [] : [options.stdin]);
  (stdin as Readable & { isTTY?: boolean }).isTTY = options.stdinIsTTY ?? false;
  const opened: string[] = [];
  const runtime: Runtime = {
    env: {
      SALLI_CONFIG_DIR: options.configDir,
      SALLI_CREDENTIAL_STORE: 'file',
      SALLI_LOCALE: 'en-US',
      NO_COLOR: '1',
      ...options.env,
    },
    stdout,
    stderr,
    stdin,
    platform: 'linux',
    homedir: options.configDir,
    cwd: options.cwd ?? options.configDir,
    now: () => options.now ?? FIXED_NOW,
    fetch: globalThis.fetch.bind(globalThis),
    openUrl: async (url) => {
      opened.push(url);
      return (options.openUrl ?? followInBrowser)(url);
    },
    canOpenBrowser: () => options.browser ?? true,
    signal: options.signal ?? new AbortController().signal,
    standalone: false,
    prompter: options.prompter ?? new ScriptedPrompter([], false),
  };
  const code = await main(args, runtime);
  return { code, stdout: stdout.text, stderr: stderr.text, opened };
}

/** The URL of a port nothing listens on (fetch refuses some low ports outright). */
export async function closedServerUrl(): Promise<string> {
  const { createServer } = await import('node:http');
  const server = createServer();
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address() as { port: number };
  await new Promise<void>((resolve) => server.close(() => resolve()));
  return `http://127.0.0.1:${port}`;
}

export async function tempConfigDir(): Promise<{ dir: string; cleanup: () => Promise<void> }> {
  const dir = await mkdtemp(join(tmpdir(), 'salli-cli-test-'));
  return { dir, cleanup: () => rm(dir, { recursive: true, force: true }) };
}

type Answer = string | boolean | ((options: { message: string; options?: Choice<unknown>[] }) => unknown);

/** Answers prompts from a list, in order, and records what was asked. */
export class ScriptedPrompter implements Prompter {
  readonly asked: string[] = [];
  constructor(
    private readonly answers: Answer[],
    readonly interactive = true,
  ) {}

  private next(message: string, choices?: Choice<unknown>[]): unknown {
    this.asked.push(message);
    if (this.answers.length === 0) throw new Error(`Unexpected prompt: ${message}`);
    const answer = this.answers.shift();
    return typeof answer === 'function' ? answer({ message, ...(choices ? { options: choices } : {}) }) : answer;
  }

  async confirm(o: { message: string }): Promise<boolean> {
    return Boolean(this.next(o.message));
  }
  async text(o: { message: string }): Promise<string> {
    return String(this.next(o.message));
  }
  async password(o: { message: string }): Promise<string> {
    return String(this.next(o.message));
  }
  async select<T>(o: { message: string; options: Choice<T>[] }): Promise<T> {
    const answer = this.next(o.message, o.options as Choice<unknown>[]);
    const found = o.options.find((c) => c.value === answer || c.label === answer);
    if (!found) throw new Error(`No choice "${String(answer)}" for: ${o.message} (have ${o.options.map((c) => c.label).join(', ')})`);
    return found.value;
  }
  async search<T>(o: { message: string; options: Choice<T>[] }): Promise<T> {
    return this.select(o);
  }
  spinner(): Spinner {
    return { start: () => undefined, message: () => undefined, stop: () => undefined };
  }
}

export { PassThrough };
