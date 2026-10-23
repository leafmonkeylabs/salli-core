/**
 * Tax (docs/design/console.md, section 5; docs/taxrules.md; `salli tax
 * year`, `latest`, `compute`, `explain`, `salli tax rules list`): the
 * current tax year and the rules computing it (`tax.currentYear`); the last
 * computation (`tax.latest`), its result, what it took from the books and
 * every line with its expression and source, each explained on request
 * (`tax.explain`, nothing stored); computing again now (`tax.compute`,
 * kept); the deadlines the active rules name; and every rule set with its
 * active and newest versions (`tax.ruleSets.list`).
 *
 * Every figure is the engine's, from rules the person activated: the
 * console adds nothing up.
 */
import {
  taxCompute,
  taxCurrentYear,
  taxExplain,
  taxLatest,
  taxRuleSetsList,
  taxRuleSetsVersionsGet,
  type TaxComputation,
  type TaxLineExplanation,
  type TaxRuleSet,
  type TaxYearStatus,
} from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useState } from 'react';
import { useApi, useRead, useWrite } from '../../api';
import { displayDate, displayMoment, displayRange } from '../../kit/dates';
import { Button } from '../../kit/forms';
import { Blank, Empty, Grid, Loaded, Page, Panel, Provenance, Row, Rows, Section } from '../../kit/layout';
import { Money } from '../../kit/Money';
import { ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { taxStrings } from '../../tax-strings';
import { deadlinesOf, sourcesOf } from './document';
import { ruleSetPath, SourceLink, StatusTag, versionPath } from './parts';

const t = taxStrings.tax;
const TAX_READS = ['tax.latest', 'tax.currentYear'];

function Year({ year }: { year: TaxYearStatus }) {
  const locale = useLocale();
  if (!year.country) return <Empty>{t.noCountry}</Empty>;
  return (
    <>
      <Rows>
        <Row label={t.country}>{t.countryIs(year.region ? `${year.country}, ${year.region}` : year.country, t.countryFrom[year.country_source ?? 'given'] ?? '')}</Row>
        {year.year ? <Row label={t.yearIs}>{t.yearRange(year.year, year.start && year.end ? displayRange(year.start, year.end, locale) : '')}</Row> : null}
        {year.rule_set_id && year.rule_set_version_id && year.version !== null ? (
          <Row label={t.rulesUsed}>
            <Link to={versionPath(year.rule_set_id, year.rule_set_version_id)}>{t.version(`${year.country} ${year.year ?? ''}`.trim(), year.version)}</Link>
          </Row>
        ) : null}
      </Rows>
      {!year.rule_set_id && !year.latest_year ? <p className="section-help">{t.noRules}</p> : null}
    </>
  );
}

function Explanation({ explained, currency, onClose }: { explained: TaxLineExplanation; currency: string; onClose: () => void }) {
  const line = explained.line;
  return (
    <div className="explanation stack-tight" role="region" aria-label={t.explained(line.label)}>
      <h3 className="subhead">{t.explained(line.label)}</h3>
      <p>
        <Money amount={line.amount} currency={currency} /> = <code className="mono">{line.expr}</code>
      </p>
      <p className="muted">{t.writtenAt(line.path, line.block ?? '')}</p>
      {line.source ? (
        <p>
          {t.citing}: <SourceLink source={{ id: line.source.id, url: line.source.url, title: line.source.title, retrieved: line.source.retrieved }} />
        </p>
      ) : null}
      {explained.inputs.length || explained.lines.length ? (
        <>
          <p className="field-label">{t.uses}</p>
          <Rows>
            {explained.inputs.map((i) => (
              <Row key={`role-${i.key}`} label={`${i.label} (${t.kinds[i.kind] ?? i.kind})`}>
                <Money amount={i.total} currency={currency} />
              </Row>
            ))}
            {explained.lines.map((l) => (
              <Row key={`line-${l.key}`} label={l.label}>
                <Money amount={l.amount} currency={currency} />
              </Row>
            ))}
          </Rows>
        </>
      ) : (
        <p className="muted">{t.usesNothing}</p>
      )}
      {explained.answers.length ? (
        <>
          <p className="field-label">{t.answers}</p>
          <Rows>
            {explained.answers.map((a) => (
              <Row key={a.key} label={a.label}>
                {String(a.value)}
                {a.default ? ` (${t.answerDefault})` : ''}
              </Row>
            ))}
          </Rows>
        </>
      ) : null}
      {explained.tables.map((table) => (
        <div key={table.key} className="stack-tight">
          <p className="field-label">{t.bands(table.label ?? table.key)}</p>
          <Rows>
            {table.bands.map((band, i) => (
              <Row key={i} label={band.upto ? t.upTo(band.upto) : t.above}>
                {band.rate}
              </Row>
            ))}
          </Rows>
          {table.source ? (
            <p>
              {t.citing}: <SourceLink source={{ id: table.source.id, url: table.source.url, title: table.source.title, retrieved: table.source.retrieved }} />
            </p>
          ) : null}
        </div>
      ))}
      {explained.used_by.length ? <p className="muted">{t.usedBy(explained.used_by.join(', '))}</p> : null}
      <div>
        <Button variant="tertiary" onPress={onClose}>
          {t.closeExplanation}
        </Button>
      </div>
    </div>
  );
}

function Computation({ result, year }: { result: TaxComputation; year: TaxYearStatus }) {
  const locale = useLocale();
  const api = useApi();
  const [open, setOpen] = useState<{ key: string; pending: boolean; explained?: TaxLineExplanation; error?: unknown } | null>(null);
  const ruleSetName = `${result.country}${result.region ? ` ${result.region}` : ''} ${result.year}`;
  const query = { ...(year.country_source === 'given' && year.country ? { country: year.country } : {}), year: result.year, ...(result.region ? { region: result.region } : {}) };
  const explain = async (key: string): Promise<void> => {
    setOpen({ key, pending: true });
    try {
      setOpen({ key, pending: false, explained: await api.call(taxExplain, { body: { line_key: key, answers: result.answers }, query }) });
    } catch (error) {
      setOpen({ key, pending: false, error });
    }
  };
  return (
    <div className="stack">
      <Rows>
        <Row label={t.net}>
          <Money amount={result.net} currency={result.currency} />
        </Row>
        <Row label={t.payable}>
          <Money amount={result.tax_payable} currency={result.currency} />
        </Row>
        <Row label={t.refund}>
          <Money amount={result.refund_due} currency={result.currency} />
        </Row>
      </Rows>
      <Provenance>
        {t.computedOn(result.created_at ? displayMoment(result.created_at, locale) : '')}{' '}
        <Link to={versionPath(result.rule_set_id, result.rule_set_version_id)}>{taxStrings.version.title(ruleSetName, result.version)}</Link>.
      </Provenance>
      <p className="provenance mono hash">{t.hash(result.content_hash)}</p>
      {result.warnings.length ? (
        <>
          <p className="field-label">{t.warnings}</p>
          <ul className="list">
            {result.warnings.map((w) => (
              <li key={w} className="warn-line">
                {w}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <div className="stack-tight">
        <h3 className="subhead">{t.lines}</h3>
        <p className="section-help">{t.linesHelp}</p>
        <Table
          caption={t.lines}
          captionHidden
          rows={result.lines}
          rowKey={(l) => l.key}
          columns={[
            { key: 'line', header: t.line, label: t.line, render: (l) => l.label },
            { key: 'expr', header: t.expression, label: t.expression, render: (l) => <code className="mono expr">{l.expr}</code> },
            { key: 'source', header: t.source, label: t.source, render: (l) => l.source ?? <Blank>{t.noSource}</Blank> },
            { key: 'amount', header: `${t.amount} (${result.currency})`, label: t.amount, align: 'end', render: (l) => <Money amount={l.amount} currency={result.currency} variant="table" /> },
            {
              key: 'explain',
              header: <span className="sr-only">{t.explain}</span>,
              label: '',
              align: 'end',
              render: (l) => (
                <Button variant="tertiary" aria-label={t.explainLabel(l.label)} onPress={() => void explain(l.key)} isPending={open?.key === l.key && open.pending}>
                  {t.explain}
                </Button>
              ),
            },
          ]}
        />
        <div aria-live="polite">
          {open?.pending ? <p className="muted">{t.explaining}</p> : null}
          {open?.error ? <ProblemView error={open.error} compact /> : null}
          {open?.explained ? <Explanation explained={open.explained} currency={result.currency} onClose={() => setOpen(null)} /> : null}
        </div>
      </div>
      <div className="stack-tight">
        <h3 className="subhead">{t.roles}</h3>
        <p className="section-help">{t.rolesHelp}</p>
        <Table
          caption={t.roles}
          captionHidden
          rows={result.roles}
          rowKey={(r) => r.key}
          columns={[
            { key: 'role', header: t.role, label: t.role, render: (r) => r.label },
            { key: 'kind', header: t.kind, label: t.kind, render: (r) => t.kinds[r.kind] ?? r.kind },
            { key: 'postings', header: t.postings, label: t.postings, align: 'end', render: (r) => r.postings },
            { key: 'total', header: `${t.total} (${result.currency})`, label: t.total, align: 'end', render: (r) => <Money amount={r.total} currency={result.currency} variant="table" /> },
          ]}
        />
      </div>
      {result.rates.length ? (
        <div className="stack-tight">
          <h3 className="subhead">{t.rates}</h3>
          <Rows>
            {result.rates.map((rate) => (
              <Row key={rate.date} label={displayDate(rate.date, locale)}>
                {rate.rate}
                {rate.source ? ` · ${rate.source}` : ''}
              </Row>
            ))}
          </Rows>
        </div>
      ) : null}
      <Provenance>{result.provenance}</Provenance>
    </div>
  );
}

/** The last computation for the year computing uses (the current one, else the latest active year begun). */
function Latest({ year }: { year: TaxYearStatus }) {
  const target = year.latest_year ?? year.year;
  const query = useRead('tax.latest', taxLatest, target ? { query: { year: target } } : undefined);
  const [done, setDone] = useState(false);
  const compute = useWrite<{ year: string | null }, TaxComputation>('tax.compute', (api, input) => api.call(taxCompute, { body: {}, ...(input.year ? { query: { year: input.year } } : {}) }), {
    invalidate: TAX_READS,
    onSuccess: () => setDone(true),
  });
  return (
    <Section label={t.latest} full>
      <Panel>
        <Loaded query={query}>{({ result }) => (result ? <Computation result={result} year={year} /> : <Empty>{t.noComputation}</Empty>)}</Loaded>
        {target ? (
          <div className="stack-tight">
            <p className="section-help">{t.computeHelp}</p>
            <div className="form-actions">
              <Button
                onPress={() => {
                  setDone(false);
                  compute.mutate({ year: target });
                }}
                isPending={compute.isPending}
              >
                {compute.isPending ? t.computing : t.compute}
              </Button>
              <p role="status" className="quiet-success">
                {done ? (
                  <>
                    <span aria-hidden="true">✓</span> {t.computed}
                  </>
                ) : null}
              </p>
            </div>
          </div>
        ) : null}
        {compute.isError ? <ProblemView error={compute.error} compact /> : null}
      </Panel>
    </Section>
  );
}

function Deadlines({ year }: { year: TaxYearStatus }) {
  const locale = useLocale();
  const enabled = Boolean(year.rule_set_id && year.rule_set_version_id);
  const query = useRead(
    'tax.ruleSets.versions.get',
    taxRuleSetsVersionsGet,
    { path: { rule_set_id: year.rule_set_id ?? '', version_id: year.rule_set_version_id ?? '' } },
    { enabled },
  );
  if (!enabled) return null;
  return (
    <Section label={t.deadlines}>
      <Panel>
        <p className="section-help">{t.deadlinesHelp}</p>
        <Loaded query={query}>
          {(version) => {
            const deadlines = deadlinesOf(version.document);
            const sources = new Map(sourcesOf(version.document).map((s) => [s.id, s]));
            return deadlines.length ? (
              <ul className="list">
                {deadlines.map((d) => {
                  const source = d.source ? sources.get(d.source) : undefined;
                  return (
                    <li key={d.key} className="dated">
                      <span className="dated-date">{displayDate(d.date, locale)}</span>
                      <span>
                        {d.label}
                        {source ? (
                          <span className="muted">
                            {' '}
                            · <SourceLink source={source} />
                          </span>
                        ) : null}
                      </span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <Empty>{t.noDeadlines}</Empty>
            );
          }}
        </Loaded>
      </Panel>
    </Section>
  );
}

function RuleSets() {
  const query = useRead('tax.ruleSets.list', taxRuleSetsList);
  return (
    <Section label={t.ruleSets}>
      <Panel>
        <p className="section-help">{t.ruleSetsHelp}</p>
        <Loaded query={query}>
          {(sets) =>
            sets.length ? (
              <ul className="list">
                {sets.map((set: TaxRuleSet) => {
                  const active = set.versions.find((v) => v.id === set.active_version_id);
                  const newest = set.versions[set.versions.length - 1];
                  return (
                    <li key={set.id} className="stack-tight">
                      <p className="signal-title">
                        <Link to={ruleSetPath(set.id)} aria-label={t.open(set.name)}>
                          {set.name}
                        </Link>
                      </p>
                      <p className="muted">
                        {t.active}: {active ? taxStrings.version.title(set.name, active.version) : t.noneActive}
                      </p>
                      {newest && newest.id !== active?.id ? (
                        <p className="muted">
                          {t.newest}: <Link to={versionPath(set.id, newest.id)}>{taxStrings.version.title(set.name, newest.version)}</Link> <StatusTag status={newest.status} />
                        </p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <Empty>{t.noRuleSets}</Empty>
            )
          }
        </Loaded>
        <p className="provenance">{taxStrings.ruleSet.onlyAPerson}</p>
      </Panel>
    </Section>
  );
}

export function Tax() {
  const year = useRead('tax.currentYear', taxCurrentYear);
  return (
    <Page title={t.title} description={t.description}>
      <Grid>
        <Section label={t.year}>
          <Panel>
            <Loaded query={year}>{(y) => <Year year={y} />}</Loaded>
          </Panel>
        </Section>
        <RuleSets />
        {year.data && (year.data.latest_year ?? year.data.year) ? <Latest year={year.data} /> : null}
        {year.data ? <Deadlines year={year.data} /> : null}
      </Grid>
    </Page>
  );
}

export default Tax;
