# Software Requirements Document — Backtest Module (BKT)

**Document ID:** SRD-BKT
**Version:** 1.1.0
**Traces To:** FO-BKT v1.1.0
**Status:** Draft
**Last Updated:** 2026-10-29
**Project:** US Swing Trading System

> v1.1.0: SRD-BKT-002.001–.017 added — engine Phase 0 and 1; approved by user 2026-10-29.
> v1.0.0: SRD-BKT-001.001–.011 added — backtest data store and downloader (Draft, waiting for user approval).

---

## FO-BKT-001 — Backtest Data Store and Downloader

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-BKT-001.001 | FO-BKT-001 | Must | 1d candles are stored as one Parquet file per stock and 3m candles as one file per stock per year under `~/.usswing/backtest/`. | bars | Parquet files | Never reads or writes `candles.db` | Implemented |
| SRD-BKT-001.002 | FO-BKT-001 | Must | Saving merges new bars with saved bars by timestamp, keeps one row per timestamp and replaces the file atomically. | bars | file | A crash mid-write leaves the old file intact | Implemented |
| SRD-BKT-001.003 | FO-BKT-001 | Must | Bars of the current US trading day are not saved before 16:15 US/Eastern. | bars, clock | filtered bars | Applies to 1d and 3m | Implemented |
| SRD-BKT-001.004 | FO-BKT-001 | Must | Settings hold start date, end date or latest, auto delta on/off, run time and run days, saved in `settings.json`. | settings | JSON file | Defaults 2016-01-01, latest, on, 17:30, Mon–Fri; bad file loads defaults | Implemented |
| SRD-BKT-001.005 | FO-BKT-001 | Must | The download plan asks for 1d in one request per stock, then 3m in 3-month chunks newest first, skipping ranges already saved. | settings, saved ranges | request list | Chunks before a stock's first available bar are skipped | Implemented |
| SRD-BKT-001.006 | FO-BKT-001 | Must | The downloader runs the plan in the background, waits and retries a failed request up to 3 times, then marks the stock failed and continues. | request list | bars, progress | Own TWS client ID; IBKR pacing limit respected | Implemented |
| SRD-BKT-001.007 | FO-BKT-001 | Must | A stop request ends the run after the current request; the next run continues from the saved files. | stop | stopped run | No saved month is downloaded twice | Implemented |
| SRD-BKT-001.008 | FO-BKT-001 | Must | Delta fill asks each stock for the days since its last saved bar, at least 2 days, and skips a stock whose last saved bar is the last session. | saved ranges | request list | Runs only when end date is latest; reopened by user 2026-10-29 | Implemented |
| SRD-BKT-001.009 | FO-BKT-001 | Must | Auto delta is due at the set US/Eastern time on set days, and a missed run is due at the next app start. | settings, last delta, clock | due yes/no | Off when auto delta is off or end date is fixed | Implemented |
| SRD-BKT-001.010 | FO-BKT-001 | Must | Clear deletes all saved candles and download state but keeps `settings.json`. | click | empty store | Refused while a download runs | Implemented |
| SRD-BKT-001.011 | FO-BKT-001 | Should | Stats give stock count, 1d and 3m bar counts, first and last date, disk size and last delta time. | store | stats | Read from Parquet metadata, not full files | Implemented |
| SRD-BKT-001.012 | FO-BKT-001 | Must | Every 3m save rebuilds that stock's 15m bars for each year touched, five 3m bars per 15m bar from 09:30 ET. | saved 3m year file | `15m/<SYM>/<YYYY>.parquet` | Approved by user 2026-10-29; not downloaded from TWS | Implemented |
| SRD-BKT-001.013 | FO-BKT-001 | Must | Every 1d save rebuilds that stock's 1w bars, Monday to Friday, dated by the Monday, with a day count. | saved 1d file | `1w/<SYM>.parquet` | Approved by user 2026-10-29; unfinished week kept with its day count | Implemented |
| SRD-BKT-001.014 | FO-BKT-001 | Must | 15m and 1w files that are missing or older than their source are built in the background at app start. | 3m and 1d files | built files, stock count logged | Approved by user 2026-10-29; Clear also removes them | Implemented |

## FO-BKT-002 — Backtest Engine (Phase 0 · Foundation)

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-BKT-002.001 | FO-BKT-002 | Must | A run plan is a frozen, versioned dataclass that saves to JSON and loads back equal. | plan / JSON | JSON / plan | `schema` 1; unknown keys ignored | Implemented |
| SRD-BKT-002.002 | FO-BKT-002 | Must | Validation returns a list of plain error messages for a bad plan. | plan | messages | Empty list = valid; unknown schema is an error | Implemented |
| SRD-BKT-002.003 | FO-BKT-002 | Must | List values of capital, allocation % and per-trade % expand into a grid of variants. | plan | variants | More than 64 variants is a validation error | Implemented |
| SRD-BKT-002.004 | FO-BKT-002 | Must | The universe resolves to a sorted list of stocks from S&P 500, sectors or names, then add, then remove. | spec, universe records | symbols | Records are passed in; no network call | Implemented |
| SRD-BKT-002.005 | FO-BKT-002 | Must | The step cache stores a frame under a sha256 key of step, step version and params, written atomically. | key parts, frame | Parquet file | A miss returns nothing; a crash never leaves a half file | Implemented |
| SRD-BKT-002.006 | FO-BKT-002 | Should | Cache cleanup deletes entries unused for 30 days, then the oldest until the size limit is met. | cache folder | freed bytes | Default limit 5 GB | Implemented |
| SRD-BKT-002.007 | FO-BKT-002 | Must | A results store in `results.db` keeps each run with its plan, status and start and end time. | run | rows | SQLite; one row per run | Implemented |
| SRD-BKT-002.008 | FO-BKT-002 | Must | The estimate gives the stock count, stocks missing 1d or 3m candles for the period, and the cached and to-run days of Step 1. | plan, store, cache | estimate | Reads metadata only | Implemented |
| SRD-BKT-002.009 | FO-BKT-002 | Should | A command line runs `estimate` and `run` on a plan JSON file. | plan file | printed summary | `python -m us_swing.backtest.cli` | Implemented |

## FO-BKT-002 — Backtest Engine (Phase 1 · Step 1 Stocks)

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-BKT-002.010 | FO-BKT-002 | Must | Step 1 days are the SPY 1d dates inside the period, or all stocks' dates when SPY is missing. | store, period | days | SPY is also passed to the screener as the benchmark | Implemented |
| SRD-BKT-002.011 | FO-BKT-002 | Must | For each day, each stock gets its last 600 1d bars up to that day and the preset's pre-filter, screeners and group or weight logic run without the AI stage. | preset, bars | passed, score per stock | Same code path as the live screener | Implemented |
| SRD-BKT-002.012 | FO-BKT-002 | Must | Each day's passing stocks with score are cached in one file per day, keyed by the preset rules, the stock list and the step version. | day result | cache file | Scores can depend on other stocks (RS rank), so the key holds the whole stock list | Implemented |
| SRD-BKT-002.013 | FO-BKT-002 | Must | Days already cached are not computed again; top N and the AI tick are not part of the key. | plan, cache | days to run | — | Implemented |
| SRD-BKT-002.014 | FO-BKT-002 | Must | The daily list joins all days as date, symbol, score and rank, and can keep only the top N per day. | day files, N | frame | Rank 1 = highest score, ties by symbol; N 0 = all | Implemented |
| SRD-BKT-002.015 | FO-BKT-002 | Must | Days are computed in a process pool with progress as days done of total, and cancel stops between days. | days | day results, progress | Finished days stay cached after cancel | Implemented |
| SRD-BKT-002.016 | FO-BKT-002 | Must | A weekly preset or a ticked AI ranking stops the run with a plain message. | plan | error | AI ranking (D4) is built in a later phase | Implemented |
| SRD-BKT-002.018 | FO-BKT-002 | Must | A preset with an enabled RS rule stops Step 1 and the data check with one plain sentence when SPY is not in the store. | preset, store | message | User 2026-10-29: backtest data is S&P 500 only, SPY is not downloaded | Implemented |
| SRD-BKT-002.019 | FO-BKT-002 | Must | An error inside a worker process reaches the user once, in plain text, with the day. | error | message | Fixes the doubled RS message | Implemented |
| SRD-BKT-002.017 | FO-BKT-002 | Must | `BacktestService` gives estimate and Step 1 run with progress and cancel, and records each run in the results store. | plan | estimate, daily list | Used by GUI and CLI | Implemented |

## FO-BKT-002 — Backtest Engine (Phase 2 · Step 2 Signals)

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-BKT-002.020 | FO-BKT-002 | Must | `core/expr` re-exports the live condition parser so the backtest uses the same parser. | — | `parse()` | Live code unchanged (user chose re-export 2026-10-29) | Implemented |
| SRD-BKT-002.021 | FO-BKT-002 | Must | Each of the 10 functions gives a series per timeframe whose value at a bar equals the live value on the closed bars up to that bar. | frames, args | series | Parity checked per function and timeframe | Implemented |
| SRD-BKT-002.022 | FO-BKT-002 | Must | Values are read at each 3m bar close: 3m and 15m bars once closed, 1d bars from the next session, 1w bars from the next week. | series | aligned values | No look-ahead | Implemented |
| SRD-BKT-002.023 | FO-BKT-002 | Must | Price reads candles like live: on 15m "current" is the forming bar built from 3m bars and any other candle is the bar before. | 3m bars | prices | 1d and 1w have no forming bar, as in live | Implemented |
| SRD-BKT-002.024 | FO-BKT-002 | Must | VWAP on 3m and 15m resets at the start of each session. | bars | VWAP | User chose reset 2026-10-29; live adds up 30 days (reported) | Implemented |
| SRD-BKT-002.025 | FO-BKT-002 | Must | A value that cannot be computed (NaN) makes its comparison false instead of stopping the run. | values | false | Live raises an error and skips the bar | Implemented |
| SRD-BKT-002.026 | FO-BKT-002 | Must | Entry and exit conditions give periods (start, end, close at start, values) per stock per strategy, only on bars inside the strategy's hours and days. | conditions, bars | periods | Hours as live: start ≤ bar close < end, US/Eastern | Implemented |
| SRD-BKT-002.027 | FO-BKT-002 | Must | A condition that uses PNL is flagged and PNL counts as unknown (false) in Step 2. | condition | flag | Step 3 re-checks per held bar; live PNL is always 0 (reported) | Implemented |
| SRD-BKT-002.028 | FO-BKT-002 | Must | Step 2 runs on the stocks in Step 1's top-N list that the strategy accepts, cached per strategy and stock, in a process pool with progress and cancel. | daily list, strategies | cache files | Key: condition text, hours, days, period, candle coverage, step version | Implemented |
| SRD-BKT-002.029 | FO-BKT-002 | Must | Strategies are read from the live strategy store by name, and `BacktestService.run_signals()` and the CLI give the signal periods. | plan | signal list | A missing strategy name is a plain error | Implemented |
