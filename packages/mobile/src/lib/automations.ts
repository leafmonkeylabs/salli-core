/**
 * Matching rules for automations (docs/design/mobile.md, "Automations"): a
 * bank's message, handed over by a Shortcuts automation or pasted, becomes a
 * draft for review when one of the person's rules reads it. The rules and the
 * messages stay on the phone; only what a rule picks out is sent. Amounts are
 * kept as written, tidied into a decimal string, never computed with.
 */

export type DateOrder = 'DMY' | 'MDY' | 'YMD';

export interface AutomationRule {
  id: string;
  /** What the person calls it: "Card spend". */
  name: string;
  /** Who sends the messages, as the automation names them: "EXAMPLEBANK", "alerts@bank.example". */
  senders: string[];
  /** A template ("debited {amount} at {payee}") or, under Advanced, a regular expression with named groups. */
  pattern: string;
  kind: 'template' | 'regex';
  /** Which way the money goes in every message the rule reads. */
  direction: 'out' | 'in';
  /** The bank or card account the transactions are on. */
  accountId: string;
  /** How the messages write dates such as 05/10/26. */
  dateOrder: DateOrder;
  /** The amounts' decimal mark: "1,245.50" or "1.245,50". */
  decimalMark: '.' | ',';
}

/** What a rule picked out of a message: the draft the server is sent. */
export interface Draft {
  date: string;
  description: string;
  /** A decimal string, as written in the message. */
  amount: string;
  credit_flag: boolean;
  bank_ref?: string;
}

export type Reading =
  | { kind: 'draft'; rule: AutomationRule; draft: Draft }
  /** From a watched sender, but no rule's pattern fits: it waits on the phone. */
  | { kind: 'unread'; rules: AutomationRule[] }
  /** Nobody's rule watches the sender: dropped at once. */
  | { kind: 'ignored' };

export const PLACEHOLDERS = ['amount', 'payee', 'date', 'ref', 'skip'] as const;

const PIECES: Record<(typeof PLACEHOLDERS)[number], string> = {
  // Digits with the separators banks group them by; tidied later.
  amount: "(?<amount>\\d(?:[\\d.,'\\u00a0\\u202f ]*\\d)?)",
  payee: '(?<payee>.+?)',
  date: '(?<date>\\d{1,4}[-/.]\\d{1,2}[-/.]\\d{1,4}|\\d{1,2}[- ]?[A-Za-z]{3,9}[- ,]*\\d{2,4}|[A-Za-z]{3,9}\\.? \\d{1,2},? \\d{4})',
  ref: '(?<ref>[A-Za-z0-9][A-Za-z0-9/_-]*)',
  skip: '.*?',
};

/** A template as a regular expression: its words as written, its {parts} as groups. */
export function templateSource(template: string): string {
  const parts = template.trim().split(/(\{[a-z]+\})/);
  let source = '';
  parts.forEach((part, i) => {
    const name = /^\{([a-z]+)\}$/.exec(part)?.[1];
    if (name && name in PIECES) {
      source += PIECES[name as keyof typeof PIECES];
      // A part at the end runs to the sentence's end, not one character.
      if (i === parts.length - 2 && parts[parts.length - 1] === '') source += '(?=\\.?\\s*$|\\.\\s|\\n)';
      return;
    }
    source += part
      .split(/\s+/)
      .map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
      .join('\\s+');
  });
  return source;
}

/** The rule's pattern as a regular expression, or why it isn't one. */
export function patternOf(rule: Pick<AutomationRule, 'pattern' | 'kind'>): RegExp | string {
  if (!rule.pattern.trim()) return 'Write the pattern.';
  try {
    const source = rule.kind === 'template' ? templateSource(rule.pattern) : rule.pattern;
    const pattern = new RegExp(source, 'i');
    if (!/\(\?<amount>/.test(source)) return rule.kind === 'template' ? 'Mark the amount: {amount}.' : 'Name a group amount: (?<amount>…).';
    return pattern;
  } catch {
    return 'This regular expression doesn’t read.';
  }
}

/** An amount as written ("1,23,455.00", "1.245,50", "8 400") as a decimal string, or undefined. */
export function amountOf(written: string, decimalMark: '.' | ','): string | undefined {
  // Grouping comes before the decimal mark, and there is one mark at most:
  // "1,245.50" read with a comma mark is refused, never read as 1.24550.
  const marks = written.split(decimalMark);
  if (marks.length > 2 || /[^0-9]/.test(marks[1] ?? '')) return undefined;
  const kept = written.replace(new RegExp(`[^0-9${decimalMark === ',' ? ',' : '.'}]`, 'g'), '');
  const text = decimalMark === ',' ? kept.replace(',', '.') : kept;
  return /^\d+(\.\d+)?$/.test(text) ? text.replace(/^0+(?=\d)/, '') : undefined;
}

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

/** A date as written in a message, as YYYY-MM-DD, or undefined when it isn't a real day. */
export function dateOf(written: string, order: DateOrder): string | undefined {
  const text = written.trim();
  let year: string | undefined;
  let month: string | undefined;
  let day: string | undefined;
  const numeric = /^(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})$/.exec(text);
  const named = /^(\d{1,2})[- ]?([A-Za-z]{3,9})[- ,]*(\d{2,4})$/.exec(text) ?? /^([A-Za-z]{3,9})\.? (\d{1,2}),? (\d{4})$/.exec(text);
  if (numeric) {
    const [, a = '', b = '', c = ''] = numeric;
    // Four digits first are a year, whatever the rule says.
    [year, month, day] = a.length === 4 || order === 'YMD' ? [a, b, c] : order === 'MDY' ? [c, a, b] : [c, b, a];
  } else if (named) {
    const [, a = '', b = '', c = ''] = named;
    const dayFirst = /^\d/.test(a);
    const name = (dayFirst ? b : a).slice(0, 3).toLowerCase();
    const index = MONTHS.indexOf(name);
    if (index < 0) return undefined;
    [year, month, day] = [c, String(index + 1), dayFirst ? a : b];
  } else {
    return undefined;
  }
  if (!year || !month || !day) return undefined;
  if (year.length === 2) year = `20${year}`;
  if (year.length !== 4) return undefined;
  const iso = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
  // A real day: one the calendar has, read back the same.
  const checked = new Date(`${iso}T00:00:00Z`);
  return !Number.isNaN(checked.getTime()) && checked.toISOString().startsWith(iso) ? iso : undefined;
}

function watches(rule: AutomationRule, sender: string): boolean {
  const who = sender.trim().toLowerCase();
  return rule.senders.some((s) => s.trim().toLowerCase() === who);
}

/** What one rule reads in a message: a draft, or why not. */
export function readWith(rule: AutomationRule, text: string, today: string): Draft | string {
  const pattern = patternOf(rule);
  if (typeof pattern === 'string') return pattern;
  const found = pattern.exec(text)?.groups;
  if (!found) return 'The pattern doesn’t fit this message.';
  const amount = found.amount ? amountOf(found.amount, rule.decimalMark) : undefined;
  if (!amount || /^0+(\.0+)?$/.test(amount)) return 'No amount read.';
  const date = found.date ? dateOf(found.date, rule.dateOrder) : today;
  if (!date) return `“${found.date ?? ''}” isn’t a date read as ${rule.dateOrder}.`;
  const payee = (found.payee ?? '').trim().replace(/\s+/g, ' ');
  return {
    date,
    description: payee || rule.name,
    amount,
    credit_flag: rule.direction === 'in',
    ...(found.ref ? { bank_ref: found.ref } : {}),
  };
}

/**
 * A message as the person's rules read it. With a `sender`, only the rules
 * watching it are tried, and a message from no one watched is ignored; a
 * message pasted by hand has none, and every rule is tried.
 */
export function read(rules: readonly AutomationRule[], message: { text: string; sender?: string }, today: string): Reading {
  const candidates = message.sender === undefined ? [...rules] : rules.filter((r) => watches(r, message.sender ?? ''));
  if (candidates.length === 0) return message.sender === undefined ? { kind: 'unread', rules: [] } : { kind: 'ignored' };
  for (const rule of candidates) {
    const draft = readWith(rule, message.text, today);
    if (typeof draft !== 'string') return { kind: 'draft', rule, draft };
  }
  return { kind: 'unread', rules: candidates };
}
