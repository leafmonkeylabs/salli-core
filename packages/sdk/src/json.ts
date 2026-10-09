/**
 * The JSON a response arrived as.
 *
 * `SalliClient.call` keeps each JSON response's text alongside the parsed
 * value, so a client can print what the API sent rather than a re-encoding
 * of it: a float the server wrote as `0.0` stays `0.0`.
 */

/** Where the response text is kept on a parsed value (non-enumerable). */
export const RAW_JSON: unique symbol = Symbol.for('salli.rawJson') as never;

/** The JSON text a value was parsed from, when the SDK kept it. */
export function rawJsonOf(value: unknown): string | undefined {
  if (typeof value !== 'object' || value === null) return undefined;
  const raw = (value as { [RAW_JSON]?: unknown })[RAW_JSON];
  return typeof raw === 'string' ? raw : undefined;
}

/** Records the text `value` was parsed from. Returns `value`. */
export function withRawJson<T>(value: T, raw: string | undefined): T {
  if (raw !== undefined && typeof value === 'object' && value !== null && Object.isExtensible(value)) {
    Object.defineProperty(value, RAW_JSON, { value: raw, enumerable: false, configurable: true });
  }
  return value;
}

interface ReviverContext {
  source?: string;
}

type RawJsonFactory = (text: string) => unknown;

/**
 * Parses JSON keeping each number's source text (via `JSON.rawJSON`, where
 * the runtime has it), so encoding the result again writes `0.0` as `0.0`.
 * Without `JSON.rawJSON` this is plain `JSON.parse`.
 */
export function parseJsonExact(text: string): unknown {
  const rawJSON = (JSON as unknown as { rawJSON?: RawJsonFactory }).rawJSON;
  if (typeof rawJSON !== 'function') return JSON.parse(text) as unknown;
  return JSON.parse(text, (_key: string, val: unknown, context?: ReviverContext) =>
    typeof val === 'number' && context?.source !== undefined ? rawJSON(context.source) : val,
  ) as unknown;
}

/** Re-indents JSON text without changing a single value. */
export function reindentJson(text: string, indent = 2): string {
  return JSON.stringify(parseJsonExact(text), null, indent);
}

/**
 * Replaces each value that kept its JSON text (a response, or one inside an
 * object built from several responses) with an exact parse of that text.
 */
export function exactValue(value: unknown): unknown {
  const raw = rawJsonOf(value);
  if (raw !== undefined) {
    try {
      return parseJsonExact(raw);
    } catch {
      // keep the parsed value
    }
  }
  if (Array.isArray(value)) return value.map(exactValue);
  if (typeof value === 'object' && value !== null && Object.getPrototypeOf(value) === Object.prototype) {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, exactValue(v)]));
  }
  return value;
}

/**
 * A value as JSON text, as the server sent it where known: responses (and
 * responses inside a composite) keep their numbers' exact text.
 */
export function toJsonText(value: unknown, indent = 2): string {
  return JSON.stringify(exactValue(value), null, indent) ?? 'null';
}
