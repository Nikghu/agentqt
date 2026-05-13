# Unit Test Case Document — GUI Module (GUI)

**Document ID:** UTCD-GUI
**Version:** 1.2.0
**Traces To:** MD-GUI v1.2.0
**Status:** Draft
**Last Updated:** 2026-05-13
**Project:** US Swing Trading System

> Tests written BEFORE implementation per process.md §7.
> GUI tests use `pytest-qt` (`qtbot` fixture) for widget testing.

---

## Module: `gui/main_window.py` — MainWindow

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-001.001.M01.T01 | MD-GUI-001.001.M01 | Unit | MainWindow creates exactly 4 nav tab buttons in `_TitleBar` | Construct `MainWindow(svc)` | `len(window._title_bar._tabs) == 4`; labels: Dashboard, Screener, Execution, Settings | Implemented |
| UT-GUI-001.001.M01.T02 | MD-GUI-001.001.M01 | Unit | Status bar has Internet pill, P&L, Positions (left) and NYSE, NASDAQ pills (right) | Construct `MainWindow(svc)` | `_sb_conn`, `_sb_pnl`, `_sb_pos`, `_sb_nyse`, `_sb_nasdaq` exist and are visible | Implemented |
| UT-GUI-001.001.M01.T03 | MD-GUI-001.001.M01 | Unit | Scope combo change updates `_AdminContextBar` scope icon | `svc.set_viewing_uid(user_id)` emits `viewing_changed` | `_admin_ctx_bar._scope_icon.text() == "👤"` for single-user; `"🌐"` for all-users | Implemented |
| UT-GUI-001.001.M01.T04 | MD-GUI-001.001.M01 | Unit | `feed_status_changed("connected")` updates feed button text | Emit `svc.feed_status_changed("connected")` | `_title_bar._feed_btn.text() == "🟢  Connected"` | Implemented |
| UT-GUI-001.001.M01.T05 | MD-GUI-001.001.M01 | Unit | Window geometry saved on close | Close window | `QSettings("USSwing", "MainWindow")` contains `"geometry"` key | Implemented |
| UT-GUI-001.001.M01.T06 | MD-GUI-001.001.M01 | Unit | Window geometry restored on launch | Pre-set `QSettings` geometry | Window position matches saved values | Implemented |

---

## Module: `gui/position_table_model.py` — PositionTableModel

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-002.001.M02.T01 | MD-GUI-002.001.M02 | Unit | Empty model has 0 rows, 9 columns (base, no User col) | `PositionTableModel()` with no positions | `rowCount() == 0`; `columnCount() == 9` | Implemented |
| UT-GUI-002.001.M02.T02 | MD-GUI-002.001.M02 | Unit | User column prepended when `set_show_user(True)` | `set_show_user(True, {1: "alice"})` | `columnCount() == 10`; `headerData(0) == "User"` | Implemented |
| UT-GUI-002.001.M02.T03 | MD-GUI-002.001.M02 | Unit | Positive P&L cell has green-tinted background and green foreground | Position with `unrealised_pnl=500` | `BackgroundRole == QColor(C.PNL_POS_BG)`; `ForegroundRole == QColor(C.GREEN)` | Implemented |
| UT-GUI-002.001.M02.T04 | MD-GUI-002.001.M02 | Unit | Negative P&L cell has red-tinted background and red foreground | Position with `unrealised_pnl=-200` | `BackgroundRole == QColor(C.PNL_NEG_BG)`; `ForegroundRole == QColor(C.RED)` | Implemented |
| UT-GUI-002.001.M02.T05 | MD-GUI-002.001.M02 | Unit | `refresh()` resets model and reflects new positions | `refresh([pos1, pos2])` | `rowCount() == 2`; `modelReset` signal emitted via `beginResetModel/endResetModel` | Implemented |

---

## Module: `gui/screener_panel.py` — ScreenerPanel

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-003.001.M01.T01 | MD-GUI-003.001.M01 | Unit | Filter chips reflect enabled state from `AppService.get_screener_filters()` | Service returns 2 of 5 filters enabled | 2 `_FilterChip` checkboxes checked, 3 unchecked | Approved |
| UT-GUI-003.001.M01.T02 | MD-GUI-003.001.M01 | Unit | "Run Screener" button disabled during execution | Click run; check button state immediately | `_run_btn.isEnabled() == False`; re-enabled on `_ScreenerWorker.finished` | Approved |
| UT-GUI-003.001.M01.T03 | MD-GUI-003.001.M01 | Unit | Results table populated after screener run | Worker emits `finished` with 10 results | `_results_model.rowCount() == 10` | Approved |
| UT-GUI-003.001.M01.T04 | MD-GUI-003.001.M01 | Unit | Filter chip spinboxes disabled when chip unchecked | Uncheck a `_FilterChip` | All `_spins` in that chip have `isEnabled() == False` | Approved |

---

## Module: `gui/execution_panel.py` — ExecutionPanel

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-004.001.M01.T01 | MD-GUI-004.001.M01 | Unit | Signal rows created from `AppService.get_pending_signals()` at init | Service returns 2 signals | `len(panel._signal_rows) == 2`; each row has symbol label and Execute button | Implemented |
| UT-GUI-004.001.M01.T02 | MD-GUI-004.001.M01 | Unit | Override qty shows "(overridden)" when value differs from recommended | Set `_spin.value` != `signal.recommended_qty` | `_override_lbl.text() == "(overridden)"` | Implemented |
| UT-GUI-004.001.M01.T03 | MD-GUI-004.001.M01 | Unit | Override qty spinbox minimum is 1 | Attempt to set value to 0 | `_spin.value() == 1` (clamped by `setRange(1, 10_000)`) | Implemented |
| UT-GUI-004.001.M01.T04 | MD-GUI-004.001.M01 | Unit | Circuit breaker disables all execute buttons and shows banner | `panel.on_circuit_breaker(True)` | All `_SignalRow._exec_btn.isEnabled() == False`; `_cb_banner.isVisible() == True` | Implemented |
| UT-GUI-004.001.M01.T05 | MD-GUI-004.001.M01 | Unit | `viewing_changed` syncs Execute-for combo to current scope | `svc.set_viewing_uid(user_id)` | `_exec_user_combo` index matches `user_id` entry | Implemented |

---

## Module: `gui/position_monitor_panel.py` — PositionMonitorPanel

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-005.001.M01.T01 | MD-GUI-005.001.M01 | Unit | Positions from `AppService.get_positions()` shown on init | Service returns 2 OPEN positions | `_pos_model.rowCount() == 2` | Implemented |
| UT-GUI-005.001.M01.T02 | MD-GUI-005.001.M01 | Unit | Capital indicator shows correct available amount | `equity=100_000`, `open_position_value=30_000` | `_remaining_lbl.text() == "$70,000  of  $100,000"` | Implemented |
| UT-GUI-005.001.M01.T03 | MD-GUI-005.001.M01 | Unit | "CAN ENTER" badge when capital available | `available > 0` and `util_pct < max_allocation_pct` | `_can_enter.text() == "CAN ENTER"` | Implemented |
| UT-GUI-005.001.M01.T04 | MD-GUI-005.001.M01 | Unit | "CANNOT ENTER" badge when capital exhausted | `util_pct >= max_allocation_pct` | `_can_enter.text() == "CANNOT ENTER"` | Implemented |
| UT-GUI-005.001.M01.T05 | MD-GUI-005.001.M01 | Unit | Position state colour coding | OPEN and PARTIAL_EXIT positions | OPEN `BackgroundRole == QColor("#1a3326")`; PARTIAL_EXIT `QColor("#332500")` | Implemented |

---

## Module: `gui/settings_panel.py` — SettingsPanel

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-006.001.M01.T01 | MD-GUI-006.001.M01 | Unit | Settings panel has 5 sub-tabs in correct order | Construct `SettingsPanel(svc)` | `tabs.count() == 5`; tab texts: Users, Strategies, Screeners, System, Universe | Implemented |
| UT-GUI-006.001.M01.T02 | MD-GUI-006.001.M01 | Unit | New user dialog calls `AppService.add_user()` | Fill `_UserDialog` and click OK | `svc.add_user()` called once; `users_changed` triggers table refresh | Implemented |
| UT-GUI-006.001.M01.T03 | MD-GUI-006.001.M01 | Unit | Delete user blocked when `AppService.delete_user()` returns error | Select user; click Delete; confirm | Warning `QMessageBox` shown; user remains in table | Implemented |
| UT-GUI-006.001.M01.T04 | MD-GUI-006.001.M01 | Unit | Universe tab meta label shows constituent count | `svc.get_sp500_universe()` returns 503 records | `_meta_label.text()` contains `"503 constituents"` | Implemented |

---

## Module: `gui/log_viewer_panel.py` — Log Viewer

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-007.001.M01.T01 | MD-GUI-007.001.M01 | Unit | Log entries appear when `AppService.log_message` emitted | Emit `svc.log_message("INFO", "hello")` 3 times | `panel._line_count == 3`; `_log_view` is non-empty | Implemented |
| UT-GUI-007.001.M01.T02 | MD-GUI-007.001.M01 | Unit | ERROR entry emits `error_occurred` signal | Emit `svc.log_message("ERROR", "fail")` | `error_occurred` signal emitted once | Implemented |
| UT-GUI-007.001.M01.T03 | MD-GUI-007.001.M01 | Unit | Level filter hides lower-priority entries | Buffer: 2 INFO + 1 WARNING; set level combo to WARNING | `_reapply_filter()` renders 1 visible entry | Implemented |
| UT-GUI-007.001.M01.T04 | MD-GUI-007.001.M01 | Unit | Buffer evicts oldest entries when exceeding `MAX_LINES` | Push `MAX_LINES + 5` messages | `len(panel._buffer) == MAX_LINES` | Implemented |
| UT-GUI-007.001.M01.T05 | MD-GUI-007.001.M01 | Unit | Pause halts display; Resume flushes buffered entries | Pause; emit 3 messages; Resume | After Resume `_line_count` increases by 3 | Implemented |

---

## Module: `gui/ibkr_session.py` — IBKRSession

> Tests use a `FakeIB` double in `tests/gui/conftest.py` exposing the `ib_insync` event objects (`accountValueEvent`, `pendingTickersEvent`, `disconnectedEvent`) as plain Python `Event` shims, plus stubs for `connectAsync`, `disconnect`, `reqAccountUpdates`, `reqMktData`, `cancelMktData`, `accountValues`, `portfolio`. No live IBKR connection. Asyncio loop spun up via `pytest-asyncio`.

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-012.001.M01.T01 | MD-GUI-012.001.M01 | Positive | `start(host, port, client_id)` boots dedicated QThread, creates asyncio loop, calls `connectAsync` exactly once with the supplied client_id | `session.start("127.0.0.1", 4001, 1)` | `FakeIB.connect_calls == [("127.0.0.1", 4001, 1)]`; `session._session_thread.isRunning() is True` | Skip |
| UT-GUI-012.001.M01.T02 | MD-GUI-012.001.M01 | Negative | Calling `start()` twice without intervening `stop()` is idempotent — no second thread/connection | `session.start(...)`; `session.start(...)` | `FakeIB.connect_calls.__len__() == 1`; only one `QThread` created | Skip |
| UT-GUI-012.001.M01.T03 | MD-GUI-012.001.M01 | Positive | `stop()` cancels asyncio tasks, calls `ib.disconnect()`, joins thread within 3 s | After `start`, call `session.stop()` | `FakeIB.disconnect_called is True`; `session._session_thread.isFinished() is True` within 3000 ms | Skip |
| UT-GUI-012.001.M01.T04 | MD-GUI-012.001.M01 | Edge | `stop()` returns cleanly even if asyncio loop is mid-`asyncio.sleep` in `_reconnect_loop` | Force session into reconnect state, then `stop()` | No `RuntimeError`; thread joins within 3 s; no orphan tasks reported by `asyncio.all_tasks()` | Skip |
| UT-GUI-012.001.M01.T05 | MD-GUI-012.001.M01 | Positive | `accountValueEvent` fires → after 50 ms `account_ready` signal emits exactly once with built snapshot | Fire `accountValueEvent` 5× in 10 ms | After 100 ms, `account_ready` emission count == 1; payload `AccountState.equity` reflects last value | Pass |
| UT-GUI-012.001.M01.T06 | MD-GUI-012.001.M01 | Positive | `pendingTickersEvent` fires → after 250 ms `quotes_updated` signal emits exactly once with combined row list | Fire `pendingTickersEvent` 3× in 50 ms with 2 symbols | After 350 ms, `quotes_updated` emission count == 1; payload has `len == 2` and `source=="ibkr"` for each | Pass |
| UT-GUI-012.001.M01.T07 | MD-GUI-012.001.M01 | Positive | `set_market_watch_symbols(["AAPL","MSFT"])` triggers `reqMktData` for both, none cancelled | After `start`, call `set_market_watch_symbols(["AAPL","MSFT"])` | `FakeIB.req_calls == ["AAPL","MSFT"]`; `cancel_calls == []` | Pass |
| UT-GUI-012.001.M01.T08 | MD-GUI-012.001.M01 | Positive | Mutating Market Watch symbols issues a delta only — overlapping symbols are not re-subscribed | After subscribing `["AAPL","MSFT"]`, call `set_market_watch_symbols(["AAPL","TSLA"])` | `FakeIB.req_calls == ["AAPL","MSFT","TSLA"]`; `cancel_calls == ["MSFT"]` | Pass |
| UT-GUI-012.001.M01.T09 | MD-GUI-012.001.M01 | Negative | Index symbols (`^GSPC`, `^IXIC`, `^DJI`) are filtered out inside `_apply_symbol_delta` and never reach `reqMktData` | `set_market_watch_symbols(["^GSPC","AAPL"])` | `FakeIB.req_calls == ["AAPL"]`; `"^GSPC" not in session._tickers` | Pass |
| UT-GUI-012.001.M01.T10 | MD-GUI-012.001.M01 | Positive | Union of MW and WL drives subscriptions; symbol in both remains subscribed when removed from one set | Set MW=`["AAPL","MSFT"]`, WL=`["AAPL","TSLA"]`; then MW=`["MSFT"]` | After second call: `cancel_calls == []`; `session._tickers.keys() == {"AAPL","MSFT","TSLA"}` | Pass |
| UT-GUI-012.001.M01.T11 | MD-GUI-012.001.M01 | Positive | `ib.disconnectedEvent` fires → `connection_lost` emits and reconnect loop starts | Fire `disconnectedEvent` after successful `start` | Within 50 ms `connection_lost` emitted once; `session._reconnect_task is not None` | Pass |
| UT-GUI-012.001.M01.T12 | MD-GUI-012.001.M01 | Positive | Reconnect loop on second attempt succeeds → resubscribes account + all tracked tickers; emits `connection_restored` | Disconnect once; let backoff fire; second `connectAsync` returns success | `connection_restored` emission count == 1; `reqAccountUpdates_calls.__len__() >= 2`; tickers resubscribed | Pass |
| UT-GUI-012.001.M01.T13 | MD-GUI-012.001.M01 | Negative | After 10 consecutive failed reconnects, session emits final `connection_lost("Max reconnect attempts reached")` and stops its loop | Force `connectAsync` to always raise | Final `connection_lost` payload contains `"Max reconnect"`; `session._stopping is True`; loop stopped | Pass |
| UT-GUI-012.001.M01.T14 | MD-GUI-012.001.M01 | Performance | Backoff sequence honours base 2 s, cap 30 s, ±20 % jitter | Force 4 failed attempts, capture sleep durations | Each captured delay ∈ `[base*0.8, base*1.2]`; sequence monotonic until cap; 5th attempt ≤ 36 s | Pass |
| UT-GUI-012.001.M01.T15 | MD-GUI-012.001.M01 | Negative | Account event arriving AFTER `stop()` does NOT emit `account_ready` (SRD-GUI-012.004 robustness) | After `start`, call `stop`; once thread is finished, push `accountValueEvent` synchronously into the fake | `account_ready` emission count remains 0 post-stop; no `RuntimeError` raised | Pass |
| UT-GUI-012.001.M01.T16 | MD-GUI-012.001.M01 | Negative | Re-applying the SAME symbol set is a no-op — no spurious `reqMktData` or `cancelMktData` calls (SRD-GUI-012.006 idempotence) | After subscribing `["AAPL","MSFT"]`, call `set_market_watch_symbols(["AAPL","MSFT"])` again | `FakeIB.req_calls` unchanged (length stays 2); `cancel_calls == []` | Pass |

---

## Module: `gui/app_service.py` — AppService Bridge (FO-GUI-012 deltas)

> Uses `qtbot` + `FakeIBKRSession` (a `QObject` exposing the same four signals as `IBKRSession`) injected via `monkeypatch` on `app_service.IBKRSession`. No real `ib_insync`, no real network.

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-GUI-012.001.M02.T01 | MD-GUI-012.001.M02 | Positive | `_on_session_account_ready` emits `account_updated` and `positions_updated` exactly once each, with `_ibkr_acct` and `_ibkr_positions` updated | After `connect_feed`, fake-session emits `account_ready(acct, [p1,p2])` | `account_updated` emitted once; `positions_updated` emitted once; `svc._ibkr_acct is acct`; `svc._ibkr_positions == [p1,p2]` | Pass |
| UT-GUI-012.001.M02.T02 | MD-GUI-012.001.M02 | Negative | `account_ready` emission delivered AFTER `disconnect_feed` does NOT re-populate `_ibkr_acct` or re-emit public signals | `connect_feed`; capture slot; `disconnect_feed`; manually invoke slot with stale args | `svc._ibkr_acct is None`; `account_updated` not emitted by the late slot call | Pass |
| UT-GUI-012.001.M02.T03 | MD-GUI-012.001.M02 | Positive | `_on_session_quotes_updated` partitions rows into MW and WL by membership in `_watch` / `_watchlist` and emits both public signals | Emit `quotes_updated([{AAPL},{MSFT},{TSLA}])` with `_watch=[AAPL]`, `_watchlist=[MSFT,TSLA]` | `market_watch_updated` and `watchlist_updated` each emitted once; `_wl_quotes` has keys `{MSFT,TSLA}` | Pass |
| UT-GUI-012.001.M02.T04 | MD-GUI-012.001.M02 | Edge | Index-symbol carve-out: `^`-prefixed Market Watch symbol missing from `quotes_updated` triggers a one-shot yfinance fetch | `_watch=[^GSPC,AAPL]`; emit `quotes_updated([{AAPL}])` | `_MarketWatchYfinanceWorker` spawned with `symbols == ["^GSPC"]` | Pass |
| UT-GUI-012.001.M02.T05 | MD-GUI-012.001.M02 | Positive | `connect_feed` after TCP probe success instantiates `IBKRSession`, wires four signals, calls `start` with `system_cfg.ibkr_system_client_id` | Call `connect_feed`; `_ConnectWorker` reports success | `IBKRSession.start_calls == [("host","port", system_cfg.ibkr_system_client_id)]`; four slot connections present | Pass |
| UT-GUI-012.001.M02.T06 | MD-GUI-012.001.M02 | Positive | `disconnect_feed` calls `IBKRSession.stop`, disconnects signals, releases reference, starts yfinance fallback timer | After connect, call `disconnect_feed` | `fake_session.stop_called is True`; `svc._ibkr_session is None`; `svc._yf_fallback_timer.isActive() is True` | Pass |
| UT-GUI-012.001.M02.T07 | MD-GUI-012.001.M02 | Positive | `connection_lost(reason)` from session triggers `_set_status(RECONNECTING)` without dropping the session reference | Emit `connection_lost("socket closed")` from fake session | `svc.connection_status == ConnectionStatus.RECONNECTING`; `svc._ibkr_session is not None` | Pass |
| UT-GUI-012.001.M02.T08 | MD-GUI-012.001.M02 | Positive | `connection_restored` from session triggers `_set_status(CONNECTED)` | Emit `connection_restored()` | `svc.connection_status == ConnectionStatus.CONNECTED`; `feed_status_changed` emitted with value `"connected"` | Pass |
| UT-GUI-012.001.M02.T09 | MD-GUI-012.001.M02 | Positive | yfinance fallback worker runs ONLY when `DISCONNECTED`; `_yf_fallback_timer` is stopped while `CONNECTED` | Start CONNECTED → DISCONNECTED → CONNECTED | While DISCONNECTED: `_yf_fallback_timer.isActive() is True`; on re-connect: `_yf_fallback_timer.isActive() is False` | Pass |
| UT-GUI-012.001.M02.T10 | MD-GUI-012.001.M02 | Positive | `set_market_watch_symbols` and `set_watchlist` forward to `IBKRSession` when CONNECTED | While connected, call `svc.set_market_watch_symbols(["AAPL"])` and `svc.set_watchlist([...])` | `fake_session.set_mw_calls[-1] == ["AAPL"]`; `set_wl_calls[-1] == [...]` | Pass |
| UT-GUI-012.001.M02.T11 | MD-GUI-012.001.M02 | Negative | `set_market_watch_symbols` does NOT forward to `IBKRSession` when DISCONNECTED (no crash, no AttributeError) | While disconnected, call `svc.set_market_watch_symbols(["AAPL"])` | No exception; `fake_session.set_mw_calls == []`; `_watch` still updated | Pass |
| UT-GUI-012.001.M02.T12 | MD-GUI-012.001.M02 | Negative | Deleted-identifier sweep: legacy classes/methods/fields are absent from `app_service.py` after refactor | Static grep over `app_service.py` source | Zero matches for `_AccountDataWorker`, `_MarketWatchWorker`, `_WatchlistQuoteWorker`, `_acct_timer`, `_watch_timer`, `_wl_timer`, `_refresh_account_data`, `_refresh_market_watch`, `_refresh_watchlist`, `_mw_log_on_next_fetch` | Pass |
| UT-GUI-012.001.M02.T13 | MD-GUI-012.001.M02 | Negative | Removed clientId fields are absent from `SystemConfig` dataclass | Inspect `SystemConfig` fields via `dataclasses.fields()` | `"ibkr_mw_client_id" not in field_names`; `"ibkr_wl_client_id" not in field_names`; `"ibkr_system_client_id" in field_names` | Pass |
| UT-GUI-012.001.M02.T14 | MD-GUI-012.001.M02 | Positive | Public AppService signal signatures remain unchanged (regression guard) | Reflect on `account_updated`, `positions_updated`, `market_watch_updated`, `watchlist_updated`, `feed_status_changed` | Each signal's `signal` attribute matches the pre-refactor reference signature captured in the test fixture | Pass |
