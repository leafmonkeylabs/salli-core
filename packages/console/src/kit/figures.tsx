/**
 * Key figures (C5): a row of cards, each a figure with its label and a
 * line or two of what it is and where it came from. Every figure is the
 * server's, shown exactly; a card computes nothing.
 */
import { useId, type ReactNode } from 'react';

export function KeyFigures({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <div className="figures" {...(label ? { role: 'group', 'aria-label': label } : {})}>
      {children}
    </div>
  );
}

/**
 * One key figure: a labelled group holding the figure, then its notes. A
 * group, not a region: a page's sections are its landmarks, and a figure
 * often shares its name with the section that details it.
 */
export function KeyFigure({ label, children, note }: { label: string; children: ReactNode; note?: ReactNode }) {
  const id = useId();
  return (
    <div className="figure-card" role="group" aria-labelledby={id}>
      <h2 id={id} className="section-label">
        {label}
      </h2>
      <div className="figure-value">{children}</div>
      {note ? <div className="figure-card-note">{note}</div> : null}
    </div>
  );
}

/**
 * A row of the segmented control's buttons (a chart's range): one pressed
 * at a time, each a button with `aria-pressed`.
 */
export function Segmented<T extends string>({ label, options, value, onChange }: { label: string; options: ReadonlyArray<{ value: T; label: string }>; value: T; onChange: (value: T) => void }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button key={option.value} type="button" aria-pressed={option.value === value} onClick={() => onChange(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  );
}
