import { afterEach, describe, expect, it } from 'vitest';
import { parseAgentEvent, streamAgentChat, streamAgentResume, type AgentEvent } from '../src/agent';
import { createClient } from '../src/client';
import { SalliApiError } from '../src/errors';
import { rawJsonOf } from '../src/json';
import { readServerSentEvents } from '../src/sse';
import { sendProblem, startServer, type TestServer } from './helpers/server';

let server: TestServer | undefined;

afterEach(async () => {
  await server?.close();
  server = undefined;
});

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect<T>(iterable: AsyncIterable<T>): Promise<T[]> {
  const out: T[] = [];
  for await (const item of iterable) out.push(item);
  return out;
}

describe('readServerSentEvents', () => {
  it('reassembles events split across chunks', async () => {
    const events = await collect(
      readServerSentEvents(
        streamOf(['data: {"type":"tok', 'en","content":"Hel"}\n', '\ndata: {"type":"done"}\n\n']),
      ),
    );
    expect(events.map((e) => e.data)).toEqual(['{"type":"token","content":"Hel"}', '{"type":"done"}']);
  });

  it('keeps multi-byte characters intact across chunk boundaries', async () => {
    const bytes = new TextEncoder().encode('data: {"type":"token","content":"රු 1,500"}\n\n');
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, 33));
        controller.enqueue(bytes.slice(33));
        controller.close();
      },
    });
    const [event] = await collect(readServerSentEvents(stream));
    expect(JSON.parse(event?.data ?? '{}')).toEqual({ type: 'token', content: 'රු 1,500' });
  });

  it('delivers a final event the server ended without a blank line', async () => {
    const events = await collect(readServerSentEvents(streamOf(['data: {"type":"done"}\n'])));
    expect(events).toHaveLength(1);
  });

  it('stops when the caller aborts', async () => {
    const controller = new AbortController();
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(new TextEncoder().encode('data: {"type":"token","content":"a"}\n\n'));
        // never closes
      },
    });
    const seen: string[] = [];
    const run = (async () => {
      for await (const event of readServerSentEvents(stream, controller.signal)) {
        seen.push(event.data);
        controller.abort();
      }
    })();
    await expect(run).rejects.toThrow();
    expect(seen).toHaveLength(1);
  });
});

describe('parseAgentEvent', () => {
  it('parses known events and keeps their JSON text', () => {
    const event = parseAgentEvent({ data: '{"type":"tool_call","name":"get_balance","input":{"x":1.0}}' });
    expect(event).toEqual({ type: 'tool_call', name: 'get_balance', input: { x: 1 } });
    expect(rawJsonOf(event)).toBe('{"type":"tool_call","name":"get_balance","input":{"x":1.0}}');
  });

  it('passes unknown events through rather than dropping them', () => {
    expect(parseAgentEvent({ data: '{"type":"thinking","content":"hm"}' })).toEqual({
      type: 'unknown',
      data: { type: 'thinking', content: 'hm' },
    });
    expect(parseAgentEvent({ data: 'not json' })).toEqual({ type: 'unknown', data: 'not json' });
  });
});

describe('streamAgentChat', () => {
  it('posts the message and yields the events as they arrive', async () => {
    server = await startServer((req, res) => {
      res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' });
      res.write('data: {"type":"token","content":"Your balance is "}\n\n');
      res.write('data: {"type":"tool_call","name":"get_balance","input":{}}\n\n');
      res.write('data: {"type":"approval_required","action":{"type":"write","action":"add_entry","description":"Post Lunch","params":{"amount":"12.50"}}}\n\n');
      res.end('data: {"type":"done"}\n\n');
    });
    const salli = createClient({ server: server.url, auth: 'tok' });
    const events: AgentEvent[] = await collect(
      streamAgentChat(salli, { thread_id: 't-1', message: 'What is my balance?' }),
    );
    expect(events.map((e) => e.type)).toEqual(['token', 'tool_call', 'approval_required', 'done']);
    const approval = events[2];
    expect(approval?.type === 'approval_required' && approval.action.description).toBe('Post Lunch');
    expect(JSON.parse(server.requests[0]?.body ?? '{}')).toEqual({ thread_id: 't-1', message: 'What is my balance?' });
    expect(server.requests[0]?.path).toBe('/v1/agent/chat');
  });

  it('resumes with a decision', async () => {
    server = await startServer((req, res) => {
      res.writeHead(200, { 'Content-Type': 'text/event-stream' });
      res.end('data: {"type":"token","content":"Done."}\n\ndata: {"type":"done"}\n\n');
    });
    const salli = createClient({ server: server.url, auth: 'tok' });
    const events = await collect(
      streamAgentResume(salli, { thread_id: 't-1', decision: 'approved' }),
    );
    expect(events).toEqual([{ type: 'token', content: 'Done.' }, { type: 'done' }]);
    expect(server.requests[0]?.path).toBe('/v1/agent/resume');
  });

  it('raises the problem when the server refuses before streaming', async () => {
    server = await startServer((req, res) =>
      sendProblem(res, 429, { type: '/problems/usage-limit', title: 'Usage limit reached', detail: 'Daily limit' }),
    );
    const salli = createClient({ server: server.url, auth: 'tok' });
    const error = await collect(streamAgentChat(salli, { thread_id: 't', message: 'hi' })).catch(
      (e: unknown) => e,
    );
    expect(error).toBeInstanceOf(SalliApiError);
    expect((error as SalliApiError).kind).toBe('usage-limit');
  });
});
