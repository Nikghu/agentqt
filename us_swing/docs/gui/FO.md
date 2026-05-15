# Functional Overview — GUI Module (GUI)

**Document ID:** FO-GUI
**Version:** 2.4.0
**Traces To:** requirements.md §21, §22, §23.3, §24, §25, §28.1, §29.1, §32
**Status:** Draft
**Last Updated:** 2026-05-13
**Project:** US Swing Trading System

---

## FO-GUI-000: Admin Terminal Architecture
- **Status:** Implemented

**Priority:** Must
**Source:** requirements.md §22, design decision 2026-03-08

This terminal operates as a **single-admin multi-user** application. The administrator has full access to all users' data and can take actions on behalf of any user. Non-admin views are accessed in the Settings panel only (user CRUD). All other panels (Dashboard, Screener, Execution) are multi-user aware via a scope selector.

### Admin Scope Model

| Scope | Meaning | Trigger |
|---|---|---|
| **All Users** | Aggregate view — positions, P&L, equity across all users | Default at startup |
| **Specific User** | Scoped view — data filtered to one user; actions target that user | Dropdown OR pill buttons |

### Scope Controls (two synchronized endpoints)
1. **Title bar dropdown** (`Scope:` QComboBox) — always visible, global to all panels.
2. **Dashboard pill strip** — quick-switch pills (`🌐 All`, `🔴 Alice`, `🔵 Bob`, `🔵 Carol`) per Dashboard panel.

Both endpoints call `DemoService.set_viewing_uid()` which emits `viewing_changed` signal. All panels connect to `viewing_changed` and re-render their data.

### Admin Admin Context Bar
A slim 28px bar below the accent line (`_AdminContextBar`) shows live-updating metadata for the current scope:
- **All Users**: user count · total equity · combined P&L · total open positions
- **Specific User**: username · equity · day P&L · open positions · risk % · mode · IBKR client ID

### Admin Action Attribution
When the admin acts on a specific user's positions (through the exit dialog or square-off actions), an "Acting on behalf of *Username*" banner appears in the confirmation dialog. All generated log messages include `[Username]` prefix.

---

## FO-GUI-001: Main Window & System Status Bar
- **Status:** Implemented

**Priority:** Must
**Source:** §21.1

The system shall provide a PyQt6 frameless main window with horizontal navigation containing: Dashboard, Screener, Execution, Chart, Settings panels. A persistent status bar shows broker connection state, current scope label (All Users / username), daily P&L for the current scope, and open position count. The title bar includes:
- Brand label
- Horizontal nav tabs (Dashboard · Screener · Execution · Chart · Settings)
- **🔐 ADMIN** role badge (yellow, persistent)
- **Scope QComboBox** (🌐 All Users, 🔴 Alice LIVE, 🔵 Bob PAPER, 🔵 Carol PAPER)
- Close/minimize/maximize window controls

Below the accent line: `_AdminContextBar` (28px) with scope-reactive metadata.

### Acceptance Criteria

1. Main window launches with all 5 panels accessible and scope defaulting to All Users.
2. Status bar updates in real-time (≤ 1 second latency) and reflects current scope label.
3. Window state (size, position) persists across sessions.
4. Changing scope combo instantly updates all panels without requiring manual refresh.
5. Admin context bar always reflects the current scope data.

---

## FO-GUI-002: Dashboard Panel
- **Status:** Implemented

**Priority:** Must
**Source:** §21.2, §25, §29.1

The Dashboard panel provides a real-time overview with scope-reactive data. Layout top-to-bottom:
1. **KPI Cards** (4): Today's P&L · Capital Utilised · Open Positions · Account Equity — all scoped.
2. **User Scope Pill Strip**: `🌐 All` + one pill per registered user. Clicking switches the scope and syncs with the title bar dropdown.
3. **Market Pulse Bar**: buying power, margin used, session mode.
4. **Tab widget**: Open Positions · Trade History — both scoped.
5. **Position action toolbar**: Square Off All (scoped) · Manage Selected (opens exit dialog).
6. **Log section** (bottom): Level filter · Search · Auto-scroll · Pause · Clear.

### Multi-user specifics
- In **All Users** scope: positions table prepends a **User** column (colour-coded by mode). Square Off All closes positions across all users (with confirmation).
- In **Specific User** scope: User column hidden, positions filtered to that user. Square Off All is scoped to that user.
- **Manage Selected** dialog shows `🔐 Admin · Acting on behalf of <Username>` banner when acting for any user.
- All position mutations (`close`, `partial_close`, `set_stop_loss`) carry the `user_id` of the row's owner, regardless of current scope.

### Acceptance Criteria

1. Scope pill and title bar dropdown stay in sync at all times.
2. Position table shows User column only in All-Users scope; column disappears when a specific user is selected.
3. KPI cards update immediately on scope change.
4. Manage Selected dialog shows acting-for banner when acting on a position belonging to any user.
5. Square Off All confirmation dialog shows scope context.

---

## FO-GUI-003: Screener Panel
- **Status:** Implemented

**Priority:** Must
**Source:** §21.3, §6 (req #6)

The Screener panel lists available screener filters with per-filter enable/disable toggle, adjustable parameter controls (RSI range, ATR period, volume multiplier, etc.), a "Run Screener" button for manual screening, and a results table (symbol, composite score, per-filter pass/fail) with "Add to Watchlist" action. Users select which screeners to run.

### Acceptance Criteria

1. Filter toggles persist across sessions per user.
2. Parameter controls validate input ranges (e.g., RSI 0–100).
3. "Run Screener" button is disabled while a screen is already running; progress indicator shown.
4. Results table supports sorting by composite score.
5. "Add to Watchlist" adds symbol to active watchlist and triggers real-time subscription.

---

## FO-GUI-004: Trade Execution Panel
- **Status:** Implemented

**Priority:** Must
**Source:** §21.4, §14 (req #14), §23.3

The Trade Execution panel is split horizontally into two panes:

**Left — Filtered Stocks pane:** Shows the most recent screener output across all presets. Stocks that passed any preset run are listed with their composite score, run type (Manual / Auto), trading styles, and source preset name. A date selector filters the list to a specific run date. The pane updates automatically whenever the Screener panel completes a preset run. This bridges the Screener and Execution workflows, giving the admin a single view of which stocks are ready for trade consideration.

**Right — Pending Signals pane:** For each pending trade signal, shows symbol, strategy, entry/stop/target levels, R:R ratio, a recommended quantity (auto-calculated by `RiskManager`), and a user-override quantity input. An **"Execute for" QComboBox** lets the admin choose which user (or All / Broadcast) receives the order; this syncs with the global viewing scope automatically. An optional entry confirmation dialog precedes execution and shows the target user in yellow.

### Acceptance Criteria

1. "Execute for" combo syncs with the global scope when `viewing_changed` fires.
2. Order confirmation dialog shows the target user label with admin attribution.
3. User-override quantity field accepts positive integers only.
4. Circuit breaker disables all entry buttons when active.
5. Exit controls remain enabled during circuit breaker.
6. Filtered Stocks pane auto-refreshes when `screener_results_updated` fires (no manual reload needed).
7. Filtered Stocks pane shows an empty-state placeholder when no screener results exist on disk.
8. Date selector in the Filtered Stocks pane contains only dates for which results exist, sorted newest first.

---

## FO-GUI-005: Position Monitor Panel
- **Status:** Implemented

**Priority:** Must
**Source:** §21.5, §25.1, §25.2, §25.3

The Position Monitor panel displays carry-over positions from prior sessions, position states (NEW, PARTIAL_ENTRY, OPEN, PARTIAL_EXIT, CLOSED), and capital availability for new entries. An explicit "Can enter next stock? Yes/No" indicator with remaining capital amount is shown.

### Acceptance Criteria

1. Carry-over positions loaded on startup via `PositionTracker.load_from_db(user_id)`.
2. Capital indicator: `remaining = total_equity − sum(open_position_values)`.
3. "Can enter?" evaluates `remaining >= min_position_cost` (i.e., `entry_price × floor(risk_dollars / risk_per_share)`).
4. Panel auto-refreshes on position state changes.

---

## FO-GUI-006: Settings Panel
- **Status:** Implemented

**Priority:** Must
**Source:** §21.6, §22

The Settings panel provides user management (create/edit/delete users), per-user settings (risk %, max position value, max allocation %, daily loss limit, default order type), strategy configuration (enable/disable strategies, parameter tuning), screener configuration (filter enable/disable, parameter editing), and system config (database URL, log level, IBKR connection params including the **System IBKR Client ID**, scheduler settings).

The Users tab enforces admin designation: each user row shows an "Admin" indicator; at least one admin must exist at all times; delete and demote actions are blocked for the last admin.

### Acceptance Criteria

1. User CRUD operations persist to `~/.usswing/users.json` immediately via atomic JSON write (write to `.tmp` then `Path.replace()`); on first launch the file is seeded with the first user as admin.
2. Settings changes take effect without requiring application restart.
3. System config changes (database URL, IBKR params) require confirmation dialog before applying.
4. Invalid setting values are rejected with inline validation messages.
5. Deleting the only admin user is blocked with an error dialog ("Cannot delete the only administrator").
6. The System tab exposes a "System IBKR Client ID" field for the clientId used by the system's market data connection.

---

## FO-GUI-007: Log Viewer Panel
- **Status:** Implemented

**Priority:** Should
**Source:** §21.7, §28.1

The Log Viewer panel provides a real-time streaming log display (INFO/WARNING/ERROR), filterable by log level, module, and symbol. Errors are highlighted and trigger alert indicators in the system status bar.

### Acceptance Criteria

1. Log entries stream in real-time via a `QueueHandler` → Qt signal bridge.
2. Filters apply without clearing existing log buffer.
3. ERROR-level entries cause status bar alert indicator to flash until acknowledged.
4. Log buffer is capped (configurable, default 10,000 entries) with oldest entries discarded.

---

## FO-GUI-008: Feed Connection Management
**Status:** Implemented
**Priority:** Must
**Source:** Phase 0 architecture constraint

The title bar exposes a Connect / Disconnect toggle button (after the Scope
selector) that initiates and terminates the IBKR paper-feed connection.
AppService owns a ConnectionStatus typed property accessible to any
subsystem for architecture-level failsafe checks.

### Acceptance Criteria

1. A single toggle button labelled "Connect Feed" is visible in the title bar
   when the feed is disconnected; it changes to "??  Connected" while connected
   and is disabled (showing "?  Connecting…") during the handshake window.
2. Clicking "??  Connected" opens a confirmation dialog ("Disconnect data feed?
   Position prices will stop updating.") requiring explicit Yes confirmation.
3. AppService.connection_status is a typed ConnectionStatus enum property
   usable by any module for failsafe guards without string comparisons.
4. Paper mode is the only mode available in Phase 0; no live trading path exists.

---

## FO-GUI-009: Market Watch
**Status:** Implemented
**Priority:** Must
**Source:** Feed verification + live LTP visibility

A compact Market Watch strip on the Dashboard (placed between KPI cards and the scope strip) shows live LTP and daily change % for up to 3 user-configurable symbols, defaulting to S&P 500 (^GSPC), NASDAQ (^IXIC), and Dow Jones (^DJI).

### Acceptance Criteria

1. Market Watch strip is always visible on the Dashboard, showing Name, LTP and Daily Change % for up to 3 symbols.
2. Prices refresh automatically every 15 seconds while feed is connected, and on connect.
3. User can edit symbols via an "Edit" button — entering any valid yfinance symbol (index or stock).
4. Prices show "–" when feed is disconnected or data is unavailable.
5. Daily Change % is green for positive, red for negative.

---

## FO-GUI-010: Candle Download Failure Tracking & Repair
**Status:** Approved
**Priority:** Should
**Source:** Operational need — IBKR Error 200 / transient data-farm failures

During a candle database build or delta-fill, individual symbol requests may fail (invalid contract, no data available, transient IBKR error). The system shall:

1. Detect per-symbol failures, record them with the reason, and inform the user in real time during the download.
2. After the download completes, surface a clear summary of failed symbols so the user knows exactly what data is missing.
3. Persist the failed-symbol list to disk so it survives application restarts.
4. Provide a one-click "Fix Discrepancies" action that re-attempts download for only the failed symbols without rebuilding the full database.

### Acceptance Criteria

1. Each symbol failure emits a log entry at WARNING level with the symbol name and reason.
2. The download progress section shows a live failed-symbol counter that increments as failures occur.
3. After download finishes, a "Discrepancies" panel appears if any symbols failed, listing the symbol names and a count.
4. The "Fix Discrepancies" button is enabled only when IBKR feed is connected and failed symbols exist.
5. Clicking "Fix Discrepancies" downloads only the listed failed symbols; on full success the discrepancy panel is cleared.
6. The failed-symbols list is persisted to `~/.usswing/candle_failed_symbols.json` and survives app restart.

---

## FO-GUI-011: Candle Chart Viewer
**Status:** Implemented
**Priority:** Should
**Source:** requirements.md §32

The system shall provide a dedicated "📈 Chart" navigation tab that allows the operator to visually inspect OHLCV candlestick data stored in the local candles.db for any available symbol. The primary use case is data-quality verification after a candle download.

The chart viewer shall:
1. List all symbols present in the local candles.db and let the user select one via a searchable dropdown with case-insensitive autocomplete.
2. Render a candlestick series and a synchronised volume histogram using TradingView Lightweight Charts v5 (Apache 2.0), embedded offline via QWebEngineView.
3. Support daily ("1d") and weekly ("1w") timeframes switchable without manual reload.
4. Show a configurable bar-count limit (20–2000, default 500) so the operator can focus on recent history.
5. Display an OHLCV crosshair tooltip in the chart header on hover.
6. Automatically refresh the symbol list whenever the tab becomes visible, reflecting any download activity that occurred while another tab was open.

### Acceptance Criteria

1. Symbol dropdown is populated from `AppService.get_candle_symbols()` on tab show and on "↺ Refresh List" click; previously selected symbol is preserved when still available.
2. Clicking "Load Chart" (or pressing Enter in the symbol field) renders a candlestick chart + synced volume histogram for the selected symbol/timeframe/limit.
3. Changing the timeframe combo or editing the bars spinbox triggers an automatic reload if a chart is already displayed.
4. Crosshair tooltip in the header shows: date, O, H, L, C, Vol for the hovered bar.
5. Candle and volume time-scales remain synchronised during pan and zoom.
6. A "No data" placeholder is shown (instead of an empty chart) when the queried symbol/timeframe has no rows in the database.
7. The bundled `lightweight-charts.standalone.production.js` is used when present; CDN fallback is used only when the bundle is missing.

---

## FO-GUI-012: Persistent IBKR Session
**Status:** Draft
**Priority:** Must
**Source:** Architectural fix — eliminate connect/disconnect cycling on IBKR Gateway

The system shall maintain a single persistent `ib_insync.IB` session for the lifetime of the IBKR feed connection. Account state, portfolio positions, Market Watch quotes, and Watchlist quotes shall be delivered by push-based subscriptions (`reqAccountUpdates`, `reqMktData`) rather than by repeated short-lived poll workers. Per-tick connect / authenticate / subscribe / disconnect cycling — currently producing rapid client-id churn on IBKR Gateway and risking "too many clients" throttling — shall be eliminated for monitoring traffic.

The persistent session shall be owned by a new `IBKRSession` module under `gui/`. `AppService` shall hold one reference to it and bridge its asyncio-thread signals onto the existing public Qt signals so no panel-level code is impacted.

### Scope Boundary

- **In scope (consolidated onto persistent session):** account / portfolio updates (replaces `_AccountDataWorker`), Market Watch quotes (replaces `_MarketWatchWorker`), Watchlist quotes (replaces the watchlist worker).
- **Out of scope (remain isolated as today):** candle download worker (intentional isolation per SRD-GUI-006.012), live-bar worker (already long-lived), execution path (read-only architecture unchanged).

### Acceptance Criteria

1. While the feed is `CONNECTED`, exactly one `ib_insync.IB` socket connection exists for monitoring traffic (account + Market Watch + Watchlist). Verifiable by inspecting open IBKR clientIds during a 10-minute session — no churn, no transient clientIds.
2. Account equity, portfolio positions, Market Watch LTPs, and Watchlist LTPs reach the GUI within 2 seconds of an IBKR push under normal operation; no GUI polling timer drives these updates.
3. Public `AppService` signals `account_updated`, `positions_updated`, `market_watch_updated`, `watchlist_updated`, and `feed_status_changed` retain their existing signatures byte-for-byte; no panel code requires modification.
4. `disconnect_feed()` cleanly cancels every active subscription and tears down the persistent session; reconnecting via `connect_feed()` re-establishes the session and re-subscribes the current Market Watch + Watchlist symbol sets within 5 seconds.
5. On an unexpected socket drop, the session shall transition `feed_status_changed` to `RECONNECTING`, attempt reconnect with backoff, and on success resubscribe transparently — no panel code observes a partial-state outage other than the standard status transition.
6. When `DISCONNECTED`, Market Watch and Watchlist quotes fall back to the existing yfinance path with unchanged semantics; no quote-source regression is introduced for offline use.
7. The Market Watch and Watchlist symbol sets are mutable at runtime: editing them while `CONNECTED` cancels stale subscriptions and creates new ones without dropping unaffected symbols.
8. The persistent session uses one dedicated `clientId` (the existing system clientId); the legacy `clientId + 1`, `ibkr_mw_client_id`, and `ibkr_wl_client_id` allocations are removed wherever they are no longer referenced.
9. The candle download worker and the live-bar worker continue to use their own isolated clientIds and connection lifecycles; this feature shall not alter their behaviour.
10. All deleted legacy code (`_AccountDataWorker`, `_MarketWatchWorker`, the watchlist worker, their timers, refresh handlers, and orphaned config keys) is removed in full — no commented-out blocks, "removed" placeholders, or backwards-compatibility shims remain.
