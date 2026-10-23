# Revision Note — RN-EXE-1.34.0-20261023

**Tool:** EXE
**Version:** 1.34.0
**Date:** 2026-10-23
**Type:** feat
**Author:** Claude Opus 5.5 under user direction
**Phase:** FO-EXE-019 Strategy P&L History — P1 of the Execution screen redesign (FO-GUI-024)

---

## Summary

The new Execution screen shows a **Strategy P&L** chart for each strategy. The user asked that
past P&L come from stored data. Closed trades are already saved in `trade_cycles` with the
strategy name, close time and realized P&L, so no new table was added (user choice). This
phase adds the read path and the summary maths only; the chart comes in FO-GUI-024 P4.

## The change

| Area | Change |
|---|---|
| Read | `closed_for_strategy(strategy_id, *, since_iso, user_id)` on the repository, the `TradeCycleQuery` protocol and the service: CLOSED cycles of one strategy, oldest close first, no day cap. |
| Summary | New `trade_cycle/_pnl_history.py`: `StrategyPnlSummary` (running-total points, total, trades, win rate, average win / loss, max drawdown with its span, today) and `summarise(...)`. Cycles without realized P&L are skipped. |
| Index | `idx_trade_cycles_strategy_closed (strategy_id, closed_at)`. |
| App | `AppService.get_strategy_pnl(strategy_id, since_iso=None)` — viewing user as filter, ET market day as "today", empty summary and a `[Strategy]` log line on failure. |

**Cross-tool (INF):** `db/schema.create_schema` now also creates missing indexes of tables that
already exist. `metadata.create_all` only adds indexes when it creates a table, so without this
the new index would never reach the user's existing `candles.db`. Safe to repeat
(`checkfirst=True`).

## Notes

- History starts at the 2026-10-16 trade-data clear; older closed trades no longer exist.
- Deleting a strategy keeps its closed cycles (user choice); the P&L is simply not shown.
- The strategy id is its name. Renaming a strategy in Edit starts a fresh P&L history under the
  new name — not changed here; raised to the user.

## Tests

`tests/execution/test_strategy_pnl_history.py` — 14 tests (UT-EXE-019.*), real in-memory SQLite.
Execution suite 301 passed. `ruff` clean; `mypy --strict` clean on the touched files.
