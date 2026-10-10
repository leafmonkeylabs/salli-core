/**
 * Everything the CLI touches outside itself, in one object, so a test can
 * run the real command tree with its own streams, environment, clock,
 * config directory and browser.
 */
import { homedir } from 'node:os';
import type { Readable, Writable } from 'node:stream';
import { browserAvailable, openInBrowser } from './auth/browser';
import type { Prompter } from './util/prompts';

export interface OutputStream extends Writable {
  isTTY?: boolean;
  columns?: number;
}

export interface InputStream extends Readable {
  isTTY?: boolean;
  setRawMode?: (mode: boolean) => unknown;
}

export interface Runtime {
  env: Record<string, string | undefined>;
  stdout: OutputStream;
  stderr: OutputStream;
  stdin: InputStream;
  platform: NodeJS.Platform;
  homedir: string;
  /** The current time. */
  now(): Date;
  fetch: typeof globalThis.fetch;
  /** Opens a URL in the user's browser; resolves false if it could not. */
  openUrl(url: string): Promise<boolean>;
  /** Whether a browser can open here at all (not over SSH, not headless). */
  canOpenBrowser(): boolean;
  /** Aborts when the user presses Ctrl-C. */
  signal: AbortSignal;
  /** True inside a standalone (bun --compile) binary. */
  standalone: boolean;
  /** Asks the user questions; tests supply scripted answers. Default: @clack/prompts. */
  prompter?: Prompter;
}

declare const Bun: unknown;

/** Whether this process is a `bun build --compile` executable. */
export function isStandaloneBinary(): boolean {
  if (typeof Bun === 'undefined') return false;
  // A compiled binary's modules live in Bun's virtual filesystem.
  return import.meta.url.includes('$bunfs') || import.meta.url.includes('~BUN');
}

/** The runtime of the process itself. */
export function processRuntime(signal: AbortSignal): Runtime {
  return {
    env: process.env,
    stdout: process.stdout,
    stderr: process.stderr,
    stdin: process.stdin,
    platform: process.platform,
    homedir: homedir(),
    now: () => new Date(),
    fetch: globalThis.fetch.bind(globalThis),
    openUrl: (url) => openInBrowser(url, process.env, process.platform),
    canOpenBrowser: () => browserAvailable(process.env, process.platform),
    signal,
    standalone: isStandaloneBinary(),
  };
}
