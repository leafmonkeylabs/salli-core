/**
 * A table in the brand's style: hairline row rules, no zebra stripes, a
 * sticky header in the label style on a bone well, figures right-aligned in tabular
 * figures, a total with a hairline above and a double rule below. On a phone
 * each row becomes a short list that keeps its figures right-aligned (each
 * cell carries its column's header as `data-label`).
 */
import { useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';

export interface Column<T> {
  key: string;
  header: ReactNode;
  /** The header as text, for the phone layout's labels. */
  label: string;
  /** `end` for figures. */
  align?: 'start' | 'end';
  /** Classes for its cells: `cell-tight` (as narrow as it can be), `cell-description`. */
  className?: string;
  /** How the rows are sorted by it, if they are (`aria-sort`). */
  sort?: 'ascending' | 'descending';
  render: (row: T) => ReactNode;
}

function cellClass<T>(column: Column<T>): string | undefined {
  return [column.align === 'end' ? 'num' : '', column.className ?? ''].filter(Boolean).join(' ') || undefined;
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
  /** The row that is open beside the table (shaded). */
  selected?: (row: T) => boolean;
}

/**
 * Whether a table is wider than its card, so it scrolls: then its wrapper
 * takes the focus, named by the caption, and the keyboard can scroll it.
 */
function useScrolls(): [React.RefObject<HTMLDivElement | null>, boolean] {
  const ref = useRef<HTMLDivElement>(null);
  const [scrolls, setScrolls] = useState(false);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const check = (): void => setScrolls(el.scrollWidth > el.clientWidth + 1);
    check();
    const observer = new ResizeObserver(check);
    observer.observe(el);
    if (el.firstElementChild) observer.observe(el.firstElementChild);
    return () => observer.disconnect();
  }, []);
  return [ref, scrolls];
}

export function Table<T>({ caption, captionHidden, columns, rows, rowKey, total, selected }: TableProps<T>) {
  const [wrap, scrolls] = useScrolls();
  const captionId = useId();
  return (
    <div ref={wrap} className="table-wrap" {...(scrolls ? { tabIndex: 0, role: 'group', 'aria-labelledby': captionId } : {})}>
      <table className="table">
        <caption id={captionId} className={captionHidden ? 'sr-only' : undefined}>
          {caption}
        </caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={cellClass(column)} {...(column.sort ? { 'aria-sort': column.sort } : {})}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className={selected?.(row) ? 'is-selected' : undefined}>
              {columns.map((column, i) =>
                i === 0 ? (
                  <th key={column.key} scope="row" data-label={column.label} className={cellClass(column)}>
                    {column.render(row)}
                  </th>
                ) : (
                  <td key={column.key} data-label={column.label} className={cellClass(column)}>
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
