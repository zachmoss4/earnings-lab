# Methodology

This document describes the calculation rules, units, input checks, and data conventions.

## Filter rules

| Feature | Calculation | Passing condition |
|---|---|---|
| Share volume | Mean of the latest 30 daily volume observations | ≥ 1,500,000 shares |
| IV/RV | IV interpolated to 30 calendar days / legacy OHLC realized volatility | ≥ 1.25 |
| Term slope | `(IV45 − IV_front) / (45 − DTE_front)` | ≤ −0.00406 decimal IV per calendar day |

The interface converts the slope to volatility percentage points per day: −0.00406 decimal IV is −0.406 points. All conditions pass → original “Recommended”; slope and one other pass → “Consider”; otherwise → “Avoid.” The interface uses descriptive filter labels instead of presenting these as forecasts.

The 30-day IV horizon is in calendar days. Historical RV uses 30 trading observations plus a preceding close, annualized with 252. These are intentionally distinct conventions.

## Volatility estimate and interpolation

The supplied historical-volatility function combines overnight squared log returns, a k-weighted close-to-close squared-return component, and a Rogers–Satchell term. Rolling sums use `window − 1`. This release preserves that exact formula and compares numerical output with the preserved source on a controlled fixture. It does not assert that the implementation faithfully reproduces every property of the published Yang–Zhang estimator.

ATM IV averages the nearest call's and put's IV. This release requires their strikes to match and their quotes to be valid. A bad nearest contract stops analysis instead of selecting a farther, more favorable-looking contract. IV is interpolated linearly, with flat endpoints, matching the supplied convention. NumPy interpolation replaces the original SciPy dependency for this bounded linear calculation.

At least one future expiration must fall before day 45 and one on or after day 45. Today's expiration is excluded. This also removes the original day-45 division-by-zero case. If the earliest expiration is beyond day 30, IV30 is clamped and an explicit warning is shown.

## Input validation and data provenance

- USD pricing must be confirmed by Yahoo history metadata. This release targets USD-denominated equity options.
- Prices, bids, asks, strikes, and IV must be finite and positive. Crossed bid/ask quotes and inconsistent OHLC ranges are rejected.
- Required history includes at least 31 observations. Negative or missing volume is rejected.
- Option spread widths above 20% of midpoint and open interest below 100 are separate review notes, not changes to the original three thresholds.
- Adjusted OHLC history is explicitly requested. The latest daily close supplies the displayed underlying price using positional indexing.
- A possibly incomplete latest daily bar remains included under the original convention and is flagged during the regular session.
- Retrieval time describes when the request finished, not when every bid/ask quote was established. Last-trade time is not substituted for quote time.
- Requests with the same ticker and manual-event input reuse a result for up to 60 seconds, preserving its original retrieval time.

## Earnings context

Yahoo calendar dates remain estimates. If Yahoo supplies a range, the earliest future date is displayed and the range is flagged. The app does not invent an announcement session. A manual date/session remains labeled as manually supplied.

The front expiration is checked against the event date/session. A same-day after-close announcement is not covered by that expiration. A same-day event with unknown session remains uncertain. The original filter classification remains separate from event eligibility, and an uncovered event is flagged.

The tool does not schedule trades, place orders, or perform automatic exits.

## Move and calendar references

The premium-based move is `(front call midpoint + front put midpoint) / underlying price × 100`. It applies through the displayed front expiration. It is not a confidence interval or a calibrated prediction.

The calendar reference uses the same call strike across two valid expirations and chooses the available back expiration closest to a 30-day gap. It is shown only when both legs report regular contracts and the midpoint debit is positive. Cost uses the standard 100-share multiplier; five spreads comprise ten leg contracts. The conservative quote illustration buys the back ask and sells the front bid. Neither estimate includes commissions or guarantees a fill. No portfolio allocation is recommended.

## Snapshots and examples

Snapshots preserve inputs, units, thresholds, selected quote data, source, calculation version, event assumptions, and retrieval time as local JSON. CSV exports summarize the result and its provenance. Opening a snapshot does not fetch new quotes.

The optional offline example is generated from a deterministic synthetic fixture. Its symbol, prices, option chains, volume, and event are fabricated and prominently labeled. A failed Yahoo request never silently falls back to that fixture.

See [verification](verification.md) for the tested environment and checks.
