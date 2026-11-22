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

## Files

`gui/app_service.py` (coverage status, `fill_backtest_symbols`, `get_backtest_range`, partial count), `backtest/store.py` (`partial_stocks`), `gui/backtest_data_panel.py`, `gui/settings_panel.py` (Universe table, buttons).

## Tests

UT-GUI-030.006.M01.T03, UT-GUI-030.008.M02.T02–T03, UT-GUI-030.008.M03.T02–T03, UT-GUI-030.009.M02.T02; UT-GUI-030.008.M02.T01 and UT-GUI-030.011.M02.T01 changed.
