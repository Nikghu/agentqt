# Design Document — Backtest Module (BKT)

**Document ID:** DD-BKT
**Version:** 1.1.0
**Traces To:** SRD-BKT v1.1.0
**Status:** Draft
**Last Updated:** 2026-10-29
**Project:** US Swing Trading System

> v1.1.0: DD-BKT-002.001.D01 and DD-BKT-002.010.D01 added — engine foundation and Step 1.
> v1.0.0: DD-BKT-001.001.D01 added — Parquet store, planner, downloader and auto delta schedule.

---

## DD-BKT-001.001.D01 — Backtest Data Store and Downloader

**Traces:** SRD-BKT-001.001–.014

**Layout.** Root `~/.usswing/backtest/` (injectable for tests):

```
settings.json        start_date, end_date (null = latest), auto_delta, run_time "HH:MM", run_days [0..6]
state.json           last_delta (ISO, UTC), floors {symbol: first date with 3m data}, failed [symbols]
1d/<SYM>.parquet     ts (date), open, high, low, close, volume
3m/<SYM>/<YYYY>.parquet   ts (UTC timestamp), open, high, low, close, volume
15m/<SYM>/<YYYY>.parquet  built from 3m — same columns (SRD .012)
1w/<SYM>.parquet          built from 1d — ts (Monday date), open, high, low, close, volume, days (SRD .013)
```

**Store (`store.py`).** `BacktestStore(root)`. `save(symbol, tf, df, now)` drops unfinished bars (SRD .003: rows on today's US/Eastern date while `now` < 16:15 ET), splits 3m rows by year, and for each target file reads the saved rows, concatenates, `drop_duplicates("ts", keep="last")`, sorts, writes `<file>.tmp` with pyarrow, then `os.replace`. `read(symbol, tf, start, end)` returns one frame. `coverage(symbol, tf)` returns `(first, last)` from the `ts` column statistics in Parquet metadata, or `None`. `stats()` sums `num_rows` from metadata and file sizes; first/last date come from 1d coverage. `clear()` removes `1d/`, `3m/`, `15m/`, `1w/` and `state.json` only.

**Built timeframes (SRD .012–.014).** After each 3m year file is written, `save()` reads that whole year file and writes `15m/<SYM>/<YYYY>.parquet`: group by `ts.floor("15min")` in UTC (US/Eastern is a whole-hour offset, so buckets are 09:30, 09:45 … 15:45 ET; 26 per normal day, 14 on a 13:00 half-day), open = first, high = max, low = min, close = last, volume = sum. After each 1d write, it rebuilds `1w/<SYM>.parquet` the same way, grouped by `ts − weekday` (Monday), plus `days` = number of daily bars. Built files are fully rewritten, not merged. `build_missing()` builds any 15m/1w file that is missing or has an older mtime than its source; `_BacktestStatsWorker` calls it before `stats()`, so data saved before this change is built once (about 0.12 s per stock). Temp files get a unique name per write, so the stats worker and a running download can write the same file safely. `stats().size_bytes` includes the built files. `read()` and `coverage()` accept `15m` and `1w`.

**Settings (`settings.py`).** `BacktestDataSettings` frozen dataclass with `load(root)` / `save(root)`; a missing or broken file returns defaults. `DownloadState` (last delta, floors, failed) lives in `state.json` with the same load/save pattern.

**Planner (`planner.py`, pure; trading days counted as weekdays).** `plan(symbols, settings, coverage, floors, last_session, delta_only) -> list[Job]`, `Job(symbol, tf, end, duration)`.
- 1d: no file → one job `end=end_date`, `duration="<years> Y"`; first saved > start → back-fill job ending at first saved.
- 3m: walk 3-month windows from end back to start; skip windows inside the saved range or before the stock's floor; `duration="3 M"`.
- Forward gap (last saved < last session): `duration="<n> D"`, n = trading days since last saved + 1, minimum 2; no job when the last saved bar is the last session (delta too).
- `delta_only=True` returns forward-gap jobs only. Order: all 1d jobs, then 3m jobs sorted by `end` descending (every stock gets recent years first).

**Downloader (`downloader.py`).** `BacktestDownloader(QThread)` takes a job list or a function that builds it (run in the thread), with its own asyncio loop and `ib_insync.IB` on `ibkr_backtest_client_id` (default 16; the next ID is tried when it is in use, like `IntradayCandleLoader`). For each job (one after another, no fixed rate limit — same as the candle download; TWS throttles 1d/3m requests itself; a `PacingQueue` can be injected), call `reqHistoricalDataAsync(..., barSizeSetting="1 day" | "3 mins", whatToShow="TRADES", useRTH=True)` with a 90 s timeout, then `store.save`. On timeout or IBKR error: wait 30 s and retry, up to 3 tries, then add the stock to `failed` and skip its other jobs. A 3m window that returns no bars while newer data exists sets the stock's floor to that window's end. `request_stop()` sets a flag checked between jobs. Signals: `progress(tf, done, total, symbol)`, `completed(ok, message)` (`finished` is taken by `QThread`). Pause in the GUI = stop; Start runs a fresh plan from disk (SRD .007).

**Schedule (`schedule.py`, pure).** `delta_due(settings, last_delta, now) -> bool`: false when auto delta is off or end date is fixed; else find the latest scheduled moment ≤ `now` (run time on the newest selected weekday, in US/Eastern) and return `last_delta < that moment`. `AppService` checks it at start and every 60 s while no download runs.

---

## DD-BKT-002.001.D01 — Backtest Engine Foundation (Phase 0)

**Traces:** SRD-BKT-002.001–.009

**Run plan (`spec.py`).** Frozen dataclasses: `Period(start, end)`, `UniverseSpec(mode, sectors, names, add, remove)` with mode `sp500 | sector | names`, `ScreenerSpec(preset_id, top_n=0, ai_ranking=False)`, `StrategySpec(id, allocation_pct, per_trade_pct)`, `AccountSpec(capital, grow_with_pnl, max_daily_loss_pct, when_full)` with `when_full` `first_signal | highest_score`, `CostSpec(per_order, slippage_bps)`, and `RunPlan(name, period, universe, screener, strategies, account, costs, schema=1)`. Value lists (`capital`, `allocation_pct`, `per_trade_pct`) are tuples; JSON accepts a number or a list and writes a number back when the tuple has one value. JSON keys follow Engine_plan §4 (`period.from` / `period.to`). `from_dict` ignores unknown keys and fills defaults.

`validate() -> list[str]`: schema ≠ 1; start after end; bad universe mode; sector mode with no sectors; names mode with no names; empty preset id; `top_n` < 0; capital ≤ 0; allocation or per-trade outside 0–100; daily loss < 0; bad `when_full`; costs < 0; variant count > 64. `variants() -> list[Variant]` is the product of capital × each strategy's allocation × each strategy's per-trade list; `Variant(capital, strategies=((id, alloc, per_trade), …))`.

**Universe (`universe.py`).** `resolve(spec, records) -> list[str]`; `records` is any sequence with `symbol` and `sector`. `sp500` = all records; `sector` = records whose sector is in `sectors` (exact text); `names` = upper-cased names. Then `add` is joined and `remove` taken out; the result is sorted and unique.

**Step cache (`cache.py`).** `StepCache(root)`, root `~/.usswing/backtest/cache/`. `make_key(step, version, params)` = sha256 of `json.dumps({"step", "version", "params"}, sort_keys=True, default=str)`. Layout `<root>/<step>/<key>/<name>.parquet`. `write(step, key, name, df)` writes `<name>.<uuid>.tmp` then `os.replace`. `read(...)` returns `None` when missing and touches the file mtime (last use). `names(step, key)` lists saved names. `cleanup(now, max_age_days=30, max_bytes=5 GB)` removes files with mtime older than the age, then the oldest files until the total is under the limit, then empty key folders; returns bytes freed.

**Results store (`results.py`).** `ResultsStore(path)`, default `~/.usswing/backtest/results.db`, stdlib `sqlite3`. Table `runs(run_id TEXT PK, name, plan_json, status, started, finished, message)`. `start_run(plan, now) -> run_id` (uuid4 hex, status `running`), `finish_run(run_id, status, now, message="")` with status `done | cancelled | failed`, `list_runs(limit=50)` newest first, `get_run(run_id)`. Variants, trades and logs tables come in Phase 3.

**Estimate (`service.py`).** `BacktestService(store, cache, results, records, presets)`; `records` and `presets` are callables (universe records; preset loader) so tests and the GUI inject their own. `estimate(plan, user_id) -> Estimate(symbols, missing_1d, missing_3m, benchmark_ok, days_total, days_cached, errors)`. A stock misses a timeframe when it has no coverage, its first date is more than 5 calendar days after the start, or its last date is more than 5 calendar days before the end (clipped to today). `benchmark_ok` = SPY has 1d coverage. Days come from Step 1 (DD-BKT-002.010.D01); with errors (validation or preset not found) the day counts are 0.

**CLI (`cli.py`).** `python -m us_swing.backtest.cli estimate PLAN` prints the estimate; `run PLAN [--user ID] [--workers N]` runs Step 1 and prints days, total passes and the top 5 of the last day. Exit code 0 ok, 1 errors. Universe records come from `core.backtest_bridge.load_universe()`.

---

## DD-BKT-002.010.D01 — Step 1 Stocks (Phase 1)

**Traces:** SRD-BKT-002.010–.017

**Bridge (`core/backtest_bridge.py`).** The engine does not import `screener` or `universe` directly. The bridge gives: `load_universe()` (S&P 500 records from `universe.store`), `list_presets(user_id)` (admin + user presets as `PresetInfo(id, name, timeframe, ai)`), `load_preset_dict(preset_id, user_id)` and `screen_day(preset_dict, symbols, bars, market_caps) -> {symbol: (passed, score)}`. `screen_day` builds a `Preset` and calls the new public `PresetExecutor.screen()` (pre-filter + Stage 2 + group/weight logic, no AI, nothing saved). `run_preset()` now calls `screen()` too, so live and backtest use one path (cross-tool note for SCR; live behaviour unchanged).

**Days (SRD .010).** `trading_days(store, period, symbols)`: dates of `store.read("SPY", "1d", start, end)`; if empty, the sorted union of the stocks' 1d dates in the period.

**Rules key (SRD .012–.013).** `rules_key(preset_dict, symbols)` = `make_key("stocks", STEP_VERSION, {preset fields that change results, symbols})`. Kept preset fields: `preset_type`, `groups`, `screeners`, `threshold`, `timeframe`. Not in the key: name, dates, users, `top_n`, AI fields. One cache file per day, name `YYYY-MM-DD`, columns `symbol, passed, score` (passing rows only; an empty frame is saved for a day with no passes so it counts as done).

**Day compute (SRD .011).** Worker processes start with `_init_worker(root, symbols, load_start, end)`, which reads each stock's 1d bars (plus SPY) once into a module global: `dates` (numpy `datetime64[D]`) and a list of slotted `_Bar(datetime, open, high, low, close, volume)`. `load_start` = period start − 900 calendar days (600 trading bars). `_run_day(preset_dict, day, market_caps)` slices each stock with `searchsorted(dates, day, "right")` to the last 600 bars, drops stocks with no bar on `day`, calls `screen_day`, and returns `(day, frame)`. SPY bars are passed in `bars` but not in `symbols` unless the universe has it.

**Run (SRD .015).** `run_stocks(plan, preset_dict, symbols, store, cache, market_caps, workers, progress, cancel)`: compute the key and the days not cached. `workers=0` runs in this process (tests); else `ProcessPoolExecutor(min(workers, cpu))` with the initialiser, one task per day. Each finished day is written to the cache and `progress(done, total)` is called. `cancel()` is checked after each result; when true, pending tasks are cancelled (`shutdown(cancel_futures=True)`) and `StepCancelled` is raised. `run_gui.py` calls `multiprocessing.freeze_support()` for the frozen app.

**Daily list (SRD .014).** `daily_list(cache, key, days)` reads the day files and returns `date, symbol, score, rank` (`rank` = position by score descending, ties by symbol, starting at 1). `top_n(frame, n)` keeps `rank <= n`; `n == 0` keeps all.

**Refusals (SRD .016).** Before any compute: preset `timeframe` ≠ `1d` → "Weekly screener presets are not supported in backtest yet"; `plan.screener.ai_ranking` → "AI ranking is not built yet — untick it to run". Also added to `estimate().errors`.

**Service (SRD .017).** `BacktestService.run_stocks(plan, user_id, progress, cancel, workers=4) -> DailyList(key, days, frame)`: validate, resolve symbols, load the preset, clean the cache (SRD .006), start a run row, call the step, finish the row as `done`, `cancelled` or `failed`. Market caps come from the universe records.
