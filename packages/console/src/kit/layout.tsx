/**
 * Page layout from the brand's components (docs/brand/README.md, "Layout and
 * components"): one h1 per page, sections with a small outlined square
 * before a tracked capital label, bone panels with hairline borders, and
 * figures with their provenance beside them.
 */
import type { UseQueryResult } from '@tanstack/react-query';
import { useEffect, useId, type ReactNode } from 'react';
import { strings } from '../strings';
import { ProblemView } from './Problem';

export function Page({ title, description, actions, children }: { title: string; description?: string; actions?: ReactNode; children: ReactNode }) {
  useEffect(() => {
    document.title = `${title} · ${strings.product}`;
  }, [title]);
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{title}</h1>
          {description ? <p className="page-description">{description}</p> : null}
        </div>
        {actions ? <div className="page-actions">{actions}</div> : null}
      </header>
      {children}
    </div>
  );
}

/**
 * A section of a page: a labelled region with the brand's section label.
 * `anchor` lets another page link straight to it (`/cash#forecast`).
 */
export function Section({
  label,
  children,
  className,
  wide,
  full,
  anchor,
}: {
  label: string;
  children: ReactNode;
  className?: string;
  wide?: boolean;
  full?: boolean;
  anchor?: string;
}) {
  const id = useId();
  return (
    <section id={anchor} aria-labelledby={id} className={['section', wide ? 'section-wide' : '', full ? 'section-full' : '', className ?? ''].filter(Boolean).join(' ')}>
      <h2 id={id} className="section-label">
        {label}
      </h2>
      {children}
    </section>
  );
}

/** A bone panel with a hairline border. */
export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={['panel', className ?? ''].filter(Boolean).join(' ')}>{children}</div>;
}

/** A grid of sections: 12 columns on a wide screen, one on a phone. */
export function Grid({ children }: { children: ReactNode }) {
  return <div className="grid">{children}</div>;
}

/** Where a figure came from: *as of*, *placeholder assumptions*, *computed by…*. */
export function Provenance({ children }: { children: ReactNode }) {
  return <p className="provenance">{children}</p>;
}

/** A label and a value on one row, the value right-aligned in tabular figures. */
export function Row({ label, children, total, indent }: { label: ReactNode; children: ReactNode; total?: boolean; indent?: boolean }) {
  return (
    <div className={['row', total ? 'row-total' : '', indent ? 'row-indent' : ''].filter(Boolean).join(' ')}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function Rows({ children }: { children: ReactNode }) {
  return <dl className="rows">{children}</dl>;
}

/** Shown while a section loads: its shape, without a shimmer. */
export function Loading({ lines = 3 }: { lines?: number }) {
  return (
    <div className="loading" role="status">
      <span className="sr-only">{strings.loading}</span>
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="loading-line" aria-hidden="true" />
      ))}
    </div>
  );
}

/** A quiet sentence for an empty section. */
export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

/** A read's section: its shape while it loads, its problem with a retry, or its content. */
export function Loaded<T>({ query, children, lines }: { query: UseQueryResult<T, Error>; children: (data: T) => ReactNode; lines?: number }) {
  if (query.isPending) return <Loading {...(lines ? { lines } : {})} />;
  if (query.isError) return <ProblemView error={query.error} compact onRetry={() => void query.refetch()} />;
  return <>{children(query.data)}</>;
}
