/**
 * A panel: a page a server describes and a client only draws (`salli.panel/1`).
 * What the words say, and what an action does, are the server's; a client
 * adds none of its own. `parsePanel` reads a document defensively: a document
 * that is not this schema is refused whole, a row it cannot draw safely
 * (a link that is not https, an action outside `/v1/`) is left out.
 */

export interface PanelAction {
  method: 'POST' | 'DELETE';
  /** A path under `/v1/`. */
  path: string;
  body?: Record<string, unknown>;
  /** What the client does after the server accepts it. */
  then: 'refresh' | 'close';
}

export interface PanelField {
  name: string;
  label: string;
  type: 'text' | 'number' | 'select';
  options?: string[];
  required: boolean;
}

export type PanelRow =
  | { kind: 'text'; label: string; value?: string }
  | { kind: 'link'; label: string; detail?: string; url: string }
  | { kind: 'action'; label: string; detail?: string; confirm?: string; action: PanelAction }
  | { kind: 'form'; label: string; fields: PanelField[]; submit: { label: string; method: 'POST' | 'DELETE'; path: string; then: 'refresh' | 'close' } };

export interface PanelSection {
  heading: string | null;
  rows: PanelRow[];
  footnote: string | null;
}

export interface Panel {
  schema: 'salli.panel/1';
  id: string;
  title: string;
  sections: PanelSection[];
  note: string | null;
}

/** A problem's offer: a sheet's words and the panel its button opens. */
export interface Offer {
  title: string;
  detail: string;
  label: string;
  panel: string;
}

type Obj = Record<string, unknown>;
const isObj = (value: unknown): value is Obj => typeof value === 'object' && value !== null && !Array.isArray(value);
const str = (value: unknown): string | undefined => (typeof value === 'string' && value !== '' ? value : undefined);
const optional = (value: unknown): string | null => str(value) ?? null;

/** Whether a path is one the API serves: under `/v1/`, no dot segments, no query, no host. */
export function isApiPath(path: unknown): path is string {
  return typeof path === 'string' && /^\/v1\/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*$/.test(path) && !path.split('/').some((part) => part === '.' || part === '..') && !path.includes('//');
}

/** Whether a panel id is one that can sit in a path. */
export function isPanelId(id: unknown): id is string {
  return typeof id === 'string' && /^[A-Za-z0-9._-]{1,64}$/.test(id);
}

function isHttps(url: unknown): url is string {
  if (typeof url !== 'string') return false;
  try {
    return new URL(url).protocol === 'https:';
  } catch {
    return false;
  }
}

function method(value: unknown): 'POST' | 'DELETE' | undefined {
  return value === 'POST' || value === 'DELETE' ? value : undefined;
}

function then(value: unknown): 'refresh' | 'close' | undefined {
  return value === 'refresh' || value === 'close' ? value : undefined;
}

function actionOf(value: unknown): PanelAction | undefined {
  if (!isObj(value)) return undefined;
  const m = method(value.method);
  const after = then(value.then);
  if (!m || !after || !isApiPath(value.path)) return undefined;
  if (value.body !== undefined && !isObj(value.body)) return undefined;
  return { method: m, path: value.path, ...(value.body ? { body: value.body } : {}), then: after };
}

function fieldOf(value: unknown): PanelField | undefined {
  if (!isObj(value)) return undefined;
  const name = str(value.name);
  const label = str(value.label);
  if (!name || !label || (value.type !== 'text' && value.type !== 'number' && value.type !== 'select')) return undefined;
  let options: string[] | undefined;
  if (value.type === 'select') {
    if (!Array.isArray(value.options) || !value.options.length || !value.options.every((o) => typeof o === 'string' && o !== '')) return undefined;
    options = value.options as string[];
  }
  return { name, label, type: value.type, ...(options ? { options } : {}), required: value.required === true };
}

function rowOf(value: unknown): PanelRow | undefined {
  if (!isObj(value)) return undefined;
  const label = str(value.label);
  if (!label) return undefined;
  switch (value.kind) {
    case 'text':
      return { kind: 'text', label, ...(str(value.value) ? { value: str(value.value) as string } : {}) };
    case 'link':
      return isHttps(value.url) ? { kind: 'link', label, ...(str(value.detail) ? { detail: str(value.detail) as string } : {}), url: value.url } : undefined;
    case 'action': {
      const action = actionOf(value.action);
      if (!action) return undefined;
      return { kind: 'action', label, ...(str(value.detail) ? { detail: str(value.detail) as string } : {}), ...(str(value.confirm) ? { confirm: str(value.confirm) as string } : {}), action };
    }
    case 'form': {
      const fields = Array.isArray(value.fields) ? value.fields.map(fieldOf) : [];
      const submit = isObj(value.submit) ? value.submit : undefined;
      const m = method(submit?.method);
      const after = then(submit?.then);
      const submitLabel = str(submit?.label);
      if (!fields.length || fields.some((f) => !f) || !m || !after || !submitLabel || !isApiPath(submit?.path)) return undefined;
      return { kind: 'form', label, fields: fields as PanelField[], submit: { label: submitLabel, method: m, path: submit?.path as string, then: after } };
    }
    default:
      return undefined;
  }
}

/** A panel document, or undefined when it is not a `salli.panel/1`. */
export function parsePanel(value: unknown): Panel | undefined {
  if (!isObj(value) || value.schema !== 'salli.panel/1' || !Array.isArray(value.sections)) return undefined;
  const id = str(value.id);
  const title = str(value.title);
  if (!id || !title) return undefined;
  const sections: PanelSection[] = [];
  for (const raw of value.sections) {
    if (!isObj(raw) || !Array.isArray(raw.rows)) return undefined;
    const rows = raw.rows.map(rowOf).filter((row): row is PanelRow => row !== undefined);
    sections.push({ heading: optional(raw.heading), rows, footnote: optional(raw.footnote) });
  }
  return { schema: 'salli.panel/1', id, title, sections, note: optional(value.note) };
}

/** The offer a problem carries, if it carries a whole one. */
export function offerOf(body: unknown): Offer | undefined {
  const offer = isObj(body) ? body.offer : undefined;
  if (!isObj(offer)) return undefined;
  const [title, detail, label, panel] = [str(offer.title), str(offer.detail), str(offer.label), offer.panel];
  return title && detail && label && isPanelId(panel) ? { title, detail, label, panel } : undefined;
}

/** What a form's fields hold, as the body a submit sends: the empty ones left out. */
export function formBody(fields: readonly PanelField[], values: Readonly<Record<string, string>>): Record<string, string> {
  const body: Record<string, string> = {};
  for (const field of fields) {
    const text = (values[field.name] ?? '').trim();
    if (text) body[field.name] = text;
  }
  return body;
}

/** The names of the required fields still empty. */
export function missingFields(fields: readonly PanelField[], values: Readonly<Record<string, string>>): string[] {
  return fields.filter((field) => field.required && !(values[field.name] ?? '').trim()).map((field) => field.name);
}

/** The panels a list names, whatever shape of list the server sends (an array, or `{panels: [...]}`). */
export interface PanelEntry {
  id: string;
  title: string;
  entry: string | undefined;
}

export function parsePanelList(value: unknown): PanelEntry[] {
  const list = Array.isArray(value) ? value : isObj(value) && Array.isArray(value.panels) ? value.panels : [];
  const out: PanelEntry[] = [];
  for (const item of list) {
    if (!isObj(item) || !isPanelId(item.id)) continue;
    const title = str(item.title);
    if (title) out.push({ id: item.id, title, entry: str(item.entry) });
  }
  return out;
}
