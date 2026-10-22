export type Quote = {
  strike: number;
  bid: number;
  ask: number;
  mid: number;
  iv: number;
  open_interest: number | null;
  last_trade_time: string | null;
  contract_size: string;
};
export type Point = { expiry: string; dte: number; iv: number; call: Quote; put: Quote };
export type Result = {
  schema_version: string;
  id: string;
  symbol: string;
  company_name: string;
  source: 'example' | 'yahoo';
  source_label: string;
  retrieved_at: string;
  saved_at?: string;
  as_of_date: string;
  currency: string;
  price: number;
  classification: {
    key: 'matches' | 'partial' | 'no_match';
    label: string;
    original_label: string;
    passed: number;
  };
  flags: { avg_volume: boolean; iv_rv_ratio: boolean; slope: boolean };
  metrics: {
    avg_volume: number;
    iv30: number;
    rv30: number;
    iv_rv_ratio: number;
    slope_decimal_per_day: number;
    slope_points_per_day: number;
    expected_move_pct: number;
  };
  thresholds: { avg_volume: number; iv_rv_ratio: number; slope: number };
  points: Point[];
  event: {
    date: string | null;
    session: string;
    status: string;
    source: string;
    days_until?: number;
    in_front_expiry: boolean | null;
  };
  calendar: {
    front_expiry: string;
    back_expiry: string;
    strike: number;
    gap_days: number;
    mid_debit: number;
    conservative_debit: number;
    multiplier: number;
  } | null;
  warnings: { code: string; message: string }[];
  expected_move_expiry: string;
  method: {
    name: string;
    version: string;
    rv_window_observations: number;
    annualization: number;
    interpolation: string;
    history_adjustment: string;
  };
  history_observations: number;
};
export type Snapshot = Pick<
  Result,
  'id' | 'symbol' | 'source' | 'classification' | 'retrieved_at'
> & { saved_at: string };
