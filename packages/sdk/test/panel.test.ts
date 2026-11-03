import { afterEach, describe, expect, it } from 'vitest';
import { createClient } from '../src/client';
import { SalliApiError } from '../src/errors';
import { formBody, isApiPath, missingFields, offerOf, parsePanel, parsePanelList, type PanelField } from '../src/panel';
import { sendJson, startServer, type TestServer } from './helpers/server';

let server: TestServer | undefined;
afterEach(async () => {
  await server?.close();
  server = undefined;
});

const action = { method: 'POST', path: '/v1/things/ask', then: 'refresh' };
const document = {
  schema: 'salli.panel/1',
  id: 'status',
  title: 'Your status',
  sections: [
    {
      heading: 'Now',
      rows: [
        { kind: 'text', label: 'Standing', value: 'Fine' },
        { kind: 'link', label: 'Read more', detail: 'Opens a page', url: 'https://example.org/more' },
        { kind: 'action', label: 'Ask', confirm: 'Ask now?', action },
        { kind: 'form', label: 'Tell us', fields: [{ name: 'note', label: 'Note', type: 'text', required: true }], submit: { label: 'Send', method: 'POST', path: '/v1/things/tell', then: 'close' } },
      ],
      footnote: 'Small print',
    },
  ],
  note: 'A note',
};

describe('parsePanel', () => {
  it('reads every kind of row', () => {
    const panel = parsePanel(document);
    expect(panel?.title).toBe('Your status');
    expect(panel?.sections[0]?.rows.map((r) => r.kind)).toEqual(['text', 'link', 'action', 'form']);
    expect(panel?.note).toBe('A note');
  });

  it('refuses what is not a salli.panel/1', () => {
    for (const bad of [null, 'text', [], {}, { ...document, schema: 'salli.panel/2' }, { ...document, sections: 'x' }, { ...document, title: '' }, { ...document, sections: [{ rows: 'x' }] }]) {
      expect(parsePanel(bad)).toBeUndefined();
    }
  });

  it('leaves out a row it cannot draw safely', () => {
    const rows = [
      { kind: 'link', label: 'Plain', url: 'http://example.org' },
      { kind: 'link', label: 'Script', url: 'javascript:alert(1)' },
      { kind: 'action', label: 'Elsewhere', action: { ...action, path: '/other' } },
      { kind: 'action', label: 'Escapes', action: { ...action, path: '/v1/../admin' } },
      { kind: 'action', label: 'Wrong verb', action: { ...action, method: 'GET' } },
      { kind: 'form', label: 'No fields', fields: [], submit: { label: 'Go', method: 'POST', path: '/v1/x', then: 'close' } },
      { kind: 'form', label: 'Empty select', fields: [{ name: 'a', label: 'A', type: 'select', required: false }], submit: { label: 'Go', method: 'POST', path: '/v1/x', then: 'close' } },
      { kind: 'unknown', label: 'Future' },
      { kind: 'text' },
      { kind: 'text', label: 'Kept' },
    ];
    const panel = parsePanel({ ...document, sections: [{ heading: null, rows, footnote: null }] });
    expect(panel?.sections[0]?.rows).toEqual([{ kind: 'text', label: 'Kept' }]);
  });
});

describe('isApiPath', () => {
  it('takes only paths under /v1/', () => {
    expect(isApiPath('/v1/things/1')).toBe(true);
    for (const bad of ['/v2/x', 'v1/x', '/v1/../x', '/v1//x', '/v1/x?a=1', 'https://example.org/v1/x', 7]) expect(isApiPath(bad)).toBe(false);
  });
});

describe('offerOf', () => {
  it('reads a whole offer and nothing less', () => {
    const offer = { title: 'T', detail: 'D', label: 'L', panel: 'upgrade' };
    expect(offerOf({ type: '/problems/capability-refused', offer })).toEqual(offer);
    expect(offerOf({ offer: { ...offer, panel: '../x' } })).toBeUndefined();
    expect(offerOf({ offer: { ...offer, label: '' } })).toBeUndefined();
    expect(offerOf({})).toBeUndefined();
    expect(offerOf(null)).toBeUndefined();
  });
});

describe('forms', () => {
  const fields: PanelField[] = [
    { name: 'a', label: 'A', type: 'text', required: true },
    { name: 'b', label: 'B', type: 'number', required: false },
  ];
  it('names the required fields still empty, and sends only what is filled', () => {
    expect(missingFields(fields, { a: '  ', b: '2' })).toEqual(['a']);
    expect(missingFields(fields, { a: 'x' })).toEqual([]);
    expect(formBody(fields, { a: ' x ', b: '' })).toEqual({ a: 'x' });
  });
});

describe('parsePanelList', () => {
  it('reads an array or a wrapped list, skipping what has no id or title', () => {
    const items = [{ id: 'a', title: 'A', entry: 'more' }, { id: 'b' }, { id: '../c', title: 'C' }, { id: 'd', title: 'D' }];
    const expected = [{ id: 'a', title: 'A', entry: 'more' }, { id: 'd', title: 'D', entry: undefined }];
    expect(parsePanelList(items)).toEqual(expected);
    expect(parsePanelList({ panels: items })).toEqual(expected);
    expect(parsePanelList('x')).toEqual([]);
  });
});

describe('client.send and onApiError', () => {
  it('sends a body to a path and tells the hook of a problem', async () => {
    server = await startServer((req, res) => {
      if (req.path === '/v1/things/ask') return sendJson(res, 200, { ok: true });
      res.statusCode = 402;
      res.setHeader('Content-Type', 'application/problem+json');
      res.end(JSON.stringify({ type: '/problems/capability-refused', title: 'Refused', status: 402, offer: { title: 'T', detail: 'D', label: 'L', panel: 'p' } }));
    });
    const seen: SalliApiError[] = [];
    const salli = createClient({ server: server.url, onApiError: (error) => seen.push(error) });
    expect(await salli.send({ method: 'POST', path: '/v1/things/ask', body: { a: '1' } })).toEqual({ ok: true });
    expect(server.requests[0]?.body).toBe('{"a":"1"}');
    await expect(salli.send({ method: 'POST', path: '/v1/other' })).rejects.toBeInstanceOf(SalliApiError);
    expect(seen).toHaveLength(1);
    expect(offerOf(seen[0]?.body)?.panel).toBe('p');
  });
});
