/**
 * The mock server's digest routes (`/v1/notifications`), kept in memory and
 * typed with the SDK's generated types. The preview and the log are what
 * the real server answered for a person with a decision to review, a
 * reminder, a filing deadline and cash going below zero, on Monday
 * 2026-10-12 at 09:30 in Lisbon. Turning digests on without a time zone is
 * refused, as the server refuses it.
 */
import type { DigestDeliveries, DigestPreview, NotificationPreferences } from '@leafmonkeylabs/salli-sdk';

type Reply = { status: number; body?: unknown; headers?: Record<string, string>; raw?: string };

export interface NotificationsRequest {
  method: string;
  path: string;
  query: URLSearchParams;
  json?: unknown;
}

export const PREFERENCES: NotificationPreferences = {
  enabled: false,
  cadence: 'weekly',
  weekday: 'monday',
  hour: 9,
  items: ['decision_review_due', 'reminder_due', 'filing_deadline', 'cash_below_zero_ahead'],
  time_zone: null,
  next_at: null,
  sender_enabled: true,
};

export const DIGEST_ID = '71398767e5d0586fe9644c522d43d32d91fffc0cc06c2810739ac2849b0def1e';

export const PREVIEW: DigestPreview = {
  period: '2026-W42',
  as_of: '2026-10-12',
  time_zone: 'Europe/Lisbon',
  digest: {
    id: DIGEST_ID,
    kind: 'digest',
    period: '2026-W42',
    subject: 'Salli: what is waiting, week of Oct 12, 2026',
    text:
      'What is waiting for you in Salli, as of Oct 12, 2026:\n\n' +
      '- 1 decision ready for review (since Oct 5, 2026)\n' +
      '- 1 reminder due on Oct 14, 2026\n' +
      '- 1 filing deadline on Oct 20, 2026\n' +
      '- Your cash forecast goes below zero on Nov 2, 2026\n\n' +
      'Open Salli to see them: https://money.example.org\n\n' +
      'You asked for this digest every week. To change it or turn it off: salli notifications set\n',
    items: [
      { kind: 'decision_review_due', title: '1 decision ready for review (since Oct 5, 2026)', count: 1, date: '2026-10-05' },
      { kind: 'reminder_due', title: '1 reminder due on Oct 14, 2026', count: 1, date: '2026-10-14' },
      { kind: 'filing_deadline', title: '1 filing deadline on Oct 20, 2026', count: 1, date: '2026-10-20' },
      { kind: 'cash_below_zero_ahead', title: 'Your cash forecast goes below zero on Nov 2, 2026', count: 1, date: '2026-11-02' },
    ],
    link: 'https://money.example.org',
  },
  note: 'This is the digest that would go if it went now.',
};

export const DELIVERIES: DigestDeliveries = {
  deliveries: [
    {
      id: DIGEST_ID,
      period: '2026-W42',
      status: 'sent',
      attempts: 1,
      items: [
        { kind: 'decision_review_due', count: 1, date: '2026-10-05' },
        { kind: 'reminder_due', count: 1, date: '2026-10-14' },
        { kind: 'filing_deadline', count: 1, date: '2026-10-20' },
        { kind: 'cash_below_zero_ahead', count: 1, date: '2026-11-02' },
      ],
      hash: 'sha256:ba052edbc1a52049e8b1593c1879291d1dd8f369b75a6c78c361698badb2ed87',
      created_at: '2026-10-12T08:30:00+00:00',
      last_attempt_at: '2026-10-12T08:30:00+00:00',
      sent_at: '2026-10-12T08:30:00+00:00',
    },
  ],
};

function problem(status: number, title: string, detail: unknown, type: string): Reply {
  return {
    status,
    body: { type, title, status, detail },
    headers: { 'Content-Type': 'application/problem+json', 'X-Request-Id': 'req-test-1' },
  };
}

export class NotificationsMock {
  preferences: NotificationPreferences = structuredClone(PREFERENCES);
  preview: DigestPreview = structuredClone(PREVIEW);
  deliveries: DigestDeliveries = structuredClone(DELIVERIES);
  /** PATCH bodies, in order. */
  readonly bodies: unknown[] = [];

  route(req: NotificationsRequest): Reply | undefined {
    const { method, path } = req;
    if (!path.startsWith('/v1/notifications/')) return undefined;
    if (path === '/v1/notifications/preferences' && method === 'GET') return { status: 200, body: this.preferences };
    if (path === '/v1/notifications/preferences' && method === 'PATCH') {
      const body = (req.json ?? {}) as Partial<NotificationPreferences>;
      this.bodies.push(body);
      const next = { ...this.preferences, ...body };
      if (next.enabled && !next.time_zone) {
        return problem(
          422,
          'Unprocessable Entity',
          "a digest goes at your local hour: set your time zone (an IANA name, such as 'Europe/Lisbon') to turn it on",
          '/problems/unprocessable',
        );
      }
      if (next.time_zone && !/^[A-Za-z]+(\/[A-Za-z_+-]+)+$|^UTC$/.test(next.time_zone)) {
        return problem(422, 'Unprocessable Entity', `'${next.time_zone}' is not an IANA time zone name (such as 'Europe/Lisbon' or 'UTC')`, '/problems/unprocessable');
      }
      next.next_at = next.enabled ? '2026-10-12T09:00:00+01:00' : null;
      this.preferences = next;
      return { status: 200, body: this.preferences };
    }
    if (path === '/v1/notifications/preview' && method === 'GET') return { status: 200, body: this.preview };
    if (path === '/v1/notifications/deliveries' && method === 'GET') {
      // eslint-disable-next-line no-restricted-syntax -- not money: how many log rows
      const limit = Number(req.query.get('limit') ?? 50);
      return { status: 200, body: { deliveries: this.deliveries.deliveries.slice(0, limit) } };
    }
    return undefined;
  }
}
