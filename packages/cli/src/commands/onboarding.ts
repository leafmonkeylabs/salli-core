/**
 * salli onboarding: the first-run step that saves who you are and opens a
 * starter chart of accounts. Safe to run again: what exists is kept.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import { onboardingComplete, onboardingStatus, type OnboardingRequest } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import { singleLine } from '../output/text';
import { amountArg, currencyArg } from './shared';

const INCOME_SOURCES = ['employment', 'freelance', 'rental', 'interest', 'foreign', 'dividends'] as const;
const GOALS = ['financial_independence', 'retirement', 'home', 'emergency_fund', 'debt_free', 'wealth_growth'] as const;

/** "employment, rental" → ["employment", "rental"], refusing a source the server would not open accounts for. */
function incomeSources(value: string): string[] {
  const sources = value
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
  const unknown = sources.filter((s) => !(INCOME_SOURCES as readonly string[]).includes(s));
  if (unknown.length) {
    throw new UsageError(`Unknown income source: ${unknown.join(', ')}.`, `Sources: ${INCOME_SOURCES.join(', ')}.`);
  }
  return sources;
}

export function registerOnboarding(program: Command, app: App): void {
  const onboarding = program.command('onboarding').description('First-run setup: your profile and a starter chart of accounts');

  onboarding
    .command('status')
    .description('Whether onboarding is done')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(onboardingStatus);
      app.out.emit(data, { human: (d) => app.out.line(`Onboarding: ${d.complete ? 'done' : 'not done yet'}`) });
    });

  onboarding
    .command('complete')
    .description('Save your profile and open a starter chart of accounts (safe to run again)')
    .requiredOption('--name <name>', 'Your name')
    .option('--base-currency <code>', 'The currency your ledger is kept in (only while it is empty)')
    .option('--tax-residency <country>', 'The country you are taxed in, as a code (LK, GB, US…)')
    .addOption(new Option('--residency <status>', 'Tax residency status').choices(['resident', 'non_resident']).default('resident'))
    .option('--income <sources>', `Where your income comes from, comma-separated: ${INCOME_SOURCES.join(', ')}`)
    .addOption(new Option('--goal <goal>', 'Your main goal').choices(GOALS))
    .option('--goal-amount <amount>', 'How much that goal needs, in your base currency')
    .option('--goal-year <yyyy>', 'When you want to reach it')
    .action(async (opts) => {
      const residency = opts.taxResidency?.trim();
      if (residency !== undefined && !/^[A-Za-z]{2}$/.test(residency)) {
        throw new UsageError(`A country is a two-letter code like LK or GB (got "${opts.taxResidency}").`);
      }
      if (opts.goalYear !== undefined && !/^\d{4}$/.test(opts.goalYear.trim())) {
        throw new UsageError(`--goal-year is a year like 2040 (got "${opts.goalYear}").`);
      }
      if ((opts.goalAmount !== undefined || opts.goalYear !== undefined) && !opts.goal) {
        throw new UsageError('--goal-amount and --goal-year describe a goal: pass --goal too.');
      }
      const body: OnboardingRequest = {
        name: opts.name,
        residency: opts.residency,
        ...(opts.baseCurrency ? { base_currency: currencyArg(opts.baseCurrency) } : {}),
        ...(residency ? { tax_residency: residency.toUpperCase() } : {}),
        ...(opts.income ? { income_sources: incomeSources(opts.income) } : {}),
        ...(opts.goal ? { primary_goal: opts.goal } : {}),
        ...(opts.goalAmount ? { goal_target_amount: amountArg(opts.goalAmount, '--goal-amount') } : {}),
        ...(opts.goalYear ? { goal_target_year: opts.goalYear.trim() } : {}),
      };
      const api = await app.api();
      const result = await api.call(onboardingComplete, { body });
      app.out.emit(result, {
        records: (r) => r.accounts_created.map((name) => ({ account: name, created: true })),
        human: (r) => {
          app.out.success(
            `Onboarding done: ${r.accounts_created.length} account${r.accounts_created.length === 1 ? '' : 's'} opened, ${r.accounts_skipped.length} already there.`,
          );
          for (const name of r.accounts_created) app.out.line(`  ${singleLine(name)}`);
          app.out.note('Next: salli accounts list, or record something with salli add "lunch 12.50 cash".');
        },
      });
    });
}
