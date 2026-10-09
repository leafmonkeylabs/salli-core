/**
 * Reminders, reports, tax, documents, your profile and data, your own LLM
 * keys, and AI clients connected over MCP.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  accountExport,
  agentFilesUpload,
  compareAmounts,
  documentsDelete,
  documentsGet,
  documentsList,
  llmKeysDelete,
  llmKeysList,
  llmKeysSet,
  mcpConnectionsList,
  mcpConnectionsRevoke,
  mcpEnabledGet,
  mcpEnabledSet,
  profileGet,
  profileUpdate,
  remindersCreate,
  remindersDelete,
  remindersList,
  remindersMarkDone,
  remindersSeedFilingCalendar,
  remindersSyncAlerts,
  reportsBalanceSheet,
  reportsExportCsv,
  reportsGoalProgress,
  reportsNetWorth,
  taxCompute,
  taxCurrentYear,
  taxLatest,
  taxPacks,
  toJsonText,
  type AgentDocument,
  type ProfileIdentityRequest,
  type Reminder,
  type SalliClient,
  type TaxComputation,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { CliError, UsageError } from '../errors';
import { displayWidth, padEnd, padStart, singleLine } from '../output/text';
import { displayDate, displayRange, isoDate, parseDate } from '../util/dates';
import { readUpload, textOf, writeOutput } from '../util/files';
import { resolveById } from '../util/resolve';
import { readAllStdin } from '../util/stdin';
import { renderRecord } from './records';
import { humanize } from './status';
import { collect, confirmAction, countArg, currencyArg, rateArg } from './shared';

/** A field from the server, as one line of safe text. */
const str = (v: string | null | undefined): string => (v ? singleLine(v) : '');

// ── Reminders ────────────────────────────────────────────────────────────────

function registerReminders(program: Command, app: App): void {
  const reminders = program.command('reminders').alias('reminder').description('Deadlines and alerts: filing dates, overspending, missed charges, expiring cover');
  const resolveReminder = async (api: SalliClient, query: string): Promise<Reminder> =>
    resolveById((await api.call(remindersList)).reminders, query, 'reminder');

  reminders
    .command('list')
    .alias('ls')
    .description('List reminders, soonest first')
    .addOption(new Option('--status <status>', 'Only pending or done ones').choices(['pending', 'done']))
    .option('--alerts', 'Only alerts Salli raised (not reminders you or the filing calendar made)')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(remindersList, {
        query: { ...(opts.status ? { status: opts.status } : {}), ...(opts.alerts ? { alerts_only: true } : {}) },
      });
      const today = isoDate(app.runtime.now());
      app.out.emit(data, {
        records: (d) => d.reminders,
        human: (d) => {
          if (!d.reminders.length) return app.out.note('Nothing to remind you of.');
          const c = app.out.colors;
          const sorted = [...d.reminders].sort((a, b) => a.due_date.localeCompare(b.due_date));
          app.out.line(
            app.out.table(sorted, [
              { header: 'ID', get: (r) => r.id.slice(0, 8), style: (t) => c.dim(t) },
              { header: 'DUE', get: (r) => displayDate(r.due_date, app.out.locale), style: (t, r) => (r.status === 'pending' && r.due_date < today ? c.red(t) : t) },
              { header: 'WHAT', get: (r) => humanize(r.kind), shrink: true },
              { header: 'STATUS', get: (r) => r.status, style: (t, r) => (r.status === 'done' ? c.dim(t) : t) },
              { header: 'ALERT', get: (r) => r.severity ?? '', style: (t, r) => (r.severity === 'critical' ? c.red(t) : c.yellow(t)) },
            ]),
          );
        },
      });
    });

  reminders
    .command('add')
    .argument('<what>', 'What to remember, e.g. quarterly_installment')
    .requiredOption('--due <date>', 'When (YYYY-MM-DD)')
    .description('Add a reminder')
    .action(async (kind, opts) => {
      const api = await app.api();
      const created = await api.call(remindersCreate, { body: { kind, due_date: parseDate(opts.due, app.runtime.now(), '--due') } });
      if (app.out.machine) app.out.emit(created, { human: () => undefined });
      else app.out.success(`Reminder added for ${displayDate(parseDate(opts.due, app.runtime.now()), app.out.locale)}.`);
    });

  reminders
    .command('done')
    .argument('<reminder>', 'Reminder id (or its start)')
    .description('Mark a reminder done')
    .action(async (query) => {
      const api = await app.api();
      const reminder = await resolveReminder(api, query);
      await api.call(remindersMarkDone, { path: { reminder_id: reminder.id } });
      app.out.done({ id: reminder.id, status: 'done' }, `Done: ${humanize(reminder.kind)}.`);
    });

  reminders
    .command('delete')
    .argument('<reminder>', 'Reminder id (or its start)')
    .description('Delete a reminder')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const reminder = await resolveReminder(api, query);
      if (!(await confirmAction(app, opts.yes, `Delete the reminder “${humanize(reminder.kind)}”?`))) return;
      await api.call(remindersDelete, { path: { reminder_id: reminder.id } });
      app.out.done({ id: reminder.id, deleted: true }, 'Reminder deleted.');
    });

  reminders
    .command('seed')
    .description('Add the tax filing deadlines for a year of assessment')
    .option('--year <year>', 'Year of assessment, e.g. 2025/26 (default: the server’s)')
    .action(async (opts) => {
      const api = await app.api();
      const result = await api.call(remindersSeedFilingCalendar, { query: opts.year ? { year: opts.year } : {} });
      app.out.done(result, `Added ${result.created} filing deadline${result.created === 1 ? '' : 's'}.`);
    });

  reminders
    .command('sync-alerts')
    .description('Check budgets, subscriptions and insurance now, and raise alerts')
    .action(async () => {
      const api = await app.api();
      const result = await api.call(remindersSyncAlerts);
      app.out.emit(result, {
        human: (r) => {
          if (!r.total) return app.out.success('Nothing needs your attention.');
          app.out.success(`${r.total} alert${r.total === 1 ? '' : 's'}: ${Object.entries(r.counts).filter(([, n]) => n).map(([k, n]) => `${n} ${humanize(k).toLowerCase()}`).join(', ')}.`);
        },
      });
    });
}

// ── Reports ──────────────────────────────────────────────────────────────────

const REPORT_TYPES = ['balance-sheet', 'net-worth', 'goal-progress'] as const;

function registerReports(program: Command, app: App): void {
  const reports = program.command('reports').alias('report').description('Statements of where you stand: balance sheet, net worth, goals');

  reports
    .command('balance-sheet')
    .alias('bs')
    .description('What you own, what you owe, and your net worth')
    .action(async () => {
      const api = await app.api();
      const bs = await api.call(reportsBalanceSheet);
      const lines = [
        ...bs.assets.map((l) => ({ section: 'asset', ...l })),
        ...bs.liabilities.map((l) => ({ section: 'liability', ...l })),
        ...bs.equity.map((l) => ({ section: 'equity', ...l })),
      ];
      app.out.emit(bs, {
        records: () => lines.map((l) => ({ ...l, currency: bs.currency })),
        human: () => {
          const out = app.out;
          const c = out.colors;
          const cur = bs.currency;
          const all = [...lines.map((l) => out.amount(l.balance, cur)), out.amount(bs.total_assets, cur), out.amount(bs.net_worth, cur)];
          const amountWidth = Math.max(...all.map((a) => displayWidth(a)));
          const nameWidth = Math.max(16, ...lines.map((l) => displayWidth(singleLine(`${l.code} ${l.name}`)) + 2));
          const row = (label: string, amount: string, strong = false): string => {
            const text = `${padEnd(label, nameWidth)}  ${padStart(amount, amountWidth)}`;
            return strong ? c.bold(text) : text;
          };
          const section = (title: string, items: typeof lines, total: string): void => {
            out.line(c.bold(title));
            if (!items.length) out.line(c.dim('  none'));
            for (const l of items) out.line(row(`  ${singleLine(`${l.code} ${l.name}`)}`, out.amount(l.balance, cur)));
            out.line(row(`Total ${title.toLowerCase()}`, out.amount(total, cur), true));
            out.line();
          };
          out.line(c.dim(`In ${cur}`));
          section('Assets', lines.filter((l) => l.section === 'asset'), bs.total_assets);
          section('Liabilities', lines.filter((l) => l.section === 'liability'), bs.total_liabilities);
          if (bs.equity.length) section('Equity', lines.filter((l) => l.section === 'equity'), bs.total_equity);
          out.line(row('Net worth', out.signed(out.amount(bs.net_worth, cur), bs.net_worth), true));
        },
      });
    });

  reports
    .command('net-worth')
    .description('Your net worth now, and how it has moved')
    .action(async () => {
      const api = await app.api();
      const r = await api.call(reportsNetWorth);
      app.out.emit(r, {
        records: (d) => d.trend,
        human: (d) => {
          const out = app.out;
          out.line(`${out.heading('Net worth')} ${out.signed(out.money(d.current_net_worth, d.currency), d.current_net_worth)}${d.as_of ? out.colors.dim(` as of ${displayDate(d.as_of, out.locale)}`) : ''}`);
          if (!d.trend.length) return;
          out.line();
          out.line(
            out.table(d.trend.slice(-12), [
              { header: 'DATE', get: (t) => displayDate(t.date, out.locale) },
              { header: `NET WORTH (${d.currency})`, get: (t) => out.amount(t.net_worth, d.currency), align: 'right' },
            ]),
          );
        },
      });
    });

  reports
    .command('goal-progress')
    .description('Progress towards your goals')
    .action(async () => {
      const api = await app.api();
      const r = await api.call(reportsGoalProgress);
      app.out.emit(r, {
        records: (d) => d.goals,
        human: (d) => {
          const out = app.out;
          if (!d.goals.length) return out.note('No goals yet. Add one with `salli goals add`.');
          out.line(
            out.table(d.goals, [
              { header: 'GOAL', get: (g) => g.name, shrink: true },
              { header: 'TARGET', get: (g) => out.money(g.target_amount, g.currency), align: 'right' },
              { header: 'FUNDED', get: (g) => out.amount(g.current_amount, g.currency), align: 'right' },
              { header: 'PROGRESS', get: (g) => out.percent(g.progress, 0), align: 'right' },
            ]),
          );
          out.note(`${d.completed_count} reached, ${d.in_progress_count} in progress.`);
        },
      });
    });

  reports
    .command('export')
    .argument('<report>', `One of: ${REPORT_TYPES.join(', ')}`)
    .description('A report as CSV, to a file or stdout')
    .option('-o, --out <file>', 'Write it to this file (default: stdout)')
    .action(async (type, opts) => {
      if (!(REPORT_TYPES as readonly string[]).includes(type)) {
        throw new UsageError(`Unknown report "${type}".`, `Reports: ${REPORT_TYPES.join(', ')}`);
      }
      const api = await app.api();
      const csv = textOf(await api.call(reportsExportCsv, { path: { report_type: type }, parseAs: 'text' }));
      await writeOutput(app, csv, opts.out, { report: type }, `the ${type} report`);
    });
}

// ── Tax ──────────────────────────────────────────────────────────────────────

function taxView(app: App, t: TaxComputation): void {
  const out = app.out;
  const cur = t.currency;
  out.line(`${out.heading(`Income tax ${t.pack_year}`)} ${out.colors.dim(`${t.pack_country} pack v${t.pack_version} · not tax advice`)}`);
  if (t.band_workings.length) {
    out.line(
      out.table(t.band_workings, [
        { header: 'BAND', get: (b) => b.band },
        { header: 'RATE', get: (b) => b.rate, align: 'right' },
        { header: `TAXABLE (${cur})`, get: (b) => out.amount(b.taxable_in_band, cur), align: 'right' },
        { header: `TAX (${cur})`, get: (b) => out.amount(b.tax, cur), align: 'right' },
      ]),
    );
    out.line();
  }
  const m = (amount: string): string => out.money(amount, cur);
  const nonzero = (amount: string): boolean => compareAmounts(amount, '0') !== 0;
  out.line(
    out.details([
      ['Gross income', m(t.gross_income)],
      nonzero(t.foreign_service_income) && ['Foreign service income', m(t.foreign_service_income)],
      ['Personal relief', m(t.personal_relief_applied)],
      nonzero(t.qp_deduction) && ['Qualifying payments', m(t.qp_deduction)],
      ['Taxable income', m(t.taxable_income)],
      nonzero(t.fsi_tax) && ['Tax on foreign income', m(t.fsi_tax)],
      ['Tax before credits', m(t.tax_before_credits)],
      nonzero(t.total_credits) && ['Credits (APIT, AIT, FTC)', m(t.total_credits)],
      ['Tax payable', m(t.tax_payable), out.colors.bold],
      nonzero(t.refund_due) && ['Refund due', m(t.refund_due), out.colors.green],
    ]),
  );
}

function registerTax(program: Command, app: App): void {
  const tax = program.command('tax').description('Income tax, by the versioned rules of your country’s tax pack');

  tax
    .command('packs')
    .description('The tax packs this server has')
    .action(async () => {
      const api = await app.api();
      const packs = await api.call(taxPacks);
      app.out.emit(packs, {
        human: (d) => {
          app.out.line(
            app.out.table(d, [
              { header: 'COUNTRY', get: (p) => p.country },
              { header: 'YEAR', get: (p) => p.year },
              { header: 'VERSION', get: (p) => p.version },
              { header: 'CURRENCY', get: (p) => p.currency },
              { header: 'PERIOD', get: (p) => displayRange(p.period_start, p.period_end, app.out.locale) },
              { header: 'RETURN DUE', get: (p) => displayDate(p.return_due, app.out.locale) },
            ]),
          );
        },
      });
    });

  tax
    .command('year')
    .description('The tax year you are in today, and the latest one Salli can compute')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(taxCurrentYear);
      app.out.emit(data, {
        human: (d) => {
          const out = app.out;
          if (!d.country) {
            out.warn('Salli does not know where you are taxed.');
            out.note('Set it with `salli profile set --tax-residency <country>`, e.g. LK or GB.');
            return;
          }
          const from = d.country_source === 'tax_residency' ? 'your tax residency' : 'your base currency';
          out.line(
            out.details([
              ['Country', `${d.country} (from ${from})`],
              ['Tax year', d.year ? `${d.year} (${displayRange(d.start, d.end, out.locale)})` : 'Salli has no tax pack for it yet'],
              ['Can compute', d.latest_year ? `${d.latest_year}${d.has_pack ? '' : ' (no pack for the current year yet)'}` : 'none yet'],
            ]),
          );
        },
      });
    });

  tax
    .command('compute')
    .description('Compute your income tax from the ledger (and store the result)')
    .option('--year <year>', 'Year of assessment, e.g. 2025/26 (default: the server’s)')
    .action(async (opts) => {
      const api = await app.api();
      const t = await api.call(taxCompute, { query: opts.year ? { year: opts.year } : {} });
      app.out.emit(t, { records: (d) => d.band_workings, human: (d) => taxView(app, d) });
    });

  tax
    .command('latest')
    .description('The last stored computation for a year')
    .option('--year <year>', 'Year of assessment (default: the server’s)')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(taxLatest, { query: opts.year ? { year: opts.year } : {} });
      if (!data.result && !app.out.machine) {
        throw new CliError('No stored computation for that year.', { exitCode: 4, kind: 'not-found', hint: 'Run `salli tax compute`.' });
      }
      app.out.emit(data, { human: (d) => d.result && taxView(app, d.result) });
    });
}

// ── Documents ────────────────────────────────────────────────────────────────

function registerDocuments(program: Command, app: App): void {
  const documents = program.command('documents').alias('docs').description('Files and notes the AI keeps for you (receipts, memories)');
  const resolveDoc = async (api: SalliClient, query: string): Promise<AgentDocument> =>
    resolveById((await api.call(documentsList)).documents, query, 'document');

  documents
    .command('list')
    .alias('ls')
    .description('List documents')
    .option('--search <text>', 'Search titles and contents')
    .addOption(new Option('--namespace <ns>', 'documents or memories').choices(['documents', 'memories']))
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(documentsList, {
        query: { ...(opts.search ? { search: opts.search } : {}), ...(opts.namespace ? { namespace: opts.namespace } : {}) },
      });
      app.out.emit(data, {
        records: (d) => d.documents,
        human: (d) => {
          if (!d.documents.length) return app.out.note('No documents.');
          app.out.line(
            app.out.table(d.documents, [
              { header: 'ID', get: (x) => x.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'TITLE', get: (x) => x.title, shrink: true },
              { header: 'KIND', get: (x) => x.namespace },
              { header: 'TYPE', get: (x) => x.mime_type },
              { header: 'ADDED', get: (x) => displayDate(x.created_at, app.out.locale) },
            ]),
          );
        },
      });
    });

  documents
    .command('show')
    .argument('<document>', 'Document id (or its start)')
    .description('Show a document')
    .action(async (query) => {
      const api = await app.api();
      const doc = await resolveDoc(api, query);
      const data = await api.call(documentsGet, { path: { doc_id: doc.id } });
      app.out.emit(data, {
        human: (d) => {
          app.out.line(renderRecord(app, d, { hide: ['content'] }));
          if (d.content) {
            app.out.line();
            app.out.line(d.content.replace(/\r\n/g, '\n'));
          }
        },
      });
    });

  documents
    .command('upload')
    .argument('<file>', 'A file: PDF, image, CSV, text, Excel')
    .description('Store a file (e.g. a receipt to attach: salli entries add --receipt <id>)')
    .action(async (file) => {
      const upload = await readUpload(file);
      const api = await app.api();
      const result = await api.call(agentFilesUpload, { body: { file: upload }, timeoutMs: 120_000 });
      if (app.out.machine) app.out.emit(result, { human: () => undefined });
      else app.out.success(`Stored ${singleLine(result.name)} ${app.out.errColors.dim(result.file_ref)}`);
    });

  documents
    .command('delete')
    .argument('<document>', 'Document id (or its start)')
    .description('Delete a document')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const doc = await resolveDoc(api, query);
      if (!(await confirmAction(app, opts.yes, `Delete “${str(doc.title)}”?`))) return;
      await api.call(documentsDelete, { path: { doc_id: doc.id } });
      app.out.done({ id: doc.id, deleted: true }, `Deleted “${str(doc.title)}”.`);
    });
}

// ── Profile and your data ────────────────────────────────────────────────────

function registerProfile(program: Command, app: App): void {
  const profile = program.command('profile').description('Your profile: name, base currency, and what tax and planning need to know');

  profile
    .command('get')
    .alias('show')
    .description('Show your profile')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(profileGet);
      app.out.emit(data, {
        human: (d) => {
          const ids = d.tax_ids ?? [];
          const own = Object.entries(d.fi_assumptions ?? {}).filter(([, v]) => v !== null && v !== undefined);
          app.out.line(
            renderRecord(app, d, {
              hide: ['tax_ids', 'fi_assumptions'],
              extra: [
                ['Tax ids', ids.length ? ids.map((t) => `${t.scheme} ${t.value}`).join(', ') : undefined],
                ['FI assumptions', own.length ? own.map(([k, v]) => `${k.replace(/_/g, ' ')} ${app.out.percent(v, 2)}`).join(', ') : undefined],
              ],
            }),
          );
        },
      });
    });

  profile
    .command('set')
    .description('Change your profile')
    .option('--name <name>', 'Display name')
    .option('--base-currency <code>', 'The currency your ledger is kept in (only while it is empty)')
    .option('--birth-date <date>', 'Date of birth (YYYY-MM-DD)')
    .option('--dependents <n>', 'Number of dependents', countArg('--dependents'))
    .addOption(new Option('--employment-status <status>', 'Employment status').choices(['employed', 'self_employed', 'unemployed', 'student', 'retired']))
    .addOption(new Option('--employment-type <type>', 'Employment type').choices(['permanent', 'contract', 'self_employed', 'other']))
    .addOption(new Option('--residency <status>', 'Tax residency').choices(['resident', 'non_resident']))
    .option('--employer <name>', 'Employer')
    .option('--tax-residency <country>', 'The country you are taxed in, as a code (LK, GB, US…); "none" clears it')
    .option('--tax-id <scheme=number>', 'A tax id, e.g. LK-TIN=123456789 (repeatable); SCHEME= removes one', collect)
    .option('--ird-number <number>', 'Your Sri Lankan taxpayer number (LK-TIN)')
    .option('--nic <number>', 'Your Sri Lankan national identity card number (LK-NIC)')
    .option('--fi-inflation <rate>', 'Your own yearly inflation for FI plans, e.g. 3%; "none" for the default')
    .option('--fi-real-return <rate>', 'Your own yearly return after inflation, e.g. 4%; "none" for the default')
    .option('--fi-swr <rate>', 'Your own safe withdrawal rate, e.g. 3.5%; "none" for the default')
    .action(async (opts) => {
      const rate = (value: string | undefined, flag: string): string | null | undefined =>
        value === undefined ? undefined : value.trim().toLowerCase() === 'none' ? null : rateArg(value, flag);
      const own = Object.fromEntries(
        Object.entries({
          inflation: rate(opts.fiInflation, '--fi-inflation'),
          real_return: rate(opts.fiRealReturn, '--fi-real-return'),
          safe_withdrawal_rate: rate(opts.fiSwr, '--fi-swr'),
        }).filter(([, v]) => v !== undefined),
      );
      const residency = opts.taxResidency?.trim();
      if (residency && residency.toLowerCase() !== 'none' && !/^[A-Za-z]{2}$/.test(residency)) {
        throw new UsageError(`A country is a two-letter code like LK or GB (got "${opts.taxResidency}").`);
      }
      const idChanges = (opts.taxId ?? []).map((raw) => {
        const at = raw.indexOf('=');
        if (at <= 0) throw new UsageError(`--tax-id takes SCHEME=NUMBER, e.g. LK-TIN=123456789 (got "${raw}").`);
        return { scheme: raw.slice(0, at).trim().toUpperCase(), value: raw.slice(at + 1).trim() };
      });
      const body: ProfileIdentityRequest = Object.fromEntries(
        Object.entries({
          display_name: opts.name,
          base_currency: opts.baseCurrency ? currencyArg(opts.baseCurrency) : undefined,
          date_of_birth: opts.birthDate ? parseDate(opts.birthDate, app.runtime.now(), '--birth-date') : undefined,
          dependents_count: opts.dependents,
          employment_status: opts.employmentStatus,
          employment_type: opts.employmentType,
          residency_status: opts.residency,
          employer: opts.employer,
          tax_residency: residency === undefined ? undefined : residency.toLowerCase() === 'none' ? null : residency.toUpperCase(),
          ird_number: opts.irdNumber,
          nic: opts.nic,
          fi_assumptions: Object.keys(own).length ? own : undefined,
        }).filter(([, v]) => v !== undefined),
      );
      if (!Object.keys(body).length && !idChanges.length) {
        throw new UsageError('Nothing to change.', 'See `salli profile set --help` for what can be set.');
      }
      const api = await app.api();
      if (idChanges.length) {
        // Each sets or removes one scheme; the others stay as they are.
        const ids = new Map((await api.call(profileGet)).tax_ids?.map((t) => [t.scheme, t.value]) ?? []);
        for (const { scheme, value } of idChanges) {
          if (value) ids.set(scheme, value);
          else ids.delete(scheme);
        }
        body.tax_ids = [...ids].map(([scheme, value]) => ({ scheme, value }));
      }
      const result = await api.call(profileUpdate, { body });
      app.out.done(result, 'Profile updated.');
    });

  profile
    .command('export')
    .description('Download everything Salli stores about you, as one JSON file')
    .option('-o, --out <file>', 'Where to write it ("-" for stdout; default: salli-export-<date>.json)')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(accountExport, { timeoutMs: 5 * 60_000 });
      const text = `${toJsonText(data)}\n`;
      await writeOutput(app, text, opts.out ?? `salli-export-${isoDate(app.runtime.now())}.json`, {}, 'your data', { private: true });
    });
}

// ── Your LLM keys and MCP clients ────────────────────────────────────────────

function registerKeysAndMcp(program: Command, app: App): void {
  const keys = program.command('llm-keys').description('Your own AI provider key (used for every AI feature; never shown again)');

  keys
    .command('list')
    .alias('ls')
    .description('Which keys you have stored (the last four characters only)')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(llmKeysList);
      app.out.emit(data, {
        records: (d) => d.keys,
        human: (d) => {
          if (!d.available) app.out.warn('This server cannot store keys (it has no encryption key set).');
          if (!d.keys.length) return app.out.note('No keys stored. Add yours with `salli llm-keys set anthropic`.');
          app.out.line(
            app.out.table(d.keys, [
              { header: 'PROVIDER', get: (k) => k.provider },
              { header: 'KEY', get: (k) => `…${k.last4}` },
              { header: 'CHECKED', get: (k) => displayDate(k.validated_at, app.out.locale) },
              { header: '', get: (k) => (k.readable ? '' : 'unreadable: set it again'), style: (t) => app.out.colors.red(t) },
            ]),
          );
        },
      });
    });

  keys
    .command('set')
    .argument('[provider]', 'The provider', 'anthropic')
    .description('Store your key (checked with the provider first). Asks for it, or reads stdin')
    .action(async (provider) => {
      if (provider !== 'anthropic') throw new UsageError(`Unknown provider "${provider}".`, 'Providers: anthropic');
      let key: string;
      if (app.runtime.stdin.isTTY !== true) key = await readAllStdin(app.runtime.stdin);
      else key = await app.prompter.password({ message: 'Anthropic API key' });
      key = key.trim();
      if (!key) throw new UsageError('No key given.', 'Type it when asked, or pipe it in: salli llm-keys set < key.txt');
      const api = await app.api();
      await api.call(llmKeysSet, { path: { provider }, body: { key } });
      app.out.done({ provider, saved: true }, `Saved your ${provider} key.`);
    });

  keys
    .command('delete')
    .argument('[provider]', 'The provider', 'anthropic')
    .description('Remove your stored key')
    .action(async (provider) => {
      if (provider !== 'anthropic') throw new UsageError(`Unknown provider "${provider}".`, 'Providers: anthropic');
      const api = await app.api();
      await api.call(llmKeysDelete, { path: { provider } });
      app.out.done({ provider, deleted: true }, `Removed your ${provider} key.`);
    });

  const mcp = program.command('mcp').description('AI clients (Claude, ChatGPT) connected to your Salli over MCP');

  mcp
    .command('status')
    .description('Whether AI clients may connect')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(mcpEnabledGet);
      app.out.emit(data, { human: (d) => app.out.line(`MCP: ${d.enabled ? 'on' : 'off'}`) });
    });

  for (const [name, enabled, message] of [
    ['enable', true, 'MCP on: AI clients can connect (each one still asks you first).'],
    ['disable', false, 'MCP off: every connected AI client is cut off now.'],
  ] as const) {
    mcp
      .command(name)
      .description(enabled ? 'Let AI clients connect (each still asks for your approval)' : 'Cut off every AI client now, and refuse new ones')
      .action(async () => {
        const api = await app.api();
        await api.call(mcpEnabledSet, { body: { enabled } });
        app.out.done({ enabled }, message);
      });
  }

  mcp
    .command('connections')
    .description('AI clients connected now')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(mcpConnectionsList);
      app.out.emit(data, {
        records: (d) => d.connections,
        human: (d) => {
          if (!d.connections.length) return app.out.note('No AI clients connected.');
          app.out.line(
            app.out.table(d.connections, [
              { header: 'ID', get: (c) => c.token_id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'CLIENT', get: (c) => c.client_name, shrink: true },
              { header: 'SCOPE', get: (c) => c.scope },
              { header: 'CONNECTED', get: (c) => displayDate(c.connected_at, app.out.locale) },
            ]),
          );
        },
      });
    });

  mcp
    .command('revoke')
    .argument('<connection>', 'Connection id (or its start)')
    .description('Disconnect one AI client')
    .action(async (query) => {
      const api = await app.api();
      const { connections } = await api.call(mcpConnectionsList);
      const connection = resolveById(
        connections.map((c) => ({ ...c, id: c.token_id })),
        query,
        'connection',
      );
      await api.call(mcpConnectionsRevoke, { path: { token_id: connection.token_id } });
      app.out.done({ token_id: connection.token_id, revoked: true }, `Disconnected ${str(connection.client_name) || connection.token_id.slice(0, 8)}.`);
    });
}

/** Reminders, reports and tax. */
export function registerMore(program: Command, app: App): void {
  registerReminders(program, app);
  registerReports(program, app);
  registerTax(program, app);
}

/** Your profile and data, documents, LLM keys and MCP clients. */
export function registerYourData(program: Command, app: App): void {
  registerProfile(program, app);
  registerDocuments(program, app);
  registerKeysAndMcp(program, app);
}
