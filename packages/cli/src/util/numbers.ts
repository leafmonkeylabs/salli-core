/**
 * Whole numbers that are not money: date parts, counts, ports, widths.
 * Amounts never come through here; they stay decimal strings.
 */

/** The integer a string of digits spells, or undefined if it is not one. */
export function parseWholeNumber(text: string | undefined): number | undefined {
  if (text === undefined || !/^\d{1,15}$/.test(text.trim())) return undefined;
  // eslint-disable-next-line no-restricted-syntax -- not money: a count, a date part, a port
  return Number.parseInt(text.trim(), 10);
}

/** Like parseWholeNumber, for text already known to be digits. */
export function digits(text: string | undefined): number {
  return parseWholeNumber(text) ?? Number.NaN;
}
