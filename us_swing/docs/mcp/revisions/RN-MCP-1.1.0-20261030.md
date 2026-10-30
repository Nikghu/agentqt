# Revision Note — RN-MCP-1.1.0-20261030

**Version:** 1.1.0
**Date:** 2026-10-30
**Tool:** MCP
**Artifact:** FO-MCP-007 / SRD-MCP-007.001–.010
**Type:** Feature

---

## Summary

The MCP tool now has its first code: a backtest-only MCP server over stdio (`python -m us_swing.mcp`), run as its own process. It exposes 8 `bt_` tools (catalog, estimate, run, status, cancel, summary, trades, compare) on `BacktestService`, and shares `results.db` with the app. Background runs are limited to 2 jobs and 30 minutes each.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MCP-007.001.M01 | `src/us_swing/mcp/backtest_tools.py`, `src/us_swing/mcp/__main__.py` | New: 8 `bt_` tools, plain error replies, stdio server |
| MD-MCP-007.004.M02 | `src/us_swing/mcp/jobs.py` | New: `JobManager` (2 jobs, 30 min limit, cancel, progress, run id) |
| — | `src/us_swing/backtest/service.py` | Added `get_run()` and `run_portfolio(started=callback)` |
| — | `src/us_swing/core/backtest_bridge.py` | Added `default_user_id()`: empty user_id = the app's first saved user |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MCP-007.001 | Stdio server `us_swing_backtest` registers the 8 backtest tools | Implemented |
| SRD-MCP-007.002 | `bt_catalog` lists presets, live strategies and S&P 500 sectors | Implemented |
| SRD-MCP-007.003 | `bt_estimate` returns stock count, missing data and errors for a plan | Implemented |
| SRD-MCP-007.004 | `bt_run` checks the plan and starts a background job, returns job id | Implemented |
| SRD-MCP-007.005 | `bt_status` returns job state, step, progress and run id; 30 min limit | Implemented |
| SRD-MCP-007.006 | `bt_cancel` stops a running job at the next progress step | Implemented |
| SRD-MCP-007.007 | `bt_summary` returns a saved run's plan and stats from `results.db` | Implemented |
| SRD-MCP-007.008 | `bt_trades` returns one variant's trades (limit 100, max 500) | Implemented |
| SRD-MCP-007.009 | `bt_compare` returns compare stats for 1 to 10 saved runs | Implemented |
| SRD-MCP-007.010 | Every tool returns a plain `{"error": ...}` on bad input, never a stack trace | Implemented |

---

## Design Decisions

- Backtest-only server, separate stdio process, not inside the app (user, 2026-10-30). This replaces the in-app design in FO-MCP-001.
- Core 8 tools only. `bt_validate_rule`, `bt_quick_from_screener`, `bt_day_log`, `bt_breakdown` deferred (TODO T74).
- Empty `user_id` uses the app's first saved user.

---

## Issues Resolved

None

---

## Test Coverage

8 UT-MCP-007.* tests Pass, including one real stdio session (UT-MCP-007.001.M01.T02). 144 backtest engine and 46 backtest GUI tests pass. ruff and mypy --strict clean on changed files. Real-data check: `bt_catalog` shows 4 presets, 3 strategies, 11 sectors; `bt_estimate` (AAPL, MSFT, NVDA, 2026-09-01 to 10-29) gives 0 missing and 42 sessions. User check in Claude Code pending.
