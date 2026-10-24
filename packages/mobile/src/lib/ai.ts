/**
 * Your AI (docs/design/mobile.md, "Your AI"): the providers it may run on,
 * which of Salli's tools only read, and what the conversations kept on this
 * phone hold. Plain TypeScript: the model calls are in src/ai.
 */
import type { ModelMessage } from 'ai';
import { strings } from '../strings';
import { displayDate } from './display';

export type ProviderId = 'anthropic' | 'openai' | 'xai' | 'meta' | 'openrouter';

export interface Provider {
  id: ProviderId;
  name: string;
  /** Its API, for the models list and, past Anthropic, an OpenAI-style chat. */
  baseURL: string;
  /** The model to start with when the person hasn't chosen one. */
  defaultModel?: string;
}

export const PROVIDERS: readonly Provider[] = [
  { id: 'anthropic', name: 'Anthropic', baseURL: 'https://api.anthropic.com/v1', defaultModel: 'claude-opus-5-5' },
  { id: 'openai', name: 'OpenAI', baseURL: 'https://api.openai.com/v1' },
  { id: 'xai', name: 'xAI', baseURL: 'https://api.x.ai/v1' },
  { id: 'meta', name: 'Meta', baseURL: 'https://api.llama.com/compat/v1' },
  { id: 'openrouter', name: 'OpenRouter', baseURL: 'https://openrouter.ai/api/v1' },
];

export function providerOf(id: string | undefined): Provider | undefined {
  return PROVIDERS.find((p) => p.id === id);
}

/** A model a provider lists for the key: its id, and a name to show. */
export interface Model {
  id: string;
  name: string;
}

/**
 * A provider's models list (`GET /models`), whichever shape it answers in:
 * Anthropic's and OpenAI's `{data: [{id, display_name?}]}`, OpenRouter's
 * `{data: [{id, name}]}`, or a bare array. Chat models only, where the list
 * says which are; newest first as listed.
 */
export function modelsOf(answer: unknown): Model[] {
  const rows = Array.isArray(answer) ? answer : Array.isArray((answer as { data?: unknown })?.data) ? (answer as { data: unknown[] }).data : [];
  const models: Model[] = [];
  for (const row of rows) {
    if (typeof row !== 'object' || row === null) continue;
    const { id, display_name: displayName, name } = row as { id?: unknown; display_name?: unknown; name?: unknown };
    if (typeof id !== 'string' || !id) continue;
    // Embedding, image, audio and moderation models answer no conversation.
    if (/embed|whisper|tts|dall-e|image|moderation|audio|transcribe|realtime/i.test(id)) continue;
    models.push({ id, name: typeof displayName === 'string' ? displayName : typeof name === 'string' ? name : id });
  }
  return models;
}

/**
 * Salli's tools that only read, by name. Every other tool changes something
 * (an entry, a reminder, a rule, a decision, a document) and waits for the
 * person's approval: a tool core adds later is asked about until it is
 * listed here, never run unasked.
 */
export function onlyReads(tool: string): boolean {
  return (
    /^(get|list|read|explain|check|compare|suggest|diff|evaluate|validate)_/.test(tool) ||
    ['run_scenario', 'start_decision', 'suggested_tax_accounts'].includes(tool)
  );
}

/** A conversation's title: its first question, cut at a word to one line. */
export function titleOf(question: string, limit = 48): string {
  const text = question.trim().replace(/\s+/g, ' ');
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit);
  const space = cut.lastIndexOf(' ');
  return `${(space > limit / 2 ? cut.slice(0, space) : cut).replace(/[,.;:]$/, '')}…`;
}

/** The newest conversations kept, at most `limit`, the one just changed first. */
export function keepNewest<T extends { id: string; at: string }>(all: readonly T[], changed: T, limit = 20): T[] {
  return [changed, ...all.filter((c) => c.id !== changed.id)].sort((a, b) => b.at.localeCompare(a.at)).slice(0, limit);
}

/**
 * A change the AI asked to make, in one line for the approval card: what
 * kind of change, then what it is about and when. Amounts are shown as the
 * tool was given them, never worked out.
 */
export function changeOf(tool: string, input: Readonly<Record<string, unknown>>): string {
  const label = strings.ai.changeLabels[tool] ?? `${tool.charAt(0).toUpperCase()}${tool.slice(1).replace(/_/g, ' ')}`;
  const what = ['title', 'name', 'description', 'question', 'kind', 'text', 'label'].map((k) => input[k]).find((v): v is string => typeof v === 'string' && v.trim() !== '');
  const when = ['due_date', 'date', 'entry_date', 'review_on'].map((k) => input[k]).find((v): v is string => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}/.test(v));
  const amount = typeof input.amount === 'string' && typeof input.currency === 'string' ? `${input.currency} ${input.amount}` : undefined;
  const details = [what?.trim(), amount, when ? displayDate(when) : undefined].filter(Boolean);
  return details.length ? `${label}: ${details.join(', ')}` : label;
}

/** What a conversation shows: your messages, and each answer with how much it read from Salli. */
export type Block = { kind: 'you'; text: string } | { kind: 'ai'; reads: number; text: string };

/** A change asked for and not yet answered: the conversation waits on it. */
export interface Pending {
  approvalId: string;
  tool: string;
  input: Record<string, unknown>;
}

type Part = { type: string; text?: string; toolName?: string; approvalId?: string; toolCallId?: string; input?: unknown };
const partsOf = (message: ModelMessage): Part[] => (typeof message.content === 'string' ? [{ type: 'text', text: message.content }] : (message.content as Part[]));

export function blocksOf(messages: readonly ModelMessage[]): Block[] {
  const blocks: Block[] = [];
  for (const message of messages) {
    if (message.role === 'user') {
      const text = partsOf(message).map((p) => (p.type === 'text' ? (p.text ?? '') : '')).join('');
      blocks.push({ kind: 'you', text });
      continue;
    }
    // Tool results sit between an answer's steps: the answer goes on past them.
    if (message.role !== 'assistant') continue;
    const last = blocks[blocks.length - 1];
    const block: Extract<Block, { kind: 'ai' }> = last && last.kind === 'ai' ? last : { kind: 'ai', reads: 0, text: '' };
    if (block !== last) blocks.push(block);
    for (const part of partsOf(message)) {
      if (part.type === 'text' && part.text) block.text = block.text ? `${block.text}\n\n${part.text}` : part.text;
      else if (part.type === 'tool-call' && part.toolName && onlyReads(part.toolName)) block.reads += 1;
    }
  }
  return blocks;
}

/** The approvals the last answer asked for that no answer has met yet. */
export function pendingOf(messages: readonly ModelMessage[]): Pending[] {
  const answered = new Set<string>();
  const calls = new Map<string, { tool: string; input: Record<string, unknown> }>();
  const asked: { approvalId: string; toolCallId: string }[] = [];
  for (const message of messages) {
    for (const part of partsOf(message)) {
      if (part.type === 'tool-call' && part.toolCallId && part.toolName) {
        calls.set(part.toolCallId, { tool: part.toolName, input: (part.input ?? {}) as Record<string, unknown> });
      } else if (part.type === 'tool-approval-request' && part.approvalId && part.toolCallId) {
        asked.push({ approvalId: part.approvalId, toolCallId: part.toolCallId });
      } else if (part.type === 'tool-approval-response' && part.approvalId) {
        answered.add(part.approvalId);
      }
    }
  }
  return asked
    .filter((a) => !answered.has(a.approvalId))
    .map((a) => ({ approvalId: a.approvalId, ...(calls.get(a.toolCallId) ?? { tool: 'unknown', input: {} }) }));
}

/**
 * How the app's AI answers on a phone, added to the server's instructions
 * (older servers ask for "a few short sentences"): figures first, short,
 * longer only when asked or needed.
 */
export const BRIEF =
  'On a phone: lead with the figure, in one to three short lines or a short list. No preamble, no restating the question, no closing offer. Go longer only when asked for detail or when the question needs it, such as a decision or a comparison.';
