# Software Requirements — Market Analytics (MKT)

**Document ID:** SRD-MKT
**Version:** 0.3.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.3.0: SRD-MKT-002.001–.010 added as Draft — sector strength, rotation and stock RS (P2).
> v0.2.0: SRD-MKT-001.001–.012 added as Draft — regime, breadth and fear (P1).
> v0.1.0: Empty. Rows are added per phase, starting with the first FO of this tool.

---

## FO-MKT-001: Market Regime, Breadth and Fear

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-001.001 | FO-MKT-001 | Must | Daily bars for SPY and the S&P 500 members are read from `candles.db` in read-only mode. | `price_1d` | bars by symbol | Never writes `candles.db`; members from the saved S&P 500 list | Implemented |
| SRD-MKT-001.002 | FO-MKT-001 | Must | Regime is Uptrend when SPY closes above its 50 and 200-day averages and the 50-day average is higher than 10 days ago, Downtrend in the mirror case, else Choppy. | SPY closes | regime | Needs 210 SPY bars | Implemented |
| SRD-MKT-001.003 | FO-MKT-001 | Must | Volatility is SPY's 20-day annualised swing, rated Calm below the 30th and High above the 70th percentile of the past 252 days, else Normal. | SPY closes | volatility, percentile | — | Implemented |
| SRD-MKT-001.004 | FO-MKT-001 | Must | Breadth gives the share of members above their 20, 50 and 200-day averages, 52-week new highs and lows, and advancers and decliners. | member bars | breadth row | A member counts only with enough bars for that measure | Implemented |
| SRD-MKT-001.005 | FO-MKT-001 | Must | Daily VIX and VIX3M closes are fetched from Yahoo Finance and kept in `desk.db`. | network | VIX rows | Fetch only missing days; a failure is logged and never stops the step | Implemented |
| SRD-MKT-001.006 | FO-MKT-001 | Must | The fear score adds points for VIX level, VIX above VIX3M, High volatility and weak breadth, and maps 0–1 to Calm, 2–3 to Nervous, 4 or more to Fearful. | VIX, volatility, breadth | fear, score | Without VIX the note says "no VIX" | Implemented |
| SRD-MKT-001.007 | FO-MKT-001 | Must | Results are kept in `regime_snapshot` and `breadth_daily` tables in `desk.db`, one row per trading day. | rows | tables | Tables made by MKT on first use; re-running a day replaces its row | Implemented |
| SRD-MKT-001.008 | FO-MKT-001 | Must | The first run fills every day that has enough history; later runs add only days not yet stored. | stored dates | new rows | — | Implemented |
| SRD-MKT-001.009 | FO-MKT-001 | Must | A day with data for fewer than 80% of members is not stored and is logged. | member count | skip | — | Implemented |
| SRD-MKT-001.010 | FO-MKT-001 | Must | The data date is the latest SPY candle; when it is older than the last weekday the note says the candles are stale. | SPY dates, clock | note | Stale data is not an error | Implemented |
| SRD-MKT-001.011 | FO-MKT-001 | Must | The work runs as the desk step "Market regime" registered for the desk. | desk run | step | `market` never imports `desk` | Implemented |
| SRD-MKT-001.012 | FO-MKT-001 | Should | Each run logs the days added, the latest regime and fear, and the data date. | step | log lines | `[Regime]` prefix | Implemented |

## FO-MKT-002: Sector Strength and Rotation

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-002.001 | FO-MKT-002 | Must | Each member stock is placed in its sector from the saved S&P 500 list, and member candles are aligned to SPY's trading days. | list, candles | sector map, bars | Stocks without a sector are left out and counted in the log | Implemented |
| SRD-MKT-002.002 | FO-MKT-002 | Must | A sector line starts at 100 and moves each day by the average daily move of its members that have a bar on both days. | member closes | line per sector | Equal weight | Implemented |
| SRD-MKT-002.003 | FO-MKT-002 | Must | Sectors are ranked 1–11 by the average of their 1, 3 and 6-month moves minus SPY's moves over the same days. | lines, SPY | relative moves, rank | 21, 63 and 126 trading days | Implemented |
| SRD-MKT-002.004 | FO-MKT-002 | Must | RS-ratio is 100 times the sector line over SPY divided by its 50-day average; RS-momentum is 100 times RS-ratio over its value 10 days before. | lines, SPY | ratio, momentum | — | Implemented |
| SRD-MKT-002.005 | FO-MKT-002 | Must | The quadrant is Leading (ratio and momentum at or above 100), Weakening (ratio at or above, momentum below), Lagging (both below) or Improving (ratio below, momentum at or above). | ratio, momentum | quadrant | — | Implemented |
| SRD-MKT-002.006 | FO-MKT-002 | Must | A stock's RS score is 40% of its 3-month move plus 20% each of its 6, 9 and 12-month moves, and its rating is its percentile among members, from 1 to 99. | member closes | score, rating | Needs 95% of 252 bars; others get no rating | Implemented |
| SRD-MKT-002.007 | FO-MKT-002 | Must | Each rated stock gets its rank by score inside its sector and the sector's size. | scores, sectors | rank | 1 is the strongest | Implemented |
| SRD-MKT-002.008 | FO-MKT-002 | Must | Results are kept in `sector_daily` (one row per sector per day) and `stock_rs` (one row per stock per day) in `desk.db`. | rows | tables | Re-running a day replaces its rows | Implemented |
| SRD-MKT-002.009 | FO-MKT-002 | Must | The desk step "Sectors" runs after "Market regime", fills history on its first run, recomputes the last 7 days and skips days with data for fewer than 80% of members. | desk run | rows | `market` never imports `desk`; a missing candle file never fails the run | Implemented |
| SRD-MKT-002.010 | FO-MKT-002 | Should | Each run logs the days added, the top 3 sectors and sectors that changed quadrant. | step | log lines | `[Sectors]` prefix | Implemented |
