/**
 * salli ai status | use | models | set-models | host | connect chatgpt | disconnect chatgpt
 *
 * What powers Salli's AI: your ChatGPT plan, your own Anthropic or OpenAI
 * key (`salli llm-keys`), or the server's key.
 */
import type { Command } from '@commander-js/extra-typings';
import {
  aiChatgptDisconnect,
  aiChatgptGet,
  aiHostGet,
  aiModelsList,
  aiModelsSet,
  aiSettingsGet,
  aiSettingsSet,
  type AiModels,
  type ChatGptConnection,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { connectChatGpt, MANAGE_USAGE_URL } from '../auth/chatgpt';
import { CliError, UsageError } from '../errors';
import type { Output } from '../output/output';
import { singleLine } from '../output/text';
import { displayDate } from '../util/dates';
import { countArg } from './shared';

const PROVIDERS = ['anthropic', 'openai', 'chatgpt'] as const;
const CHOICES = ['auto', ...PROVIDERS] as const;
const SOURCE: Record<string, string> = { user: 'yours', platform: 'this server’s key', none: 'nothing set up yet' };

function onlyChatGpt(provider: string): void {
  if (provider !== 'chatgpt') {
    throw new UsageError('Only `chatgpt` is signed in to.', 'For an API key, use `salli llm-keys set openai` (or anthropic).');
  }
}

function chatGptLine(out: Output, s: ChatGptConnection): string {
  const c = out.colors;
  const state: Record<ChatGptConnection['status'], string> = {
    active: `${c.green('connected')} as ${singleLine(s.email ?? 'your account')}`,
    needs_sign_in: c.yellow('needs you to sign in again (salli ai connect chatgpt)'),
    needs_consent: c.yellow('signed in, but plan use is not allowed (salli ai connect chatgpt)'),
    signed_out: 'disconnected',
    not_connected: 'not connected',
  };
  return state[s.status];
}

function printModels(out: Output, m: AiModels): void {
  out.line(`${out.heading(m.provider)} best ${out.colors.bold(singleLine(m.best))}, fast ${out.colors.bold(singleLine(m.fast))}`);
  const chosen = Object.entries(m.chosen).filter(([, v]) => v);
  if (chosen.length) out.line(out.colors.dim(`chosen by you: ${chosen.map(([k, v]) => `${k} = ${singleLine(String(v))}`).join(', ')}`));
  out.line(
    out.table(m.models, [
      { header: 'MODEL', get: (x) => x.id },
      { header: 'NAME', get: (x) => (x.name !== x.id ? x.name : ''), shrink: true },
      { header: '', get: (x) => [x.id === m.best ? 'best' : '', x.id === m.fast ? 'fast' : ''].filter(Boolean).join(', '), style: (t) => out.colors.dim(t) },
    ]),
  );
}

export function registerAi(program: Command, app: App): void {
  const ai = program
    .command('ai')
    .description('What powers Salli’s AI: your ChatGPT plan, your own API key, or the server’s')
    .addHelpText(
      'after',
      `
Examples:
  $ salli ai status
  $ salli ai connect chatgpt            (use your ChatGPT plan; counts toward its limits)
  $ salli ai use auto                   (your plan, then your keys, then the server's)
  $ salli ai set-models openai --fast gpt-5-mini`,
    );

  ai.command('status')
    .description('Which provider powers your AI, and your ChatGPT plan connection')
    .action(async () => {
      const api = await app.api();
      const [settings, chatgpt] = await Promise.all([api.call(aiSettingsGet), api.call(aiChatgptGet)]);
      app.out.emit(
        { settings, chatgpt },
        {
          human: () => {
            const out = app.out;
            out.line(
              out.details([
                ['AI provider', `${settings.provider} → ${settings.active.provider} (${SOURCE[settings.active.source] ?? settings.active.source})`],
                ['Your API keys', settings.keys.length ? settings.keys.join(', ') : 'none'],
                ['ChatGPT', chatgpt.available ? chatGptLine(out, chatgpt) : out.colors.yellow('off on this server')],
                ['Paused until', chatgpt.paused_until ? displayDate(chatgpt.paused_until, out.locale) : undefined],
                ['Detail', chatgpt.detail ?? undefined],
              ]),
            );
            if (chatgpt.status !== 'not_connected') out.note(`Manage what Salli uses of your plan: ${chatgpt.manage_usage_url ?? MANAGE_USAGE_URL}`);
          },
        },
      );
    });

  ai.command('use')
    .argument('<provider>', CHOICES.join(', '))
    .description('Choose what powers your AI (auto: your ChatGPT plan, then your Anthropic key, then OpenAI, then the server’s)')
    .action(async (provider) => {
      if (!(CHOICES as readonly string[]).includes(provider)) throw new UsageError(`A provider is one of: ${CHOICES.join(', ')} (got "${provider}").`);
      const api = await app.api();
      const settings = await api.call(aiSettingsSet, { body: { provider: provider as (typeof CHOICES)[number] } });
      app.out.done(
        settings,
        `AI provider set to ${settings.provider}: runs on ${settings.active.provider} (${SOURCE[settings.active.source] ?? settings.active.source}).`,
      );
    });

  ai.command('models')
    .argument('[provider]', `${PROVIDERS.join(', ')} (default: the one in use)`)
    .description('The models a provider offers you, and which one each task runs on')
    .action(async (provider) => {
      if (provider && !(PROVIDERS as readonly string[]).includes(provider)) throw new UsageError(`A provider is one of: ${PROVIDERS.join(', ')}.`);
      const api = await app.api();
      const name = (provider ?? (await api.call(aiSettingsGet)).active.provider) as (typeof PROVIDERS)[number];
      const models = await api.call(aiModelsList, { path: { provider: name } });
      app.out.emit(models, { records: (m) => m.models, human: (m) => printModels(app.out, m) });
    });

  ai.command('set-models')
    .argument('<provider>', 'openai or chatgpt')
    .description('Name the model each task runs on (neither: let Salli pick again)')
    .option('--fast <model>', 'For sorting statements and quick add')
    .option('--best <model>', 'For chat, the FIRE strategy and advice')
    .action(async (provider, opts) => {
      if (provider !== 'openai' && provider !== 'chatgpt') throw new UsageError('Models can be chosen for openai or chatgpt.');
      const api = await app.api();
      const models = await api.call(aiModelsSet, { path: { provider }, body: { fast: opts.fast ?? null, best: opts.best ?? null } });
      app.out.emit(models, { records: (m) => m.models, human: (m) => printModels(app.out, m) });
    });

  ai.command('host')
    .description('This server’s host id for Sign in with ChatGPT (not a secret)')
    .action(async () => {
      const api = await app.api();
      const host = await api.call(aiHostGet);
      app.out.emit(host, { human: (h) => app.out.line(singleLine(h.ext_agent_host_id)) });
    });

  ai.command('connect')
    .argument('<provider>', 'chatgpt')
    .description('Connect your ChatGPT plan: Continue with ChatGPT in your browser')
    .option('--new-account', 'Register a different ChatGPT account than the connected one')
    .option('--port <n>', 'The port on 127.0.0.1 the browser returns to', countArg('--port'), 1455)
    .option('--no-browser', 'Print the link instead of opening a browser')
    .option('--timeout <seconds>', 'How long to wait for the browser', countArg('--timeout'), 300)
    .addHelpText(
      'after',
      `
Run it where your browser is. Salli's AI requests then use your ChatGPT plan
and count toward its usage limits (review them at ${MANAGE_USAGE_URL}).
The sign-in goes straight to the server, which keeps and renews it; nothing
is stored on this computer, and no token is ever printed.`,
    )
    .action(async (provider, opts) => {
      onlyChatGpt(provider);
      const api = await app.api();
      const status = await connectChatGpt(app, api, {
        newAccount: opts.newAccount === true,
        port: opts.port,
        openBrowser: opts.browser,
        timeoutMs: opts.timeout * 1000,
      });
      if (app.out.machine) {
        app.out.emit(status, { human: () => undefined });
        return;
      }
      const out = app.out;
      if (status.first_time) {
        out.success('You’re using your ChatGPT plan.');
        out.info(`Salli’s AI requests now use your ChatGPT plan. Review and manage what Salli uses in ChatGPT settings: ${status.manage_usage_url ?? MANAGE_USAGE_URL}`);
      } else {
        out.success(`Connected to ChatGPT as ${singleLine(status.email ?? 'your account')}.`);
      }
    });

  ai.command('disconnect')
    .argument('<provider>', 'chatgpt')
    .description('Disconnect your ChatGPT plan: end the sign-in with OpenAI and forget its tokens')
    .action(async (provider) => {
      onlyChatGpt(provider);
      const api = await app.api();
      const result = await api.call(aiChatgptDisconnect);
      if (!result.disconnected) throw new CliError('ChatGPT is not connected.');
      app.out.done(result, singleLine(result.message));
    });
}
