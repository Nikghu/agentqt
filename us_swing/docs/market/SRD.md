# Software Requirements — Market Analytics (MKT)

**Document ID:** SRD-MKT
**Version:** 0.10.2
**Status:** Draft
**Last Updated:** 2026-11-11
**Project:** US Swing Trading System

> v0.18.2: Step F setup tuning rows Implemented (12, 2026-11-11).
> v0.18.1: SRD-MKT-015.001–.012 approved by user 2026-11-11.
> v0.18.0: Autonomous desk step F (user, 2026-11-11): SRD-MKT-015.001–.012 added as Draft — setup tuning research.
> v0.17.2: Step E rows Implemented (5, 2026-11-11).
> v0.17.1: SRD-MKT-014.001–.005 approved by user 2026-11-11.
> v0.17.0: Autonomous desk step E (user, 2026-11-11): SRD-MKT-014.001–.005 added as Draft — lead research tickets.
> v0.16.2: Step D rows Implemented (12, 2026-11-11).
> v0.16.1: SRD-MKT-013.001–.012 approved by user 2026-11-11.
> v0.16.0: Autonomous desk step D (user, 2026-11-11): SRD-MKT-013.001–.012 added as Draft — check-ins and watchers.
> v0.15.2: SRD-MKT-012.001–.006 Implemented 2026-11-11.
> v0.15.1: SRD-MKT-012.001–.006 approved by user 2026-11-11.
> v0.15.0: Autonomous desk step C (user, 2026-11-11): SRD-MKT-012.001–.006 added as Draft — memory v1.
> v0.14.2: Step A rows Implemented 2026-11-11.
> v0.14.1: Step A rows approved by user 2026-11-11.
> v0.14.0: Autonomous desk step A (user, 2026-11-10): SRD-MKT-001.013–.017 added as Draft (candle check, Yahoo desk-only copy); SRD-MKT-005.015/.016 reopened (morning brief, feed kind `morning`).
> v0.13.2: SRD-MKT-011.001–.009 Implemented (RN-MKT-0.12.0-20261110).
> v0.13.1: SRD-MKT-011.001–.009 approved by user 2026-11-10.
> v0.13.0: SRD-MKT-011.001–.009 added as Draft — ask the desk for new data (P10).
> v0.12.2: SRD-MKT-010.001–.008 Implemented (RN-MKT-0.11.0-20261106).
> v0.12.1: SRD-MKT-010.001–.008 approved by user 2026-11-06.
> v0.12.0: SRD-MKT-010.001–.008 added as Draft — lead chat (P9).
> v0.11.2: SRD-MKT-009.001–.008 Implemented (RN-MKT-0.10.0-20261106).
> v0.11.1: SRD-MKT-009.001–.008 approved by user 2026-11-06.
> v0.11.0: SRD-MKT-009.001–.008 added as Draft — pick results (P8).
> v0.10.2: SRD-MKT-008.001–.006 Implemented (RN-MKT-0.9.0-20261106).
> v0.10.1: SRD-MKT-008.001–.006 approved by user 2026-11-06.
> v0.10.0: SRD-MKT-008.001–.006 added as Draft — link to Execution (P7).
> v0.9.1: SRD-MKT-007.001–.008 approved by user 2026-11-06; .004 reopened by user and reworded (no employee in the page row).
> v0.9.0: SRD-MKT-007.001–.008 added as Draft — AI report pages (P5d).
> v0.8.0: SRD-MKT-006.001–.012 added as Draft — news, economic calendar and event risk (P5c).
> v0.7.0: SRD-MKT-005.006–.018 — sector/flow view, setup review, risk check, lead brief (P5b).
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
| SRD-MKT-001.013 | FO-MKT-001 | Must | A desk step "Candle check" runs first and finds SPY and the members whose last daily bar is before the last closed trading day. | `candles.db`, desk copy, clock | stocks behind | Last closed trading day: today after 16:00 ET, else the trading day before | Implemented |
| SRD-MKT-001.014 | FO-MKT-001 | Must | Stocks behind get only their missing daily bars from Yahoo Finance, kept in `candle_topup` in `desk.db`. | stocks behind | copy rows | `candles.db` is never written; prices not dividend-adjusted, as IBKR | Implemented |
| SRD-MKT-001.015 | FO-MKT-001 | Must | The candle reader adds desk-copy bars only for days `candles.db` does not have for that stock. | both sources | bars | Copy rows on or before the stock's last `candles.db` day are deleted at each check | Implemented |
| SRD-MKT-001.016 | FO-MKT-001 | Must | When SPY or more than 2% of members are still behind after the top-up, the step stops the run before any AI call. | stocks behind | failed run | The error names the count; the desk retries per SRD-DSK-001.015 | Implemented |
| SRD-MKT-001.017 | FO-MKT-001 | Should | The check logs how many stocks were behind, how many were filled from Yahoo and how many are still behind. | step | log lines | `[Candles]` prefix | Implemented |

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
| SRD-MKT-003.005 | FO-MKT-003 | Must | The score is RS 20, money flow 20, setup 20, sector 15 and regime 15 points, scaled by 100/90 because news is not in this score. | parts | score 0–100 per side | News 10 points come in the final score of listed ideas (SRD-MKT-006.008); reopened by user 2026-11-06 | Implemented |
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
| SRD-MKT-005.006 | FO-MKT-005 | Must | Sector/flow view facts are the last 5 days of sector ranks, quadrants and 1 and 3-month relative moves, each sector's average money flow per side and the rule regime. | `desk.db` | facts text | Fresh only when the latest sector day equals the latest SPY candle day; needs nothing | Implemented |
| SRD-MKT-005.007 | FO-MKT-005 | Must | The sector/flow answer is 1 to 3 sectors to favour, 0 to 3 to avoid, a rotation note of at most 200 characters and a brief of at most 400. | facts | view | Sector names must be from the saved list | Implemented |
| SRD-MKT-005.008 | FO-MKT-005 | Must | Each sector/flow view is kept in `sector_view` per data day and its brief goes to the AI feed. | view | row, feed item | A new run on the same day replaces it | Implemented |
| SRD-MKT-005.009 | FO-MKT-005 | Must | Setup review facts are the day's listed ideas per side with score parts, setup, trigger, stop and reasons, plus the rule regime. | `ideas`, `idea_reasons`, `stock_score` | facts text | At most 20 ideas; needs nothing | Implemented |
| SRD-MKT-005.010 | FO-MKT-005 | Must | The setup review answer gives each idea a grade (A, B or C) and a note of at most 120 characters; it is kept in `setup_review`. | facts | rows | Ideas not in the facts are dropped and logged | Implemented |
| SRD-MKT-005.011 | FO-MKT-005 | Must | Hard risk limits in code veto a listed idea that is long in a Downtrend or short in an Uptrend, has a stop under 1% or over 10% from its trigger, has a trigger under $5, or is past the third idea of its sector on its side. | ideas, regime | code vetoes | Limits are constants in code, not in any file an agent can read or write | Implemented |
| SRD-MKT-005.012 | FO-MKT-005 | Must | The risk check AI reads the ideas that passed the code limits with their grades, news tags and the regime and sector views, and may veto more ideas with a reason of at most 120 characters. | facts | AI vetoes | Needs regime view, sector/flow view, setup review and news review; cannot undo a code veto; unknown ideas are dropped and logged; reopened by user 2026-11-06 | Implemented |
| SRD-MKT-005.013 | FO-MKT-005 | Must | Each listed idea gets one `risk_check` row per data day: pass or veto, by code or AI, and the reason. | vetoes | rows | Code limits are applied even when the AI call fails or the budget is used up | Implemented |
| SRD-MKT-005.014 | FO-MKT-005 | Must | Lead brief facts are the day's regime, sector/flow, setup, news and risk views, with a note for any view that is missing, and the ideas that passed with their final scores. | `desk.db` | facts text | Needs the four skills above and the news review; reopened by user 2026-11-06 | Implemented |
| SRD-MKT-005.015 | FO-MKT-005 | Must | The lead answer is up to 5 picks per side, each with a reason of at most 120 characters, and a morning brief of at most 1,200 characters. | facts | picks, brief | A pick that did not pass the risk check is dropped and logged; reopened 2026-11-10: evening → morning | Implemented |
| SRD-MKT-005.016 | FO-MKT-005 | Must | Picks are kept in `lead_picks` per data day and the morning brief goes to the AI feed as kind `morning`. | picks, brief | rows, feed item | A new run on the same day replaces the picks; old `evening` briefs stay readable; reopened 2026-11-10 | Implemented |
| SRD-MKT-005.017 | FO-MKT-005 | Must | Default employees ship as `emp-002` "Expert 2" (sector/flow view), `emp-003` "Expert 3" (setup review), `emp-004` "Expert 4" (risk check) and `emp-005` "Lead 1" (lead brief), all on `after_run`. | — | files | Experts report to `emp-005` as data only; calls per day 3, monthly cap USD 3 each | Implemented |
| SRD-MKT-005.018 | FO-MKT-005 | Must | The four new skills are added to the skill list in `core/desk_steps.py`. | — | skill paths | `market` never imports `desk` | Implemented |

## FO-MKT-006: News, Economic Calendar and Event Risk

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-006.001 | FO-MKT-006 | Must | A desk step "News" runs after "Ideas" and keeps, for each listed idea of the latest day, its Yahoo Finance headlines of the last 3 days in `news_items`. | listed ideas | `news_items` rows | At most 10 per stock; a failed fetch is logged and skipped; never fails the run | Implemented |
| SRD-MKT-006.002 | FO-MKT-006 | Must | The News step also keeps market headlines of the last 24 hours from a fixed list of public RSS feeds. | RSS feeds | `news_items` rows (no symbol) | At most 30; no API key; `feedparser` | Implemented |
| SRD-MKT-006.003 | FO-MKT-006 | Must | A headline is kept once (same link or same title for the same stock), and headlines older than 30 days are deleted on each run. | rows | `news_items` | — | Implemented |
| SRD-MKT-006.004 | FO-MKT-006 | Must | A yearly economic calendar in code lists the date, New York time, name and importance of each FOMC decision, CPI, jobs report, PCE and GDP release. | — | events | FOMC, CPI and jobs report are high; PCE and GDP medium; a year without a list is logged once as a warning | Implemented |
| SRD-MKT-006.005 | FO-MKT-006 | Must | News review facts are the listed ideas with their headlines, the market headlines, the rule regime and the economic events of the next 5 trading days. | `desk.db`, calendar | facts text | Fresh only when the news day equals the latest ideas day and SPY candle day; needs nothing | Implemented |
| SRD-MKT-006.006 | FO-MKT-006 | Must | The news review answer gives each listed idea a tone (positive, neutral or negative) and a reason of at most 120 characters, plus a market note of at most 400 characters. | facts | answer | Ideas not in the facts are dropped and logged | Implemented |
| SRD-MKT-006.007 | FO-MKT-006 | Must | News points are 10 for positive, 6 for neutral or no tag and 2 for negative, minus 3 when a high-importance event is on the next trading day, never below 0. | tone, calendar | points 0–10 | Event points are applied by code even when the model gives no answer | Implemented |
| SRD-MKT-006.008 | FO-MKT-006 | Must | Each listed idea's final score is 0.9 times its P3 score plus its news points, kept with its tone and reason in `news_tags`. | score, points | `news_tags` row | The P3 score and idea list stay unchanged; a new run on the same day replaces the rows | Implemented |
| SRD-MKT-006.009 | FO-MKT-006 | Must | The news review adds its market note to the AI feed. | answer | feed item | Author is the employee's current name | Implemented |
| SRD-MKT-006.010 | FO-MKT-006 | Must | The risk check and the lead brief also need the news review, and their facts show each idea's tone, reason and final score. | `news_tags` | facts text | A missing news view is noted, as for other views | Implemented |
| SRD-MKT-006.011 | FO-MKT-006 | Must | A default expert-level employee for the news review ships as `emp-006` (generic name "Expert 5") with trigger `after_run`, and the skill is added to the skill list. | — | files, skill path | Calls per day 3; monthly cap USD 3; `market` never imports `desk` | Implemented |
| SRD-MKT-006.012 | FO-MKT-006 | Should | The News step logs the stocks fetched, headlines kept, feeds that failed and rows deleted. | step | log lines | `[News]` prefix | Implemented |

## FO-MKT-007: AI Report Pages

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-007.001 | FO-MKT-007 | Must | Report page facts are the lead brief of the latest data day with its picks, and the regime, sector and news views of that day. | `desk.db` | facts text | Fresh only when the lead brief day equals the latest ideas day; needs the lead brief | Implemented |
| SRD-MKT-007.002 | FO-MKT-007 | Must | The report page answer gives a title of at most 80 characters and one HTML page with inline CSS of at most 200 KB. | facts | answer | HTML and CSS only; images only as inline data; limits are also in the JSON schema | Implemented |
| SRD-MKT-007.003 | FO-MKT-007 | Must | Code cleans the page before it is kept, removing scripts, event handler attributes, outside or local links and images, and any tag or attribute not on an allowed list. | answer | clean HTML | Allowed lists are in the DD; the cleaner lives in `core/` so the GUI can use it too | Implemented |
| SRD-MKT-007.004 | FO-MKT-007 | Must | Each clean page is added to `canvas_pages` as a new version with data day, version number, title, HTML and time. | clean HTML | row | Append-only; old versions are never changed or deleted | Implemented |
| SRD-MKT-007.005 | FO-MKT-007 | Must | When the answer is missing, invalid or still over 200 KB after cleaning, no version is added and no brief is posted. | answer | log line | The last good version stays; a later run on the same day tries again | Implemented |
| SRD-MKT-007.006 | FO-MKT-007 | Must | After a version is added, the report page skill posts a short feed brief with the page title to mark its day done. | page | feed item | Author is the employee's current name | Implemented |
| SRD-MKT-007.007 | FO-MKT-007 | Must | A default expert-level employee for report pages ships as `emp-007` (generic name "Expert 6") with trigger `after_run`, and the skill is added to the skill list. | — | files, skill path | Calls per day 3; monthly cap USD 3; `market` never imports `desk` | Implemented |
| SRD-MKT-007.008 | FO-MKT-007 | Should | The report page skill logs the data day, version, page size before and after cleaning, and the number of items removed. | step | log lines | `[Report]` prefix | Implemented |

## FO-MKT-008: Link to Execution

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-008.001 | FO-MKT-008 | Must | Trade picks are the lead picks of the latest data day whose risk check verdict is pass, with trigger and stop from `ideas`. | `desk.db` | pick list | Long and short both; a pick with no trigger or stop is not listed | Implemented |
| SRD-MKT-008.002 | FO-MKT-008 | Must | A pick's target is the trigger plus `trade_target_r` × R for a long and minus it for a short, where R is the gap between trigger and stop. | pick, desk settings | target | `trade_target_r` in `desk_ai.json`, default 2.0; a pick with R = 0 or a stop on the wrong side is not listed | Implemented |
| SRD-MKT-008.003 | FO-MKT-008 | Must | A pick is waiting until a `trade` approval row exists for it or the next NYSE market open after its data day has passed. | approvals, clock | pick state | Waiting, approved, rejected and expired are worked out, never stored; open time from `data/market_calendar` | Implemented |
| SRD-MKT-008.004 | FO-MKT-008 | Must | Each Master decision adds one `approvals` row with kind `trade`, subject `date:side:symbol`, decision approve or reject, and the entry, stop, target and quantity in detail. | decision | row | Append-only; a second decision on the same pick or on an expired pick is refused | Implemented |
| SRD-MKT-008.005 | FO-MKT-008 | Must | The pick and decision logic lives in `core/` so the GUI can use it, and only the app process writes trade approvals. | — | — | `market` never imports `desk`; the GUI never imports `desk`; no AI employee calls it | Implemented |
| SRD-MKT-008.006 | FO-MKT-008 | Should | Each trade decision logs the side, stock and decision, and the waiting list logs how many picks expired. | decision | log lines | `[AI Desk]` prefix; no employee names | Implemented |

## FO-MKT-009: Pick Results

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-009.001 | FO-MKT-009 | Must | A "Pick results" desk step runs after the Ideas step and works out a paper result for every lead pick from daily candles. | `lead_picks`, `ideas`, `candles.db` | `pick_results` rows | No AI call; every pick is worked out again on each run; `market` never imports `desk` | Implemented |
| SRD-MKT-009.002 | FO-MKT-009 | Must | A paper pick is entered on the first day its high (long) or low (short) reaches the trigger within 5 trading days after its data day, else it is no fill. | daily bars | entry day, entry | Entry price is the trigger; gaps are not modelled because daily bars have no open | Implemented |
| SRD-MKT-009.003 | FO-MKT-009 | Must | An entered paper pick ends on the first day its stop or target is reached, or at the close of its 10th trading day from entry. | daily bars | status, exit, R | Stop wins when both are reached on one day; until it ends the pick is open and marked at the latest close; target uses `trade_target_r` | Implemented |
| SRD-MKT-009.004 | FO-MKT-009 | Must | `pick_results` keeps one row per pick with date, side, symbol, status, entry day, entry, exit day, exit and R. | results | table | Status is no_fill, open, stop, target or time; rows are replaced on each run | Implemented |
| SRD-MKT-009.005 | FO-MKT-009 | Must | When an AI Desk trade cycle closes, the app adds one `pick_trades` row with the pick, side, entry, exit, quantity, P&L, R and exit reason. | closed cycle | row | Append-only; the pick is the newest executed approval for that stock and side; app process only | Implemented |
| SRD-MKT-009.006 | FO-MKT-009 | Must | A shared results view gives paper totals and breakdowns by Master decision, setup review grade and news tone, and real trade totals. | `desk.db` | results view | Lives in `core/`; grouped by skill input, never by employee name | Implemented |
| SRD-MKT-009.007 | FO-MKT-009 | Should | The weekly report adds a pick results section for picks whose data day is in the week. | results view | report text | Paper picks, fills, hit rate, average R; real trades, wins, P&L | Implemented |
| SRD-MKT-009.008 | FO-MKT-009 | Should | The Pick results step logs how many picks it worked out and how many are still open. | step | log lines | `[Results]` prefix | Implemented |

## FO-MKT-010: Lead Chat

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-010.001 | FO-MKT-010 | Must | A Master question from Command is saved as a `chat` row and posts one `chat_question` event. | question text | chat row, event | 1 to 500 characters; the GUI only adds rows and never imports `desk` | Implemented |
| SRD-MKT-010.002 | FO-MKT-010 | Must | A `chat_question` event has priority 0, a 2-minute deadline and a 30-minute expiry, one event per question. | question | event | Added to the desk event kinds; priority 0 skips the 30-minute wake gap | Implemented |
| SRD-MKT-010.003 | FO-MKT-010 | Must | A lead chat skill answers the oldest open question from the latest day's facts, the last 10 trading days of picks with paper results, and the last 6 chat turns. | `desk.db` | facts text | No skill needs; a question older than 30 minutes is not answered | Implemented |
| SRD-MKT-010.004 | FO-MKT-010 | Must | The answer is one text of at most 1500 characters, saved as a lead `chat` row linked to its question. | answer | chat row | Limit also in the JSON schema; `chat` is append-only | Implemented |
| SRD-MKT-010.005 | FO-MKT-010 | Must | When no valid answer comes, a failed reply row is saved for the question. | no answer | chat row | Plain text says the desk could not answer; no retry | Implemented |
| SRD-MKT-010.006 | FO-MKT-010 | Must | The chat answer has only text, and no chat code approves, rejects or places a trade. | — | — | No tools; schema has one text field | Implemented |
| SRD-MKT-010.007 | FO-MKT-010 | Must | A default lead-level chat employee ships as `emp-008` (generic name "Lead 2") with trigger `chat_question`, and the skill is added to the skill list. | — | files, skill path | Calls per day 200 so only the monthly cap USD 3 and the desk budget limit it; `market` never imports `desk` | Implemented |
| SRD-MKT-010.008 | FO-MKT-010 | Should | Each chat answer or failed reply logs the question number and the seconds it took. | answer | log line | `[Chat]` prefix | Implemented |

## FO-MKT-011: Ask the Desk for New Data

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-011.001 | FO-MKT-011 | Must | A Master data request from the Floor catalog is saved as a `data_requests` row and posts one `data_request` event. | request text | row, event | 1 to 300 characters; the GUI only adds rows and never imports `desk` | Implemented |
| SRD-MKT-011.002 | FO-MKT-011 | Must | A `data_request` event has priority 0, a 5-minute deadline and a 2-hour expiry, one event per request. | request | event | Added to the desk event kinds | Implemented |
| SRD-MKT-011.003 | FO-MKT-011 | Must | A data recipe skill turns the oldest open request into a recipe of source, columns, filters, sort and row limit from a fixed menu. | request, menu | recipe | Sources: scores, ideas, stock RS, sectors, pick results; the answer has no SQL | Implemented |
| SRD-MKT-011.004 | FO-MKT-011 | Must | Code checks each recipe against the menu and runs it read-only on the latest data day, with at most 100 rows. | recipe | rows | Table and column names only from the menu; filter values passed as parameters | Implemented |
| SRD-MKT-011.005 | FO-MKT-011 | Must | Each answer adds one `asked_products` row: proposed with its title and recipe, or failed with the reason. | answer | row | Append-only; one row per request; a recipe that fails the check is failed | Implemented |
| SRD-MKT-011.006 | FO-MKT-011 | Must | The Master approves or rejects a proposed product, and each decision is an `approvals` row of kind `data_product`. | decision | row | Append-only; a second decision on the same product is refused | Implemented |
| SRD-MKT-011.007 | FO-MKT-011 | Must | Approved products are listed in the Floor catalog and their rows come from the recipe on the latest data day each time they are shown. | approvals, recipe | product, rows | Title marked "asked"; a new evening run gives new rows without a rebuild | Implemented |
| SRD-MKT-011.008 | FO-MKT-011 | Must | A default expert-level data employee ships as `emp-009` (generic name "Expert 7") with trigger `data_request`, and the skill is added to the skill list. | — | files, skill path | Calls per day 20; monthly cap USD 3; `market` never imports `desk` | Implemented |
| SRD-MKT-011.009 | FO-MKT-011 | Should | Each request logs whether a product was proposed or failed, with the request number. | answer | log line | `[Data]` prefix | Implemented |

## FO-MKT-012: Learning from Pick Results

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-012.001 | FO-MKT-012 | Must | Code builds count, win rate and average R of closed paper picks by side, setup, regime, sector, grade and news tone. | `pick_results`, ideas, reviews | stats table | Closed means stop, target or time | Implemented |
| SRD-MKT-012.002 | FO-MKT-012 | Must | The reflect skill (`lesson_reflect`) asks for at most 3 candidate lessons from the stats, today's closed picks and the active lessons. | stats, picks, lessons | candidates | Fresh only on a data day with new closed picks | Implemented |
| SRD-MKT-012.003 | FO-MKT-012 | Must | The reflect answer is a typed form: text of at most 200 characters, tags from a fixed list, claim better or worse, and 1 to 20 pick keys. | answer | candidates | Checked by the gateway; unknown pick keys are dropped | Implemented |
| SRD-MKT-012.004 | FO-MKT-012 | Must | A default expert-level employee ships as `emp-010` (generic name "Expert 8") with trigger `after_run` and skill `lesson_reflect`. | default files | employee | Copied only when missing; the Master may rename it | Implemented |
| SRD-MKT-012.005 | FO-MKT-012 | Must | Setup review, news review, risk check and lead brief facts end with the lessons block from SRD-DSK-009.004. | lessons | facts text | Regime view and sector view get none | Implemented |
| SRD-MKT-012.006 | FO-MKT-012 | Should | Each reflect run logs how many candidates were kept and dropped. | answer | log line | `[Memory]` prefix | Implemented |

## FO-MKT-013: Intraday Watchers and Check-in Notes

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-013.001 | FO-MKT-013 | Must | Watchers read the latest 3-minute bars of plan stocks, open-trade stocks and SPY from `price_3m` in `candles.db`. | `candles.db` | bars | Read-only; a stock whose newest bar is over 15 minutes old gives no flag | Implemented |
| SRD-MKT-013.002 | FO-MKT-013 | Must | The trigger watcher flags a listed idea of the day whose bar high (long) or low (short) reaches its trigger. | ideas, bars | flag `trigger_hit` | Once per idea a day | Implemented |
| SRD-MKT-013.003 | FO-MKT-013 | Must | The stop and target watcher flags an open trade whose bar low or high reaches its stop or target. | `open_trades`, bars | flag `stop_touch`, `target_touch` | Covers every open trade the app lists; short trades use the other side | Implemented |
| SRD-MKT-013.004 | FO-MKT-013 | Must | The volume watcher flags a plan stock whose last bar volume is at least 3 times the average of its previous 20 bars. | bars | flag `volume_spike` | Needs 20 earlier bars | Implemented |
| SRD-MKT-013.005 | FO-MKT-013 | Must | The gap watcher flags a plan stock whose first bar of the day opens more than 3% away from the previous close. | bars, daily close | flag `gap` | Once a day | Implemented |
| SRD-MKT-013.006 | FO-MKT-013 | Must | The regime watcher flags when SPY is more than 1.5% up or down from the previous close. | SPY bars | flag `regime_move` | Once per direction a day; VIX is not watched in step D | Implemented |
| SRD-MKT-013.007 | FO-MKT-013 | Should | The news watcher reads headlines of lead picks and open-trade stocks every 15 minutes and flags one not seen before. | RSS | flag `headline` | Headlines older than the day's open are left out | Implemented |
| SRD-MKT-013.008 | FO-MKT-013 | Must | The flag skill (`watch_flag`) asks whether the plan for the oldest unanswered flag still holds. | flag, plan, bars | verdict | Facts hold the flag, the idea or trade plan and the last 12 bars | Implemented |
| SRD-MKT-013.009 | FO-MKT-013 | Must | The flag answer is a typed form: verdict holds, watch or broken, and a note of at most 300 characters; it is kept and shown as a feed note. | answer | row, brief | A broken verdict raises the alert of SRD-DSK-007.009 | Implemented |
| SRD-MKT-013.010 | FO-MKT-013 | Must | The check-in skill (`checkin_note`) writes a note of at most 600 characters on plan stocks against trigger, open trades against stop and target, SPY and the flags since the last check-in. | bars, trades, flags | brief | One note per check-in time | Implemented |
| SRD-MKT-013.011 | FO-MKT-013 | Must | Default employees ship as `emp-011` ("Expert 9", skill `watch_flag`, trigger `watch_flag`) and `emp-012` ("Lead 3", skill `checkin_note`, trigger `market_checkin`). | default files | employees | Copied only when missing; generic names | Implemented |
| SRD-MKT-013.012 | FO-MKT-013 | Should | Each flag answer logs the stock, flag kind and verdict. | answer | log line | `[Watch]` prefix | Implemented |

## FO-MKT-014: Lead Research Tickets

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-014.001 | FO-MKT-014 | Must | The lead plan (`lead_brief`) and check-in (`checkin_note`) answers may hold up to 3 tickets, each with kind, topic, goal, done test and token cap. | answer | tickets | Typed form; an empty list is valid | Implemented |
| SRD-MKT-014.002 | FO-MKT-014 | Must | Ticket kinds come from a fixed list: setup tuning, pick post-mortem, stock study, sentiment, book to strategy and strategy test. | kind | checked kind | An unknown kind makes the ticket invalid, not the answer | Implemented |
| SRD-MKT-014.003 | FO-MKT-014 | Must | A ticket's token cap is between 1,000 and 100,000 tokens. | cap | checked cap | — | Implemented |
| SRD-MKT-014.004 | FO-MKT-014 | Must | The lead's prompt shows its research tokens left today, its open tickets and its results from the last 30 days. | `tickets`, `activity` | prompt text | At most 600 tokens | Implemented |
| SRD-MKT-014.005 | FO-MKT-014 | Must | Valid tickets of a kept answer are handed to the research queue. | tickets | `tickets` rows | Queue rules of FO-DSK-010 decide approve, wait or refuse | Implemented |

## FO-MKT-015: Setup Tuning Research

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-MKT-015.001 | FO-MKT-015 | Must | The setup tuning skill (`setup_tuning`) works `setup_tuning` tickets, whose target is one desk setup or one live strategy. | ticket | target | Unknown target ends the ticket `failed` | Implemented |
| SRD-MKT-015.002 | FO-MKT-015 | Must | Each desk setup exposes its fixed limits as named knobs, each with today's value as default and a fixed allowed range. | `setups` | knobs | Live picks unchanged at default values | Implemented |
| SRD-MKT-015.003 | FO-MKT-015 | Must | The first step makes one AI call that picks up to 3 variants, each changing at most 2 knobs or numeric strategy values. | ticket, knobs | variants | Values outside the range are dropped; no valid variant ends `failed` | Implemented |
| SRD-MKT-015.004 | FO-MKT-015 | Must | Code replays the baseline and each desk-setup variant on the last 5 years of daily bars for S&P 500 members. | `candles.db` | trades | No tokens; entry at trigger, setup stop, 2R target, 10-day exit | Implemented |
| SRD-MKT-015.005 | FO-MKT-015 | Must | Code runs the baseline and each strategy variant on the backtest engine as renamed copies fed by its strategy loader. | backtest store | trades | Up to 5 years held; not saved as Backtest runs; no fixed stop ends `failed` | Implemented |
| SRD-MKT-015.006 | FO-MKT-015 | Must | Code builds a result table of trades, win rate, expectancy in R and change against the baseline per variant. | trades | table | Kept in the ticket state | Implemented |
| SRD-MKT-015.007 | FO-MKT-015 | Must | Code marks a gain when a variant's expectancy beats the baseline by at least 0.05R on at least 100 trades. | table | gain | AI never sets the gain | Implemented |
| SRD-MKT-015.008 | FO-MKT-015 | Must | The last step makes one AI call that reads the table and writes a verdict of at most 600 characters, then ends `done`. | table | result | — | Implemented |
| SRD-MKT-015.009 | FO-MKT-015 | Must | A desk-setup gain writes one candidate lesson tagged with the setup and side, claim worse, with the backtest numbers as proof. | gain | lesson | Goes active only by FO-MKT-012 case rules; strategy gains write none | Implemented |
| SRD-MKT-015.010 | FO-MKT-015 | Must | The skill never changes a live setup, a strategy or the strategy list; the result only names the winning values. | — | — | Master user applies changes by hand | Implemented |
| SRD-MKT-015.011 | FO-MKT-015 | Must | Default employee ships as `emp-013` ("Researcher 1", skill `setup_tuning`) and its skill path is in `SKILL_PATHS` and the app build. | default files | employee | Copied only when missing; generic name | Implemented |
| SRD-MKT-015.012 | FO-MKT-015 | Should | Each step logs the target, the variant count and the gain. | step | log line | `[Research]` prefix | Implemented |
