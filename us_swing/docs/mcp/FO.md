# Functional Overview — MCP Server Module (MCP)

**Document ID:** FO-MCP
**Version:** 1.1.0
**Traces To:** requirements.md §27
**Status:** Draft
**Last Updated:** 2026-10-30
**Project:** US Swing Trading System

---

## FO-MCP-001: MCP Server Interface

**Priority:** Must
**Source:** §27.1, §27.2

The system shall expose a Model Context Protocol (MCP) server that runs alongside the GUI, providing AI agent integration endpoints. MCP tools mirror core functionality — no separate business logic. Each tool delegates to the same service layer used by the GUI. The server handles JSON-schema validated requests, per-user scoping, and error responses.

### Acceptance Criteria

1. MCP server starts when the application starts and runs on a configurable port.
2. All 9 planned tools are registered and discoverable via MCP introspection.
3. Each tool call is scoped to a `user_id` parameter (where applicable).
4. Invalid requests return structured error responses (not exceptions).
5. MCP server and GUI can operate simultaneously without interference.

---

## FO-MCP-002: Data & Universe Tools

**Priority:** Must
**Source:** §27.2 (`fetch_ohlcv`, `get_universe`)

MCP tools for data operations:
- `fetch_ohlcv`: Fetch or update historical OHLCV data for one or more symbols. Delegates to `DataEngine`.
- `get_universe`: Return the current S&P 500 universe list from `UniverseManager`.

### Acceptance Criteria

1. `fetch_ohlcv` accepts symbol(s) and optional date range; returns fetched bar count.
2. `get_universe` returns list of all symbols with metadata (sector, name).
3. Both tools are read-safe (no side effects beyond data caching).

---

## FO-MCP-003: Screener & Watchlist Tools

**Priority:** Must
**Source:** §27.2 (`run_screener`, `get_watchlist`)

MCP tools for screening:
- `run_screener`: Run screening with specified config, return ranked results. Delegates to `ScreenerEngine`.
- `get_watchlist`: Return current day's watchlist symbols.

### Acceptance Criteria

1. `run_screener` accepts optional screener config override; defaults to active user's config.
2. `run_screener` returns list of symbols with composite scores.
3. `get_watchlist` returns current watchlist with max 20 symbols.

---

## FO-MCP-004: Analysis & Signal Tools

**Priority:** Must
**Source:** §27.2 (`get_signals`)

MCP tool for analysis:
- `get_signals`: Return pending entry/exit signals from `StrategyEngine` for the active user.

### Acceptance Criteria

1. Returns signals with: symbol, side (BUY/SELL), strategy_id, entry_price, stop_loss, target, recommended qty.
2. Only returns signals not yet acted upon.
3. Scoped to requesting user_id.

---

## FO-MCP-005: Execution & Position Tools

**Priority:** Must
**Source:** §27.2 (`get_positions`, `submit_order`, `get_daily_pnl`)

MCP tools for execution:
- `get_positions`: Return all open positions with state for the user.
- `submit_order`: Submit an entry/exit order for a symbol. Delegates to `ExecutionRouter`.
- `get_daily_pnl`: Return today's realised P&L for the user.

### Acceptance Criteria

1. `get_positions` returns positions with: symbol, qty, avg_entry, state, unrealised_pnl, mode.
2. `submit_order` validates via `RiskManager` before execution; returns order_id or rejection reason.
3. `submit_order` respects paper/live mode of the user.
4. `get_daily_pnl` returns total realised P&L as a float.

---

## FO-MCP-006: System Health Tool

**Priority:** Should
**Source:** §27.2 (`system_health`)

MCP tool for monitoring:
- `system_health`: Return system health status including broker connection, active subscriptions, data freshness, and error count.

### Acceptance Criteria

1. Returns structured health object with: broker_connected, active_subscriptions count, last_data_update timestamp, error_count_today, circuit_breaker_active.
2. Response time ≤ 500ms (no heavy computation).

---

## FO-MCP-007: Backtest Tools

**Priority:** Must
**Source:** `docs/backtest/Engine_plan.md` Phase 6; user choice 2026-10-30 (backtest-only stdio server, core 8 tools)

- The system shall run a backtest-only MCP server over stdio (`python -m us_swing.mcp`), separate from the app.
- The tools shall call `BacktestService` only, and share the step cache and `results.db` with the app.
- An agent shall be able to list inputs, check data, start a run, follow or cancel it, and read and compare results.

### Acceptance Criteria

1. `bt_catalog`, `bt_estimate`, `bt_run`, `bt_status`, `bt_cancel`, `bt_summary`, `bt_trades` and `bt_compare` are listed by MCP introspection.
2. A run started from MCP shows in the app's Reports tab.
3. Bad input returns `{"error": "<plain message>"}`, never a stack trace.
4. Limits: 64 variants per plan, 2 running jobs, 30 minutes per job.
