/**
 * Server-sent events, read from a response body.
 *
 * The agent chat and the FIRE strategy generator stream their progress as
 * SSE. These are POSTs that act (a chat message is metered and remembered),
 * so a dropped stream is never retried here: replaying it would send the
 * message twice.
 */
import { createParser, type EventSourceMessage } from 'eventsource-parser';

export type { EventSourceMessage } from 'eventsource-parser';

/**
 * Yields each event in an SSE stream as it arrives. Ends when the stream
 * does; stops early (and cancels the stream) when `signal` aborts or the
 * caller stops iterating.
 */
export async function* readServerSentEvents(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<EventSourceMessage, void, undefined> {
  const queue: EventSourceMessage[] = [];
  const parser = createParser({ onEvent: (event) => queue.push(event) });
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let finished = false;
  const onAbort = (): void => {
    reader.cancel(signal?.reason).catch(() => undefined);
  };
  signal?.addEventListener('abort', onAbort, { once: true });
  try {
    for (;;) {
      if (signal?.aborted) throw signal.reason ?? new DOMException('Aborted', 'AbortError');
      const { done, value } = await reader.read();
      if (done) {
        // Strictly, an event the stream ends without its blank line is
        // discarded; a proxy that drops the final newline should not cost
        // the last event (usually `done`), so the blank line is supplied.
        parser.feed(`${decoder.decode()}\n\n`);
        finished = true;
      } else {
        parser.feed(decoder.decode(value, { stream: true }));
      }
      while (queue.length > 0) {
        const event = queue.shift();
        if (event) yield event;
      }
      if (finished) return;
    }
  } finally {
    signal?.removeEventListener('abort', onAbort);
    if (!finished) await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

/** Parses an event's `data` as JSON, or returns undefined when it is not JSON. */
export function parseEventData(event: EventSourceMessage): unknown {
  try {
    return JSON.parse(event.data) as unknown;
  } catch {
    return undefined;
  }
}
