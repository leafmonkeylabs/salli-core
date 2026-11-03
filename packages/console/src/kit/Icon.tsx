/**
 * The console's icons (brand README, "Icons"): a 24 px grid, 1.75 px
 * strokes, round caps and joins, inner corners 2.5 to 3.5. Each is decoration beside
 * words, or the picture on a button whose name says what it does, so each
 * is hidden from screen readers.
 */
import type { ReactElement } from 'react';

const PATHS = {
  home: <path d="M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5.5h-5V20H5a1 1 0 0 1-1-1z" />,
  cash: (
    <>
      <rect x="3" y="6.5" width="18" height="11" rx="3" />
      <path d="M12 9.5v5M9.5 12h5" />
    </>
  ),
  books: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="3.5" />
      <path d="M4 9.5h16M4 14.5h16M10 4v16" />
    </>
  ),
  decide: <path d="M12 4v15M8.5 19.5h7M5.5 7.5h13M5.5 7.5 3 13a2.5 2.5 0 0 0 5 0zM18.5 7.5 16 13a2.5 2.5 0 0 0 5 0z" />,
  tax: <path d="M7 3.5h7l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V5A1.5 1.5 0 0 1 7 3.5zM9.5 16l5-5M9.5 11h.01M14.5 16h.01" />,
  attention: <path d="M6.5 15.5V11a5.5 5.5 0 0 1 11 0v4.5l1.5 2H5zM10 20.5h4" />,
  independence: <path d="m4 17.5 5.5-5.5 4 4 6.5-7.5M15 8.5h5v5" />,
  settings: (
    <>
      <path d="M5 7h9M18 7h1M5 17h3M12 17h7" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="10" cy="17" r="2" />
    </>
  ),
  more: <path d="M5 7h14M5 12h14M5 17h14" />,
  page: <path d="M7 3.5h7l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V5A1.5 1.5 0 0 1 7 3.5zM9.5 12.5h5M9.5 16h3.5" />,
  account: <path d="m3 9.5 9-5 9 5M5.5 10v8M10 10v8M14 10v8M18.5 10v8M3.5 20h17" />,
  entries: <path d="M5 6.5h14M5 12h14M5 17.5h9" />,
  plus: <path d="M12 5v14M5 12h14" />,
  upload: <path d="M12 15.5V5M7.5 9.5 12 5l4.5 4.5M5 19h14" />,
  download: <path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14" />,
  filter: <path d="M4.5 6.5h15M7.5 12h9M10.5 17.5h3" />,
  columns: (
    <>
      <rect x="4" y="5" width="16" height="14" rx="3" />
      <path d="M9.5 5v14M14.5 5v14" />
    </>
  ),
  search: <path d="m16.5 16.5 3.5 3.5M17 11a6 6 0 1 1-12 0 6 6 0 0 1 12 0z" />,
  eye: <path d="M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6zM14.5 12a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z" />,
  close: <path d="m6.5 6.5 11 11M17.5 6.5l-11 11" />,
  right: <path d="m9.5 6 6 6-6 6" />,
  left: <path d="m14.5 6-6 6 6 6" />,
  down: <path d="m7 10 5 5 5-5" />,
  back: <path d="M19 12H5M11 6l-6 6 6 6" />,
  sidebar: (
    <>
      <rect x="3.5" y="4.5" width="17" height="15" rx="3.5" />
      <path d="M9.5 4.5v15" />
    </>
  ),
  sun: <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z" />,
  moon: <path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z" />,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  sort: <path d="M8 5v14M4.5 15.5 8 19l3.5-3.5M16 19V5M12.5 8.5 16 5l3.5 3.5" />,
  reverse: <path d="M9 6 4 11l5 5M4 11h11a5 5 0 0 1 0 10h-3" />,
  copy: (
    <>
      <rect x="8" y="8" width="12" height="12" rx="3" />
      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
    </>
  ),
} satisfies Record<string, ReactElement>;

export type IconName = keyof typeof PATHS;

export function Icon({ name, small }: { name: IconName; small?: boolean }) {
  return (
    <svg className={small ? 'icon icon-small' : 'icon'} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {PATHS[name]}
    </svg>
  );
}
