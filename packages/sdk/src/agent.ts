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
import type {
  AgentChatData,
  AgentResumeData,
  ChatRequest,
  FireStrategy,
  FiStrategyGenerateData,
  ResumeRequest,
} from './generated/types.gen';
import type { SalliClient } from './client';
import { withRawJson } from './json';
import { parseEventData, type EventSourceMessage } from './sse';

// Typed by the operations' own paths, so a renamed route fails to compile.
const CHAT: AgentChatData['url'] = '/v1/agent/chat';
const RESUME: AgentResumeData['url'] = '/v1/agent/resume';
const STRATEGY: FiStrategyGenerateData['url'] = '/v1/fi/strategy/generate';

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
  for await (const message of salli.events({ url: CHAT, body, ...(options.signal ? { signal: options.signal } : {}) })) {
    yield parseAgentEvent(message);
  }
}

/** Answers an approval (or other interrupt) and yields the rest of the turn. */
export async function* streamAgentResume(
  salli: SalliClient,
  body: ResumeRequest,
  options: AgentStreamOptions = {},
): AsyncGenerator<AgentEvent, void, undefined> {
  for await (const message of salli.events({ url: RESUME, body, ...(options.signal ? { signal: options.signal } : {}) })) {
    yield parseAgentEvent(message);
  }
}

/** One event of the FIRE strategy generator's stream. */
export type StrategyEvent =
  | { type: 'status'; message: string }
  | { type: 'done'; strategy: FireStrategy }
  | { type: 'error'; message: string }
  | { type: 'unknown'; data: unknown };

/** Starts drafting a FIRE strategy and yields its progress, then the strategy. */
export async function* streamStrategyGeneration(
  salli: SalliClient,
  options: AgentStreamOptions = {},
): AsyncGenerator<StrategyEvent, void, undefined> {
  for await (const message of salli.events({ url: STRATEGY, ...(options.signal ? { signal: options.signal } : {}) })) {
    const value = parseEventData(message) as { type?: unknown } | undefined;
    const type = value?.type;
    const event: StrategyEvent =
      type === 'status' || type === 'done' || type === 'error' ? (value as StrategyEvent) : { type: 'unknown', data: value ?? message.data };
    yield withRawJson(event, message.data);
  }
}
