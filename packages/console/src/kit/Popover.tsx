/**
 * A popover (C5): a button that shows a small panel beside it (the
 * filters, the columns, who is signed in). It is a disclosure, not a
 * modal: the panel takes the focus when it opens; Escape closes it and
 * gives the focus back to its button; a click outside it, or the focus
 * leaving it, closes it. Only React renders into it.
 */
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode, type Ref } from 'react';

export interface PopoverTriggerProps {
  ref: Ref<HTMLButtonElement>;
  type: 'button';
  'aria-expanded': boolean;
  'aria-controls': string;
  onClick: () => void;
}

export interface PopoverProps {
  /** The button, given the props that tie it to its panel. */
  trigger: (props: PopoverTriggerProps) => ReactNode;
  /** The panel's name. */
  label: string;
  /** `end` lines the panel up with the button's far edge. */
  align?: 'start' | 'end';
  role?: 'dialog' | 'group';
  className?: string;
  children: (close: () => void) => ReactNode;
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])';

export function Popover({ trigger, label, align = 'start', role = 'dialog', className, children }: PopoverProps) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);

  const close = useCallback((refocus = true) => {
    setOpen(false);
    if (refocus) button.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    const first = panel.current?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? panel.current)?.focus();
    const outside = (event: PointerEvent): void => {
      if (wrap.current && !wrap.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (event.key === 'Escape' && open) {
      event.stopPropagation();
      close();
    }
  };

  return (
    <div
      ref={wrap}
      className={['popover-wrap', className ?? ''].filter(Boolean).join(' ')}
      onKeyDown={onKeyDown}
      onBlur={(event) => {
        if (open && event.relatedTarget && wrap.current && !wrap.current.contains(event.relatedTarget as Node)) setOpen(false);
      }}
    >
      {trigger({ ref: button, type: 'button', 'aria-expanded': open, 'aria-controls': id, onClick: () => setOpen((was) => !was) })}
      <div ref={panel} id={id} role={role} aria-label={label} tabIndex={-1} className={`popover popover-${align}`} hidden={!open}>
        {open ? children(() => close()) : null}
      </div>
    </div>
  );
}
