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
 * Re-indents JSON text without changing a single value: numbers keep their
 * exact source text (via `JSON.rawJSON` where the runtime has it).
 */
export function reindentJson(text: string, indent = 2): string {
  const rawJSON = (JSON as unknown as { rawJSON?: RawJsonFactory }).rawJSON;
  if (typeof rawJSON !== 'function') return JSON.stringify(JSON.parse(text), null, indent);
  const value: unknown = JSON.parse(text, (_key: string, val: unknown, context?: ReviverContext) =>
    typeof val === 'number' && context?.source !== undefined ? rawJSON(context.source) : val,
  );
  return JSON.stringify(value, null, indent);
}

/**
 * A value as JSON text: the text it arrived as (re-indented, numbers
 * untouched) when known, else its encoding.
 */
export function toJsonText(value: unknown, indent = 2): string {
  const raw = rawJsonOf(value);
  if (raw !== undefined) {
    try {
      return reindentJson(raw, indent);
    } catch {
      // fall through to encoding the parsed value
    }
  }
  return JSON.stringify(value, null, indent) ?? 'null';
}
