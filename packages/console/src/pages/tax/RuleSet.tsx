/**
 * A tax rule set (`tax.ruleSets.get`; `salli tax rules show <set>`): its
 * jurisdiction and year, and every version with its status, who wrote it,
 * its note and when, each opening its review. Only a person activates.
 */
import { taxRuleSetsGet, type TaxRuleSetVersionSummary } from '@leafmonkeylabs/salli-sdk';
import { Link, useParams } from '@tanstack/react-router';
import { useRead } from '../../api';
import { displayDate } from '../../kit/dates';
import { Grid, Loaded, Page, Panel, Section } from '../../kit/layout';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { taxStrings } from '../../tax-strings';
import { authorOf, StatusTag, versionPath } from './parts';

const s = taxStrings.ruleSet;

export function RuleSet() {
  const locale = useLocale();
  const params = useParams({ strict: false }) as { ruleSet?: string };
  const id = decodeURIComponent(params.ruleSet ?? '');
  const query = useRead('tax.ruleSets.get', taxRuleSetsGet, { path: { rule_set_id: id } });
  const set = query.data;
  return (
    <Page
      title={set ? set.name : query.isError ? s.notFound : taxStrings.tax.title}
      {...(set ? { description: s.description(set.country, set.region ?? '', set.year_label) } : {})}
    >
      <p>
        <Link to="/tax">{taxStrings.nav.overview}</Link>
      </p>
      <Grid>
        <Section label={s.versions} full>
          <Panel>
            <p className="section-help">{s.versionsHelp}</p>
            <Loaded query={query}>
              {(found) => (
                <Table<TaxRuleSetVersionSummary>
                  caption={s.versions}
                  captionHidden
                  rows={[...found.versions].reverse()}
                  rowKey={(v) => v.id}
                  columns={[
                    {
                      key: 'version',
                      header: s.version,
                      label: s.version,
                      render: (v) => <Link to={versionPath(found.id, v.id)}>{taxStrings.version.title(found.name, v.version)}</Link>,
                    },
                    { key: 'status', header: s.status, label: s.status, render: (v) => <StatusTag status={v.status} /> },
                    { key: 'author', header: s.author, label: s.author, render: (v) => authorOf(v) },
                    { key: 'note', header: s.note, label: s.note, render: (v) => v.change_note ?? '—' },
                    { key: 'created', header: s.created, label: s.created, render: (v) => displayDate(v.created_at, locale) },
                  ]}
                />
              )}
            </Loaded>
            <p className="provenance">{s.onlyAPerson}</p>
          </Panel>
        </Section>
      </Grid>
    </Page>
  );
}

export default RuleSet;
