# Unit Test Case Document — Backtest Module (BKT)

**Document ID:** UTCD-BKT
**Version:** 1.1.0
**Traces To:** MD-BKT v1.1.0
**Status:** Draft
**Last Updated:** 2026-10-29
**Project:** US Swing Trading System

> v1.1.0: UT-BKT-002.* added — engine Phase 0 and 1.
> v1.0.0: UT-BKT-001.* added — store, settings, planner, downloader (fake IB), schedule.

---

## FO-BKT-001 — Backtest Data Store and Downloader

| UT ID | MD | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-BKT-001.001.M01.T01 | MD-BKT-001.001.M01 | Positive | 3m bars split by year | bars over 2024-12-31 and 2025-01-02 | files `3m/AAPL/2024` and `2025`; read returns all rows in order | Pass |
| UT-BKT-001.001.M01.T02 | MD-BKT-001.001.M01 | Negative | Unknown stock reads empty | no files for ZZZZ | empty frame; coverage None; no file created | Pass |
| UT-BKT-001.002.M01.T01 | MD-BKT-001.001.M01 | Positive | Overlap merge keeps one row per timestamp | save, then save overlapping rows with new close | no duplicate ts; new close kept | Pass |
| UT-BKT-001.002.M01.T02 | MD-BKT-001.001.M01 | Negative | Failed write keeps old file | write raises mid-save | old file still readable; no `.tmp` left | Pass |
| UT-BKT-001.003.M01.T01 | MD-BKT-001.001.M01 | Negative | Unfinished day dropped | today's bars, now 14:00 ET | today's rows not saved | Pass |
| UT-BKT-001.003.M01.T02 | MD-BKT-001.001.M01 | Positive | Finished day kept | today's bars, now 16:20 ET | today's rows saved | Pass |
| UT-BKT-001.005.M01.T01 | MD-BKT-001.001.M01 | Negative | Bars before job start dropped | 1d and 3m bars from 2025, start 2026-01-01 | only 2026 rows saved; no `3m/AAPL/2025` file | Pass |
| UT-BKT-001.010.M01.T01 | MD-BKT-001.001.M01 | Positive | Clear keeps settings | store with data, settings and a `candles.db` beside it | data and state gone; `settings.json` and `candles.db` kept | Pass |
| UT-BKT-001.010.M01.T02 | MD-BKT-001.001.M01 | Negative | Clear on empty store is safe | empty root with `settings.json` only | no error; `settings.json` unchanged | Pass |
| UT-BKT-001.011.M01.T01 | MD-BKT-001.001.M01 | Positive | Stats from metadata | 2 stocks saved | stock count 2; bar counts, first/last date and size match | Pass |
| UT-BKT-001.011.M01.T02 | MD-BKT-001.001.M01 | Edge | 3m complete-from date | 3 stocks, one listed later with a floor | first_3m is the latest start of the other two | Pass |
| UT-BKT-001.012.M01.T01 | MD-BKT-001.001.M01 | Positive | 15m built on 3m save | one session of 130 3m bars | 26 15m bars 09:30–15:45 ET; first bar OHLCV from bars 1–5 | Pass |
| UT-BKT-001.012.M01.T02 | MD-BKT-001.001.M01 | Edge | Summer time and gaps | a winter and a summer session, 2 summer bars missing | 52 bars; buckets start 09:30 ET both; short bucket volume from 3 bars | Pass |
| UT-BKT-001.013.M01.T01 | MD-BKT-001.001.M01 | Positive | 1w built on 1d save | 2 weeks, Thanksgiving week has 4 days | weeks dated 11-17 and 11-24; days 5 and 4; close, high, volume match | Pass |
| UT-BKT-001.013.M01.T02 | MD-BKT-001.001.M01 | Edge | Unfinished week grows | Mon–Tue saved, then Wed | days 2, then 3; close from Wed | Pass |
| UT-BKT-001.014.M01.T01 | MD-BKT-001.001.M01 | Positive | Build for old data | 2 stocks with 15m/1w folders deleted | returns 2; files back; second call returns 0 | Pass |
| UT-BKT-001.014.M01.T02 | MD-BKT-001.001.M01 | Negative | Only stale files rebuilt | AAPL 15m older than its 3m file, MSFT current | returns 1; AAPL rebuilt; MSFT file untouched | Pass |
| UT-BKT-001.004.M02.T01 | MD-BKT-001.004.M02 | Positive | Settings round trip | save custom settings, load | values equal | Pass |
| UT-BKT-001.004.M02.T02 | MD-BKT-001.004.M02 | Negative | Broken file loads defaults | `settings.json` with bad JSON | defaults 2016-01-01, latest, on, 17:30, Mon–Fri | Pass |
| UT-BKT-001.005.M03.T01 | MD-BKT-001.005.M03 | Positive | Empty store plan | 2 stocks, 2025-01-01 to 2025-12-31 | 2 1d jobs first; 3m jobs newest end first across both stocks | Pass |
| UT-BKT-001.005.M03.T02 | MD-BKT-001.005.M03 | Negative | Fully saved store has no jobs | coverage equals range | empty plan | Pass |
| UT-BKT-001.005.M03.T03 | MD-BKT-001.005.M03 | Edge | Earlier start back-fills only older windows | saved 2024–2025, start moved to 2023 | 3m jobs only for 2023 windows; one 1d back-fill job | Pass |
| UT-BKT-001.005.M03.T04 | MD-BKT-001.005.M03 | Edge | Floor skips windows before first data | floor 2024-06-01 | no 3m job ending before the floor | Pass |
| UT-BKT-001.008.M03.T01 | MD-BKT-001.005.M03 | Positive | Delta asks days since last bar | last saved 3 trading days ago, `delta_only` | one job per stock and tf, duration "4 D" | Pass |
| UT-BKT-001.008.M03.T02 | MD-BKT-001.005.M03 | Edge | Delta skips up-to-date stock | AAPL saved to last session, MSFT one day behind | no AAPL job; MSFT "2 D" for 1d and 3m | Pass |
| UT-BKT-001.008.M03.T03 | MD-BKT-001.005.M03 | Negative | No delta with fixed end date | end date 2025-12-31, `delta_only` | empty plan | Pass |
| UT-BKT-001.006.M04.T01 | MD-BKT-001.006.M04 | Positive | Jobs saved with progress | fake IB returns bars for 2 jobs | both saved; progress emitted 1/2, 2/2; returns ok | Pass |
| UT-BKT-001.006.M04.T02 | MD-BKT-001.006.M04 | Negative | Retry then mark failed | fake IB times out every time for AAPL | 3 tries; AAPL in failed; MSFT jobs still run | Pass |
| UT-BKT-001.006.M04.T03 | MD-BKT-001.006.M04 | Edge | Empty window sets floor | 3m window returns no bars, newer data saved | floor set to window end | Pass |
| UT-BKT-001.006.M04.T04 | MD-BKT-001.006.M04 | Negative | Slow empty answer is a timeout | ib_insync times out and returns no bars | retried 3 times, marked failed, no floor | Pass |
| UT-BKT-001.007.M04.T01 | MD-BKT-001.006.M04 | Positive | Stop ends after current job | stop requested during job 1 of 3 | job 1 saved; jobs 2–3 not requested | Pass |
| UT-BKT-001.007.M04.T02 | MD-BKT-001.006.M04 | Negative | Stopped run is not reported complete | stop requested during job 1 of 3 | returns ok False with message "Stopped" | Pass |
| UT-BKT-001.009.M05.T01 | MD-BKT-001.009.M05 | Positive | Due after run time | Tue 17:31 ET, last delta Mon 17:35 | due | Pass |
| UT-BKT-001.009.M05.T02 | MD-BKT-001.009.M05 | Negative | Not due before run time | Tue 17:00 ET, last delta Mon 17:35 | not due | Pass |
| UT-BKT-001.009.M05.T03 | MD-BKT-001.009.M05 | Edge | Missed Friday caught up on Monday morning | Mon 09:00 ET, last delta Thu 17:35 | due | Pass |
| UT-BKT-001.009.M05.T04 | MD-BKT-001.009.M05 | Negative | Off when fixed end date | end date set, Tue 17:31 ET | not due | Pass |

## FO-BKT-002 — Backtest Engine (Phase 0 and 1)

| UT ID | MD | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-BKT-002.001.M01.T01 | MD-BKT-002.001.M01 | Positive | Plan JSON round trip | Engine_plan §4 example | loaded plan equals saved; capital list kept, single values written as numbers | Pass |
| UT-BKT-002.001.M01.T02 | MD-BKT-002.001.M01 | Negative | Unknown keys and missing parts | JSON with extra key and no `costs` | loads; defaults used | Pass |
| UT-BKT-002.002.M01.T01 | MD-BKT-002.001.M01 | Positive | Good plan is valid | example plan | no messages | Pass |
| UT-BKT-002.002.M01.T02 | MD-BKT-002.001.M01 | Negative | Bad values listed | start after end, sector mode with no sectors, capital 0, schema 2 | 4 plain messages | Pass |
| UT-BKT-002.003.M01.T01 | MD-BKT-002.001.M01 | Positive | Variant grid | capital [2000, 5000], one strategy per-trade [50, 100] | 4 variants in order | Pass |
| UT-BKT-002.003.M01.T02 | MD-BKT-002.001.M01 | Negative | Over 64 variants | capital list of 65 values | validation message about 64 | Pass |
| UT-BKT-002.004.M02.T01 | MD-BKT-002.004.M02 | Positive | Each mode resolves | 4 records in 2 sectors; sp500, sector, names | 4; sector's 2; given names | Pass |
| UT-BKT-002.004.M02.T02 | MD-BKT-002.004.M02 | Negative | Add and remove | sector mode, add PLTR, remove one sector stock, duplicate add | sorted unique; removed stock absent | Pass |
| UT-BKT-002.005.M03.T01 | MD-BKT-002.005.M03 | Positive | Write then read | frame under a key | read equals frame; key stable for same params in other order | Pass |
| UT-BKT-002.005.M03.T02 | MD-BKT-002.005.M03 | Negative | Miss and failed write | unknown key; write raises mid-save | `None`; no file and no temp left | Pass |
| UT-BKT-002.006.M03.T01 | MD-BKT-002.005.M03 | Positive | Cleanup by age and size | one old file, three new files over the limit | old file gone, then oldest new file gone; bytes freed returned | Pass |
| UT-BKT-002.007.M04.T01 | MD-BKT-002.007.M04 | Positive | Run row life | start, finish done | row has plan, status done, both times | Pass |
| UT-BKT-002.007.M04.T02 | MD-BKT-002.007.M04 | Negative | Unknown run | `get_run("x")` | `None` | Pass |
| UT-BKT-002.008.M05.T01 | MD-BKT-002.008.M05 | Positive | Estimate on a fake store | 3 stocks, one with no 3m, SPY saved | symbols 3; missing_3m 1; benchmark ok; days counted | Pass |
| UT-BKT-002.008.M05.T02 | MD-BKT-002.008.M05 | Negative | Estimate with errors | plan with start after end | errors listed; day counts 0 | Pass |
| UT-BKT-002.009.M06.T01 | MD-BKT-002.009.M06 | Positive | CLI estimate | plan file, fake service | exit 0; stock count printed | Pass |
| UT-BKT-002.010.M07.T01 | MD-BKT-002.010.M07 | Positive | Days from SPY | SPY and AAPL saved, period inside | SPY dates in the period | Pass |
| UT-BKT-002.010.M07.T02 | MD-BKT-002.010.M07 | Negative | No SPY | only AAPL and MSFT saved | union of their dates | Pass |
| UT-BKT-002.011.M07.T01 | MD-BKT-002.010.M07 | Positive | Replay equals live screener | preset "close above EMA 20" over 3 stocks, one day | same passed and score as `PresetExecutor.screen()` on bars up to that day | Pass |
| UT-BKT-002.011.M07.T02 | MD-BKT-002.010.M07 | Negative | No look-ahead | stock jumps the day after D | D result uses no bar after D | Pass |
| UT-BKT-002.012.M07.T01 | MD-BKT-002.010.M07 | Positive | One file per day | 5-day run | 5 day files under one key | Pass |
| UT-BKT-002.012.M07.T02 | MD-BKT-002.010.M07 | Negative | Rules change gives new key | change rule period | different key; nothing reused | Pass |
| UT-BKT-002.013.M07.T01 | MD-BKT-002.010.M07 | Positive | Second run computes nothing | run twice; second with other top N | second run progress total 0 | Pass |
| UT-BKT-002.013.M07.T02 | MD-BKT-002.010.M07 | Edge | Longer period computes only new days | run 5 days, then 7 | 2 days computed | Pass |
| UT-BKT-002.014.M07.T01 | MD-BKT-002.010.M07 | Positive | Rank and top N | day with scores 0.9, 0.5, 0.9 | ranks 1, 2 (tie by symbol) and 3; top 1 keeps one row | Pass |
| UT-BKT-002.014.M07.T02 | MD-BKT-002.010.M07 | Negative | Top N 0 keeps all | N 0 | all rows | Pass |
| UT-BKT-002.015.M07.T01 | MD-BKT-002.010.M07 | Positive | Process pool run | 2 workers, 4 days | same frames as in-process; progress reaches 4 of 4 | Pass |
| UT-BKT-002.015.M07.T02 | MD-BKT-002.010.M07 | Negative | Cancel keeps finished days | cancel after first day, in process | `StepCancelled`; first day cached | Pass |
| UT-BKT-002.016.M07.T01 | MD-BKT-002.010.M07 | Negative | Weekly preset refused | preset timeframe 1w | `StepRefused` with plain message | Pass |
| UT-BKT-002.016.M07.T02 | MD-BKT-002.010.M07 | Negative | AI tick refused | `ai_ranking` true | `StepRefused`; zero screener calls | Pass |
| UT-BKT-002.018.M07.T01 | MD-BKT-002.010.M07 | Positive | RS rule detected | RS rule on, off, and no RS rule | true, false, false | Pass |
| UT-BKT-002.018.M07.T02 | MD-BKT-002.010.M07 | Negative | RS rule refused without SPY | preset with RS rule, no SPY | `StepRefused` starting "This screener uses the RS rule"; SPY named once | Pass |
| UT-BKT-002.018.M05.T01 | MD-BKT-002.008.M05 | Negative | Data check shows the RS message | estimate with RS preset | one error; 0 days | Pass |
| UT-BKT-002.019.M07.T01 | MD-BKT-002.010.M07 | Negative | Worker error is plain | screener raises an error that formats its argument | `RuntimeError("2025-03-03: Data for 'SPY' is missing")`; same text after pickling | Pass |
| UT-BKT-002.017.M05.T01 | MD-BKT-002.008.M05 | Positive | Service run recorded | fake store, preset loader | daily list returned; run row done | Pass |
| UT-BKT-002.017.M05.T02 | MD-BKT-002.008.M05 | Negative | Service cancel recorded | cancel at once | run row cancelled | Pass |

## FO-BKT-002 — Backtest Engine (Phase 2)

| UT ID | MD | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-BKT-002.020.M09.T01 | MD-BKT-002.020.M09 | Positive | Parser is the live parser | `parse("RSI('Spot', 14, '3m') > 50")` | same AST as live `_Parser` | Pass |
| UT-BKT-002.020.M09.T02 | MD-BKT-002.020.M09 | Negative | Bad text raises | `"RSI(("` | `EvaluatorError` | Pass |
| UT-BKT-002.021.M10.T01 | MD-BKT-002.021.M10 | Positive | Parity for every function and timeframe | random-walk 3m, 15m, 1d, 1w frames | series[i] equals live value on frame[:i+1] for RSI, ADX, EMA, MACD, SUPERTREND, SWING, VWAP (1d) | Pass |
| UT-BKT-002.021.M10.T02 | MD-BKT-002.021.M10 | Negative | Too few bars | 5 bars, RSI 14 | NaN where live raises | Pass |
| UT-BKT-002.022.M10.T01 | MD-BKT-002.021.M10 | Positive | Daily and 15m alignment | 3m timeline of 2 days | 1d value on day 2 is day 1's; 15m value changes only at bucket closes | Pass |
| UT-BKT-002.022.M10.T02 | MD-BKT-002.021.M10 | Negative | No look-ahead | change day 2's 1d bar | day 2 3m results unchanged | Pass |
| UT-BKT-002.023.M10.T01 | MD-BKT-002.021.M10 | Positive | Price current and Last on 15m | 3m bars in one bucket | current close = 3m close; Last = previous 15m close; current high = running high | Pass |
| UT-BKT-002.024.M10.T01 | MD-BKT-002.021.M10 | Positive | VWAP resets per session | 2 sessions of 3m bars | first bar of day 2 VWAP = its typical price | Pass |
| UT-BKT-002.025.M10.T01 | MD-BKT-002.021.M10 | Negative | NaN comparison is false | RSI 14 on first 10 bars `!= 0` | false on those bars | Pass |
| UT-BKT-002.026.M11.T01 | MD-BKT-002.026.M11 | Positive | Periods from runs of true bars | fired F T T F T | 2 periods with start, end, close at start | Pass |
| UT-BKT-002.026.M11.T02 | MD-BKT-002.026.M11 | Negative | Hours and days | bars closing 09:36, 10:00 and 15:30 ET on a Monday and a Saturday, hours 09:40–15:30 Mon–Fri | only the Monday 10:00 bar kept | Pass |
| UT-BKT-002.027.M10.T01 | MD-BKT-002.021.M10 | Positive | PNL flagged | `PNL('Spot') > 1 OR RSI(…) > 0` | `uses_pnl` true; result equals the RSI part | Pass |
| UT-BKT-002.028.M11.T01 | MD-BKT-002.026.M11 | Positive | Cache reuse | run twice | second run computes nothing | Pass |
| UT-BKT-002.028.M11.T02 | MD-BKT-002.026.M11 | Negative | Stocks follow top N and include list | include mode with 1 stock, top N 1 | only that stock computed | Pass |
| UT-BKT-002.028.M11.T03 | MD-BKT-002.026.M11 | Positive | Process pool equals in-process | 2 workers | same frames | Pass |
| UT-BKT-002.029.M05.T01 | MD-BKT-002.008.M05 | Negative | Missing strategy name | plan names "X" | `ValueError` "Strategy X is not in the strategy list" | Pass |
| UT-BKT-002.029.M05.T02 | MD-BKT-002.008.M05 | Positive | Service run of Step 2 | fake store and one strategy | signal list returned; run row done | Pass |
