# Module Decomposition — GUI Module (GUI)

**Document ID:** MD-GUI
**Version:** 1.2.0
**Traces To:** SRD-GUI v2.6.0 / DD-GUI v1.3.0
**Status:** Draft
**Last Updated:** 2026-05-14
**Project:** US Swing Trading System

---

## GUI Modules

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP | Status |
|---|---|---|---|---|---|---|---|
| MD-GUI-001.001.M01 | SRD-GUI-001.001–004 | `src/us_swing/gui/main_window.py` | `MainWindow(QMainWindow)` — application shell, tab layout, status bar, geometry persistence, connection/circuit-breaker state | `set_active_user(user_id)`, `update_connection_status(connected)`, `on_circuit_breaker(active)` | All panel modules, `user/manager.py`, `config/settings.py`, PyQt6 | No | Implemented |
| MD-GUI-002.001.M01 | SRD-GUI-002.001–005 | `src/us_swing/gui/dashboard_panel.py` | `DashboardPanel(QWidget)` — position table, P&L summary, capital utilisation bar, trade history | `refresh()` | `execution/position_tracker.py`, `execution/circuit_breaker.py`, `db/manager.py`, PyQt6 | No | Implemented |
| MD-GUI-002.001.M02 | SRD-GUI-002.001–002 | `src/us_swing/gui/position_table_model.py` | `PositionTableModel(QAbstractTableModel)` — data model for position table with colour-coded P&L and state | `refresh()`, `data()`, `rowCount()`, `columnCount()` | `execution/position_tracker.py`, PyQt6 | No | Implemented |
| MD-GUI-003.001.M01 | SRD-GUI-003.001–005 | `src/us_swing/gui/screener_panel.py` | `ScreenerPanel(QWidget)` — filter toggles, parameter controls, run button, results table, add-to-watchlist | — (event-driven) | `screener/engine.py`, `screener/config.py`, `user/manager.py`, PyQt6 | No | Approved |
| MD-GUI-004.001.M01 | SRD-GUI-004.001–006 | `src/us_swing/gui/execution_panel.py` | `ExecutionPanel(QWidget)` — entry rows with override qty, execute button, paper/live toggle, exit controls, circuit breaker banner | — (event-driven) | `execution/execution_router.py`, `execution/risk_manager.py`, `execution/position_tracker.py`, `user/manager.py`, PyQt6 | No | Implemented |
| MD-GUI-004.001.M02 | SRD-GUI-004.009 | `src/us_swing/gui/app_service.py` | `_IBKRLiveSession(QThread)` — persistent IBKR market-data session; owns IB() in a dedicated asyncio event loop; `subscribe_symbols` / `unsubscribe_symbols` are thread-safe via `run_coroutine_threadsafe`; emits `price_tick(symbol, price)` per tick; auto-reconnects with exponential backoff | `subscribe_symbols(set[str])`, `unsubscribe_symbols(set[str])`, `request_stop()`, `price_tick` signal | `ib_insync`, `asyncio`, PyQt6 | No | Implemented |
| MD-GUI-005.001.M01 | SRD-GUI-005.001–004 | `src/us_swing/gui/position_monitor_panel.py` | `PositionMonitorPanel(QWidget)` — carry-over positions, state colour coding, capital indicator, can-enter badge | `refresh()` | `execution/position_tracker.py`, `execution/risk_manager.py`, PyQt6 | No | Implemented |
| MD-GUI-006.001.M01 | SRD-GUI-006.001–005 | `src/us_swing/gui/settings_panel.py` | `SettingsPanel(QWidget)` — sub-tabs for Users, Risk, Strategies, Screeners, System config | — (event-driven) | `user/manager.py`, `config/settings.py`, `db/manager.py`, PyQt6 | No | Implemented |
| MD-GUI-007.001.M01 | SRD-GUI-007.001–004 | `src/us_swing/gui/log_viewer_panel.py` | `LogViewerPanel(QWidget)` — streaming log display, level/module/symbol filters, error highlighting, buffer management | — (event-driven) | `logging`, `queue`, PyQt6 | No | Implemented |
| MD-GUI-007.001.M02 | SRD-GUI-007.001 | `src/us_swing/gui/log_bridge.py` | `LogSignalEmitter(QObject)` — QueueHandler → Qt signal bridge for thread-safe log streaming | `new_log_entry` signal | `logging`, `queue`, PyQt6 | No | Implemented |
| MD-GUI-011.001.M01 | SRD-GUI-011.001–004 | `src/us_swing/gui/chart_panel.py` | `CandleChartPanel(QWidget)` — "📈 Chart" nav tab; symbol/timeframe/bars toolbar; TradingView Lightweight Charts v5 candlestick + volume histogram via `QWebEngineView`; offline JS bundle with CDN fallback | `showEvent()` (auto-refresh) | `AppService`, `PyQt6.QtWebEngineWidgets`, `theme.C`, `json`, `pathlib` | No | Implemented |

---

## Module Dependency Graph

```
gui/main_window.py           ← all panel modules, user/manager.py, config/settings.py
gui/dashboard_panel.py       ← position_table_model.py, execution/position_tracker.py,
                                execution/circuit_breaker.py, db/manager.py
gui/position_table_model.py  ← execution/position_tracker.py
gui/screener_panel.py        ← screener/engine.py, screener/config.py, user/manager.py
gui/execution_panel.py       ← execution/execution_router.py, execution/risk_manager.py,
                                execution/position_tracker.py, user/manager.py
gui/position_monitor_panel.py ← execution/position_tracker.py, execution/risk_manager.py
gui/settings_panel.py        ← user/manager.py, config/settings.py, db/manager.py
gui/log_viewer_panel.py      ← log_bridge.py
gui/log_bridge.py            ← logging, queue
gui/chart_panel.py           ← app_service.py, theme.py, PyQt6.QtWebEngineWidgets,
                                json, pathlib, resources/lightweight-charts.standalone.production.js
```
