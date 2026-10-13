/**
 * The console's icons (brand README, "Icons"): a 24 px grid, 1.5 px
 * strokes, square caps and joins, geometric. Each is decoration beside
 * words, or the picture on a button whose name says what it does, so each
 * is hidden from screen readers.
 */
import type { ReactElement } from 'react';

const PATHS = {
  home: <path d="M4 11 12 4l8 7v9h-5v-6H9v6H4z" />,
  cash: (
    <>
      <rect x="3" y="7" width="18" height="10" />
      <path d="M12 9.5v5M9.5 12h5" />
    </>
  ),
  books: (
    <>
      <rect x="4" y="4" width="16" height="16" />
      <path d="M4 9h16M4 14h16M10 4v16" />
    </>
  ),
  decide: <path d="M12 4v16M8 20h8M5 8h14M5 8l-2.5 6h5zM19 8l-2.5 6h5z" />,
  tax: <path d="M6 3h9l3 3v15H6zM9 16l6-6M9 10h1.5M13.5 16H15" />,
  attention: <path d="M6 16v-5a6 6 0 0 1 12 0v5l2 2H4zM10 21h4" />,
  independence: <path d="M4 18l6-6 4 4 6-8M15 8h5v5" />,
  settings: (
    <>
      <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
      <rect x="14" y="5" width="4" height="4" />
      <rect x="8" y="15" width="4" height="4" />
    </>
  ),
  more: <path d="M4 7h16M4 12h16M4 17h16" />,
  page: <rect x="5" y="4" width="14" height="16" />,
  account: <path d="M3 9 12 4l9 5M5 9v9M10 9v9M14 9v9M19 9v9M3 20h18" />,
  entries: <path d="M4 6h16M4 12h16M4 18h10" />,
  plus: <path d="M12 5v14M5 12h14" />,
  upload: <path d="M12 16V5M7 10l5-5 5 5M5 20h14" />,
  download: <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />,
  filter: <path d="M4 6h16M7 12h10M10 18h4" />,
  columns: (
    <>
      <rect x="4" y="5" width="16" height="14" />
      <path d="M10 5v14M15 5v14" />
    </>
  ),
  search: <path d="M16 16l4 4M17 11a6 6 0 1 1-12 0 6 6 0 0 1 12 0z" />,
  eye: <path d="M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12zM14.5 12a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  right: <path d="M9 6l6 6-6 6" />,
  left: <path d="M15 6l-6 6 6 6" />,
  down: <path d="M6 9l6 6 6-6" />,
  back: <path d="M19 12H5M11 6l-6 6 6 6" />,
  sidebar: (
    <>
      <rect x="3" y="4" width="18" height="16" />
      <path d="M9 4v16" />
    </>
  ),
  sun: <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z" />,
  moon: <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" />,
  check: <path d="M5 12l5 5 9-10" />,
  sort: <path d="M8 5v14M4 15l4 4 4-4M16 19V5M12 9l4-4 4 4" />,
  reverse: <path d="M9 6 4 11l5 5M4 11h11a5 5 0 0 1 0 10h-3" />,
  copy: <path d="M8 8h12v12H8zM4 16V4h12" />,
} satisfies Record<string, ReactElement>;

export type IconName = keyof typeof PATHS;

export function Icon({ name, small }: { name: IconName; small?: boolean }) {
  return (
    <svg className={small ? 'icon icon-small' : 'icon'} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {PATHS[name]}
    </svg>
  );
}
