# Module Decomposition — GUI Module (GUI)

**Document ID:** MD-GUI
**Version:** 1.7.0
**Traces To:** SRD-GUI v2.16.0 / DD-GUI v1.7.0
**Status:** Draft
**Last Updated:** 2026-09-17
**Project:** US Swing Trading System

> v1.18.0: MD-GUI-022.001.M01 (screener_views.py) added; MD-GUI-003.001.M01 hosts the views.
> v1.17.0: MD-GUI-018.008.M04 (sidebar.py Connections panel) added; MD-GUI-018.005.M03 drops the title bar feed toggle.
> v1.16.0: MD-GUI-021.001.M01 (settings_panel.py section list) added.
> v1.15.0: MD-GUI-020.001.M01 (chart_workspace.py) added.
> v1.14.0: MD-GUI-019.001.M01 (side_panels.py) added; MD-GUI-019.006.M02 (dashboard exit drawer) and MD-GUI-019.002.M03 (main_window panels) extend existing files.
> v1.13.0: MD-GUI-018.001.M01 (sidebar.py), MD-GUI-018.006.M02 (reveal.py) added; MD-GUI-018.005.M03 covers main_window.py shell changes.
> v1.12.0: MD-GUI-017.001.M02 (theme.py Carbon extension) and MD-GUI-017.003.M01 (icons.py) added for the Carbon theme (SRD-GUI-017.001, .002, .005).
> v1.11.0: MD-GUI-004.001.M03 (intraday_cleanup.py) added; MD-GUI-004.001.M01 extended for startup cleanup (SRD-GUI-004.013).
> v1.10.0: MD-GUI-004.001.M02 (manual_picks_store.py) added; MD-GUI-004.001.M01 extended for manual picks (SRD-GUI-004.010–.012).
> v1.9.0: MD-GUI-004.001.M01 extended — Execution feed skips unassigned or missing presets (SRD-GUI-004.009, ISS-GUI-0004).
> v1.8.0: MD-GUI-006.001.M01 extended — weekly candles built from daily in `app_service.py` (SRD-GUI-006.019, ISS-GUI-0003).
> v1.7.0: Cross-module rows added for SRD-GUI-013.016–.019 and SRD-GUI-014.016–.018 — Short Trade Direction (FO-EXE-018) GUI surfaces.

> v1.6.0: MD-GUI-004.001.M01 extended — live tick worker watchdog in AppService (SRD-GUI-012.008–009).

> v1.5.0: Cross-module rows added for SRD-GUI-014.014 (AppService event_stream + ActiveCyclesPanel wired into _ExecutionPanel as "Active Trades" tab).
> v1.4.0: Cross-module rows added for SRD-GUI-013.015 (Reset Strategy action) and SRD-GUI-014.013 (Rex column).
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
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | Add the tick watchdog: `_tick_watchdog` QTimer plus `_start_tick_worker()`, `_on_tick_worker_finished()`, `_check_tick_health()`, `_warn_if_ticks_stale()`; stamp `_last_tick_at` in `_record_market_price`; stop the watchdog in `disconnect_feed`; emit tick failures to the GUI log panel from `_on_tick_sub_failed`. `live_tick_worker.py` is unchanged. | SRD-GUI-012.008–009 |
| MD-GUI-006.001.M01 | `src/us_swing/gui/settings_panel.py` | Add "Tick Data Client ID" `QSpinBox` row to System tab, bound to `SystemConfig.ibkr_tick_client_id`. Follows same pattern as existing clientId spinboxes. | SRD-GUI-012.001 |
| — | `src/us_swing/gui/system_store.py` | Add `ibkr_tick_client_id: int = 14` field to `SystemConfig` dataclass. No migration needed — default value handles missing key on first load. | SRD-GUI-012.001 |
| MD-GUI-006.001.M01 | `src/us_swing/gui/app_service.py` | Add `_rebuild_weekly_from_daily(conn, symbol)`; `_download_all` and `_download_benchmark` stop requesting IBKR `1 week` bars and rebuild `price_1w` per symbol after its daily bars are saved. | SRD-GUI-006.019 |
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | `get_latest_screener_results()` skips result folders whose preset is not found or has an empty `assigned_to`. | SRD-GUI-004.009 |
| MD-GUI-004.001.M02 | `src/us_swing/gui/manual_picks_store.py` (new) | `load_manual_picks(user_id)`, `save_manual_picks(user_id, symbols)` — per-user JSON, atomic write. | SRD-GUI-004.010 |
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | `add_manual_pick()`, `remove_manual_pick()`, `_manual_pick_entries()`, `_refresh_after_pick_change()`; picks lead `get_latest_screener_results()`; ledger records picks apart; empty list updates `_filtered_symbols`; `ScreenerApprovedEvent` skipped for pick changes. | SRD-GUI-004.010, .012 |
| MD-GUI-004.001.M01 | `src/us_swing/gui/execution_panel.py` | Pick box + "+ Add" in `_FilteredStocksPane`; `_PinnedPicksProxy`; pick rows in `_FilteredStocksModel`; ✕ click removes. | SRD-GUI-004.011 |
| MD-GUI-004.001.M03 | `src/us_swing/gui/intraday_cleanup.py` (new) | `remove_stale_intraday(db_path, keep, idle_days) -> list[str]` — finds and deletes stale stocks' rows in price_1m/3m/15m. | SRD-GUI-004.013 |
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | `_cleanup_stale_intraday(entries)` runs first in `_boot_candle_check()`; keep-set = Filtered Stocks + open trade cycles + positions. | SRD-GUI-004.013 |

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
- **Status:** Approved

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP | Status |
|---|---|---|---|---|---|---|---|
| MD-GUI-013.001.M01 | SRD-GUI-013.001 — .014 | `src/us_swing/gui/strategy_builder_dialog.py` | `StrategyBuilderDialog(QDialog)` — frameless modal wizard with 5 pages (Info, Triggers, Scheduler, Execution, Risk); owns indicator catalogue, `StrategyConfig` dataclass, `load_strategies()`/`save_strategies()` registry I/O, `commit()` helper; embeds `_ConditionSelectorDialog`, `_CondBubble`, `_StrategyInfoPage`, `_TriggersPage`, `_SchedulerPage`, `_SettingsPage`, `_RiskPage` | `StrategyBuilderDialog(registry, editing=None, parent=None)`, signal `saved(StrategyConfig)`; module-level `load_strategies() -> list[StrategyConfig]`, `save_strategies(configs)`, `commit(registry, cfg) -> list[StrategyConfig]`, `StrategyConfig` dataclass | `PyQt6` (`QDialog`, `QTreeWidget`, `QStackedWidget`, `QFormLayout`, `QComboBox`, `QLineEdit`, `QSpinBox`, `QDoubleSpinBox`, `QDateEdit`, `QTimeEdit`, `QCheckBox`, `QPushButton`, `QListWidget`), `theme.C`, `universe/store.py` (`load_sp500`), `dataclasses`, `json`, `pathlib` | No | Approved |

### Cross-Module Modifications for FO-GUI-013

| Module ID | File | Change Required | SRD |
|---|---|---|---|
| MD-GUI-004.001.M01 | `src/us_swing/gui/execution_panel.py` | Add an "Add Strategy" button and an "Edit" action on the strategy table that instantiate `StrategyBuilderDialog(registry, editing=…)` and connect its `saved` signal to refresh the strategy table. | SRD-GUI-013.001 |
| MD-GUI-004.001.M01 | `src/us_swing/gui/execution_panel.py` | Add a Reset icon to each `_StrategyTablePane` row that opens a `QMessageBox` confirmation and on confirm calls `app.rex_counters.reset(strategy_id)`. Wire `app.rex_counters` from `AppService`. Update the `rex_count` `QSpinBox` tooltip in `_SettingsPage` to "Re-execution count: extra entries per stock beyond the first (0 = first entry only)". | SRD-GUI-013.015 |
| MD-GUI-013.001.M01 | `src/us_swing/gui/strategy_builder_dialog.py` | Add `_direction_combo` (Long / Short) to the execution form with load/save of `direction`; `has_open_trades` ctor flag disables it with a tooltip; amber no-stop note on the Risk page driven by direction + stop-loss toggle; `_paint_direction` colours the combo text green / red. | SRD-GUI-013.016, .017, .018, .020 |
| MD-GUI-004.001.M01 | `src/us_swing/gui/execution_panel.py` + `src/us_swing/gui/app_service.py` | Pass `has_open_trades` to `StrategyBuilderDialog` on Edit from the new `AppService.has_live_or_pending_trades(name)`, which covers open cycles and signals awaiting the user. | SRD-GUI-013.017, .021 |
| MD-GUI-004.001.M02 | `src/us_swing/gui/strategy_table_model.py` | Add `COL_DIRECTION` after `COL_TRADE_TYPE` (later constants shift by one) with header `Direction`, `Long` / `Short` cell text and a green / red foreground. | SRD-GUI-013.019, .020 |

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
| MD-GUI-004.001.M01 | `src/us_swing/gui/execution_panel.py` | Replace the "Pending Signals" bottom tab construction in `_build_bottom_tabs` with `_build_active_trades_pane` returning an `ActiveCyclesPanel`. Tab label "Active Trades". Legacy `_build_signals_pane` / `_refresh_signals_pane` / `_inject_action_buttons` remain dormant in the file for Phase 2 removal. | SRD-GUI-014.001 |
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | Construct `_AppEventStream(lifecycle_bus, strategy_bus)` after engine start; expose `event_stream`, `cycle_query`, `cycle_cmd`, `pending_store` as `@property` accessors consumed by `ActiveCyclesPanel`. | SRD-GUI-014.014 |
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | Wire FO-EXE-011 `PendingSignalStore` and FO-EXE-012 `TradeCycleService` into AppService construction; expose `cycle_query`, `cycle_cmd`, `pending_store` properties consumed by `ActiveCyclesPanel`. Forward `circuit_breaker_changed(bool)` (FO-EXE-003) so the delegate's button-paint can react. | SRD-GUI-014.012 |
| MD-GUI-014.001.M02 | `src/us_swing/gui/active_cycles_model.py` | Add `Col.REX` to the column enum + header label "Rex"; cell `data()` queries `app.rex_counters.get(strategy_id, symbol)`, renders the integer (or `cfg.rex_count` when `None`); a value `< 0` paints dimmed (`ForegroundRole = C.MUTED`) with `ToolTipRole = "Rex limit reached — Reset Strategy to re-enable entries"`. Refresh on `on_cycle_opened` and `on_pending_added`. | SRD-GUI-014.013 |
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | Expose `rex_counters: RexCounterRepository` constructed once in `AppService.__init__` from the shared `self._db_engine`. Consumed by `_StrategyTablePane` (Reset action, SRD-GUI-013.015) and `_ActiveCyclesModel` (Rex column, SRD-GUI-014.013). | SRD-GUI-013.015, SRD-GUI-014.013 |
| MD-GUI-014.001.M02 | `src/us_swing/gui/active_cycles_model.py` | Add `Col.SIDE` after `Col.SYMBOL` and `_Row.direction`, filled from the pending signal or cycle snapshot; green `Long` / red `Short` cell. | SRD-GUI-014.016 |
| MD-GUI-014.001.M01 | `src/us_swing/gui/active_cycles_panel.py` | Add `_order_verb(direction, is_exit)`; use it in the Execute and Close confirmations and button text; margin check stays entry-only. | SRD-GUI-014.017 |
| MD-GUI-014.001.M03 | `src/us_swing/gui/risk_editor_widget.py` | Swap the Hard Stop and Target spinbox ranges around the current price for a Short cycle. | SRD-GUI-014.018 |

---

## FO-GUI-015 — Indicator Rule Library Dialog Modules

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP | Status |
|---|---|---|---|---|---|---|---|
| MD-GUI-015.002.M01 | SRD-GUI-015.002 | `src/us_swing/gui/frameless_dialog.py` | Shared frameless dialog base with custom title bar, moved unchanged from `screener_panel.py`. | `FramelessDialog(title, min_width, min_height, extra_qss, parent)`, `content_layout()` | PyQt6, `theme.C` | No | Implemented |
| MD-GUI-015.008.M02 | SRD-GUI-015.008, .012 | `src/us_swing/gui/indicator_rule_model.py` | Table model holding the dialog's `Rule` list; no screening logic. | `RuleTableModel`, `set_rules()`, `rules()`, `add_rule()`, `remove_row()`, `set_enabled()`, `update_rule()`, signal `rules_changed` | `core.indicator_rules`, PyQt6, `theme.C` | No | Implemented |
| MD-GUI-015.009.M03 | SRD-GUI-015.009–.010, .015 | `src/us_swing/gui/indicator_rule_delegates.py` | Delegates for toggle, condition combo, number spinboxes, settings cell and remove button. | `ToggleSwitchDelegate`, `ConditionComboDelegate`, `NumberSpinDelegate`, `SettingsDelegate`, `RemoveButtonDelegate` | `indicator_rule_model`, `core.indicator_rules`, PyQt6, `theme.C` | No | Implemented |
| MD-GUI-015.003.M04 | SRD-GUI-015.003–.006 | `src/us_swing/gui/indicator_library_model.py` | Catalogue tree model with usage counts, search proxy and drag-source view. | `LibraryTreeModel`, `LibraryFilterProxy`, `LibraryTreeView`, `MIME_INDICATOR`, `set_usage()`, `find_item()` | `core.indicator_rules`, PyQt6, `theme.C` | No | Implemented |
| MD-GUI-015.011.M05 | SRD-GUI-015.011 | `src/us_swing/gui/indicator_params_dialog.py` | Title-bar-less popup panel (S2) anchored under the Settings cell; Enter saves, Esc or click outside discards. | `IndicatorParamsDialog(spec, params)`, `place_under(anchor)`, `get_params()` | `frameless_dialog`, `core.indicator_rules`, PyQt6 | No | Implemented |
| MD-GUI-015.001.M06 | SRD-GUI-015.001, .007, .013 | `src/us_swing/gui/indicator_rules_dialog.py` | Assembles library pane, rule table, header and footer; loads and returns rule-list config. | `IndicatorRulesDialog(config, parent)`, `get_config()`, `rules()`, `RuleTableView` | M01–M05, `core.indicator_rules`, PyQt6 | No | Implemented |

### Cross-Module Modifications for FO-GUI-015

| Module ID | File | Change Required | SRD |
|---|---|---|---|
| MD-GUI-003.001.M01 | `src/us_swing/gui/screener_panel.py` | Import `FramelessDialog` (keep `_FramelessDialog` alias); both builder call sites open `IndicatorRulesDialog`; Details column uses `config_summary()`; delete `_IndicatorConfigDialog`, `_INDICATOR_DEFAULTS`, `_format_indicator_config`. | SRD-GUI-015.014 |

## FO-GUI-016 — Price Action Pattern Library Dialog Modules

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP | Status |
|---|---|---|---|---|---|---|---|
| MD-GUI-016.004.M07 | SRD-GUI-016.004, .008 | `src/us_swing/gui/pattern_rule_model.py` | Table model holding the dialog's `PatternRule` list; no screening logic. | `PatternRuleTableModel`, `set_rules()`, `rules()`, `add_rule()`, `remove_row()`, `set_enabled()`, `update_rule()`, signal `rules_changed` | `core.price_patterns`, `indicator_rule_model` roles, PyQt6, `theme.C` | No | Implemented |
| MD-GUI-016.001.M08 | SRD-GUI-016.001, .003, .006–.007, .009, .011 | `src/us_swing/gui/price_action_rules_dialog.py` | Assembles pattern library, threshold header, rule table and footer; loads and returns rule-list config. | `PriceActionRulesDialog(config, parent)`, `get_config()`, `rules()`, `threshold()` | M01–M07, `core.price_patterns`, PyQt6 | No | Implemented |

### Cross-Module Modifications for FO-GUI-016

| Module ID | File | Change Required | SRD |
|---|---|---|---|
| MD-GUI-015.003.M04 | `src/us_swing/gui/indicator_library_model.py` | `LibraryTreeModel` takes optional `entries` and `categories` (defaults: indicator catalogue). | SRD-GUI-016.002 |
| MD-GUI-015.009.M03 | `src/us_swing/gui/indicator_rule_delegates.py` | Toggle / Remove use a `RuleRowsModel` Protocol; Settings paints the model's display text. | SRD-GUI-016.005 |
| MD-GUI-015.008.M02 | `src/us_swing/gui/indicator_rule_model.py` | Settings column returns `settings_summary()` as display text. | SRD-GUI-016.005 |
| MD-GUI-015.011.M05 | `src/us_swing/gui/indicator_params_dialog.py` | `spec` typed as a `ParamsOwner` Protocol so pattern specs work. | SRD-GUI-016.006 |
| MD-GUI-003.001.M01 | `src/us_swing/gui/screener_panel.py` | Price action call sites open `PriceActionRulesDialog`; Details adds `pattern_config_summary()`; delete `_PriceActionConfigDialog`, `_PA_PATTERN_LABELS`, `_PA_DEFAULTS`, `_format_price_action_config`. | SRD-GUI-016.010 |

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

## FO-GUI-017 — Carbon Theme and Icon System

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-GUI-017.001.M02 | SRD-GUI-017.001 | `us_swing/src/us_swing/gui/theme.py` | Carbon tokens and QSS, danger QSS, font loading | `THEMES`, `load_theme_id()`, `load_fonts()` | `QtGui` | No |
| MD-GUI-017.003.M01 | SRD-GUI-017.003 | `us_swing/src/us_swing/gui/icons.py` | Role-coloured, cached SVG icons | `icon()`, `set_icon()`, `icon_button()`, `clear_cache()` | `theme`, `QtSvg` | No |

> MD-GUI-017.001.M02 also covers SRD-GUI-017.002 and .005. Panel edits for SRD-GUI-017.004/.005 stay under each panel's existing MD ID.

## FO-GUI-018 — Sidebar Workspace Shell

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-GUI-018.001.M01 | SRD-GUI-018.001 | `us_swing/src/us_swing/gui/sidebar.py` | Sidebar nav, mini labels, account footer | `Sidebar`, `page_requested`, `mini_toggled`, `hover_changed`, `set_mini()`, `set_current()` | `icons`, `theme`, `AppService` | No |
| MD-GUI-018.006.M02 | SRD-GUI-018.006 | `us_swing/src/us_swing/gui/reveal.py` | Size animation for hide/show panels | `RevealController`, `register()`, `on_reveal_requested()`, `revealed` | `QtCore` | No |
| MD-GUI-018.005.M03 | SRD-GUI-018.005 | `us_swing/src/us_swing/gui/main_window.py` | Shell layout, mini state, peek geometry, screen slide | `MainWindow` | `sidebar`, `reveal` | No |
| MD-GUI-018.008.M04 | SRD-GUI-018.008 | `us_swing/src/us_swing/gui/sidebar.py` | Connections panel, retry text, market countdown, mini plug | `_ConnectionsPanel`, `market_text()`, `Sidebar.set_feed_retry()`, `Sidebar.clear_feed_retry()` | `AppService`, `market_calendar`, `icons`, `theme` | No |

## FO-GUI-019 — Side Panels and Exit Drawer

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-GUI-019.001.M01 | SRD-GUI-019.001 | `us_swing/src/us_swing/gui/side_panels.py` | Icon strip and Position Details panel | `IconStrip`, `PositionDetails` | `icons`, `theme`, `AppService` | No |
| MD-GUI-019.006.M02 | SRD-GUI-019.006 | `us_swing/src/us_swing/gui/dashboard_panel.py` | Exit drawer, exit and square-off forms, apply exit | `DashboardPanel.open_exit()`, `position_selected`, `watchlist_widget` | `AppService` | No |
| MD-GUI-019.002.M03 | SRD-GUI-019.002 | `us_swing/src/us_swing/gui/main_window.py` | Panel layout and wiring | `MainWindow` | `side_panels`, `reveal`, `log_viewer_panel` | No |

## FO-GUI-020 — Charts Workspace

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-GUI-020.001.M01 | SRD-GUI-020.001 | `us_swing/src/us_swing/gui/chart_workspace.py` | MDI chart windows, arrange modes, open path | `ChartWorkspace`, `open_symbol()`, `refresh_theme()` | `chart_panel`, `icons` | No |

> `chart_panel.py` (MD-GUI-011) gains `chart_loaded` and a timeframe argument on `show_symbol`; `screener_panel.py` (MD-GUI-003.001.M01) emits `chart_requested` and drops `QuickChartWindow`; `main_window.py` wiring stays under MD-GUI-019.002.M03.

## FO-GUI-021 — Settings Section List

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-GUI-021.001.M01 | SRD-GUI-021.001 | `us_swing/src/us_swing/gui/settings_panel.py` | Section list, section cards, system sections, risk save | `SettingsPanel`, `theme_changed`, `trigger_fill_delta()` | `theme`, `icons`, `app_service` | No |

> `theme.py` (MD-GUI-017) gains the `settings_nav`, `settings_card`, `settings_head`, `panel_group` and `data_*` QSS rules; `side_panels.py` (MD-GUI-019.001.M01) gains the `system` and `data` strip buttons and `set_data_state()`; `main_window.py` (MD-GUI-019.002.M03) adds the System and Data panels to the right panel stack.

## FO-GUI-022 — Screener Result Views

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-GUI-022.001.M01 | SRD-GUI-022.001 | `us_swing/src/us_swing/gui/screener_views.py` | Result rows, sort, CSV rows, view switch, List + detail view, Cards view, preset filter | `ResultRow`, `RuleCheck`, `rows_from_result()`, `sort_rows()`, `csv_rows()`, `filter_presets()`, `ViewSwitch`, `ListDetailView`, `CardsView` | `theme`, `icons` | No |

> `screener_panel.py` (MD-GUI-003.001.M01) hosts the views, the Sort box and the new preset rail; `theme.py` (MD-GUI-017) gains the screener view QSS rules.
