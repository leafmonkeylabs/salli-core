/**
 * salli chat (a conversation), salli ask (one question), and salli sessions.
 *
 * The agent's reply streams in as it is written. Its tool calls and the
 * specialists it hands work to show as quiet progress lines. When it wants
 * to change something it asks first, and nothing is written unless you
 * approve.
 */
import { randomUUID } from 'node:crypto';
import { createInterface, type Interface } from 'node:readline';
import { Option, type Command } from '@commander-js/extra-typings';
import {
  agentAuditLog,
  agentFilesUpload,
  agentHistory,
  agentSessionsDelete,
  agentSessionsList,
  rawJsonOf,
  streamAgentChat,
  streamAgentResume,
  type AgentApprovalRequest,
  type AgentEvent,
  type SalliClient,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { CliError, InterruptedError, UsageError } from '../errors';
import { sanitize, singleLine, truncate } from '../output/text';
import { displayDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { readUpload } from '../util/files';
import { collect, confirmAction, limitArg } from './shared';

type Persona = 'scrooge' | 'buddy';
const PERSONAS = ['scrooge', 'buddy'] as const;

interface Session {
  thread_id: string;
  title?: string | null;
  last_active_at?: string | null;
  created_at?: string | null;
}

/** "tax_specialist" → "Tax specialist". */
const agentName = (name: string): string => {
  const text = singleLine(name.replace(/[_-]+/g, ' '));
  return text.charAt(0).toUpperCase() + text.slice(1);
};

function preview(value: unknown, width = 60): string {
  if (value === undefined || value === null) return '';
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  return truncate(singleLine(text), width);
}

/** What one turn of the conversation ended with. */
interface TurnEnd {
  approval?: AgentApprovalRequest;
  error?: string;
  text: string;
}

/** Writes a turn's events as they arrive: the reply to stdout, progress to stderr. */
async function renderTurn(
  app: App,
  events: AsyncIterable<AgentEvent>,
  options: { json: boolean; progress: boolean; prefix?: string },
): Promise<TurnEnd> {
  const out = app.out;
  const c = out.errColors;
  const end: TurnEnd = { text: '' };
  let atLineStart = true;
  // Written before the reply's first words, so a turn with none prints nothing.
  let prefix = options.prefix;
  // In a terminal the reply and the progress lines share the screen, so a
  // progress line starts on a line of its own; piped, the reply stays whole.
  const sharedScreen = app.runtime.stdout.isTTY === true && app.runtime.stderr.isTTY === true;
  const progress = (line: string): void => {
    if (!options.progress) return;
    if (!atLineStart && sharedScreen) {
      out.write('\n');
      atLineStart = true;
    }
    out.errLine(c.dim(line));
  };
  for await (const event of events) {
    if (options.json) {
      out.line(rawJsonOf(event) ?? JSON.stringify(event));
    }
    switch (event.type) {
      case 'token': {
        const text = sanitize(event.content);
        end.text += text;
        if (!options.json && text) {
          if (prefix && atLineStart) out.write(prefix);
          prefix = undefined;
          out.write(text);
          atLineStart = text.endsWith('\n');
        }
        break;
      }
      case 'subagent_start':
        progress(`  ↳ ${agentName(event.agent)} is on it`);
        break;
      case 'subagent_token':
        if (app.globals.verbose) progress(`    ${preview(event.content, 120)}`);
        break;
      case 'tool_call':
        progress(`  · ${singleLine(event.name)}${event.input && Object.keys(event.input as object).length ? ` ${preview(event.input)}` : ''}`);
        break;
      case 'tool_result':
        if (app.globals.verbose) progress(`    → ${preview(event.output, 120)}`);
        break;
      case 'approval_required':
        end.approval = event.action;
        break;
      case 'interrupt':
        progress(`  (paused: ${preview(event.data, 100)})`);
        break;
      case 'error':
        end.error = event.message;
        break;
      default:
        break;
    }
  }
  if (!options.json && !atLineStart) out.write('\n');
  return end;
}

function describeApproval(app: App, approval: AgentApprovalRequest): string {
  const c = app.out.errColors;
  const what = approval.description ? singleLine(String(approval.description)) : `run ${singleLine(String(approval.action ?? 'a write'))}`;
  const params = approval.params && Object.keys(approval.params).length ? `\n    ${c.dim(preview(approval.params, 100))}` : '';
  return `${c.yellow('?')} The agent wants to ${what.charAt(0).toLowerCase()}${what.slice(1)}${params}`;
}

/** Uploads a file for the agent to read; returns its reference. */
async function attach(app: App, api: SalliClient, path: string): Promise<string> {
  const file = await readUpload(path);
  const result = (await api.call(agentFilesUpload, { body: { file }, timeoutMs: 120_000 })) as { file_ref: string; name?: string };
  app.out.note(`Attached ${singleLine(result.name ?? file.name)}.`);
  return result.file_ref;
}

async function resolveThread(api: SalliClient, query: string): Promise<string> {
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(query)) return query;
  const { sessions } = (await api.call(agentSessionsList, { query: { limit: 200 } })) as { sessions: Session[] };
  return resolveById(
    sessions.map((s) => ({ ...s, id: s.thread_id })),
    query,
    'conversation',
  ).thread_id;
}

/** Runs one message to the end of its turn, answering approvals as asked. */
async function converse(
  app: App,
  api: SalliClient,
  thread: string,
  persona: Persona,
  message: string,
  decide: (approval: AgentApprovalRequest) => Promise<boolean>,
  options: { json: boolean; progress: boolean; signal: AbortSignal; prefix?: string; fileRefs?: string[] },
): Promise<TurnEnd> {
  const body = { thread_id: thread, message, persona, ...(options.fileRefs?.length ? { file_refs: options.fileRefs } : {}) };
  let end = await renderTurn(app, streamAgentChat(api, body, { signal: options.signal }), options);
  while (end.approval && !end.error) {
    const approved = await decide(end.approval);
    end = await renderTurn(
      app,
      streamAgentResume(api, { thread_id: thread, decision: approved ? 'approved' : 'denied', workflow: 'chat', persona }, { signal: options.signal }),
      options,
    );
  }
  return end;
}

const HELP = `Commands:
  /attach <file>  send a file (receipt, statement, photo) with your next message
  /new            start a new conversation
  /thread         show this conversation's id
  /exit           leave (or press Ctrl-D)`;

export function registerChat(program: Command, app: App): void {
  const personaOption = () =>
    new Option('--persona <persona>', 'Who answers: scrooge (Salli AI) or buddy').choices(PERSONAS).default('scrooge' as Persona);

  program
    .command('chat')
    .description('Talk with Salli’s AI about your money (streams; asks before it changes anything)')
    .option('--thread <id>', 'Continue an earlier conversation (see `salli sessions list`)')
    .addOption(personaOption())
    .action(async (opts) => {
      const api = await app.api();
      let thread = opts.thread ? await resolveThread(api, opts.thread) : randomUUID();
      const persona = opts.persona as Persona;
      const { stdin, stderr } = app.runtime;
      const terminal = stdin.isTTY === true;
      const rl: Interface = createInterface({ input: stdin, output: stderr, terminal, historySize: 200 });
      const c = app.out.errColors;
      app.out.errLine(c.dim(`Salli · conversation ${thread.slice(0, 8)}${opts.thread ? ' (continued)' : ''} · /help for commands, Ctrl-D to leave`));

      // Lines are read through the iterator, which keeps any typed (or
      // piped) while a reply is streaming, rather than dropping them.
      const lines = rl[Symbol.asyncIterator]();
      let closed = false;
      rl.on('close', () => {
        closed = true;
      });
      const ask = async (prompt: string): Promise<string | undefined> => {
        // Piped input may have ended while lines it sent are still waiting.
        if (!closed) {
          rl.setPrompt(prompt);
          rl.prompt();
        }
        const next = await lines.next();
        return next.done ? undefined : String(next.value);
      };

      let turn: AbortController | undefined;
      const pending: string[] = [];
      const stop = (): void => {
        // Ctrl-C stops the reply in progress; at the prompt, it leaves.
        if (turn) turn.abort(new InterruptedError('Stopped.'));
        else rl.close();
      };
      rl.on('SIGINT', stop);
      app.runtime.signal.addEventListener('abort', stop);

      const decide = async (approval: AgentApprovalRequest): Promise<boolean> => {
        app.out.errLine(describeApproval(app, approval));
        const answer = ((await ask(`  Approve? ${c.dim('[y/N]')} `)) ?? '').trim().toLowerCase();
        const ok = answer === 'y' || answer === 'yes';
        app.out.errLine(c.dim(ok ? '  Approved.' : '  Declined.'));
        return ok;
      };

      try {
        for (;;) {
          const line = await ask(`${c.cyan('you')} › `);
          if (line === undefined) break; // Ctrl-D, or the end of piped input
          const message = line.trim();
          if (!message) continue;
          if (message === '/exit' || message === '/quit') break;
          if (message === '/help') {
            app.out.errLine(HELP);
            continue;
          }
          if (message === '/thread') {
            app.out.errLine(thread);
            continue;
          }
          if (message === '/new') {
            thread = randomUUID();
            app.out.errLine(c.dim(`New conversation ${thread.slice(0, 8)}.`));
            continue;
          }
          if (message.startsWith('/attach')) {
            const path = message.slice('/attach'.length).trim().replace(/^["']|["']$/g, '');
            if (!path) app.out.errLine('Usage: /attach <file>');
            else {
              try {
                pending.push(await attach(app, api, path));
              } catch (error) {
                app.out.errLine(`${c.red('✗')} ${singleLine((error as Error).message)}`);
              }
            }
            continue;
          }
          turn = new AbortController();
          const fileRefs = pending.splice(0);
          try {
            const end = await converse(app, api, thread, persona, message, decide, {
              json: false,
              progress: true,
              signal: turn.signal,
              prefix: `${app.out.colors.green('salli')} › `,
              fileRefs,
            });
            if (end.error) app.out.errLine(`${c.red('✗')} ${singleLine(end.error)}`);
          } catch (error) {
            if (!turn.signal.aborted) throw error;
            app.out.errLine(c.dim('\n(stopped)'));
          } finally {
            turn = undefined;
          }
        }
      } finally {
        app.runtime.signal.removeEventListener('abort', stop);
        rl.close();
      }
      app.out.errLine(c.dim(`Conversation ${thread.slice(0, 8)} saved; continue it with: salli chat --thread ${thread.slice(0, 8)}`));
    });

  program
    .command('ask')
    .argument('<question...>', 'Your question')
    .description('Ask one question and print the answer (--json streams the events as NDJSON)')
    .option('--thread <id>', 'Ask within an earlier conversation')
    .option('--attach <file>', 'Send a file with the question (repeatable)', collect)
    .addOption(personaOption())
    .addHelpText(
      'after',
      `
If the agent wants to change something, you are asked in a terminal;
without one, the change is declined.

Examples:
  $ salli ask "how much did I spend on groceries last month?"
  $ salli ask "what is this charge?" --attach receipt.pdf
  $ salli ask "what is my FI number?" --json | jq -r 'select(.type=="token") | .content'`,
    )
    .action(async (words, opts) => {
      const message = words.join(' ').trim();
      if (!message) throw new UsageError('Ask a question, e.g. salli ask "what is my net worth?"');
      const api = await app.api();
      const thread = opts.thread ? await resolveThread(api, opts.thread) : randomUUID();
      const fileRefs: string[] = [];
      for (const path of opts.attach ?? []) fileRefs.push(await attach(app, api, path));
      const json = app.out.json;
      const decide = async (approval: AgentApprovalRequest): Promise<boolean> => {
        app.out.errLine(describeApproval(app, approval));
        if (!app.prompter.interactive) {
          app.out.note('  Declined: there is no terminal to ask in. Use `salli chat` to approve changes.');
          return false;
        }
        return app.prompter.confirm({ message: 'Approve?', initialValue: false });
      };
      const end = await converse(app, api, thread, opts.persona as Persona, message, decide, {
        json,
        progress: !json && (app.runtime.stderr.isTTY === true || app.globals.verbose === true),
        signal: app.runtime.signal,
        fileRefs,
      });
      if (end.error) throw new CliError(`The agent could not answer: ${end.error}`);
    });

  const sessions = program.command('sessions').description('Your conversations with the AI');

  sessions
    .command('list')
    .alias('ls')
    .description('Conversations, most recent first')
    .option('--limit <n>', 'At most this many', limitArg)
    .addOption(personaOption())
    .action(async (opts) => {
      const api = await app.api();
      const data = (await api.call(agentSessionsList, {
        query: { limit: opts.limit ?? 50, persona: opts.persona as Persona },
      })) as { sessions: Session[] };
      app.out.emit(data, {
        records: (d) => d.sessions,
        human: (d) => {
          if (d.sessions.length === 0) {
            app.out.note('No conversations yet. Start one with `salli chat`.');
            return;
          }
          const c = app.out.colors;
          app.out.line(
            app.out.table(d.sessions, [
              { header: 'THREAD', get: (s) => s.thread_id.slice(0, 8), style: (t) => c.dim(t) },
              { header: 'TITLE', get: (s) => s.title || '(untitled)', shrink: true },
              { header: 'LAST ACTIVE', get: (s) => displayDate(s.last_active_at ?? s.created_at ?? '', app.out.locale) },
            ]),
          );
        },
      });
    });

  sessions
    .command('show')
    .argument('<thread>', 'Conversation id (or its start)')
    .description('Print a conversation')
    .addOption(personaOption())
    .action(async (query, opts) => {
      const api = await app.api();
      const thread = await resolveThread(api, query);
      const data = (await api.call(agentHistory, { path: { thread_id: thread }, query: { persona: opts.persona as Persona } })) as {
        thread_id: string;
        messages: Array<{ role: string; content?: string; parts?: Array<Record<string, unknown>> }>;
      };
      app.out.emit(data, {
        records: (d) => d.messages,
        human: (d) => {
          const c = app.out.colors;
          const printParts = (parts: Array<Record<string, unknown>>, indent: string): void => {
            for (const part of parts) {
              if (part.type === 'text' || part.type === 'token') app.out.line(indent + sanitize(String(part.content ?? '')));
              else if (part.type === 'tool_call') app.out.line(c.dim(`${indent}· ${String(part.name ?? '')}`));
              else if (part.type === 'subagent_section') {
                app.out.line(c.dim(`${indent}↳ ${agentName(String(part.agent ?? ''))}`));
                printParts((part.parts as Array<Record<string, unknown>>) ?? [], `${indent}  `);
              }
            }
          };
          for (const m of d.messages) {
            if (m.role === 'user') app.out.line(`\n${c.cyan('you')} › ${sanitize(m.content ?? '')}`);
            else {
              app.out.line(`\n${c.green('salli')} ›`);
              printParts(m.parts ?? [], '  ');
            }
          }
        },
      });
    });

  sessions
    .command('delete')
    .argument('<thread>', 'Conversation id (or its start)')
    .description('Delete a conversation')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const thread = await resolveThread(api, query);
      if (!(await confirmAction(app, opts.yes, `Delete conversation ${thread.slice(0, 8)}?`))) return;
      await api.call(agentSessionsDelete, { path: { thread_id: thread } });
      app.out.done({ thread_id: thread, deleted: true }, `Deleted conversation ${thread.slice(0, 8)}.`);
    });

  sessions
    .command('audit-log')
    .description('Every change the AI asked to make, and whether it was approved')
    .option('--limit <n>', 'At most this many', limitArg)
    .action(async (opts) => {
      const api = await app.api();
      const data = (await api.call(agentAuditLog, { query: { limit: opts.limit ?? 100 } })) as {
        entries: Array<{ created_at?: string; action?: string; decision?: string; params?: unknown }>;
      };
      app.out.emit(data, {
        records: (d) => d.entries,
        human: (d) => {
          if (d.entries.length === 0) {
            app.out.note('The AI has not asked to change anything yet.');
            return;
          }
          const c = app.out.colors;
          app.out.line(
            app.out.table(d.entries, [
              { header: 'WHEN', get: (e) => displayDate(e.created_at ?? '', app.out.locale) },
              { header: 'ACTION', get: (e) => e.action ?? '' },
              { header: 'DECISION', get: (e) => e.decision ?? '', style: (t) => (t === 'approved' ? c.green(t) : c.red(t)) },
              { header: 'DETAILS', get: (e) => preview(e.params, 80), shrink: true },
            ]),
          );
        },
      });
    });
}
