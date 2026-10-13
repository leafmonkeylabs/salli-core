/**
 * A side sheet (C5): one thing from a list, opened beside it (an entry
 * from the ledger). It is a complementary region, not a modal: its title
 * takes the focus when it opens, and Escape or Close shuts it, giving the
 * focus back to whatever opened it. On a narrower screen it sits under the
 * list instead of over it.
 */
import { useEffect, useId, useRef, type ReactNode } from 'react';
import { strings } from '../strings';
import { Icon } from './Icon';

export interface SheetProps {
  /** A small label above, in the brand's label style ("Entry"). */
  kicker: string;
  /** Beside the label (an id chip). */
  badge?: ReactNode;
  title: string;
  /** Under the title: when, from where, how it stands. */
  meta?: ReactNode;
  onClose: () => void;
  children: ReactNode;
}

export function Sheet({ kicker, badge, title, meta, onClose, children }: SheetProps) {
  const id = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus({ preventScroll: false });
  }, [title]);
  return (
    <aside
      className="sheet"
      aria-labelledby={id}
      onKeyDown={(event) => {
        // A confirmation's own Escape is the dialog's, not the sheet's.
        if (event.key === 'Escape' && !(event.target as Element).closest('dialog')) {
          event.stopPropagation();
          onClose();
        }
      }}
    >
      <div className="sheet-bar">
        <span className="section-label">{kicker}</span>
        {badge}
        <span className="sheet-gap" />
        <button type="button" className="icon-button icon-button-small" aria-label={strings.sheet.close} onClick={onClose}>
          <Icon name="close" small />
        </button>
      </div>
      <div className="sheet-head">
        <h2 id={id} ref={heading} tabIndex={-1} className="sheet-title">
          {title}
        </h2>
        {meta ? <div className="sheet-meta">{meta}</div> : null}
      </div>
      <div className="sheet-body">{children}</div>
    </aside>
  );
}
