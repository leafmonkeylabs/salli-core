/**
 * Files sent to the server: statements, receipts, attachments.
 */
import { readFile, stat } from 'node:fs/promises';
import { basename, extname } from 'node:path';
import { UsageError } from '../errors';

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
