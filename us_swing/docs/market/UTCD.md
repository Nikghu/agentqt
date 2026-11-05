# Unit Test Cases — Market Analytics (MKT)

**Document ID:** UTCD-MKT
**Version:** 0.2.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.2.0: 25 test cases for FO-MKT-001 (P1).
> v0.1.0: Empty. Rows are added per phase, starting with the first FO of this tool.

---

## FO-MKT-001: Market Regime, Breadth and Fear

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MKT-001.001.M01.T01 | MD-MKT-001.001.M01 | Positive | Reads bars read-only (SRD-MKT-001.001) | temp candles.db with SPY and 3 members | frames per symbol; file unchanged | Not Run |
| UT-MKT-001.001.M01.T02 | MD-MKT-001.001.M01 | Negative | Missing candles file (SRD-MKT-001.001) | no file | raises FileNotFoundError; no file created | Not Run |
| UT-MKT-001.002.M02.T01 | MD-MKT-001.002.M02 | Positive | Uptrend (SRD-MKT-001.002) | rising SPY series, 260 days | last day Uptrend | Not Run |
| UT-MKT-001.002.M02.T02 | MD-MKT-001.002.M02 | Positive | Downtrend (SRD-MKT-001.002) | falling series | last day Downtrend | Not Run |
| UT-MKT-001.002.M02.T03 | MD-MKT-001.002.M02 | Negative | Choppy and too short (SRD-MKT-001.002) | flat zig-zag; 150 days | Choppy; no value before 210 bars | Not Run |
| UT-MKT-001.003.M02.T01 | MD-MKT-001.002.M02 | Positive | High volatility (SRD-MKT-001.003) | calm year then 20 wild days | High, percentile above 70 | Not Run |
| UT-MKT-001.003.M02.T02 | MD-MKT-001.002.M02 | Negative | Calm volatility (SRD-MKT-001.003) | wild year then 20 quiet days | Calm | Not Run |
| UT-MKT-001.004.M02.T01 | MD-MKT-001.002.M02 | Positive | Breadth counts (SRD-MKT-001.004) | 4 members, hand-made closes | pct above 20/50/200, highs, lows, advancers, decliners as computed by hand | Not Run |
| UT-MKT-001.004.M02.T02 | MD-MKT-001.002.M02 | Negative | Short history member (SRD-MKT-001.004) | member with 30 bars | counted for 20-day, not for 50/200 | Not Run |
| UT-MKT-001.005.M03.T01 | MD-MKT-001.005.M03 | Positive | VIX rows from download (SRD-MKT-001.005) | fake downloader frame | rows by date with vix and vix3m | Not Run |
| UT-MKT-001.005.M03.T02 | MD-MKT-001.005.M03 | Negative | Download fails (SRD-MKT-001.005) | downloader raises | empty result; warning logged | Not Run |
| UT-MKT-001.006.M02.T01 | MD-MKT-001.002.M02 | Positive | Fear points (SRD-MKT-001.006) | VIX 32 above VIX3M, High, pct50 35 | score 6, Fearful | Not Run |
| UT-MKT-001.006.M02.T02 | MD-MKT-001.002.M02 | Negative | No VIX (SRD-MKT-001.006) | VIX missing, Normal, pct50 60 | score 0, Calm, note no VIX | Not Run |
| UT-MKT-001.007.M04.T01 | MD-MKT-001.007.M04 | Positive | Rows round trip (SRD-MKT-001.007) | write two days, read back | same values; re-write replaces | Not Run |
| UT-MKT-001.007.M04.T02 | MD-MKT-001.007.M04 | Edge | Tables beside desk tables (SRD-MKT-001.007) | existing desk.db | desk tables untouched | Not Run |
| UT-MKT-001.007.M04.T03 | MD-MKT-001.007.M04 | Negative | Row without a date refused (SRD-MKT-001.007) | regime row with empty date | raises ValueError; nothing written | Not Run |
| UT-MKT-001.008.M05.T01 | MD-MKT-001.011.M05 | Positive | First run fills history (SRD-MKT-001.008) | 260 days of bars | rows from day 210 to last | Not Run |
| UT-MKT-001.008.M05.T02 | MD-MKT-001.011.M05 | Positive | Later run adds only new days (SRD-MKT-001.008) | second run with one new day | one row added | Not Run |
| UT-MKT-001.008.M05.T03 | MD-MKT-001.011.M05 | Negative | No new candles (SRD-MKT-001.008) | second run, same bars | no rows added | Not Run |
| UT-MKT-001.009.M05.T01 | MD-MKT-001.011.M05 | Negative | Low coverage day skipped (SRD-MKT-001.009) | day with 70% of members | no row; logged | Not Run |
| UT-MKT-001.009.M05.T02 | MD-MKT-001.011.M05 | Positive | Full coverage day stored (SRD-MKT-001.009) | day with all members | row stored with members count | Not Run |
| UT-MKT-001.010.M05.T01 | MD-MKT-001.011.M05 | Negative | Stale candles noted (SRD-MKT-001.010) | last SPY day a week old | note says stale | Not Run |
| UT-MKT-001.010.M05.T02 | MD-MKT-001.011.M05 | Positive | Fresh candles not flagged (SRD-MKT-001.010) | last SPY day is the last weekday | note has no stale text | Not Run |
| UT-MKT-001.011.M05.T01 | MD-MKT-001.011.M05 | Positive | Step runs in a desk run (SRD-MKT-001.011) | DeskProcess with loaded steps, run-now | run ok; rows written | Not Run |
| UT-MKT-001.011.M05.T02 | MD-MKT-001.011.M05 | Negative | VIX down, step still ok (SRD-MKT-001.011) | fake VIX fetch fails | rows written; note no VIX | Not Run |
