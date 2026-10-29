# Functional Overview — Backtest Module (BKT)

**Document ID:** FO-BKT
**Version:** 1.0.0
**Status:** Draft
**Last Updated:** 2026-10-28
**Project:** US Swing Trading System

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
