/**
 * Categorisation rules (docs/design/console.md, section 5; `salli rules`):
 * the person's rules in the order they are tried (`rules.list`), each in
 * words with what it has decided; adding and editing one (`rules.create`,
 * `rules.update`), tested against what is already booked first if the
 * person wants (`rules.test`); deleting one after a confirmation
 * (`rules.delete`); and the rules their own bookkeeping implies
 * (`rules.suggestions`), each made a rule as it is or edited first.
 */
import { rulesCreate, rulesDelete, rulesList, rulesSuggestions, type CategorizationRule, type RuleSuggestion } from '@leafmonkeylabs/salli-sdk';
import { useState } from 'react';
import { useRead, useWrite } from '../../api';
import { bookStrings } from '../../books-strings';
import { displayDate } from '../../kit/dates';
import { Button, Confirm } from '../../kit/forms';
import { Empty, Grid, Loaded, Page, Panel, Section } from '../../kit/layout';
import { ProblemView } from '../../kit/Problem';
import { useLocale } from '../../preferences';
import { BooksNav, useAccountBook, type AccountBook } from './ledger';
import { actionWords, conditionWords, RULE_READS, RuleForm, type RuleStart } from './rule-form';

const r = bookStrings.rules;

const EMPTY: RuleStart = { name: '', conditions: [], actions: {} };

function RuleItem({ rule, book, onEdit, onDelete }: { rule: CategorizationRule; book: AccountBook; onEdit: () => void; onDelete: () => void }) {
  const locale = useLocale();
  return (
    <li className="rule">
      <p className="signal-title">
        {rule.name} <span className="tag">{r.order(rule.priority ?? 100)}</span>
        {rule.enabled === false ? <span className="tag tag-warn"> {r.off}</span> : null}
      </p>
      <p>
        <span className="field-label">{r.when}</span> {rule.match_all === false ? r.whenAny : r.whenAll}:{' '}
        {rule.conditions.map(conditionWords).join('; ')}
      </p>
      <p>
        <span className="field-label">{r.then}</span> {actionWords(rule.actions, book) || r.accountNone}
      </p>
      <p className="muted">{r.hits(rule.hits, rule.last_hit_at ? displayDate(rule.last_hit_at, locale) : '')}</p>
      <div className="form-actions">
        <Button variant="secondary" aria-label={r.editLabel(rule.name)} onPress={onEdit}>
          {r.edit}
        </Button>
        <Button variant="tertiary" aria-label={r.deleteLabel(rule.name)} onPress={onDelete}>
          {r.delete}
        </Button>
      </div>
    </li>
  );
}

function asStart(suggestion: RuleSuggestion): RuleStart {
  return {
    name: suggestion.name,
    conditions: suggestion.conditions,
    actions: suggestion.actions,
    priority: suggestion.priority ?? 100,
    match_all: suggestion.match_all ?? true,
    enabled: suggestion.enabled ?? true,
  };
}

function Suggestions({ book, onEdit, onMade }: { book: AccountBook; onEdit: (start: RuleStart) => void; onMade: (name: string) => void }) {
  const query = useRead('rules.suggestions', rulesSuggestions);
  const make = useWrite<RuleStart, unknown>(
    'rules.create',
    (api, input) =>
      api.call(rulesCreate, {
        body: {
          name: input.name,
          conditions: input.conditions,
          actions: input.actions,
          priority: input.priority ?? 100,
          match_all: input.match_all ?? true,
          enabled: input.enabled ?? true,
        },
      }),
    { invalidate: RULE_READS, onSuccess: (_, input) => onMade(input.name) },
  );
  return (
    <Section label={r.suggestions} full>
      <Panel>
        <p className="section-help">{r.suggestionsHelp}</p>
        <Loaded query={query}>
          {(suggestions) =>
            suggestions.length ? (
              <ul className="list">
                {suggestions.map((s) => (
                  <li key={`${s.name}-${s.conditions.map(conditionWords).join('|')}`} className="rule">
                    <p className="signal-title">{s.name}</p>
                    <p>
                      <span className="field-label">{r.when}</span> {s.conditions.map(conditionWords).join('; ')}
                    </p>
                    <p>
                      <span className="field-label">{r.then}</span> {actionWords(s.actions, book)}
                    </p>
                    <p className="muted">{r.support(s.support, s.agreement)}</p>
                    {s.examples.length ? <p className="muted">{r.examples(s.examples.join(', '))}</p> : null}
                    <div className="form-actions">
                      <Button variant="secondary" aria-label={r.makeItLabel(s.name)} onPress={() => make.mutate(asStart(s))} isPending={make.isPending && make.variables?.name === s.name}>
                        {r.makeIt}
                      </Button>
                      <Button variant="tertiary" aria-label={r.editFirstLabel(s.name)} onPress={() => onEdit(asStart(s))}>
                        {r.editFirst}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>{r.noSuggestions}</Empty>
            )
          }
        </Loaded>
        {make.isError ? <ProblemView error={make.error} compact /> : null}
      </Panel>
    </Section>
  );
}

function Book({ book }: { book: AccountBook }) {
  const query = useRead('rules.list', rulesList);
  const [start, setStart] = useState<RuleStart>(EMPTY);
  const [said, setSaid] = useState('');
  const [deleting, setDeleting] = useState<CategorizationRule | null>(null);
  const remove = useWrite<{ id: string; name: string }, unknown>('rules.delete', (api, input) => api.call(rulesDelete, { path: { rule_id: input.id } }), {
    invalidate: RULE_READS,
    onSuccess: (_, input) => {
      setDeleting(null);
      setSaid(r.deleted(input.name));
      if (start.id === input.id) setStart(EMPTY);
    },
  });
  const edit = (next: RuleStart): void => {
    setSaid('');
    setStart(next);
    document.getElementById('rule-form')?.scrollIntoView?.({ block: 'start' });
  };
  return (
    <>
      <Section label={r.yours} full>
        <Panel>
          <p className="section-help">{r.yoursHelp}</p>
          <Loaded query={query}>
            {(rules) =>
              rules.length ? (
                <ul className="list">
                  {rules.map((rule) => (
                    <RuleItem
                      key={rule.id}
                      rule={rule}
                      book={book}
                      onEdit={() =>
                        edit({
                          id: rule.id,
                          name: rule.name,
                          conditions: rule.conditions,
                          actions: rule.actions,
                          priority: rule.priority ?? 100,
                          match_all: rule.match_all ?? true,
                          enabled: rule.enabled ?? true,
                        })
                      }
                      onDelete={() => {
                        remove.reset();
                        setDeleting(rule);
                      }}
                    />
                  ))}
                </ul>
              ) : (
                <Empty>{r.none}</Empty>
              )
            }
          </Loaded>
          <p role="status" className="quiet-success">
            {said ? (
              <>
                <span aria-hidden="true">✓</span> {said}
              </>
            ) : null}
          </p>
          {remove.isError ? <ProblemView error={remove.error} compact /> : null}
          <Confirm
            isOpen={deleting !== null}
            onOpenChange={(open) => (open ? undefined : setDeleting(null))}
            title={r.deleteTitle}
            confirmLabel={r.deleteConfirm}
            cancelLabel={r.cancel}
            isPending={remove.isPending}
            onConfirm={() => (deleting ? remove.mutate({ id: deleting.id, name: deleting.name }) : undefined)}
          >
            {deleting ? <p>{r.deleteBody(deleting.name)}</p> : null}
          </Confirm>
        </Panel>
      </Section>
      <Section label={start.id ? r.editing(start.name) : r.add} full anchor="rule-form">
        <Panel>
          <RuleForm
            key={JSON.stringify(start)}
            book={book}
            start={start}
            onSaved={(name) => {
              setStart(EMPTY);
              setSaid(r.saved(name));
            }}
            {...(start.id || start.name ? { onCancel: () => setStart(EMPTY) } : {})}
          />
        </Panel>
      </Section>
      <Suggestions
        book={book}
        onEdit={edit}
        onMade={(name) => {
          setSaid(r.made(name));
        }}
      />
    </>
  );
}

export function Rules() {
  const { query, book } = useAccountBook();
  return (
    <Page title={r.title} description={r.description}>
      <BooksNav />
      <Grid>
        <Loaded query={query}>{() => (book ? <Book book={book} /> : null)}</Loaded>
      </Grid>
    </Page>
  );
}

export default Rules;
