/**
 * Page layout from the brand's components (docs/brand/README.md, "Layout and
 * components"): a header card with one h1 per page, sections as paper
 * cards with hairline borders and a small outlined square before a tracked
 * capital label, and figures with their provenance beside them.
 */
import type { UseQueryResult } from '@tanstack/react-query';
import { useRouterState } from '@tanstack/react-router';
import { useEffect, useId, type ReactNode } from 'react';
import { useShellPage } from '../shell/context';
import { appPath, placeOf, type Crumb } from '../shell/places';
import { strings } from '../strings';
import { Icon, type IconName } from './Icon';
import { ProblemView } from './Problem';

export interface PageProps {
  title: string;
  description?: string | undefined;
  /** The page's actions: buttons and links, the primary one last. */
  actions?: ReactNode;
  /** Facts beside the title, as chips: a currency, a count, what the server checked. */
  facts?: ReactNode;
  /** The tile's picture; the place's own by default. */
  icon?: IconName;
  /** Crumbs between the page's place and it (a rule set, above its version). */
  trail?: readonly Crumb[];
  children: ReactNode;
}

/**
 * A page: its header card (the place's tile, the one h1, facts as chips,
 * what it is, its actions), then its content. It tells the shell its
 * title for the breadcrumb.
 */
export function Page({ title, description, actions, facts, icon, trail, children }: PageProps) {
  const shell = useShellPage();
  const path = appPath(useRouterState({ select: (state) => state.location.pathname }));
  const trailKey = JSON.stringify(trail ?? []);
  useEffect(() => {
    document.title = `${title} · ${strings.product}`;
    shell.report(title, JSON.parse(trailKey) as Crumb[]);
  }, [title, trailKey, shell]);
  const tile = icon ?? placeOf(path, shell.places)?.icon ?? 'page';
  return (
    <div className="page">
      <header className="page-header">
        <span className="page-tile" aria-hidden="true">
          <Icon name={tile} />
        </span>
        <div className="page-heading">
          <h1>{title}</h1>
          {facts ? <div className="page-facts">{facts}</div> : null}
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
  aside,
}: {
  /** Beside the label, at the card's far end: a range, a readout. */
  aside?: ReactNode;
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
      {aside ? (
        <div className="card-head">
          <h2 id={id} className="section-label">
            {label}
          </h2>
          {aside}
        </div>
      ) : (
        <h2 id={id} className="section-label">
          {label}
        </h2>
      )}
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

/**
 * Shown while a section loads: what is loading, in words ("Loading net
 * worth…"), over its shape, without a shimmer.
 */
export function Loading({ lines = 3, what }: { lines?: number; what?: string | undefined }) {
  return (
    <div className="loading" role="status">
      <p className="loading-what">{what ? strings.loadingWhat(what) : strings.loading}</p>
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

/** A word in place of a figure the server didn't give ("None", "Not sent"), in the muted colour. */
export function Blank({ children }: { children: ReactNode }) {
  return <span className="muted">{children}</span>;
}

/** A read's section: its shape while it loads, its problem with a retry, or its content. */
export function Loaded<T>({
  query,
  children,
  lines,
  what,
}: {
  query: UseQueryResult<T, Error>;
  children: (data: T) => ReactNode;
  lines?: number;
  /** What is loading, in words: "net worth". */
  what?: string;
}) {
  if (query.isPending) return <Loading {...(lines ? { lines } : {})} what={what} />;
  if (query.isError) return <ProblemView error={query.error} compact onRetry={() => void query.refetch()} />;
  return <>{children(query.data)}</>;
}
