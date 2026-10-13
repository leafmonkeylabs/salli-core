/**
 * An error, plainly: what happened, then what to do (docs/brand/README.md,
 * "Voice"). Salli's errors are RFC 9457 problem details; the console shows
 * the problem's own title and detail as the server wrote them, each failed
 * field of a validation error on its own line, and the request id to quote.
 * Text from the server is rendered as text, never as HTML.
 */
import { describeDetail, SalliApiError, SalliNetworkError, type ValidationIssue } from '@leafmonkeylabs/salli-sdk';
import { strings } from '../strings';

function issues(detail: unknown): ValidationIssue[] {
  if (!Array.isArray(detail)) return [];
  return detail.filter(
    (item): item is ValidationIssue =>
      typeof item === 'object' && item !== null && Array.isArray((item as ValidationIssue).loc) && typeof (item as ValidationIssue).msg === 'string',
  );
}

function field(loc: Array<string | number>): string {
  const parts = loc[0] === 'body' && loc.length > 1 ? loc.slice(1) : loc;
  return parts.map((part) => (typeof part === 'number' ? `[${part}]` : part)).join('.').replace(/\.\[/g, '[');
}

export function ProblemView({ error, onRetry, compact }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  let title: string = strings.problem.title;
  let detail = '';
  let fields: ValidationIssue[] = [];
  let requestId: string | undefined;
  if (error instanceof SalliApiError) {
    const problem = error.toProblem();
    title = problem.title;
    fields = issues(problem.detail);
    detail = fields.length ? '' : describeDetail(problem.detail);
    requestId = error.requestId ?? (typeof problem.request_id === 'string' ? problem.request_id : undefined);
  } else if (error instanceof SalliNetworkError) {
    title = strings.start.unreachableTitle;
    detail = strings.problem.network(error.url ? new URL(error.url).origin : window.location.origin);
  } else if (error instanceof Error) {
    detail = error.message;
  }
  const Heading = compact ? 'p' : 'h2';
  return (
    <div className={['problem', compact ? 'problem-compact' : ''].filter(Boolean).join(' ')} role="alert">
      <Heading className="problem-title">
        <span className="warn-mark" aria-hidden="true">
          !
        </span>{' '}
        {title}
      </Heading>
      {detail ? <p>{detail}</p> : null}
      {fields.length ? (
        <>
          <p>{strings.problem.fields}</p>
          <ul className="problem-fields">
            {fields.map((issue, i) => (
              <li key={i}>
                {field(issue.loc) ? <code>{field(issue.loc)}</code> : null} {issue.msg}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {requestId ? <p className="provenance">{strings.problem.requestId(requestId)}</p> : null}
      {onRetry ? (
        <button type="button" className="button button-secondary" onClick={onRetry}>
          {strings.problem.retry}
        </button>
      ) : null}
    </div>
  );
}
