# Unit Test Case Document — MCP Server Module (MCP)

**Document ID:** UTCD-MCP
**Version:** 1.1.0
**Traces To:** MD-MCP v1.0.0
**Status:** Draft
**Last Updated:** 2026-10-30
**Project:** US Swing Trading System

> Tests written BEFORE implementation per process.md §7.

---

## Module: `mcp/server.py` — MCPServer

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MCP-001.001.M01.T01 | MD-MCP-001.001.M01 | Unit | Server registers all 9 tools on init | Construct MCPServer with mocks | 9 tools discoverable via FastMCP introspection | Draft |
| UT-MCP-001.001.M01.T02 | MD-MCP-001.001.M01 | Unit | Invalid JSON schema returns validation_error | Call `fetch_ohlcv` with `symbols="not_a_list"` | `{"error": "validation_error", "details": [...]}` | Draft |
| UT-MCP-001.001.M01.T03 | MD-MCP-001.001.M01 | Unit | Unknown user_id returns error | Call `get_positions` with `user_id=9999` | `{"error": "unknown_user", "user_id": 9999}` | Draft |
| UT-MCP-001.001.M01.T04 | MD-MCP-001.001.M01 | Unit | Unhandled exception returns internal_error | Mock service to raise `RuntimeError` | `{"error": "internal_error", "message": "..."}` logged as ERROR | Draft |
| UT-MCP-001.001.M01.T05 | MD-MCP-001.001.M01 | Edge | No stack trace in error response | Trigger internal error | Response contains no file paths or line numbers | Draft |

---

## Module: `mcp/tools/data_tools.py` — fetch_ohlcv & get_universe

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MCP-002.001.M01.T01 | MD-MCP-002.001.M01 | Unit | `fetch_ohlcv` delegates to DataEngine | `symbols=["AAPL"]` | `DataEngine.fetch("AAPL")` called; returns `{"fetched": {"AAPL": 252}}` | Draft |
| UT-MCP-002.001.M01.T02 | MD-MCP-002.001.M01 | Unit | `fetch_ohlcv` with multiple symbols | `symbols=["AAPL","MSFT"]` | Both fetched; result has both keys | Draft |
| UT-MCP-002.001.M01.T03 | MD-MCP-002.001.M01 | Unit | `get_universe` returns full list | Mock UniverseManager with 3 symbols | `{"symbols": [{"symbol": "AAPL", ...}, ...]}` with 3 items | Draft |

---

## Module: `mcp/tools/screener_tools.py` — run_screener & get_watchlist

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MCP-003.001.M01.T01 | MD-MCP-003.001.M01 | Unit | `run_screener` uses user's config when no override | `user_id=1, config_override=null` | `ScreenerEngine.run()` called with user's `ScreenerConfig` | Draft |
| UT-MCP-003.001.M01.T02 | MD-MCP-003.001.M01 | Unit | `run_screener` with config override | `user_id=1, config_override={...}` | `ScreenerEngine.run()` called with override config | Draft |
| UT-MCP-003.001.M01.T03 | MD-MCP-003.001.M01 | Unit | `get_watchlist` returns current watchlist | `user_id=1`; watchlist has 5 symbols | `{"watchlist": ["AAPL", "MSFT", ...]}` with 5 items | Draft |

---

## Module: `mcp/tools/analysis_tools.py` — get_signals

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MCP-004.001.M01.T01 | MD-MCP-004.001.M01 | Unit | `get_signals` returns pending signals for user | `user_id=1`; 2 pending signals | `{"signals": [...]}` with 2 items containing all required fields | Draft |
| UT-MCP-004.001.M01.T02 | MD-MCP-004.001.M01 | Unit | `get_signals` returns empty when no signals | `user_id=1`; no pending signals | `{"signals": []}` | Draft |

---

## Module: `mcp/tools/execution_tools.py` — get_positions, submit_order, get_daily_pnl

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MCP-005.001.M01.T01 | MD-MCP-005.001.M01 | Unit | `get_positions` returns non-CLOSED positions | `user_id=1`; 2 OPEN + 1 CLOSED | `{"positions": [...]}` with 2 items (CLOSED excluded) | Draft |
| UT-MCP-005.001.M01.T02 | MD-MCP-005.001.M01 | Unit | `submit_order` delegates to ExecutionRouter | `user_id=1, symbol="AAPL", side="BUY", quantity=100, order_type="MKT"` | `ExecutionRouter.route_signal()` called; `{"order_id": 123}` | Draft |
| UT-MCP-005.001.M01.T03 | MD-MCP-005.001.M01 | Unit | `submit_order` returns rejection when risk check fails | Signal that exceeds capital | `{"error": "rejected", "reason": "capital allocation limit..."}` | Draft |
| UT-MCP-005.001.M01.T04 | MD-MCP-005.001.M01 | Unit | `submit_order` respects paper/live mode | user.mode='paper' | `PaperEngine.simulate_fill()` called (not IBKR) | Draft |
| UT-MCP-005.001.M01.T05 | MD-MCP-005.001.M01 | Unit | `get_daily_pnl` returns P&L and trade count | `user_id=1`; daily_pnl=-500, 3 trades | `{"daily_pnl": -500.0, "trade_count": 3}` | Draft |

---

## Module: `mcp/tools/health_tools.py` — system_health

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MCP-006.001.M01.T01 | MD-MCP-006.001.M01 | Unit | `system_health` returns all required fields | No params | Response contains all 5 required keys with correct types | Draft |
| UT-MCP-006.001.M01.T02 | MD-MCP-006.001.M01 | Unit | `system_health` when broker disconnected | Mock broker_connected=False | `{"broker_connected": false, ...}` | Draft |

---

## Module: `mcp/backtest_tools.py`, `mcp/jobs.py` — Backtest tools (FO-MCP-007)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-MCP-007.001.M01.T01 | MD-MCP-007.001.M01 | Positive | Tools listed | server | the 8 bt_ tool names | Pass |
| UT-MCP-007.001.M01.T02 | MD-MCP-007.001.M01 | Integration | Real stdio session | python -m us_swing.mcp; bt_status "nope" | 8 tools listed; plain "No backtest job" error | Pass |
| UT-MCP-007.002.M01.T01 | MD-MCP-007.001.M01 | Positive | Catalog and estimate | fake presets, strategies, records; 3-name plan; plan without period | sorted lists; 3 stocks, 3 missing 3m; "Run plan is not valid" | Pass |
| UT-MCP-007.004.M01.T01 | MD-MCP-007.001.M01 | Negative | Run refusals | no strategy; 65 capitals; empty names; unknown job | plain error for each | Pass |
| UT-MCP-007.007.M01.T01 | MD-MCP-007.001.M01 | Positive | Summary, trades, compare | saved run with 4 trades; unknown ids | label and stats; last 2 trades; rows plus errors | Pass |
| UT-MCP-007.004.M02.T01 | MD-MCP-007.004.M02 | Positive | Job runs to done | fake service | state done, run id, Portfolio 4 of 4 | Pass |
| UT-MCP-007.006.M02.T01 | MD-MCP-007.004.M02 | Negative | Cancel and failure | cancel; failing Step 2 | cancelled with message; failed with step message | Pass |
| UT-MCP-007.005.M02.T01 | MD-MCP-007.004.M02 | Edge | Time and job limits | 2 jobs, third start, clock past limit | third refused; both stopped at the limit | Pass |
