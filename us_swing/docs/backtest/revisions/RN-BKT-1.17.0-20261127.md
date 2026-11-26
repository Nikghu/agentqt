# Revision Note — RN-BKT-1.17.0-20261127

**Version:** 1.17.0
**Date:** 2026-11-27
**Tool:** BKT
**Artifact:** FO-BKT-001, FO-BKT-002 / SRD-BKT-001.019, SRD-BKT-002.089–.091
**Type:** Bugfix

---

## Summary

The HTML report All trades table now shows Entry and Exit rows in time order, with Available capital after each row, and shades idle capital red. A start-date bug is fixed: a plan for 2021 started in 2024 because Step 1 days came from SPY's daily candles. Step 1 days now come from the run stocks, and SPY, RSP and the sector ETFs download first. Real data: the 2021 plan now has 1,482 sessions from 2021-01-04 (was 728 from 2024).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.083.M15 | `backtest/html_report.py` | All trades: Entry and Exit rows in time order, numbered by entry, Time column, Available after each row, red shade above 80% |
| MD-BKT-002.010.M07 | `backtest/steps/stocks.py` | `trading_days()` takes Step 1 days from the run stocks' own daily dates; SPY only for the RS rule |
| MD-BKT-001.005.M03 | `backtest/planner.py` | SPY, RSP and sector ETFs are asked before any S&P 500 stock in every download, delta and fill |

Data repair (one-off, no code): SPY, RSP and 11 sector ETF daily candles re-downloaded from TWS and merged; now 2019-09-23 to 2026-11-25. A wrong SPY floor of 2024-01-02 still sits in the download state (harmless now).

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-001.019 | Every download, delta and fill asks for SPY, RSP and sector ETFs before any S&P 500 stock | Implemented |
| SRD-BKT-002.089 | HTML All trades: Entry and Exit rows in time order, Available after each row | Implemented |
| SRD-BKT-002.090 | HTML All trades: Available cell shaded light red above 80% of start capital | Implemented |
| SRD-BKT-002.091 | Step 1 days are the run stocks' own daily dates; SPY never sets or cuts the days | Implemented |

---

## Design Decisions

- Step 1 days come from the traded stocks, so the run starts on the first stock day in the plan, not on SPY's first candle.
- SPY stays only for the RS rule.
- Accumulation preset checked: works, about 1 pick a day, matches live saved lists. Not a bug.

---

## Issues Resolved

None (the 2024 start bug has no ISS ID)

---

## Test Coverage

- New, Pass: UT-BKT-002.089.M15.T01–T02; UT-BKT-002.090.M15.T01; UT-BKT-002.091.M07.T01; UT-BKT-001.019.M03.T01.
- Updated, Pass: UT-BKT-002.083.M15.T01 and T09 (Entry and Exit rows with time).
- Replaced: UT-BKT-002.053.M15.T01 (by UT-BKT-002.089.M15.T01); UT-BKT-002.010.M07.T01 (by UT-BKT-002.091.M07.T01).
- Open user checks are in TODO.md (T258, T259).
