/**
 * The agent's event stream.
 *
 * `POST /v1/agent/chat` and `POST /v1/agent/resume` answer with server-sent
 * events, one JSON object each:
 *
 *   token             the agent's reply, a piece at a time
 *   subagent_start    a specialist agent took over …
 *   subagent_token    … what it is writing …
 *   subagent_end      … and handed back
 *   tool_call         a tool the agent called (and its input)
 *   tool_result       what the tool returned
 *   approval_required the agent wants to change something: ask the user, then
 *                     resume with `decision: "approved"` or `"denied"`
 *   interrupt         any other pause
 *   error             the turn failed
 *   done              the turn is over
 */
import { agentChat, agentResume } from './generated/sdk.gen';
import type { ChatRequest, ResumeRequest } from './generated/types.gen';
import type { SalliClient } from './client';
import { withRawJson } from './json';
import type { EventSourceMessage } from './sse';

/** What the agent asks permission for before it writes anything. */
export interface AgentApprovalRequest {
  /** The tool's kind of action, e.g. `write`. */
  type?: string;
  /** The tool it wants to run. */
  action?: string;
  /** A sentence for the user saying what will happen. */
  description?: string;
  /** The arguments it will run with. */
  params?: Record<string, unknown>;
  [field: string]: unknown;
}

export type AgentEvent =
  | { type: 'token'; content: string }
  | { type: 'subagent_start'; agent: string }
  | { type: 'subagent_token'; agent: string; content: string }
  | { type: 'subagent_end'; agent: string }
  | { type: 'tool_call'; name: string; input?: unknown; agent?: string }
  | { type: 'tool_result'; name: string; output?: unknown; agent?: string }
  | { type: 'approval_required'; action: AgentApprovalRequest }
  | { type: 'interrupt'; data: unknown }
  | { type: 'error'; message: string }
  | { type: 'done' }
  | { type: 'unknown'; data: unknown };

const KNOWN = new Set([
  'token',
  'subagent_start',
  'subagent_token',
  'subagent_end',
  'tool_call',
  'tool_result',
  'approval_required',
  'interrupt',
  'error',
  'done',
]);

/**
 * Parses one SSE message from the agent. Unrecognised events come back as
 * `{ type: "unknown" }` rather than being dropped. The event's JSON text is
 * kept (see `rawJsonOf`), for printing it exactly.
 */
export function parseAgentEvent(message: EventSourceMessage): AgentEvent {
  let value: unknown;
  try {
    value = JSON.parse(message.data) as unknown;
  } catch {
    return withRawJson({ type: 'unknown', data: message.data }, JSON.stringify(message.data));
  }
  const type = (value as { type?: unknown } | null)?.type;
  if (typeof type === 'string' && KNOWN.has(type)) return withRawJson(value as AgentEvent, message.data);
  return withRawJson({ type: 'unknown', data: value }, message.data);
}

export interface AgentStreamOptions {
  signal?: AbortSignal;
}

/** Sends a chat message and yields the agent's events until the turn ends. */
export async function* streamAgentChat(
  salli: SalliClient,
  body: ChatRequest,
  options: AgentStreamOptions = {},
): AsyncGenerator<AgentEvent, void, undefined> {
  for await (const message of salli.events(agentChat, {
    body,
    ...(options.signal ? { signal: options.signal } : {}),
  })) {
    yield parseAgentEvent(message);
  }
}

/** Answers an approval (or other interrupt) and yields the rest of the turn. */
export async function* streamAgentResume(
  salli: SalliClient,
  body: ResumeRequest,
  options: AgentStreamOptions = {},
): AsyncGenerator<AgentEvent, void, undefined> {
  for await (const message of salli.events(agentResume, {
    body,
    ...(options.signal ? { signal: options.signal } : {}),
  })) {
    yield parseAgentEvent(message);
  }
}
