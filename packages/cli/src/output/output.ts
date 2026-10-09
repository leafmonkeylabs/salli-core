/**
 * The output contract.
 *
 * Data goes to stdout; everything else (progress, confirmations of what
 * happened, warnings, errors) goes to stderr, so stdout is always the
 * command's result and nothing else.
 *
 *   table   people: tables and summaries (the default)
 *   json    the API's JSON exactly as the server sent it (re-indented only)
 *   ndjson  one JSON value per line: each record of a list, or the result
 *   csv     the records, one row each, fields as columns
 *
 * A command that combines several API calls prints an object holding each
 * response; one whose operation returns no content prints a small object
 * saying what was done.
 */
import { exactValue, formatAmount, formatRatio, toJsonText, type FormatAmountOptions } from '@leafmonkeylabs/salli-sdk';
import type { OutputFormat } from '../config/config';
import type { Runtime } from '../runtime';
import type { Colors } from './colors';
import { renderDetails, renderTable, type Column, type DetailRow } from './table';
import { sanitize } from './text';

export interface View<T> {
  /** The records a list holds, for ndjson and csv. Default: the data itself. */
  records?: (data: T) => unknown;
  /** Writes the human view (table format). */
  human: (data: T) => void;
}

export interface OutputSettings {
  format: OutputFormat;
  colors: Colors;
  errColors: Colors;
  /** Terminal width for tables; Infinity when not a terminal. */
  width: number;
  locale: string | undefined;
}

// Intl puts a no-break space between a currency code and the number.
const NBSP = new RegExp(String.fromCharCode(0xa0), 'g');

function isRawJson(value: unknown): boolean {
  const check = (JSON as unknown as { isRawJSON?: (v: unknown) => boolean }).isRawJSON;
  return typeof check === 'function' && check(value);
}

function csvCell(value: unknown): string {
  let text: string;
  if (value === null || value === undefined) text = '';
  else if (typeof value === 'string') text = value;
  else if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') text = String(value);
  else if (isRawJson(value)) text = JSON.stringify(value);
  else text = JSON.stringify(value);
  return /[",\r\n]/.test(text) || /^\s|\s$/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** Records as CSV: one column per field, in the order fields first appear. */
export function toCsv(records: unknown[]): string {
  const rows = records.map((r) =>
    typeof r === 'object' && r !== null && !Array.isArray(r) ? (r as Record<string, unknown>) : { value: r },
  );
  const fields: string[] = [];
  for (const row of rows) for (const key of Object.keys(row)) if (!fields.includes(key)) fields.push(key);
  const lines = [fields.map(csvCell).join(',')];
  for (const row of rows) lines.push(fields.map((f) => csvCell(row[f])).join(','));
  return `${lines.join('\r\n')}\r\n`;
}

export class Output {
  readonly format: OutputFormat;
  readonly colors: Colors;
  readonly errColors: Colors;
  readonly width: number;
  readonly locale: string | undefined;
  private readonly runtime: Runtime;

  constructor(runtime: Runtime, settings: OutputSettings) {
    this.runtime = runtime;
    this.format = settings.format;
    this.colors = settings.colors;
    this.errColors = settings.errColors;
    this.width = settings.width;
    this.locale = settings.locale;
  }

  /** json, ndjson or csv: no tables, no decoration on stdout. */
  get machine(): boolean {
    return this.format !== 'table';
  }

  /** json or ndjson. */
  get json(): boolean {
    return this.format === 'json' || this.format === 'ndjson';
  }

  /** Writes a line to stdout. */
  line(text = ''): void {
    this.runtime.stdout.write(`${text}\n`);
  }

  /** Writes text to stdout as it is (no newline). */
  write(text: string): void {
    this.runtime.stdout.write(text);
  }

  /** Writes a line to stderr. */
  errLine(text = ''): void {
    this.runtime.stderr.write(`${text}\n`);
  }

  info(message: string): void {
    this.errLine(message);
  }

  success(message: string): void {
    this.errLine(`${this.errColors.green('✓')} ${message}`);
  }

  warn(message: string): void {
    this.errLine(`${this.errColors.yellow('!')} ${message}`);
  }

  /** A quieter line on stderr: empty states, tips. */
  note(message: string): void {
    this.errLine(this.errColors.dim(message));
  }

  /** Prints a command's result in the chosen format. */
  emit<T>(data: T, view: View<T>): void {
    switch (this.format) {
      case 'json':
        this.line(toJsonText(data));
        return;
      case 'ndjson': {
        // Records are taken from the exact parse, so their numbers keep their text too.
        const source = exactValue(data) as T;
        const records = view.records ? view.records(source) : source;
        if (Array.isArray(records)) for (const record of records) this.line(JSON.stringify(record));
        else this.line(JSON.stringify(records));
        return;
      }
      case 'csv': {
        const records = view.records ? view.records(data) : data;
        this.write(toCsv(Array.isArray(records) ? records : [records]));
        return;
      }
      case 'table':
        view.human(data);
        return;
    }
  }

  /** Prints a result that is only a confirmation: JSON in machine formats, a line for people. */
  done(data: Record<string, unknown>, message: string): void {
    if (this.machine) this.emit(data, { human: () => undefined });
    else this.success(message);
  }

  table<T>(rows: readonly T[], columns: readonly Column<T>[]): string {
    return renderTable(rows, columns, { width: this.width, colors: this.colors });
  }

  details(rows: ReadonlyArray<DetailRow | false | undefined | null>): string {
    return renderDetails(rows, this.colors);
  }

  /** A heading for a section of human output. */
  heading(text: string): string {
    return this.colors.bold(sanitize(text));
  }

  /** An amount with its currency code: `USD 1,234.50`. */
  money(amount: unknown, currency: unknown, options: Omit<FormatAmountOptions, 'locale'> = {}): string {
    if (amount === null || amount === undefined || amount === '') return '—';
    const code = typeof currency === 'string' && currency ? currency : 'XXX';
    const text = formatAmount(amount as string, code, { locale: this.locale, ...options });
    return text.replace(NBSP, ' ');
  }

  /** An amount without its code, for a column already labelled with one. */
  amount(amount: unknown, currency: unknown): string {
    return this.money(amount, currency, { display: 'none' });
  }

  /** Colours an amount red when negative (for people only). */
  signed(text: string, amount: unknown): string {
    return typeof amount === 'string' && /^-/.test(amount.trim()) && !/^-0*(\.0*)?$/.test(amount.trim())
      ? this.colors.red(text)
      : text;
  }

  /** A fraction as a percentage: "0.185" → "18.5%". */
  percent(fraction: unknown, maximumFractionDigits = 1): string {
    if (fraction === null || fraction === undefined || fraction === '') return '—';
    return formatRatio(fraction as string, { locale: this.locale, maximumFractionDigits });
  }
}
