# Functional Overview — GUI Module (GUI)

**Document ID:** FO-GUI
**Version:** 2.6.0
**Traces To:** requirements.md §21, §22, §23.3, §24, §25, §28.1, §29.1, §32
**Status:** Draft
**Last Updated:** 2026-05-22
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

## FO-GUI-012: Live Streaming Price Display

**Status:** Approved
**Priority:** Must
**Depends on:** FO-EXE-008, FO-GUI-005, FO-GUI-009
**Source:** Operational need — eliminate yfinance polling latency for live position and watchlist prices

AppService shall replace yfinance polling for current price on three GUI surfaces with IBKR `reqMktData` streaming ticks provided by `LiveTickWorker` (FO-EXE-008). The change is transparent to all consumer panels — they continue to receive the existing `positions_updated`, `market_watch_updated`, and `watchlist_updated` signals; only the internal price-update path changes.

### Surface 1 — Market Watch Strip (extends FO-GUI-009)

The 15-second `_MarketWatchWorker` QThread and its yfinance polling path are removed. Market Watch symbols (user-entered in Yahoo notation, e.g. `^GSPC`) are translated to IBKR index contracts by a static mapping maintained in AppService:

| Yahoo symbol | IBKR Contract |
|---|---|
| `^GSPC` | `symbol=SPX, secType=IND, exchange=CBOE, currency=USD` |
| `^IXIC` | `symbol=COMP, secType=IND, exchange=NASDAQ, currency=USD` |
| `^DJI` | `symbol=INDU, secType=IND, exchange=ECBOT, currency=USD` |

Symbols not present in the map are not subscribed; their displayed price shows `"–"`. On each `tick_price(tag, price)` event for a Market Watch tag, AppService updates the in-memory watch entry and emits `market_watch_updated`.

### Surface 2 — Watchlist Quote Panel (extends FO-GUI-003)

The 30-second `_WatchlistQuoteWorker` price-polling path is replaced with tick events. AppService subscribes only watchlist symbols that appear in the locally cached S&P 500 universe (`load_sp500()`, `universe/store.py`). Non-S&P 500 symbols are not subscribed; their LTP column shows the last known value or `"–"` if no tick has arrived.

Static metadata fields (day_open, day_high, day_low, year_high, year_low, volume, market_cap) are fetched once via yfinance at watchlist load time (no continuous polling). These fields are not updated by streaming ticks.

### Surface 3 — Position Monitor current_price (extends FO-GUI-005)

`_AccountDataWorker` (30-second IBKR portfolio snapshot) remains the authoritative source for account equity, P&L, and position snapshot. However, for any open position whose symbol is a member of the S&P 500, `current_price` is overridden by the most recent `tick_price` value. Non-S&P 500 position symbols continue to derive current_price from the portfolio snapshot (marketValue / quantity).

### Lifecycle & Subscription Management

- `LiveTickWorker` is instantiated by AppService immediately after IBKR connect succeeds. Initial contract set = Market Watch contracts + active watchlist S&P 500 symbols + open position S&P 500 symbols.
- On watchlist change or position open/close, AppService calls `LiveTickWorker.set_contracts()` to reconcile subscriptions.
- On IBKR disconnect, AppService calls `LiveTickWorker.request_stop()`. Market Watch prices revert to `"–"`; position and watchlist LTPs retain their last known values until the next account poll updates them.
- `SystemConfig.ibkr_tick_client_id` (default 14) is exposed in the Settings → System tab so operators can adjust it without redeploying.

### Acceptance Criteria

1. With IBKR feed connected, a price move for an S&P 500 symbol held as an open position updates the Position Monitor `current_price` column within 1 s — no manual refresh required.
2. Market Watch `^GSPC` LTP updates within 1 s of an SPX index tick; daily change % recalculates correctly from the same tick data.
3. Adding an S&P 500 stock to the Watchlist triggers a `LiveTickWorker.set_contracts()` call and that symbol's LTP begins streaming within 2 s. Day_open and year_high fields remain as set at watchlist-load time.
4. On IBKR disconnect, Market Watch cells display `"–"`; Position Monitor current_price retains its last streamed value.
5. A non-S&P 500 symbol open in the Position Monitor receives no tick subscription; its current_price is updated by the 30-second `_AccountDataWorker` poll as before.
6. A user-entered Market Watch symbol with no entry in the index translation map (e.g., a custom ticker) is not subscribed and displays `"–"` without error.
7. Changing `ibkr_tick_client_id` in Settings and reconnecting the feed starts a new `LiveTickWorker` with the updated clientId.

---

## FO-GUI-013: Strategy Builder Dialog (Add / Edit Strategy)

**Status:** Approved
**Priority:** Must
**Depends on:** FO-GUI-004 (Execution Panel hosts the launcher)
**Precedes:** FO-EXE-011 (Strategy Engine consumes the produced `StrategyConfig`)
**Source:** Strategy authoring workflow

The system shall provide a modal **Strategy Builder dialog** that lets the administrator define and edit a strategy configuration across five pages. The dialog is the sole authoring surface for strategy definitions and produces a `StrategyConfig` record consumed by the Strategy Engine (FO-EXE-011). It is launched from the Execution Panel via an Add Strategy button (new) or an Edit action (existing).

### Layout
Frameless modal with a left-side navigation tree and a right-side stacked content panel. Nav entries in order: **Strategy Info · Triggers · Scheduler · Execution · Risk**. Switching nav entries preserves in-progress edits.

### Page 1 — Strategy Info
- **Name** — required, unique within the registry
- **Symbol Scope** — `All S&P 500` / `Include Only` / `Exclude These`; non-`All` reveals a per-symbol picker (search-completer + add/remove list)
- **Mode** — `Disabled` / `Manual` / `Auto` (semantics owned by FO-EXE-011)
- **Capital Max** — integer percentage of available capital allocated to this strategy

### Page 2 — Triggers
Progressive condition builder. The user chains two indicator expressions with a relational operator and a logical operator, presses **Compile**, then assigns the compiled clause to **Entry** or **Exit**. Multiple compiled clauses join with `AND` / `OR`. Supported indicators: `Number`, `PNL`, `VWAP`, `Price`, `RSI`, `ADX`, `EMA`, `SUPERTREND`, `SWING`, `MACD`, `BOS_Engulfing`, `BOSS_EMA`, `BOSS_ADX`, `BOSS_SMT`. Each indicator's parameter form is rendered from a static catalogue (parameter name, widget type, value domain).

### Page 3 — Scheduler
- **Time Range** — `start_time` / `end_time` (HH:mm, defaults 09:30 / 15:30)
- **Date Range** — `start_date` / `end_date` (defaults today and today + 6 months)
- **Days of Week** — Mon–Fri toggle pills, all enabled by default

### Page 4 — Execution
- **Auto Trade** — boolean flag for automatic order submission
- **Trade Type** — `Intraday` / `Positional`

### Page 5 — Risk
- **Target** — enable flag, type (`Fixed` / `Trailing`), value (% of entry)
- **Stop Loss** — enable flag, type (`Fixed` / `Trailing`), value (% of entry)

### Persistence
Configurations are persisted to a strategy registry on disk (current location: `~/.usswing/strategies.json`; FO-EXE-011 may migrate the registry into `candles.db`). Each record contains the five-page settings plus a `strategy_signal` runtime block (status, executed quantity, order timestamps) initialized to inactive. Saving by an existing `name` overwrites; a new `name` appends. Editing populates every field from the persisted record; closing without saving discards changes.

### Acceptance Criteria
1. Strategy name is required; saving with a blank name is blocked with an inline error.
2. Symbol scope `Include Only` / `Exclude These` reveals the per-symbol picker; the saved record stores the list in `symbols_include` or `symbols_exclude`. `All S&P 500` leaves both lists empty.
3. The trigger builder reveals its next element only after the previous is set: Condition 1 → relational operator → Condition 2 → logical operator → Compile.
4. **Compile** appends the new clause to the read-only compiled-conditions buffer joined by the chosen logical operator (`AND` / `OR`).
5. **Entry** / **Exit** assign the compiled buffer to the corresponding slot and clear the buffer; pressing either with an empty buffer surfaces an inline error.
6. Each saved indicator expression is a parseable function-call string `INDICATOR(param1, 'param2', …)` — dropdown values single-quoted, editbox values bare.
7. Target and stop-loss Type combo + Value spinbox are disabled until their enable checkbox is ticked.
8. **Capital Max** accepts integer percentages 5–100 inclusive, stepped by 5, default 25.
9. `strategy_signal.Status` is forcibly reset to `Inactive` on every load from disk — no strategy resumes a running state from persistence alone.
10. The `StrategyConfig` field set produced by the dialog is the contract consumed by FO-EXE-011; the canonical schema is owned by the downstream SRD.

---

## FO-GUI-014: Active Cycles Panel (Pending Signals + Open Trades)

**Status:** Approved
**Priority:** Must
**User-facing label:** "Active Trades" (the term "cycle" is internal/code only)
**Depends on:** FO-EXE-011 (pending-signal store + `StrategyEvent`), FO-EXE-012 (`TradeCycleEvent`, `TradeCycleQuery`, `TradeCycleCommand`)
**Supersedes:** FO-GUI-004 "Pending Signals" pane (right pane only — the left "Filtered Stocks" pane is unchanged)
**Source:** Trader requirement — one panel that shows the full Entry→Exit lifecycle of every active swing trade with live PnL, hard stop, target, trailing stop.

The system shall provide an **Active Cycles Panel** that replaces the right pane of the Execution Panel (FO-GUI-004) with a single unified table tracking every `(strategy_id, symbol)` pair currently in motion — from the moment a Manual-mode signal lands in the pending-signal store, through entry-order in flight, open position with live PnL, through exit-order in flight, until the cycle closes and the row drops out. Each row carries a State badge, identity columns (entry time, symbol, strategy), live market columns (LTP, PnL), risk columns (hard stop / target / trailing stop), and a context-appropriate action set. The panel owns no business logic — it consumes events from FO-EXE-011 and FO-EXE-012 and emits user-action signals back to those services.

### State Badges

| Badge | Source | Source state | Visual |
|---|---|---|---|
| `PENDING` | FO-EXE-011 pending-signal store | Signal awaiting user execution (Manual mode or `auto_trade=False`) | Amber |
| `OPENING` | FO-EXE-012 cycle | `state=OPENING` (entry order in flight) | Blue spinner |
| `OPEN` | FO-EXE-012 cycle | `state=OPEN` (position live, ticks updating) | Green |
| `CLOSING` | FO-EXE-012 cycle | `state=CLOSING` (exit order in flight) | Orange spinner |

`ABORTED` and `CLOSED` cycles drop out of the panel within 1 second of their terminal event; closed-cycle history lives on the Dashboard Trade History tab.

### Columns

| Column | PENDING | OPENING | OPEN | CLOSING |
|---|---|---|---|---|
| **State** | badge | badge | badge | badge |
| **Time** | signal time | signal time | entry fill time | entry fill time |
| **Symbol** | shown | shown | shown | shown |
| **Strategy** | `strategy_id` | `strategy_id` | `strategy_id` | `strategy_id` |
| **Qty** | recommended | submitted | filled | filled |
| **Entry $** | est. | est. | actual `entry_price` | actual `entry_price` |
| **LTP** | — | live | live | live |
| **PnL $ / %** | — | live (mark) | live | live |
| **Hard Stop** | from `StrategyConfig` | snapshot | editable | editable (read-only during fill) |
| **Target** | from `StrategyConfig` | snapshot | editable | editable (read-only during fill) |
| **Trail** | — | snapshot | live `trailing_stop_level` | live |
| **Actions** | `[Execute]` `[✕]` | spinner | `[Edit Risk ▼]` `[Close]` | spinner |

### Actions

| Control | State allowed | Effect |
|---|---|---|
| `[Execute]` | PENDING only | Opens confirmation dialog; on confirm, sends pending signal to `ExecutionRouter` via FO-EXE-011 command surface; row transitions to `OPENING` on order submission |
| `[✕] Dismiss` | PENDING only | Removes signal from pending-signal store; logs `[Execution] User dismissed signal for {symbol}` at INFO; row disappears |
| `[Edit Risk ▼]` | OPEN only | Expands inline editor for `hard_stop_loss`, `target_price`, `trailing_offset`, `trailing_mode`; on Save invokes `TradeCycleCommand.update_risk(cycle_id, …)`; invariant violations from FO-EXE-012 §10 surface as inline error |
| `[Close]` | OPEN only | Opens confirmation dialog with current LTP and estimated PnL; on confirm, emits `manual_close(cycle_id)` to FO-EXE-002; row transitions to `CLOSING` |

### Requirements

1. **Single unified table.** The panel shall render one table with rows representing every active state (`PENDING` / `OPENING` / `OPEN` / `CLOSING`) for any `(strategy_id, symbol)` pair, sorted newest-first by Time.
2. **Event subscriptions.** The panel shall subscribe to: `pending_signal_added`, `pending_signal_removed` from FO-EXE-011, and `CycleOpened`, `CycleUpdated`, `CycleClosing`, `CycleClosed`, `CycleAborted`, `RiskUpdated` from FO-EXE-012. Each event triggers an incremental row mutation; no full table re-render.
3. **Live tick rendering.** `CycleUpdated` payloads (≥ 500 ms throttle from the ledger) update LTP, PnL $/%, trailing-stop level, and effective-stop columns in place. PnL cells are colour-coded green for positive, red for negative.
4. **PENDING → OPENING transition.** When the user clicks `[Execute]` on a PENDING row and the confirmation is accepted, the panel sends the signal to the FO-EXE-011 command surface and shows an OPENING badge until the matching `CycleOpened` event arrives, at which point the badge flips to OPEN.
5. **OPEN row expand.** Clicking `[Edit Risk ▼]` on an OPEN row reveals an inline editor under the row with editable `hard_stop_loss`, `target_price`, `trailing_offset`, `trailing_mode` (`$` / `%`) controls and Save / Cancel buttons. Save invokes `TradeCycleCommand.update_risk()`; an `invariant_violation` error is rendered inline without closing the editor.
6. **Risk-edit invariants.** The editor's spinboxes shall pre-validate locally per FO-EXE-012 §10: HSL spinbox max = current LTP; Target spinbox min = current LTP; trailing offset min = 0.01. The server-side check remains authoritative.
7. **`[Close]` confirmation.** The close dialog shall display `Close position? Submit SELL {qty} × {symbol} @ MKT — Entry ${entry_price} · Current ~${LTP} · Est. P&L: {pnl}`. On confirm the row transitions to CLOSING immediately (optimistic UI); a `CycleClosed` event removes the row, or a fill-reject restores it to OPEN.
8. **Terminal row removal.** On `CycleClosed` or `CycleAborted` for any row, the row shall disappear from the table within 1 second of event receipt; a brief fade-out animation is acceptable but not required.
9. **Empty state.** When the table contains zero rows the panel shall render a placeholder ("No active cycles — pending signals and open positions appear here") with no actions.
10. **No business logic.** No panel module shall compute PnL, evaluate exit conditions, or apply risk edits locally. Every mutation flows through `TradeCycleCommand` / FO-EXE-011 command surfaces. The panel is a renderer + action emitter.
11. **Scope sync.** When the global admin Scope (FO-GUI-001) changes, the table re-queries `TradeCycleQuery.open_cycles()` and the pending-signal store, filtering to the selected user. The "All Users" scope shows every user's cycles with a prepended `User` column.
12. **Circuit breaker behaviour.** When `circuit_breaker_active = True` (FO-EXE-003), `[Execute]` is disabled on every PENDING row with tooltip `Circuit breaker active — no new entries`; `[Close]` and `[Edit Risk ▼]` remain enabled so the trader can manage existing positions.

### Acceptance Criteria

1. A new pending signal for `(boss_ema, AAPL)` from FO-EXE-011 inserts exactly one new row with State badge `PENDING`, Strategy `boss_ema`, Symbol `AAPL`, the recommended Qty, est. Entry from the signal's payload, and `[Execute]` / `[✕]` buttons in the Actions cell.
2. Clicking `[✕]` on that PENDING row removes the row, dispatches the dismiss command to FO-EXE-011, and emits one INFO log `[Execution] User dismissed signal for AAPL`.
3. Clicking `[Execute]` opens a confirmation dialog showing `Submit BUY {qty} × AAPL @ MKT?`; on confirm, the row's badge flips to `OPENING` within 100 ms (optimistic), then to `OPEN` when `CycleOpened` arrives.
4. With an OPEN cycle at `entry_price=$182.50, qty=25`, a `CycleUpdated` event carrying `current_price=185.00, current_pnl_usd=62.50, trailing_stop_level=182.50` updates the row's LTP cell to `185.00`, PnL cell to `+$62.50` (green), and Trail cell to `182.50` within the next paint cycle.
5. Clicking `[Edit Risk ▼]` on the OPEN AAPL row reveals an inline editor; setting `hard_stop_loss=$200` (above current `$185.00`) and clicking Save renders an inline error "HSL cannot exceed current price" and leaves the row's HSL unchanged.
6. Setting `hard_stop_loss=$184.50` and clicking Save invokes `update_risk(cycle_id, hard_sl=184.50)`, returns successfully, the editor closes, and the row's Hard Stop cell shows `184.50`.
7. Clicking `[Close]` on the OPEN AAPL row shows a confirmation dialog with current LTP and estimated PnL; on confirm the row's badge flips to `CLOSING` immediately and `[Close]` / `[Edit Risk ▼]` are replaced by a spinner.
8. A `CycleClosed(cycle_id, …)` event for the AAPL cycle removes the row within 1 second; the table updates to show one fewer row.
9. With `circuit_breaker_active = True`, every PENDING row's `[Execute]` button is disabled with the tooltip text; `[Close]` and `[Edit Risk ▼]` on existing OPEN rows remain enabled.
10. With the global Scope switched from "All Users" to a specific user, the table re-queries and renders only that user's pending signals and open cycles; the prepended User column is hidden.
11. With zero rows in any state, the panel renders the empty-state placeholder; no row container is drawn.
