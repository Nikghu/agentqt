# Module Decomposition — MCP Server Module (MCP)

**Document ID:** MD-MCP
**Version:** 1.1.0
**Traces To:** SRD-MCP v1.0.0 / DD-MCP v1.0.0
**Status:** Draft
**Last Updated:** 2026-10-30
**Project:** US Swing Trading System

---

## MCP Modules

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP | Status |
|---|---|---|---|---|---|---|---|
| MD-MCP-001.001.M01 | SRD-MCP-001.001–004 | `src/us_swing/mcp/server.py` | `MCPServer` — FastMCP wrapper, tool registration, lifecycle management, request validation, error handling | `start()`, `stop()` | `fastmcp`, `jsonschema`, all service modules | Yes — MCP server itself | Draft |
| MD-MCP-002.001.M01 | SRD-MCP-002.001–002 | `src/us_swing/mcp/tools/data_tools.py` | `fetch_ohlcv` and `get_universe` tool handlers | `fetch_ohlcv()`, `get_universe()` | `data_engine/engine.py`, `universe/manager.py` | Yes | Draft |
| MD-MCP-003.001.M01 | SRD-MCP-003.001–002 | `src/us_swing/mcp/tools/screener_tools.py` | `run_screener` and `get_watchlist` tool handlers | `run_screener()`, `get_watchlist()` | `screener/engine.py`, `screener/config.py`, `user/manager.py` | Yes | Draft |
| MD-MCP-004.001.M01 | SRD-MCP-004.001 | `src/us_swing/mcp/tools/analysis_tools.py` | `get_signals` tool handler | `get_signals()` | `analysis/strategy_engine.py` | Yes | Draft |
| MD-MCP-005.001.M01 | SRD-MCP-005.001–003 | `src/us_swing/mcp/tools/execution_tools.py` | `get_positions`, `submit_order`, `get_daily_pnl` tool handlers | `get_positions()`, `submit_order()`, `get_daily_pnl()` | `execution/execution_router.py`, `execution/position_tracker.py`, `execution/circuit_breaker.py`, `user/manager.py` | Yes | Draft |
| MD-MCP-006.001.M01 | SRD-MCP-006.001 | `src/us_swing/mcp/tools/health_tools.py` | `system_health` tool handler | `system_health()` | `monitoring/health.py`, `broker/client.py` | Yes | Draft |
| MD-MCP-007.001.M01 | SRD-MCP-007.001 | `src/us_swing/mcp/backtest_tools.py`, `mcp/__main__.py` | The 8 backtest tools, plain error replies and the stdio server | `BacktestTools`, `build_server()`, `default_tools()` | `backtest.service`, `core.backtest_bridge`, `mcp` (FastMCP) | Yes | Implemented |
| MD-MCP-007.004.M02 | SRD-MCP-007.004 | `src/us_swing/mcp/jobs.py` | Background run jobs: limit 2, 30 minute stop, cancel, progress and run id | `JobManager`, `Job` | `backtest.service` | No | Implemented |

---

## Module Dependency Graph

```
mcp/server.py             ← fastmcp, jsonschema, all tool modules
mcp/tools/data_tools.py   ← data_engine/engine.py, universe/manager.py
mcp/tools/screener_tools.py ← screener/engine.py, screener/config.py, user/manager.py
mcp/tools/analysis_tools.py ← analysis/strategy_engine.py
mcp/tools/execution_tools.py ← execution/execution_router.py, execution/position_tracker.py,
                                execution/circuit_breaker.py, user/manager.py
mcp/tools/health_tools.py   ← monitoring/health.py, broker/client.py
```

---

## JSON Schema Files

| File | Tool | Purpose |
|---|---|---|
| `mcp/schemas/fetch_ohlcv.json` | `fetch_ohlcv` | Validate symbols array, optional date range |
| `mcp/schemas/get_universe.json` | `get_universe` | Empty object validation |
| `mcp/schemas/run_screener.json` | `run_screener` | Validate user_id, optional config_override |
| `mcp/schemas/get_watchlist.json` | `get_watchlist` | Validate user_id |
| `mcp/schemas/get_signals.json` | `get_signals` | Validate user_id |
| `mcp/schemas/get_positions.json` | `get_positions` | Validate user_id |
| `mcp/schemas/submit_order.json` | `submit_order` | Validate user_id, symbol, side, quantity, order_type |
| `mcp/schemas/get_daily_pnl.json` | `get_daily_pnl` | Validate user_id |
| `mcp/schemas/system_health.json` | `system_health` | Empty object validation |
