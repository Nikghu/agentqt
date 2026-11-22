# ISS-BKT-0003 — Old stocks start in 2023/2024 but Backtest data says "Up to date"

**Date:** 2026-11-22
**Tool:** BKT (shown in GUI Settings → Universe and Backtest data)
**Status:** Fixed (code), app check pending (TODO T223)

## Symptom

Range start is 2022-01-03, but 224 old stocks (UNP, UPS, V, VZ, MSFT …) had daily and 3m data only from 2023-01-03 or 2024-01-02. Universe showed ✓ and Backtest data showed "All candles saved / Up to date".

## Root cause

When a daily back-fill came back empty, `_update_floor()` saved the first saved bar as the stock's listing date (floor). On 2026-11-19 IBKR refused requests with Error 162 "Trading TWS session is connected from a different IP address", so 224 fake floors were saved (176 at 2023-01-03, 48 at 2024-01-02). The planner never asks before a floor, and the Universe status moved the start to the floor, so both said complete.

## Fix (user decision 2026-11-22, no new SRD)

- Universe status compares BT From / BT To only with the Backtest Data range; a stock that does not cover it, or has no 3m data, is **Partial** (floors are not used).
- Universe rows that are Partial or missing get a tick box; **Select partial** ticks them all, **Fill selected** drops the ticked stocks' floors and downloads only those stocks from the range start.
- Backtest data card shows "N stocks partial" and a Partial button (off) instead of "Up to date".

Data that IBKR does not have today stays Partial; the user can fill it again later.

## Part 2 — missing 3m days inside the range (2026-11-22)

A check of META and TSLA after the fill found both complete except 2024-01-05. Across the store, 492 of 504 stocks missed whole 3m days that their daily data has (most: 2024-01-05 263 stocks, 2024-07-03 218, 2024-01-04 213, 2026-07-28/29 115, 2024-10-02 59). The planner and the status looked only at the first and last date, so these gaps were never asked again.

- `BacktestStore.gap_days()` finds them; `refresh_gaps()` caches them in `gaps.json` (re-worked only when a stock's files change; about 2 minutes the first time, in the background); `cached_gaps()` is a fast read for the GUI.
- The planner asks each run of gap days again with a short 3m request ("1 D", "2 D" …); 15m and 30m are rebuilt on save. Delta runs skip them.
- A stock with gap days is Partial; the Universe tooltip lists the days.

## Files

`gui/app_service.py` (coverage status, `fill_backtest_symbols`, `get_backtest_range`, partial count), `backtest/store.py` (`partial_stocks`), `gui/backtest_data_panel.py`, `gui/settings_panel.py` (Universe table, buttons).

## Tests

UT-GUI-030.006.M01.T03, UT-GUI-030.008.M02.T02–T03, UT-GUI-030.008.M03.T02–T06, UT-GUI-030.009.M02.T02, UT-GUI-030.011.M02.T02; UT-BKT-001.001.M01.T03–T04, UT-BKT-001.005.M03.T06; UT-GUI-030.008.M02.T01 and UT-GUI-030.011.M02.T01 changed.
