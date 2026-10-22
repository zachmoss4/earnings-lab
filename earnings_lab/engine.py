"""Deterministic analysis. No network, GUI, or portfolio-return predictions.

The OHLC estimator and three filters follow the reference implementation.
See docs/methodology.md for units and calculation conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
import math
import re
import uuid

import numpy as np
import pandas as pd

METHOD_VERSION = "original-rules-1.0"
THRESHOLDS = {"avg_volume": 1_500_000, "iv_rv_ratio": 1.25, "slope": -0.00406}


class AnalysisError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.status = code, status


@dataclass
class MarketInputs:
    symbol: str
    name: str
    price: float
    history: pd.DataFrame
    chains: dict[str, tuple[pd.DataFrame, pd.DataFrame]]
    as_of: date
    source: str = "yahoo"
    event: dict[str, Any] | None = None
    warnings: list[dict[str, str]] | None = None


def symbol_input(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=\-]{0,14}", value.strip().upper()):
        raise AnalysisError("invalid_symbol", "Enter a valid ticker, such as AAPL or BRK-B.")
    return value.strip().upper()


def selected_expiries(expiries: list[str], as_of: date) -> list[str]:
    try:
        dates = sorted({date.fromisoformat(x) for x in expiries if date.fromisoformat(x) > as_of})
    except (ValueError, TypeError):
        raise AnalysisError("invalid_expiries", "The provider returned an invalid expiration date.") from None
    near = [x for x in dates if x < as_of + timedelta(days=45)]
    far = [x for x in dates if x >= as_of + timedelta(days=45)]
    if not near or not far:
        raise AnalysisError("insufficient_expiries", "This analysis needs an expiration before day 45 and one on or after day 45.")
    return [x.isoformat() for x in near + far[:1]]


def legacy_realized_volatility(history: pd.DataFrame, window: int = 30) -> float:
    """Preserve the supplied formula, rather than silently substitute an estimator."""
    columns = ["Open", "High", "Low", "Close", "Volume"]
    if not all(x in history.columns for x in columns) or len(history) < window + 1:
        raise AnalysisError("insufficient_history", "At least 31 daily OHLCV observations are required.")
    tail = history[columns].tail(window + 1).astype(float)
    values = tail.to_numpy()
    if not np.isfinite(values).all() or (tail[columns[:4]] <= 0).any().any() or (tail.Volume < 0).any():
        raise AnalysisError("invalid_history", "Recent price history contains missing or invalid values.")
    if (tail.High < tail[["Open", "Close", "Low"]].max(axis=1)).any() or (tail.Low > tail[["Open", "Close"]].min(axis=1)).any():
        raise AnalysisError("invalid_history", "Recent OHLC price ranges are inconsistent.")
    ho = np.log(tail.High / tail.Open)
    lo = np.log(tail.Low / tail.Open)
    co = np.log(tail.Close / tail.Open)
    oc = np.log(tail.Open / tail.Close.shift(1))
    cc = np.log(tail.Close / tail.Close.shift(1))
    rs = ho * (ho - co) + lo * (lo - co)
    k = 0.34 / (1.34 + ((window + 1) / (window - 1)))
    variance = (oc.iloc[-window:].pow(2).sum() + k * cc.iloc[-window:].pow(2).sum() + (1 - k) * rs.iloc[-window:].sum()) / (window - 1)
    rv = math.sqrt(float(variance) * 252) if variance > 0 else 0.0
    if not math.isfinite(rv) or rv <= 0:
        raise AnalysisError("invalid_rv", "Realized volatility could not be calculated from this history.")
    return rv


def _quote(row: pd.Series) -> dict[str, Any]:
    try:
        strike, bid, ask, iv = (float(row[x]) for x in ["strike", "bid", "ask", "impliedVolatility"])
    except (KeyError, ValueError, TypeError):
        raise AnalysisError("invalid_quote", "Required option quote fields are missing.") from None
    if not all(math.isfinite(x) and x > 0 for x in [strike, bid, ask, iv]) or ask < bid:
        raise AnalysisError("invalid_quote", "The nearest ATM option has a missing, zero, or crossed quote.")
    try:
        oi_value = float(row.get("openInterest"))
        oi = int(oi_value) if math.isfinite(oi_value) and oi_value >= 0 else None
    except (ValueError, TypeError, OverflowError):
        oi = None
    try:
        traded_value = row.get("lastTradeDate")
        traded = pd.Timestamp(traded_value).isoformat() if traded_value is not None and pd.notna(traded_value) else None
    except (ValueError, TypeError):
        traded = None
    size = str(row.get("contractSize", "UNKNOWN"))
    return {"strike": strike, "bid": bid, "ask": ask, "mid": (bid + ask) / 2, "iv": iv,
            "open_interest": oi, "last_trade_time": traded, "contract_size": size}


def _atm_point(expiry: str, calls: pd.DataFrame, puts: pd.DataFrame, price: float, as_of: date) -> dict[str, Any]:
    if calls.empty or puts.empty or "strike" not in calls or "strike" not in puts:
        raise AnalysisError("empty_chain", "No usable call and put chain is available.")
    for frame in [calls, puts]:
        strikes = pd.to_numeric(frame["strike"], errors="coerce")
        if not np.isfinite(strikes).all() or (strikes <= 0).any():
            raise AnalysisError("invalid_strikes", "The option chain contains missing or invalid strike prices.")
    # Keep original nearest-ATM selection; do not move to a farther, better-looking
    # strike just because the original candidate has an unusable quote.
    call_row = calls.loc[(pd.to_numeric(calls.strike) - price).abs().idxmin()]
    put_row = puts.loc[(pd.to_numeric(puts.strike) - price).abs().idxmin()]
    call, put = _quote(call_row), _quote(put_row)
    if call["strike"] != put["strike"]:
        raise AnalysisError("mismatched_strikes", "The nearest call and put do not share a strike.")
    return {"expiry": expiry, "dte": (date.fromisoformat(expiry) - as_of).days,
            "iv": (call["iv"] + put["iv"]) / 2, "call": call, "put": put}


def classify(volume: bool, ratio: bool, slope: bool) -> dict[str, Any]:
    count = sum([volume, ratio, slope])
    if count == 3:
        return {"key": "matches", "label": "Meets all filters", "original_label": "Recommended", "passed": count}
    if slope and (volume or ratio):
        return {"key": "partial", "label": "Partial match", "original_label": "Consider", "passed": count}
    return {"key": "no_match", "label": "Does not meet filters", "original_label": "Avoid", "passed": count}


def analyze(inputs: MarketInputs) -> dict[str, Any]:
    symbol = symbol_input(inputs.symbol)
    if not math.isfinite(inputs.price) or inputs.price <= 0:
        raise AnalysisError("invalid_price", "A valid underlying price is required.")
    warnings = list(inputs.warnings or [])
    points: list[dict[str, Any]] = []
    for expiry in selected_expiries(list(inputs.chains), inputs.as_of):
        try:
            points.append(_atm_point(expiry, *inputs.chains[expiry], inputs.price, inputs.as_of))
        except AnalysisError as exc:
            # Never silently shift the front expiry or interpolation bracket.
            raise AnalysisError(exc.code, f"{expiry}: {exc}") from None
    if len(points) < 2:
        raise AnalysisError("insufficient_points", "At least two valid IV points are required.")
    dtes, ivs = [p["dte"] for p in points], [p["iv"] for p in points]
    iv30, iv45 = float(np.interp(30, dtes, ivs)), float(np.interp(45, dtes, ivs))
    rv = legacy_realized_volatility(inputs.history)
    volume = float(inputs.history.Volume.tail(30).mean())
    slope = (iv45 - points[0]["iv"]) / (45 - dtes[0])
    ratio = iv30 / rv
    front = points[0]
    move = (front["call"]["mid"] + front["put"]["mid"]) / inputs.price * 100
    if dtes[0] > 30:
        warnings.append({"code": "iv30_clamped", "message": "The first expiration is beyond 30 days. IV30 uses the original endpoint-clamping convention."})
    for point in points:
        for kind in ["call", "put"]:
            q = point[kind]
            if (q["ask"] - q["bid"]) / q["mid"] > .20:
                warnings.append({"code": "wide_spread", "message": f"{point['expiry']} {kind}: the bid–ask spread exceeds 20% of midpoint."})
            if q["open_interest"] is None or q["open_interest"] < 100:
                warnings.append({"code": "low_oi", "message": f"{point['expiry']} {kind}: open interest is missing or below 100 contracts."})
    if inputs.source == "yahoo":
        warnings.append({"code": "quote_time_unverified", "message": "Yahoo does not provide verified bid/ask timestamps here. Retrieval time is not quote time; displayed prices may be delayed."})
    event = dict(inputs.event or {"date": None, "session": "unknown", "status": "unavailable", "source": "Not supplied"})
    included = None
    if event.get("date"):
        event_day = date.fromisoformat(event["date"])
        front_day = date.fromisoformat(front["expiry"])
        included = front_day > event_day or (front_day == event_day and event.get("session") == "before_open")
        if front_day == event_day and event.get("session") == "unknown":
            included = None
        event["days_until"] = (event_day - inputs.as_of).days
        if event_day < inputs.as_of:
            included = False
        if included is False:
            warnings.append({"code": "event_not_covered", "message": "The front expiration does not cover the selected future earnings event. The original filter result is not an event-qualified setup."})
    else:
        warnings.append({"code": "event_unknown", "message": "An upcoming earnings date could not be verified. Confirm the date and announcement session before using this screen."})
    if event.get("session") == "unknown":
        warnings.append({"code": "session_unknown", "message": "Announcement timing is unverified. Before-open and after-close releases require different entry sessions."})
    event["in_front_expiry"] = included
    calendar = None
    candidates = [p for p in points[1:] if p["call"]["strike"] == front["call"]["strike"]]
    if candidates:
        back = min(candidates, key=lambda p: abs(p["dte"] - front["dte"] - 30))
        debit = back["call"]["mid"] - front["call"]["mid"]
        if debit > 0 and all(p["call"]["contract_size"] == "REGULAR" for p in [front, back]):
            calendar = {"front_expiry": front["expiry"], "back_expiry": back["expiry"], "strike": front["call"]["strike"],
                        "gap_days": back["dte"] - front["dte"], "mid_debit": debit,
                        "conservative_debit": back["call"]["ask"] - front["call"]["bid"], "multiplier": 100}
    flags = {"avg_volume": volume >= THRESHOLDS["avg_volume"], "iv_rv_ratio": ratio >= THRESHOLDS["iv_rv_ratio"], "slope": slope <= THRESHOLDS["slope"]}
    return {"schema_version": "1.0", "id": str(uuid.uuid4()), "symbol": symbol, "company_name": inputs.name,
            "source": inputs.source, "source_label": "Synthetic offline example" if inputs.source == "example" else "Yahoo Finance via yfinance",
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "as_of_date": inputs.as_of.isoformat(), "currency": "USD", "price": inputs.price,
            "classification": classify(flags["avg_volume"], flags["iv_rv_ratio"], flags["slope"]), "flags": flags,
            "metrics": {"avg_volume": volume, "iv30": iv30, "rv30": rv, "iv_rv_ratio": ratio,
                        "slope_decimal_per_day": slope, "slope_points_per_day": slope * 100, "expected_move_pct": move},
            "thresholds": THRESHOLDS.copy(), "points": points, "event": event, "calendar": calendar,
            "warnings": warnings, "expected_move_expiry": front["expiry"],
            "method": {"name": "Original rules", "version": METHOD_VERSION, "rv_window_observations": 30,
                       "annualization": 252, "interpolation": "Linear IV, flat endpoints", "history_adjustment": "Adjusted OHLC"},
            "history_observations": len(inputs.history)}

