"""Fabricated, deterministic fixtures. These are never represented as market data."""

from datetime import date, timedelta
import numpy as np
import pandas as pd
from .engine import MarketInputs


def example_inputs() -> MarketInputs:
    anchor = date(2026, 10, 20)
    rng = np.random.default_rng(14)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, .012, 80)))
    opens = closes * np.exp(rng.normal(0, .006, 80))
    frame = pd.DataFrame({"Open": opens, "High": np.maximum(opens, closes) * 1.009,
                          "Low": np.minimum(opens, closes) * .991, "Close": closes,
                          "Volume": rng.integers(2_100_000, 4_900_000, 80)},
                         index=pd.bdate_range(end=anchor, periods=80))
    chains = {}
    for dte, iv, premium in [(3, .86, 3.35), (10, .69, 3.95), (17, .58, 4.35), (24, .51, 4.65), (31, .465, 4.95), (38, .43, 5.2), (52, .39, 5.65)]:
        expiry = (anchor + timedelta(days=dte)).isoformat()
        call = pd.DataFrame([{"strike": 100., "bid": premium - .08, "ask": premium + .08,
                              "impliedVolatility": iv + .005, "openInterest": 1840 + dte * 7,
                              "contractSize": "REGULAR"}])
        put = pd.DataFrame([{"strike": 100., "bid": premium - .12, "ask": premium + .04,
                             "impliedVolatility": iv - .005, "openInterest": 1630 + dte * 6,
                             "contractSize": "REGULAR"}])
        chains[expiry] = call, put
    return MarketInputs("EXAMPLE", "Example company", 100., frame, chains, anchor, "example",
                        {"date": "2026-10-21", "session": "after_close", "status": "synthetic", "source": "Fabricated demonstration event"},
                        [{"code": "synthetic", "message": "All prices, options, volumes, and event details in this example are fabricated. No network request was made."}])
