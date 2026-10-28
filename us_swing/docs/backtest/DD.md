# Design Document — Backtest Module (BKT)

**Document ID:** DD-BKT
**Version:** 1.0.0
**Traces To:** SRD-BKT v1.0.0
**Status:** Draft
**Last Updated:** 2026-10-28
**Project:** US Swing Trading System

> v1.0.0: DD-BKT-001.001.D01 added — Parquet store, planner, downloader and auto delta schedule.

---

## DD-BKT-001.001.D01 — Backtest Data Store and Downloader

**Traces:** SRD-BKT-001.001–.011

**Layout.** Root `~/.usswing/backtest/` (injectable for tests):

```
settings.json        start_date, end_date (null = latest), auto_delta, run_time "HH:MM", run_days [0..6]
state.json           last_delta (ISO, UTC), floors {symbol: first date with 3m data}, failed [symbols]
1d/<SYM>.parquet     ts (date), open, high, low, close, volume
3m/<SYM>/<YYYY>.parquet   ts (UTC timestamp), open, high, low, close, volume
```

**Store (`store.py`).** `BacktestStore(root)`. `save(symbol, tf, df, now)` drops unfinished bars (SRD .003: rows on today's US/Eastern date while `now` < 16:15 ET), splits 3m rows by year, and for each target file reads the saved rows, concatenates, `drop_duplicates("ts", keep="last")`, sorts, writes `<file>.tmp` with pyarrow, then `os.replace`. `read(symbol, tf, start, end)` returns one frame. `coverage(symbol, tf)` returns `(first, last)` from the `ts` column statistics in Parquet metadata, or `None`. `stats()` sums `num_rows` from metadata and file sizes; first/last date come from 1d coverage. `clear()` removes `1d/`, `3m/` and `state.json` only.

**Settings (`settings.py`).** `BacktestDataSettings` frozen dataclass with `load(root)` / `save(root)`; a missing or broken file returns defaults. `DownloadState` (last delta, floors, failed) lives in `state.json` with the same load/save pattern.

**Planner (`planner.py`, pure; trading days counted as weekdays).** `plan(symbols, settings, coverage, floors, last_session, delta_only) -> list[Job]`, `Job(symbol, tf, end, duration)`.
- 1d: no file → one job `end=end_date`, `duration="<years> Y"`; first saved > start → back-fill job ending at first saved.
- 3m: walk 3-month windows from end back to start; skip windows inside the saved range or before the stock's floor; `duration="3 M"`.
- Forward gap (last saved < last session): `duration="<n> D"`, n = trading days since last saved + 1, minimum 2.
- `delta_only=True` returns forward-gap jobs only. Order: all 1d jobs, then 3m jobs sorted by `end` descending (every stock gets recent years first).

**Downloader (`downloader.py`).** `BacktestDownloader(QThread)` takes a job list or a function that builds it (run in the thread), with its own asyncio loop and `ib_insync.IB` on `ibkr_backtest_client_id` (default 16; the next ID is tried when it is in use, like `IntradayCandleLoader`). For each job: wait on `PacingQueue`, call `reqHistoricalDataAsync(..., barSizeSetting="1 day" | "3 mins", whatToShow="TRADES", useRTH=True)` with a 90 s timeout, then `store.save`. On timeout or IBKR error: wait 30 s and retry, up to 3 tries, then add the stock to `failed` and skip its other jobs. A 3m window that returns no bars while newer data exists sets the stock's floor to that window's end. `request_stop()` sets a flag checked between jobs. Signals: `progress(tf, done, total, symbol)`, `completed(ok, message)` (`finished` is taken by `QThread`). Pause in the GUI = stop; Start runs a fresh plan from disk (SRD .007).

**Schedule (`schedule.py`, pure).** `delta_due(settings, last_delta, now) -> bool`: false when auto delta is off or end date is fixed; else find the latest scheduled moment ≤ `now` (run time on the newest selected weekday, in US/Eastern) and return `last_delta < that moment`. `AppService` checks it at start and every 60 s while no download runs.
