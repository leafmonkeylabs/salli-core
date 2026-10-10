/**
 * Text that is safe and measurable in a terminal.
 *
 * Everything shown comes from a server (account names, descriptions, the
 * agent's replies), so it is stripped of escape sequences and control
 * characters before it reaches the terminal: a description must not be able
 * to move the cursor, change the title or hide text.
 */
import stringWidth from 'string-width';

const ESC = String.fromCharCode(0x1b);
const BEL = String.fromCharCode(0x07);
// CSI (ESC [ … final), OSC (ESC ] … BEL or ESC \), and two-character escapes.
const ANSI = new RegExp(
  `${ESC}\\[[0-?]*[ -/]*[@-~]|${ESC}\\][^${BEL}${ESC}]*(?:${BEL}|${ESC}\\\\)?|${ESC}[@-Z\\\\-_]`,
  'g',
);
// C0 and C1 controls, except tab and newline (handled per use).
// eslint-disable-next-line no-control-regex -- matching control characters is the point
const CONTROL = new RegExp('[\\u0000-\\u0008\\u000b-\\u001f\\u007f-\\u009f]', 'g');

/** Removes escape sequences and control characters; keeps newlines and tabs. */
export function sanitize(text: string): string {
  return text.replace(ANSI, '').replace(CONTROL, '');
}

/** One line of text for a table cell or a label: whitespace runs become one space. */
export function singleLine(text: string): string {
  return sanitize(text).replace(/\s*[\t\n\r]+\s*/g, ' ').trim();
}

/** The number of terminal columns `text` occupies (ignoring colour codes). */
export function displayWidth(text: string): number {
  return stringWidth(text);
}

const segmenter = new Intl.Segmenter(undefined, { granularity: 'grapheme' });

/** Cuts `text` to at most `width` columns, ending with … when cut. */
export function truncate(text: string, width: number): string {
  if (width <= 0) return '';
  if (displayWidth(text) <= width) return text;
  if (width === 1) return '…';
  let out = '';
  let used = 0;
  for (const { segment } of segmenter.segment(text)) {
    const w = displayWidth(segment);
    if (used + w > width - 1) break;
    out += segment;
    used += w;
  }
  return `${out}…`;
}

export function padEnd(text: string, width: number): string {
  const gap = width - displayWidth(text);
  return gap > 0 ? text + ' '.repeat(gap) : text;
}

export function padStart(text: string, width: number): string {
  const gap = width - displayWidth(text);
  return gap > 0 ? ' '.repeat(gap) + text : text;
}

/** "1 account" / "3 accounts". */
export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** The first characters of an id, as lists show it. */
export function shortId(id: unknown, length = 8): string {
  return typeof id === 'string' ? id.slice(0, length) : '';
}
