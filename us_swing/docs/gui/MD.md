# Module Decomposition — GUI Module (GUI)

**Document ID:** MD-GUI
**Version:** 1.2.0
**Traces To:** SRD-GUI v2.6.0 / DD-GUI v1.4.0
**Status:** Draft
**Last Updated:** 2026-05-13
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
| MD-GUI-005.001.M01 | SRD-GUI-005.001–004 | `src/us_swing/gui/position_monitor_panel.py` | `PositionMonitorPanel(QWidget)` — carry-over positions, state colour coding, capital indicator, can-enter badge | `refresh()` | `execution/position_tracker.py`, `execution/risk_manager.py`, PyQt6 | No | Implemented |
| MD-GUI-006.001.M01 | SRD-GUI-006.001–005 | `src/us_swing/gui/settings_panel.py` | `SettingsPanel(QWidget)` — sub-tabs for Users, Risk, Strategies, Screeners, System config | — (event-driven) | `user/manager.py`, `config/settings.py`, `db/manager.py`, PyQt6 | No | Implemented |
| MD-GUI-007.001.M01 | SRD-GUI-007.001–004 | `src/us_swing/gui/log_viewer_panel.py` | `LogViewerPanel(QWidget)` — streaming log display, level/module/symbol filters, error highlighting, buffer management | — (event-driven) | `logging`, `queue`, PyQt6 | No | Implemented |
| MD-GUI-007.001.M02 | SRD-GUI-007.001 | `src/us_swing/gui/log_bridge.py` | `LogSignalEmitter(QObject)` — QueueHandler → Qt signal bridge for thread-safe log streaming | `new_log_entry` signal | `logging`, `queue`, PyQt6 | No | Implemented |
| MD-GUI-011.001.M01 | SRD-GUI-011.001–004 | `src/us_swing/gui/chart_panel.py` | `CandleChartPanel(QWidget)` — "📈 Chart" nav tab; symbol/timeframe/bars toolbar; TradingView Lightweight Charts v5 candlestick + volume histogram via `QWebEngineView`; offline JS bundle with CDN fallback | `showEvent()` (auto-refresh) | `AppService`, `PyQt6.QtWebEngineWidgets`, `theme.C`, `json`, `pathlib` | No | Implemented |
| MD-GUI-012.001.M01 | SRD-GUI-012.001–007, .011 | `src/us_swing/gui/ibkr_session.py` | `IBKRSession(QObject)` — owns one persistent `ib_insync.IB` instance on a dedicated `QThread` asyncio loop; subscribes `reqAccountUpdates` + `reqMktData`; debounces account events (50 ms) and coalesces tick events (250 ms); reconnect state machine with exponential backoff (2–30 s, ±20 % jitter, max 10 attempts); thread-safe `pyqtSignal` bridging to Qt main thread | Signals: `account_ready(AccountState, list[OpenPosition])`, `quotes_updated(list[dict])`, `connection_lost(str)`, `connection_restored()`. Methods: `start(host, port, client_id)`, `stop()`, `set_market_watch_symbols(list[str])`, `set_watchlist_symbols(list[str])` | `ib_insync`, `asyncio`, `PyQt6.QtCore`, `data/models.py` (`AccountState`, `OpenPosition`) | No | Draft |
| MD-GUI-012.001.M02 | SRD-GUI-012.003, .008–.012 | `src/us_swing/gui/app_service.py` | AppService bridge — owns one `IBKRSession`, wires its signals to existing public `account_updated` / `positions_updated` / `market_watch_updated` / `watchlist_updated` / `feed_status_changed`; deletes legacy `_AccountDataWorker`, `_MarketWatchWorker`, `_WatchlistQuoteWorker`, their three `QTimer`s and refresh methods; adds `_MarketWatchYfinanceWorker(QThread)` used **only** when `DISCONNECTED` (30 s timer) plus index-symbol carve-out path | Bridge slots `_on_session_account_ready`, `_on_session_quotes_updated`, `_on_session_connection_lost`, `_on_session_connection_restored` (private). Public signal contract unchanged. | `gui/ibkr_session.py`, `yfinance`, `PyQt6.QtCore`, existing AppService deps | No | Draft |

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
gui/ibkr_session.py          ← ib_insync, asyncio, PyQt6.QtCore, data/models.py
gui/app_service.py           ← ibkr_session.py (new), yfinance (fallback only),
                                PyQt6.QtCore, existing deps
```
