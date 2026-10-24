/**
 * One turn of Your AI: the person's provider and key, Salli's tools over the
 * server's MCP (the AI's own sign-in), and core's own instructions (the
 * `talk_with_me` prompt, which ends with Salli's guardrails). Tools that only
 * read run as the model asks; any other waits for the person's approval.
 */
import { createAnthropic } from '@ai-sdk/anthropic';
import { createMCPClient } from '@ai-sdk/mcp';
import { createOpenAI } from '@ai-sdk/openai';
import { createOpenAICompatible } from '@ai-sdk/openai-compatible';
import { createXai } from '@ai-sdk/xai';
import { createOpenRouter } from '@openrouter/ai-sdk-provider';
import { stepCountIs, streamText, type LanguageModel, type ModelMessage } from 'ai';
import { fetch as expoFetch } from 'expo/fetch';
import { BRIEF, modelsOf, onlyReads, providerOf, type Model, type ProviderId } from '../lib/ai';

// Streaming needs Expo's fetch: React Native's own reads a response whole.
const streamingFetch = expoFetch as unknown as typeof globalThis.fetch;

export function modelFor(provider: ProviderId, apiKey: string, model: string): LanguageModel {
  switch (provider) {
    case 'anthropic':
      return createAnthropic({ apiKey, fetch: streamingFetch })(model);
    case 'openai':
      return createOpenAI({ apiKey, fetch: streamingFetch })(model);
    case 'xai':
      return createXai({ apiKey, fetch: streamingFetch })(model);
    case 'meta':
      return createOpenAICompatible({ name: 'meta', baseURL: providerOf('meta')?.baseURL ?? '', apiKey, fetch: streamingFetch })(model);
    case 'openrouter':
      return createOpenRouter({ apiKey, fetch: streamingFetch })(model);
  }
}

/** The models the key can use, from the provider's own list. */
export async function listModels(provider: ProviderId, apiKey: string): Promise<Model[]> {
  const base = providerOf(provider)?.baseURL ?? '';
  const headers: Record<string, string> =
    provider === 'anthropic' ? { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' } : { authorization: `Bearer ${apiKey}` };
  const response = await fetch(`${base}/models`, { headers });
  if (!response.ok) throw new Error(response.status === 401 ? 'The key was refused.' : `The provider answered ${response.status}.`);
  return modelsOf(await response.json());
}

/** A change the AI wants to make, waiting for the person. */
export interface Approval {
  approvalId: string;
  tool: string;
  input: Record<string, unknown>;
}

export type TurnEvent = { type: 'text'; text: string } | { type: 'read'; tool: string };

export interface Turn {
  /** What the turn added to the conversation, to keep and to send next time. */
  messages: ModelMessage[];
  /** Changes waiting for approval; the conversation goes on once they are answered. */
  approvals: Approval[];
}

/**
 * Runs the conversation forward: from the person's message, or from their
 * answers to the approvals the last turn asked for (already in `messages`).
 */
export async function runTurn(options: {
  model: LanguageModel;
  mcpUrl: string;
  mcpToken: string;
  messages: ModelMessage[];
  onEvent: (event: TurnEvent) => void;
  signal?: AbortSignal;
}): Promise<Turn> {
  const mcp = await createMCPClient({
    transport: { type: 'http', url: options.mcpUrl, headers: { authorization: `Bearer ${options.mcpToken}` } },
  });
  try {
    const prompt = await mcp.experimental_getPrompt({ name: 'talk_with_me' });
    const instructions = prompt.messages
      .map((m) => (m.content.type === 'text' ? m.content.text : ''))
      .join('\n')
      .trim();
    if (!instructions) throw new Error('This server has no instructions for an AI conversation yet: it needs Salli 0.5 or later.');
    const tools = await mcp.tools();
    const result = streamText({
      model: options.model,
      system: `${instructions}\n\n${BRIEF}`,
      messages: options.messages,
      tools,
      toolApproval: ({ toolCall }) => (onlyReads(toolCall.toolName) ? undefined : 'user-approval'),
      stopWhen: stepCountIs(12),
      ...(options.signal ? { abortSignal: options.signal } : {}),
    });
    const approvals: Approval[] = [];
    for await (const part of result.fullStream) {
      if (part.type === 'text-delta') options.onEvent({ type: 'text', text: part.text });
      else if (part.type === 'tool-call' && onlyReads(part.toolName)) options.onEvent({ type: 'read', tool: part.toolName });
      else if (part.type === 'tool-approval-request') {
        approvals.push({
          approvalId: part.approvalId,
          tool: part.toolCall.toolName,
          input: (part.toolCall.input ?? {}) as Record<string, unknown>,
        });
      } else if (part.type === 'error') throw part.error instanceof Error ? part.error : new Error(String(part.error));
    }
    // Every step's messages: its tool calls and results as well as its text.
    return { messages: await result.responseMessages, approvals };
  } finally {
    await mcp.close();
  }
}

/** The person's answers to the changes a turn asked about, as the next message. */
export function answers(approvals: readonly Approval[], approved: boolean): ModelMessage {
  return {
    role: 'tool',
    content: approvals.map((a) => ({
      type: 'tool-approval-response' as const,
      approvalId: a.approvalId,
      approved,
      ...(approved ? {} : { reason: 'The person said not now.' }),
    })),
  };
}
