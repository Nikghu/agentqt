# Unit Test Cases — Market Analytics (MKT)

**Document ID:** UTCD-MKT
**Version:** 0.5.0
**Status:** Draft
**Last Updated:** 2026-11-06
**Project:** US Swing Trading System

> v0.8.0: 35 test cases for FO-MKT-006 news, economic calendar and event risk (P5c).
> v0.7.0: 35 test cases for the P5b skills (sector/flow view, setup review, risk limits, risk check, lead brief, defaults).
> v0.6.0: 13 test cases for the FO-MKT-005 regime view skill (P5a).
> v0.5.0: 23 test cases for FO-MKT-004 (P4).
> v0.4.0: 35 test cases for FO-MKT-003 (P3).
> v0.3.0: 22 test cases for FO-MKT-002 (P2).
> v0.2.0: 28 test cases for FO-MKT-001 (P1).
> v0.1.0: Empty. Rows are added per phase, starting with the first FO of this tool.

---

## FO-MKT-001: Market Regime, Breadth and Fear

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-001.001.M01.T01 | MD-MKT-001.001.M01 | Positive | Reads bars read-only (SRD-MKT-001.001) | temp candles.db with SPY and 3 members | frames per symbol; file unchanged | Pass |
| UT-MKT-001.001.M01.T02 | MD-MKT-001.001.M01 | Negative | Missing candles file (SRD-MKT-001.001) | no file | raises FileNotFoundError; no file created | Pass |
| UT-MKT-001.002.M02.T01 | MD-MKT-001.002.M02 | Positive | Uptrend (SRD-MKT-001.002) | rising SPY series, 260 days | last day Uptrend | Pass |
| UT-MKT-001.002.M02.T02 | MD-MKT-001.002.M02 | Positive | Downtrend (SRD-MKT-001.002) | falling series | last day Downtrend | Pass |
| UT-MKT-001.002.M02.T03 | MD-MKT-001.002.M02 | Negative | Choppy and too short (SRD-MKT-001.002) | flat zig-zag; 150 days | Choppy; no value before 210 bars | Pass |
| UT-MKT-001.003.M02.T01 | MD-MKT-001.002.M02 | Positive | High volatility (SRD-MKT-001.003) | calm year then 20 wild days | High, percentile above 70 | Pass |
| UT-MKT-001.003.M02.T02 | MD-MKT-001.002.M02 | Negative | Calm volatility (SRD-MKT-001.003) | wild year then 20 quiet days | Calm | Pass |
| UT-MKT-001.004.M02.T01 | MD-MKT-001.002.M02 | Positive | Breadth counts (SRD-MKT-001.004) | 4 members, hand-made closes | pct above 20/50/200, highs, lows, advancers, decliners as computed by hand | Pass |
| UT-MKT-001.004.M02.T02 | MD-MKT-001.002.M02 | Negative | Short history member (SRD-MKT-001.004) | member with 30 bars | counted for 20-day, not for 50/200 | Pass |
| UT-MKT-001.004.M02.T03 | MD-MKT-001.002.M02 | Negative | Stray date row ignored (SRD-MKT-001.004) | one member with a non-trading-day row | breadth complete on later days | Pass |
| UT-MKT-001.005.M03.T01 | MD-MKT-001.005.M03 | Positive | VIX rows from download (SRD-MKT-001.005) | fake downloader frame | rows by date with vix and vix3m | Pass |
| UT-MKT-001.005.M03.T02 | MD-MKT-001.005.M03 | Negative | Download fails (SRD-MKT-001.005) | downloader raises | empty result; warning logged | Pass |
| UT-MKT-001.006.M02.T01 | MD-MKT-001.002.M02 | Positive | Fear points (SRD-MKT-001.006) | VIX 32 above VIX3M, High, pct50 35 | score 6, Fearful | Pass |
| UT-MKT-001.006.M02.T02 | MD-MKT-001.002.M02 | Negative | No VIX (SRD-MKT-001.006) | VIX missing, Normal, pct50 60 | score 0, Calm, note no VIX | Pass |
| UT-MKT-001.007.M04.T01 | MD-MKT-001.007.M04 | Positive | Rows round trip (SRD-MKT-001.007) | write two days, read back | same values; re-write replaces | Pass |
| UT-MKT-001.007.M04.T02 | MD-MKT-001.007.M04 | Edge | Tables beside desk tables (SRD-MKT-001.007) | existing desk.db | desk tables untouched | Pass |
| UT-MKT-001.007.M04.T03 | MD-MKT-001.007.M04 | Negative | Row without a date refused (SRD-MKT-001.007) | regime row with empty date | raises ValueError; nothing written | Pass |
| UT-MKT-001.008.M05.T01 | MD-MKT-001.011.M05 | Positive | First run fills history (SRD-MKT-001.008) | 260 days of bars | rows from day 210 to last | Pass |
| UT-MKT-001.008.M05.T02 | MD-MKT-001.011.M05 | Positive | Later run adds only new days (SRD-MKT-001.008) | second run with one new day | one row added | Pass |
| UT-MKT-001.008.M05.T03 | MD-MKT-001.011.M05 | Negative | No new candles (SRD-MKT-001.008) | second run, same bars | no rows added | Pass |
| UT-MKT-001.008.M05.T04 | MD-MKT-001.011.M05 | Positive | Partial day redone next run (SRD-MKT-001.008) | last day missing one stock, then complete | members 9, then 10 | Pass |
| UT-MKT-001.009.M05.T01 | MD-MKT-001.011.M05 | Negative | Low coverage day skipped (SRD-MKT-001.009) | day with 70% of members | no row; logged | Pass |
| UT-MKT-001.009.M05.T02 | MD-MKT-001.011.M05 | Positive | Full coverage day stored (SRD-MKT-001.009) | day with all members | row stored with members count | Pass |
| UT-MKT-001.010.M05.T01 | MD-MKT-001.011.M05 | Negative | Stale candles noted (SRD-MKT-001.010) | last SPY day a week old | note says stale | Pass |
| UT-MKT-001.010.M05.T02 | MD-MKT-001.011.M05 | Positive | Fresh candles not flagged (SRD-MKT-001.010) | last SPY day is the last weekday | note has no stale text | Pass |
| UT-MKT-001.011.M05.T01 | MD-MKT-001.011.M05 | Positive | Step runs in a desk run (SRD-MKT-001.011) | DeskProcess with loaded steps, run-now | run ok; rows written | Pass |
| UT-MKT-001.011.M05.T02 | MD-MKT-001.011.M05 | Negative | VIX down, step still ok (SRD-MKT-001.011) | fake VIX fetch fails | rows written; note no VIX | Pass |
| UT-MKT-001.011.M05.T03 | MD-MKT-001.011.M05 | Negative | No candle file yet (SRD-MKT-001.011) | missing candles.db | no rows; run not failed | Pass |

## FO-MKT-002: Sector Strength and Rotation

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-002.001.M01.T01 | MD-MKT-002.001.M01 | Positive | Sector map from list (SRD-MKT-002.001) | list with 3 stocks in 2 sectors | symbol to sector map; ibkr form matched | Pass |
| UT-MKT-002.001.M01.T02 | MD-MKT-002.001.M01 | Negative | Stock without a sector (SRD-MKT-002.001) | list row with empty sector | left out; logged | Pass |
| UT-MKT-002.002.M02.T01 | MD-MKT-002.002.M02 | Positive | Equal-weight line (SRD-MKT-002.002) | 2 members: +10% and 0% on day 2 | line 100 then 105 | Pass |
| UT-MKT-002.002.M02.T02 | MD-MKT-002.002.M02 | Negative | Missing bar left out (SRD-MKT-002.002) | member with no bar on day 2 | average of the others only | Pass |
| UT-MKT-002.003.M02.T01 | MD-MKT-002.002.M02 | Positive | Rank by relative moves (SRD-MKT-002.003) | 3 sectors rising at different speeds, flat SPY | fastest rank 1 | Pass |
| UT-MKT-002.003.M02.T02 | MD-MKT-002.002.M02 | Negative | Too short for 6 months (SRD-MKT-002.003) | 100 days | no rank | Pass |
| UT-MKT-002.004.M02.T01 | MD-MKT-002.002.M02 | Positive | Ratio and momentum (SRD-MKT-002.004) | sector outrunning SPY | ratio above 100, momentum above 100 | Pass |
| UT-MKT-002.004.M02.T02 | MD-MKT-002.002.M02 | Negative | Same as SPY (SRD-MKT-002.004) | line equal to SPY | ratio 100, momentum 100 | Pass |
| UT-MKT-002.005.M02.T01 | MD-MKT-002.002.M02 | Positive | Four quadrants (SRD-MKT-002.005) | 4 ratio and momentum pairs | Leading, Weakening, Lagging, Improving | Pass |
| UT-MKT-002.005.M02.T02 | MD-MKT-002.002.M02 | Edge | Exactly 100 (SRD-MKT-002.005) | ratio 100, momentum 100 | Leading | Pass |
| UT-MKT-002.005.M02.T03 | MD-MKT-002.002.M02 | Negative | Missing value (SRD-MKT-002.005) | ratio NaN | no quadrant | Pass |
| UT-MKT-002.006.M03.T01 | MD-MKT-002.006.M03 | Positive | Score and rating (SRD-MKT-002.006) | 5 stocks with known moves | score by formula; best 99, worst near 20 | Pass |
| UT-MKT-002.006.M03.T02 | MD-MKT-002.006.M03 | Negative | Short history (SRD-MKT-002.006) | stock with 200 bars | no score, no rating | Pass |
| UT-MKT-002.007.M03.T01 | MD-MKT-002.006.M03 | Positive | Rank inside sector (SRD-MKT-002.007) | 3 stocks in one sector | ranks 1, 2, 3; size 3 | Pass |
| UT-MKT-002.007.M03.T02 | MD-MKT-002.006.M03 | Negative | Unrated stock (SRD-MKT-002.007) | stock without score | no sector rank | Pass |
| UT-MKT-002.008.M04.T01 | MD-MKT-002.008.M04 | Positive | Rows round trip (SRD-MKT-002.008) | 2 days of sector and stock rows | same rows read back; re-write replaces | Pass |
| UT-MKT-002.008.M04.T02 | MD-MKT-002.008.M04 | Negative | Row without a date (SRD-MKT-002.008) | sector row with empty date | raises ValueError; nothing written | Pass |
| UT-MKT-002.009.M05.T01 | MD-MKT-002.009.M05 | Positive | First run fills history (SRD-MKT-002.009) | 300 days, 3 sectors | rows from the first ready day | Pass |
| UT-MKT-002.009.M05.T02 | MD-MKT-002.009.M05 | Positive | Later run adds new day (SRD-MKT-002.009) | one more bar | one new day of rows | Pass |
| UT-MKT-002.009.M05.T03 | MD-MKT-002.009.M05 | Negative | Low coverage day skipped (SRD-MKT-002.009) | last day missing 30% of members | no rows for that day | Pass |
| UT-MKT-002.009.M05.T04 | MD-MKT-002.009.M05 | Negative | No candle file (SRD-MKT-002.009) | missing candles.db | no rows; run not failed | Pass |
| UT-MKT-002.009.M05.T05 | MD-MKT-002.009.M05 | Positive | Runs after regime in a desk run (SRD-MKT-002.009) | loaded step list, run-now | both steps ok; sector rows written | Pass |

## FO-MKT-003: Money Flow, Setups, Readiness Score and Ideas

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-003.001.M01.T01 | MD-MKT-003.001.M01 | Positive | Volume read (SRD-MKT-003.001) | candles with volume | volumes frame by date and symbol | Pass |
| UT-MKT-003.001.M02.T01 | MD-MKT-003.002.M02 | Positive | Liquid stock scored (SRD-MKT-003.001) | close 100, volume 300k | dollar volume 30M; kept | Pass |
| UT-MKT-003.001.M02.T02 | MD-MKT-003.002.M02 | Negative | Thin stock left out (SRD-MKT-003.001) | close 10, volume 1M | dollar volume 10M; not scored | Pass |
| UT-MKT-003.002.M02.T01 | MD-MKT-003.002.M02 | Positive | Strong buying (SRD-MKT-003.002) | up days on high volume, closes near highs | flow long near 1; short near 0 | Pass |
| UT-MKT-003.002.M02.T02 | MD-MKT-003.002.M02 | Negative | Heavy selling (SRD-MKT-003.002) | down days on high volume, closes near lows | flow long near 0 | Pass |
| UT-MKT-003.002.M02.T03 | MD-MKT-003.002.M02 | Edge | Flat bar (SRD-MKT-003.002) | high equals low | money flow term 0; no error | Pass |
| UT-MKT-003.003.M03.T01 | MD-MKT-003.003.M03 | Positive | Squeeze found (SRD-MKT-003.003) | uptrend, then narrow range | Squeeze; trigger 20-day high; stop 20-day low | Pass |
| UT-MKT-003.003.M03.T02 | MD-MKT-003.003.M03 | Positive | Flat base found (SRD-MKT-003.003) | near 52-week high, 25-day range 10% | Flat base; trigger 25-day high | Pass |
| UT-MKT-003.003.M03.T03 | MD-MKT-003.003.M03 | Positive | Pullback found (SRD-MKT-003.003) | uptrend, low touches 21-day average | Pullback; trigger 3-day high; stop 5-day low | Pass |
| UT-MKT-003.003.M03.T04 | MD-MKT-003.003.M03 | Negative | No long setup (SRD-MKT-003.003) | downtrend | no setup; tightness 0 | Pass |
| UT-MKT-003.004.M03.T01 | MD-MKT-003.003.M03 | Positive | Failed breakout found (SRD-MKT-003.004) | close above pivot, then back below | Failed breakout; stop at breakout high | Pass |
| UT-MKT-003.004.M03.T02 | MD-MKT-003.003.M03 | Positive | Lower highs found (SRD-MKT-003.004) | three falling 10-day highs under falling 50-day | Lower highs; trigger 10-day low | Pass |
| UT-MKT-003.004.M03.T03 | MD-MKT-003.003.M03 | Positive | Breakdown found (SRD-MKT-003.004) | close crosses under 50-day on 2x volume | Breakdown; trigger today's low | Pass |
| UT-MKT-003.004.M03.T04 | MD-MKT-003.003.M03 | Negative | No short setup (SRD-MKT-003.004) | steady uptrend | no setup | Pass |
| UT-MKT-003.005.M04.T01 | MD-MKT-003.005.M04 | Positive | Score from parts (SRD-MKT-003.005) | all parts 1 | score 100 | Pass |
| UT-MKT-003.005.M04.T02 | MD-MKT-003.005.M04 | Positive | Weights and scale (SRD-MKT-003.005) | known parts | score = (20rs+20flow+20setup+15sector+15regime)*100/90 | Pass |
| UT-MKT-003.005.M04.T03 | MD-MKT-003.005.M04 | Negative | Missing RS rating (SRD-MKT-003.005) | stock without rating that day | no score | Pass |
| UT-MKT-003.006.M04.T01 | MD-MKT-003.005.M04 | Positive | Extended long (SRD-MKT-003.006) | close 10% above 20-day average | 10 points off; reason added | Pass |
| UT-MKT-003.006.M04.T02 | MD-MKT-003.005.M04 | Edge | Score floor (SRD-MKT-003.006) | raw 5, penalty 10 | score 0 | Pass |
| UT-MKT-003.006.M04.T03 | MD-MKT-003.005.M04 | Negative | Not extended (SRD-MKT-003.006) | close 5% above 20-day average | no penalty; no extended reason | Pass |
| UT-MKT-003.007.M04.T01 | MD-MKT-003.005.M04 | Positive | Top 10 per side (SRD-MKT-003.007) | 15 stocks scoring 60+ | 10 listed, ranks 1–10 | Pass |
| UT-MKT-003.007.M04.T02 | MD-MKT-003.005.M04 | Negative | Below 60 left out (SRD-MKT-003.007) | best score 55 | no ideas | Pass |
| UT-MKT-003.007.M04.T03 | MD-MKT-003.005.M04 | Positive | Earnings to Watch (SRD-MKT-003.007) | earnings in 3 trading days | status watch; reason Earnings in 3 days | Pass |
| UT-MKT-003.007.M04.T04 | MD-MKT-003.005.M04 | Positive | Short against Uptrend (SRD-MKT-003.007) | regime Uptrend, short 70 | status watch | Pass |
| UT-MKT-003.008.M04.T01 | MD-MKT-003.005.M04 | Positive | Reasons in plain words (SRD-MKT-003.008) | listed idea | 1–5 reasons; no codes or underscores | Pass |
| UT-MKT-003.008.M04.T02 | MD-MKT-003.005.M04 | Negative | No false reasons (SRD-MKT-003.008) | listed idea, no earnings, with the regime | no Watch or earnings reason | Pass |
| UT-MKT-003.009.M05.T01 | MD-MKT-003.009.M05 | Positive | Earnings dates read (SRD-MKT-003.009) | fake Yahoo calendar | date per symbol | Pass |
| UT-MKT-003.009.M05.T02 | MD-MKT-003.009.M05 | Negative | Yahoo down (SRD-MKT-003.009) | fetch raises | None per symbol; no error | Pass |
| UT-MKT-003.010.M06.T01 | MD-MKT-003.010.M06 | Positive | Rows round trip (SRD-MKT-003.010) | 2 days of score, idea and reason rows | same rows back; re-write replaces the day | Pass |
| UT-MKT-003.010.M06.T02 | MD-MKT-003.010.M06 | Negative | Row without a date (SRD-MKT-003.010) | idea row with empty date | raises ValueError; nothing written | Pass |
| UT-MKT-003.011.M07.T01 | MD-MKT-003.011.M07 | Positive | First run fills history (SRD-MKT-003.011) | 300 days, regime and sector rows present | score and idea rows from the first ready day | Pass |
| UT-MKT-003.011.M07.T02 | MD-MKT-003.011.M07 | Positive | Later run adds a new day (SRD-MKT-003.011) | one more bar | one new day of rows; earnings checked for it | Pass |
| UT-MKT-003.011.M07.T03 | MD-MKT-003.011.M07 | Negative | No sector rows yet (SRD-MKT-003.011) | desk.db without sector_daily rows | no rows; run not failed | Pass |
| UT-MKT-003.011.M07.T04 | MD-MKT-003.011.M07 | Negative | No candle file (SRD-MKT-003.011) | missing candles.db | no rows; run not failed | Pass |
| UT-MKT-003.011.M07.T05 | MD-MKT-003.011.M07 | Positive | Runs third in a desk run (SRD-MKT-003.011) | loaded step list, run-now | regime, sectors and ideas ok; idea rows written | Pass |

## FO-MKT-004: Proof on Past Data

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-004.001.M01.T01 | MD-MKT-004.001.M01 | Positive | Daily files read (SRD-MKT-004.001) | SPY + 3 stock files | closes, highs, lows, opens, volumes by SPY's days | Pass |
| UT-MKT-004.001.M01.T02 | MD-MKT-004.001.M01 | Negative | No Backtest Data folder (SRD-MKT-004.001) | missing folder | None; warning logged | Pass |
| UT-MKT-004.001.M01.T03 | MD-MKT-004.001.M01 | Edge | Stock missing a day (SRD-MKT-004.001) | one stock without one SPY day | that cell NaN; other days kept | Pass |
| UT-MKT-004.001.M02.T01 | MD-MKT-004.002.M02 | Negative | Run without data (SRD-MKT-004.001) | no daily files | None; nothing written | Pass |
| UT-MKT-004.002.M02.T01 | MD-MKT-004.002.M02 | Positive | Replay matches desk step (SRD-MKT-004.002) | same synthetic candles in candles.db and daily files | replayed scores, setups and statuses equal the IdeaStep rows | Pass |
| UT-MKT-004.002.M02.T02 | MD-MKT-004.002.M02 | Positive | No look-ahead (SRD-MKT-004.002) | change all bars after day d | scores up to day d unchanged | Pass |
| UT-MKT-004.002.M02.T03 | MD-MKT-004.002.M02 | Positive | No earnings Watch (SRD-MKT-004.002) | replay of a short in an Uptrend | status watch from regime only; no earnings note | Pass |
| UT-MKT-004.002.M02.T04 | MD-MKT-004.002.M02 | Negative | Thin day not scored (SRD-MKT-004.002) | one day with data for under 80% of members | no scores for that day | Pass |
| UT-MKT-004.003.M02.T01 | MD-MKT-004.002.M02 | Positive | Long forward return (SRD-MKT-004.003) | next open 100, close at t+5 110, SPY +5% | ret 10%; vs SPY 5% | Pass |
| UT-MKT-004.003.M02.T02 | MD-MKT-004.002.M02 | Positive | Short forward return (SRD-MKT-004.003) | same bars, short side | ret -10%; vs SPY -5% | Pass |
| UT-MKT-004.003.M02.T03 | MD-MKT-004.002.M02 | Edge | End of data (SRD-MKT-004.003) | day 10 sessions before the last | 5 and 10-day samples; no 20-day sample | Pass |
| UT-MKT-004.003.M02.T04 | MD-MKT-004.002.M02 | Negative | Missing exit bar (SRD-MKT-004.003) | close at t+10 missing | no 10-day sample for that stock-day | Pass |
| UT-MKT-004.004.M02.T01 | MD-MKT-004.002.M02 | Positive | Band edges (SRD-MKT-004.004) | scores 39.9, 40, 70, 80, 100 | under 40, 40–50, 70–80, 80+, 80+ | Pass |
| UT-MKT-004.004.M02.T02 | MD-MKT-004.002.M02 | Positive | Setup and status groups (SRD-MKT-004.004) | rows with setups, No setup, list, watch, none | one group each; counts, days, win rate and averages right | Pass |
| UT-MKT-004.004.M02.T03 | MD-MKT-004.002.M02 | Negative | Empty group left out (SRD-MKT-004.004) | no stock-day in the 80+ band | no 80+ row; other bands kept | Pass |
| UT-MKT-004.005.M02.T01 | MD-MKT-004.002.M02 | Positive | Side passes (SRD-MKT-004.005) | 70+ vs SPY +2%, under 40 -1%, 150 each | pass | Pass |
| UT-MKT-004.005.M02.T02 | MD-MKT-004.002.M02 | Negative | Side fails (SRD-MKT-004.005) | 70+ vs SPY -0.5%, under 40 -1% | fail | Pass |
| UT-MKT-004.005.M02.T03 | MD-MKT-004.002.M02 | Edge | Too few samples (SRD-MKT-004.005) | 70+ has 99 stock-days | not enough data | Pass |
| UT-MKT-004.006.M02.T01 | MD-MKT-004.002.M02 | Positive | Run stores and reports (SRD-MKT-004.006) | two runs on synthetic files | two proof_run rows; stats for both sides, 3 kinds, 3 horizons; report text returned | Pass |
| UT-MKT-004.007.M02.T01 | MD-MKT-004.002.M02 | Positive | Short history reminder (SRD-MKT-004.007) | 3.2 years of SPY bars | report ends with the Settings → Backtest Data reminder | Pass |
| UT-MKT-004.007.M02.T02 | MD-MKT-004.002.M02 | Negative | Long history, no reminder (SRD-MKT-004.007) | 6 years of SPY bars | no reminder line | Pass |
| UT-MKT-004.006.M03.T01 | MD-MKT-004.006.M03 | Positive | Proof round trip (SRD-MKT-004.006) | write run + stats; read latest | same values; latest run id | Pass |
| UT-MKT-004.006.M03.T02 | MD-MKT-004.006.M03 | Negative | No runs yet (SRD-MKT-004.006) | empty desk.db | latest_proof is None | Pass |

## FO-MKT-005: AI Experts, Risk Manager and Trade Manager

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-005.001.M01.T01 | MD-MKT-005.001.M01 | Positive | Facts built (SRD-MKT-005.001) | desk.db with regime, breadth, sectors, ideas, proof | text holds each part; fresh True | Pass |
| UT-MKT-005.001.M01.T02 | MD-MKT-005.001.M01 | Negative | Stale data (SRD-MKT-005.001) | regime day older than SPY day | fresh False; both days named | Pass |
| UT-MKT-005.001.M01.T03 | MD-MKT-005.001.M01 | Negative | No regime rows (SRD-MKT-005.001) | empty desk.db | fresh False | Pass |
| UT-MKT-005.002.M01.T01 | MD-MKT-005.001.M01 | Negative | Answer schema (SRD-MKT-005.002) | regime Sideways; confidence 1.4; 4 reasons; long brief | each refused by the schema | Pass |
| UT-MKT-005.002.M01.T02 | MD-MKT-005.001.M01 | Positive | Valid view accepted (SRD-MKT-005.002) | Choppy, 0.6, 2 reasons, 200-char brief | RegimeView | Pass |
| UT-MKT-005.004.M01.T01 | MD-MKT-005.001.M01 | Positive | Agreeing view (SRD-MKT-005.004) | answer Choppy, rules Choppy | brief only; regime_view agrees 1 | Pass |
| UT-MKT-005.004.M01.T02 | MD-MKT-005.001.M01 | Positive | Disagreeing view (SRD-MKT-005.004) | answer Downtrend, rules Choppy | brief ends with the plain note; agrees 0 | Pass |
| UT-MKT-005.004.M01.T03 | MD-MKT-005.001.M01 | Negative | No valid answer (SRD-MKT-005.004) | ask returns None | no feed item; no regime_view row | Pass |
| UT-MKT-005.003.M02.T01 | MD-MKT-005.003.M02 | Positive | View stored and replaced (SRD-MKT-005.003) | write twice for one day | one row with the second view | Pass |
| UT-MKT-005.003.M01.T01 | MD-MKT-005.001.M01 | Negative | No view, no row (SRD-MKT-005.003) | ask returns None | regime_view empty | Pass |
| UT-MKT-005.005.M03.T01 | MD-MKT-005.005.M03 | Positive | Default employee files valid (SRD-MKT-005.005) | shipped default for regime_view | loads; skill regime_view; trigger after_run; caps 3 and USD 3; name filled into the soul | Pass |
| UT-MKT-005.005.M03.T02 | MD-MKT-005.005.M03 | Positive | Full run in a desk run (SRD-MKT-005.005) | real steps on synthetic candles, fake model | activity, regime_view and brief carry the made-up id and name | Pass |
| UT-MKT-005.005.M03.T03 | MD-MKT-005.005.M03 | Negative | Broken default copy (SRD-MKT-005.005) | job.yaml copy without trigger | stays asleep; warning | Pass |

### P5b — sector/flow view, setup review, risk check, lead brief

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-005.006.M04.T01 | MD-MKT-005.006.M04 | Positive | Sector facts (SRD-MKT-005.006) | desk.db with 5 sector days, scores, regime | text has ranks, quadrants, moves, flow per side; fresh True | Pass |
| UT-MKT-005.006.M04.T02 | MD-MKT-005.006.M04 | Negative | Stale sectors (SRD-MKT-005.006) | sector day older than SPY day | fresh False; both days named | Pass |
| UT-MKT-005.007.M04.T01 | MD-MKT-005.006.M04 | Positive | Valid sector view (SRD-MKT-005.007) | 2 favour, 1 avoid from the day's sectors | SectorView | Pass |
| UT-MKT-005.007.M04.T02 | MD-MKT-005.006.M04 | Negative | Bad sector view (SRD-MKT-005.007) | unknown sector; 4 favour; same sector in both; long brief | each refused by the schema | Pass |
| UT-MKT-005.008.M04.T01 | MD-MKT-005.006.M04 | Positive | Stored and in feed (SRD-MKT-005.008) | valid answer, run twice | one sector_view row with the second view; info feed item | Pass |
| UT-MKT-005.008.M04.T02 | MD-MKT-005.006.M04 | Negative | No answer (SRD-MKT-005.008) | ask returns None | no row; no feed item | Pass |
| UT-MKT-005.008.M04.T03 | MD-MKT-005.006.M04 | Edge | No sectors for the day (SRD-MKT-005.008) | sector rows missing for the data day | no question asked; no feed item | Pass |
| UT-MKT-005.009.M05.T01 | MD-MKT-005.009.M05 | Positive | Setup facts (SRD-MKT-005.009) | 12 long and 3 short listed ideas plus Watch names | 10 long and 3 short in text with parts and reasons; no Watch names | Pass |
| UT-MKT-005.009.M05.T02 | MD-MKT-005.009.M05 | Negative | No listed ideas (SRD-MKT-005.009) | only Watch rows | fresh False; reason says no ideas | Pass |
| UT-MKT-005.010.M05.T01 | MD-MKT-005.009.M05 | Positive | Grades stored (SRD-MKT-005.010) | A, B, C for 3 ideas | 3 setup_review rows | Pass |
| UT-MKT-005.010.M05.T02 | MD-MKT-005.009.M05 | Negative | Unknown or repeated idea (SRD-MKT-005.010) | grade for a stock not in facts; two grades for one | both dropped; one log line | Pass |
| UT-MKT-005.010.M05.T03 | MD-MKT-005.009.M05 | Negative | Bad grade (SRD-MKT-005.010) | grade D; 130-char note | refused by the schema | Pass |
| UT-MKT-005.011.M06.T01 | MD-MKT-005.011.M06 | Positive | Within limits (SRD-MKT-005.011) | long, Uptrend, trigger 50, stop 47 | no veto | Pass |
| UT-MKT-005.011.M06.T02 | MD-MKT-005.011.M06 | Negative | Against the regime (SRD-MKT-005.011) | long in Downtrend; short in Uptrend | both vetoed with the plain reason | Pass |
| UT-MKT-005.011.M06.T03 | MD-MKT-005.011.M06 | Negative | Stop distance (SRD-MKT-005.011) | stop 0.5% and 12% from trigger | both vetoed | Pass |
| UT-MKT-005.011.M06.T04 | MD-MKT-005.011.M06 | Edge | Limits exact (SRD-MKT-005.011) | stop exactly 1% and 10%; trigger exactly $5 | no veto | Pass |
| UT-MKT-005.011.M06.T05 | MD-MKT-005.011.M06 | Negative | Low trigger and missing stop (SRD-MKT-005.011) | trigger 4.9; stop missing | both vetoed | Pass |
| UT-MKT-005.011.M06.T06 | MD-MKT-005.011.M06 | Negative | Sector cap (SRD-MKT-005.011) | 5 long Technology ideas, rank 2 breaks the stop rule | ranks 1, 3, 4 pass; 2 and 5 vetoed | Pass |
| UT-MKT-005.012.M07.T01 | MD-MKT-005.012.M07 | Positive | AI adds a veto (SRD-MKT-005.012) | AI vetoes one passed idea | that row veto by ai with the reason | Pass |
| UT-MKT-005.012.M07.T02 | MD-MKT-005.012.M07 | Negative | AI cannot undo a code veto (SRD-MKT-005.012) | AI answer names a code-vetoed idea; facts list it as vetoed | row stays veto by code | Pass |
| UT-MKT-005.012.M07.T03 | MD-MKT-005.012.M07 | Negative | Unknown idea (SRD-MKT-005.012) | AI vetoes a stock not listed | dropped; logged | Pass |
| UT-MKT-005.012.M07.T04 | MD-MKT-005.012.M07 | Edge | Missing views (SRD-MKT-005.012) | no sector_view row for the day | facts say the sector view is not available | Pass |
| UT-MKT-005.013.M07.T01 | MD-MKT-005.012.M07 | Positive | One row per idea (SRD-MKT-005.013) | 6 listed ideas, 2 code vetoes | 6 risk_check rows; feed item counts both kinds | Pass |
| UT-MKT-005.013.M07.T02 | MD-MKT-005.012.M07 | Negative | Code vetoes without AI (SRD-MKT-005.013) | ask returns None | code vetoes stored; others pass by code | Pass |
| UT-MKT-005.014.M08.T01 | MD-MKT-005.014.M08 | Positive | Lead facts (SRD-MKT-005.014) | all four views and risk rows | text holds each view and only passed ideas | Pass |
| UT-MKT-005.014.M08.T02 | MD-MKT-005.014.M08 | Negative | No risk rows (SRD-MKT-005.014) | risk employee not hired; an idea breaks a hard limit | idea not in the facts; risk view noted missing | Pass |
| UT-MKT-005.015.M08.T01 | MD-MKT-005.014.M08 | Positive | Valid lead answer (SRD-MKT-005.015) | 3 long and 2 short picks, 600-char brief | LeadBrief | Pass |
| UT-MKT-005.015.M08.T02 | MD-MKT-005.014.M08 | Negative | Vetoed or extra picks (SRD-MKT-005.015) | a vetoed pick; 7 long picks | vetoed dropped and logged; first 5 long kept | Pass |
| UT-MKT-005.015.M08.T03 | MD-MKT-005.014.M08 | Negative | Bad lead answer (SRD-MKT-005.015) | 1,300-char brief; 130-char reason | refused by the schema | Pass |
| UT-MKT-005.016.M08.T01 | MD-MKT-005.014.M08 | Positive | Picks and evening brief (SRD-MKT-005.016) | valid answer, run twice | lead_picks rows of the second run with rank; feed item kind evening | Pass |
| UT-MKT-005.016.M08.T02 | MD-MKT-005.014.M08 | Negative | No answer (SRD-MKT-005.016) | ask returns None | no picks; no feed item | Pass |
| UT-MKT-005.017.M09.T01 | MD-MKT-005.017.M09 | Positive | Default files valid (SRD-MKT-005.017) | shipped emp-002 to emp-005 | each loads with its skill, after_run, caps 3 and USD 3, generic name filled into the soul | Pass |
| UT-MKT-005.017.M09.T02 | MD-MKT-005.017.M09 | Negative | No real names in defaults (SRD-MKT-005.017) | scan default files | names match generic level pattern only | Pass |
| UT-MKT-005.017.M09.T03 | MD-MKT-005.017.M09 | Positive | Name placeholder in souls (SRD-MKT-005.017) | each shipped soul.md | holds {name} to fill in | Pass |
| UT-MKT-005.018.M09.T01 | MD-MKT-005.017.M09 | Positive | Skill list (SRD-MKT-005.018) | SKILL_PATHS | five keys load to skills with matching key | Pass |
| UT-MKT-005.018.M09.T02 | MD-MKT-005.017.M09 | Negative | No desk import (SRD-MKT-005.018) | scan `market` sources | no `us_swing.desk` import | Pass |
| UT-MKT-005.018.M09.T03 | MD-MKT-005.017.M09 | Positive | Full evening chain (SRD-MKT-005.018) | real steps on synthetic candles, made-up employees, fake model | views, risk rows, picks and evening brief stored; lead ran last | Pass |
| UT-MKT-005.013.M07.T03 | MD-MKT-005.012.M07 | Edge | Second wake keeps AI vetoes (SRD-MKT-005.013) | AI veto, then a wake with no valid answer | AI veto kept; code vetoes kept; no feed item | Pass |

## FO-MKT-006: News, Economic Calendar and Event Risk

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-006.001.M01.T01 | MD-MKT-006.001.M01 | Positive | Read a feed (SRD-MKT-006.001) | RSS text with 3 items | 3 headlines with title, link and UTC time | Pass |
| UT-MKT-006.001.M01.T02 | MD-MKT-006.001.M01 | Negative | Bad feed (SRD-MKT-006.001) | broken XML; item without a time; HTTP error | no headlines or that item skipped; no exception | Pass |
| UT-MKT-006.001.M01.T03 | MD-MKT-006.001.M01 | Edge | Symbol with a dot (SRD-MKT-006.001) | BRK.B | URL asks for BRK-B | Pass |
| UT-MKT-006.001.M01.T04 | MD-MKT-006.001.M01 | Negative | Plain failure log (SRD-MKT-006.001) | time-out, HTTP 404, refused connection | one [News] line each: timed out, HTTP 404, connection failed | Pass |
| UT-MKT-006.001.M02.T01 | MD-MKT-006.001.M02 | Positive | Stock headlines kept (SRD-MKT-006.001) | 3 listed ideas, fake getter | rows for each with the ideas day | Pass |
| UT-MKT-006.001.M02.T02 | MD-MKT-006.001.M02 | Negative | One stock fails (SRD-MKT-006.001) | getter raises for one stock | others kept; logged; step does not raise | Pass |
| UT-MKT-006.001.M02.T03 | MD-MKT-006.001.M02 | Edge | Window and cap (SRD-MKT-006.001) | 14 items, 2 older than 3 days | 10 newest within 3 days | Pass |
| UT-MKT-006.001.M02.T04 | MD-MKT-006.001.M02 | Edge | Time limit (SRD-MKT-006.001) | timer past 90 seconds after the first stock | no more stocks fetched; [News] line says how many were not fetched | Pass |
| UT-MKT-006.001.M02.T05 | MD-MKT-006.001.M02 | Negative | Step never raises (SRD-MKT-006.001) | error inside the run | logged with [News]; step returns | Pass |
| UT-MKT-006.002.M02.T01 | MD-MKT-006.001.M02 | Positive | Market headlines (SRD-MKT-006.002) | 3 feeds, 50 items, some older than 24 hours | at most 30, all within 24 hours, symbol empty | Pass |
| UT-MKT-006.002.M02.T02 | MD-MKT-006.001.M02 | Negative | All feeds fail (SRD-MKT-006.002) | getter raises | 0 market rows; logged | Pass |
| UT-MKT-006.003.M02.T01 | MD-MKT-006.001.M02 | Positive | Kept once (SRD-MKT-006.003) | run twice; same title with a new link | no repeated rows | Pass |
| UT-MKT-006.003.M02.T02 | MD-MKT-006.001.M02 | Negative | Old rows deleted (SRD-MKT-006.003) | rows 31 and 29 days old | 31-day row gone, 29-day row kept | Pass |
| UT-MKT-006.003.M02.T03 | MD-MKT-006.001.M02 | Positive | Seen again moves day (SRD-MKT-006.003) | same headline on the next day | row has the new day; counted as not new | Pass |
| UT-MKT-006.003.M02.T04 | MD-MKT-006.001.M02 | Edge | No link (SRD-MKT-006.003) | two headlines without a link, different titles | both kept | Pass |
| UT-MKT-006.004.M03.T01 | MD-MKT-006.004.M03 | Positive | Events listed (SRD-MKT-006.004) | 2026-11-09 to 2026-11-13 | CPI 2026-11-10 08:30 high | Pass |
| UT-MKT-006.004.M03.T02 | MD-MKT-006.004.M03 | Negative | Year not covered (SRD-MKT-006.004) | days in 2029, asked twice | empty; one warning only | Pass |
| UT-MKT-006.004.M03.T03 | MD-MKT-006.004.M03 | Edge | Next trading day (SRD-MKT-006.004) | 2026-11-25; 2026-11-06 | 2026-11-27 (Thanksgiving skipped); 2026-11-09 | Pass |
| UT-MKT-006.004.M03.T04 | MD-MKT-006.004.M03 | Positive | Calendar data sane (SRD-MKT-006.004) | all events | sorted, known names, high for FOMC, CPI, jobs; medium for PCE, GDP | Pass |
| UT-MKT-006.004.M03.T05 | MD-MKT-006.004.M03 | Positive | Covered year (SRD-MKT-006.004) | days in 2026 | no warning | Pass |
| UT-MKT-006.004.M03.T06 | MD-MKT-006.004.M03 | Edge | 2027 holidays (SRD-MKT-006.004) | 2027-11-24, 2027-12-23, 2027-01-15 | 2027-11-26, 2027-12-27, 2027-01-19 | Pass |
| UT-MKT-006.005.M04.T01 | MD-MKT-006.005.M04 | Positive | News facts (SRD-MKT-006.005) | ideas, headlines, market headlines | text holds ideas, headlines, market lines and events; fresh True | Pass |
| UT-MKT-006.005.M04.T02 | MD-MKT-006.005.M04 | Negative | Stale news (SRD-MKT-006.005) | news day older than ideas day | fresh False; days named | Pass |
| UT-MKT-006.005.M04.T03 | MD-MKT-006.005.M04 | Edge | No headlines (SRD-MKT-006.005) | ideas but no stock headlines | fresh True; facts say no headlines | Pass |
| UT-MKT-006.006.M04.T01 | MD-MKT-006.005.M04 | Positive | Valid answer (SRD-MKT-006.006) | 2 tags and a 200-char note | NewsReview | Pass |
| UT-MKT-006.006.M04.T02 | MD-MKT-006.005.M04 | Negative | Bad answer (SRD-MKT-006.006) | tone great; 130-char reason; 500-char note | each refused by the schema | Pass |
| UT-MKT-006.006.M04.T03 | MD-MKT-006.005.M04 | Negative | Unknown or repeated idea (SRD-MKT-006.006) | tag for a stock not listed; two tags for one | dropped; one log line | Pass |
| UT-MKT-006.007.M04.T01 | MD-MKT-006.005.M04 | Positive | Points table (SRD-MKT-006.007) | each tone, no event | 10, 6, 6, 2 | Pass |
| UT-MKT-006.007.M04.T02 | MD-MKT-006.005.M04 | Negative | High event next day (SRD-MKT-006.007) | day before CPI; negative tone | 3 less; never below 0 | Pass |
| UT-MKT-006.007.M04.T03 | MD-MKT-006.005.M04 | Edge | Medium event only (SRD-MKT-006.007) | day before PCE | no change | Pass |
| UT-MKT-006.008.M04.T01 | MD-MKT-006.005.M04 | Positive | Final score stored (SRD-MKT-006.008) | score 70, positive | final 73.0 in news_tags; ideas table unchanged | Pass |
| UT-MKT-006.008.M04.T02 | MD-MKT-006.005.M04 | Negative | No answer (SRD-MKT-006.008) | ask returns None, day before CPI | code rows tone none, points 3; no feed item | Pass |
| UT-MKT-006.008.M04.T03 | MD-MKT-006.005.M04 | Edge | Earlier tags kept (SRD-MKT-006.008) | real tags, then a failed second ask | earlier tags stay | Pass |
| UT-MKT-006.008.M05.T01 | MD-MKT-006.008.M05 | Edge | Rerun replaces (SRD-MKT-006.008) | write tags twice for one day | one set of rows | Pass |
| UT-MKT-006.009.M04.T01 | MD-MKT-006.005.M04 | Positive | Market note in feed (SRD-MKT-006.009) | valid answer | info feed item with the note | Pass |
| UT-MKT-006.009.M04.T02 | MD-MKT-006.005.M04 | Negative | No note without answer (SRD-MKT-006.009) | ask returns None | no feed item | Pass |
| UT-MKT-006.010.M07.T01 | MD-MKT-005.012.M07 | Positive | Risk facts show news (SRD-MKT-006.010) | news_tags for the day | facts list tone, points and final score | Pass |
| UT-MKT-006.010.M07.T02 | MD-MKT-005.012.M07 | Negative | News missing (SRD-MKT-006.010) | no news_tags | facts say the news review is not available | Pass |
| UT-MKT-006.010.M08.T01 | MD-MKT-005.014.M08 | Positive | Lead sees final score (SRD-MKT-006.010) | news_tags for passed ideas | final column in the facts | Pass |
| UT-MKT-006.010.M08.T02 | MD-MKT-005.014.M08 | Positive | Run order (SRD-MKT-006.010) | needs of risk check and lead | both include news_review | Pass |
| UT-MKT-006.011.M06.T01 | MD-MKT-006.011.M06 | Positive | Default file valid (SRD-MKT-006.011) | shipped emp-006 | loads; skill news_review; after_run; caps 3 and USD 3; generic name | Pass |
| UT-MKT-006.011.M06.T02 | MD-MKT-006.011.M06 | Negative | Skill list and boundary (SRD-MKT-006.011) | SKILL_PATHS, STEP_PATHS, market sources | news_review loads; News after Ideas; no desk import | Pass |
| UT-MKT-006.012.M02.T01 | MD-MKT-006.001.M02 | Positive | Run log (SRD-MKT-006.012) | one run with one failed feed | one [News] line with the counts | Pass |
