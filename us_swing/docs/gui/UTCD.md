# Unit Test Case Document â€” GUI Module (GUI)

**Document ID:** UTCD-GUI
**Version:** 1.3.1
**Traces To:** MD-GUI v1.3.0
**Status:** Draft
**Last Updated:** 2026-05-29
**Project:** US Swing Trading System

> v1.3.0: UTCD-GUI-013 (Strategy Builder Dialog, 22 tests) and UTCD-GUI-014 (Active Cycles Panel, 24 tests) added.

> Tests written BEFORE implementation per process.md Â§7.
> GUI tests use `pytest-qt` (`qtbot` fixture) for widget testing.

---

## Module: `gui/main_window.py` â€” MainWindow

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-001.001.M01.T01 | MD-GUI-001.001.M01 | Unit | MainWindow creates exactly 4 nav tab buttons in `_TitleBar` | Construct `MainWindow(svc)` | `len(window._title_bar._tabs) == 4`; labels: Dashboard, Screener, Execution, Settings | Implemented |
| UT-GUI-001.001.M01.T02 | MD-GUI-001.001.M01 | Unit | Status bar has Internet pill, P&L, Positions (left) and NYSE, NASDAQ pills (right) | Construct `MainWindow(svc)` | `_sb_conn`, `_sb_pnl`, `_sb_pos`, `_sb_nyse`, `_sb_nasdaq` exist and are visible | Implemented |
| UT-GUI-001.001.M01.T03 | MD-GUI-001.001.M01 | Unit | Scope combo change updates `_AdminContextBar` scope icon | `svc.set_viewing_uid(user_id)` emits `viewing_changed` | `_admin_ctx_bar._scope_icon.text() == "ðŸ‘¤"` for single-user; `"ðŸŒ"` for all-users | Implemented |
| UT-GUI-001.001.M01.T04 | MD-GUI-001.001.M01 | Unit | `feed_status_changed("connected")` updates feed button text | Emit `svc.feed_status_changed("connected")` | `_title_bar._feed_btn.text() == "ðŸŸ¢  Connected"` | Implemented |
| UT-GUI-001.001.M01.T05 | MD-GUI-001.001.M01 | Unit | Window geometry saved on close | Close window | `QSettings("USSwing", "MainWindow")` contains `"geometry"` key | Implemented |
| UT-GUI-001.001.M01.T06 | MD-GUI-001.001.M01 | Unit | Window geometry restored on launch | Pre-set `QSettings` geometry | Window position matches saved values | Implemented |

---

## Module: `gui/position_table_model.py` â€” PositionTableModel

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-002.001.M02.T01 | MD-GUI-002.001.M02 | Unit | Empty model has 0 rows, 9 columns (base, no User col) | `PositionTableModel()` with no positions | `rowCount() == 0`; `columnCount() == 9` | Implemented |
| UT-GUI-002.001.M02.T02 | MD-GUI-002.001.M02 | Unit | User column prepended when `set_show_user(True)` | `set_show_user(True, {1: "alice"})` | `columnCount() == 10`; `headerData(0) == "User"` | Implemented |
| UT-GUI-002.001.M02.T03 | MD-GUI-002.001.M02 | Unit | Positive P&L cell has green-tinted background and green foreground | Position with `unrealised_pnl=500` | `BackgroundRole == QColor(C.PNL_POS_BG)`; `ForegroundRole == QColor(C.GREEN)` | Implemented |
| UT-GUI-002.001.M02.T04 | MD-GUI-002.001.M02 | Unit | Negative P&L cell has red-tinted background and red foreground | Position with `unrealised_pnl=-200` | `BackgroundRole == QColor(C.PNL_NEG_BG)`; `ForegroundRole == QColor(C.RED)` | Implemented |
| UT-GUI-002.001.M02.T05 | MD-GUI-002.001.M02 | Unit | `refresh()` resets model and reflects new positions | `refresh([pos1, pos2])` | `rowCount() == 2`; `modelReset` signal emitted via `beginResetModel/endResetModel` | Implemented |

---

## Module: `gui/screener_panel.py` â€” ScreenerPanel

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-003.001.M01.T01 | MD-GUI-003.001.M01 | Unit | Filter chips reflect enabled state from `AppService.get_screener_filters()` | Service returns 2 of 5 filters enabled | 2 `_FilterChip` checkboxes checked, 3 unchecked | Approved |
| UT-GUI-003.001.M01.T02 | MD-GUI-003.001.M01 | Unit | "Run Screener" button disabled during execution | Click run; check button state immediately | `_run_btn.isEnabled() == False`; re-enabled on `_ScreenerWorker.finished` | Approved |
| UT-GUI-003.001.M01.T03 | MD-GUI-003.001.M01 | Unit | Results table populated after screener run | Worker emits `finished` with 10 results | `_results_model.rowCount() == 10` | Approved |
| UT-GUI-003.001.M01.T04 | MD-GUI-003.001.M01 | Unit | Filter chip spinboxes disabled when chip unchecked | Uncheck a `_FilterChip` | All `_spins` in that chip have `isEnabled() == False` | Approved |

---

## Module: `gui/execution_panel.py` â€” ExecutionPanel

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-004.001.M01.T01 | MD-GUI-004.001.M01 | Unit | Signal rows created from `AppService.get_pending_signals()` at init | Service returns 2 signals | `len(panel._signal_rows) == 2`; each row has symbol label and Execute button | Implemented |
| UT-GUI-004.001.M01.T02 | MD-GUI-004.001.M01 | Unit | Override qty shows "(overridden)" when value differs from recommended | Set `_spin.value` != `signal.recommended_qty` | `_override_lbl.text() == "(overridden)"` | Implemented |
| UT-GUI-004.001.M01.T03 | MD-GUI-004.001.M01 | Unit | Override qty spinbox minimum is 1 | Attempt to set value to 0 | `_spin.value() == 1` (clamped by `setRange(1, 10_000)`) | Implemented |
| UT-GUI-004.001.M01.T04 | MD-GUI-004.001.M01 | Unit | Circuit breaker disables all execute buttons and shows banner | `panel.on_circuit_breaker(True)` | All `_SignalRow._exec_btn.isEnabled() == False`; `_cb_banner.isVisible() == True` | Implemented |
| UT-GUI-004.001.M01.T05 | MD-GUI-004.001.M01 | Unit | `viewing_changed` syncs Execute-for combo to current scope | `svc.set_viewing_uid(user_id)` | `_exec_user_combo` index matches `user_id` entry | Implemented |
| UT-GUI-004.001.M01.T06 | MD-GUI-004.001.M01 | Positive | `_on_run()` on SQUARING_OFF with no open cycles forces run_state to STOPPED and saves | `run_state="SQUARING_OFF"`; `get_open_symbols_for_strategy` returns `[]`; call `_on_run(0)` | `cfg.strategy_signal["run_state"] == "STOPPED"`; `save_strategies` called once | Pass |
| UT-GUI-004.001.M01.T07 | MD-GUI-004.001.M01 | Negative | `_on_run()` on SQUARING_OFF with open cycles leaves state unchanged and does not save | `run_state="SQUARING_OFF"`; `get_open_symbols_for_strategy` returns `["AAPL","MSFT"]`; call `_on_run(0)` | `cfg.strategy_signal["run_state"] == "SQUARING_OFF"`; `save_strategies` not called | Pass |

---

## Module: `gui/position_monitor_panel.py` â€” PositionMonitorPanel

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-005.001.M01.T01 | MD-GUI-005.001.M01 | Unit | Positions from `AppService.get_positions()` shown on init | Service returns 2 OPEN positions | `_pos_model.rowCount() == 2` | Implemented |
| UT-GUI-005.001.M01.T02 | MD-GUI-005.001.M01 | Unit | Capital indicator shows correct available amount | `equity=100_000`, `open_position_value=30_000` | `_remaining_lbl.text() == "$70,000  of  $100,000"` | Implemented |
| UT-GUI-005.001.M01.T03 | MD-GUI-005.001.M01 | Unit | "CAN ENTER" badge when capital available | `available > 0` and `util_pct < max_allocation_pct` | `_can_enter.text() == "CAN ENTER"` | Implemented |
| UT-GUI-005.001.M01.T04 | MD-GUI-005.001.M01 | Unit | "CANNOT ENTER" badge when capital exhausted | `util_pct >= max_allocation_pct` | `_can_enter.text() == "CANNOT ENTER"` | Implemented |
| UT-GUI-005.001.M01.T05 | MD-GUI-005.001.M01 | Unit | Position state colour coding | OPEN and PARTIAL_EXIT positions | OPEN `BackgroundRole == QColor("#1a3326")`; PARTIAL_EXIT `QColor("#332500")` | Implemented |

---

## Module: `gui/settings_panel.py` â€” SettingsPanel

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-006.001.M01.T01 | MD-GUI-006.001.M01 | Unit | Settings panel has 5 sub-tabs in correct order | Construct `SettingsPanel(svc)` | `tabs.count() == 5`; tab texts: Users, Strategies, Screeners, System, Universe | Implemented |
| UT-GUI-006.001.M01.T02 | MD-GUI-006.001.M01 | Unit | New user dialog calls `AppService.add_user()` | Fill `_UserDialog` and click OK | `svc.add_user()` called once; `users_changed` triggers table refresh | Implemented |
| UT-GUI-006.001.M01.T03 | MD-GUI-006.001.M01 | Unit | Delete user blocked when `AppService.delete_user()` returns error | Select user; click Delete; confirm | Warning `QMessageBox` shown; user remains in table | Implemented |
| UT-GUI-006.001.M01.T04 | MD-GUI-006.001.M01 | Unit | Universe tab meta label shows constituent count | `svc.get_sp500_universe()` returns 503 records | `_meta_label.text()` contains `"503 constituents"` | Implemented |

---

## Module: `gui/log_viewer_panel.py` â€” Log Viewer

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-007.001.M01.T01 | MD-GUI-007.001.M01 | Unit | Log entries appear when `AppService.log_message` emitted | Emit `svc.log_message("INFO", "hello")` 3 times | `panel._line_count == 3`; `_log_view` is non-empty | Implemented |
| UT-GUI-007.001.M01.T02 | MD-GUI-007.001.M01 | Unit | ERROR entry emits `error_occurred` signal | Emit `svc.log_message("ERROR", "fail")` | `error_occurred` signal emitted once | Implemented |
| UT-GUI-007.001.M01.T03 | MD-GUI-007.001.M01 | Unit | Level filter hides lower-priority entries | Buffer: 2 INFO + 1 WARNING; set level combo to WARNING | `_reapply_filter()` renders 1 visible entry | Implemented |
| UT-GUI-007.001.M01.T04 | MD-GUI-007.001.M01 | Unit | Buffer evicts oldest entries when exceeding `MAX_LINES` | Push `MAX_LINES + 5` messages | `len(panel._buffer) == MAX_LINES` | Implemented |
| UT-GUI-007.001.M01.T05 | MD-GUI-007.001.M01 | Unit | Pause halts display; Resume flushes buffered entries | Pause; emit 3 messages; Resume | After Resume `_line_count` increases by 3 | Implemented |

---

## Module: `gui/app_service.py` â€” AppService (FO-GUI-012 tick integration)

### LiveTickWorker lifecycle (SRD-GUI-012.001)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-012.001.M01.T01 | MD-GUI-004.001.M01 | Positive | `_on_connect_ok()` creates `LiveTickWorker` with host/port from `SystemConfig` and `ibkr_tick_client_id=14` | Mock `SystemConfig` with `ibkr_tick_client_id=14`; call `svc._on_connect_ok()` | `svc._tick_worker` is not None; `isinstance(svc._tick_worker, LiveTickWorker) is True`; constructed with clientId=14 | Pass |
| UT-GUI-012.001.M01.T02 | MD-GUI-004.001.M01 | Positive | `disconnect_feed()` calls `request_stop()` on the running worker and sets `_tick_worker = None` | Attach mock `LiveTickWorker` to `svc._tick_worker`; call `svc.disconnect_feed()` | `mock_worker.request_stop.called is True`; `svc._tick_worker is None` | Pass |
| UT-GUI-012.001.M01.T03 | MD-GUI-004.001.M01 | Negative | Second call to `_on_connect_ok()` while worker is running does not start a second worker | Call `_on_connect_ok()` twice; `_tick_worker.isRunning()` returns True | `LiveTickWorker` constructor called exactly once (not twice) | Pass |
| UT-GUI-012.001.M01.T19 | MD-GUI-004.001.M01 | Negative | `disconnect_feed()` when `_tick_worker is None` (never connected) does not raise | `svc._tick_worker = None`; call `svc.disconnect_feed()` | No exception raised; `market_watch_updated` still emitted (ltp cleared) | Pass |

### Market Watch â€” IBKR contract routing (SRD-GUI-012.002)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-012.001.M01.T04 | MD-GUI-004.001.M01 | Positive | `_sync_tick_subscriptions()` maps `"^GSPC"` to `Contract(symbol="SPX", secType="IND", exchange="CBOE")` in the set passed to `LiveTickWorker.set_contracts()` | `svc._watch` contains item with `symbol="^GSPC"`; mock `_tick_worker` | `set_contracts` called with dict containing key `"^GSPC"` whose value has `symbol="SPX"`, `secType="IND"`, `exchange="CBOE"` | Pass |
| UT-GUI-012.001.M01.T05 | MD-GUI-004.001.M01 | Negative | Symbol absent from `_YAHOO_TO_IBKR` map is not included in `set_contracts()` call | `svc._watch` contains `symbol="^CUSTOM"` (not in map) | `set_contracts` called without `"^CUSTOM"` key | Pass |

### _on_mktwatch_tick (SRD-GUI-012.003)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-012.001.M01.T06 | MD-GUI-004.001.M01 | Positive | `_on_mktwatch_tick` updates ltp, computes change_pct, emits `market_watch_updated` | `_watch` has item `symbol="^GSPC"`; `_watch_prev_close={"^GSPC": 5100.0}`; call `_on_mktwatch_tick("^GSPC", 5200.0)` | item.ltp=5200.0; item.change_pctâ‰ˆ1.96; `market_watch_updated` emitted once | Pass |
| UT-GUI-012.001.M01.T07 | MD-GUI-004.001.M01 | Positive | `change_pct` is None when no prev_close stored; signal still emitted | `_watch_prev_close={}` (empty); call `_on_mktwatch_tick("^GSPC", 5200.0)` | item.ltp=5200.0; item.change_pct is None; `market_watch_updated` emitted | Pass |
| UT-GUI-012.001.M01.T08 | MD-GUI-004.001.M01 | Negative | `_on_mktwatch_tick` with unknown tag â†’ no signal, no exception | Call `_on_mktwatch_tick("UNKNOWN", 100.0)` | `market_watch_updated` NOT emitted; no exception raised | Pass |

### _on_watchlist_tick (SRD-GUI-012.004)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-012.001.M01.T09 | MD-GUI-004.001.M01 | Positive | `_on_watchlist_tick` updates ltp/change/change_pct and emits `watchlist_updated` | `_watchlist` has `{"symbol": "AAPL", "prev_close": 175.0, "ltp": 175.0, ...}`; call `_on_watchlist_tick("AAPL", 180.0)` | item["ltp"]=180.0; item["change"]=5.0; item["change_pct"]â‰ˆ2.857; `watchlist_updated` emitted | Pass |
| UT-GUI-012.001.M01.T10 | MD-GUI-004.001.M01 | Negative | Non-S&P 500 symbol is absent from the dict passed to `set_contracts()` | `_watchlist_symbols={"AAPL", "NOTSP"}` where "NOTSP" absent from `_sp500_cache`; call `_sync_tick_subscriptions()` | `set_contracts` called without `"NOTSP"` key | Pass |

### _on_position_tick (SRD-GUI-012.005)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-012.001.M01.T11 | MD-GUI-004.001.M01 | Positive | `_on_position_tick` updates `current_price` on matching open position and emits `positions_updated` | `_positions` has `OpenPosition(symbol="AAPL", current_price=180.0, state="OPEN")`; call `_on_position_tick("AAPL", 185.0)` | `pos.current_price == 185.0`; `positions_updated` emitted once | Pass |
| UT-GUI-012.001.M01.T12 | MD-GUI-004.001.M01 | Negative | `_on_position_tick` with no matching position â†’ no signal, no exception | `_positions=[]`; call `_on_position_tick("AAPL", 185.0)` | `positions_updated` NOT emitted; no exception | Pass |

### _sync_tick_subscriptions() (SRD-GUI-012.006)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-012.001.M01.T13 | MD-GUI-004.001.M01 | Positive | `_sync_tick_subscriptions()` merges Market Watch, watchlist S&P 500, and position S&P 500 into one `set_contracts()` call | `_watch=["^GSPC"]`; watchlist=`["AAPL"]` (S&P 500); positions=`[OpenPosition("MSFT")]` (S&P 500) | `set_contracts` called once with dict containing `"^GSPC"`, `"AAPL"`, `"MSFT"` | Pass |
| UT-GUI-012.001.M01.T14 | MD-GUI-004.001.M01 | Edge | > 95 total contracts â†’ WARNING logged; position contracts trimmed; Market Watch and watchlist contracts preserved | Build 100-contract scenario (3 market watch + 30 watchlist + 67 positions); call `_sync_tick_subscriptions()` | WARNING log contains "near IBKR limit"; `set_contracts` called with â‰¤ 95 keys; all 3 Market Watch and all 30 watchlist keys present | Pass |
| UT-GUI-012.001.M01.T18 | MD-GUI-004.001.M01 | Negative | `_sync_tick_subscriptions()` is a no-op when `_tick_worker is None` (called before connect) | `svc._tick_worker = None`; call `svc._sync_tick_subscriptions()` | `set_contracts` NOT called; no exception raised | Pass |

### Disconnect behaviour (SRD-GUI-012.007)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-012.001.M01.T15 | MD-GUI-004.001.M01 | Positive | `disconnect_feed()` sets all `_watch` item `ltp=None` and emits `market_watch_updated` | `_watch` has 3 items with non-None ltp; call `svc.disconnect_feed()` | All items have `ltp is None`; `market_watch_updated` emitted | Pass |
| UT-GUI-012.001.M01.T16 | MD-GUI-004.001.M01 | Negative | Position `current_price` is NOT cleared on disconnect | `_positions` has `OpenPosition(current_price=185.0)`; call `svc.disconnect_feed()` | `pos.current_price == 185.0` (unchanged) | Pass |
| UT-GUI-012.001.M01.T17 | MD-GUI-004.001.M01 | Negative | Watchlist ltp is NOT cleared on disconnect | `_watchlist` has item with `ltp=180.0`; call `svc.disconnect_feed()` | `item["ltp"] == 180.0` (unchanged) | Pass |

---

## Module: `gui/strategy_builder_dialog.py` — StrategyBuilderDialog (FO-GUI-013)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-013.001.M01.T01 | MD-GUI-013.001.M01 | Unit | Dialog opens with 5 nav entries in the tree | `StrategyBuilderDialog([], None)` | `_nav_tree.topLevelItemCount() == 5`; labels match Strategy Info / Triggers / Scheduler / Execution / Risk | Not Run |
| UT-GUI-013.001.M01.T02 | MD-GUI-013.001.M01 | Unit | Selecting a nav entry switches the stacked page | Click "Triggers" nav item | `_page_stack.currentIndex() == _PAGE_TRIGGER` | Not Run |
| UT-GUI-013.001.M01.T03 | MD-GUI-013.001.M01 | Negative | Saving with blank Name is blocked with inline error | Leave Name empty, click Save | `saved` signal not emitted; inline error label visible with text containing "name" | Not Run |
| UT-GUI-013.001.M01.T04 | MD-GUI-013.001.M01 | Negative | Saving with a duplicate name (case-insensitive) is blocked | Registry has `[StrategyConfig(name="boss_ema")]`; set Name = "BOSS_EMA"; click Save | `saved` not emitted; inline error mentions "unique" or "exists" | Not Run |
| UT-GUI-013.001.M01.T05 | MD-GUI-013.001.M01 | Positive | "Include Only" scope reveals stock picker | Set scope combo to "Include Only" | `_picker_panel.isVisible() == True` | Not Run |
| UT-GUI-013.001.M01.T06 | MD-GUI-013.001.M01 | Positive | Picker symbols save into `symbols_include` for `include_only` scope | Add `["AAPL", "MSFT"]`; set scope `include_only`; Save | Saved `StrategyConfig.symbols_include == ["AAPL","MSFT"]`; `symbols_exclude == []` | Not Run |
| UT-GUI-013.001.M01.T07 | MD-GUI-013.001.M01 | Positive | Capital Max accepts 5–100 step 5, default 25 | Inspect spinbox properties | `minimum=5`, `maximum=100`, `singleStep=5`, `value=25` | Not Run |
| UT-GUI-013.001.M01.T08 | MD-GUI-013.001.M01 | Edge | Capital Max cannot be set below 5 | `_capital_spin.setValue(2)` | `_capital_spin.value() == 5` (clamped) | Not Run |
| UT-GUI-013.001.M01.T09 | MD-GUI-013.001.M01 | Positive | Trigger builder reveals relop pill only after Condition 1 is set | Initially empty; set `_cond1_fn = "RSI('Spot', 14, '3m')"`; call `_rebuild_chain()` | `_relop.isVisible() == True`; `_add_c2.isVisible() == True` | Not Run |
| UT-GUI-013.001.M01.T10 | MD-GUI-013.001.M01 | Positive | Compile appends `(c1) op (c2)` to buffer with logical join | Both conds set; click Compile twice with logop OR | Buffer text = `"(c1a) > (c2a) OR (c1b) < (c2b)"` | Not Run |
| UT-GUI-013.001.M01.T11 | MD-GUI-013.001.M01 | Negative | Pressing Entry with empty compiled buffer shows inline error | Click Entry while buffer is empty | `entry_condition` unchanged; inline error visible | Not Run |
| UT-GUI-013.001.M01.T12 | MD-GUI-013.001.M01 | Positive | Entry button copies buffer to `entry_condition` and clears buffer | Buffer = `"(RSI('Spot', 14, '3m')) > (Number(30))"`; click Entry | `entry_condition` equals buffer text; `_output.toPlainText() == ""` | Not Run |
| UT-GUI-013.001.M01.T13 | MD-GUI-013.001.M01 | Edge | Indicator expression with dropdown args is single-quoted; numeric args are bare | Build `RSI` with Symbol Type='Spot', Length=14, Timeframe='3m' | Resulting expression: `"RSI('Spot', 14, '3m')"` | Not Run |
| UT-GUI-013.001.M01.T14 | MD-GUI-013.001.M01 | Negative | Empty editbox parameter blocks Add in condition selector | Leave "RSI Length" blank; click Add | `condition_built` signal not emitted; inline error visible | Not Run |
| UT-GUI-013.001.M01.T15 | MD-GUI-013.001.M01 | Positive | Scheduler defaults: 09:30 / 15:30 ET, today / today+6mo, Mon–Fri all checked | Open fresh dialog | `_start_time == 09:30`; `_end_time == 15:30`; `_start_date == today`; `_end_date == today+6mo`; all 5 day pills checked | Not Run |
| UT-GUI-013.001.M01.T16 | MD-GUI-013.001.M01 | Negative | Save blocked when `end_time <= start_time` | Set start=15:30, end=09:30; click Save | `saved` not emitted; inline error mentions "time" | Not Run |
| UT-GUI-013.001.M01.T17 | MD-GUI-013.001.M01 | Positive | Target spinbox is disabled until Target enable checkbox is ticked | Inspect Target page on open | `_target_value.isEnabled() == False`; tick checkbox → True | Not Run |
| UT-GUI-013.001.M01.T18 | MD-GUI-013.001.M01 | Positive | `load_strategies()` returns empty list when file is missing | `_STRATEGIES_PATH` does not exist | `load_strategies() == []` | Not Run |
| UT-GUI-013.001.M01.T19 | MD-GUI-013.001.M01 | Negative | `load_strategies()` returns empty list on malformed JSON | Write `"not valid json"` to file | `load_strategies() == []`; no exception raised | Not Run |
| UT-GUI-013.001.M01.T20 | MD-GUI-013.001.M01 | Positive | `load_strategies()` forces `Status='Inactive'` on every record | File has record with `strategy_signal.Status='Running'` | Loaded record has `strategy_signal['Status'] == 'Inactive'` and `Running_Symbols == []` | Not Run |
| UT-GUI-013.001.M01.T21 | MD-GUI-013.001.M01 | Positive | `commit()` overwrites existing record by case-insensitive name | Registry `[cfg(name="boss_ema")]`; commit `cfg(name="BOSS_EMA")` | Registry length stays 1; record replaced | Not Run |
| UT-GUI-013.001.M01.T22 | MD-GUI-013.001.M01 | Positive | `save_strategies()` writes via temp-file + atomic replace | Stub `Path.replace`; call `save_strategies([cfg])` | `Path.replace` called once with `.tmp` → final path; final file exists | Not Run |

---

## Module: `gui/active_cycles_model.py` — _ActiveCyclesModel (FO-GUI-014)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-014.001.M02.T01 | MD-GUI-014.001.M02 | Unit | Empty model has 0 rows, 14 columns | Construct with empty query + empty store | `rowCount() == 0`; `columnCount() == 14` | Not Run |
| UT-GUI-014.001.M02.T02 | MD-GUI-014.001.M02 | Positive | `on_pending_added(signal)` inserts one row with state=PENDING | Call with `TradeSignal(ENTRY, AAPL, boss_ema, qty=25)` | `rowCount() == 1`; row state="PENDING"; symbol="AAPL"; qty=25 | Not Run |
| UT-GUI-014.001.M02.T03 | MD-GUI-014.001.M02 | Positive | `on_cycle_opened(snap)` inserts one OPEN row | `CycleSnapshot(cycle_id=1, state="OPEN", symbol="AAPL", entry_price=182.5, entry_qty=25)` | `rowCount() == 1`; row state="OPEN"; entry=182.5 | Not Run |
| UT-GUI-014.001.M02.T04 | MD-GUI-014.001.M02 | Positive | `on_cycle_updated` mutates only LTP/PnL/Trail columns, emits contiguous dataChanged | Existing OPEN row; updated snap with new ltp/pnl/trail | `dataChanged.emit` called once with column range covering [LTP, TRAIL]; STATE/SYMBOL untouched | Not Run |
| UT-GUI-014.001.M02.T05 | MD-GUI-014.001.M02 | Negative | `on_cycle_updated` for unknown cycle_id is a no-op | Call with `cycle_id=999` not in `_by_key` | No row inserted; no `dataChanged` emitted | Not Run |
| UT-GUI-014.001.M02.T06 | MD-GUI-014.001.M02 | Positive | Positive PnL cell uses green tinted background + green foreground | Row with `pnl_usd=62.50` | `BackgroundRole == C.PNL_POS_BG`; `ForegroundRole == C.GREEN` | Not Run |
| UT-GUI-014.001.M02.T07 | MD-GUI-014.001.M02 | Positive | Negative PnL cell uses red tinted background + red foreground | Row with `pnl_usd=-15.00` | `BackgroundRole == C.PNL_NEG_BG`; `ForegroundRole == C.RED` | Not Run |
| UT-GUI-014.001.M02.T08 | MD-GUI-014.001.M02 | Positive | `on_cycle_closed` removes the matching row | Existing OPEN row for cycle_id=1; call `on_cycle_closed(snap)` | `rowCount() == 0`; `removeRows` emitted | Not Run |
| UT-GUI-014.001.M02.T09 | MD-GUI-014.001.M02 | Positive | `on_pending_removed` removes the matching pending row | Existing PENDING row; call `on_pending_removed(signal_id)` | `rowCount() == 0`; `removeRows` emitted | Not Run |
| UT-GUI-014.001.M02.T10 | MD-GUI-014.001.M02 | Positive | `set_scope(uid)` filters rows to that user; "All Users" shows all | 3 rows for users {1,2,3}; `set_scope(2)` | `rowCount() == 1`; row's user_id == 2 | Not Run |
| UT-GUI-014.001.M02.T11 | MD-GUI-014.001.M02 | Negative | Event payload arriving for a stale/unknown pending signal_id is a no-op (covers SRD-GUI-014.003) | Call `on_pending_removed("missing-id")` with no matching row in `_by_key` | No exception raised; no `removeRows` emitted; `rowCount()` unchanged | Not Run |
| UT-GUI-014.001.M02.T12 | MD-GUI-014.001.M02 | Negative | `on_cycle_closed(snap)` for an unknown cycle_id is a no-op (covers SRD-GUI-014.009) | `cycle_id=999` not in `_by_key` | No `removeRows` emitted; `rowCount()` unchanged; no exception | Not Run |
| UT-GUI-014.001.M02.T13 | MD-GUI-014.001.M02 | Negative | `set_scope(uid)` to a user with zero matching rows yields empty model (covers SRD-GUI-014.011) | 3 rows for users {1,2,3}; `set_scope(99)` | `rowCount() == 0`; no rows visible | Not Run |

---

## Module: `gui/active_cycles_panel.py` — ActiveCyclesPanel & _RowActionsDelegate (FO-GUI-014)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-014.001.M01.T01 | MD-GUI-014.001.M01 | Unit | Panel renders empty placeholder when row count is zero | Empty model | `_table.isHidden() == True`; `_empty_label.isVisible() == True` | Not Run |
| UT-GUI-014.001.M01.T02 | MD-GUI-014.001.M01 | Positive | Adding a pending signal hides empty state and shows table | `on_pending_added(signal)` | `_table.isVisible() == True`; `_empty_label.isHidden() == True` | Not Run |
| UT-GUI-014.001.M01.T03 | MD-GUI-014.001.M01 | Positive | Clicking Execute opens confirmation dialog | Click rect for "Execute" button on a PENDING row | A `QMessageBox` is shown with text containing `"BUY"` and symbol | Not Run |
| UT-GUI-014.001.M01.T04 | MD-GUI-014.001.M01 | Positive | Confirming Execute calls `pending_store.execute(signal_id)` and flips state to OPENING optimistically | Mock store; click Execute, click Yes on dialog | `pending_store.execute` called with signal_id; row state flips to "OPENING" within 100 ms | Not Run |
| UT-GUI-014.001.M01.T05 | MD-GUI-014.001.M01 | Positive | Dismiss button calls `pending_store.dismiss(id)` and removes row | Click `[✕]` on PENDING row | `pending_store.dismiss` called; `rowCount()` decreases by 1 | Not Run |
| UT-GUI-014.001.M01.T06 | MD-GUI-014.001.M01 | Positive | `[Edit Risk ▼]` expands inline editor row below | Click on OPEN row | New synthetic row inserted at `parent_row+1`; `setIndexWidget` called with `_RiskEditorWidget` | Not Run |
| UT-GUI-014.001.M01.T07 | MD-GUI-014.001.M01 | Positive | Opening a second editor collapses the first | Editor open for cycle 1; click Edit Risk on cycle 2 | Synthetic row for cycle 1 removed; new editor row for cycle 2 | Not Run |
| UT-GUI-014.001.M01.T08 | MD-GUI-014.001.M01 | Positive | `[Close]` opens confirmation showing PnL estimate | Click Close on OPEN row with `entry=182.5`, `ltp=185.0`, `qty=25` | Dialog text contains `"+$62.50"` (or formatted equivalent) | Not Run |
| UT-GUI-014.001.M01.T09 | MD-GUI-014.001.M01 | Positive | Confirming Close flips row to CLOSING optimistically | Click Yes on close confirmation | Row state="CLOSING"; `ExecutionEngine.exit_position(cycle_id, reason='manual')` called | Not Run |
| UT-GUI-014.001.M01.T10 | MD-GUI-014.001.M01 | Negative | `[Execute]` is visually disabled when circuit breaker is active | `app_service.circuit_breaker_active = True`; trigger paint | Delegate paints Execute with muted colour; click is swallowed (no action) | Not Run |
| UT-GUI-014.001.M01.T11 | MD-GUI-014.001.M01 | Positive | `[Close]` remains enabled when circuit breaker is active | `circuit_breaker_active = True`; click Close on OPEN row | Close confirmation dialog opens normally | Not Run |
| UT-GUI-014.001.M01.T12 | MD-GUI-014.001.M01 | Positive | Scope change triggers re-query and User column hide/show | Construct with All-Users scope; switch to single-user | `set_columnHidden(Col.USER, True)` called; rows filtered to that user | Not Run |
| UT-GUI-014.001.M01.T13 | MD-GUI-014.001.M01 | Edge | Editor auto-dismisses when its cycle's `CycleClosed` arrives | Editor open for cycle 1; emit `CycleClosed(cycle_id=1)` | Synthetic row removed; `_expanded_cycle_id is None`; DEBUG log emitted | Not Run |
| UT-GUI-014.001.M01.T14 | MD-GUI-014.001.M01 | Negative | Cancel on the Execute confirmation dialog does NOT submit (covers SRD-GUI-014.005) | Click `[Execute]` on PENDING row; click Cancel on `QMessageBox` | `pending_store.execute` NOT called; row stays state=`PENDING`; no optimistic transition fires | Not Run |
| UT-GUI-014.001.M01.T15 | MD-GUI-014.001.M01 | Negative | Dismissing a signal whose row is already gone is a no-op (covers SRD-GUI-014.006) | Row removed by an earlier `on_pending_removed`; click `[✕]` (handled stale) OR call `pending_store.dismiss` for a missing id | `pending_store.dismiss` returns `None`; no exception; `rowCount()` unchanged | Not Run |
| UT-GUI-014.001.M01.T16 | MD-GUI-014.001.M01 | Negative | Cancel on the Close confirmation dialog does NOT submit (covers SRD-GUI-014.008) | Click `[Close]` on OPEN row; click Cancel on `QMessageBox` | `ExecutionEngine.exit_position` NOT called; row stays state=`OPEN`; no optimistic flip to `CLOSING` | Not Run |
| UT-GUI-014.001.M01.T17 | MD-GUI-014.001.M01 | Negative | Empty-state placeholder is hidden when at least one row exists (covers SRD-GUI-014.010) | Insert one row via `on_pending_added(signal)` | `_empty_label.isVisible() == False`; `_table.isVisible() == True` | Not Run |

---

## Module: `gui/risk_editor_widget.py` — _RiskEditorWidget (FO-GUI-014)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-014.001.M03.T01 | MD-GUI-014.001.M03 | Unit | Widget initializes spinboxes from supplied snapshot | `CycleSnapshot(hard_stop_loss=179, target_price=189, trailing_offset=2.5, trailing_mode="$", current_price=185)` | `_hsl.value()==179`; `_target.value()==189`; `_trail_offset.value()==2.5`; `_trail_mode.currentText()=="$"` | Not Run |
| UT-GUI-014.001.M03.T02 | MD-GUI-014.001.M03 | Positive | HSL spinbox max equals snapshot's `current_price` | snap with `current_price=185.40` | `_hsl.maximum() == 185.40` | Not Run |
| UT-GUI-014.001.M03.T03 | MD-GUI-014.001.M03 | Positive | Target spinbox min equals snapshot's `current_price` | snap with `current_price=185.40` | `_target.minimum() == 185.40` | Not Run |
| UT-GUI-014.001.M03.T04 | MD-GUI-014.001.M03 | Edge | Trail offset spinbox min is 0.01 | Inspect on construction | `_trail_offset.minimum() == 0.01` | Not Run |
| UT-GUI-014.001.M03.T05 | MD-GUI-014.001.M03 | Positive | Save emits diff-only fields when nothing changed | Open with snap; click Save without edits | `cancelled` emitted with cycle_id; `saved` NOT emitted | Not Run |
| UT-GUI-014.001.M03.T06 | MD-GUI-014.001.M03 | Positive | Save emits only changed fields | Open with snap; change HSL only; click Save | `saved.emit(cycle_id, {"hard_stop_loss": new_value})`; no other keys in dict | Not Run |
| UT-GUI-014.001.M03.T07 | MD-GUI-014.001.M03 | Positive | `show_error(msg)` displays error label and clears on field edit | Call `show_error("HSL too high")`; then edit `_hsl` | Error label visible after `show_error`; hidden after edit | Not Run |
| UT-GUI-014.001.M03.T08 | MD-GUI-014.001.M03 | Negative | Cancel button discards in-progress edits and emits no `saved` signal (covers SRD-GUI-014.007 mutation rollback) | Open editor with snap (`hsl=179`); change `_hsl` to `178`; click Cancel | `cancelled` emitted with cycle_id; `saved` NOT emitted; no call to `update_risk` | Not Run |
