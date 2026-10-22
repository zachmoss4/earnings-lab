"""Yahoo adapter. Provider estimates and retrieval time are labeled explicitly."""

from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Any
import logging

import pandas as pd
import yfinance as yf

from .engine import AnalysisError, MarketInputs, selected_expiries, symbol_input

log = logging.getLogger(__name__)


def fetch_inputs(symbol: str, event_override: dict[str, Any] | None = None) -> MarketInputs:
    symbol = symbol_input(symbol)
    now = datetime.now(ZoneInfo("America/New_York"))
    warnings = []
    try:
        stock = yf.Ticker(symbol)
        dates = selected_expiries(list(stock.options), now.date())
        if len(dates) > 24:
            raise AnalysisError("too_many_expiries", "This first release supports equities with up to 24 expirations through day 45.")
        history = stock.history(period="3mo", auto_adjust=True, timeout=15)
        if history.empty:
            raise AnalysisError("no_history", "No recent price history was returned for this ticker.")
        price = float(history.Close.iloc[-1])
        chains = {}
        for expiry in dates:
            chain = stock.option_chain(expiry)
            chains[expiry] = (chain.calls, chain.puts)
        metadata = stock.get_history_metadata() or {}
        if metadata.get("currency") != "USD":
            raise AnalysisError("unsupported_currency", "This release supports USD-denominated equity options. The provider did not confirm USD pricing for this symbol.")
        name = metadata.get("longName") or metadata.get("shortName") or symbol
        event = None
        if event_override and event_override.get("date"):
            day = date.fromisoformat(event_override["date"])
            session = event_override.get("session", "unknown")
            if session not in ["unknown", "before_open", "after_close"]:
                raise AnalysisError("invalid_session", "Select a valid announcement session.")
            event = {"date": day.isoformat(), "session": session, "status": "manual", "source": "Manually supplied"}
        else:
            try:
                calendar = stock.get_calendar() or {}
                days = calendar.get("Earnings Date", [])
                future = sorted(pd.Timestamp(x).date() for x in days if pd.Timestamp(x).date() >= now.date())
                if future:
                    event = {"date": future[0].isoformat(), "session": "unknown", "status": "estimated", "source": "Yahoo calendar estimate"}
                    if len(future) > 1:
                        warnings.append({"code": "event_range", "message": "Yahoo supplied an earnings-date range. The earliest estimate is displayed; confirm the date with investor relations."})
            except Exception:
                log.info("Earnings calendar unavailable for %s", symbol)
        if history.index[-1].date() == now.date() and now.hour < 16:
            warnings.append({"code": "partial_session", "message": "The latest daily bar may be incomplete. The original rolling-volume and RV conventions include it."})
        if (now.date() - history.index[-1].date()).days > 4:
            warnings.append({"code": "old_history", "message": "The newest underlying price bar is more than four calendar days old."})
        return MarketInputs(symbol, name, price, history, chains, now.date(), "yahoo", event, warnings)
    except AnalysisError:
        raise
    except ValueError as exc:
        raise AnalysisError("provider_data", "The provider returned unusable data. Check the ticker or try again later.", 502) from exc
    except Exception as exc:
        log.warning("Yahoo request failed for %s (%s)", symbol, type(exc).__name__)
        raise AnalysisError("provider_unavailable", "Yahoo Finance could not complete this request. Try again later or open the offline example.", 502) from exc

