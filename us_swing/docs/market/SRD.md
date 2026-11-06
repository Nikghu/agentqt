# Software Requirements — Market Analytics (MKT)

**Document ID:** SRD-MKT
**Version:** 0.3.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.6.1: SRD-MKT-005.001–.005 reworded by skill; no employee names (user, 2026-11-06).
> v0.6.0: SRD-MKT-005.001–.005 added as Draft — regime view skill (P5a).
> v0.5.0: SRD-MKT-004.001–.009 added as Draft — proof on past data (P4).
> v0.4.0: SRD-MKT-003.001–.012 added as Draft — money flow, setups, readiness score and ideas (P3).
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

## FO-MKT-003: Money Flow, Setups, Readiness Score and Ideas

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-003.001 | FO-MKT-003 | Must | Daily bars include volume, and stocks whose 20-day average dollar volume is below $20M are not scored. | candles | bars, liquid set | Aligned to SPY's days | Implemented |
| SRD-MKT-003.002 | FO-MKT-003 | Must | Money flow (0–1) is the mean of net accumulation days over 25 sessions, 20-day Chaikin money flow and 50-day up against down volume; the short value is 1 minus the long value. | bars | flow per side | Each part clipped to 0–1 | Implemented |
| SRD-MKT-003.003 | FO-MKT-003 | Must | Long setups are Squeeze, Flat base and Pullback; each match gives a trigger, a stop and a tightness from 0 to 1. | bars | setup, trigger, stop | Best match kept | Implemented |
| SRD-MKT-003.004 | FO-MKT-003 | Must | Short setups are Failed breakout, Lower highs and Breakdown; each match gives a trigger, a stop and a tightness from 0 to 1. | bars | setup, trigger, stop | Best match kept | Implemented |
| SRD-MKT-003.005 | FO-MKT-003 | Must | The score is RS 20, money flow 20, setup 20, sector 15 and regime 15 points, scaled by 100/90 while news is not scored. | parts | score 0–100 per side | News 10 points join in P5c | Implemented |
| SRD-MKT-003.006 | FO-MKT-003 | Must | A stock more than 8% past its 20-day average in the idea's direction loses 10 points, and the score never goes below 0. | bars | penalty | — | Implemented |
| SRD-MKT-003.007 | FO-MKT-003 | Must | Per side, the 10 best stocks scoring 60 or more are the idea list; a stock with earnings within 5 trading days or against the regime goes to Watch. | scores | ideas, watch | Shorts are against the regime in an Uptrend, longs in a Downtrend | Implemented |
| SRD-MKT-003.008 | FO-MKT-003 | Must | Each idea and Watch name keeps up to 5 one-line reasons with its setup, trigger and stop. | parts | reasons | Plain words, no codes | Implemented |
| SRD-MKT-003.009 | FO-MKT-003 | Must | Next earnings dates come from Yahoo Finance for the 30 best-scored stocks per side on the latest day only. | symbols | dates | A failed fetch means no earnings check and a note | Implemented |
| SRD-MKT-003.010 | FO-MKT-003 | Must | Results are kept in `stock_score`, `ideas` and `idea_reasons` in `desk.db`. | rows | tables | Re-running a day replaces its rows | Implemented |
| SRD-MKT-003.011 | FO-MKT-003 | Must | The desk step "Ideas" runs after "Sectors", fills history on its first run, recomputes the last 7 days and skips days without regime and sector rows or with data for fewer than 80% of members. | desk run | rows | A missing candle file never fails the run | Implemented |
| SRD-MKT-003.012 | FO-MKT-003 | Should | Each run logs the days added, the idea and Watch counts per side and the top 3 ideas per side. | step | log lines | `[Ideas]` prefix | Implemented |

## FO-MKT-004: Proof on Past Data

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-004.001 | FO-MKT-004 | Must | Daily bars of the members and SPY come from the Backtest Data store's daily files, read only. | `backtest/1d/*.parquet` | bars | Same member list and SPY day alignment as P2; no import of the backtest tool | Implemented |
| SRD-MKT-004.002 | FO-MKT-004 | Must | For every past day the regime, sector quadrant and rank, RS rating, score, setup and idea list are recomputed with the P1–P3 rules from data up to that day only. | bars | scores and idea status per day | No past earnings dates, so the earnings Watch rule is not applied | Implemented |
| SRD-MKT-004.003 | FO-MKT-004 | Must | Each scored stock-day gets 5, 10 and 20-day returns per side, entering at the next day's open and exiting at the close, and the same against SPY. | bars, scores | forward returns | Short return is minus the long return; days without enough future bars are left out | Implemented |
| SRD-MKT-004.004 | FO-MKT-004 | Must | Results are grouped per side and horizon by score band (under 40, 40–50, 50–60, 60–70, 70–80, 80+), by setup and by idea status (list, Watch, not picked). | forward returns | count, days, win rate, average return, average against SPY | Win means a return above 0 | Implemented |
| SRD-MKT-004.005 | FO-MKT-004 | Must | A side passes when, at 10 days, stocks scoring 70+ average a positive return against SPY and beat stocks scoring under 40. | group results | pass, fail or not enough data | Each group needs at least 100 stock-days | Implemented |
| SRD-MKT-004.006 | FO-MKT-004 | Must | Each run is kept in `proof_run` and `proof_stats` in `desk.db` with its data range and result per side. | results | tables | Older runs are kept; the latest is shown | Implemented |
| SRD-MKT-004.007 | FO-MKT-004 | Must | When daily history is shorter than 5 years, the report and the panel say so and point to Settings → Backtest Data. | data range | reminder text | — | Implemented |
| SRD-MKT-004.008 | FO-MKT-004 | Should | Each run logs the data range, stock count, scored days, time taken and result per side. | run | log lines | `[Proof]` prefix | Implemented |
| SRD-MKT-004.009 | FO-MKT-004 | Should | A run on 6 years of about 500 stocks finishes in under 10 minutes. | bars | — | Score worked out in yearly chunks | Implemented |

## FO-MKT-005: AI Experts, Risk Manager and Trade Manager

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-005.001 | FO-MKT-005 | Must | Regime view facts are the last 20 days of regime, volatility, fear and VIX, the latest breadth, sector ranks and quadrants, today's idea counts and the latest proof result. | `desk.db` | facts text | Fresh only when the latest regime day equals the latest SPY candle day | Implemented |
| SRD-MKT-005.002 | FO-MKT-005 | Must | The regime view answer is a typed view: regime (Uptrend, Choppy or Downtrend), confidence 0–1, 1 to 3 reasons and a brief of at most 400 characters. | facts | view | Checked by the gateway | Implemented |
| SRD-MKT-005.003 | FO-MKT-005 | Must | Each view is kept in `regime_view` per data day with the rule regime and whether they agree. | view | `regime_view` row | A new run on the same day replaces it | Implemented |
| SRD-MKT-005.004 | FO-MKT-005 | Must | The regime view adds its brief to the AI feed; when it disagrees with the rule regime the brief ends with a plain note. | view | feed item | Author is the employee's current name | Implemented |
| SRD-MKT-005.005 | FO-MKT-005 | Must | A default expert-level employee for the regime view ships in `market/employees/emp-001/` (generic name "Expert 1") with trigger `after_run`. | — | files | Calls per day 3; monthly cap USD 3; the Master user may rename or re-level it | Implemented |
