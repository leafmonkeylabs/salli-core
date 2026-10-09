/**
 * Showing one record (a budget, a debt, a policy): every field, labelled,
 * with amounts formatted in the record's currency and fractions as
 * percentages. For the many `show` commands that print what the API sends.
 */
import type { App } from '../app';
import { singleLine, truncate } from '../output/text';
import { displayDate } from '../util/dates';

const HIDDEN = new Set(['currency', 'user_id', 'inputs_hash']);

/** "next_due_date" → "Next due date". */
export function fieldLabel(key: string): string {
  const text = key
    .replace(/_/g, ' ')
    .replace(/\bpct\b/, '%')
    .replace(/\b(id|mcp|ird|fi|apr|swr|llm)\b/gi, (word) => word.toUpperCase());
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export interface RecordFormat {
  /** Fields that are amounts in the record's `currency`. */
  money?: readonly string[];
  /** Fields that are fractions, shown as percentages. */
  ratios?: readonly string[];
  /** Fields that are dates. */
  dates?: readonly string[];
  /** Fields to leave out. */
  hide?: readonly string[];
}

function scalar(value: unknown): string | undefined {
  if (value === null || value === undefined || value === '') return undefined;
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return truncate(singleLine(JSON.stringify(value)), 100);
}

/** The details view of one API record. */
export function renderRecord(app: App, record: Record<string, unknown>, format: RecordFormat = {}): string {
  const currency = typeof record.currency === 'string' ? record.currency : undefined;
  const rows = Object.entries(record)
    .filter(([key]) => !HIDDEN.has(key) && !format.hide?.includes(key))
    .map(([key, value]): readonly [string, string | undefined] => {
      if (format.money?.includes(key) && currency) return [fieldLabel(key), value === null ? undefined : app.out.money(value, currency)];
      if (format.ratios?.includes(key)) return [fieldLabel(key), value === null ? undefined : app.out.percent(value)];
      if (format.dates?.includes(key) || key.endsWith('_date') || key.endsWith('_at')) {
        return [fieldLabel(key), typeof value === 'string' ? displayDate(value, app.out.locale) : scalar(value)];
      }
      return [fieldLabel(key), scalar(value)];
    });
  return app.out.details(rows);
}
