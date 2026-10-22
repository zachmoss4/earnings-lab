import { useId, useState } from 'react';
import { ArrowsOut } from '@phosphor-icons/react';
import type { Result } from './types';

export const dateLabel = (value: string, full = false) =>
  new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    ...(full ? { year: 'numeric' } : {}),
    timeZone: 'UTC',
  }).format(new Date(value + 'T12:00:00Z'));
export const percent = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`;

export default function Chart({ result, onExpand }: { result: Result; onExpand?: () => void }) {
  const titleId = useId();
  const [active, setActive] = useState<number | null>(null);
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const points = result.points;
  const width = 800,
    height = 290,
    left = 65,
    right = 28,
    top = 24,
    bottom = 46;
  const xMax = Math.ceil(Math.max(45, points.at(-1)!.dte) / 15) * 15;
  const yMin = Math.max(0, Math.floor(Math.min(...points.map((p) => p.iv)) * 10) / 10 - 0.05);
  const yMax = Math.ceil(Math.max(...points.map((p) => p.iv)) * 10) / 10 + 0.05;
  const x = (d: number) => left + (d / xMax) * (width - left - right);
  const y = (v: number) => top + ((yMax - v) / (yMax - yMin)) * (height - top - bottom);
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(p.dte)},${y(p.iv)}`).join(' ');
  const current = active === null ? null : points[active];
  return (
    <section
      id={onExpand ? 'volatility' : undefined}
      className="panel chart-panel"
      aria-labelledby={titleId}
    >
      <div className="panel-heading">
        <div>
          <h2 id={titleId}>Volatility term structure</h2>
          <p>At-the-money implied volatility by expiration</p>
        </div>
        <div className="chart-controls">
          <div className="segmented" aria-label="Term structure display">
            <button type="button" aria-pressed={view === 'chart'} onClick={() => setView('chart')}>
              Chart
            </button>
            <button type="button" aria-pressed={view === 'table'} onClick={() => setView('table')}>
              Data
            </button>
          </div>
          {onExpand && (
            <button
              className="icon-button chart-expand"
              onClick={onExpand}
              aria-label="Expand volatility chart"
            >
              <ArrowsOut size={18} />
            </button>
          )}
        </div>
      </div>
      {view === 'chart' ? (
        <>
          <div className="chart-readout" aria-live="polite">
            {current ? (
              <>
                <span>
                  {dateLabel(current.expiry)} · {current.dte} days
                </span>
                <strong>{percent(current.iv)}</strong>
              </>
            ) : (
              <>
                <span>ATM call + put average</span>
                <strong>{points.length} expirations</strong>
              </>
            )}
          </div>
          <svg
            className="iv-chart"
            viewBox={`0 0 ${width} ${height}`}
            role="group"
            aria-label="Implied volatility across expirations. Focus each point for its value."
            onPointerLeave={() => setActive(null)}
          >
            <title>ATM implied volatility term structure</title>
            {[0, 1, 2, 3, 4].map((i) => {
              const v = yMin + ((yMax - yMin) * i) / 4;
              return (
                <g key={i}>
                  <line className="gridline" x1={left} x2={width - right} y1={y(v)} y2={y(v)} />
                  <text x={left - 12} y={y(v) + 4} textAnchor="end">
                    {Math.round(v * 100)}%
                  </text>
                </g>
              );
            })}
            {Array.from({ length: xMax / 15 + 1 }, (_, i) => i * 15).map((d) => (
              <text key={d} x={x(d)} y={height - 17} textAnchor="middle">
                {d}d
              </text>
            ))}
            {[
              { d: 30, iv: result.metrics.iv30, label: '30D' },
              {
                d: 45,
                iv: points[0].iv + result.metrics.slope_decimal_per_day * (45 - points[0].dte),
                label: '45D',
              },
            ].map((p) => (
              <g key={p.d}>
                <line
                  className="reference-line"
                  x1={x(p.d)}
                  x2={x(p.d)}
                  y1={top}
                  y2={height - bottom}
                />
                <text className="reference-label" x={x(p.d)} y={top - 9} textAnchor="middle">
                  {p.label}
                </text>
              </g>
            ))}
            <path className="iv-path" d={path} />
            {points.map((p, i) => (
              <g key={p.expiry}>
                <circle
                  className="point-hit"
                  cx={x(p.dte)}
                  cy={y(p.iv)}
                  r={14}
                  tabIndex={0}
                  role="img"
                  aria-label={`${dateLabel(p.expiry, true)}, ${p.dte} days, IV ${percent(p.iv)}`}
                  onPointerEnter={() => setActive(i)}
                  onFocus={() => setActive(i)}
                  onBlur={() => setActive(null)}
                />
                <circle
                  className={`iv-point ${active === i ? 'active' : ''}`}
                  pointerEvents="none"
                  cx={x(p.dte)}
                  cy={y(p.iv)}
                  r={active === i ? 5 : 3.5}
                />
              </g>
            ))}
          </svg>
          <div className="chart-caption">
            <span>
              <i className="line-key" />
              Observed ATM IV
            </span>
            <span>
              <i className="dash-key" />
              Interpolation targets
            </span>
            <span>Calendar days to expiration</span>
          </div>
        </>
      ) : (
        <div className="table-scroll">
          <table>
            <caption className="sr-only">
              Observed option expirations and implied volatility
            </caption>
            <thead>
              <tr>
                <th>Expiration</th>
                <th>Days</th>
                <th>ATM strike</th>
                <th>Call IV</th>
                <th>Put IV</th>
                <th>Average IV</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.expiry}>
                  <td>{dateLabel(p.expiry, true)}</td>
                  <td>{p.dte}</td>
                  <td>${p.call.strike.toFixed(2)}</td>
                  <td>{percent(p.call.iv)}</td>
                  <td>{percent(p.put.iv)}</td>
                  <td>{percent(p.iv)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="chart-footnote">
        Linear IV interpolation · 30-calendar-day target · Original endpoint convention
      </div>
    </section>
  );
}
