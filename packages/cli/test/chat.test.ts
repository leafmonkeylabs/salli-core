import { PassThrough } from 'node:stream';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { MockSalli } from './helpers/mock-server';
import { runCli, ScriptedPrompter, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
  mock = await MockSalli.start();
});
afterEach(async () => {
  await mock.close();
  await cleanup();
});

const run = (args: string[], options: Partial<RunOptions> = {}) =>
  runCli(args, {
    configDir: dir,
    ...options,
    env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', ...options.env },
  });

describe('salli ask', () => {
  it('prints the answer', async () => {
    const result = await run(['ask', 'what is my net worth?']);
    expect(result.code).toBe(0);
    expect(result.stdout).toBe('Your net worth is USD 14,034.50.\n');
    const body = mock.requestsTo('POST', '/v1/agent/chat')[0]?.json as { thread_id: string; message: string; persona: string };
    expect(body.message).toBe('what is my net worth?');
    expect(body.persona).toBe('scrooge');
    expect(body.thread_id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it('streams the events as NDJSON with --json, exactly as sent', async () => {
    const result = await run(['ask', 'net worth?', '--json']);
    const lines = result.stdout.trim().split('\n');
    expect(lines).toEqual(mock.chatEvents.map((e) => JSON.stringify(e)));
  });

  it('declines a change when there is no terminal to ask in', async () => {
    mock.chatEvents = [
      { type: 'token', content: 'I can record that. ' },
      { type: 'approval_required', action: { type: 'write', action: 'add_entry', description: 'Post “Lunch” for USD 12.50', params: { amount: '12.50' } } },
      { type: 'done' },
    ];
    const result = await run(['ask', 'record lunch 12.50']);
    expect(result.code).toBe(0);
    expect(result.stdout).toBe('I can record that. \nOkay, I left it.\n');
    expect(result.stderr).toContain('The agent wants to post “Lunch” for USD 12.50');
    expect(mock.requestsTo('POST', '/v1/agent/resume')[0]?.json).toMatchObject({ decision: 'denied', workflow: 'chat' });
  });

  it('asks in a terminal, and resumes with the answer', async () => {
    mock.chatEvents = [
      { type: 'approval_required', action: { action: 'add_entry', description: 'Post “Lunch”' } },
      { type: 'done' },
    ];
    const result = await run(['ask', 'record lunch'], { prompter: new ScriptedPrompter([true]) });
    expect(result.stdout).toBe('Posted.\n');
    expect(mock.requestsTo('POST', '/v1/agent/resume')[0]?.json).toMatchObject({ decision: 'approved' });
  });

  it('exits 1 when the agent fails', async () => {
    mock.chatEvents = [{ type: 'error', message: 'Anthropic rejected the API key' }, { type: 'done' }];
    const result = await run(['ask', 'hello']);
    expect(result.code).toBe(1);
    expect(result.stderr).toContain('The agent could not answer: Anthropic rejected the API key');
  });

  it('passes a usage limit through as a refusal (exit 5)', async () => {
    mock.on('POST', '/v1/agent/chat', () => ({
      status: 429,
      body: { type: '/problems/usage-limit', title: 'Usage limit reached', status: 429, detail: 'Daily AI limit reached' },
      headers: { 'Content-Type': 'application/problem+json' },
    }));
    const result = await run(['ask', 'hello']);
    expect(result.code).toBe(5);
    expect(result.stderr).toContain('Usage limit reached: Daily AI limit reached');
  });
});

describe('salli chat', () => {
  it('holds a conversation from piped input, approving a change', async () => {
    mock.chatEvents = [
      { type: 'subagent_start', agent: 'ledger_specialist' },
      { type: 'tool_call', name: 'add_entry', input: { amount: '12.50' }, agent: 'ledger_specialist' },
      { type: 'subagent_end', agent: 'ledger_specialist' },
      { type: 'approval_required', action: { action: 'add_entry', description: 'Post “Lunch”' } },
      { type: 'done' },
    ];
    const stdin = new PassThrough();
    stdin.end('record lunch 12.50 cash\ny\n/thread\n');
    const result = await run(['chat'], { stdin });
    expect(result.code).toBe(0);
    expect(result.stdout).toBe('salli › Posted.\n');
    expect(result.stderr).toContain('↳ Ledger specialist is on it');
    expect(result.stderr).toContain('· add_entry {"amount":"12.50"}');
    expect(result.stderr).toContain('? The agent wants to post “Lunch”');
    const chat = mock.requestsTo('POST', '/v1/agent/chat')[0]?.json as { thread_id: string };
    const resume = mock.requestsTo('POST', '/v1/agent/resume')[0]?.json as { thread_id: string; decision: string };
    expect(resume).toMatchObject({ thread_id: chat.thread_id, decision: 'approved' });
    // /thread prints the conversation id; leaving names it too.
    expect(result.stderr).toContain(chat.thread_id);
    expect(result.stderr).toContain(`salli chat --thread ${chat.thread_id.slice(0, 8)}`);
  });
});
