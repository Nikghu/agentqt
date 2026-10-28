# Revision Note — RN-BKT-1.0.0-20261028

**Version:** 1.0.0
**Date:** 2026-10-28
**Tool:** BKT
**Artifact:** FO-BKT-001 / SRD-BKT-001.001–.011
**Type:** Feature

---

## Summary

First BKT module: a Parquet candle store for backtesting plus a TWS downloader. 1d and 3m candles for the S&P 500 are saved under `~/.usswing/backtest/`, apart from `candles.db`. Downloads resume from disk. A daily delta fill can run on its own at a set US/Eastern time.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-001.001.M01 | `backtest/store.py` | New — merge-save with atomic replace, unfinished-day guard, coverage and stats from metadata, clear |
| MD-BKT-001.004.M02 | `backtest/settings.py` | New — `settings.json` and `state.json` (last delta, floors, failed) |
| MD-BKT-001.005.M03 | `backtest/planner.py` | New — 1d then 3m 3-month windows, newest first; delta jobs; floors |
| MD-BKT-001.006.M04 | `backtest/downloader.py` | New — QThread + asyncio, client ID 16 with fallback, pacing, 3 tries, stop |
| MD-BKT-001.009.M05 | `backtest/schedule.py` | New — `delta_due()` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-001.001 | 1d one file per stock, 3m one file per stock per year | Implemented |
| SRD-BKT-001.002 | Merge by timestamp, atomic replace | Implemented |
| SRD-BKT-001.003 | No bars of today before 16:15 ET | Implemented |
| SRD-BKT-001.004 | Settings file with defaults | Implemented |
| SRD-BKT-001.005 | Download plan skips saved ranges and floors | Implemented |
| SRD-BKT-001.006 | Background download, retry 3 times then mark failed | Implemented |
| SRD-BKT-001.007 | Stop after current request; resume from files | Implemented |
| SRD-BKT-001.008 | Delta asks days since last bar, at least 2 | Implemented |
| SRD-BKT-001.009 | Auto delta due at set ET time, missed run caught up | Implemented |
| SRD-BKT-001.010 | Clear keeps `settings.json` | Implemented |
| SRD-BKT-001.011 | Stats from Parquet metadata | Implemented |

---

## Design Decisions

- Trading days are counted as weekdays: `NYSE_HOLIDAYS` only covers 2026, and a holiday only makes a delta request one day longer.
- The run-end signal is `completed`, because `QThread` already owns `finished`.
- The plan is built inside the download thread; reading metadata for 500 stocks is too slow for the GUI thread.
- A 1d request that starts much later than the range start (IPO) sets the stock's floor, so it is not asked again.
- No fixed 50-per-10-minute limiter (user test 2026-10-28: download sat at 50 of 503 for 10 minutes). Requests run back to back like the candle download; errors and timeouts still retry. Estimate line now shows hours (~1 s per 1d, ~4 s per 3m request, measured).
- Bars before the job start are dropped on save (IBKR "1 Y" returns a full year), 3m windows start at the range start, and an empty delta no longer stamps Last delta. Panel stats refresh every 15 s during a run; counts say "this run"; estimate uses all S&P 500 stocks.
- Stocks use the S&P 500 `ibkr_symbol` (e.g. `BRK B`) as the file name.

---

## Tests

27 UT-BKT-001.* pass (store, settings, planner, fake-IB downloader, schedule). Real TWS check with 3 stocks not run — TWS was closed.
