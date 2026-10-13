/**
 * A horizontal bar beside a figure (C5): where the figure sits on a scale
 * the caller made with `amountScale` (the geometry module, the one place an
 * amount becomes a number, and only for pixels). Decoration beside the
 * figure, which is always shown in words: hidden from screen readers.
 */
export function Bar({ length, alt }: { /** 0 to 100: the share of the track it fills. */ length: number; alt?: boolean }) {
  const fill = Math.max(0, Math.min(100, length));
  return (
    <svg className="bar" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <rect className="bar-track" x="0" y="0" width="100" height="10" />
      {fill > 0 ? <rect className={alt ? 'bar-fill bar-fill-2' : 'bar-fill'} x="0" y="0" width={fill.toFixed(2)} height="10" /> : null}
    </svg>
  );
}
