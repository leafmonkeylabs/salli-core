/**
 * The decision lab (docs/design/console.md, section 5): where to start, and
 * what is due for review. Salli computes; the person decides.
 */
import { decisionsTemplatesList } from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useRead } from '../../api';
import { Grid, Loaded, Page, Panel, Section } from '../../kit/layout';
import { labStrings } from '../../lab-strings';
import { DueReviews } from './Due';
import { LAB_PLACES, LabNav, templatePath } from './LabNav';

const l = labStrings;

const SENTENCES: Record<string, string> = {
  '/decide/templates': l.places.templates,
  '/decide/scenarios': l.places.scenarios,
  '/decide/principles': l.places.principles,
  '/decide/journal': l.places.journal,
  '/decide/baseline': l.places.baseline,
};

export function Lab() {
  const templates = useRead('decisions.templates.list', decisionsTemplatesList);
  return (
    <Page title={l.title} description={l.description}>
      <LabNav />
      <Grid>
        <Section label={l.dueTitle}>
          <Panel>
            <DueReviews />
          </Panel>
        </Section>
        <Section label={l.nav.templates} wide>
          <Panel>
            <Loaded query={templates}>
              {({ templates: list }) => (
                <ul className="list template-list">
                  {list.map((template) => (
                    <li key={template.id}>
                      <Link to={templatePath(template.id)} className="strong-link">
                        {template.title}
                      </Link>
                      <p className="muted">{template.summary}</p>
                    </li>
                  ))}
                </ul>
              )}
            </Loaded>
          </Panel>
        </Section>
        {LAB_PLACES.filter((p) => p.to !== '/decide' && p.to !== '/decide/templates').map((place) => (
          <Section key={place.to} label={place.label} className="section-quarter">
            <Panel>
              <p>{SENTENCES[place.to]}</p>
              <p>
                <Link to={place.to} className="strong-link">
                  {l.open(place.label)}
                </Link>
              </p>
            </Panel>
          </Section>
        ))}
      </Grid>
    </Page>
  );
}

export default Lab;
