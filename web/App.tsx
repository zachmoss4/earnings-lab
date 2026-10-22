import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import {
  ArrowRight,
  BookmarkSimple,
  CalendarBlank,
  ChartLineUp,
  Check,
  CheckCircle,
  Clock,
  Database,
  DownloadSimple,
  Flask,
  FolderSimple,
  Info,
  MagnifyingGlass,
  SpinnerGap,
  WarningCircle,
  X,
} from '@phosphor-icons/react';
import Chart, { dateLabel, percent } from './Chart';
import type { Result, Snapshot } from './types';

const money = (v: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v);
const timeLabel = (v: string) =>
  new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(new Date(v));
async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    ...(body !== undefined
      ? {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      : {}),
    signal,
  });
  const value = await response.json();
  if (!response.ok)
    throw new Error(value.error || 'The local app could not complete this request.');
  return value;
}
function exportCSV(result: Result) {
  const rows: [string, unknown][] = [
    ['symbol', result.symbol],
    ['data_source', result.source_label],
    ['synthetic', result.source === 'example'],
    ['retrieved_at', result.retrieved_at],
    ['as_of_date', result.as_of_date],
    ['calculation_version', result.method.version],
    ['classification', result.classification.label],
    ['original_label', result.classification.original_label],
    ['underlying_price_usd', result.price],
    ['average_share_volume_30_observations', result.metrics.avg_volume],
    ['iv30_decimal', result.metrics.iv30],
    ['rv30_decimal', result.metrics.rv30],
    ['iv_rv_ratio', result.metrics.iv_rv_ratio],
    ['slope_decimal_iv_per_calendar_day', result.metrics.slope_decimal_per_day],
    ['expected_move_percent', result.metrics.expected_move_pct],
    ['expected_move_expiry', result.expected_move_expiry],
    ['earnings_date', result.event.date || 'unavailable'],
    ['earnings_session', result.event.session],
    ['earnings_source', result.event.source],
    ['event_in_front_expiry', result.event.in_front_expiry ?? 'unknown'],
    ['volume_threshold', result.thresholds.avg_volume],
    ['iv_rv_threshold', result.thresholds.iv_rv_ratio],
    ['slope_threshold', result.thresholds.slope],
    ...result.warnings.map((w) => [`warning_${w.code}`, w.message] as [string, unknown]),
  ];
  const cell = (v: unknown) => {
    let s = String(v ?? '');
    if (typeof v !== 'number' && /^[=+\-@]/.test(s)) s = `'${s}`;
    return `"${s.replaceAll('"', '""')}"`;
  };
  const csv = [['field', 'value'], ...rows].map((row) => row.map(cell).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `earnings-lab-${result.symbol}-${result.as_of_date}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function Dialog({
  title,
  children,
  close,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    const previousFocus = document.activeElement as HTMLElement | null;
    dialog.showModal();
    return () => {
      dialog.close();
      previousFocus?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`dialog${wide ? ' dialog-wide' : ''}`}
      onCancel={close}
      aria-labelledby="dialog-title"
    >
      <div className="dialog-heading">
        <h2 id="dialog-title">{title}</h2>
        <button className="icon-button" aria-label="Close dialog" onClick={close}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

function FilterPanel({ result }: { result: Result }) {
  const metrics = result.metrics;
  const filters = [
    {
      key: 'avg_volume' as const,
      title: 'Average share volume',
      value: `${(metrics.avg_volume / 1e6).toFixed(2)}M`,
      threshold: 'At least 1.50M shares / day',
      detail: '30 trading observations. Stock activity does not establish option liquidity.',
    },
    {
      key: 'iv_rv_ratio' as const,
      title: 'Implied / realized volatility',
      value: `${metrics.iv_rv_ratio.toFixed(2)}×`,
      threshold: 'Ratio of at least 1.25×',
      detail: `IV30 ${percent(metrics.iv30)} · RV30 ${percent(metrics.rv30)}. Historical RV follows the supplied formula.`,
    },
    {
      key: 'slope' as const,
      title: 'Term-structure slope',
      value: metrics.slope_points_per_day.toFixed(3),
      threshold: 'At or below −0.406 IV points / day',
      detail: 'Nearest expiration to interpolated day 45. Values use calendar days.',
    },
  ];
  return (
    <section className="panel filters" aria-labelledby="filters-title">
      <div className="filter-heading">
        <h2 id="filters-title">The three filters</h2>
        <span className="small-tag">Original rules</span>
      </div>
      {filters.map((f) => (
        <div className="filter-row" key={f.key}>
          <div className="filter-label">
            <h3>{f.title}</h3>
            <span className={result.flags[f.key] ? 'check pass' : 'check fail'}>
              {result.flags[f.key] ? (
                <Check size={12} weight="bold" />
              ) : (
                <X size={12} weight="bold" />
              )}
              {result.flags[f.key] ? 'Pass' : 'Fail'}
            </span>
          </div>
          <div className="filter-value">
            {f.value}
            {f.key === 'slope' && <small>pts / day</small>}
          </div>
          <p className="threshold">{f.threshold}</p>
          <p className="filter-detail">{f.detail}</p>
        </div>
      ))}
      <div className="filter-footer">
        <Info size={16} />
        <span>Filters describe a setup. They do not estimate profit or win probability.</span>
      </div>
    </section>
  );
}

function EventPanel({ result }: { result: Result }) {
  const event = result.event;
  const session =
    event.session === 'after_close'
      ? 'After market close'
      : event.session === 'before_open'
        ? 'Before market open'
        : 'Announcement time unverified';
  return (
    <section id="earnings-context" className="panel event-panel">
      <div className="panel-heading">
        <h2>
          <CalendarBlank size={18} />
          Earnings context
        </h2>
        <span className="small-tag">
          {event.status === 'synthetic'
            ? 'Example event'
            : event.status === 'manual'
              ? 'Manual entry'
              : 'Unverified estimate'}
        </span>
      </div>
      <div className="event-date">
        {event.date ? dateLabel(event.date, true) : 'Date unavailable'}
      </div>
      <p className="event-session">{session}</p>
      <dl className="facts">
        <div>
          <dt>Front expiration</dt>
          <dd>{dateLabel(result.points[0].expiry)}</dd>
        </div>
        <div>
          <dt>Event inside expiration</dt>
          <dd>
            {event.in_front_expiry === null
              ? 'Confirm timing'
              : event.in_front_expiry
                ? 'Yes'
                : 'No'}
          </dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{event.source}</dd>
        </div>
      </dl>
      <p className="quiet-note">
        Research protocol: enter 15 minutes before the pre-announcement close; exit 15 minutes after
        the next session opens.
      </p>
    </section>
  );
}

function CalendarPanel({ result }: { result: Result }) {
  const [quantity, setQuantity] = useState(1);
  const cal = result.calendar;
  return (
    <section id="calendar-reference" className="panel calendar-panel">
      <div className="panel-heading">
        <div>
          <h2>Call calendar reference</h2>
          <p>Same-strike pair closest to a 30-day gap</p>
        </div>
        <span className="small-tag">Indicative</span>
      </div>
      {cal ? (
        <>
          <div className="calendar-legs">
            <div>
              <span className="leg-type sell">SELL</span>
              <span>{dateLabel(cal.front_expiry)}</span>
              <strong>{money(cal.strike)} call</strong>
            </div>
            <div>
              <span className="leg-type buy">BUY</span>
              <span>{dateLabel(cal.back_expiry)}</span>
              <strong>{money(cal.strike)} call</strong>
            </div>
          </div>
          <div className="sizing">
            <label>
              Spreads
              <input
                aria-label="Number of calendar spreads"
                type="number"
                min="1"
                max="1000"
                value={quantity}
                onChange={(e) =>
                  setQuantity(Math.max(1, Math.min(1000, Math.floor(Number(e.target.value) || 1))))
                }
              />
            </label>
            <div>
              <span>Leg contracts</span>
              <strong>{quantity * 2}</strong>
            </div>
            <div>
              <span>Midpoint debit</span>
              <strong>{money(cal.mid_debit * cal.multiplier * quantity)}</strong>
            </div>
          </div>
          <p className="quiet-note">
            {cal.gap_days}-day gap · {cal.multiplier}-share multiplier · {money(cal.mid_debit)}{' '}
            quoted debit. Paying the ask and selling the bid implies{' '}
            {money(cal.conservative_debit * 100 * quantity)} before fees. These are reference
            quotes, not executable fills.
          </p>
        </>
      ) : (
        <p className="quiet-note">
          A valid same-strike call pair with a verified regular contract size is unavailable. No
          calendar cost is estimated.
        </p>
      )}
    </section>
  );
}

export default function App() {
  const [result, setResult] = useState<Result | null>(null);
  const [symbol, setSymbol] = useState('');
  const [eventDate, setEventDate] = useState('');
  const [eventSession, setEventSession] = useState('unknown');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [modal, setModal] = useState<'method' | 'saved' | 'chart' | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [saving, setSaving] = useState(false);
  const [savedLoading, setSavedLoading] = useState(false);
  const pending = useRef<AbortController | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const notify = (text: string) => {
    setToast(text);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(''), 4500);
  };
  useEffect(() => {
    return () => {
      pending.current?.abort();
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);
  async function openExample() {
    pending.current?.abort();
    setError('');
    setLoading(true);
    setSymbol('');
    try {
      setResult(await api<Result>('/api/example'));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (loading) return;
    setResult(null);
    setError('');
    setLoading(true);
    const controller = new AbortController();
    pending.current = controller;
    const timeout = setTimeout(() => controller.abort(), 120_000);
    try {
      setResult(
        await api<Result>(
          '/api/analyze',
          { symbol, ...(eventDate ? { event: { date: eventDate, session: eventSession } } : {}) },
          controller.signal
        )
      );
    } catch (e) {
      setError(
        (e as Error).name === 'AbortError'
          ? 'The request stopped. You can try again or use the offline example.'
          : (e as Error).message
      );
    } finally {
      clearTimeout(timeout);
      pending.current = null;
      setLoading(false);
    }
  }
  async function save() {
    if (!result) return;
    setSaving(true);
    try {
      await api('/api/snapshots', { analysis_id: result.id });
      notify('Snapshot saved on this computer.');
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  async function openSaved() {
    setModal('saved');
    setSavedLoading(true);
    try {
      setSnapshots(await api<Snapshot[]>('/api/snapshots'));
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setSavedLoading(false);
    }
  }
  async function loadSnapshot(id: string) {
    try {
      const data = await api<Result>(`/api/snapshots/${id}`);
      setResult(data);
      setModal(null);
      setError('');
      setSymbol(data.source === 'example' ? '' : data.symbol);
      notify('Saved snapshot opened. Prices have not been refreshed.');
    } catch (e) {
      notify((e as Error).message);
    }
  }
  const warnings = result?.warnings.filter((w) => w.code !== 'synthetic') ?? [];
  return (
    <>
      <a className="skip-link" href="#workspace">
        Skip to analysis
      </a>
      <header className="app-header">
        <div className="header-inner">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span aria-hidden="true">/</span>
            <strong>Earnings analysis</strong>
          </div>
          <nav className="tool-actions" aria-label="Calculator tools">
            <button className="button secondary" onClick={openSaved}>
              <FolderSimple size={16} />
              Saved snapshots
            </button>
            <button className="button secondary" onClick={() => setModal('method')}>
              Calculation notes
            </button>
          </nav>
        </div>
      </header>
      <main id="workspace" className="workspace">
        <div className="page-heading">
          <div>
            <h1>Earnings analysis</h1>
            <p>Compare implied volatility, recent movement, and the earnings calendar.</p>
          </div>
          <button
            className="button secondary example-button"
            onClick={openExample}
            disabled={loading}
          >
            <Flask size={17} />
            Offline example
          </button>
        </div>
        <section className="search-panel" aria-label="Analyze a stock">
          <form onSubmit={submit}>
            <div className="ticker-field">
              <label htmlFor="ticker">Stock ticker</label>
              <div>
                <MagnifyingGlass size={19} />
                <input
                  id="ticker"
                  autoComplete="off"
                  autoCapitalize="characters"
                  spellCheck={false}
                  maxLength={15}
                  placeholder="AAPL"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                  required
                  aria-describedby="ticker-help"
                />
              </div>
            </div>
            <p id="ticker-help">
              Enter one ticker to retrieve an options snapshot.
              <br />
              <span>Yahoo data may be delayed.</span>
            </p>
            <button className="button primary" type="submit" disabled={loading}>
              {loading ? (
                <>
                  <SpinnerGap className="spin" size={18} />
                  Loading
                </>
              ) : (
                <>
                  Analyze ticker
                  <ArrowRight size={17} />
                </>
              )}
            </button>
          </form>
          <details className="event-override">
            <summary>
              Add a confirmed earnings date <span>Optional</span>
            </summary>
            <div className="event-fields">
              <label htmlFor="event-date">
                Earnings date
                <input
                  id="event-date"
                  type="date"
                  value={eventDate}
                  onChange={(e) => setEventDate(e.target.value)}
                />
              </label>
              <label htmlFor="event-session">
                Announcement session
                <select
                  id="event-session"
                  value={eventSession}
                  onChange={(e) => setEventSession(e.target.value)}
                >
                  <option value="unknown">Not confirmed</option>
                  <option value="before_open">Before market open</option>
                  <option value="after_close">After market close</option>
                </select>
              </label>
              <p>
                Use the company's investor-relations announcement. Manual dates remain labeled as
                your input.
              </p>
            </div>
          </details>
        </section>
        {error && (
          <div className="error-notice" role="alert">
            <WarningCircle size={21} />
            <div>
              <strong>Analysis unavailable</strong>
              <p>{error}</p>
            </div>
            <button className="text-button" onClick={openExample}>
              Use example
              <ArrowRight size={16} />
            </button>
          </div>
        )}
        {loading ? (
          <section className="loading-state" aria-live="polite" aria-busy="true">
            <SpinnerGap size={30} className="spin" />
            <h2>
              {symbol ? `Retrieving ${symbol.trim().toUpperCase()}` : 'Opening the workspace'}
            </h2>
            <p>Checking option expirations, price history, and available event data.</p>
            {pending.current && (
              <button className="button secondary" onClick={() => pending.current?.abort()}>
                Cancel request
              </button>
            )}
          </section>
        ) : result ? (
          <>
            {result.source === 'example' && (
              <div className="example-notice">
                <Flask size={17} />
                <strong>Offline example</strong>
                <span>All prices, options, volumes, and event details below are fabricated.</span>
              </div>
            )}
            {result.saved_at && (
              <div className="saved-notice">
                <BookmarkSimple size={17} />
                Saved snapshot · {timeLabel(result.saved_at)}. Prices have not been refreshed.
              </div>
            )}
            <div className="result-heading">
              <div className="symbol-heading">
                <span className="ticker-monogram">
                  {result.source === 'example' ? <Flask size={23} /> : result.symbol.slice(0, 2)}
                </span>
                <div>
                  <div className="symbol-line">
                    <h2>{result.symbol}</h2>
                    <span>
                      {result.company_name === result.symbol
                        ? 'Options research'
                        : result.company_name}
                    </span>
                  </div>
                  <div className="source-line">
                    {result.source === 'example' ? 'Synthetic fixture' : 'Yahoo Finance'}
                    <span>·</span>As of {dateLabel(result.as_of_date, true)}
                  </div>
                </div>
              </div>
              <div className="result-actions">
                <button className="button secondary" onClick={save} disabled={saving}>
                  <BookmarkSimple size={16} />
                  {saving ? 'Saving…' : 'Save snapshot'}
                </button>
                <button
                  className="button secondary"
                  onClick={() => {
                    exportCSV(result);
                    notify('CSV exported. Source and calculation version are included.');
                  }}
                >
                  <DownloadSimple size={16} />
                  Export CSV
                </button>
              </div>
            </div>
            <section className="result-summary" aria-label="Analysis overview">
              <div className={`classification ${result.classification.key}`}>
                {result.classification.key === 'matches' ? (
                  <CheckCircle size={21} />
                ) : (
                  <WarningCircle size={21} />
                )}
                <div>
                  <strong>{result.classification.label}</strong>
                  <span>
                    {result.classification.passed} of 3 conditions pass · Event context is separate
                  </span>
                </div>
              </div>
              <div className="summary-stat">
                <span>Underlying price</span>
                <strong>{money(result.price)}</strong>
              </div>
              <div className="summary-stat">
                <span>
                  Premium-based move{' '}
                  <span className="subtle">to {dateLabel(result.expected_move_expiry)}</span>
                </span>
                <strong>±{result.metrics.expected_move_pct.toFixed(2)}%</strong>
              </div>
            </section>
            <div className="dashboard-grid">
              <Chart key={result.id} result={result} onExpand={() => setModal('chart')} />
              <div className="context-stack">
                <EventPanel result={result} />
                <CalendarPanel key={result.id} result={result} />
              </div>
            </div>
            <FilterPanel result={result} />
            <section className="quality-panel" aria-label="Data notes">
              <div>
                <Database size={18} />
                <strong>Data notes</strong>
                <span>
                  {warnings.length ? `${warnings.length} to review` : 'Fixture fields validated'}
                </span>
              </div>
              {warnings.length ? (
                <ul>
                  {warnings.map((w, i) => (
                    <li key={`${w.code}-${i}`}>{w.message}</li>
                  ))}
                </ul>
              ) : (
                <p>
                  This synthetic example demonstrates the workflow. Live requests are labeled
                  separately and checked for missing or invalid fields.
                </p>
              )}
            </section>
            <div className="provenance">
              <span>
                <Clock size={14} />
                Retrieved {timeLabel(result.retrieved_at)}
              </span>
              <span>
                {result.method.name} · {result.method.version}
              </span>
              <span>IV30: calendar days · RV30: trading observations</span>
            </div>
          </>
        ) : (
          <section className="empty-state">
            <ChartLineUp size={32} />
            <h2>Start with a ticker.</h2>
            <p>Or open the offline example to explore the workspace without a data request.</p>
            <button className="button secondary" onClick={openExample}>
              Open offline example
              <ArrowRight size={16} />
            </button>
          </section>
        )}
        <footer className="app-footer">
          <span>Local options research</span>
          <button onClick={() => setModal('method')}>Calculation notes</button>
        </footer>
      </main>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle size={19} />
          {toast}
          <button aria-label="Dismiss notification" onClick={() => setToast('')}>
            <X size={16} />
          </button>
        </div>
      )}
      {modal === 'chart' && result && (
        <Dialog
          key="chart"
          title={`${result.symbol} · Volatility term structure`}
          close={() => setModal(null)}
          wide
        >
          <p className="dialog-intro">
            {result.source === 'example' ? 'Synthetic example' : 'Yahoo Finance'} · As of{' '}
            {dateLabel(result.as_of_date, true)} · Same observations as the workspace.
          </p>
          <Chart result={result} />
        </Dialog>
      )}
      {modal === 'method' && (
        <Dialog key="method" title="Calculation notes" close={() => setModal(null)}>
          <div className="method-content">
            <p className="dialog-intro">Filter thresholds, units, and data conventions.</p>
            <h3>Filter rules</h3>
            <ol>
              <li>30-observation average stock volume ≥ 1,500,000 shares.</li>
              <li>30-calendar-day IV divided by historical RV ≥ 1.25.</li>
              <li>Nearest-to-45-day IV slope ≤ −0.00406 decimal IV per calendar day.</li>
            </ol>
            <p>
              All three pass: “Recommended” in the original calculator. Slope plus one other pass:
              “Consider.” Otherwise: “Avoid.” This interface describes these as filter matches, not
              calibrated predictions.
            </p>
            <h3>Calculation conventions</h3>
            <p>
              Historical volatility preserves the supplied OHLC formula, its 30-observation window,
              and 252-day annualization. It is labeled a legacy estimate rather than an
              independently verified implementation of the published Yang–Zhang estimator. IV
              interpolation is linear with flat endpoints.
            </p>
            <p>
              The displayed move is the front ATM call-plus-put midpoint divided by the underlying
              price. It is a rough premium-based measure through that expiration, not a confidence
              interval.
            </p>
            <h3>What changed</h3>
            <p>
              Explicit positional price lookup, consistent errors, finite-value checks, matched ATM
              strikes, expiration guards, event context, source labels, local snapshots, and CSV
              exports. An invalid quote stops analysis rather than silently selecting a more
              favorable contract.
            </p>
            <h3>Research limits</h3>
            <p>
              This tool contains no historical backtest, automated execution, or return forecast.
              Calendar reference costs exclude commissions and assume standard 100-share contracts.
              Yahoo data may be delayed; retrieval time is not a verified quote timestamp.
            </p>
          </div>
        </Dialog>
      )}
      {modal === 'saved' && (
        <Dialog key="saved" title="Saved snapshots" close={() => setModal(null)}>
          <p className="dialog-intro">
            Stored on this computer. Opening a snapshot does not fetch new prices.
          </p>
          {savedLoading ? (
            <div className="saved-empty">
              <SpinnerGap className="spin" size={26} />
              <p>Opening snapshots…</p>
            </div>
          ) : snapshots.length ? (
            <div className="snapshot-list">
              {snapshots.map((s) => (
                <button key={s.id} onClick={() => loadSnapshot(s.id)}>
                  <span className="snapshot-icon">
                    {s.source === 'example' ? <Flask size={21} /> : <ChartLineUp size={21} />}
                  </span>
                  <span>
                    <strong>
                      {s.symbol}
                      <small>
                        {s.source === 'example' ? 'Synthetic example' : s.classification.label}
                      </small>
                    </strong>
                    <span>Saved {timeLabel(s.saved_at)}</span>
                  </span>
                  <ArrowRight size={18} />
                </button>
              ))}
            </div>
          ) : (
            <div className="saved-empty">
              <FolderSimple size={35} />
              <h3>Your research, kept together.</h3>
              <p>Save an analysis to return to its numbers, source, and settings later.</p>
            </div>
          )}
        </Dialog>
      )}
    </>
  );
}
