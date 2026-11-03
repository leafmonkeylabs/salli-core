/**
 * A server that describes panels (`salli.panel/1`), as the fixtures answer
 * it: a list, one page with a text, a link, an action that asks first and a
 * form, and what the page says once the action was made. The words are
 * the server's own, written here by hand: the console draws them as sent.
 */
import type { Answer, Recorded } from './api';

export const PANEL_LIST = [
  { id: 'account', title: 'Your account', entry: 'more' },
  { id: 'move', title: 'Move your books', entry: 'more' },
];

const SEND = { method: 'POST', path: '/v1/example/requests', then: 'refresh' } as const;

export function accountPanel(requested: boolean): unknown {
  return {
    schema: 'salli.panel/1',
    id: 'account',
    title: 'Your account',
    sections: [
      {
        heading: 'Now',
        rows: [
          { kind: 'text', label: 'Standing', value: 'Starter' },
          { kind: 'text', label: 'People', value: 'One' },
        ],
        footnote: null,
      },
      {
        heading: 'More room',
        rows: requested
          ? [
              { kind: 'text', label: 'Requested', value: 'Waiting for a reply' },
              { kind: 'action', label: 'Withdraw the request', confirm: 'Withdraw your request?', action: { method: 'DELETE', path: '/v1/example/requests/r1', then: 'refresh' } },
            ]
          : [
              { kind: 'action', label: 'Ask for more room', detail: 'Adds people to your book.', confirm: 'Ask for more room?', action: SEND },
              { kind: 'link', label: 'What is included', detail: 'On the website', url: 'https://example.org/included' },
              {
                kind: 'form',
                label: 'Tell us what you need',
                fields: [
                  { name: 'size', label: 'People', type: 'number', required: true },
                  { name: 'kind', label: 'Kind', type: 'select', options: [{ value: 'Household', label: 'Household' }, { value: 'Practice', label: 'Practice' }], required: false },
                  { name: 'note', label: 'Anything else', type: 'text', required: false },
                ],
                submit: { label: 'Send', method: 'POST', path: '/v1/example/requests', then: 'refresh' },
              },
            ],
        footnote: 'Nothing changes until we reply.',
      },
    ],
    note: requested ? 'We will reply by email.' : null,
  };
}

export class PanelsState {
  requested = false;
  /** When set, the next action is refused with this problem. */
  refuse: Answer | undefined;

  answer({ method, path }: Recorded): Answer | undefined {
    if (method === 'GET' && path === '/v1/panels') return { status: 200, body: { panels: PANEL_LIST } };
    if (method === 'GET' && path === '/v1/panels/account') return { status: 200, body: accountPanel(this.requested) };
    if (method === 'GET' && path === '/v1/panels/move') return { status: 200, body: { schema: 'salli.panel/1', id: 'move', title: 'Move your books', sections: [], note: 'Nothing to show yet.' } };
    if (method === 'GET' && path.startsWith('/v1/panels/')) return { status: 404, body: { type: 'about:blank', title: 'Not Found', status: 404, detail: 'No such panel' } };
    if (path.startsWith('/v1/example/requests')) {
      if (this.refuse) return this.refuse;
      this.requested = method === 'POST';
      return { status: 204 };
    }
    return undefined;
  }
}
