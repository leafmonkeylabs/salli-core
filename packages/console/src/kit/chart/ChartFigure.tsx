/**
 * A chart, as the design draws them (docs/design/console.md, section 4,
 * "Charts"): a <figure> whose caption says what it shows and its key
 * figure, an SVG with role="img" and a label, and **Show the figures**, the
 * same data as a table: the table is the accessible way in (made when it is
 * opened, so a year of days costs nothing until asked for). Hand-drawn SVG
 * from the tokens, 1.5 px lines, hairline gridlines, no animation into
 * place: a line is exact from its first frame.
 */
import { useId, useState, type ReactNode } from 'react';
import { strings } from '../../strings';

export function ChartFigure({
  caption,
  children,
  figures,
}: {
  /** What it shows and its key figure, as a sentence. */
  caption: ReactNode;
  /** The <svg role="img" aria-label=…> (or two: one wide, one for phones). */
  children: ReactNode;
  /** The same data as a table. */
  figures: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <figure className="chart">
      <div className="chart-plot">
        {children}
      </div>
      <figcaption>
        <span>{caption}</span>{' '}
        <button type="button" className="button-link" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
          {open ? strings.chart.hideFigures : strings.chart.showFigures}
        </button>
      </figcaption>
      <div id={id} hidden={!open}>
        {open ? figures : null}
      </div>
    </figure>
  );
}
