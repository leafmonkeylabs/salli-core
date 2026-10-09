/**
 * Tables and detail views for people.
 *
 * Borderless, like `gh` and `kubectl`: a header row, columns two spaces
 * apart, amounts right-aligned. In a terminal the widest text columns shrink
 * (ending in …) to fit; piped, nothing is cut.
 */
import type { Colors } from './colors';
import { displayWidth, padEnd, padStart, singleLine, truncate } from './text';

export interface Column<T> {
  header: string;
  /** The cell's text. Sanitised and kept to one line. */
  get: (row: T) => string | number | null | undefined;
  align?: 'left' | 'right';
  /** May be cut with … when the table is wider than the terminal. */
  shrink?: boolean;
  /** Colours the cell after it is cut and padded. */
  style?: (cell: string, row: T) => string;
}

export interface TableOptions {
  /** Terminal width; Infinity for no limit. */
  width: number;
  colors: Colors;
}

const GAP = '  ';
const MIN_SHRINK = 8;

export function renderTable<T>(rows: readonly T[], columns: readonly Column<T>[], options: TableOptions): string {
  const visible = columns;
  const cells = rows.map((row) =>
    visible.map((column) => {
      const value = column.get(row);
      return value === null || value === undefined ? '' : singleLine(String(value));
    }),
  );
  const widths = visible.map((column, i) =>
    Math.max(displayWidth(column.header), ...cells.map((row) => displayWidth(row[i] ?? ''))),
  );

  // Shrink the widest shrinkable column, a column at a time, until it fits.
  const total = (): number => widths.reduce((sum, w) => sum + w, 0) + GAP.length * (widths.length - 1);
  if (Number.isFinite(options.width)) {
    let overflow = total() - options.width;
    while (overflow > 0) {
      let widest = -1;
      visible.forEach((column, i) => {
        const floor = Math.max(MIN_SHRINK, displayWidth(column.header));
        if (column.shrink && (widths[i] ?? 0) > floor && (widest === -1 || (widths[i] ?? 0) > (widths[widest] ?? 0))) {
          widest = i;
        }
      });
      if (widest === -1) break;
      widths[widest] = (widths[widest] ?? 0) - 1;
      overflow -= 1;
    }
  }

  const last = visible.length - 1;
  const line = (texts: string[], styleRow?: (text: string, i: number) => string): string =>
    texts
      .map((text, i) => {
        const width = widths[i] ?? 0;
        const cut = truncate(text, width);
        const aligned =
          visible[i]?.align === 'right' ? padStart(cut, width) : i === last ? cut : padEnd(cut, width);
        return styleRow ? styleRow(aligned, i) : aligned;
      })
      .join(GAP)
      .trimEnd();

  const header = line(
    visible.map((c) => c.header),
    (text) => options.colors.bold(text),
  );
  const body = cells.map((texts, r) =>
    line(texts, (text, i) => {
      const style = visible[i]?.style;
      const row = rows[r];
      return style && row !== undefined && text.trim() !== '' ? style(text, row) : text;
    }),
  );
  return [header, ...body].join('\n');
}

export type DetailRow = readonly [label: string, value: string | number | null | undefined];

/** Label/value lines, labels aligned. Rows with no value are left out. */
export function renderDetails(rows: ReadonlyArray<DetailRow | false | undefined | null>, colors: Colors): string {
  const shown = rows.filter(
    (row): row is DetailRow => !!row && row[1] !== undefined && row[1] !== null && row[1] !== '',
  );
  const width = Math.max(0, ...shown.map(([label]) => displayWidth(label)));
  return shown
    .map(([label, value]) => `${colors.dim(padEnd(label, width))}  ${String(value)}`)
    .join('\n');
}
