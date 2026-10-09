/**
 * Files sent to the server (statements, receipts, attachments), and text the
 * server sends back to be saved (CSV reports, plain-text ledgers, exports).
 */
import { chmod, readFile, stat, writeFile } from 'node:fs/promises';
import { basename, extname, resolve } from 'node:path';
import type { App } from '../app';
import { CliError, UsageError } from '../errors';

const MIME: Record<string, string> = {
  '.pdf': 'application/pdf',
  '.csv': 'text/csv',
  '.txt': 'text/plain',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  '.xls': 'application/vnd.ms-excel',
};

/** Reads a file to upload, refusing what is missing, not a file, or too big. */
export async function readUpload(path: string, maxBytes?: number): Promise<File> {
  let info;
  try {
    info = await stat(path);
  } catch {
    throw new UsageError(`No such file: ${path}`);
  }
  if (!info.isFile()) throw new UsageError(`Not a file: ${path}`);
  const name = basename(path);
  if (maxBytes !== undefined && info.size > maxBytes) {
    throw new UsageError(`${name} is larger than the server accepts (${Math.round(maxBytes / 1024 / 1024)} MB).`);
  }
  return new File([await readFile(path)], name, { type: MIME[extname(name).toLowerCase()] ?? 'application/octet-stream' });
}

/** A text response (CSV, a plain-text ledger) as the string it should be. */
export function textOf(value: unknown): string {
  if (typeof value === 'string') return value;
  throw new CliError('The server answered without the text it should have sent.');
}

/**
 * Writes a command's text result: to stdout when `path` is undefined or "-",
 * otherwise to that file, saying so (as JSON for scripts: what, where, how
 * many bytes). A private file is readable only by you.
 */
export async function writeOutput(
  app: App,
  text: string,
  path: string | undefined,
  describe: Record<string, unknown>,
  what: string,
  options: { private?: boolean } = {},
): Promise<void> {
  if (path === undefined || path === '-') {
    app.out.write(text);
    return;
  }
  await writeFile(path, text, { encoding: 'utf8', ...(options.private ? { mode: 0o600 } : {}) });
  // `mode` applies only to a new file; an existing one keeps its permissions otherwise.
  if (options.private) await chmod(path, 0o600);
  app.out.done(
    { ...describe, path: resolve(path), bytes: Buffer.byteLength(text) },
    `Wrote ${what} to ${path}${options.private ? ' (readable only by you)' : ''}.`,
  );
}
