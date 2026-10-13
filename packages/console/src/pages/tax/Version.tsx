/**
 * A version of a tax rule set, reviewed and activated (docs/taxrules.md;
 * decision 6; `salli tax rules show --version`, `diff`, `validate`,
 * `propose`, `activate`, `export`): what the CLI's activation review
 * shows, as a page.
 *
 * - Its status, who wrote it (the person, or an agent and its name), its
 *   note and content hash.
 * - **What is new** against the active version (`tax.ruleSets.diff`): each
 *   change with its path, before and after, whether it is a figure, and the
 *   source it cites with that source's link.
 * - **Worked examples**, each passing or failing with every mismatch, and
 *   any problem the validator found, at its path.
 * - Its sources (links only to https), its deadlines, and the canonical
 *   document saved on this device (`tax.ruleSets.versions.export`).
 * - **Activate**, for a version that compiles and whose examples all pass,
 *   after a confirmation that says what Salli will do and who wrote it.
 *   A console sign-in holds `tax:activate` only within five minutes of its
 *   password: past that, Salli answers `/problems/step-up-required`, and
 *   the console sends the person through Salli's own sign-in page with
 *   `prompt=login`, checks it is the same person, and activates on return
 *   (`useWrite`, C1). Only a person activates, never an AI: the page says
 *   so.
 */
import {
  taxRuleSetsDiff,
  taxRuleSetsGet,
  taxRuleSetsVersionsActivate,
  taxRuleSetsVersionsExport,
  taxRuleSetsVersionsGet,
  taxRuleSetsVersionsPropose,
  taxRuleSetsVersionsValidate,
  type TaxRuleChange,
  type TaxRuleProblem,
  type TaxRuleSet,
  type TaxRuleSetVersion,
} from '@leafmonkeylabs/salli-sdk';
import { Link, useParams } from '@tanstack/react-router';
import { useState } from 'react';
import { useApi, useRead, useWrite } from '../../api';
import { isStepUpRequired } from '../../auth/session';
import { displayDate, displayMoment } from '../../kit/dates';
import { saveText } from '../../kit/download';
import { Button, Confirm } from '../../kit/forms';
import { Empty, Grid, Loaded, Page, Panel, Section } from '../../kit/layout';
import { ProblemView } from '../../kit/Problem';
import { useLocale } from '../../preferences';
import { strings } from '../../strings';
import { taxStrings } from '../../tax-strings';
import { deadlinesOf, shownValue, sourcesOf, type Source } from './document';
import { authorOf, ruleSetPath, SourceLink, StatusTag } from './parts';

const v = taxStrings.version;
const RULE_READS = ['tax.ruleSets.get', 'tax.ruleSets.list', 'tax.ruleSets.versions.get', 'tax.ruleSets.diff', 'tax.currentYear', 'tax.latest', 'reminders.list'];

interface Target {
  ruleSet: string;
  version: string;
}

function Changes({ set, version }: { set: TaxRuleSet; version: TaxRuleSetVersion }) {
  const active = set.versions.find((x) => x.id === set.active_version_id);
  const enabled = Boolean(active && active.id !== version.id);
  const query = useRead('tax.ruleSets.diff', taxRuleSetsDiff, { path: { rule_set_id: set.id }, query: { to: version.id } }, { enabled });
  const sources = new Map(sourcesOf(version.document).map((s) => [s.id, s]));
  return (
    <Section label={v.whatsNew} full>
      <Panel>
        {!active ? (
          <p>{v.first}</p>
        ) : !enabled ? (
          <p>{v.sameAsActive}</p>
        ) : (
          <Loaded query={query}>
            {(diff) => {
              const all: Map<string, Source> = new Map([...sources]);
              for (const [id, raw] of Object.entries(diff.sources)) {
                const found = sourcesOf({ sources: [raw] })[0];
                if (found && !all.has(id)) all.set(id, found);
              }
              return (
                <div className="stack-tight">
                  <p className="section-help">{v.whatsNewAgainst(active.version)}</p>
                  {diff.changes.length ? (
                    <ul className="list changes">
                      {diff.changes.map((change: TaxRuleChange) => {
                        const source = change.source ? all.get(change.source) : undefined;
                        return (
                          <li key={`${change.kind}-${change.path}`} className="change-item">
                            <p className="signal-title">
                              <span className="tag">{v.kinds[change.kind] ?? change.kind}</span> <code className="mono">{change.path}</code>
                              {change.figure ? <span className="tag tag-due"> {v.aFigure}</span> : null}
                            </p>
                            <dl className="change-values">
                              {change.kind !== 'added' ? (
                                <>
                                  <dt>{v.before}</dt>
                                  <dd className="mono change-value">{shownValue(change.before) || v.nothing}</dd>
                                </>
                              ) : null}
                              {change.kind !== 'removed' ? (
                                <>
                                  <dt>{v.after}</dt>
                                  <dd className="mono change-value">{shownValue(change.after) || v.nothing}</dd>
                                </>
                              ) : null}
                            </dl>
                            <p className="muted">{source ? (
                                <>
                                  {v.cites} <SourceLink source={source} />
                                </>
                              ) : change.figure ? (
                                v.citesNothing
                              ) : null}</p>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p>{v.noChanges}</p>
                  )}
                </div>
              );
            }}
          </Loaded>
        )}
      </Panel>
    </Section>
  );
}

function Problems({ label, problems }: { label: string; problems: readonly TaxRuleProblem[] }) {
  if (!problems.length) return null;
  return (
    <div className="stack-tight">
      <p className="field-label">{label}</p>
      <ul className="list">
        {problems.map((p, i) => (
          <li key={i}>
            <p>
              <code className="mono">{v.at(p.path)}</code> {p.message}
            </p>
            {p.snippet ? <pre className="snippet">{p.snippet}</pre> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Examples({ version }: { version: TaxRuleSetVersion }) {
  const { examples, errors, warnings } = version.validation;
  return (
    <Section label={v.examples} full>
      <Panel>
        <p className="section-help">{v.examplesHelp}</p>
        {examples.length ? (
          <ul className="list">
            {examples.map((e) => (
              <li key={e.name} className="example">
                <p className="signal-title">
                  {e.passed ? (
                    <span className="check-mark check-keeps" aria-hidden="true">
                      ✓
                    </span>
                  ) : (
                    <span className="warn-mark" aria-hidden="true">
                      !
                    </span>
                  )}{' '}
                  {e.name} <span className={e.passed ? 'tag' : 'tag tag-warn'}>{e.passed ? v.passes : v.fails}</span>
                </p>
                {e.error ? <p className="warn-line">{v.exampleError(e.error)}</p> : null}
                {e.mismatches.map((m, i) => (
                  <p key={i} className="warn-line mono">
                    {v.mismatch(m.key, m.expected, m.got, m.expr)}
                  </p>
                ))}
              </li>
            ))}
          </ul>
        ) : (
          <Empty>{v.noExamples}</Empty>
        )}
        {errors.length || warnings.length ? (
          <div className="stack-tight">
            <h3 className="subhead">{v.problems}</h3>
            <Problems label={v.errors} problems={errors} />
            <Problems label={v.warningsLabel} problems={warnings} />
          </div>
        ) : null}
      </Panel>
    </Section>
  );
}

function Sources({ version }: { version: TaxRuleSetVersion }) {
  const locale = useLocale();
  const sources = sourcesOf(version.document);
  const deadlines = deadlinesOf(version.document);
  return (
    <>
      <Section label={v.sources}>
        <Panel>
          <p className="section-help">{v.sourcesHelp}</p>
          {sources.length ? (
            <ul className="list">
              {sources.map((s) => (
                <li key={s.id} className="stack-tight">
                  <p className="signal-title">
                    <SourceLink source={s} />
                  </p>
                  <p className="muted mono source-url">{s.url}</p>
                  {s.retrieved ? <p className="muted">{v.retrieved(displayDate(s.retrieved, locale))}</p> : null}
                </li>
              ))}
            </ul>
          ) : (
            <Empty>{v.noSources}</Empty>
          )}
        </Panel>
      </Section>
      <Section label={v.deadlines}>
        <Panel>
          {deadlines.length ? (
            <ul className="list">
              {deadlines.map((d) => (
                <li key={d.key} className="dated">
                  <span className="dated-date">{displayDate(d.date, locale)}</span>
                  <span>{d.label}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>{v.noDeadlines}</Empty>
          )}
        </Panel>
      </Section>
    </>
  );
}

function Document({ target, version }: { target: Target; version: TaxRuleSetVersion }) {
  const api = useApi();
  const [state, setState] = useState<{ busy: boolean; error?: unknown }>({ busy: false });
  const save = async (): Promise<void> => {
    setState({ busy: true });
    try {
      const exported = await api.call(taxRuleSetsVersionsExport, { path: { rule_set_id: target.ruleSet, version_id: target.version } });
      saveText(exported.filename, exported.text, 'application/json');
      setState({ busy: false });
    } catch (error) {
      setState({ busy: false, error });
    }
  };
  return (
    <Section label={v.document} full>
      <Panel>
        <p className="section-help">{v.documentHelp}</p>
        <p className="provenance mono hash">{version.content_hash ? v.hash(version.content_hash) : v.noHash}</p>
        <div className="form-actions">
          <Button variant="secondary" onPress={() => void save()} isPending={state.busy}>
            {state.busy ? v.saving : v.save}
          </Button>
        </div>
        {state.error ? <ProblemView error={state.error} compact /> : null}
      </Panel>
    </Section>
  );
}

function Activating({ target, set, version }: { target: Target; set: TaxRuleSet; version: TaxRuleSetVersion }) {
  const [asking, setAsking] = useState(false);
  const [said, setSaid] = useState('');
  const active = set.versions.find((x) => x.id === set.active_version_id);
  const activate = useWrite<Target, TaxRuleSetVersion>(
    'tax.ruleSets.versions.activate',
    (api, input) => api.call(taxRuleSetsVersionsActivate, { path: { rule_set_id: input.ruleSet, version_id: input.version } }),
    {
      invalidate: RULE_READS,
      onSuccess: (done) => {
        setAsking(false);
        setSaid(v.activated(set.name, done.version));
      },
    },
  );
  const validate = useWrite<Target, TaxRuleSetVersion>(
    'tax.ruleSets.versions.validate',
    (api, input) => api.call(taxRuleSetsVersionsValidate, { path: { rule_set_id: input.ruleSet, version_id: input.version } }),
    { invalidate: RULE_READS, onSuccess: (done) => setSaid(v.validated(taxStrings.statuses[done.status] ?? done.status)) },
  );
  const propose = useWrite<Target, TaxRuleSetVersion>(
    'tax.ruleSets.versions.propose',
    (api, input) => api.call(taxRuleSetsVersionsPropose, { path: { rule_set_id: input.ruleSet, version_id: input.version } }),
    { invalidate: RULE_READS, onSuccess: () => setSaid(v.proposed) },
  );
  const ready = (version.status === 'validated' || version.status === 'proposed') && version.validation.ok;
  // Back from Salli's sign-in page and still asked for the password: said, not followed again.
  const stillAsks = activate.retried && activate.isError && isStepUpRequired(activate.error);
  const failed = [activate, validate, propose].find((w) => w.isError && !w.stepUpPending && !(w === activate && stillAsks));
  return (
    <Section label={v.activating} full>
      <Panel>
        <p className="section-help">{taxStrings.statusHelp[version.status] ?? ''}</p>
        <p className="only-a-person">{taxStrings.ruleSet.onlyAPerson}</p>
        {version.status === 'active' ? <p>{v.isActive}</p> : null}
        {version.status === 'superseded' ? <p>{v.isSuperseded}</p> : null}
        {!ready && version.status !== 'active' && version.status !== 'superseded' ? <p>{v.cannotActivate}</p> : null}
        <div className="form-actions">
          {ready ? (
            <Button
              onPress={() => {
                setSaid('');
                activate.reset();
                setAsking(true);
              }}
            >
              {v.activate(version.version)}
            </Button>
          ) : null}
          {version.status !== 'active' && version.status !== 'superseded' ? (
            <Button variant="secondary" onPress={() => validate.mutate(target)} isPending={validate.isPending}>
              {validate.isPending ? v.validating : v.validate}
            </Button>
          ) : null}
          {version.status === 'validated' ? (
            <Button variant="tertiary" onPress={() => propose.mutate(target)} isPending={propose.isPending}>
              {propose.isPending ? v.proposing : v.propose}
            </Button>
          ) : null}
        </div>
        <p role="status" className="quiet-success">
          {said ? (
            <>
              <span aria-hidden="true">✓</span> {said} {activate.isSuccess ? <Link to="/tax">{v.seeTax}</Link> : null}
            </>
          ) : activate.stepUpPending ? (
            v.stepUp
          ) : null}
        </p>
        {stillAsks ? <p className="warn-line">{v.stepUpAgain}</p> : null}
        {failed ? <ProblemView error={failed.error} compact /> : null}
        <Confirm
          isOpen={asking}
          onOpenChange={setAsking}
          title={v.activateTitle(version.version)}
          confirmLabel={v.activateConfirm}
          cancelLabel={v.cancel}
          isPending={activate.isPending}
          onConfirm={() => activate.mutate(target)}
        >
          <p>{v.activateBody(set.name, version.version, active ? taxStrings.version.title(set.name, active.version) : '')}</p>
          <p>{v.activateWho(authorOf(version))}</p>
          <p>{v.activateStepUp}</p>
        </Confirm>
      </Panel>
    </Section>
  );
}

export function Version() {
  const locale = useLocale();
  const params = useParams({ strict: false }) as { ruleSet?: string; version?: string };
  const target: Target = { ruleSet: decodeURIComponent(params.ruleSet ?? ''), version: decodeURIComponent(params.version ?? '') };
  const set = useRead('tax.ruleSets.get', taxRuleSetsGet, { path: { rule_set_id: target.ruleSet } });
  const query = useRead('tax.ruleSets.versions.get', taxRuleSetsVersionsGet, { path: { rule_set_id: target.ruleSet, version_id: target.version } });
  const version = query.data;
  const name = set.data?.name ?? '';
  const title = version && set.data ? v.title(name, version.version) : query.isError ? v.notFound : taxStrings.tax.title;
  const when = (value: string | null | undefined): string => (value ? displayMoment(value, locale) : '');
  const description = version
    ? [
        version.author_kind === 'agent' ? v.byAgent(version.author_name ?? '', when(version.created_at)) : v.byYou(when(version.created_at)),
        version.change_note ? `“${version.change_note}”` : '',
        version.proposed_at && version.status === 'proposed' ? v.proposedOn(when(version.proposed_at)) : '',
        version.activated_at ? v.activatedOn(when(version.activated_at)) : '',
        version.superseded_at ? v.supersededOn(when(version.superseded_at)) : '',
      ]
        .filter(Boolean)
        .join(' ')
    : undefined;
  return (
    <Page title={title} {...(description ? { description } : {})} actions={version ? <StatusTag status={version.status} /> : undefined}>
      <p>
        <Link to={ruleSetPath(target.ruleSet)}>{name ? v.back(name) : strings.loading}</Link>
      </p>
      <Grid>
        <Loaded query={query}>
          {(found) => (
            <Loaded query={set}>
              {(rules) => (
                <>
                  <Changes set={rules} version={found} />
                  <Examples version={found} />
                  <Sources version={found} />
                  <Activating target={target} set={rules} version={found} />
                  <Document target={target} version={found} />
                </>
              )}
            </Loaded>
          )}
        </Loaded>
      </Grid>
    </Page>
  );
}

export default Version;
