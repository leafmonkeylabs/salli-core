/**
 * Rates as the server writes them (fractions, "0.04") and as a person reads
 * and types them (percentages, "4"), moved by two decimal places in the
 * digits themselves: no arithmetic, so nothing is rounded.
 */

/** "0.035" → "3.5"; "1" → "100". */
export function percentOf(fraction: string): string {
  const negative = fraction.startsWith('-');
  const [whole = '0', part = ''] = fraction.replace(/^-/, '').split('.');
  const digits = (whole + part.padEnd(2, '0')).replace(/^0+(?=\d)/, '');
  const at = digits.length - (part.length > 2 ? part.length - 2 : 0);
  const shown = part.length > 2 ? `${digits.slice(0, at)}.${digits.slice(at)}` : digits;
  return `${negative ? '-' : ''}${shown.replace(/^\./, '0.')}`;
}

/** "3.5" → "0.035"; undefined when it isn't a number. */
export function fractionOf(percent: string): string | undefined {
  const text = percent.trim().replace(/%$/, '').trim();
  if (!/^-?\d+(\.\d+)?$/.test(text)) return undefined;
  const negative = text.startsWith('-');
  const [whole = '0', part = ''] = text.replace(/^-/, '').split('.');
  const padded = whole.padStart(3, '0');
  const result = `${padded.slice(0, -2)}.${padded.slice(-2)}${part}`.replace(/^0+(?=\d)/, '').replace(/\.?0+$/, '');
  return `${negative ? '-' : ''}${result || '0'}`;
}
