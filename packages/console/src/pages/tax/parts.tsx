/**
 * What the tax pages share: a source as a link (https only, opening apart
 * from the console), a version's status in words, who wrote it, and where
 * a rule set's and a version's pages are.
 */
import type { TaxRuleSetVersionSummary } from '@leafmonkeylabs/salli-sdk';
import { taxStrings } from '../../tax-strings';
import { httpsUrl, type Source } from './document';

const s = taxStrings;

export function ruleSetPath(id: string): string {
  return `/tax/rules/${encodeURIComponent(id)}`;
}

export function versionPath(ruleSetId: string, versionId: string): string {
  return `${ruleSetPath(ruleSetId)}/versions/${encodeURIComponent(versionId)}`;
}

/** A source's title, linked when its address is https, with the address shown. */
export function SourceLink({ source }: { source: Source }) {
  const href = httpsUrl(source.url);
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {source.title}
    </a>
  ) : (
    <span>{source.title}</span>
  );
}

export function StatusTag({ status }: { status: string }) {
  const warn = status === 'invalid' || status === 'draft';
  const due = status === 'proposed';
  return <span className={['tag', warn ? 'tag-warn' : '', due ? 'tag-due' : ''].filter(Boolean).join(' ')}>{s.statuses[status] ?? status}</span>;
}

/** "You", or "An agent: Claude". */
export function authorOf(version: Pick<TaxRuleSetVersionSummary, 'author_kind' | 'author_name'>): string {
  return version.author_kind === 'agent' ? s.ruleSet.agent(version.author_name ?? '') : s.ruleSet.you;
}
