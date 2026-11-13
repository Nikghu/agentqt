# Unit Test Cases — Market Analytics (MKT)

**Document ID:** UTCD-MKT
**Version:** 0.9.1
**Status:** Draft
**Last Updated:** 2026-11-11
**Project:** US Swing Trading System

> v0.24.0: UT-MKT-013.013.M02.T01–T03 added (Not Run, 3) — AI Desk v3 M2 (2026-11-13).
> v0.23.1: UT-MKT-005.024.M05.T01–T02 added and Pass; UT-MKT-005.022.M07.T05 Pass (2026-11-13).
> v0.23.0: UT-MKT-005.019–.023 and 006.013 added (Not Run, 16) — AI Desk v3 M1 (2026-11-13).
> v0.22.1: UT-MKT-019.* Pass (36, 2026-11-12).
> v0.22.0: UT-MKT-019.* added (36, Not Run) — strategy test research (2026-11-12).
> v0.21.1: Step F book cases Pass (23, 2026-11-11).
> v0.21.0: UT-MKT-018.* added (23, Not Run) — book to strategy research (step F).
> v0.20.1: Step F sentiment cases Pass (22, 2026-11-11).
> v0.20.0: UT-MKT-017.* added (22, Not Run) — sentiment research (step F).
> v0.19.1: Step F post-mortem cases Pass (22, 2026-11-11).
> v0.19.0: UT-MKT-016.* added (22, Not Run) — pick post-mortem research (step F).
> v0.18.1: Step F setup tuning cases Pass (31, 2026-11-11).
> v0.18.0: UT-MKT-015.* added (31, Not Run) — setup tuning research (step F).
> v0.17.1: Step E cases Pass (12, 2026-11-11).
> v0.17.0: Autonomous desk step E (2026-11-11): UT-MKT-014.001–.005 added (12 cases).
> v0.16.1: Step D cases Pass (31, 2026-11-11).
> v0.16.0: Autonomous desk step D (2026-11-11): UT-MKT-013.* added (31 cases).
> v0.15.1: Step C cases Pass (13 cases, 2026-11-11).
> v0.15.0: Autonomous desk step C (2026-11-11): UT-MKT-012.* added (13 cases).
> v0.14.0: Autonomous desk step A (2026-11-11): 14 cases for the candle check and desk copy (UT-MKT-001.013–.017); morning brief rows reworded.
> v0.13.1: UT-MKT-011 test cases run — 25 Pass.
> v0.13.0: 25 test cases for FO-MKT-011 ask the desk for new data (P10).
> v0.12.0: 17 test cases for FO-MKT-010 lead chat (P9).
> v0.11.0: 23 test cases for FO-MKT-009 pick results (P8).
> v0.10.1: UT-MKT-008.004.M01.T05 added (review fix).
> v0.10.0: 18 test cases for FO-MKT-008 link to Execution (P7).
> v0.9.0: 23 test cases for FO-MKT-007 AI report pages (P5d).
> v0.8.0: 43 test cases for FO-MKT-006 news, economic calendar and event risk (P5c).
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
| UT-MKT-001.013.M06.T01 | MD-MKT-001.013.M06 | Positive | Target day (SRD-MKT-001.013) | Wed 2026-11-11 08:30 ET; Wed 16:05 ET; Mon 2026-11-16 08:30 ET | 2026-11-10; 2026-11-11; 2026-11-13 | Pass |
| UT-MKT-001.013.M06.T02 | MD-MKT-001.013.M06 | Positive | Up to date: no fetch (SRD-MKT-001.013) | all members and SPY at the target day | fetch not called; step returns; no copy rows | Pass |
| UT-MKT-001.014.M06.T01 | MD-MKT-001.013.M06 | Positive | Behind stocks filled into the desk copy (SRD-MKT-001.014) | 3 of 100 members one day behind; fake Yahoo with 10 overlap days | 3 copy rows on the target day; `candles.db` unchanged | Pass |
| UT-MKT-001.014.M06.T02 | MD-MKT-001.013.M06 | Positive | Volume scaled by the IBKR/Yahoo median (SRD-MKT-001.014) | overlap volume ratios 0.5, 0.5, 0.6; new Yahoo volume 1,000,000 | copy volume 500,000 | Pass |
| UT-MKT-001.014.M06.T03 | MD-MKT-001.013.M06 | Negative | Price mismatch or short overlap skips the stock (SRD-MKT-001.014) | overlap close off by 2%; only 2 overlap days | no copy row for those stocks | Pass |
| UT-MKT-001.015.M01.T01 | MD-MKT-001.001.M01 | Positive | Reader adds copy days candles.db lacks (SRD-MKT-001.015) | candles.db to 11-09, copy 11-10 | read() ends 11-10; symbols() includes copy-only stocks | Pass |
| UT-MKT-001.015.M01.T02 | MD-MKT-001.001.M01 | Edge | candles.db wins over the copy (SRD-MKT-001.015) | both have 11-10 with different closes | candles.db close used | Pass |
| UT-MKT-001.015.M04.T01 | MD-MKT-001.007.M04 | Positive | Copy rows trimmed once IBKR has the day (SRD-MKT-001.015) | copy 11-10; candles.db now to 11-10 | copy row deleted | Pass |
| UT-MKT-001.015.M04.T02 | MD-MKT-001.007.M04 | Positive | Unsettled copy bar fetched again (SRD-MKT-001.015) | copy row for 11-10 fetched 16:05 ET | row dropped, fetched again from Yahoo | Pass |
| UT-MKT-001.015.M01.T03 | MD-MKT-001.001.M01 | Positive | Latest SPY day sees the copy (SRD-MKT-001.015) | SPY in candles.db to 11-09, copy 11-10 | `latest_spy_day` returns 2026-11-10 | Pass |
| UT-MKT-001.016.M06.T01 | MD-MKT-001.013.M06 | Negative | Still behind stops the run with an alert (SRD-MKT-001.016, SRD-DSK-007.007) | Yahoo returns nothing; 5 of 100 behind | raises `CandleCheckError` naming 5 of 101; one `candles` alert | Pass |
| UT-MKT-001.016.M06.T02 | MD-MKT-001.013.M06 | Edge | 2% rule and SPY (SRD-MKT-001.016) | 2 of 100 members behind; SPY alone behind | no error; error | Pass |
| UT-MKT-001.016.M06.T03 | MD-MKT-001.013.M06 | Negative | No candle file (SRD-MKT-001.016) | missing candles.db | raises `CandleCheckError` | Pass |
| UT-MKT-001.017.M06.T01 | MD-MKT-001.013.M06 | Positive | Check logs the counts (SRD-MKT-001.017) | 3 behind, 2 filled | one `[Candles]` line with 3, 2 and 1 | Pass |
| UT-MKT-001.013.M06.T03 | MD-MKT-001.013.M06 | Positive | Candle check is the first desk step (SRD-MKT-001.013) | `STEP_PATHS` | first path is the candle check | Pass |

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
| UT-MKT-005.016.M08.T01 | MD-MKT-005.014.M08 | Positive | Picks and morning brief (SRD-MKT-005.015, .016) | valid answer with a `morning` field, run twice | lead_picks rows of the second run with rank; feed item kind morning | Pass |
| UT-MKT-005.016.M08.T02 | MD-MKT-005.014.M08 | Negative | No answer (SRD-MKT-005.016) | ask returns None | no picks; no feed item | Pass |
| UT-MKT-005.017.M09.T01 | MD-MKT-005.017.M09 | Positive | Default files valid (SRD-MKT-005.017) | shipped emp-002 to emp-005 | each loads with its skill, after_run, caps 3 and USD 3, generic name filled into the soul | Pass |
| UT-MKT-005.017.M09.T02 | MD-MKT-005.017.M09 | Negative | No real names in defaults (SRD-MKT-005.017) | scan default files | names match generic level pattern only | Pass |
| UT-MKT-005.017.M09.T03 | MD-MKT-005.017.M09 | Positive | Name placeholder in souls (SRD-MKT-005.017) | each shipped soul.md | holds {name} to fill in | Pass |
| UT-MKT-005.018.M09.T01 | MD-MKT-005.017.M09 | Positive | Skill list (SRD-MKT-005.018) | SKILL_PATHS | five keys load to skills with matching key | Pass |
| UT-MKT-005.018.M09.T02 | MD-MKT-005.017.M09 | Negative | No desk import (SRD-MKT-005.018) | scan `market` sources | no `us_swing.desk` import | Pass |
| UT-MKT-005.018.M09.T03 | MD-MKT-005.017.M09 | Positive | Full morning chain (SRD-MKT-005.018) | real steps on synthetic candles, made-up employees, fake model | views, risk rows, picks and morning brief stored; lead ran last | Pass |
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

## FO-MKT-007: AI Report Pages

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-007.001.M02.T01 | MD-MKT-007.001.M02 | Positive | Report facts (SRD-MKT-007.001) | ideas, lead picks, morning brief (and an old evening brief on another day), views for the day | text holds the day's brief, picks and views; fresh True | Pass |
| UT-MKT-007.001.M02.T02 | MD-MKT-007.001.M02 | Negative | No lead brief (SRD-MKT-007.001) | ideas for the day, no evening brief | fresh False; reason names the day | Pass |
| UT-MKT-007.001.M02.T03 | MD-MKT-007.001.M02 | Edge | No briefs table (SRD-MKT-007.001) | fresh ideas, `briefs` table missing | fresh False; no exception | Pass |
| UT-MKT-007.001.M02.T04 | MD-MKT-007.001.M02 | Positive | Run order (SRD-MKT-007.001) | skill needs | needs is ("lead_brief",) | Pass |
| UT-MKT-007.002.M02.T01 | MD-MKT-007.001.M02 | Positive | Valid answer (SRD-MKT-007.002) | 20-char title, 2 KB html | ReportPage | Pass |
| UT-MKT-007.002.M02.T02 | MD-MKT-007.001.M02 | Negative | Bad answer (SRD-MKT-007.002) | 81-char title; 50-char html; html over 200 000 chars; extra field | each refused by the schema | Pass |
| UT-MKT-007.003.M01.T01 | MD-MKT-007.003.M01 | Positive | Allowed content kept (SRD-MKT-007.003) | table, h2, style block, inline svg chart | same tags and text kept; removed 0 | Pass |
| UT-MKT-007.003.M01.T02 | MD-MKT-007.003.M01 | Negative | Scripts and handlers (SRD-MKT-007.003) | script with code, onclick, onload on svg, iframe, a href javascript: | no script text, no on* attribute, no iframe, no href; removed counted | Pass |
| UT-MKT-007.003.M01.T03 | MD-MKT-007.003.M01 | Negative | Outside and local images (SRD-MKT-007.003) | img src https, file:, data:image/svg+xml, data:image/png;base64 | only the png img kept | Pass |
| UT-MKT-007.003.M01.T04 | MD-MKT-007.003.M01 | Negative | CSS loads (SRD-MKT-007.003) | style with @import, url(), expression(); style attribute with url() | those parts removed; other rules kept | Pass |
| UT-MKT-007.003.M01.T05 | MD-MKT-007.003.M01 | Edge | Tricky markup (SRD-MKT-007.003) | escaped script text, upper-case SCRIPT, unclosed tags, comment, doctype, closing style tag inside CSS | text stays escaped; script dropped; comment and doctype gone; output parses | Pass |
| UT-MKT-007.003.M01.T06 | MD-MKT-007.003.M01 | Positive | Sealed shell (SRD-MKT-007.003) | clean body and a title with < | full page with the CSP meta; title escaped | Pass |
| UT-MKT-007.003.M01.T07 | MD-MKT-007.003.M01 | Negative | CSS rebuilt loads (SRD-MKT-007.003) | ur<l(...), ur@import a;l(...), CSS escapes, image-set(), @font-face local() | no url(, image-set, @import, local( or backslash left | Pass |
| UT-MKT-007.003.M01.T08 | MD-MKT-007.003.M01 | Negative | Repeated and SVG attributes (SRD-MKT-007.003) | img with two src; svg fill url(); self-closed style | only a data src kept; fill cleaned; style dropped; later text kept | Pass |
| UT-MKT-007.004.M03.T01 | MD-MKT-007.004.M03 | Positive | Versions (SRD-MKT-007.004) | two pages on one day, one on the next | versions 1, 2, then 1 | Pass |
| UT-MKT-007.004.M03.T02 | MD-MKT-007.004.M03 | Negative | Append-only (SRD-MKT-007.004) | UPDATE and DELETE on canvas_pages | both refused; rows unchanged | Pass |
| UT-MKT-007.005.M02.T01 | MD-MKT-007.001.M02 | Negative | No answer (SRD-MKT-007.005) | ask returns None | no page row; no feed item | Pass |
| UT-MKT-007.005.M02.T02 | MD-MKT-007.001.M02 | Negative | Empty after cleaning (SRD-MKT-007.005) | html made only of script and iframe | no page row; no feed item; [Report] warning | Pass |
| UT-MKT-007.005.M02.T03 | MD-MKT-007.001.M02 | Edge | Last good version stays (SRD-MKT-007.005) | one saved version, then a failed answer | still one version, unchanged | Pass |
| UT-MKT-007.006.M02.T01 | MD-MKT-007.001.M02 | Positive | Feed brief (SRD-MKT-007.006) | valid answer | one info feed item with the title and version; html stored cleaned | Pass |
| UT-MKT-007.007.M04.T01 | MD-MKT-007.007.M04 | Positive | Default file valid (SRD-MKT-007.007) | shipped emp-007 | loads; skill report_page; after_run; caps 3 and USD 3; generic name | Pass |
| UT-MKT-007.007.M04.T02 | MD-MKT-007.007.M04 | Negative | Skill list and boundary (SRD-MKT-007.007) | SKILL_PATHS, market sources | report_page loads; no desk import in market | Pass |
| UT-MKT-007.008.M02.T01 | MD-MKT-007.001.M02 | Positive | Run log (SRD-MKT-007.008) | valid answer with one script | one [Report] line with day, version, sizes and 1 item removed | Pass |

## FO-MKT-008: Link to Execution

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-008.001.M01.T01 | MD-MKT-008.001.M01 | Positive | Trade picks listed (SRD-MKT-008.001) | long and short lead picks, both pass, with ideas | 2 picks with entry, stop and target; ordered by side and rank | Pass |
| UT-MKT-008.001.M01.T02 | MD-MKT-008.001.M01 | Negative | Not listed (SRD-MKT-008.001) | a vetoed pick; a pick with no risk row; an idea with no trigger | none of them listed | Pass |
| UT-MKT-008.001.M01.T03 | MD-MKT-008.001.M01 | Edge | Latest day only (SRD-MKT-008.001) | lead picks on two days; no lead_picks table | only the newer day; empty list, no error | Pass |
| UT-MKT-008.002.M01.T01 | MD-MKT-008.001.M01 | Positive | 2R target (SRD-MKT-008.002) | long 100 / 95, r 2; short 50 / 52, r 2 | 110.0; 46.0 | Pass |
| UT-MKT-008.002.M01.T02 | MD-MKT-008.001.M01 | Negative | Bad stop (SRD-MKT-008.002) | stop equals entry; long stop above entry; short stop below entry | None each; the pick is not listed | Pass |
| UT-MKT-008.002.M02.T01 | MD-MKT-008.002.M02 | Positive | R setting (SRD-MKT-008.002) | no file; file with trade_target_r 1.5 | 2.0; 1.5 | Pass |
| UT-MKT-008.002.M02.T02 | MD-MKT-008.002.M02 | Negative | R not above 0 (SRD-MKT-008.002) | trade_target_r 0 in code; -1 in the file | ValueError; defaults loaded with a warning | Pass |
| UT-MKT-008.003.M01.T01 | MD-MKT-008.001.M01 | Positive | Waiting until next open (SRD-MKT-008.003) | day Fri 2026-11-06, now Sat noon ET | waiting; expires Mon 2026-11-09 09:30 ET | Pass |
| UT-MKT-008.003.M01.T02 | MD-MKT-008.001.M01 | Edge | Expiry edge and holiday (SRD-MKT-008.003) | now exactly 09:30 ET on the next day; day 2026-11-25 | expired; expires 2026-11-27 09:30 ET | Pass |
| UT-MKT-008.003.M01.T03 | MD-MKT-008.001.M01 | Positive | Decided state (SRD-MKT-008.003) | approve row; reject row for another pick | approved; rejected | Pass |
| UT-MKT-008.003.M01.T04 | MD-MKT-008.001.M01 | Negative | Other rows ignored (SRD-MKT-008.003) | reject row for another pick; hire row with the same subject; no desk.db | waiting each time | Pass |
| UT-MKT-008.004.M01.T01 | MD-MKT-008.001.M01 | Positive | Approve row (SRD-MKT-008.004) | waiting pick, qty 45 | one row kind trade, subject day:side:symbol, detail JSON with entry, stop, target, qty | Pass |
| UT-MKT-008.004.M01.T02 | MD-MKT-008.001.M01 | Negative | Second or late decision (SRD-MKT-008.004) | decide twice; decide after expiry; decision 'maybe' | reason returned each time; one row only | Pass |
| UT-MKT-008.004.M01.T03 | MD-MKT-008.001.M01 | Edge | Table missing and append-only (SRD-MKT-008.004) | desk.db with no approvals table; then UPDATE the row | table made and row saved; UPDATE refused | Pass |
| UT-MKT-008.004.M01.T04 | MD-MKT-008.001.M01 | Positive | Approved picks for a day (SRD-MKT-008.004) | approve and reject rows for day Fri; trading day Mon | only the approved pick, with its detail values | Pass |
| UT-MKT-008.004.M01.T05 | MD-MKT-008.001.M01 | Positive | Done picks left out (SRD-MKT-008.004) | two approved picks; one has an executed outcome row | only the other pick comes back | Pass |
| UT-MKT-008.005.M01.T01 | MD-MKT-008.001.M01 | Positive | No desk or GUI import (SRD-MKT-008.005) | source of core/desk_trades.py | no import of desk, market or gui | Pass |
| UT-MKT-008.005.M01.T02 | MD-MKT-008.001.M01 | Negative | Desk process never writes (SRD-MKT-008.005) | source of the desk and market packages | no call to record_trade_decision and no trade approval insert | Pass |
| UT-MKT-008.006.M01.T01 | MD-MKT-008.001.M01 | Positive | Logs (SRD-MKT-008.006) | approve one pick; list with 2 expired picks | INFO lines with [AI Desk] prefix, side, stock and decision; expired count 2 | Pass |

## FO-MKT-009: Pick Results

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-009.001.M01.T01 | MD-MKT-009.001.M01 | Positive | Step scores every pick (SRD-MKT-009.001) | 2 lead picks on 2 days with ideas and candles | 2 pick_results rows | Pass |
| UT-MKT-009.001.M01.T02 | MD-MKT-009.001.M01 | Negative | No candle file (SRD-MKT-009.001) | candle path missing | one warning; no rows; no error | Pass |
| UT-MKT-009.002.M01.T01 | MD-MKT-009.001.M01 | Positive | Long entry (SRD-MKT-009.002) | trigger 100; high 99, 99, 101 | entry day 3 at 100 | Pass |
| UT-MKT-009.002.M01.T02 | MD-MKT-009.001.M01 | Negative | No fill (SRD-MKT-009.002) | trigger touched only on bar 6 | no_fill | Pass |
| UT-MKT-009.002.M01.T03 | MD-MKT-009.001.M01 | Positive | Short entry (SRD-MKT-009.002) | short trigger 50; low 49 on bar 1 | entry day 1 at 50 | Pass |
| UT-MKT-009.003.M01.T01 | MD-MKT-009.001.M01 | Positive | Target (SRD-MKT-009.003) | long 100 / 95 / 110; later high 111 | target; exit 110; R 2.0 | Pass |
| UT-MKT-009.003.M01.T02 | MD-MKT-009.001.M01 | Positive | Stop (SRD-MKT-009.003) | long 100 / 95; later low 94 | stop; exit 95; R -1.0 | Pass |
| UT-MKT-009.003.M01.T03 | MD-MKT-009.001.M01 | Edge | Stop and target one day (SRD-MKT-009.003) | bar with low 94 and high 111 | stop | Pass |
| UT-MKT-009.003.M01.T04 | MD-MKT-009.001.M01 | Edge | Time exit and open (SRD-MKT-009.003) | 10 quiet bars after entry; then only 4 bars | time at close of day 10; open marked at latest close, no exit day | Pass |
| UT-MKT-009.003.M01.T05 | MD-MKT-009.001.M01 | Negative | Bad levels (SRD-MKT-009.003) | long stop above trigger; short target above trigger | None; not scored | Pass |
| UT-MKT-009.004.M02.T01 | MD-MKT-009.004.M02 | Positive | Rows replaced (SRD-MKT-009.004) | replace the same 2 rows twice | 2 rows, no duplicates | Pass |
| UT-MKT-009.004.M02.T02 | MD-MKT-009.004.M02 | Negative | Bad status (SRD-MKT-009.004) | status 'won' | ValueError; table unchanged | Pass |
| UT-MKT-009.005.M03.T01 | MD-MKT-009.005.M03 | Positive | Real trade matched (SRD-MKT-009.005) | executed trade_done row; closed long cycle 100 → 110, stop 95, qty 10 | row with subject, pnl 100, R 2.0 | Pass |
| UT-MKT-009.005.M03.T02 | MD-MKT-009.005.M03 | Negative | No pick and append-only (SRD-MKT-009.005) | cycle with no approval row; then UPDATE the row | row with empty subject; UPDATE refused | Pass |
| UT-MKT-009.005.M04.T01 | MD-MKT-009.005.M04 | Positive | App hook (SRD-MKT-009.005) | CycleClosed for AI Desk and for another strategy | one row, for AI Desk only | Pass |
| UT-MKT-009.006.M03.T01 | MD-MKT-009.005.M03 | Positive | Totals (SRD-MKT-009.006) | picks with target, stop, no_fill and open | picks 4, fills 3, finished 2, hit rate 50%, avg R 0.5 | Pass |
| UT-MKT-009.006.M03.T02 | MD-MKT-009.005.M03 | Positive | Breakdowns (SRD-MKT-009.006) | grades A and B, tones positive and none, one approved and one rejected pick | groups per decision, grade and tone with their counts | Pass |
| UT-MKT-009.006.M03.T03 | MD-MKT-009.005.M03 | Edge | Empty desk (SRD-MKT-009.006) | no desk.db; no pick_results table | zero totals; no error | Pass |
| UT-MKT-009.006.M03.T04 | MD-MKT-009.005.M03 | Negative | No employee names (SRD-MKT-009.006) | employee folder with a made-up name; results lines | the name is in no group label or line | Pass |
| UT-MKT-009.007.M05.T01 | MD-MKT-009.007.M05 | Positive | Weekly section (SRD-MKT-009.007) | picks in the week and one before | Pick results section counts only the week's picks | Pass |
| UT-MKT-009.007.M05.T02 | MD-MKT-009.007.M05 | Edge | No picks (SRD-MKT-009.007) | week with no lead picks | section says no lead picks this week | Pass |
| UT-MKT-009.001.M06.T01 | MD-MKT-009.001.M06 | Positive | Step order (SRD-MKT-009.001) | STEP_PATHS | Pick results after Ideas and News, before AI employees | Pass |
| UT-MKT-009.008.M01.T01 | MD-MKT-009.001.M01 | Positive | Logs (SRD-MKT-009.008) | run with one open pick | [Results] line with counts | Pass |

## FO-MKT-010: Lead Chat

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-010.001.M01.T01 | MD-MKT-010.001.M01 | Positive | Question saved (SRD-MKT-010.001) | ask 'Why AAPL?' | one master chat row; one waiting chat_question event | Pass |
| UT-MKT-010.001.M01.T02 | MD-MKT-010.001.M01 | Negative | Bad question (SRD-MKT-010.001) | empty text; 501 characters | ValueError; no row, no event | Pass |
| UT-MKT-010.001.M01.T03 | MD-MKT-010.001.M01 | Positive | Notes and turns (SRD-MKT-010.001) | question with desk up, desk down, 31 minutes later, then a reply | waiting; start the desk; expired; empty note; turns oldest first | Pass |
| UT-MKT-010.001.M01.T04 | MD-MKT-010.001.M01 | Edge | Append-only (SRD-MKT-010.001) | UPDATE a chat row | refused | Pass |
| UT-MKT-010.002.M02.T01 | MD-MKT-010.002.M02 | Positive | One event per question (SRD-MKT-010.002) | two questions on one day | two events, priority 0, 2-minute deadline, 30-minute expiry | Pass |
| UT-MKT-010.002.M02.T02 | MD-MKT-010.002.M02 | Negative | Unknown kind still refused (SRD-MKT-010.002) | post 'chat_answer' | ValueError | Pass |
| UT-MKT-010.003.M03.T01 | MD-MKT-010.003.M03 | Positive | Chat facts (SRD-MKT-010.003) | open question, 2 earlier turns, picks with paper results | fresh; text has the question, recent chat, today and the picks | Pass |
| UT-MKT-010.003.M03.T02 | MD-MKT-010.003.M03 | Negative | Nothing to answer (SRD-MKT-010.003) | no question; a question 31 minutes old | fresh False each time | Pass |
| UT-MKT-010.003.M03.T03 | MD-MKT-010.003.M03 | Positive | Oldest first (SRD-MKT-010.003) | two open questions | facts and reply are for the older one | Pass |
| UT-MKT-010.004.M03.T01 | MD-MKT-010.003.M03 | Positive | Answer saved (SRD-MKT-010.004) | fake gateway answers 'Because ...' | lead row answered, reply_to the question | Pass |
| UT-MKT-010.004.M03.T02 | MD-MKT-010.003.M03 | Negative | Answer too long (SRD-MKT-010.004) | 1501 characters; extra field | refused by the schema | Pass |
| UT-MKT-010.005.M03.T01 | MD-MKT-010.003.M03 | Negative | No answer (SRD-MKT-010.005) | fake gateway returns None | lead row failed with the failed text | Pass |
| UT-MKT-010.006.M03.T01 | MD-MKT-010.003.M03 | Positive | Answers only (SRD-MKT-010.006) | answer schema fields; skill source | only 'answer'; no approvals, signal or order code | Pass |
| UT-MKT-010.007.M04.T01 | MD-MKT-010.007.M04 | Positive | Default chat employee (SRD-MKT-010.007) | emp-008 job.yaml; SKILL_PATHS | level lead, skill lead_chat, trigger chat_question, 200 calls; skill loads | Pass |
| UT-MKT-010.007.M04.T02 | MD-MKT-010.007.M04 | Negative | No real names (SRD-MKT-010.007) | emp-008 files | generic name only; market does not import desk | Pass |
| UT-MKT-010.008.M03.T01 | MD-MKT-010.003.M03 | Positive | Logs (SRD-MKT-010.008) | one answer and one failure | [Chat] lines with the question numbers | Pass |
| UT-MKT-010.002.M02.T03 | MD-MKT-010.002.M02 | Positive | Desk answers end to end (SRD-MKT-010.002) | EmployeesStep events with a fake caller; one question | the chat employee is woken and a reply row is saved | Pass |

## FO-MKT-011: Ask the Desk for New Data

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-011.001.M01.T01 | MD-MKT-011.001.M01 | Positive | Request saved (SRD-MKT-011.001) | ask 'long scores above 80' | one data_requests row; one waiting data_request event | Pass |
| UT-MKT-011.001.M01.T02 | MD-MKT-011.001.M01 | Negative | Bad request (SRD-MKT-011.001) | empty text; 301 characters | ValueError; no row, no event | Pass |
| UT-MKT-011.001.M01.T03 | MD-MKT-011.001.M01 | Edge | Append-only (SRD-MKT-011.001) | UPDATE a request row; DELETE an asked product row | refused | Pass |
| UT-MKT-011.002.M02.T01 | MD-MKT-011.002.M02 | Positive | One event per request (SRD-MKT-011.002) | two requests on one day | two events, priority 0, 5-minute deadline, 2-hour expiry | Pass |
| UT-MKT-011.002.M02.T02 | MD-MKT-011.002.M02 | Negative | Unknown kind still refused (SRD-MKT-011.002) | post 'data_answer' | ValueError | Pass |
| UT-MKT-011.002.M02.T03 | MD-MKT-011.002.M02 | Positive | Desk answers end to end (SRD-MKT-011.002) | EmployeesStep events with a fake caller; one request | the data employee is woken and an asked product row is saved | Pass |
| UT-MKT-011.003.M04.T01 | MD-MKT-011.003.M04 | Positive | Recipe facts (SRD-MKT-011.003) | open request; sectors stored | fresh; text has the request, every menu source and the sector names | Pass |
| UT-MKT-011.003.M04.T02 | MD-MKT-011.003.M04 | Negative | Nothing to build (SRD-MKT-011.003) | no request; a request 3 hours old | fresh False each time | Pass |
| UT-MKT-011.003.M04.T03 | MD-MKT-011.003.M04 | Positive | Oldest first (SRD-MKT-011.003) | two open requests | facts and asked product are for the older one | Pass |
| UT-MKT-011.004.M03.T01 | MD-MKT-011.004.M03 | Positive | Recipe runs (SRD-MKT-011.004) | scores on 2 days; long, score > 80, sector = Technology, sort score, limit 2 | latest day only, matching rows, high to low, 2 rows | Pass |
| UT-MKT-011.004.M03.T02 | MD-MKT-011.004.M03 | Negative | Check refuses (SRD-MKT-011.004) | unknown column; text column with >; number column with text; unknown sort | a reason each; run raises ValueError | Pass |
| UT-MKT-011.004.M03.T03 | MD-MKT-011.004.M03 | Negative | No SQL from the model (SRD-MKT-011.004) | filter value "x'; DROP TABLE ideas;--"; column named with SQL; limit 101 | 0 rows and tables kept; refused by check; refused by the schema | Pass |
| UT-MKT-011.004.M03.T04 | MD-MKT-011.004.M03 | Edge | Read-only and empty (SRD-MKT-011.004) | no desk.db; table missing | [] each time; no file created | Pass |
| UT-MKT-011.004.M03.T05 | MD-MKT-011.004.M03 | Positive | Recipe in words (SRD-MKT-011.004) | recipe with 2 filters and a sort | source label, columns, filters, sort and row limit in words | Pass |
| UT-MKT-011.005.M04.T01 | MD-MKT-011.003.M04 | Positive | Proposed product (SRD-MKT-011.005) | fake gateway answers a good recipe | one proposed row with title and recipe | Pass |
| UT-MKT-011.005.M04.T02 | MD-MKT-011.003.M04 | Negative | Failed product (SRD-MKT-011.005) | gateway None; recipe None with reason; recipe that fails the check | one failed row each, with the reason | Pass |
| UT-MKT-011.005.M01.T01 | MD-MKT-011.001.M01 | Edge | One answer per request (SRD-MKT-011.005) | second asked product for the same request | refused | Pass |
| UT-MKT-011.006.M01.T01 | MD-MKT-011.001.M01 | Positive | Decision saved (SRD-MKT-011.006) | approve a proposed product | approvals row kind data_product; no longer waiting; listed as approved | Pass |
| UT-MKT-011.006.M01.T02 | MD-MKT-011.001.M01 | Negative | Decision refused (SRD-MKT-011.006) | second decision; unknown decision; unknown or failed product | already decided; unknown decision; not found | Pass |
| UT-MKT-011.007.M05.T01 | MD-MKT-011.007.M05 | Positive | Asked panel in the catalog (SRD-MKT-011.007) | one approved product | product asked.<id> titled '(asked)' with the recipe columns; rows from the recipe | Pass |
| UT-MKT-011.007.M05.T02 | MD-MKT-011.007.M05 | Positive | New day without a rebuild (SRD-MKT-011.007) | approved product, then a new data day stored | rows are the new day's rows | Pass |
| UT-MKT-011.007.M05.T03 | MD-MKT-011.007.M05 | Negative | Not listed (SRD-MKT-011.007) | waiting, rejected and failed products; stored recipe that no longer parses | none in the catalog; unknown asked id gives [] | Pass |
| UT-MKT-011.008.M06.T01 | MD-MKT-011.008.M06 | Positive | Default data employee (SRD-MKT-011.008) | emp-009 job.yaml; SKILL_PATHS | level expert, skill data_recipe, trigger data_request, 20 calls, USD 3; skill loads | Pass |
| UT-MKT-011.008.M06.T02 | MD-MKT-011.008.M06 | Negative | No real names (SRD-MKT-011.008) | emp-009 files | generic name only; market does not import desk | Pass |
| UT-MKT-011.009.M04.T01 | MD-MKT-011.003.M04 | Positive | Logs (SRD-MKT-011.009) | one proposed and one failed request | [Data] lines with the request numbers | Pass |

## FO-MKT-012: Learning from Pick Results

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-012.001.M01.T01 | MD-MKT-012.002.M01 | Positive | Stats by tag (SRD-MKT-012.001) | 6 closed picks, 2 setups | count, win rate and average R per setup | Pass |
| UT-MKT-012.001.M01.T02 | MD-MKT-012.002.M01 | Negative | Open picks left out (SRD-MKT-012.001) | open and no-fill picks | not counted | Pass |
| UT-MKT-012.001.M01.T03 | MD-MKT-009.001.M01 | Positive | Pick results reviews lessons (SRD-MKT-012.001) | candidate with 5 backing closed picks, run the step | lesson active | Pass |
| UT-MKT-012.002.M01.T01 | MD-MKT-012.002.M01 | Positive | Fresh with new closed picks (SRD-MKT-012.002) | closed count above the last reflect | fresh; facts hold stats, new picks and active lessons | Pass |
| UT-MKT-012.002.M01.T02 | MD-MKT-012.002.M01 | Negative | No new closed picks (SRD-MKT-012.002) | closed count equal to the last reflect | not fresh; no call | Pass |
| UT-MKT-012.003.M01.T01 | MD-MKT-012.002.M01 | Positive | Candidates kept (SRD-MKT-012.003) | valid answer with 2 lessons | 2 candidates; reflected count saved; one brief | Pass |
| UT-MKT-012.003.M01.T02 | MD-MKT-012.002.M01 | Negative | Bad form (SRD-MKT-012.003) | 4 lessons; text over 200; unknown tag | schema rejects | Pass |
| UT-MKT-012.003.M01.T03 | MD-MKT-012.002.M01 | Edge | Unknown picks dropped (SRD-MKT-012.003) | one lesson with only unknown pick keys | that lesson dropped; the other kept | Pass |
| UT-MKT-012.004.M02.T01 | MD-MKT-012.004.M02 | Positive | Default reflect employee (SRD-MKT-012.004) | load shipped defaults | emp-010 expert, skill lesson_reflect, trigger after_run | Pass |
| UT-MKT-012.004.M02.T02 | MD-MKT-012.004.M02 | Negative | Unknown skill guard (SRD-MKT-012.004) | SKILL_PATHS without lesson_reflect | emp-010 asleep; others load | Pass |
| UT-MKT-012.005.M03.T01 | MD-MKT-012.005.M03 | Positive | Pick makers get lessons (SRD-MKT-012.005) | one matching active lesson | facts of the four skills end with the block | Pass |
| UT-MKT-012.005.M03.T02 | MD-MKT-012.005.M03 | Negative | Views get none (SRD-MKT-012.005) | same lesson | regime view and sector view facts have no lessons | Pass |
| UT-MKT-012.006.M01.T01 | MD-MKT-012.002.M01 | Positive | Log line (SRD-MKT-012.006) | answer with 1 kept, 1 dropped | `[Memory] Kept 1 candidate lesson(s), dropped 1` | Pass |

## FO-MKT-013: Intraday Watchers and Check-in Notes

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-013.001.M01.T01 | MD-MKT-013.001.M01 | Positive | Today's bars (SRD-MKT-013.001) | UTC bars of today and yesterday | only today's New York bars, oldest first | Pass |
| UT-MKT-013.001.M01.T02 | MD-MKT-013.001.M01 | Negative | Stale feed (SRD-MKT-013.001) | newest bar 20 minutes old above trigger | no flag | Pass |
| UT-MKT-013.002.M01.T01 | MD-MKT-013.001.M01 | Positive | Trigger hit long (SRD-MKT-013.002) | high above trigger | trigger_hit flag | Pass |
| UT-MKT-013.002.M01.T02 | MD-MKT-013.001.M01 | Negative | Below trigger (SRD-MKT-013.002) | high below trigger | no flag | Pass |
| UT-MKT-013.002.M01.T03 | MD-MKT-013.001.M01 | Edge | Short and once a day (SRD-MKT-013.002) | short low below trigger; two passes | one flag | Pass |
| UT-MKT-013.003.M01.T01 | MD-MKT-013.001.M01 | Positive | Stop touch (SRD-MKT-013.003) | long trade, low under stop | stop_touch flag and Trade at stop alert | Pass |
| UT-MKT-013.003.M01.T02 | MD-MKT-013.001.M01 | Positive | Short target touch (SRD-MKT-013.003) | short trade, low under target | target_touch flag and alert | Pass |
| UT-MKT-013.003.M01.T03 | MD-MKT-013.001.M01 | Negative | Inside the range (SRD-MKT-013.003) | price between stop and target | no flag | Pass |
| UT-MKT-013.003.M01.T04 | MD-MKT-013.001.M01 | Edge | No stop set (SRD-MKT-013.003) | open trade with stop 0 | no stop flag | Pass |
| UT-MKT-013.004.M01.T01 | MD-MKT-013.001.M01 | Positive | Volume spike (SRD-MKT-013.004) | last volume 4 times the 20-bar mean | volume_spike flag | Pass |
| UT-MKT-013.004.M01.T02 | MD-MKT-013.001.M01 | Negative | Too few bars (SRD-MKT-013.004) | 10 bars | no flag | Pass |
| UT-MKT-013.005.M01.T01 | MD-MKT-013.001.M01 | Positive | Gap (SRD-MKT-013.005) | first open 4% above previous close | gap flag once | Pass |
| UT-MKT-013.005.M01.T03 | MD-MKT-013.001.M01 | Edge | Needs the open bar (SRD-MKT-013.005) | first bar after 09:36 | no gap flag | Pass |
| UT-MKT-013.005.M01.T02 | MD-MKT-013.001.M01 | Negative | Small gap (SRD-MKT-013.005) | first open 2% above | no flag | Pass |
| UT-MKT-013.006.M01.T01 | MD-MKT-013.001.M01 | Positive | SPY move (SRD-MKT-013.006) | SPY 2% down | regime_move flag | Pass |
| UT-MKT-013.006.M01.T02 | MD-MKT-013.001.M01 | Edge | Once per direction (SRD-MKT-013.006) | down twice, then up | one down flag, one up flag | Pass |
| UT-MKT-013.006.M01.T03 | MD-MKT-013.001.M01 | Negative | Small SPY move (SRD-MKT-013.006) | SPY 1% down | no flag | Pass |
| UT-MKT-013.007.M01.T01 | MD-MKT-013.001.M01 | Positive | New headline (SRD-MKT-013.007) | fake fetch returns an unseen title | headline flag | Pass |
| UT-MKT-013.007.M01.T02 | MD-MKT-013.001.M01 | Negative | Seen or old headline (SRD-MKT-013.007) | title in news_items; title before the open | no flag | Pass |
| UT-MKT-013.007.M01.T03 | MD-MKT-013.001.M01 | Edge | Every 15 minutes (SRD-MKT-013.007) | two passes 5 minutes apart | one fetch | Pass |
| UT-MKT-013.008.M02.T01 | MD-MKT-013.008.M02 | Positive | Flag facts (SRD-MKT-013.008) | open trigger_hit flag | fresh; facts hold the flag, the plan and bars | Pass |
| UT-MKT-013.008.M02.T02 | MD-MKT-013.008.M02 | Negative | No open flag (SRD-MKT-013.008) | all flags answered | not fresh | Pass |
| UT-MKT-013.009.M02.T01 | MD-MKT-013.008.M02 | Positive | Verdict kept (SRD-MKT-013.009) | verdict holds | flag answered; one feed item | Pass |
| UT-MKT-013.009.M02.T02 | MD-MKT-013.008.M02 | Negative | Broken plan (SRD-MKT-013.009) | verdict broken | Plan broken alert | Pass |
| UT-MKT-013.009.M02.T03 | MD-MKT-013.008.M02 | Negative | Bad form (SRD-MKT-013.009) | verdict maybe; note over 300 | schema rejects | Pass |
| UT-MKT-013.009.M02.T04 | MD-MKT-013.008.M02 | Negative | No answer frees the queue (SRD-MKT-013.009) | no valid answer for the oldest of 2 flags | it is closed; the next facts show the newer flag | Pass |
| UT-MKT-013.010.M03.T01 | MD-MKT-013.010.M03 | Positive | Check-in note (SRD-MKT-013.010) | plan, trade, SPY bars, one flag | facts hold all four; brief starts Check-in | Pass |
| UT-MKT-013.010.M03.T02 | MD-MKT-013.010.M03 | Negative | Not a trading day (SRD-MKT-013.010) | Saturday | not fresh | Pass |
| UT-MKT-013.011.M04.T01 | MD-MKT-013.011.M04 | Positive | Default employees (SRD-MKT-013.011) | load shipped defaults | emp-011 expert watch_flag; emp-012 lead checkin_note | Pass |
| UT-MKT-013.011.M04.T02 | MD-MKT-013.011.M04 | Negative | Unknown skill guard (SRD-MKT-013.011) | skill paths without the two keys | both asleep | Pass |
| UT-MKT-013.012.M02.T01 | MD-MKT-013.008.M02 | Positive | Answer log (SRD-MKT-013.012) | verdict watch | `[Watch]` line with stock, kind and verdict | Pass |

## FO-MKT-014: Lead Research Tickets

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-014.001.M01.T01 | MD-MKT-014.001.M01 | Positive | Ticket from the lead plan (SRD-MKT-014.001) | lead brief answer with one ticket | one tickets row; picks and brief kept | Pass |
| UT-MKT-014.001.M01.T02 | MD-MKT-014.001.M01 | Negative | At most 3 (SRD-MKT-014.001) | answer with 4 tickets | answer not valid | Pass |
| UT-MKT-014.001.M02.T01 | MD-MKT-014.001.M02 | Positive | Ticket from a check-in (SRD-MKT-014.001) | check-in answer with one ticket | one tickets row; note kept | Pass |
| UT-MKT-014.002.M01.T01 | MD-MKT-014.001.M01 | Negative | Unknown kind (SRD-MKT-014.002) | ticket kind `guess` | ticket dropped; answer and picks kept | Pass |
| UT-MKT-014.003.M01.T01 | MD-MKT-014.001.M01 | Edge | Cap range (SRD-MKT-014.003) | caps 999, 1,000, 100,000, 100,001 | refused, added, added, refused | Pass |
| UT-MKT-014.004.M01.T01 | MD-MKT-014.001.M01 | Positive | Research block (SRD-MKT-014.004) | lead with 5,000 research tokens used, one open and one ended ticket | facts show 13,000 left, the open ticket and the result | Pass |
| UT-MKT-014.004.M01.T02 | MD-MKT-014.001.M01 | Edge | Block limits (SRD-MKT-014.004) | 40 ended tickets; no roster | block at most 2,400 characters; facts unchanged | Pass |
| UT-MKT-014.005.M01.T01 | MD-MKT-014.001.M01 | Negative | Lead never researches (SRD-MKT-014.005) | answer with one approved ticket | one ask call only; ticket stays approved | Pass |
| UT-MKT-014.002.M01.T02 | MD-MKT-014.001.M01 | Positive | Known kinds (SRD-MKT-014.002) | one ticket of each of the 6 kinds over 2 days | every one added | Pass |
| UT-MKT-014.003.M01.T02 | MD-MKT-014.001.M01 | Positive | Cap inside the range (SRD-MKT-014.003) | cap 5,000 | added with cap 5,000 | Pass |
| UT-MKT-014.005.M01.T02 | MD-MKT-014.001.M01 | Positive | Queue decides (SRD-MKT-014.005) | tickets with caps 8,000 and 30,000 | first approved by auto; second waiting | Pass |
| UT-MKT-014.005.M01.T03 | MD-MKT-014.001.M01 | Negative | Queue error keeps the brief (SRD-MKT-014.005) | tickets table cannot be written | brief and picks kept; error logged | Pass |

## FO-MKT-015: Setup Tuning Research

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-015.001.M01.T01 | MD-MKT-015.001.M01 | Positive | Skill kinds (SRD-MKT-015.001) | skill class | kinds = (`setup_tuning`,); step_tokens set | Pass |
| UT-MKT-015.001.M01.T02 | MD-MKT-015.001.M01 | Negative | Unknown target (SRD-MKT-015.001) | plan target `Moonshot` | outcome failed; note names the target | Pass |
| UT-MKT-015.002.M02.T01 | MD-MKT-015.002.M02 | Positive | Defaults unchanged (SRD-MKT-015.002) | random bars; candidates with no values vs all defaults given | same match, trigger and stop frames | Pass |
| UT-MKT-015.002.M02.T02 | MD-MKT-015.002.M02 | Negative | Range check (SRD-MKT-015.002) | Pullback `near_sma` 1.2; unknown knob `foo` | both changes dropped | Pass |
| UT-MKT-015.002.M02.T03 | MD-MKT-015.002.M02 | Edge | Whole knobs (SRD-MKT-015.002) | `sma_days` 20.6 | kept as 21 | Pass |
| UT-MKT-015.003.M01.T01 | MD-MKT-015.001.M01 | Positive | Pick step (SRD-MKT-015.003) | plan with 3 Pullback variants | state phase run, 3 variants, side long; outcome go | Pass |
| UT-MKT-015.003.M01.T02 | MD-MKT-015.001.M01 | Negative | No valid variant (SRD-MKT-015.003) | all variants out of range | outcome failed | Pass |
| UT-MKT-015.003.M01.T03 | MD-MKT-015.001.M01 | Negative | Too many (SRD-MKT-015.003) | 4 variants, or 3 changes in one | answer not valid | Pass |
| UT-MKT-015.004.M03.T01 | MD-MKT-015.004.M03 | Positive | Replay trade (SRD-MKT-015.004) | match with trigger 101, stop 99, later bar high 106 | one trade, R 2.0, win 1.0 | Pass |
| UT-MKT-015.004.M03.T02 | MD-MKT-015.004.M03 | Edge | Busy stock (SRD-MKT-015.004) | match on 3 days in a row, one fill | one trade only | Pass |
| UT-MKT-015.004.M03.T03 | MD-MKT-015.004.M03 | Negative | No data (SRD-MKT-015.004) | empty Backtest Data folder | `None` | Pass |
| UT-MKT-015.004.M03.T04 | MD-MKT-015.004.M03 | Edge | 5-year window (SRD-MKT-015.004) | 7 years of bars with a match in year 1 | old match not traded | Pass |
| UT-MKT-015.005.M04.T01 | MD-MKT-015.005.M04 | Positive | Strategy knobs and copy (SRD-MKT-015.005) | entry `RSI(14) < 30`, change `entry#2` 35 | copy entry `RSI(14) < 35`, new name, live dict unchanged | Pass |
| UT-MKT-015.005.M04.T02 | MD-MKT-015.005.M04 | Negative | No fixed stop (SRD-MKT-015.005) | stop off; trailing stop | a reason for each | Pass |
| UT-MKT-015.005.M04.T03 | MD-MKT-015.005.M04 | Positive | Stocks (SRD-MKT-015.005) | include list; `all` mode with AI list of 35 incl. 1 unknown | include list; first 30 known | Pass |
| UT-MKT-015.005.M04.T04 | MD-MKT-015.005.M04 | Positive | R per trade (SRD-MKT-015.005) | qty 10, entry 100, stop 2%, net pnl 40 | R 2.0 | Pass |
| UT-MKT-015.005.M04.T05 | MD-MKT-015.005.M04 | Positive | Run not saved (SRD-MKT-015.005) | fake service | record False on both steps; loader gives only the copy | Pass |
| UT-MKT-015.006.M03.T01 | MD-MKT-015.004.M03 | Positive | Result table (SRD-MKT-015.006) | rows base and v1 | text lists trades, win, R and change | Pass |
| UT-MKT-015.006.M03.T02 | MD-MKT-015.004.M03 | Negative | No trades (SRD-MKT-015.006) | variant with no closed trade | row 0 trades, win 0%, +0.00R; no error | Pass |
| UT-MKT-015.007.M03.T01 | MD-MKT-015.004.M03 | Positive | Gain (SRD-MKT-015.007) | base +0.10R, v1 +0.16R on 120 trades | gain v1 | Pass |
| UT-MKT-015.007.M03.T02 | MD-MKT-015.004.M03 | Edge | Gain limits (SRD-MKT-015.007) | +0.04R on 500 trades; +0.20R on 99 trades | no gain both | Pass |
| UT-MKT-015.007.M03.T03 | MD-MKT-015.004.M03 | Negative | No variant or worse (SRD-MKT-015.007) | baseline only; variant below the baseline | no gain both | Pass |
| UT-MKT-015.008.M01.T01 | MD-MKT-015.001.M01 | Positive | Full ticket (SRD-MKT-015.008) | loop of steps, Pullback, fake replay | 5 steps; done; notes hold rows and verdict | Pass |
| UT-MKT-015.008.M01.T02 | MD-MKT-015.001.M01 | Negative | No verdict answer (SRD-MKT-015.008) | ask returns None at verdict | empty note; outcome go | Pass |
| UT-MKT-015.009.M01.T01 | MD-MKT-015.001.M01 | Positive | Candidate lesson (SRD-MKT-015.009) | setup gain | one candidate lesson, tags setup and side, claim worse | Pass |
| UT-MKT-015.009.M01.T02 | MD-MKT-015.001.M01 | Negative | No lesson (SRD-MKT-015.009) | no gain; strategy gain | no lesson rows | Pass |
| UT-MKT-015.010.M01.T01 | MD-MKT-015.001.M01 | Negative | Report only (SRD-MKT-015.010) | strategy ticket with a gain | live strategy dict and knob defaults unchanged | Pass |
| UT-MKT-015.010.M01.T02 | MD-MKT-015.001.M01 | Positive | Winning values named (SRD-MKT-015.010) | desk-setup ticket with a gain | verdict note names v1 and its values; knob defaults unchanged | Pass |
| UT-MKT-015.011.M01.T01 | MD-MKT-015.001.M01 | Positive | Default employee (SRD-MKT-015.011) | shipped emp-013 file, `SKILL_PATHS` | valid file, skill `setup_tuning`, path loads | Pass |
| UT-MKT-015.011.M01.T02 | MD-MKT-015.001.M01 | Negative | Never wakes on events (SRD-MKT-015.011) | `facts()` on a `research_done` event | not fresh; `act` returns no feed items | Pass |
| UT-MKT-015.012.M01.T01 | MD-MKT-015.001.M01 | Positive | Logs (SRD-MKT-015.012) | pick and run steps | `[Research]` lines with target, count and gain | Pass |

## FO-MKT-016: Pick Post-Mortem Research

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-016.001.M01.T01 | MD-MKT-016.001.M01 | Positive | Three steps (SRD-MKT-016.001) | full ticket with fake answers | calls pick, gather, study; outcome done | Pass |
| UT-MKT-016.001.M01.T02 | MD-MKT-016.001.M01 | Negative | No answer (SRD-MKT-016.001) | ask returns None at pick | empty note; outcome go | Pass |
| UT-MKT-016.002.M01.T01 | MD-MKT-016.001.M01 | Positive | Pick list (SRD-MKT-016.002) | closed picks 10 and 40 days old | facts list the 10-day pick only | Pass |
| UT-MKT-016.002.M01.T02 | MD-MKT-016.001.M01 | Edge | List size (SRD-MKT-016.002) | 150 closed picks | 120 shown, newest first | Pass |
| UT-MKT-016.003.M01.T01 | MD-MKT-016.001.M01 | Negative | Bad keys dropped (SRD-MKT-016.003) | unknown key, a winner named as loser | both dropped | Pass |
| UT-MKT-016.003.M01.T02 | MD-MKT-016.001.M01 | Negative | Too few losers (SRD-MKT-016.003) | 1 valid loser | outcome failed | Pass |
| UT-MKT-016.004.M02.T01 | MD-MKT-016.004.M02 | Positive | Record facts (SRD-MKT-016.004) | desk.db with idea, reasons, grade, risk, lead reason, tone, regime, result | one line holding each fact | Pass |
| UT-MKT-016.004.M02.T02 | MD-MKT-016.004.M02 | Negative | Missing tables (SRD-MKT-016.004) | desk.db with pick_results only | line with result; no error | Pass |
| UT-MKT-016.005.M02.T01 | MD-MKT-016.004.M02 | Positive | Price path (SRD-MKT-016.005) | long, trigger 100, stop 98, bars up to 103 and down to 97 | best +1.5R, worst -1.5R, gap and SPY % | Pass |
| UT-MKT-016.005.M02.T02 | MD-MKT-016.004.M02 | Positive | Backtest Data first (SRD-MKT-016.005) | same day in both stores; one day only in candles.db | Backtest Data value kept; missing day filled | Pass |
| UT-MKT-016.005.M02.T03 | MD-MKT-016.004.M02 | Negative | No bars (SRD-MKT-016.005) | symbol in neither store | path shows no bars | Pass |
| UT-MKT-016.006.M01.T01 | MD-MKT-016.001.M01 | Positive | Study answer (SRD-MKT-016.006) | answer with notes, 1 lesson, 1 follow-up, summary | result holds summary and notes | Pass |
| UT-MKT-016.006.M01.T02 | MD-MKT-016.001.M01 | Negative | Answer limits (SRD-MKT-016.006) | 4 lessons; 3 follow-ups; note of 151 characters | answer not valid | Pass |
| UT-MKT-016.007.M01.T01 | MD-MKT-016.001.M01 | Positive | Lesson kept (SRD-MKT-016.007) | lesson whose picks are all studied | one candidate lesson | Pass |
| UT-MKT-016.007.M01.T02 | MD-MKT-016.001.M01 | Negative | Lesson dropped (SRD-MKT-016.007) | lesson naming one unstudied pick | no lesson | Pass |
| UT-MKT-016.008.M01.T01 | MD-MKT-016.001.M01 | Positive | Follow-up (SRD-MKT-016.008) | follow-up setup tuning ask, cap 8,000 | tickets row raised by the ticket's lead, approved | Pass |
| UT-MKT-016.008.M01.T02 | MD-MKT-016.001.M01 | Negative | Follow-up refused (SRD-MKT-016.008) | lead already raised 3 tickets today | refusal in the result; ticket still done | Pass |
| UT-MKT-016.009.M01.T01 | MD-MKT-016.001.M01 | Positive | Gain yes (SRD-MKT-016.009) | one lesson kept | gain True | Pass |
| UT-MKT-016.009.M01.T02 | MD-MKT-016.001.M01 | Negative | Gain no (SRD-MKT-016.009) | no lesson kept | gain False; outcome done | Pass |
| UT-MKT-016.010.M01.T01 | MD-MKT-016.001.M01 | Positive | Default employee (SRD-MKT-016.010) | shipped emp-014 file, `SKILL_PATHS` | valid file, skill `post_mortem`, path loads | Pass |
| UT-MKT-016.010.M01.T02 | MD-MKT-016.001.M01 | Negative | Never wakes (SRD-MKT-016.010) | `facts()` on an event | not fresh; `act` returns no items | Pass |
| UT-MKT-016.011.M01.T01 | MD-MKT-016.001.M01 | Positive | Logs (SRD-MKT-016.011) | full ticket | `[Research]` lines with pick count, lessons and follow-ups | Pass |

## FO-MKT-017: Sentiment Research

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-017.001.M01.T01 | MD-MKT-017.001.M01 | Positive | Three steps (SRD-MKT-017.001) | full ticket with fake answers | calls pick, gather, judge; outcome done | Pass |
| UT-MKT-017.001.M01.T02 | MD-MKT-017.001.M01 | Negative | No answer (SRD-MKT-017.001) | ask returns None at pick | empty note; outcome go | Pass |
| UT-MKT-017.002.M01.T01 | MD-MKT-017.001.M01 | Positive | Pick list (SRD-MKT-017.002) | listed, watch and none ideas on the latest day, an older day, one open trade | facts list listed, watch and the trade only | Pass |
| UT-MKT-017.002.M01.T02 | MD-MKT-017.001.M01 | Negative | Too many (SRD-MKT-017.002) | 31 stocks | answer not valid | Pass |
| UT-MKT-017.003.M01.T01 | MD-MKT-017.001.M01 | Positive | Unknown stocks (SRD-MKT-017.003) | one known, one unknown | only the known kept | Pass |
| UT-MKT-017.003.M01.T02 | MD-MKT-017.001.M01 | Negative | Nothing left (SRD-MKT-017.003) | only unknown; no ideas or trades | outcome failed both | Pass |
| UT-MKT-017.004.M02.T01 | MD-MKT-017.004.M02 | Positive | Stored first (SRD-MKT-017.004) | stock with a headline from yesterday | no fetch; record holds it | Pass |
| UT-MKT-017.004.M02.T02 | MD-MKT-017.004.M02 | Positive | Gap fetched and stored (SRD-MKT-017.004) | stock with only a 5-day-old headline; fake feed with 2 new | one fetch; 2 rows added; record has 3 | Pass |
| UT-MKT-017.004.M02.T03 | MD-MKT-017.004.M02 | Edge | Limits (SRD-MKT-017.004) | 8 stored headlines; one 9 days old; budget used up | 5 newest shown; old one left out; no fetch after budget | Pass |
| UT-MKT-017.004.M02.T04 | MD-MKT-017.004.M02 | Negative | Feed fails (SRD-MKT-017.004) | fake feed returns None | record shows no news; no error | Pass |
| UT-MKT-017.005.M01.T01 | MD-MKT-017.001.M01 | Negative | Answer limits (SRD-MKT-017.005) | tone `bullish`; reason of 151 characters | answer not valid | Pass |
| UT-MKT-017.005.M01.T02 | MD-MKT-017.001.M01 | Positive | All tones (SRD-MKT-017.005) | cards with supports, neutral, against and none | all four kept | Pass |
| UT-MKT-017.006.M03.T01 | MD-MKT-017.006.M03 | Positive | Cards saved (SRD-MKT-017.006) | judge answer with 2 known stocks | 2 rows with tone, reason, headline count, ticket id | Pass |
| UT-MKT-017.006.M03.T02 | MD-MKT-017.006.M03 | Negative | Unknown and scores (SRD-MKT-017.006) | card for an unchosen stock; news_tags row | card dropped; news_tags unchanged | Pass |
| UT-MKT-017.007.M03.T01 | MD-MKT-017.006.M03 | Positive | Lead sees cards (SRD-MKT-017.007) | card 2 days old for a passed idea | lead facts hold the card line | Pass |
| UT-MKT-017.007.M03.T02 | MD-MKT-017.006.M03 | Edge | Card limits (SRD-MKT-017.007) | 10-day-old card; two cards for one stock; 35 stocks | old one left out; newest only; 30 lines | Pass |
| UT-MKT-017.007.M03.T03 | MD-MKT-017.006.M03 | Negative | No cards (SRD-MKT-017.007) | no card table; cards only for other stocks | block empty; lead facts unchanged | Pass |
| UT-MKT-017.008.M01.T01 | MD-MKT-017.001.M01 | Positive | Gain yes (SRD-MKT-017.008) | one card against | gain True; result lists tones and summary | Pass |
| UT-MKT-017.008.M01.T02 | MD-MKT-017.001.M01 | Negative | Gain no (SRD-MKT-017.008) | supports and neutral only | gain False; outcome done | Pass |
| UT-MKT-017.009.M01.T01 | MD-MKT-017.001.M01 | Positive | Default employee (SRD-MKT-017.009) | shipped emp-015 file, `SKILL_PATHS` | valid file, skill `sentiment`, path loads | Pass |
| UT-MKT-017.009.M01.T02 | MD-MKT-017.001.M01 | Negative | Never wakes (SRD-MKT-017.009) | `facts()` on an event | not fresh; `act` returns no items | Pass |
| UT-MKT-017.010.M01.T01 | MD-MKT-017.001.M01 | Positive | Logs (SRD-MKT-017.010) | full ticket | `[Research]` lines with stock count, fetched count and against count | Pass |

## FO-MKT-018: Book to Strategy Research

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-018.001.M01.T01 | MD-MKT-018.001.M01 | Positive | Two steps (SRD-MKT-018.001) | upload ticket, fake card answer | calls read, card; outcome done | Pass |
| UT-MKT-018.001.M01.T02 | MD-MKT-018.001.M01 | Negative | No answer (SRD-MKT-018.001) | ask returns None at card | empty note; outcome go | Pass |
| UT-MKT-018.002.M02.T01 | MD-MKT-018.002.M02 | Positive | Topic forms (SRD-MKT-018.002) | `upload:My Book.pdf ch 3`, `gutenberg:12345 ch 1` | both parsed with source and chapter | Pass |
| UT-MKT-018.002.M02.T02 | MD-MKT-018.002.M02 | Negative | Bad topics (SRD-MKT-018.002) | `https://x.com/b.pdf ch 1`, `upload:../a.txt ch 1`, `upload:a.exe ch 1`, `Read chapter 2` | none parsed; ticket failed with no read | Pass |
| UT-MKT-018.003.M02.T01 | MD-MKT-018.002.M02 | Positive | Gutenberg once (SRD-MKT-018.003) | fake getter; two loads of the same number | one GET to the gutenberg.org URL; cache file kept; header and footer cut | Pass |
| UT-MKT-018.003.M02.T02 | MD-MKT-018.002.M02 | Negative | Missing or failed (SRD-MKT-018.003) | upload file not in folder; getter raises | `failed` both; no other URL called | Pass |
| UT-MKT-018.004.M02.T01 | MD-MKT-018.002.M02 | Positive | Readers (SRD-MKT-018.004) | `.txt`, `.md`, `.html` with a script tag, a small `.pdf` | plain text of each; script text left out | Pass |
| UT-MKT-018.004.M02.T02 | MD-MKT-018.002.M02 | Negative | Bad PDF (SRD-MKT-018.004) | file named `.pdf` that is not a PDF | `failed`; no error raised | Pass |
| UT-MKT-018.005.M02.T01 | MD-MKT-018.002.M02 | Positive | Headings (SRD-MKT-018.005) | text with CHAPTER I, CHAPTER II, CHAPTER III | chapter 2 is the middle part | Pass |
| UT-MKT-018.005.M02.T02 | MD-MKT-018.002.M02 | Edge | No headings, cut (SRD-MKT-018.005) | 12,000 words with no heading; very long chapter | 3 parts of up to 5,000 words; text cut to 24,000 characters | Pass |
| UT-MKT-018.005.M02.T03 | MD-MKT-018.002.M02 | Negative | Missing chapter (SRD-MKT-018.005) | chapter 9 of a 3-chapter book | `failed` naming the chapter count | Pass |
| UT-MKT-018.006.M03.T01 | MD-MKT-018.006.M03 | Negative | Never re-read (SRD-MKT-018.006) | second ticket for a read chapter | `failed` naming the card; file not opened | Pass |
| UT-MKT-018.006.M03.T02 | MD-MKT-018.006.M03 | Positive | Other chapter allowed (SRD-MKT-018.006) | chapter 2 read; ticket for chapter 3 | read goes ahead | Pass |
| UT-MKT-018.007.M01.T01 | MD-MKT-018.001.M01 | Negative | Answer limits (SRD-MKT-018.007) | 4 quotes; entry of 301 characters; no quote | answer not valid | Pass |
| UT-MKT-018.008.M01.T01 | MD-MKT-018.001.M01 | Positive | Quotes checked (SRD-MKT-018.008) | 3 quotes, one with other spacing and curly quotes, one made up | 2 kept; card row and books_read row saved | Pass |
| UT-MKT-018.008.M01.T02 | MD-MKT-018.001.M01 | Negative | No quote found (SRD-MKT-018.008) | only made-up quotes | card saved with no quotes; chapter marked read | Pass |
| UT-MKT-018.009.M01.T01 | MD-MKT-018.001.M01 | Positive | Gain yes (SRD-MKT-018.009) | entry, exit, stop and a found quote | gain True; result holds the card | Pass |
| UT-MKT-018.009.M01.T02 | MD-MKT-018.001.M01 | Negative | Gain no (SRD-MKT-018.009) | blank stop | gain False; outcome done | Pass |
| UT-MKT-018.010.M03.T01 | MD-MKT-018.006.M03 | Positive | Lead books block (SRD-MKT-018.010) | 2 uploads, 1 chapter read; lead facts | block lists both files, the topic form and the read chapter | Pass |
| UT-MKT-018.010.M03.T02 | MD-MKT-018.006.M03 | Negative | Empty and limits (SRD-MKT-018.010) | no books folder; 20 uploads | "No uploaded books yet"; at most 15 lines | Pass |
| UT-MKT-018.011.M01.T01 | MD-MKT-018.001.M01 | Positive | Default employee (SRD-MKT-018.011) | shipped emp-016 file, `SKILL_PATHS` | valid file, skill `book_to_strategy`, path loads | Pass |
| UT-MKT-018.011.M01.T02 | MD-MKT-018.001.M01 | Negative | Never wakes (SRD-MKT-018.011) | `facts()` on an event | not fresh; `act` returns no items | Pass |
| UT-MKT-018.012.M01.T01 | MD-MKT-018.001.M01 | Positive | Logs (SRD-MKT-018.012) | full ticket | `[Research]` lines with book, chapter, words and quotes kept | Pass |

## FO-MKT-019: Strategy Test Research

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-019.001.M01.T01 | MD-MKT-019.001.M01 | Positive | Four steps (SRD-MKT-019.001) | card SC-1, fake recipe and verdict answers, small fake data | calls recipe, check, replay, verdict; outcome done | Pass |
| UT-MKT-019.001.M01.T02 | MD-MKT-019.001.M01 | Negative | No answer (SRD-MKT-019.001) | ask returns None at recipe | empty note; outcome go | Pass |
| UT-MKT-019.002.M01.T01 | MD-MKT-019.001.M01 | Negative | Missing card (SRD-MKT-019.002) | topic SC-99; topic hello | failed before any AI call | Pass |
| UT-MKT-019.003.M02.T01 | MD-MKT-019.003.M02 | Positive | Block menu (SRD-MKT-019.003) | block_menu() | lists rsi and bull_flag; no rvol_3m, market_cap or rs_index | Pass |
| UT-MKT-019.004.M02.T01 | MD-MKT-019.003.M02 | Positive | Good recipe (SRD-MKT-019.004) | rsi at most 30, hammer, next open, ATR 2 | no problems | Pass |
| UT-MKT-019.004.M02.T02 | MD-MKT-019.003.M02 | Negative | Unmapped part (SRD-MKT-019.004) | unmapped ["earnings date"] | earnings date has no block | Pass |
| UT-MKT-019.004.M02.T03 | MD-MKT-019.003.M02 | Negative | Unknown or intraday block (SRD-MKT-019.004) | id moon_phase; id rvol_3m | both named as no block | Pass |
| UT-MKT-019.004.M02.T04 | MD-MKT-019.003.M02 | Negative | Out of range (SRD-MKT-019.004) | rsi value 150; ATR stop n 9; no entry block | three problems named | Pass |
| UT-MKT-019.004.M01.T01 | MD-MKT-019.001.M01 | Negative | Can't test ends the ticket (SRD-MKT-019.004) | recipe with an unmapped part | failed, "can't test" note; cant_test row; no replay | Pass |
| UT-MKT-019.005.M03.T01 | MD-MKT-019.005.M03 | Positive | Replay trade (SRD-MKT-019.005) | one stock, a signal then a rise to 2R | one trade with +2R; entry and exit days right | Pass |
| UT-MKT-019.005.M03.T02 | MD-MKT-019.005.M03 | Edge | One trade per stock (SRD-MKT-019.005) | signals on 3 days in a row | one trade until its exit | Pass |
| UT-MKT-019.005.M03.T03 | MD-MKT-019.005.M03 | Positive | Entry and stop types (SRD-MKT-019.005) | next open vs signal break; signal bar, n-day, ATR, percent stops | triggers and stops as designed | Pass |
| UT-MKT-019.006.M03.T01 | MD-MKT-019.005.M03 | Positive | Baseline sample (SRD-MKT-019.006) | same data twice | same baseline trades and R | Pass |
| UT-MKT-019.007.M03.T01 | MD-MKT-019.005.M03 | Positive | Pass rule (SRD-MKT-019.007) | 30 trades +0.25R vs base 0.0 | pass | Pass |
| UT-MKT-019.007.M03.T02 | MD-MKT-019.005.M03 | Negative | Fail cases (SRD-MKT-019.007) | 29 trades +0.5R; 40 trades +0.2R; 40 trades +0.3R vs base +0.35R | fail each | Pass |
| UT-MKT-019.007.M03.T03 | MD-MKT-019.005.M03 | Edge | Worst run (SRD-MKT-019.007) | R -1, -1, +2, -1, -1, -1 | worst run 3; win rate 1 of 6 | Pass |
| UT-MKT-019.008.M01.T01 | MD-MKT-019.001.M01 | Positive | Verdict lines (SRD-MKT-019.008) | fake verdict answer | note holds the table, pass line and verdict | Pass |
| UT-MKT-019.009.M04.T01 | MD-MKT-019.009.M04 | Positive | Save and latest (SRD-MKT-019.009) | two tests of SC-1 | latest_tests gives the second | Pass |
| UT-MKT-019.009.M01.T01 | MD-MKT-019.001.M01 | Positive | Gain on pass (SRD-MKT-019.009) | passing fake score | gain yes; card_tests row pass | Pass |
| UT-MKT-019.009.M01.T02 | MD-MKT-019.001.M01 | Negative | No gain on fail (SRD-MKT-019.009) | failing fake score | gain no; row fail; no lesson | Pass |
| UT-MKT-019.010.M01.T01 | MD-MKT-019.001.M01 | Positive | Lesson on pass (SRD-MKT-019.010) | passing fake score | one candidate lesson naming SC-1 | Pass |
| UT-MKT-019.011.M04.T01 | MD-MKT-019.009.M04 | Positive | Untested block (SRD-MKT-019.011) | 12 cards, 1 tested | at most 8 lines; topic form; tested card left out | Pass |
| UT-MKT-019.011.M04.T02 | MD-MKT-019.009.M04 | Edge | Open tests (SRD-MKT-019.011) | approved ticket SC-2; done ticket SC-3 | open_test_cards is {2} | Pass |
| UT-MKT-019.012.M05.T01 | MD-MKT-019.012.M05 | Positive | Default employee (SRD-MKT-019.012) | emp-017 file, SKILL_PATHS, USSwing.spec | skill strategy_test; path loads; spec lists the module | Pass |
| UT-MKT-019.013.M01.T01 | MD-MKT-019.001.M01 | Negative | Never live (SRD-MKT-019.013) | full ticket run | strategies file and settings unchanged | Pass |
| UT-MKT-019.014.M01.T01 | MD-MKT-019.001.M01 | Positive | Logs (SRD-MKT-019.014) | full ticket run | `[Research]` lines with ticket and card | Pass |
| UT-MKT-019.002.M04.T01 | MD-MKT-019.009.M04 | Positive | Card from topic (SRD-MKT-019.002) | topic sc-12; card 12 saved | card id 12; card row found | Pass |
| UT-MKT-019.003.M02.T02 | MD-MKT-019.003.M02 | Negative | Bad recipe answer (SRD-MKT-019.003) | side both; extra field; 5 indicators | answer refused by the model check | Pass |
| UT-MKT-019.005.M03.T04 | MD-MKT-019.005.M03 | Negative | No Backtest Data (SRD-MKT-019.005) | empty data folder | no data; ticket failed with a plain note | Pass |
| UT-MKT-019.006.M03.T02 | MD-MKT-019.005.M03 | Negative | Baseline skips bad levels (SRD-MKT-019.006) | percent stop on a day where the stop is past the trigger | that day gives no baseline trade | Pass |
| UT-MKT-019.008.M01.T02 | MD-MKT-019.001.M01 | Negative | No verdict answer (SRD-MKT-019.008) | ask returns None at verdict | outcome go; no card_tests row yet | Pass |
| UT-MKT-019.011.M04.T03 | MD-MKT-019.009.M04 | Negative | No cards (SRD-MKT-019.011) | no desk.db; all cards tested | empty block | Pass |
| UT-MKT-019.012.M05.T02 | MD-MKT-019.012.M05 | Negative | No hardcoded name (SRD-MKT-019.012) | skill source | no employee name or title in code | Pass |
| UT-MKT-019.013.M01.T02 | MD-MKT-019.001.M01 | Positive | Report only (SRD-MKT-019.013) | full ticket run | only card_tests and lessons gain rows | Pass |
| UT-MKT-019.005.M03.T05 | MD-MKT-019.005.M03 | Edge | Time limit (SRD-MKT-019.005) | replay with a limit already passed | stops; ticket fails with a plain note | Pass |
| UT-MKT-019.011.M04.T04 | MD-MKT-019.009.M04 | Positive | Test cap hint (SRD-MKT-019.011) | untested block header; owner ticket cap | says token cap 20000; owner cap 20,000 | Pass |

## FO-MKT-005 / FO-MKT-006 (AI Desk v3 M1): Asks, Send-Back Fixes and News Replies

| ID | Module | Type | Title | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-MKT-005.019.M05.T01 | MD-MKT-005.009.M05 | Positive | Held idea graded after the reply (SRD-MKT-005.019) | grades for 3 ideas and an ask about NVDA; then inbox wake with the reply grading NVDA | 3 rows, no NVDA; then 4 rows, others unchanged | Pass |
| UT-MKT-005.019.M05.T02 | MD-MKT-005.009.M05 | Negative | More than 3 asked (SRD-MKT-005.019) | asks naming 5 ideas | asks for the first 3 kept; the rest dropped and logged | Pass |
| UT-MKT-005.019.M05.T03 | MD-MKT-005.009.M05 | Negative | Messages off (SRD-MKT-005.019) | fake context without talk | grades stored as today; no drafts | Pass |
| UT-MKT-005.020.M07.T01 | MD-MKT-005.012.M07 | Positive | Stop sent back (SRD-MKT-005.020) | AMD long stop 11.4% | send_back to skill:setup_review with the reason; AMD row stays veto by code | Pass |
| UT-MKT-005.020.M07.T02 | MD-MKT-005.012.M07 | Negative | Other vetoes final (SRD-MKT-005.020) | long in a Downtrend; trigger $3; fourth in its sector | no send_back | Pass |
| UT-MKT-005.021.M05.T01 | MD-MKT-005.009.M05 | Positive | Fix reply (SRD-MKT-005.021) | inbox send_back about AMD; model replies with idea_fix.v1 row | reply draft with the row; grades merged | Pass |
| UT-MKT-005.021.M05.T02 | MD-MKT-005.009.M05 | Negative | Dropped idea (SRD-MKT-005.021) | model replies dropped with a reason | reply draft with verdict dropped | Pass |
| UT-MKT-005.022.M07.T01 | MD-MKT-005.012.M07 | Positive | Fix passes (SRD-MKT-005.022) | fix reply AMD stop 7.7% | idea_fixes pass; risk_check AMD pass by code, fixed in round 1; no AI call | Pass |
| UT-MKT-005.022.M07.T02 | MD-MKT-005.012.M07 | Negative | Still over in round 1 (SRD-MKT-005.022) | fix stop 10.5% | fix fail; round-2 send_back with parent the reply | Pass |
| UT-MKT-005.022.M07.T03 | MD-MKT-005.012.M07 | Edge | Still over after round 2 (SRD-MKT-005.022) | round-2 fix still over | stays veto, still over after 2 rounds; no third send_back | Pass |
| UT-MKT-005.022.M07.T04 | MD-MKT-005.012.M07 | Negative | Wrong idea in the fix (SRD-MKT-005.022) | fix row for MSFT on AMD's send_back | ignored and logged; AMD stays vetoed | Pass |
| UT-MKT-005.022.M07.T05 | MD-MKT-005.012.M07 | Positive | Fix loop in one run (SRD-MKT-005.022) | desk copy, messages on, AMD stop 11.4%, setup review fixes to 7.7% | lead brief runs after; AMD passed with the new levels | Pass |
| UT-MKT-005.023.M04.T01 | MD-MKT-001.007.M04 | Positive | Fixed levels used (SRD-MKT-005.023) | passing fix for AMD | listed_frame, watcher ideas and watch flag plan text show the new trigger and stop | Pass |
| UT-MKT-005.023.M04.T02 | MD-MKT-001.007.M04 | Negative | Failed or pending fix not used (SRD-MKT-005.023) | fix status fail; pending | old levels everywhere | Pass |
| UT-MKT-006.013.M04.T01 | MD-MKT-006.005.M04 | Positive | News reply only (SRD-MKT-006.013) | inbox ask about NVDA; model returns one reply | reply draft; news_tags rows and feed unchanged | Pass |
| UT-MKT-006.013.M04.T02 | MD-MKT-006.005.M04 | Negative | Normal wake unchanged (SRD-MKT-006.013) | wake without inbox | tags stored and market note posted as today | Pass |
| UT-MKT-005.024.M05.T01 | MD-MKT-005.009.M05 | Positive | Price facts for a send-back (SRD-MKT-005.024) | send-back about a stock with daily bars | facts show last close, ATR(14), 20-day low | Pass |
| UT-MKT-005.024.M05.T02 | MD-MKT-005.009.M05 | Negative | No send-back, no price facts (SRD-MKT-005.024) | inbox with only an ask | no price facts in the facts | Pass |

## FO-MKT-013 (AI Desk v3 M2): Flag Escalation

| ID | Module | Type | Title | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-MKT-013.013.M02.T01 | MD-MKT-013.008.M02 | Positive | Broken plan escalates (SRD-MKT-013.013) | talking context, verdict broken on AAPL | one escalate to boss about AAPL with the note; alert raised as before | Not Run |
| UT-MKT-013.013.M02.T02 | MD-MKT-013.008.M02 | Positive | Stop touch escalates (SRD-MKT-013.013) | stop_touch flag, no valid answer | one escalate to boss | Not Run |
| UT-MKT-013.013.M02.T03 | MD-MKT-013.008.M02 | Negative | No escalate (SRD-MKT-013.013) | trigger_hit with verdict holds; plain fake context | no draft sent | Not Run |
