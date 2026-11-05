# Unit Test Cases — Market Analytics (MKT)

**Document ID:** UTCD-MKT
**Version:** 0.3.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

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
| UT-MKT-003.001.M01.T01 | MD-MKT-003.001.M01 | Positive | Volume read (SRD-MKT-003.001) | candles with volume | volumes frame by date and symbol | Not Run |
| UT-MKT-003.001.M02.T01 | MD-MKT-003.002.M02 | Positive | Liquid stock scored (SRD-MKT-003.001) | close 100, volume 300k | dollar volume 30M; kept | Not Run |
| UT-MKT-003.001.M02.T02 | MD-MKT-003.002.M02 | Negative | Thin stock left out (SRD-MKT-003.001) | close 10, volume 1M | dollar volume 10M; not scored | Not Run |
| UT-MKT-003.002.M02.T01 | MD-MKT-003.002.M02 | Positive | Strong buying (SRD-MKT-003.002) | up days on high volume, closes near highs | flow long near 1; short near 0 | Not Run |
| UT-MKT-003.002.M02.T02 | MD-MKT-003.002.M02 | Negative | Heavy selling (SRD-MKT-003.002) | down days on high volume, closes near lows | flow long near 0 | Not Run |
| UT-MKT-003.002.M02.T03 | MD-MKT-003.002.M02 | Edge | Flat bar (SRD-MKT-003.002) | high equals low | money flow term 0; no error | Not Run |
| UT-MKT-003.003.M03.T01 | MD-MKT-003.003.M03 | Positive | Squeeze found (SRD-MKT-003.003) | uptrend, then narrow range | Squeeze; trigger 20-day high; stop 20-day low | Not Run |
| UT-MKT-003.003.M03.T02 | MD-MKT-003.003.M03 | Positive | Flat base found (SRD-MKT-003.003) | near 52-week high, 25-day range 10% | Flat base; trigger 25-day high | Not Run |
| UT-MKT-003.003.M03.T03 | MD-MKT-003.003.M03 | Positive | Pullback found (SRD-MKT-003.003) | uptrend, low touches 21-day average | Pullback; trigger 3-day high; stop 5-day low | Not Run |
| UT-MKT-003.003.M03.T04 | MD-MKT-003.003.M03 | Negative | No long setup (SRD-MKT-003.003) | downtrend | no setup; tightness 0 | Not Run |
| UT-MKT-003.004.M03.T01 | MD-MKT-003.003.M03 | Positive | Failed breakout found (SRD-MKT-003.004) | close above pivot, then back below | Failed breakout; stop at breakout high | Not Run |
| UT-MKT-003.004.M03.T02 | MD-MKT-003.003.M03 | Positive | Lower highs found (SRD-MKT-003.004) | three falling 10-day highs under falling 50-day | Lower highs; trigger 10-day low | Not Run |
| UT-MKT-003.004.M03.T03 | MD-MKT-003.003.M03 | Positive | Breakdown found (SRD-MKT-003.004) | close crosses under 50-day on 2x volume | Breakdown; trigger today's low | Not Run |
| UT-MKT-003.004.M03.T04 | MD-MKT-003.003.M03 | Negative | No short setup (SRD-MKT-003.004) | steady uptrend | no setup | Not Run |
| UT-MKT-003.005.M04.T01 | MD-MKT-003.005.M04 | Positive | Score from parts (SRD-MKT-003.005) | all parts 1 | score 100 | Not Run |
| UT-MKT-003.005.M04.T02 | MD-MKT-003.005.M04 | Positive | Weights and scale (SRD-MKT-003.005) | known parts | score = (20rs+20flow+20setup+15sector+15regime)*100/90 | Not Run |
| UT-MKT-003.005.M04.T03 | MD-MKT-003.005.M04 | Negative | Missing RS rating (SRD-MKT-003.005) | stock without rating that day | no score | Not Run |
| UT-MKT-003.006.M04.T01 | MD-MKT-003.005.M04 | Positive | Extended long (SRD-MKT-003.006) | close 10% above 20-day average | 10 points off; reason added | Not Run |
| UT-MKT-003.006.M04.T02 | MD-MKT-003.005.M04 | Edge | Score floor (SRD-MKT-003.006) | raw 5, penalty 10 | score 0 | Not Run |
| UT-MKT-003.006.M04.T03 | MD-MKT-003.005.M04 | Negative | Not extended (SRD-MKT-003.006) | close 5% above 20-day average | no penalty; no extended reason | Not Run |
| UT-MKT-003.007.M04.T01 | MD-MKT-003.005.M04 | Positive | Top 10 per side (SRD-MKT-003.007) | 15 stocks scoring 60+ | 10 listed, ranks 1–10 | Not Run |
| UT-MKT-003.007.M04.T02 | MD-MKT-003.005.M04 | Negative | Below 60 left out (SRD-MKT-003.007) | best score 55 | no ideas | Not Run |
| UT-MKT-003.007.M04.T03 | MD-MKT-003.005.M04 | Positive | Earnings to Watch (SRD-MKT-003.007) | earnings in 3 trading days | status watch; reason Earnings in 3 days | Not Run |
| UT-MKT-003.007.M04.T04 | MD-MKT-003.005.M04 | Positive | Short against Uptrend (SRD-MKT-003.007) | regime Uptrend, short 70 | status watch | Not Run |
| UT-MKT-003.008.M04.T01 | MD-MKT-003.005.M04 | Positive | Reasons in plain words (SRD-MKT-003.008) | listed idea | 1–5 reasons; no codes or underscores | Not Run |
| UT-MKT-003.008.M04.T02 | MD-MKT-003.005.M04 | Negative | No false reasons (SRD-MKT-003.008) | listed idea, no earnings, with the regime | no Watch or earnings reason | Not Run |
| UT-MKT-003.009.M05.T01 | MD-MKT-003.009.M05 | Positive | Earnings dates read (SRD-MKT-003.009) | fake Yahoo calendar | date per symbol | Not Run |
| UT-MKT-003.009.M05.T02 | MD-MKT-003.009.M05 | Negative | Yahoo down (SRD-MKT-003.009) | fetch raises | None per symbol; no error | Not Run |
| UT-MKT-003.010.M06.T01 | MD-MKT-003.010.M06 | Positive | Rows round trip (SRD-MKT-003.010) | 2 days of score, idea and reason rows | same rows back; re-write replaces the day | Not Run |
| UT-MKT-003.010.M06.T02 | MD-MKT-003.010.M06 | Negative | Row without a date (SRD-MKT-003.010) | idea row with empty date | raises ValueError; nothing written | Not Run |
| UT-MKT-003.011.M07.T01 | MD-MKT-003.011.M07 | Positive | First run fills history (SRD-MKT-003.011) | 300 days, regime and sector rows present | score and idea rows from the first ready day | Not Run |
| UT-MKT-003.011.M07.T02 | MD-MKT-003.011.M07 | Positive | Later run adds a new day (SRD-MKT-003.011) | one more bar | one new day of rows; earnings checked for it | Not Run |
| UT-MKT-003.011.M07.T03 | MD-MKT-003.011.M07 | Negative | No sector rows yet (SRD-MKT-003.011) | desk.db without sector_daily rows | no rows; run not failed | Not Run |
| UT-MKT-003.011.M07.T04 | MD-MKT-003.011.M07 | Negative | No candle file (SRD-MKT-003.011) | missing candles.db | no rows; run not failed | Not Run |
| UT-MKT-003.011.M07.T05 | MD-MKT-003.011.M07 | Positive | Runs third in a desk run (SRD-MKT-003.011) | loaded step list, run-now | regime, sectors and ideas ok; idea rows written | Not Run |
