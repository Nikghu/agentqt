# Unit Test Case Document — Backtest Module (BKT)

**Document ID:** UTCD-BKT
**Version:** 1.0.0
**Traces To:** MD-BKT v1.0.0
**Status:** Draft
**Last Updated:** 2026-10-28
**Project:** US Swing Trading System

> v1.0.0: UT-BKT-001.* added — store, settings, planner, downloader (fake IB), schedule.

---

## FO-BKT-001 — Backtest Data Store and Downloader

| UT ID | MD | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-BKT-001.001.M01.T01 | MD-BKT-001.001.M01 | Positive | 3m bars split by year | bars over 2024-12-31 and 2025-01-02 | files `3m/AAPL/2024` and `2025`; read returns all rows in order | Not Run |
| UT-BKT-001.001.M01.T02 | MD-BKT-001.001.M01 | Negative | Unknown stock reads empty | no files for ZZZZ | empty frame; coverage None; no file created | Not Run |
| UT-BKT-001.002.M01.T01 | MD-BKT-001.001.M01 | Positive | Overlap merge keeps one row per timestamp | save, then save overlapping rows with new close | no duplicate ts; new close kept | Not Run |
| UT-BKT-001.002.M01.T02 | MD-BKT-001.001.M01 | Negative | Failed write keeps old file | write raises mid-save | old file still readable; no `.tmp` left | Not Run |
| UT-BKT-001.003.M01.T01 | MD-BKT-001.001.M01 | Negative | Unfinished day dropped | today's bars, now 14:00 ET | today's rows not saved | Not Run |
| UT-BKT-001.003.M01.T02 | MD-BKT-001.001.M01 | Positive | Finished day kept | today's bars, now 16:20 ET | today's rows saved | Not Run |
| UT-BKT-001.010.M01.T01 | MD-BKT-001.001.M01 | Positive | Clear keeps settings | store with data, settings and a `candles.db` beside it | data and state gone; `settings.json` and `candles.db` kept | Not Run |
| UT-BKT-001.010.M01.T02 | MD-BKT-001.001.M01 | Negative | Clear on empty store is safe | empty root with `settings.json` only | no error; `settings.json` unchanged | Not Run |
| UT-BKT-001.011.M01.T01 | MD-BKT-001.001.M01 | Positive | Stats from metadata | 2 stocks saved | stock count 2; bar counts, first/last date and size match | Not Run |
| UT-BKT-001.004.M02.T01 | MD-BKT-001.004.M02 | Positive | Settings round trip | save custom settings, load | values equal | Not Run |
| UT-BKT-001.004.M02.T02 | MD-BKT-001.004.M02 | Negative | Broken file loads defaults | `settings.json` with bad JSON | defaults 2016-01-01, latest, on, 17:30, Mon–Fri | Not Run |
| UT-BKT-001.005.M03.T01 | MD-BKT-001.005.M03 | Positive | Empty store plan | 2 stocks, 2025-01-01 to 2025-12-31 | 2 1d jobs first; 3m jobs newest end first across both stocks | Not Run |
| UT-BKT-001.005.M03.T02 | MD-BKT-001.005.M03 | Negative | Fully saved store has no jobs | coverage equals range | empty plan | Not Run |
| UT-BKT-001.005.M03.T03 | MD-BKT-001.005.M03 | Edge | Earlier start back-fills only older windows | saved 2024–2025, start moved to 2023 | 3m jobs only for 2023 windows; one 1d back-fill job | Not Run |
| UT-BKT-001.005.M03.T04 | MD-BKT-001.005.M03 | Edge | Floor skips windows before first data | floor 2024-06-01 | no 3m job ending before the floor | Not Run |
| UT-BKT-001.008.M03.T01 | MD-BKT-001.005.M03 | Positive | Delta asks days since last bar | last saved 3 trading days ago, `delta_only` | one job per stock and tf, duration "4 D" | Not Run |
| UT-BKT-001.008.M03.T02 | MD-BKT-001.005.M03 | Edge | Delta minimum 2 days | last saved = last session | duration "2 D" | Not Run |
| UT-BKT-001.008.M03.T03 | MD-BKT-001.005.M03 | Negative | No delta with fixed end date | end date 2025-12-31, `delta_only` | empty plan | Not Run |
| UT-BKT-001.006.M04.T01 | MD-BKT-001.006.M04 | Positive | Jobs saved with progress | fake IB returns bars for 2 jobs | both saved; progress emitted 1/2, 2/2; finished ok | Not Run |
| UT-BKT-001.006.M04.T02 | MD-BKT-001.006.M04 | Negative | Retry then mark failed | fake IB times out every time for AAPL | 3 tries; AAPL in failed; MSFT jobs still run | Not Run |
| UT-BKT-001.006.M04.T03 | MD-BKT-001.006.M04 | Edge | Empty window sets floor | 3m window returns no bars, newer data saved | floor set to window end | Not Run |
| UT-BKT-001.007.M04.T01 | MD-BKT-001.006.M04 | Positive | Stop ends after current job | stop requested during job 1 of 3 | job 1 saved; jobs 2–3 not requested | Not Run |
| UT-BKT-001.007.M04.T02 | MD-BKT-001.006.M04 | Negative | Stopped run is not reported complete | stop requested during job 1 of 3 | finished ok False with message "Stopped" | Not Run |
| UT-BKT-001.009.M05.T01 | MD-BKT-001.009.M05 | Positive | Due after run time | Tue 17:31 ET, last delta Mon 17:35 | due | Not Run |
| UT-BKT-001.009.M05.T02 | MD-BKT-001.009.M05 | Negative | Not due before run time | Tue 17:00 ET, last delta Mon 17:35 | not due | Not Run |
| UT-BKT-001.009.M05.T03 | MD-BKT-001.009.M05 | Edge | Missed Friday caught up on Monday morning | Mon 09:00 ET, last delta Thu 17:35 | due | Not Run |
| UT-BKT-001.009.M05.T04 | MD-BKT-001.009.M05 | Negative | Off when fixed end date | end date set, Tue 17:31 ET | not due | Not Run |
