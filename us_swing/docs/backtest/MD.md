# Module Decomposition — Backtest Module (BKT)

**Document ID:** MD-BKT
**Version:** 1.1.0
**Traces To:** SRD-BKT v1.1.0 / DD-BKT v1.1.0
**Status:** Draft
**Last Updated:** 2026-10-29
**Project:** US Swing Trading System

> v1.1.0: MD-BKT-002.* added — engine Phase 0 and 1 (spec, universe, cache, results, service, cli, steps/stocks, core bridge).
> v1.0.0: MD-BKT-001.* added — new package `us_swing/src/us_swing/backtest/`.

---

## FO-BKT-001 — Backtest Data Store and Downloader

| MD ID | SRD | File | Purpose | Public API | Depends on | Async |
|---|---|---|---|---|---|---|
| MD-BKT-001.001.M01 | SRD-BKT-001.001 | `us_swing/src/us_swing/backtest/store.py` | Parquet read, merge-save, 15m/1w build, coverage, stats and clear | `BacktestStore`, `save()`, `build_missing()`, `read()`, `coverage()`, `stats()`, `clear()`, `StoredTf` | `pandas`, `pyarrow` | No |
| MD-BKT-001.004.M02 | SRD-BKT-001.004 | `us_swing/src/us_swing/backtest/settings.py` | Settings and download state files | `BacktestDataSettings`, `DownloadState`, `load()`, `save()` | — | No |
| MD-BKT-001.005.M03 | SRD-BKT-001.005 | `us_swing/src/us_swing/backtest/planner.py` | Build the request list from settings and saved ranges | `Job`, `plan()` | `settings`, `store.Timeframe` | No |
| MD-BKT-001.006.M04 | SRD-BKT-001.006 | `us_swing/src/us_swing/backtest/downloader.py` | Run jobs against TWS with pacing, retry and stop | `BacktestDownloader`, `request_stop()`, `progress`, `completed` | `store`, `planner`, `broker.pacing`, `ib_insync` | Yes (`QThread` + asyncio) |
| MD-BKT-001.009.M05 | SRD-BKT-001.009 | `us_swing/src/us_swing/backtest/schedule.py` | Decide when auto delta is due | `delta_due()` | `settings` | No |

## FO-BKT-002 — Backtest Engine (Phase 0 and 1)

| MD ID | SRD | File | Purpose | Public API | Depends on | Async |
|---|---|---|---|---|---|---|
| MD-BKT-002.001.M01 | SRD-BKT-002.001 | `us_swing/src/us_swing/backtest/spec.py` | Run plan, JSON, validation and variants | `RunPlan`, `Period`, `UniverseSpec`, `ScreenerSpec`, `StrategySpec`, `AccountSpec`, `CostSpec`, `Variant`, `validate()`, `variants()` | — | No |
| MD-BKT-002.004.M02 | SRD-BKT-002.004 | `us_swing/src/us_swing/backtest/universe.py` | Resolve the stock list | `resolve()` | `spec` | No |
| MD-BKT-002.005.M03 | SRD-BKT-002.005 | `us_swing/src/us_swing/backtest/cache.py` | Keyed step cache with atomic writes and cleanup | `StepCache`, `make_key()`, `read()`, `write()`, `names()`, `cleanup()` | `pandas`, `pyarrow` | No |
| MD-BKT-002.007.M04 | SRD-BKT-002.007 | `us_swing/src/us_swing/backtest/results.py` | Run rows in `results.db` | `ResultsStore`, `start_run()`, `finish_run()`, `list_runs()`, `get_run()` | `sqlite3` | No |
| MD-BKT-002.008.M05 | SRD-BKT-002.008 | `us_swing/src/us_swing/backtest/service.py` | Estimate and Step 1 run for GUI and CLI | `BacktestService`, `Estimate`, `DailyList`, `estimate()`, `run_stocks()` | `store`, `cache`, `results`, `universe`, `steps.stocks` | No (called from a worker thread) |
| MD-BKT-002.009.M06 | SRD-BKT-002.009 | `us_swing/src/us_swing/backtest/cli.py` | Command line `estimate` and `run` | `main()` | `service`, `core.backtest_bridge` | No |
| MD-BKT-002.010.M07 | SRD-BKT-002.010 | `us_swing/src/us_swing/backtest/steps/stocks.py` | Step 1 screener replay, day cache, daily list | `trading_days()`, `rules_key()`, `run_stocks()`, `daily_list()`, `top_n()`, `StepCancelled`, `StepRefused` | `cache`, `store`, `core.backtest_bridge` | Process pool |
| MD-BKT-002.011.M08 | SRD-BKT-002.011 | `us_swing/src/us_swing/core/backtest_bridge.py` | Bridge to screener presets and the universe | `load_universe()`, `list_presets()`, `PresetInfo`, `load_preset_dict()`, `screen_day()` | `screener`, `universe` | No |

Cross-tool note: `screener/executor.py` gets a public `PresetExecutor.screen()` (pre-filter + Stage 2 + combine) that `run_preset()` now calls; live screener results are unchanged.
