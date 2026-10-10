import type { InputStream } from '../runtime';

/** Everything on stdin, as text (for `--token -` and piped input). */
export async function readAllStdin(stdin: InputStream): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of stdin) chunks.push(typeof chunk === 'string' ? Buffer.from(chunk) : (chunk as Buffer));
  return Buffer.concat(chunks).toString('utf8').trim();
}
