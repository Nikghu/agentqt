# Module Decomposition — Backtest Module (BKT)

**Document ID:** MD-BKT
**Version:** 1.0.0
**Traces To:** SRD-BKT v1.0.0 / DD-BKT v1.0.0
**Status:** Draft
**Last Updated:** 2026-10-28
**Project:** US Swing Trading System

> v1.0.0: MD-BKT-001.* added — new package `us_swing/src/us_swing/backtest/`.

---

## FO-BKT-001 — Backtest Data Store and Downloader

| MD ID | SRD | File | Purpose | Public API | Depends on | Async |
|---|---|---|---|---|---|---|
| MD-BKT-001.001.M01 | SRD-BKT-001.001 | `us_swing/src/us_swing/backtest/store.py` | Parquet read, merge-save, coverage, stats and clear | `BacktestStore`, `save()`, `read()`, `coverage()`, `stats()`, `clear()` | `pandas`, `pyarrow` | No |
| MD-BKT-001.004.M02 | SRD-BKT-001.004 | `us_swing/src/us_swing/backtest/settings.py` | Settings and download state files | `BacktestDataSettings`, `DownloadState`, `load()`, `save()` | — | No |
| MD-BKT-001.005.M03 | SRD-BKT-001.005 | `us_swing/src/us_swing/backtest/planner.py` | Build the request list from settings and saved ranges | `Job`, `plan()` | `market_calendar` | No |
| MD-BKT-001.006.M04 | SRD-BKT-001.006 | `us_swing/src/us_swing/backtest/downloader.py` | Run jobs against TWS with pacing, retry and stop | `BacktestDownloader`, `request_stop()`, `progress`, `finished` | `store`, `planner`, `broker.pacing`, `ib_insync` | Yes (`QThread` + asyncio) |
| MD-BKT-001.009.M05 | SRD-BKT-001.009 | `us_swing/src/us_swing/backtest/schedule.py` | Decide when auto delta is due | `delta_due()` | `settings` | No |
