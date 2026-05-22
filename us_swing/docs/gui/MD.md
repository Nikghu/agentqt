# Module Decomposition — GUI Module (GUI)

**Document ID:** MD-GUI
**Version:** 1.3.0
**Traces To:** SRD-GUI v2.8.0 / DD-GUI v1.6.0
**Status:** Draft
**Last Updated:** 2026-05-22
**Project:** US Swing Trading System

> v1.3.0: MD-GUI-013.* (Strategy Builder Dialog, 1 module) and MD-GUI-014.* (Active Cycles Panel, 3 modules) added.

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

---

## Cross-FO Modifications for FO-GUI-012

FO-GUI-012 modifies existing modules rather than creating new files. The new `LiveTickWorker` module is defined in the EXE tool (MD-EXE-008.001.M01). The table below documents which GUI modules change and what SRDs drive each change.

| Module ID | File | Change Required | SRD |
|---|---|---|---|
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | Add `LiveTickWorker` lifecycle (`_on_connect_ok`, `disconnect_feed`); add `_sync_tick_subscriptions()`; add `_on_mktwatch_tick`, `_on_watchlist_tick`, `_on_position_tick`, `_on_tick_sub_failed` slots; add `_YAHOO_TO_IBKR` constant and `_make_stk_contract()` helper; add `_watch_prev_close` and `_sp500_cache` attributes; add one-shot `_fetch_mw_prev_close_once()`; remove `_MarketWatchWorker`, `_watch_timer`, `_refresh_market_watch()`, `_on_watch_data()`, `_mw_worker`; remove `_wl_timer` repeating-poll path (keep one-shot load). | SRD-GUI-012.001–007 |
| MD-GUI-006.001.M01 | `src/us_swing/gui/settings_panel.py` | Add "Tick Data Client ID" `QSpinBox` row to System tab, bound to `SystemConfig.ibkr_tick_client_id`. Follows same pattern as existing clientId spinboxes. | SRD-GUI-012.001 |
| — | `src/us_swing/gui/system_store.py` | Add `ibkr_tick_client_id: int = 14` field to `SystemConfig` dataclass. No migration needed — default value handles missing key on first load. | SRD-GUI-012.001 |

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
gui/app_service.py (FO-GUI-012 additions)
                             ← execution/live_tick_worker.py (LiveTickWorker),
                                universe/store.py (load_sp500),
                                ib_insync (Contract)
```

---

## FO-GUI-013 — Strategy Builder Dialog Modules

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP | Status |
|---|---|---|---|---|---|---|---|
| MD-GUI-013.001.M01 | SRD-GUI-013.001 — .014 | `src/us_swing/gui/strategy_builder_dialog.py` | `StrategyBuilderDialog(QDialog)` — frameless modal wizard with 5 pages (Info, Triggers, Scheduler, Execution, Risk); owns indicator catalogue, `StrategyConfig` dataclass, `load_strategies()`/`save_strategies()` registry I/O, `commit()` helper; embeds `_ConditionSelectorDialog`, `_CondBubble`, `_StrategyInfoPage`, `_TriggersPage`, `_SchedulerPage`, `_SettingsPage`, `_RiskPage` | `StrategyBuilderDialog(registry, editing=None, parent=None)`, signal `saved(StrategyConfig)`; module-level `load_strategies() -> list[StrategyConfig]`, `save_strategies(configs)`, `commit(registry, cfg) -> list[StrategyConfig]`, `StrategyConfig` dataclass | `PyQt6` (`QDialog`, `QTreeWidget`, `QStackedWidget`, `QFormLayout`, `QComboBox`, `QLineEdit`, `QSpinBox`, `QDoubleSpinBox`, `QDateEdit`, `QTimeEdit`, `QCheckBox`, `QPushButton`, `QListWidget`), `theme.C`, `universe/store.py` (`load_sp500`), `dataclasses`, `json`, `pathlib` | No | Approved |

### Cross-Module Modifications for FO-GUI-013

| Module ID | File | Change Required | SRD |
|---|---|---|---|
| MD-GUI-004.001.M01 | `src/us_swing/gui/execution_panel.py` | Add an "Add Strategy" button and an "Edit" action on the strategy table that instantiate `StrategyBuilderDialog(registry, editing=…)` and connect its `saved` signal to refresh the strategy table. | SRD-GUI-013.001 |

---

## FO-GUI-014 — Active Cycles Panel Modules

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP | Status |
|---|---|---|---|---|---|---|---|
| MD-GUI-014.001.M01 | SRD-GUI-014.001, .003 — .005, .008 — .012 | `src/us_swing/gui/active_cycles_panel.py` | `ActiveCyclesPanel(QWidget)` — replaces right pane of `_ExecutionPanel`; owns `QTableView`, `_ActiveCyclesModel`, `_RowActionsDelegate`; subscribes to FO-EXE-011 pending-signal signals and FO-EXE-012 `TradeCycleEvent` bus via Qt-queued relay; hosts confirmation dialogs (Execute, Close); manages empty-state placeholder, scope sync, circuit-breaker delegate flag, inline-editor expand/collapse via `setSpan` + `setIndexWidget` | `ActiveCyclesPanel(cycle_query, cycle_cmd, pending_store, app_service, parent=None)`, `set_scope(user_id)` | `_active_cycles_model`, `_risk_editor_widget`, `PyQt6` (`QWidget`, `QTableView`, `QStyledItemDelegate`, `QTimer`, `QMessageBox`), `theme.C`, FO-EXE-011 `PendingSignalStore`, FO-EXE-012 `TradeCycleQuery`/`TradeCycleCommand`, `AppService` | No | Approved |
| MD-GUI-014.001.M02 | SRD-GUI-014.002, .004 | `src/us_swing/gui/active_cycles_model.py` | `_ActiveCyclesModel(QAbstractTableModel)` — unified row store for PENDING + cycle rows; `_Row` dataclass, `Col` IntEnum, `_by_key` index map; incremental `on_pending_*`/`on_cycle_*` handlers; contiguous-range `dataChanged` emission; cell formatting for state badge, PnL coloring; editor-row helpers (`_insert_editor_row`, `_remove_editor_row`) | `_ActiveCyclesModel(query, pending_store)`, `refresh()`, `on_pending_added(signal)`, `on_pending_removed(id)`, `on_cycle_opened(snap)`, `on_cycle_updated(snap)`, `on_cycle_state(snap)`, `on_cycle_closed(snap)`, `on_cycle_aborted(snap)`, `set_scope(uid)` | `PyQt6.QtCore.QAbstractTableModel`, `theme.C`, FO-EXE-012 `CycleSnapshot`, FO-EXE-011 `TradeSignal`, `dataclasses`, `enum.IntEnum` | No | Approved |
| MD-GUI-014.001.M03 | SRD-GUI-014.007 | `src/us_swing/gui/risk_editor_widget.py` | `_RiskEditorWidget(QWidget)` — inline editor for HSL / Target / Trail mode / Trail offset bound to a `CycleSnapshot`; spinbox ranges anchored to `snap.current_price` for local pre-validation; emits `saved(cycle_id, fields)` / `cancelled(cycle_id)`; renders inline error on `InvariantViolation` from server | `_RiskEditorWidget(snap)`, signals `saved(int, dict)` / `cancelled(int)`, method `show_error(msg)` | `PyQt6` (`QWidget`, `QDoubleSpinBox`, `QComboBox`, `QPushButton`, `QLabel`), `theme.C`, FO-EXE-012 `CycleSnapshot` | No | Approved |

### Cross-Module Modifications for FO-GUI-014

| Module ID | File | Change Required | SRD |
|---|---|---|---|
| MD-GUI-004.001.M01 | `src/us_swing/gui/execution_panel.py` | Remove the existing "Pending Signals" right pane widget tree. Replace with `ActiveCyclesPanel` inside the same `QSplitter` slot. Left "Filtered Stocks" pane unchanged. | SRD-GUI-014.001 |
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | Wire FO-EXE-011 `PendingSignalStore` and FO-EXE-012 `TradeCycleService` into AppService construction; expose `cycle_query`, `cycle_cmd`, `pending_store` properties consumed by `ActiveCyclesPanel`. Forward `circuit_breaker_changed(bool)` (FO-EXE-003) so the delegate's button-paint can react. | SRD-GUI-014.012 |

---

## File Tree for FO-GUI-013 + FO-GUI-014

```
us_swing/src/us_swing/gui/
├── strategy_builder_dialog.py            # MD-GUI-013.001.M01 (existing — working prototype)
├── active_cycles_panel.py                # MD-GUI-014.001.M01 (NEW)
├── active_cycles_model.py                # MD-GUI-014.001.M02 (NEW)
└── risk_editor_widget.py                 # MD-GUI-014.001.M03 (NEW)
```

> The Strategy Builder Dialog is already implemented as a single file (~1620 lines). Splitting into per-page submodules is a future refactor; the working prototype's monolithic layout is retained for this FO. The Active Cycles Panel is split into three files from the start because the model + delegate + editor benefit from clear file boundaries for testing.
