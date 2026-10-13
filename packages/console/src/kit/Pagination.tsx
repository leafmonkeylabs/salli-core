/**
 * Pages of a long list (C5): what is shown of how many, how many rows a
 * page holds, and the page before and after. It counts rows, never money.
 */
import { useEffect, useId, useState } from 'react';
import { strings } from '../strings';
import { Icon } from './Icon';

const SIZES = [15, 25, 50] as const;

export interface Paged<T> {
  /** The rows on this page. */
  shown: T[];
  page: number;
  pages: number;
  per: number;
  total: number;
  setPage: (page: number) => void;
  setPer: (per: number) => void;
}

/** Splits `rows` into pages; a new list (new filters) starts at the first. */
export function usePages<T>(rows: readonly T[], first: number = SIZES[0]): Paged<T> {
  const [per, setPer] = useState(first);
  const [page, setPage] = useState(1);
  const total = rows.length;
  const pages = Math.max(1, Math.ceil(total / per));
  useEffect(() => setPage(1), [rows, per]);
  const current = Math.min(page, pages);
  const start = (current - 1) * per;
  return { shown: rows.slice(start, start + per), page: current, pages, per, total, setPage, setPer };
}

export function Pagination<T>({ paged, noun }: { paged: Paged<T>; noun: (n: number) => string }) {
  const id = useId();
  const { page, pages, per, total } = paged;
  const start = (page - 1) * per;
  return (
    <div className="pager">
      <p className="muted pager-count" role="status">
        {total ? strings.pager.showing(start + 1, Math.min(start + per, total), noun(total)) : noun(0)}
      </p>
      <div className="pager-controls">
        <label htmlFor={id} className="muted">
          {strings.pager.rows}
        </label>
        <select
          id={id}
          className="pager-select"
          value={String(per)}
          onChange={(event) => paged.setPer(SIZES.find((size) => String(size) === event.target.value) ?? SIZES[0])}
        >
          {SIZES.map((size) => (
            <option key={size} value={String(size)}>
              {size}
            </option>
          ))}
        </select>
        <span className="muted pager-page">{strings.pager.page(page, pages)}</span>
        <button type="button" className="icon-button icon-button-small" aria-label={strings.pager.previous} disabled={page <= 1} onClick={() => paged.setPage(page - 1)}>
          <Icon name="left" small />
        </button>
        <button type="button" className="icon-button icon-button-small" aria-label={strings.pager.next} disabled={page >= pages} onClick={() => paged.setPage(page + 1)}>
          <Icon name="right" small />
        </button>
      </div>
    </div>
  );
}
