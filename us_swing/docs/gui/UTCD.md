# Unit Test Case Document â€” GUI Module (GUI)

**Document ID:** UTCD-GUI
**Version:** 1.5.1
**Traces To:** MD-GUI v1.7.0
**Status:** Draft
**Last Updated:** 2026-10-16
**Project:** US Swing Trading System

> v1.28.0: UT-GUI-028.* added — Candle data panel redesign; UT-GUI-021.004.M01.T01–T03 replaced.
> v1.27.0: UT-GUI-027.* added — Settings dialog.
> v1.26.0: UT-GUI-026.011–.012 Pass (Phase 3).
> v1.25.0: UT-GUI-026.008–.010 Pass (Phase 2).
> v1.24.0: UT-GUI-026.001–.007 Pass (Phase 1); UT-GUI-020.001–.003 Superseded by the Focus + Inspector layout.
> v1.23.0: UT-GUI-026.* added — Charts workspace Focus + Inspector (Not Run).
> v1.22.0: UT-GUI-025.016–.018 added — Side column, unset stop/target, P&L Today (Phase 5).
> v1.21.0: UT-GUI-025.013–.015 added — Performance band and Exposure tab (Phase 4).
> v1.20.0: UT-GUI-025.008–.012 added — tile buttons (Phase 2).
> v1.19.0: UT-GUI-025.* added — dashboard tiled workspace (Phase 1).
> v1.18.0: UT-GUI-023.* added — card layout.
> v1.17.0: UT-GUI-022.008–.011.* added — screener header, run stepper, transcript drawer, list detail.
> v1.16.0: UT-GUI-022.* added — screener result views and preset rail.
> v1.15.0: UT-GUI-018.008–.011.* added — Connections panel in the sidebar.
> v1.14.0: UT-GUI-021.* added — Settings section list.
> v1.13.0: UT-GUI-020.* added — Charts workspace.
> v1.12.0: UT-GUI-019.* added — side panels and Exit drawer.
> v1.11.0: UT-GUI-018.* added — sidebar workspace shell.
> v1.10.0: UT-GUI-017.* added — Carbon theme and icon system.
> v1.9.1: UT-GUI-006.001.M01.T17–T18 added — user edit keeps Telegram settings (ISS-GUI-0005).
> v1.9.0: UT-GUI-004.001.M01.T21–T25 added — startup cleanup of stale intraday candles (SRD-GUI-004.013).
> v1.8.0: UT-GUI-004.001.M01.T11–T19 added — manual picks (SRD-GUI-004.010–.012).
> v1.7.0: UT-GUI-004.001.M01.T08–T10 added — Execution feed skips unassigned or missing presets (ISS-GUI-0004).
> v1.6.0: UT-GUI-006.001.M01.T11–T16 added — weekly candles built from daily candles (ISS-GUI-0003).
> v1.5.1: UT-GUI-002.005.M01.T01–T03 added — Trade History side follows trade direction (ISS-GUI-0002).

> v1.5.0: UT-GUI-013.016–.019 and UT-GUI-014.016–.018 added (27 tests) — Short Trade Direction GUI surfaces (FO-EXE-018).

> v1.4.0: UT-GUI-012.001.M01.T20–T28 added — live tick worker watchdog (SRD-GUI-012.008–009).

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
| UT-GUI-004.001.M01.T08 | MD-GUI-004.001.M01 | Positive | Results of a preset with assigned users reach the Execution feed | Admin preset assigned to user 1 with a saved result for AAPL | `get_latest_screener_results()` returns AAPL with that preset's name (ISS-GUI-0004) | Pass |
| UT-GUI-004.001.M01.T09 | MD-GUI-004.001.M01 | Negative | Results of a preset with no assigned users are excluded | Admin preset with empty `assigned_to` and a saved result for MSFT | MSFT not returned (ISS-GUI-0004) | Pass |
| UT-GUI-004.001.M01.T10 | MD-GUI-004.001.M01 | Negative | Results of a deleted preset are excluded | Result folder `preset_<id>` with no matching preset file | Nothing returned for that folder (ISS-GUI-0004) | Pass |
| UT-GUI-004.001.M01.T11 | MD-GUI-004.001.M01 | Positive | Valid pick is saved and the list refreshes | " tsla " with TSLA in universe | Store holds TSLA; one refresh | Pass |
| UT-GUI-004.001.M01.T12 | MD-GUI-004.001.M01 | Negative | Unknown, duplicate, empty or too-early pick is refused | XYZ / existing AAPL / blank / empty universe | Matching message; store unchanged; no refresh | Pass |
| UT-GUI-004.001.M01.T13 | MD-GUI-004.001.M01 | Edge | IBKR form is stored in universe form | "brk b" | Store holds BRK.B | Pass |
| UT-GUI-004.001.M01.T14 | MD-GUI-004.001.M01 | Positive | Removing a pick saves the shorter list and drops it from the engine list | Picks AAPL, TSLA; remove AAPL; no open trade | Store holds TSLA; one refresh; engine list TSLA | Pass |
| UT-GUI-004.001.M01.T15 | MD-GUI-004.001.M01 | Positive | Picks lead the feed, need no users and win over a screener row | Picks TSLA, MSFT; preset result AAPL, MSFT | TSLA, MSFT (pick), AAPL (scheduled) | Pass |
| UT-GUI-004.001.M01.T16 | MD-GUI-004.001.M01 | Edge | Picks show with no screener results on disk | Pick TSLA; no results folder | TSLA only | Pass |
| UT-GUI-004.001.M01.T17 | MD-GUI-004.001.M01 | Negative | Pick change sends no "screener approved" message | `_refresh_after_pick_change()` | Flag False during refresh, True after | Pass |
| UT-GUI-004.001.M01.T18 | MD-GUI-004.001.M01 | Positive | Ledger records picks apart | Pick TSLA + Momentum AAPL | (Momentum, AAPL) then (Manual pick, TSLA) | Pass |
| UT-GUI-004.001.M01.T19 | MD-GUI-004.001.M01 | Positive | Picks stay on top in either sort order | Proxy sorted by score asc / desc | Row 0 is "★ TSLA" with "✕ Remove" | Pass |
| UT-GUI-004.001.M01.T20 | MD-GUI-004.001.M01 | Edge | A removed pick with an open trade stays on the engine list | Remove AAPL while AAPL has an open trade | Engine list keeps AAPL | Pass |
| UT-GUI-004.001.M01.T21 | MD-GUI-004.001.M01 | Positive | Stale stock's intraday rows are deleted from all three tables | OLD newest bar 10 days before newest DB bar; not kept | OLD gone from price_1m/3m/15m; returns [OLD] | Pass |
| UT-GUI-004.001.M01.T22 | MD-GUI-004.001.M01 | Negative | Kept stock is not deleted even when idle | OLD idle 10 days but in keep-set | OLD rows remain | Pass |
| UT-GUI-004.001.M01.T23 | MD-GUI-004.001.M01 | Edge | Stock idle less than the retention period is kept | Newest bar 3 days old, retention 5 | Rows remain | Pass |
| UT-GUI-004.001.M01.T24 | MD-GUI-004.001.M01 | Edge | A long break deletes nothing | Every stock's newest bar 30 days before today | Nothing deleted (idle is relative to newest DB bar) | Pass |
| UT-GUI-004.001.M01.T25 | MD-GUI-004.001.M01 | Negative | Cleanup is skipped when open trades cannot be read | `_tc_query` is None | `remove_stale_intraday` not called | Pass |

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
| UT-GUI-006.001.M01.T05 | MD-GUI-006.001.M01 | Negative | Candle reset succeeds while another connection holds the database open | Open a second `sqlite3` connection on candles.db, then reset | No exception; `price_1d` and `price_1w` are empty (ISS-GUI-0001) | Pass |
| UT-GUI-006.001.M01.T06 | MD-GUI-006.001.M01 | Positive | Candle reset keeps the trading tables in the same file | DB with rows in price_1d, price_1w, trade_cycles, strategies | Candle tables empty; `trade_cycles` and `strategies` rows retained | Pass |
| UT-GUI-006.001.M01.T07 | MD-GUI-006.001.M01 | Positive | Candle reset leaves the intraday price tables untouched | DB with one `price_1m` row | `price_1m` still has 1 row after reset | Pass |
| UT-GUI-006.001.M01.T08 | MD-GUI-006.001.M01 | Edge | Candle reset never unlinks the database file | Existing candles.db | File still exists after reset | Pass |
| UT-GUI-006.001.M01.T09 | MD-GUI-006.001.M01 | Positive | Candle reset clears ancillary files and refreshes status | Checkpoint and failed-symbols files present | Both files deleted; download stopped; status refresh called | Pass |
| UT-GUI-006.001.M01.T10 | MD-GUI-006.001.M01 | Edge | Candle reset on a fresh path creates empty candle tables | No candles.db at the configured path | `price_1d` and `price_1w` exist and are empty | Pass |
| UT-GUI-006.001.M01.T11 | MD-GUI-006.001.M01 | Positive | Weekly candle aggregates a full week of daily candles | Five daily rows Mon–Fri for one symbol | One `price_1w` row dated Friday; open = Monday open, high = max, low = min, close = Friday close, volume = sum (ISS-GUI-0003) | Pass |
| UT-GUI-006.001.M01.T12 | MD-GUI-006.001.M01 | Negative | Rebuild removes stale weekly rows for the same week | Daily rows Mon–Wed; `price_1w` already holds a Tue-dated and a cut-short Fri-dated row for that week | Exactly one `price_1w` row for the week, dated Wednesday, with full Mon–Wed values (ISS-GUI-0003) | Pass |
| UT-GUI-006.001.M01.T13 | MD-GUI-006.001.M01 | Edge | Holiday-short week is dated on its last trading day | Daily rows Mon–Thu (Friday holiday) | One `price_1w` row dated Thursday (ISS-GUI-0003) | Pass |
| UT-GUI-006.001.M01.T14 | MD-GUI-006.001.M01 | Edge | Rebuild only touches the given symbol | Weekly rows for AAPL and MSFT; rebuild AAPL | MSFT weekly rows unchanged (ISS-GUI-0003) | Pass |
| UT-GUI-006.001.M01.T15 | MD-GUI-006.001.M01 | Positive | Download worker no longer requests IBKR weekly bars | Run `_download_all` with a fake IB returning daily bars | No `1 week` request made; `price_1w` built from the saved daily bars; `inserted_1w` = weekly rows written (ISS-GUI-0003) | Pass |
| UT-GUI-006.001.M01.T16 | MD-GUI-006.001.M01 | Negative | Symbol with no daily bars is reported and writes nothing | Fake IB returns no daily bars | `symbol_failed(symbol, "NO_DATA")` emitted; no `price_1w` rows (ISS-GUI-0003) | Pass |
| UT-GUI-006.001.M01.T17 | MD-GUI-006.001.M01 | Negative | Editing a user keeps fields the dialog does not show | User with Telegram on, chat id, notify toggles, configs; change display name | All hidden fields unchanged (ISS-GUI-0005) | Pass |
| UT-GUI-006.001.M01.T18 | MD-GUI-006.001.M01 | Positive | A new user starts with defaults | `_UserDialog(None)` | id -1, Telegram off, empty chat id (ISS-GUI-0005) | Pass |

---

## Module: `gui/scheduler_dialog.py` / `gui/scheduler_store.py` — Windows Task Scheduler (Auto Close)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-000.003.T01 | MD-GUI-000.003 | Unit | Missing close section returns disabled default | `load_close_config()` on empty store | `enabled is False`; `close_time == "16:30"` | Pass |
| UT-GUI-000.003.T02 | MD-GUI-000.003 | Unit | Saved close config round-trips through JSON | `save_close_config(CloseConfig(True, "23:00"))` then load | Loaded `enabled is True`; `close_time == "23:00"` | Pass |
| UT-GUI-000.003.T03 | MD-GUI-000.003 | Unit | Delete reverts close config to default | Save, then `delete_close_config()`; load | `enabled is False` | Pass |
| UT-GUI-000.003.T04 | MD-GUI-000.003 | Unit | Saving close config leaves usswing section intact | Save usswing + close configs | usswing `task_name` and close `close_time` both preserved | Pass |
| UT-GUI-000.004.T01 | MD-GUI-000.004 | Unit | USSwing close task force-kills exe on weekdays | `create_usswing_close_task(cfg, "16:30")` | schtasks args include `USSwing_App_Close`, `taskkill /IM USSwing.exe /F`, `weekly`, `MON,TUE,WED,THU,FRI` | Pass |
| UT-GUI-000.004.T02 | MD-GUI-000.004 | Unit | IBKR close task uses tws image and daily schedule | `create_ibkr_close_task(cfg, "23:00")` | schtasks args include `USSwing_IBKR_Close`, `taskkill /IM tws.exe /F`, `daily` | Pass |

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

### Tick worker watchdog (SRD-GUI-012.008–009)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-012.001.M01.T20 | MD-GUI-004.001.M01 | Positive | Watchdog restarts the worker when its thread has finished | `_tick_worker` is a finished worker; status CONNECTED; call `_check_tick_health()` | A new `LiveTickWorker` is built and started; `_tick_worker` points at it | Pass |
| UT-GUI-012.001.M01.T21 | MD-GUI-004.001.M01 | Edge | Outage warning is logged once, not on every watchdog check | Two consecutive checks with a finished worker each time | Exactly one `Live prices stopped` message emitted | Pass |
| UT-GUI-012.001.M01.T22 | MD-GUI-004.001.M01 | Negative | A running worker is never restarted | `_tick_worker.isFinished()` returns False; call `_check_tick_health()` | No worker constructed; `_tick_worker` unchanged | Pass |
| UT-GUI-012.001.M01.T23 | MD-GUI-004.001.M01 | Negative | Watchdog does nothing while the feed is disconnected | status DISCONNECTED and `_tick_worker` is None; call `_check_tick_health()` | No worker constructed; `_tick_worker` stays None | Pass |
| UT-GUI-012.001.M01.T24 | MD-GUI-004.001.M01 | Positive | `finished` releases the current worker for replacement | Call `_on_tick_worker_finished(tw)` where `tw is _tick_worker` | `_tick_worker` is None; `deleteLater()` called once | Pass |
| UT-GUI-012.001.M01.T25 | MD-GUI-004.001.M01 | Negative | A late `finished` signal does not drop a newer worker | Call `_on_tick_worker_finished(old)` while `_tick_worker` holds a newer worker | `_tick_worker` still holds the newer worker; its `deleteLater()` not called | Pass |
| UT-GUI-012.001.M01.T26 | MD-GUI-004.001.M01 | Edge | Tick silence is reported but never triggers a reconnect | Running worker, `_last_tick_at` None, market open; call `_check_tick_health()` | `No live price updates` warning emitted; no worker constructed | Pass |
| UT-GUI-012.001.M01.T27 | MD-GUI-004.001.M01 | Negative | Overnight silence raises no warning | Running worker, `_last_tick_at` None, market closed; call `_check_tick_health()` | No `No live price updates` message emitted | Pass |
| UT-GUI-012.001.M01.T28 | MD-GUI-004.001.M01 | Positive | A fresh tick re-arms the stale warning for the next outage | `_tick_stale_logged` True, `_last_tick_at` just now, market open | `_tick_stale_logged` reset to False | Pass |

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
| UT-GUI-014.001.M03.T09 | MD-GUI-014.001.M03 | Positive | Trail mode dropdown shows "Off" selected when the cycle has no trailing | Open editor with `trailing_mode=None` | `_trail_mode.currentText() == "Off"` | Pass |
| UT-GUI-014.001.M03.T10 | MD-GUI-014.001.M03 | Positive | Switching a trailing cycle to "Off" saves an empty trailing mode | Open with `trailing_mode="$"`; set dropdown to "Off"; collect fields | `_collect_changed_fields()["trailing_mode"] == ""` | Pass |

---

## Module: `gui/strategy_builder_dialog.py` — Direction selector (FO-EXE-018)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-013.016.M01.T01 | MD-GUI-013.001.M01 | Positive | New strategy defaults to Long | open Add dialog | `_direction_combo.currentData() == "LONG"` | Pass |
| UT-GUI-013.016.M01.T02 | MD-GUI-013.001.M01 | Positive | Short choice is saved | fill required fields; pick `Short`; Save | emitted `StrategyConfig.direction == "SHORT"` | Pass |
| UT-GUI-013.016.M01.T03 | MD-GUI-013.001.M01 | Positive | Edit loads stored direction | open Edit with `cfg.direction="SHORT"` | combo shows `Short` | Pass |
| UT-GUI-013.017.M01.T04 | MD-GUI-013.001.M01 | Negative | Direction locked while trades are open | open Edit with `has_open_trades=True` | combo disabled; tooltip `Close open trades before changing direction`; other fields enabled | Pass |
| UT-GUI-013.017.M01.T05 | MD-GUI-013.001.M01 | Positive | Direction editable with no open trades | open Edit with `has_open_trades=False` | combo enabled | Pass |
| UT-GUI-013.018.M01.T06 | MD-GUI-013.001.M01 | Positive | No-stop note for Short | pick `Short`; stop loss off | amber note visible; Save still emits `saved` | Pass |
| UT-GUI-013.018.M01.T07 | MD-GUI-013.001.M01 | Negative | No note when stop is on or Long | Short + stop on; then Long + stop off | note hidden in both cases | Pass |
| UT-GUI-013.016.M01.T08 | MD-GUI-013.001.M01 | Negative | Unknown stored direction shows Long | open Edit with `cfg.direction="SIDEWAYS"`; Save | combo shows `Long`; saved `direction == "LONG"` | Pass |
| UT-GUI-013.020.M01.T01 | MD-GUI-013.001.M01 | Positive | Direction text is coloured by side | new dialog; switch Short then back to Long | stylesheet carries green, then red only, then green | Pass |
| UT-GUI-013.021.M01.T01 | MD-GUI-004.001.M01 | Positive | An open trade reports live trades | strategy with one open symbol | `has_live_or_pending_trades` True | Pass |
| UT-GUI-013.021.M01.T02 | MD-GUI-004.001.M01 | Positive | A waiting signal counts too | no open trade, one pending signal for the strategy | `has_live_or_pending_trades` True | Pass |
| UT-GUI-013.021.M01.T03 | MD-GUI-004.001.M01 | Negative | Another strategy's signal does not lock | pending signal for a different strategy | `has_live_or_pending_trades` False | Pass |

---

## Module: `gui/strategy_table_model.py` — Direction column (FO-EXE-018)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-013.019.M02.T01 | MD-GUI-004.001.M02 | Positive | Direction column shows Short | model loaded with one `direction="SHORT"` config | `headerData(COL_DIRECTION) == "Direction"`; cell `"Short"` | Pass |
| UT-GUI-013.019.M02.T02 | MD-GUI-004.001.M02 | Edge | Legacy config shows Long | config without an explicit direction | cell `"Long"` | Pass |
| UT-GUI-013.020.M02.T02 | MD-GUI-004.001.M02 | Positive | Direction column is coloured by side | rows for a SHORT and a LONG strategy | foreground red for Short, green for Long | Pass |

---

## Module: `gui/active_cycles_model.py` & `gui/active_cycles_panel.py` — Direction in Active Trades (FO-EXE-018)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-014.016.M02.T01 | MD-GUI-014.001.M02 | Positive | Short cycle row shows red Short | `on_cycle_opened(snap(direction="SHORT"))` | Side cell `"Short"`; foreground `C.RED` | Pass |
| UT-GUI-014.016.M02.T02 | MD-GUI-014.001.M02 | Positive | Pending Long row shows green Long | `on_pending_added(signal(direction="LONG"))` | Side cell `"Long"`; foreground `C.GREEN` | Pass |
| UT-GUI-014.016.M02.T03 | MD-GUI-014.001.M02 | Negative | Unknown direction never shows blank or Short | `on_cycle_opened(snap(direction=""))` | Side cell `"Long"`; foreground `C.GREEN` | Pass |
| UT-GUI-014.017.M01.T01 | MD-GUI-014.001.M01 | Positive | Short entry confirm says Sell short | Execute on pending SHORT ENTRY row | dialog text starts `Submit Sell short`; affordability check called | Pass |
| UT-GUI-014.017.M01.T02 | MD-GUI-014.001.M01 | Positive | Short exit confirm says Buy to cover | Execute on pending SHORT EXIT row | dialog text starts `Submit Buy to cover`; affordability check not called | Pass |
| UT-GUI-014.017.M01.T03 | MD-GUI-014.001.M01 | Positive | Close on Short cycle says Buy to cover | Close on OPEN SHORT row, entry 100, ltp 97, qty 10 | text contains `Buy to cover 10 × ` and `+$30.00` | Pass |
| UT-GUI-014.017.M01.T04 | MD-GUI-014.001.M01 | Negative | Short entry blocked when margin is short | pending SHORT ENTRY; `margin_available()` below qty × price | confirm button disabled; red warning shown | Pass |
| UT-GUI-014.017.M01.T05 | MD-GUI-014.001.M01 | Edge | Long verbs unchanged | Execute on LONG ENTRY; Close on OPEN LONG | `Buy` and `Sell` | Pass |

---

## Module: `gui/risk_editor_widget.py` — Short ranges (FO-EXE-018)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-014.018.M03.T01 | MD-GUI-014.001.M03 | Positive | Short ranges flip around price | snap `direction="SHORT"`, `current_price=100` | `_hsl.minimum() == 100`; `_target.maximum() == 100` | Pass |
| UT-GUI-014.018.M03.T02 | MD-GUI-014.001.M03 | Negative | Short stop cannot go below price | same snap; `_hsl.setValue(95)` | `_hsl.value() == 100` | Pass |
| UT-GUI-014.018.M03.T03 | MD-GUI-014.001.M03 | Edge | Long ranges unchanged | snap `direction="LONG"`, `current_price=100` | `_hsl.maximum() == 100`; `_target.minimum() == 100` | Pass |
| UT-GUI-014.018.M03.T04 | MD-GUI-014.001.M03 | Negative | Saving a Short with no stop adds no stop | snap `direction="SHORT"`, `hard_stop_loss=0.0`; collect fields, then set stop 105 | first collect has no `hard_sl`; after edit `hard_sl == 105` | Pass |

---

## Module: `gui/app_service.py` — Trade History side (FO-EXE-018, ISS-GUI-0002)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-002.005.M01.T01 | MD-GUI-004.001.M01 | Positive | Closed short shows SELL entry and BUY cover | history snap `direction="SHORT"`, closed | entry row `SELL`; exit row `BUY` | Pass |
| UT-GUI-002.005.M01.T02 | MD-GUI-004.001.M01 | Edge | Closed long unchanged | history snap `direction="LONG"`, closed | entry row `BUY`; exit row `SELL` | Pass |
| UT-GUI-002.005.M01.T03 | MD-GUI-004.001.M01 | Negative | Short entry fill log names a Sell | short snap; `FILLED` event for its entry order | log starts `[Orders] KVUE Sell fill confirmed` | Pass |


---

## FO-GUI-015 — Indicator Rule Library Dialog

Test files: `tests/gui/test_indicator_rule_model.py` (M02, M03), `tests/gui/test_indicator_library_model.py` (M04), `tests/gui/test_indicator_rules_dialog.py` (M01, M05, M06, wiring).

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-015.002.M01.T01 | MD-GUI-015.002.M01 | Positive | Moved base keeps title bar and content layout | `FramelessDialog("X")` | title label "X"; 3 window buttons; `content_layout()` is a `QVBoxLayout` | Pass |
| UT-GUI-015.002.M01.T02 | MD-GUI-015.002.M01 | Negative | Close button rejects | click ✕ | `result() == Rejected` | Pass |
| UT-GUI-015.008.M02.T01 | MD-GUI-015.008.M02 | Positive | Table has the 7 columns | empty model | headers On, Indicator, Condition, Value, To, Settings, "" | Pass |
| UT-GUI-015.008.M02.T02 | MD-GUI-015.008.M02 | Positive | Add appends default rule and signals | `add_rule("rsi")` | 1 row; `rules_changed` emitted once | Pass |
| UT-GUI-015.008.M02.T03 | MD-GUI-015.008.M02 | Negative | Unknown indicator adds no row | `add_rule("nope")` | raises `IndicatorRuleError`; 0 rows | Pass |
| UT-GUI-015.009.M02.T01 | MD-GUI-015.008.M02 | Positive | To is editable for between | RSI rule between | To cell flag `ItemIsEditable` | Pass |
| UT-GUI-015.009.M02.T02 | MD-GUI-015.008.M02 | Negative | To is locked for at least | ATR rule at least | To not editable; shows "—" | Pass |
| UT-GUI-015.009.M02.T03 | MD-GUI-015.008.M02 | Positive | Switching to between fills To | ATR at least → between | `to == spec.value_max` | Pass |
| UT-GUI-015.012.M02.T01 | MD-GUI-015.008.M02 | Positive | Disabled row is dimmed | `set_enabled(0, False)` | foreground `C.MUTED`; rule `enabled False` | Pass |
| UT-GUI-015.012.M02.T02 | MD-GUI-015.008.M02 | Negative | Removing a bad row index does nothing | `remove_row(9)` on 1 row | still 1 row; no signal | Pass |
| UT-GUI-015.009.M03.T01 | MD-GUI-015.009.M03 | Positive | Condition combo lists only allowed conditions | editor for MACD row | 4 items, crosses above first | Pass |
| UT-GUI-015.010.M03.T01 | MD-GUI-015.009.M03 | Positive | Value spinbox uses spec range and unit | editor for ATR % row | range `value_min..value_max`; suffix "%" | Pass |
| UT-GUI-015.010.M03.T02 | MD-GUI-015.009.M03 | Negative | Value above max is clamped | type 999 in RSI editor | committed value 100 | Pass |
| UT-GUI-015.012.M03.T01 | MD-GUI-015.009.M03 | Positive | Clicking the switch flips On | click centre of `switch_rect` | rule `enabled` toggles | Pass |
| UT-GUI-015.012.M03.T02 | MD-GUI-015.009.M03 | Positive | Clicking ✕ removes the row | click ✕ cell | row count drops by 1 (waitUntil) | Pass |
| UT-GUI-015.012.M03.T03 | MD-GUI-015.009.M03 | Negative | Click outside the switch does nothing | click cell corner | `enabled` unchanged | Pass |
| UT-GUI-015.015.M03.T01 | MD-GUI-015.009.M03 | Positive | Inline editor styles suppress focus outline | condition and spin editors | stylesheet contains `outline: none` | Pass |
| UT-GUI-015.015.M03.T02 | MD-GUI-015.009.M03 | Negative | No fixed heights in the new GUI modules | source of the 5 new modules (moved `frameless_dialog.py` keeps its 38 px title bar) | no `setFixedHeight` / `setFixedSize` calls | Pass |
| UT-GUI-015.003.M04.T01 | MD-GUI-015.003.M04 | Positive | Categories follow enum order and empty ones are hidden | `LibraryTreeModel()` | no Dividends/Others row; Price first | Pass |
| UT-GUI-015.003.M04.T02 | MD-GUI-015.003.M04 | Positive | Category shows used / total | `set_usage({"rsi": 1})` | Momentum text ends "1 / 7" | Pass |
| UT-GUI-015.003.M04.T03 | MD-GUI-015.003.M04 | Negative | Category rows cannot be selected or dragged | Momentum category index | flags lack `ItemIsSelectable` and `ItemIsDragEnabled` | Pass |
| UT-GUI-015.004.M04.T01 | MD-GUI-015.003.M04 | Positive | Search keeps matches and parent | filter "macd" | 3 items under Momentum | Pass |
| UT-GUI-015.004.M04.T02 | MD-GUI-015.003.M04 | Negative | Search with no match empties the tree | filter "zzz" | proxy `rowCount() == 0` | Pass |
| UT-GUI-015.005.M04.T01 | MD-GUI-015.003.M04 | Positive | In-use tag follows usage | usage `{"ema_50": 1}` then `{}` | `InUseRole` True then False | Pass |
| UT-GUI-015.005.M04.T02 | MD-GUI-015.003.M04 | Negative | Unused indicator has no tag | usage `{"rsi": 1}` | `find_item("macd")` `InUseRole` False | Pass |
| UT-GUI-015.006.M04.T01 | MD-GUI-015.003.M04 | Positive | Unavailable item is disabled with reason | `find_item("rvol_5m")` | not enabled; tooltip "needs intraday data" | Pass |
| UT-GUI-015.006.M04.T02 | MD-GUI-015.003.M04 | Negative | Double-click on unavailable item emits nothing | double-click `rvol_5m` | no `indicator_activated` | Pass |
| UT-GUI-015.011.M05.T01 | MD-GUI-015.011.M05 | Positive | One spinbox per param with ranges | MACD spec | `param_fast`, `param_slow`, `param_signal`; edits returned by `get_params()` | Pass |
| UT-GUI-015.011.M05.T02 | MD-GUI-015.011.M05 | Negative | Reset restores defaults | change fast to 5, click Reset | `get_params()["fast"] == 12` | Pass |
| UT-GUI-015.001.M06.T01 | MD-GUI-015.001.M06 | Positive | Dialog builds both panes | `IndicatorRulesDialog({})` | title "Indicator Filters"; named widgets present | Pass |
| UT-GUI-015.001.M06.T02 | MD-GUI-015.001.M06 | Negative | Cancel does not change the input config | edit a row, click Cancel | `Rejected`; input dict unchanged | Pass |
| UT-GUI-015.007.M06.T01 | MD-GUI-015.001.M06 | Positive | Adding an indicator adds a row and tags it | `_add_indicator("ema_50")` | new row; tree tag "in use" | Pass |
| UT-GUI-015.007.M06.T02 | MD-GUI-015.001.M06 | Negative | Unavailable indicator is not added | `_add_indicator("rvol_5m")` | row count unchanged | Pass |
| UT-GUI-015.007.M06.T03 | MD-GUI-015.001.M06 | Positive | Dropping an indicator adds a row | drop mime `rsi` on table | one RSI row appended | Pass |
| UT-GUI-015.013.M06.T01 | MD-GUI-015.001.M06 | Positive | Legacy config loads as 6 rows | legacy 6-section dict | 6 rows; RS row off | Pass |
| UT-GUI-015.013.M06.T02 | MD-GUI-015.001.M06 | Positive | OK returns a reloadable rule-list config | add EMA(50), `get_config()` | `schema 2`; reloads same rows | Pass |
| UT-GUI-015.013.M06.T03 | MD-GUI-015.001.M06 | Negative | Bad saved config starts empty and is kept | rule with unknown id; press OK without edits | 0 rows; WARNING `[Screener]` logged; `get_config()` returns the original config | Pass |
| UT-GUI-015.014.M01.T01 | MD-GUI-003.001.M01 | Positive | Group "Configure…" stores the new config | patched dialog accepts | `_configs[sid]` has `schema 2`; `changed` emitted | Pass |
| UT-GUI-015.014.M01.T02 | MD-GUI-003.001.M01 | Negative | Cancel keeps the old config | patched dialog rejects | `_configs[sid]` unchanged | Pass |

## FO-GUI-016 — Price Action Pattern Library Dialog

Test files:
- `tests/gui/test_pattern_rule_model.py` (M07, shared M03 delegates)
- `tests/gui/test_price_action_rules_dialog.py` (M08, M04, M05, wiring)
- The existing FO-GUI-015 tests stay as regression tests for M02–M06.

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-016.004.M07.T01 | MD-GUI-016.004.M07 | Positive | Model shows 4 columns with pattern name and settings text | rule `hammer` | headers On, Pattern, Settings, ""; text "Hammer", "1-bar window" | Pass |
| UT-GUI-016.004.M07.T02 | MD-GUI-016.004.M07 | Negative | Unknown pattern cannot be added; bad row remove is a no-op | `add_rule("nope")`; `remove_row(9)` | `PatternRuleError`; row count unchanged | Pass |
| UT-GUI-016.008.M07.T01 | MD-GUI-016.004.M07 | Positive | Disable dims the row and emits change | `set_enabled(0, False)` | foreground `C.MUTED`; `rules_changed` emitted | Pass |
| UT-GUI-016.008.M07.T02 | MD-GUI-016.004.M07 | Negative | Toggling a missing row does nothing | `set_enabled(9, False)` on 1 row | rules unchanged; no `rules_changed` | Pass |
| UT-GUI-016.005.M03.T01 | MD-GUI-015.009.M03 | Positive | Toggle and remove delegates act on the pattern model | release inside switch / ✕ rect | rule disabled; row removed | Pass |
| UT-GUI-016.005.M03.T02 | MD-GUI-015.009.M03 | Negative | Delegates ignore a model without the rule-row API | release on a plain `QStandardItemModel` | returns False; nothing changes | Pass |
| UT-GUI-016.002.M04.T01 | MD-GUI-015.003.M04 | Positive | Tree built from the pattern catalogue | `LibraryTreeModel(entries=PATTERNS, categories=PatternCategory)` | 7 category rows; `find_item("hammer")` exists | Pass |
| UT-GUI-016.002.M04.T02 | MD-GUI-015.003.M04 | Negative | Default tree is still the indicator catalogue | `LibraryTreeModel()` | `find_item("rsi")` exists; `find_item("hammer")` None | Pass |
| UT-GUI-016.006.M05.T01 | MD-GUI-015.011.M05 | Positive | Params popup edits a pattern spec | `IndicatorParamsDialog(get_pattern("vcp"), {})` | `param_lookback`, `param_contractions`, `param_final_depth` present | Pass |
| UT-GUI-016.001.M08.T01 | MD-GUI-016.001.M08 | Positive | Dialog builds both panes | `PriceActionRulesDialog({})` | title "Price Action Patterns"; named widgets present | Pass |
| UT-GUI-016.001.M08.T02 | MD-GUI-016.001.M08 | Negative | Cancel does not change the input config | edit a row, click Cancel | `Rejected`; input dict unchanged | Pass |
| UT-GUI-016.003.M08.T01 | MD-GUI-016.001.M08 | Positive | Adding a pattern adds a row and tags it | `_add_pattern("hammer")` | new row; tree tag "in use"; header count up | Pass |
| UT-GUI-016.003.M08.T02 | MD-GUI-016.001.M08 | Positive | Dropping a pattern adds a row | drop mime `doji` on table | one Doji row appended | Pass |
| UT-GUI-016.003.M08.T03 | MD-GUI-016.001.M08 | Negative | Unknown id adds nothing | `_add_pattern("nope")` | row count unchanged; WARNING `[Screener]` | Pass |
| UT-GUI-016.007.M08.T01 | MD-GUI-016.001.M08 | Positive | Threshold box saves a fraction | set `threshold_spin` 40 | `get_config()["threshold"] == 0.4` | Pass |
| UT-GUI-016.007.M08.T02 | MD-GUI-016.001.M08 | Edge | Out-of-range saved threshold is clamped in the box | config threshold 1.7 | spin shows 100 | Pass |
| UT-GUI-016.007.M08.T03 | MD-GUI-016.001.M08 | Negative | Box refuses values below 0 % | `threshold_spin.setValue(-10)` | spin shows 0; `get_config()["threshold"] == 0.0` | Pass |
| UT-GUI-016.006.M08.T01 | MD-GUI-016.001.M08 | Positive | Settings popup saves params | patched popup accepts `{"within": 3}` | rule params `within` 3; cell text "3-bar window" | Pass |
| UT-GUI-016.009.M08.T01 | MD-GUI-016.001.M08 | Positive | Legacy config loads as 5 rows with 20% | `{}` | 5 rows (2 on); spin 20 | Pass |
| UT-GUI-016.009.M08.T02 | MD-GUI-016.001.M08 | Positive | OK returns a reloadable rule-list config | add Hammer, `get_config()` | `schema 2`; reloads same rows | Pass |
| UT-GUI-016.009.M08.T03 | MD-GUI-016.001.M08 | Negative | Bad saved config starts empty and is kept | rule with unknown id; OK without edits | 0 rows; WARNING logged; `get_config()` returns the original | Pass |
| UT-GUI-016.011.M08.T01 | MD-GUI-016.001.M08 | Positive | Style rules are followed | dialog widgets | no fixed heights on buttons/inputs; threshold spin QSS has `outline: none` | Pass |
| UT-GUI-016.011.M08.T02 | MD-GUI-016.001.M08 | Negative | Warning text shows no internal names | bad saved config | log starts `[Screener]`; no class names or snake_case words | Pass |
| UT-GUI-016.010.M01.T01 | MD-GUI-003.001.M01 | Positive | Group and weighted call sites store the new config | patched dialog accepts | stored config has `schema 2`; group emits `changed` | Pass |
| UT-GUI-016.010.M01.T02 | MD-GUI-003.001.M01 | Negative | Cancel keeps the old config; old dialog is gone | patched dialog rejects; module attrs | config unchanged; no `_PriceActionConfigDialog` | Pass |

## FO-GUI-017 — Carbon Theme and Icon System

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-017.001.M02.T01 | MD-GUI-017.001.M02 | Positive | Carbon is the default theme | no saved theme file | `load_theme_id()` "carbon"; palette BG `#0c0f13` | Pass |
| UT-GUI-017.001.M02.T02 | MD-GUI-017.001.M02 | Negative | Unknown saved theme falls back to Carbon | saved id "neon" | "carbon" | Pass |
| UT-GUI-017.001.M02.T03 | MD-GUI-017.001.M02 | Positive | Carbon QSS has no Mocha colours left and same colour keys | `CARBON_QSS`, `THEME_COLORS` | no Mocha hex in QSS; carbon keys == mocha keys | Pass |
| UT-GUI-017.002.M02.T01 | MD-GUI-017.001.M02 | Negative | Missing font file does not stop the app | font dir with one bad path | other fonts load; `[Theme]` WARNING | Pass |
| UT-GUI-017.003.M01.T01 | MD-GUI-017.003.M01 | Positive | Icon is built in the role colour | `icon("plus", "add")` | non-null icon; rendered SVG uses `C.GREEN` | Pass |
| UT-GUI-017.003.M01.T02 | MD-GUI-017.003.M01 | Negative | Unknown icon name | `icon("nope")` | empty icon; WARNING logged | Pass |
| UT-GUI-017.003.M01.T03 | MD-GUI-017.003.M01 | Positive | Cache reuses and clears | same call twice; then `clear_cache()` | same key hit; cache empty after clear | Pass |
| UT-GUI-017.003.M01.T04 | MD-GUI-017.003.M01 | Positive | Icon-only button has tooltip and accessible name | `icon_button("refresh", "info", "Refresh")` | tooltip and accessible name "Refresh" | Pass |
| UT-GUI-017.004.M01.T01 | MD-GUI-017.003.M01 | Positive | No emoji on buttons and tabs | GUI panel source files | no emoji in button, tab, action or `setText` text | Pass |
| UT-GUI-017.005.M01.T01 | MD-GUI-017.003.M01 | Positive | Risky buttons are marked danger in every theme | Square Off All, Delete, Trip Circuit Breaker; all 3 QSS | `role` property "danger"; each QSS has the danger selector | Pass |

## FO-GUI-018 — Sidebar Workspace Shell

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-018.001.M01.T01 | MD-GUI-018.001.M01 | Positive | Nav click asks for that screen | click third item | `page_requested(2)`; item checked | Pass |
| UT-GUI-018.002.M01.T01 | MD-GUI-018.001.M01 | Positive | Mini mode hides labels, keeps tooltips | `set_mini(True)` | buttons have no text; tooltips are labels | Pass |
| UT-GUI-018.004.M01.T01 | MD-GUI-018.001.M01 | Positive | Footer shows user details | stub service, viewing user 1 | username, mode, IBKR, risk, `Cap` and `Avail` values | Pass |
| UT-GUI-018.004.M01.T02 | MD-GUI-018.001.M01 | Negative | Footer handles All Users and missing user | viewing `None`; then unknown id | "All Users" with count; no crash | Pass |
| UT-GUI-018.006.M02.T01 | MD-GUI-018.006.M02 | Positive | Reveal animates and reports | register 0→200, request open | width ends 200; `revealed("x", True)` once | Pass |
| UT-GUI-018.006.M02.T02 | MD-GUI-018.006.M02 | Negative | Unknown name is ignored | request "nope" | no error; no `revealed` | Pass |
| UT-GUI-018.006.M02.T03 | MD-GUI-018.006.M02 | Edge | Request during animation restarts from current size | open then close mid-way | ends at closed size; last `revealed` is False | Pass |
| UT-GUI-018.002.M03.T01 | MD-GUI-018.005.M03 | Positive | Wide screen auto-shrinks and restores | page Execution then Dashboard | slot 56 then 200 | Pass |
| UT-GUI-018.002.M03.T02 | MD-GUI-018.005.M03 | Negative | Auto restore keeps user's mini choice | user mini on; Execution then Dashboard | slot stays 56 | Pass |
| UT-GUI-018.008.M04.T01 | MD-GUI-018.008.M04 | Positive | Live rows | connected, online | "Online"; "Live"; "127.0.0.1:7497"; tip "Disconnect" | Pass |
| UT-GUI-018.008.M04.T02 | MD-GUI-018.008.M04 | Negative | Offline rows | disconnected, offline | "Offline"; "Not connected"; tip "Connect" | Pass |
| UT-GUI-018.008.M04.T03 | MD-GUI-018.008.M04 | Positive | Power button connects and disconnects | click when disconnected; click when connected, confirm Yes | `connect_feed` once; `disconnect_feed` once | Pass |
| UT-GUI-018.008.M04.T04 | MD-GUI-018.008.M04 | Edge | Button off during probe | status reconnecting | power disabled; "Connecting…" | Pass |
| UT-GUI-018.009.M04.T01 | MD-GUI-018.008.M04 | Positive | Retry shows attempt and countdown | `set_feed_retry(3, 10, 45000)`; then clear | "Attempt 3 of 10", "Next try in 45 s", tip "Try now"; then "Not connected" | Pass |
| UT-GUI-018.010.M04.T01 | MD-GUI-018.008.M04 | Positive | Open market counts to close | Wed 2026-10-21 13:46 ET | ("open", "Open", "closes in 2h 14m") | Pass |
| UT-GUI-018.010.M04.T02 | MD-GUI-018.008.M04 | Edge | Weekend and holiday skipped | Fri 2026-10-23 17:00; Wed 2026-11-25 20:30; Fri 2026-10-30 17:00 (DST ends) | "opens in 2d 16h"; "opens in 1d 13h"; "opens in 2d 17h" | Pass |
| UT-GUI-018.011.M04.T01 | MD-GUI-018.008.M04 | Positive | Mini shows plug with worst status | `set_mini(True)`, offline | rows hidden; plug shown; badge red; tooltip has 3 rows | Pass |

## FO-GUI-019 — Side Panels and Exit Drawer

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-019.001.M01.T01 | MD-GUI-019.001.M01 | Positive | Strip button toggles its panel | click Watchlist twice | `panel_toggled("watch", True)` then `False` | Pass |
| UT-GUI-019.001.M01.T02 | MD-GUI-019.001.M01 | Positive | Log badge counts warnings only while hidden | WARNING, INFO, ERROR; then open Log | badge 2; badge hidden after open | Pass |
| UT-GUI-019.003.M01.T01 | MD-GUI-019.001.M01 | Positive | Details shows the position | position NVDA 85 @ 138.20 | symbol, quantity, average, P&L shown | Pass |
| UT-GUI-019.003.M01.T02 | MD-GUI-019.001.M01 | Negative | Details with no selection | `show_position(None)` | empty hint; buttons disabled | Pass |
| UT-GUI-019.006.M02.T01 | MD-GUI-019.006.M02 | Positive | Market exit sends only after Review and Confirm | Market tab; Review; Confirm | `submitted("full_close", qty=85)` once, not on Review | Pass |
| UT-GUI-019.006.M02.T04 | MD-GUI-019.006.M02 | Negative | Double-click on Confirm sends once | Review; Confirm twice | one `submitted`; form disabled | Pass |
| UT-GUI-019.006.M02.T02 | MD-GUI-019.006.M02 | Positive | Stop tab returns the same params as the old dialog | price 132.5, trailing off | `submitted("set_stop_loss", {price 132.5, trailing False, ...})` | Pass |
| UT-GUI-019.006.M02.T03 | MD-GUI-019.006.M02 | Negative | Cancel and Back send nothing | Review then Back; Cancel | no `submitted` | Pass |
| UT-GUI-019.007.M02.T01 | MD-GUI-019.006.M02 | Positive | Square-off list shows all positions and confirms | 3 positions; Review; Confirm | 3 rows; `submitted("square_off_all")` | Pass |
| UT-GUI-019.002.M03.T01 | MD-GUI-019.002.M03 | Positive | Opening the right panel shrinks the sidebar and closing restores it | `_MiniState` panel open then closed | `want_mini` True then False | Pass |

## FO-GUI-020 — Charts Workspace

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-020.001.M01.T01 | MD-GUI-020.001.M01 | Positive | New Chart adds windows up to six | click New Chart until disabled | 6 windows; button disabled; count "6 of 6 charts" | Superseded |
| UT-GUI-020.001.M01.T02 | MD-GUI-020.001.M01 | Positive | Closing a window frees a slot | close one of six | 5 windows; button enabled | Superseded |
| UT-GUI-020.002.M01.T01 | MD-GUI-020.001.M01 | Positive | Tabs mode switches view mode | click Tabs, then Tile | tabbed view; then sub-window view | Superseded |
| UT-GUI-020.003.M01.T01 | MD-GUI-020.001.M01 | Positive | Same symbol focuses its window | open AAPL twice | one AAPL window, active | Superseded |
| UT-GUI-020.003.M01.T02 | MD-GUI-020.001.M01 | Edge | Seventh symbol loads into the active window | six open, open TSLA | still 6 windows; active shows TSLA | Superseded |
| UT-GUI-020.004.M01.T01 | MD-GUI-003.001.M01 | Negative | Quick Chart Viewer is gone | screener module | no `QuickChartWindow`; `chart_requested` signal exists | Pass |

## FO-GUI-021 — Settings Section List

| ID | Module | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-GUI-021.001.M01.T01 | MD-GUI-021.001.M01 | Positive | System tab is split into three sections | build `_SystemSections` | Connection, Scheduler, Telegram | Pass |
| UT-GUI-021.001.M01.T02 | MD-GUI-021.001.M01 | Positive | Section click shows one section | click Telegram | stack shows Telegram; Users unchecked; 6 sections, no Theme, Diagnostics or Database | Pass |
| UT-GUI-021.002.M01.T01 | MD-GUI-021.001.M01 | Positive | Risk save persists values | set 2.5 % and LMT, Save | `update_user` called with new risk config | Pass |
| UT-GUI-021.002.M01.T02 | MD-GUI-021.001.M01 | Negative | Risk save keeps other user fields | chat ID set, Save | chat ID and username unchanged | Pass |
| UT-GUI-021.003.M01.T01 | MD-GUI-021.001.M01 | Positive | System panel holds Theme, Updates, Diagnostics | build `_SystemSections` | theme, update and circuit breaker buttons inside `panel`; groups THEME, UPDATES, ORDERS | Pass |
| UT-GUI-021.003.M02.T01 | MD-GUI-019.001.M01 | Positive | Strip has a System button | click System | `panel_toggled("system", True)` | Pass |
| UT-GUI-021.004.M01.T01 | MD-GUI-021.001.M01 | Positive | Progress shows percent | progress MSFT 312 of 503 | "62%", "312 / 503 stocks", "Now: MSFT"; state downloading 62 | Superseded (UT-GUI-028.*) |
| UT-GUI-021.004.M01.T02 | MD-GUI-021.001.M01 | Positive | No failures ends Complete | finish, no failures | "Complete", "100%"; state complete | Superseded (UT-GUI-028.*) |
| UT-GUI-021.004.M01.T03 | MD-GUI-021.001.M01 | Negative | Failures end Partial | finish, 3 failed | "Partial", "500 / 503 stocks", "3 failed"; Failed group shown | Superseded (UT-GUI-028.*) |
| UT-GUI-021.004.M01.T04 | MD-GUI-021.001.M01 | Edge | Past failures mark partial | failed stocks on disk at start | state partial; Failed shown; Download hidden | Pass |
| UT-GUI-021.004.M02.T01 | MD-GUI-019.001.M01 | Positive | Data badge per state | downloading 62, complete, partial | "62"; check icon; "!" | Pass |
| UT-GUI-021.004.M02.T02 | MD-GUI-019.001.M01 | Negative | Idle hides the badge | complete then idle | badge hidden | Pass |

## FO-GUI-022 — Screener Result Views

| ID | Module | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-GUI-022.001.M01.T01 | MD-GUI-022.001.M01 | Positive | View switch saves and restores | default; click Cards; new switch on same settings | "list"; `view_changed("cards")`; new switch is "cards" | Pass |
| UT-GUI-022.001.M01.T02 | MD-GUI-022.001.M01 | Negative | Unknown saved view falls back | settings view "grid" | "list" | Pass |
| UT-GUI-022.002.M01.T01 | MD-GUI-022.001.M01 | Positive | List loads and shows first stock | 3 rows | 3 items; first selected; detail symbol, tier, "$222.00", "3.3 R", reasoning | Pass |
| UT-GUI-022.002.M01.T02 | MD-GUI-022.001.M01 | Positive | Selection updates detail and chart | select row 2 | detail shows JCI; fake chart `show_symbol("JCI", "1d")`; chart built once | Pass |
| UT-GUI-022.002.M01.T03 | MD-GUI-022.001.M01 | Negative | Missing plan shows dashes | row without plan | Entry, Stop, Target, R:R tiles "—" | Pass |
| UT-GUI-022.002.M01.T04 | MD-GUI-022.001.M01 | Positive | Detail buttons emit symbol | click Open chart, Watchlist | `chart_requested("NVDA")`, `watchlist_requested("NVDA")` | Pass |
| UT-GUI-022.002.M01.T05 | MD-GUI-022.001.M01 | Edge | Theme change keeps selection, no chart reload | select JCI; restyle | JCI still selected and shown; no new `show_symbol` call | Pass |
| UT-GUI-022.003.M01.T01 | MD-GUI-022.001.M01 | Positive | One card per stock with actions | 3 rows; click card 2 Chart | 3 cards; "#1", "NVDA", "Strong"; `chart_requested("JCI")` | Pass |
| UT-GUI-022.003.M01.T02 | MD-GUI-022.001.M01 | Edge | Empty rows clear cards | load 3 then [] | 0 cards | Pass |
| UT-GUI-022.004.M01.T01 | MD-GUI-022.001.M01 | Positive | Rows built from result meta | details bool + float, `ai_plan`, scores 0.85 / 0.55 / 0.2 | pass/fail/value checks; plan read; tiers Strong / Watch / Weak; ranked by score | Pass |
| UT-GUI-022.005.M01.T01 | MD-GUI-022.001.M01 | Positive | R:R and sort | plans valid, short-shaped, missing; sort rr, rules | 3.3; None; None; None last; most rules first | Pass |
| UT-GUI-022.006.M01.T01 | MD-GUI-022.001.M01 | Positive | CSV rows carry the plan | 2 rows, one without plan | header has Entry, Stop, Target, R:R; values and "" | Pass |
| UT-GUI-022.007.M01.T01 | MD-GUI-022.001.M01 | Positive | Preset filter by search text | 3 presets; "MOM"; "" | Momentum only; all 3 | Pass |
| UT-GUI-022.007.M01.T02 | MD-GUI-022.001.M01 | Positive | Last-run line | today, earlier date, none | "Today 13:18 · 5 matches"; "Oct 21 · 8 matches"; "Not run yet" | Pass |
| UT-GUI-022.008.M01.T01 | MD-GUI-022.001.M01 | Positive | Header run line and date text | 5 matches AI-ranked at 13:18 UTC; 1 match no time; "2026-10-22"; "bad" | full line; "1 match · ranked by score"; "Oct 22, 2026"; "bad" | Pass |
| UT-GUI-022.009.M01.T01 | MD-GUI-022.001.M01 | Positive | Stepper arrows and menu move between runs | 3 dates; click older; pick menu item 3 | Latest shown then hidden; `index_changed` 1 then 2; arrows enabled per end | Pass |
| UT-GUI-022.009.M01.T02 | MD-GUI-022.001.M01 | Negative | No saved runs disables the stepper | [] | "—"; arrows and date disabled; no Latest tag | Pass |
| UT-GUI-022.010.M01.T01 | MD-GUI-022.001.M01 | Positive | Pill shows steps and cost | 2 turns with tokens; 1 turn without | "AI transcript · 2 steps · $0.04"; "AI transcript · 1 step" | Pass |
| UT-GUI-022.010.M01.T02 | MD-GUI-022.001.M01 | Positive | Drawer opens and Esc closes it | host 1000 px; open; Esc | open, visible, 460 px wide; closed once | Pass |
| UT-GUI-022.011.M01.T01 | MD-GUI-022.001.M01 | Positive | Company name, rules count, risk / reward | names for NVDA; select row without plan | company in meta; "RULES · 1 OF 3"; "$10.00" / "$33.00" lines; bar hidden and no-plan text | Pass |
## FO-GUI-023 — Card Layout

| ID | Module | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-GUI-023.001.M01.T01 | MD-GUI-023.001.M01 | Positive | Card holds the child inside its padding | QLabel | name `shell_card`; child at index 0; margins ≥ 2 | Pass |
| UT-GUI-023.001.M01.T02 | MD-GUI-023.001.M01 | Positive | Gutter marks the widget | QWidget | same widget returned; name `shell_gutter`; GAP 4 | Pass |

## FO-GUI-024 — Execution Workspace

| ID | Module | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-GUI-024.001.M01.T01 | MD-GUI-024.001.M01 | Positive | Chips show running count and unrealised P&L | 3 strategies, 1 RUNNING + 1 with open cycle; open cycles P&L +10 and −4 | "2 of 3"; "+$6.00" | Pass |
| UT-GUI-024.001.M01.T02 | MD-GUI-024.001.M01 | Positive | Broker chip follows user mode | active user paper / live | "Paper broker" / "IBKR live" | Pass |
| UT-GUI-024.002.M02.T01 | MD-GUI-024.002.M02 | Positive | Groups: Manual first, screeners A→Z, score order, counts | 1 pick, 2 "Price Action", 2 "Momentum" | groups Manual, Momentum, Price Action; counts 1, 2, 2; higher score first | Pass |
| UT-GUI-024.002.M02.T02 | MD-GUI-024.002.M02 | Positive | ✕ on a pick removes it | click Score cell of pick row | `remove_manual_pick("DELL")` called once | Pass |
| UT-GUI-024.002.M02.T03 | MD-GUI-024.002.M02 | Negative | Not-ready symbol is tinted | readiness {"NVDA": False} | NVDA row has a background brush; others none | Pass |
| UT-GUI-024.002.M02.T04 | MD-GUI-024.002.M02 | Edge | No entries shows the empty text | [] | tree hidden; empty label shown; `get_top_symbol()` None | Pass |
| UT-GUI-024.003.M03.T01 | MD-GUI-024.003.M03 | Positive | Active filter hides closed rows | 2 open + 1 closed rows; filter "active" | 1 hidden row; counts (2, 1) | Pass |
| UT-GUI-024.003.M03.T02 | MD-GUI-024.003.M03 | Positive | Closed filter shows only closed rows | same rows; filter "closed" | 2 hidden rows | Pass |
| UT-GUI-024.004.M04.T01 | MD-GUI-024.004.M04 | Positive | List rows and selection fill the detail | 2 configs | 2 items; first selected; detail title = first name | Pass |
| UT-GUI-024.005.M04.T02 | MD-GUI-024.004.M04 | Positive | Duplicate makes a stopped copy with a unique name | "ST" and "ST copy" exist; duplicate "ST" | new "ST copy 2", run_state STOPPED, saved, selected | Pass |
| UT-GUI-024.006.M05.T01 | MD-GUI-024.006.M05 | Edge | Empty summary shows the empty text | `StrategyPnlSummary()` | chart reports empty; stats "—" | Pass |
| UT-GUI-024.006.M05.T02 | MD-GUI-024.006.M05 | Positive | Card shows total and stats | summary total 412.6, 38 trades, win rate 0.55 | "+$412.60"; "38 trades"; "55%" | Pass |
| UT-GUI-024.006.M05.T03 | MD-GUI-024.006.M05 | Positive | Range button asks for a start time | click 1W | provider called with since ≈ now − 7 days | Pass |
| UT-GUI-024.006.M05.T04 | MD-GUI-024.006.M05 | Positive | Nice y ticks | min 0, max 412.6 | ticks 0, 150, 300, 450 | Pass |
| UT-GUI-024.008.M06.T01 | MD-GUI-024.008.M06 | Positive | Hide charts is remembered | `set_charts_hidden(True)`; new pane | `charts_toggled(True)`; setting true; new pane starts hidden | Pass |
| UT-GUI-024.008.M01.T03 | MD-GUI-024.001.M01 | Positive | Header charts button names the next action | default; `show_charts_state(True)` | "Hide charts"; "Show charts" | Pass |

## FO-GUI-025 — Dashboard Tiled Workspace

| ID | Module | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-GUI-025.004.M01.T01 | MD-GUI-025.003.M01 | Positive | Maximise shows only that tile | click History maximise | only History shown; button tip "Restore" | Pass |
| UT-GUI-025.004.M01.T02 | MD-GUI-025.003.M01 | Positive | Second click restores the grid | click Watch maximise twice | all four shown; `changed` "watch", "" | Pass |
| UT-GUI-025.004.M01.T03 | MD-GUI-025.003.M01 | Negative | Unknown tile name restores | `set_maximised("no-such-tile")` | maximised ""; all shown | Pass |
| UT-GUI-025.001.M01.T01 | MD-GUI-025.003.M01 | Positive | Strip value and note | cap "45.8%" note "of 95%"; pos "5" | cap note shown; pos note hidden | Pass |
| UT-GUI-025.005.M01.T01 | MD-GUI-025.003.M01 | Positive | Bars scale to the largest P&L | +49.5, −16.3 | fractions 1.0, −0.33; total "+$33.20" | Pass |
| UT-GUI-025.005.M01.T02 | MD-GUI-025.003.M01 | Edge | No strategies | [] | "No strategies" shown; total "$0.00" | Pass |
| UT-GUI-025.001.M02.T01 | MD-GUI-025.001.M02 | Positive | Strip filled from positions and account | NDAQ long +8.55, MSFT short +16.50; daily P&L 41.75 | pos "2"; unrealised "+$25.05"; P&L "+$41.75"; strategy total "+$8.55" | Pass |
| UT-GUI-025.002.M02.T01 | MD-GUI-025.001.M02 | Positive | View switch scopes the dashboard | click "trader" | `set_viewing_uid(1)`; setting "1" | Pass |
| UT-GUI-025.006.M02.T01 | MD-GUI-025.001.M02 | Positive | Density and maximised tile remembered | Comfort + maximise Strategy; new panel | "comfort"; row height 32; maximised "strategy" | Pass |
| UT-GUI-025.006.M02.T02 | MD-GUI-025.001.M02 | Edge | First start defaults | empty settings | "compact"; full grid; scope not changed | Pass |
| UT-GUI-025.008.M02.T01 | MD-GUI-025.001.M02 | Positive | Filter hides other symbols | NDAQ, MSFT; filter "nd" | MSFT row hidden; count "1 of 2" | Pass |
| UT-GUI-025.008.M02.T02 | MD-GUI-025.001.M02 | Negative | Closing the filter shows all | filter "zzz", close | text cleared; both rows shown | Pass |
| UT-GUI-025.008.M02.T03 | MD-GUI-025.001.M02 | Edge | Filter and hidden columns survive reloads | filter "ms", Stop hidden; refresh + scope to one user | MSFT only; Stop still hidden | Pass |
| UT-GUI-025.009.M02.T01 | MD-GUI-025.001.M02 | Positive | Hidden column remembered | untick Stop; new panel | Stop hidden in both | Pass |
| UT-GUI-025.009.M02.T02 | MD-GUI-025.001.M02 | Negative | Symbol and User cannot be hidden | untick Symbol, User | action disabled; columns shown | Pass |
| UT-GUI-025.010.M02.T01 | MD-GUI-025.001.M02 | Positive | Range and state filter orders | 2 today (filled, cancelled), 3 days, 40 days | Today 2; Filled 1; 7 days 2; All/All 4 | Pass |
| UT-GUI-025.010.M02.T02 | MD-GUI-025.001.M02 | Edge | Choices remembered; bad value falls back | 30 days + Cancelled; then "bogus" | texts restored, 1 row; then "Today" | Pass |
| UT-GUI-025.011.M02.T01 | MD-GUI-025.001.M02 | Positive | Export writes shown rows | Today view | header User, Date & Time, Symbol; rows A, B | Pass |
| UT-GUI-025.011.M02.T02 | MD-GUI-025.001.M02 | Negative | Unwritable path | folder path | error logged with reason; warning box shown | Pass |
| UT-GUI-025.012.M01.T01 | MD-GUI-002.001.M01 | Positive | ✕ removes that symbol | click ✕ on MSFT row | `remove_from_watchlist("MSFT")` | Pass |
| UT-GUI-025.012.M01.T02 | MD-GUI-002.001.M01 | Negative | Other cell removes nothing | click Symbol cell | not called; right-panel model has no ✕ | Pass |
| UT-GUI-025.012.M01.T03 | MD-GUI-002.001.M01 | Edge | Tile watchlist keeps hidden columns after new quotes | reload | Open column hidden; ✕ shown | Pass |
| UT-GUI-025.013.M03.T01 | MD-GUI-025.013.M03 | Positive | Change text for the range | 25,000 → 25,041.75, 1D; reversed, 1W | "+$41.75 (+0.17%) today"; "−$41.75 (−0.17%) this week" | Pass |
| UT-GUI-025.013.M03.T02 | MD-GUI-025.013.M03 | Edge | One point gives no change | one point | "", 0 | Pass |
| UT-GUI-025.013.M03.T03 | MD-GUI-025.013.M03 | Positive | Band shows value, change and chart | 3M, two points | "$25,041.75"; text ends "in 3 months"; chart has 2 points | Pass |
| UT-GUI-025.013.M03.T04 | MD-GUI-025.013.M03 | Negative | Unknown range and empty curve | "5Y"; no points | range 1D; no change text; value "—" | Pass |
| UT-GUI-025.015.M03.T01 | MD-GUI-025.013.M03 | Positive | Bars per symbol and side, largest first | NDAQ twice, MSFT short, AMD with no quote | AMD, MSFT Short, NDAQ; AMD at entry price | Pass |
| UT-GUI-025.015.M03.T02 | MD-GUI-025.013.M03 | Positive | Totals and percent labels | long 2,000, short 2,000, equity 10,000; then equity 0 | Net $0, Gross 40.0%, labels 20.0%; then "—" and $ labels | Pass |
| UT-GUI-025.015.M03.T03 | MD-GUI-025.013.M03 | Edge | Many symbols grouped | 12 symbols | 8 bars, last "5 others"; Long total over all 12 | Pass |
| UT-GUI-025.014.M02.T01 | MD-GUI-025.001.M02 | Positive | Band open by default; hiding remembered | first start; click Performance; new panel | shown; hidden; still hidden | Pass |
| UT-GUI-025.013.M02.T01 | MD-GUI-025.001.M02 | Positive | Range asks the service and is remembered | click 1W | `get_equity_curve("1W")`; chart points set; new panel on 1W | Pass |
| UT-GUI-025.015.M02.T01 | MD-GUI-025.001.M02 | Positive | Exposure tab swaps view and tools | click Exposure, % Equity, back | bars "$1,919" then "7.7%"; filter tools hidden then shown | Pass |
| UT-GUI-025.016.M04.T01 | MD-GUI-025.016.M04 | Positive | Side and unset stop/target text | LONG and SHORT rows; stop 0, target 0 | "LONG" / "SHORT"; "No stop"; "—" | Pass |
| UT-GUI-025.016.M04.T02 | MD-GUI-025.016.M04 | Edge | Side follows Symbol with User column | User column shown | Side right after Symbol | Pass |
| UT-GUI-025.018.M02.T01 | MD-GUI-025.001.M02 | Positive | P&L Today from equity change | equity above start-of-day; different daily_pnl | KPI shows equity − start | Pass |

## FO-GUI-026 — Charts Workspace (Focus + Inspector)

| ID | Module | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-GUI-026.001.M01.T01 | MD-GUI-026.001.M01 | Positive | Three cards, no MDI | build workspace | source list, chart and Inspector cards; no `QMdiArea` | Pass |
| UT-GUI-026.001.M01.T02 | MD-GUI-026.001.M01 | Positive | open_symbol loads chart and selects row | Watchlist has NVDA; `open_symbol("NVDA", "1w")` | fake chart `show_symbol("NVDA", "1w")`; NVDA row selected; Inspector updated | Pass |
| UT-GUI-026.001.M01.T03 | MD-GUI-026.001.M01 | Negative | Symbol not in list still loads | `open_symbol("AAPL")`; then ZZZ with no bars | AAPL loads, no row selected; ZZZ header "No data" | Pass |
| UT-GUI-026.001.M01.T04 | MD-GUI-026.001.M01 | Positive | Theme change keeps symbol and recolours the change | NVDA loaded; `refresh_theme` | symbol kept; change label coloured | Pass |
| UT-GUI-026.002.M02.T01 | MD-GUI-026.002.M02 | Positive | Rows per tab | 2 watchlist items, 3 screener entries, 1 short position | 2 rows; 3 rows by score with preset sub; "Short 20 sh" | Pass |
| UT-GUI-026.002.M02.T02 | MD-GUI-026.002.M02 | Positive | Filter and tab remembered | filter "nv"; pick Trades; new list on same settings | NVDA only; new list opens on Trades | Pass |
| UT-GUI-026.002.M02.T03 | MD-GUI-026.002.M02 | Negative | Empty tab shows empty text | no positions, Trades tab | list hidden; "No open trades" shown | Pass |
| UT-GUI-026.002.M02.T04 | MD-GUI-026.002.M02 | Positive | Row click emits; watchlist signal reloads | click NVDA; add AMD, emit `watchlist_updated` | `symbol_selected("NVDA")`; rows NVDA, AMD | Pass |
| UT-GUI-026.003.M01.T01 | MD-GUI-026.001.M01 | Positive | Overlay add, remove and remember | first start; add EMA 9; ✕ on SMA 50; new workspace | defaults SMA 20, SMA 50; `set_overlays` [sma 20, ema 9]; restored | Pass |
| UT-GUI-026.003.M01.T02 | MD-GUI-026.001.M01 | Negative | Bad saved overlay is dropped | setting "sma:x,foo:5,sma:20" | overlays [sma 20] | Pass |
| UT-GUI-026.004.M01.T01 | MD-GUI-026.001.M01 | Positive | Plan sent to the chart | screener plan 129.8 / 124.5 / 141 | `set_plan((129.8, 124.5, 141.0))` | Pass |
| UT-GUI-026.004.M01.T02 | MD-GUI-026.001.M01 | Negative | No plan clears lines | symbol without plan or position | `set_plan(None)` | Pass |
| UT-GUI-026.005.M03.T01 | MD-GUI-026.005.M03 | Positive | One header per registry entry; open state remembered | `SECTIONS`; collapse Indicators; new Inspector | header per entry in order; Indicators closed | Pass |
| UT-GUI-026.005.M03.T02 | MD-GUI-026.005.M03 | Edge | Extra section plugs in | registry plus a fake section | fake section shown and its `update` called on load | Pass |
| UT-GUI-026.005.M01.T04 | MD-GUI-026.001.M01 | Negative | Hidden Inspector stays hidden | hide; new workspace | Inspector card hidden | Pass |
| UT-GUI-026.006.M03.T01 | MD-GUI-026.005.M03 | Positive | R:R and size | entry 129.8, stop 124.5, target 141; equity 40,000, risk 1 % | R:R 2.1; size 75 | Pass |
| UT-GUI-026.006.M03.T02 | MD-GUI-026.005.M03 | Negative | Invalid plan shows dashes | stop 131 ≥ entry 129.8 | R:R None; size 0; cells "—" | Pass |
| UT-GUI-026.006.M03.T03 | MD-GUI-026.005.M03 | Positive | Plan values shown | plan 129.8 / 124.5 / 141; equity 40,000, risk 1 % | "129.80", "124.50", "141.00", "2.1", "75 sh"; "Size (1% risk)" | Pass |
| UT-GUI-026.006.M01.T05 | MD-GUI-026.001.M01 | Positive | Plan source order | screener plan and position; position only; stop 0 | screener values; position avg, stop, target; None | Pass |
| UT-GUI-026.006.M01.T06 | MD-GUI-026.001.M01 | Negative | Edited plan kept; invalid plan clears lines | edit NVDA; reload; edit stop above entry | same lines after reload; `set_plan(None)` | Pass |
| UT-GUI-026.006.M03.T04 | MD-GUI-026.005.M03 | Positive | Edit updates values and lines | Edit; stop 125; Save | stop "125.00"; `plan_changed` with new stop | Pass |
| UT-GUI-026.007.M03.T01 | MD-GUI-026.005.M03 | Positive | Indicator values | 60 known bars | RSI, ATR, ADX match reference values; rel. volume 2.0× | Pass |
| UT-GUI-026.007.M03.T02 | MD-GUI-026.005.M03 | Edge | Too few bars | 5 bars | all "—" | Pass |
| UT-GUI-026.007.M01.T03 | MD-GUI-026.001.M01 | Positive | Indicators get the loaded bars | open NVDA | RSI value shown | Pass |
| UT-GUI-026.008.M03.T01 | MD-GUI-026.005.M03 | Positive | Pattern hits on recent bars | bars ending in a bullish engulfing 2 bars ago | hit "Bullish engulfing", 2 bars ago, bullish | Pass |
| UT-GUI-026.008.M03.T02 | MD-GUI-026.005.M03 | Negative | Old pattern not listed | engulfing 10 bars ago only | no Bullish Engulfing hit | Pass |
| UT-GUI-026.008.M01.T03 | MD-GUI-026.001.M01 | Positive | Inspector markers and levels reach the chart | emit markers and levels | chart studies hold both | Pass |
| UT-GUI-026.008.M03.T04 | MD-GUI-026.005.M03 | Positive | Pattern eye shows and hides its marker | click a pattern's eye twice | no markers, then that one marker, then none | Pass |
| UT-GUI-026.009.M03.T01 | MD-GUI-026.005.M03 | Positive | Nearest swing levels | bars with pivots 110, 120, 135 and close 125; tick Show on chart | above [135]; below [120, 110]; `levels_changed` [] then all three | Pass |
| UT-GUI-026.009.M03.T02 | MD-GUI-026.005.M03 | Edge | Too few bars give no levels | 5 bars | ([], []) | Pass |
| UT-GUI-026.010.M01.T01 | MD-GUI-026.001.M01 | Positive | Send to Execution adds pick | click Send to Execution; `add_manual_pick` returns None | called with "NVDA"; `execution_requested("NVDA")`; no message | Pass |
| UT-GUI-026.010.M01.T02 | MD-GUI-026.001.M01 | Negative | Existing pick shows message | `add_manual_pick` returns "NVDA is already in your picks" | message shown; no `execution_requested` | Pass |
| UT-GUI-026.012.M04.T01 | MD-GUI-026.012.M04 | Positive | Save and load drawings | in-memory SQLite; save trend + hline for NVDA 1d | load NVDA 1d returns both with same points | Pass |
| UT-GUI-026.012.M04.T02 | MD-GUI-026.012.M04 | Negative | Other symbol or timeframe sees none | load NVDA 1w; load AMD 1d | [] and [] | Pass |
| UT-GUI-026.012.M04.T03 | MD-GUI-026.012.M04 | Positive | Delete all clears one chart only | delete_all NVDA 1d | NVDA 1d []; NVDA 1w kept | Pass |
| UT-GUI-026.012.M04.T04 | MD-GUI-026.012.M04 | Negative | Bridge ignores bad JSON | `add_drawing("not json")`; one-point trend; unknown kind | no `drawing_added`; three warnings logged | Pass |
| UT-GUI-026.011.M04.T05 | MD-GUI-026.012.M04 | Positive | Bridge turns page JSON into a drawing | rect JSON; hline with NaN price | `Drawing("rect", …)` emitted; NaN → None | Pass |
| UT-GUI-026.011.M01.T01 | MD-GUI-026.001.M01 | Positive | Finished drawing is saved, tool resets, drawing comes back | Trend tool; drawing added; open AAPL then NVDA | saved with colour; pointer checked; AAPL none; NVDA drawing back | Pass |
| UT-GUI-026.011.M01.T02 | MD-GUI-026.001.M01 | Positive | Delete all clears the chart and the database | one hline; `clear_drawings()` | chart and store empty | Pass |
| UT-GUI-026.011.M01.T03 | MD-GUI-026.001.M01 | Positive | Eraser deletes only the clicked drawing | hline + trend; Eraser; page deletes the hline | trend kept on chart and in store; Eraser stays on | Pass |
| UT-GUI-026.012.M01.T05 | MD-GUI-026.001.M01 | Negative | Save failure keeps the drawing on screen | table dropped; drawing added | drawing shown; "[Charts] Could not save drawing" logged | Pass |

## FO-GUI-027 — Settings Dialog

| UT ID | MD | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-GUI-027.001.M01.T01 | MD-GUI-027.001.M01 | Positive | Dialog is frameless and modal | build dialog | frameless flag; application modal; title bar text "Settings" | Pass |
| UT-GUI-027.001.M01.T02 | MD-GUI-027.001.M01 | Positive | Open at a section | `open_at("Telegram")` | dialog visible; Telegram section shown | Pass |
| UT-GUI-027.003.M01.T01 | MD-GUI-027.001.M01 | Positive | Footer buttons | open; click Cancel; open; click OK | Apply disabled at start; rejected; accepted | Pass |
| UT-GUI-027.003.M01.T02 | MD-GUI-027.001.M01 | Positive | Footer follows the panel | panel dirty; Risk section shown; click Restore defaults | Apply and Restore defaults enabled; panel asked to restore | Pass |
| UT-GUI-027.004.M02.T01 | MD-GUI-027.004.M02 | Positive | Settings item opens, screen stays | click Settings with Execution checked | `settings_requested` once; Execution still checked | Pass |
| UT-GUI-027.004.M03.T01 | MD-GUI-027.004.M03 | Positive | Four screens | `_NAV_ITEMS` | Dashboard, Screener, Execution, Charts | Pass |
| UT-GUI-027.002.M04.T01 | MD-GUI-027.005.M04 | Positive | Eight sections in order | build panel | Users … Appearance, eight stack pages; no Updates | Pass |
| UT-GUI-027.005.M04.T01 | MD-GUI-027.005.M04 | Positive | Appearance page only | build `_SystemSections` | `app_pages` is Appearance alone; theme buttons on it | Pass |
| UT-GUI-027.005.M07.T01 | MD-GUI-027.005.M07 | Positive | Version and last check text | stamp 2026-10-25 09:14; show popup | "Installed v<version> · last checked 25 Oct 09:14" | Pass |
| UT-GUI-027.005.M07.T02 | MD-GUI-027.005.M07 | Edge | Never checked | no stamp | "not checked yet" | Pass |
| UT-GUI-027.005.M07.T03 | MD-GUI-027.005.M07 | Positive | Update found | worker emits found | `update_found` once; update dialog opened; button enabled | Pass |
| UT-GUI-027.005.M07.T04 | MD-GUI-027.005.M07 | Negative | Check fails | worker emits failed "timeout" | note "Could not check for updates — timeout"; no `update_found` | Pass |
| UT-GUI-027.005.M02.T01 | MD-GUI-027.004.M02 | Positive | Sidebar Updates item | click item; popup emits `update_found`; mini mode | popup shown; dot visible; label hidden in mini | Pass |
| UT-GUI-027.007.M06.T01 | MD-GUI-019.001.M01 | Positive | Strip keeps three buttons | build `IconStrip` | details, watch, log only | Pass |
| UT-GUI-027.008.M02.T01 | MD-GUI-027.004.M02 | Positive | Settings badge per state | downloading 62, complete, partial | "62"; check icon; "!" | Pass |
| UT-GUI-027.008.M02.T02 | MD-GUI-027.004.M02 | Negative | Idle hides the badge | complete then idle | badge hidden | Pass |
| UT-GUI-027.009.M05.T01 | MD-GUI-027.009.M05 | Positive | Header breaker trips and resets | click; breaker active; click | `set_circuit_breaker(True)`; label "Reset breaker"; `set_circuit_breaker(False)` | Pass |
| UT-GUI-027.010.M04.T01 | MD-GUI-027.005.M04 | Positive | Edit then Apply saves once | change risk to 2.5; Apply | Apply enabled after edit; `update_user` once; Apply disabled | Pass |
| UT-GUI-027.010.M04.T02 | MD-GUI-027.005.M04 | Negative | Cancel drops edits | change risk to 2.5; Cancel | no save; field back to saved value | Pass |
| UT-GUI-027.011.M04.T01 | MD-GUI-027.005.M04 | Positive | Restore defaults after yes | Risk shown, risk 2.5, confirm yes | default risk value; section dirty | Pass |
| UT-GUI-027.011.M04.T02 | MD-GUI-027.005.M04 | Negative | No keeps values | confirm no | risk still 2.5; nothing dirty | Pass |
| UT-GUI-027.012.M04.T01 | MD-GUI-027.005.M04 | Positive | Dot states | `set_section_state` ok, warn, off, none | green, amber, grey; hidden | Pass |
| UT-GUI-027.012.M04.T02 | MD-GUI-027.005.M04 | Edge | Telegram dot rule | enabled + token + chat; enabled, no chat; disabled | ok; warn; off | Pass |
| UT-GUI-027.013.M04.T01 | MD-GUI-027.005.M04 | Positive | Theme waits for Apply | click Mocha; then Apply | not applied after click; applied once and saved after Apply | Pass |

> UT-GUI-021.003.M01.T01, UT-GUI-021.003.M02.T01 and UT-GUI-021.004.M02.T01–T02 are replaced by UT-GUI-027.005.M04.T01, .007.M06.T01 and .008.M02.T01–T02: the System and Data side panels are gone.

## FO-GUI-028 — Candle Data Panel Redesign

| UT ID | MD | Type | Description | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-GUI-028.002.M01.T01 | MD-GUI-028.001.M01 | Positive | Progress line | start; MSFT 312 / 503 | "Updating 312 of 503 stocks"; detail starts "62% · MSFT"; state downloading 62 | Not Run |
| UT-GUI-028.002.M01.T02 | MD-GUI-028.001.M01 | Positive | ETA from the third stock | 10 of 100 after 20 s | detail ends "~3 min left" | Not Run |
| UT-GUI-028.001.M01.T01 | MD-GUI-028.001.M01 | Positive | Finish without failures | 502 / 503 then finished, no failures | pill "COMPLETE"; state complete 100 | Not Run |
| UT-GUI-028.001.M01.T02 | MD-GUI-028.001.M01 | Negative | Finish with failures | 3 failed | pill "PARTIAL"; "3 failed"; failed group shown; state partial | Not Run |
| UT-GUI-028.001.M01.T03 | MD-GUI-028.001.M01 | Positive | Status pill and summary | CURRENT; PARTIAL 1 day behind; EMPTY | "UP TO DATE"; "1 DAY BEHIND"; "EMPTY" with matching summary | Not Run |
| UT-GUI-028.003.M01.T01 | MD-GUI-028.001.M01 | Edge | Extra stored stocks | 518 stored, universe 503 | "503 / 503", note "+15 left the index" | Not Run |
| UT-GUI-028.004.M01.T01 | MD-GUI-028.001.M01 | Positive | Footer swaps while downloading | start download | Cancel shown, Update hidden, Reset disabled | Not Run |
| UT-GUI-028.005.M01.T01 | MD-GUI-028.001.M01 | Negative | Reset cancelled keeps data | confirm returns Cancel | `reset_candle_db` not called | Not Run |
