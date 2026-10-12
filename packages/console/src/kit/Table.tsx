/**
 * A table in the brand's style: hairline row rules, no zebra stripes, a
 * sticky header in the label style, figures right-aligned in tabular
 * figures, a total with a hairline above and a double rule below. On a phone
 * each row becomes a short list that keeps its figures right-aligned (each
 * cell carries its column's header as `data-label`).
 */
import type { ReactNode } from 'react';

export interface Column<T> {
  key: string;
  header: ReactNode;
  /** The header as text, for the phone layout's labels. */
  label: string;
  /** `end` for figures. */
  align?: 'start' | 'end';
  render: (row: T) => ReactNode;
}

export interface TableProps<T> {
  caption: ReactNode;
  /** Hide the caption visually (a section label already names the table). */
  captionHidden?: boolean;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  /** The row of totals, if any. */
  total?: { label: ReactNode; cells: Record<string, ReactNode> };
}

export function Table<T>({ caption, captionHidden, columns, rows, rowKey, total }: TableProps<T>) {
  return (
    <div className="table-wrap">
      <table className="table">
        <caption className={captionHidden ? 'sr-only' : undefined}>{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={column.align === 'end' ? 'num' : undefined}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column, i) =>
                i === 0 ? (
                  <th key={column.key} scope="row" data-label={column.label}>
                    {column.render(row)}
                  </th>
                ) : (
                  <td key={column.key} data-label={column.label} className={column.align === 'end' ? 'num' : undefined}>
                    {column.render(row)}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
        {total ? (
          <tfoot>
            <tr className="total">
              <th scope="row">{total.label}</th>
              {columns.slice(1).map((column) => (
                <td key={column.key} data-label={column.label} className={column.align === 'end' ? 'num' : undefined}>
                  {total.cells[column.key] ?? null}
                </td>
              ))}
            </tr>
          </tfoot>
        ) : null}
      </table>
    </div>
  );
}
