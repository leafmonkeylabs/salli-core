/**
 * Which of the person's principles the baseline and each option keep,
 * break or can't tell, with Salli's reason for each that isn't kept. In
 * words and a mark, never colour alone; never counted, never ordered.
 */
import type { PrincipleCheckResult, PrincipleRef } from '@leafmonkeylabs/salli-sdk';
import { Empty } from '../../kit/layout';
import { Table } from '../../kit/Table';
import { labStrings } from '../../lab-strings';

const c = labStrings.checks;

export interface CheckColumn {
  label: string;
  results: readonly PrincipleCheckResult[];
}

function Status({ status }: { status: string }) {
  const mark = status === 'keeps' ? '✓' : status === 'breaks' ? '!' : '?';
  return (
    <span className={`check check-${status}`}>
      <span aria-hidden="true" className="check-mark">
        {mark}
      </span>{' '}
      {c.status[status] ?? status}
    </span>
  );
}

export function Checks({ principles, columns, caption = c.title }: { principles: readonly PrincipleRef[]; columns: readonly CheckColumn[]; caption?: string }) {
  if (!principles.length) return <Empty>{c.none}</Empty>;
  const rows = principles.map((p, i) => ({ principle: p, results: columns.map((column) => column.results[i]) }));
  const why = columns.flatMap((column) => column.results.filter((r) => r.status !== 'keeps').map((r) => ({ column: column.label, result: r })));
  return (
    <div className="stack-tight">
      <Table
        caption={caption}
        captionHidden
        rows={rows}
        rowKey={(row) => row.principle.id}
        columns={[
          {
            key: 'principle',
            header: c.principleColumn,
            label: c.principleColumn,
            render: (row) => (
              <>
                {row.principle.label} <code className="check-code">{row.principle.check}</code>
              </>
            ),
          },
          ...columns.map((column, k) => ({
            key: `c${k}`,
            header: column.label,
            label: column.label,
            render: (row: (typeof rows)[number]) => <Status status={row.results[k]?.status ?? 'unknown'} />,
          })),
        ]}
      />
      {why.length ? (
        <>
          <p className="subhead">{c.why}</p>
          <ul className="list reasons">
            {why.map(({ column, result }, i) => (
              <li key={i}>{c.reason(column, result.label, result.reason)}</li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
