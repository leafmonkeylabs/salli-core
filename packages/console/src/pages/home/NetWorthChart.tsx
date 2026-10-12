/**
 * Net worth over time (`insights.netWorth`): at each month's end, what you
 * own above the line in ledger green, what you owe below it in graphite, and
 * net worth as a 1.5 px line in ink, labelled at its end. Phones get their
 * own drawing: fewer month labels, the label below the plot.
 */
import type { NetWorthByMonth } from '@leafmonkeylabs/salli-sdk';
import { negateAmount } from '@leafmonkeylabs/salli-sdk';
import { ChartFigure } from '../../kit/chart/ChartFigure';
import { amountScale, bandScale, linePath } from '../../kit/chart/geometry';
import { fitTicks } from '../../kit/chart/ticks';
import { displayMonth } from '../../kit/dates';
import { Money, visibleAmount } from '../../kit/Money';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { strings } from '../../strings';

type Point = NetWorthByMonth['points'][number];

interface Layout {
  width: number;
  height: number;
  top: number;
  bottom: number;
  left: number;
  right: number;
  font: number;
  /** Label every nth month. */
  every: number;
}

const WIDE: Layout = { width: 640, height: 240, top: 16, bottom: 28, left: 8, right: 128, font: 12, every: 3 };
const NARROW: Layout = { width: 320, height: 200, top: 12, bottom: 24, left: 4, right: 4, font: 11, every: 0 };

function Plot({ data, layout, label, variant }: { data: NetWorthByMonth; layout: Layout; label: string; variant: 'wide' | 'narrow' }) {
  const locale = useLocale();
  const points = data.points;
  const { width, height, top, bottom, left, right, font } = layout;
  const below = points.map((p) => negateAmount(p.liabilities));
  const y = amountScale([...points.map((p) => p.assets), ...below, ...points.map((p) => p.net_worth)], [height - bottom, top]);
  const band = bandScale(points.length, [left, width - right]);
  const zero = y('0');
  const line = linePath(points.map((p, i) => [band.at(i), y(p.net_worth)] as const));
  const last = points[points.length - 1];
  const lastX = band.at(points.length - 1);
  const labelled = (i: number): boolean =>
    layout.every > 0 ? i % layout.every === (points.length - 1) % layout.every : i === 0 || i === points.length - 1;
  const ticks = fitTicks(
    points.flatMap((p, i) => (labelled(i) ? [{ index: i, x: band.at(i), text: displayMonth(p.month, locale) }] : [])),
    font,
    [left, width - right],
  );
  return (
    <svg className={`chart-svg chart-${variant}`} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <line className="chart-zero" x1={left} x2={width - right} y1={zero} y2={zero} />
      {points.map((p, i) => (
        <g key={p.month}>
          <rect className="chart-bar-1" x={band.at(i) - band.width / 2} width={band.width} y={Math.min(y(p.assets), zero)} height={Math.abs(zero - y(p.assets))} />
          <rect className="chart-bar-2" x={band.at(i) - band.width / 2} width={band.width} y={zero} height={Math.abs(y(below[i] ?? '0') - zero)} />
        </g>
      ))}
      <path className="chart-line-baseline" d={line} />
      {last ? <circle className="chart-point" cx={lastX} cy={y(last.net_worth)} r={3} /> : null}
      {ticks.map((tick) => (
        <text key={tick.index} className="chart-tick" x={tick.x} y={height - bottom / 3} fontSize={font} textAnchor={tick.anchor}>
          {tick.text}
        </text>
      ))}
      {last && variant === 'wide' ? (
        <text className="chart-end-label" x={lastX + band.width / 2 + 8} y={y(last.net_worth) + font / 3} fontSize={font}>
          {visibleAmount(last.net_worth, data.currency, 'prose', { locale })}
        </text>
      ) : null}
    </svg>
  );
}

export function NetWorthChart({ data }: { data: NetWorthByMonth }) {
  const locale = useLocale();
  const last = data.points[data.points.length - 1];
  if (!last) return <p className="empty">{strings.home.netWorthEmpty}</p>;
  const latest = visibleAmount(last.net_worth, data.currency, 'prose', { locale });
  const caption = strings.home.netWorthCaption(latest, displayMonth(last.month, locale));
  const code = data.currency.toUpperCase();
  return (
    <ChartFigure
      caption={caption}
      figures={
        <Table<Point>
          caption={strings.home.netWorthOverTime}
          captionHidden
          rows={data.points}
          rowKey={(p) => p.month}
          columns={[
            { key: 'month', header: strings.home.month, label: strings.home.month, render: (p) => displayMonth(p.month, locale) },
            { key: 'assets', header: `${strings.home.assets} (${code})`, label: strings.home.assets, align: 'end', render: (p) => <Money amount={p.assets} currency={code} variant="table" /> },
            {
              key: 'liabilities',
              header: `${strings.home.liabilities} (${code})`,
              label: strings.home.liabilities,
              align: 'end',
              render: (p) => <Money amount={p.liabilities} currency={code} variant="table" />,
            },
            { key: 'net', header: `${strings.home.netWorth} (${code})`, label: strings.home.netWorth, align: 'end', render: (p) => <Money amount={p.net_worth} currency={code} variant="table" /> },
          ]}
        />
      }
    >
      <Plot data={data} layout={WIDE} label={caption} variant="wide" />
      <Plot data={data} layout={NARROW} label={caption} variant="narrow" />
      <p className="chart-narrow-label" aria-hidden="true">
        {latest}
      </p>
    </ChartFigure>
  );
}
