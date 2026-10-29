# Functional Overview — Backtest Module (BKT)

**Document ID:** FO-BKT
**Version:** 1.1.0
**Status:** Draft
**Last Updated:** 2026-10-29
**Project:** US Swing Trading System

> v1.1.0: FO-BKT-002 added — backtest engine (Phase 0 and 1 scope).
> v1.0.0: FO-BKT-001 added — backtest candle data store and IBKR downloader.

---

## FO-BKT-001: Backtest Data Store and Downloader

**Status:** Approved (user, 2026-10-28)
**Priority:** Must
**Depends on:** FO-INF-002 (candle data sync), universe S&P 500 list
**Source:** User picked Option A, 1d + 3m, Parquet in `~/.usswing/backtest/`, US/Eastern time from https://claude.ai/artifact/NWMti5JCJk1C36bXAw4Z71 on 2026-10-28.

The system shall keep a separate history of 1d and 3m candles for all S&P 500 stocks, downloaded from IBKR, for later backtesting. The live `candles.db` is never touched.

- The system shall store 1d and 3m candles as Parquet files under `~/.usswing/backtest/`.
- The system shall keep 15m and 1w candles built from the saved 3m and 1d candles, so they are always available (added by user 2026-10-29).
- The system shall download the range between a start date and an end date (or the latest trading day).
- The system shall download 1d first, then 3m newest years first, and resume after a stop or TWS restart.
- The system shall never save the unfinished candles of the current trading day.
- The system shall add new trading days automatically at a set US/Eastern time (auto delta), and catch up missed days.
- The system shall clear all backtest candles on request, keeping the settings.

### Acceptance Criteria

1. A stopped download continues from where it stopped, without downloading saved months again.
2. 1d and 3m candles for a stock can be read back for any date in the range.
3. Clear removes backtest data only; `candles.db` is unchanged.

---

## FO-BKT-002: Backtest Engine

**Status:** Approved (user, 2026-10-29 — Phase 0 and Phase 1 scope)
**Priority:** Must
**Depends on:** FO-BKT-001 (backtest data store), FO-SCR presets (screener replay)
**Source:** `Engine_plan.md` §1–§5, locked decisions D1–D9 (user, 2026-10-29). User asked for minimal Phase 0 and Phase 1 requirements, approved for code on 2026-10-29.

The system shall run a saved screener and the user's live strategies over history in four cached steps (Stocks, Signals, Portfolio, Report), headless behind one `BacktestService`. Phase 0 and Phase 1 cover the run plan, the data check and Step 1 (Stocks).

- The system shall describe a run in a versioned run plan saved as JSON, and expand list values into at most 64 variants.
- The system shall pick the stocks from S&P 500, sectors or names, with add and remove on top.
- The system shall check, before every run, which stocks miss 1d or 3m candles for the period.
- The system shall cache each step's output by a key of its inputs, so unchanged steps are reused.
- The system shall replay the screener preset on each trading day using only candles up to that day's close.
- The system shall give, for each day, the stocks that passed with score and rank; the list made on day D is for use on day D+1.
- The system shall be usable from a command line as well as the GUI.

### Acceptance Criteria

1. A run plan saved and loaded again is equal to the original.
2. Running Step 1 twice computes nothing the second time; changing only top N computes nothing.
3. The Step 1 list for one day equals what the screener's rule stages give on the same candles.
