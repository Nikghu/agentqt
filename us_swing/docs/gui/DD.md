# Design Document — GUI Module (GUI)

**Document ID:** DD-GUI
**Version:** 1.6.0
**Traces To:** SRD-GUI v2.8.0
**Status:** Draft
**Last Updated:** 2026-05-22
**Project:** US Swing Trading System

> v1.6.0: DD-GUI-014.* added — Active Cycles Panel (view-model, delegate, inline risk editor).
> v1.5.0: DD-GUI-013.* added — Strategy Builder Dialog (shell, schema, trigger builder, persistence).

---

## DD-GUI-001.001.D01 — MainWindow & Application Shell Design

**Parent SRD:** SRD-GUI-001.001 — SRD-GUI-001.004
- **Status:** Implemented
**Last Updated:** 2026-03-16 (revised to match implemented GUI)

### Public Interface

```python
class MainWindow(QMainWindow):
    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None

    # Public slot
    def on_circuit_breaker(self, active: bool) -> None

    # Private slots (wired to AppService signals)
    def _refresh_status(self) -> None               # account_updated / positions_updated / viewing_changed
    def _on_internet_status_changed(self, online: bool) -> None  # internet_status_changed
    def _on_market_status(self) -> None             # market_status_updated
    def _on_watchlist_add(self, symbol: str) -> None  # screener_panel.watchlist_add_requested

    # Lifecycle
    def closeEvent(self, event: object) -> None
```

> **Note:** `set_active_user()` and `update_connection_status()` do not exist. Scope selection is handled by `_TitleBar._scope_combo`; feed state is managed entirely through `AppService` signals.

### Private Components

| Class | Base | Purpose |
|---|---|---|
| `_TabBtn` | `QPushButton` | Checkable horizontal nav tab (icon + label, autoExclusive, height 38px) |
| `_WinBtn` | `QPushButton` | macOS-style 14×14 colored-circle window control; shows symbol on hover |
| `_TitleBar` | `QWidget` | Full-width 40px frameless top bar (brand, nav, admin controls, feed toggle, win controls) |
| `_AdminContextBar` | `QWidget` | 28px info strip (Market Watch + scope-aware account details) |

### Layout Structure

```
MainWindow (QMainWindow — FramelessWindowHint)
└── root QWidget (central widget)
    ├── _TitleBar  (fixed height: 40px)
    │   ├── Brand: "◈  US SWING"
    │   ├── [VDivider]
    │   ├── Nav tabs (5 × _TabBtn, QStackedWidget-driven)
    │   │   ├── 📊 Dashboard
    │   │   ├── 🔍 Screener
    │   │   ├── ⚡ Execution
    │   │   ├── 📈 Chart
    │   │   └── ⚙ Settings
    │   ├── [stretch]
    │   ├── "🔐 ADMIN" badge  (QLabel, yellow border)
    │   ├── "Scope:" label + QComboBox (width 160px)
    │   │   ├── Item 0: "🌐  All Users"  (userData=None)
    │   │   └── Item N: "{dot}  {username} · {MODE}"  (userData=user_id)
    │   ├── Feed toggle QPushButton  (fixed 140×26px, 3 visual states)
    │   │   ├── Disconnected: "Connect Feed"  (neutral border)
    │   │   ├── Reconnecting: "⟳  Connecting…"  (yellow, disabled)
    │   │   └── Connected:    "🟢  Connected"   (green border, enabled)
    │   ├── [VDivider]
    │   └── Window controls (3 × _WinBtn, spacing 6px)
    │       ├── ● Minimize  "─"
    │       ├── ● Maximize  "□"
    │       └── ● Close     "✕"
    ├── QFrame (HLine accent — blue underline)
    ├── _AdminContextBar  (fixed height: 28px)
    │   ├── "MARKET WATCH" label
    │   ├── 3 market cells: [name] [ltp] [chg%]  (chg colour: green/red)
    │   ├── "│" separator
    │   ├── Scope icon (🌐 all-users | 👤 single-user)
    │   └── Items: scope · equity · pnl · positions
    │          (+ risk · mode · ibkr  — single-user view only)
    ├── QStackedWidget  (stretch=1, content area)
    │   ├── Index 0: DashboardPanel
    │   ├── Index 1: ScreenerPanel
    │   ├── Index 2: ExecutionPanel
    │   ├── Index 3: CandleChartPanel
    │   └── Index 4: SettingsPanel
    └── QStatusBar  (sizeGripEnabled=False)
        ├── [permanent-left]  sb_conn  "●  Internet: Online/Offline/Checking…"
        ├── [permanent-left]  separator "│"
        ├── [permanent-left]  sb_pnl   "P&L: +$X,XXX.XX"  (green/red)
        ├── [permanent-left]  separator "│"
        ├── [permanent-left]  sb_pos   "Positions: N"
        ├── [permanent-right] sb_nyse   "⬤  NYSE"    (color + tooltip by session state)
        └── [permanent-right] sb_nasdaq "⬤  NASDAQ"  (color + tooltip by session state)
```

> **PositionMonitorPanel and LogViewerPanel** are not in the current nav. They exist as modules but are not wired into `_TitleBar` nav tabs as of this implementation.

### AppService Signal Wiring

| Signal | Handler | Effect |
|---|---|---|
| `svc.account_updated` | `_refresh_status` | Refresh sb_pnl, sb_pos |
| `svc.positions_updated` | `_refresh_status` | Refresh sb_pnl, sb_pos |
| `svc.viewing_changed` | `_refresh_status` | Refresh sb_pnl, sb_pos |
| `svc.internet_status_changed(bool)` | `_on_internet_status_changed` | sb_conn label text + colour |
| `svc.market_status_updated` | `_on_market_status` | NYSE/NASDAQ pill colour + tooltip |
| `svc.feed_status_changed(str)` | `_TitleBar._on_feed_status_changed` | Feed button text/colour/enabled |
| `svc.viewing_changed` | `_AdminContextBar.refresh` | Scope strip content |
| `svc.market_watch_updated` | `_AdminContextBar._refresh_mw` | Market Watch cell values |
| `screener_panel.watchlist_add_requested(str)` | `_on_watchlist_add` | Forwarded to `dashboard_panel.on_watchlist_add` |

### Status Bar Market Session Colours

| Session | Colour | Tooltip |
|---|---|---|
| `open` | Green | Regular Trading Hours  09:30 – 16:00 ET |
| `pre_market` | Orange | Pre-Market Session  04:00 – 09:30 ET |
| `after_hours` | Yellow | After-Hours Session  16:00 – 20:00 ET |
| `closed` | Muted | Market Closed |

### Admin Scope Behaviour

| `viewing_uid` | Scope icon | Items shown | Items hidden |
|---|---|---|---|
| `None` (all-users) | 🌐 | scope, equity, pnl, positions | risk, mode, ibkr |
| `int` (single user) | 👤 | scope, equity, pnl, positions, risk, mode, ibkr | — |

### Window Geometry Persistence

```python
# Restore (in __init__):
settings = QSettings("USSwing", "MainWindow")
geom = settings.value("geometry")
if geom:
    self.restoreGeometry(geom)
else:
    screen = QApplication.primaryScreen().availableGeometry()
    w, h = 1_180, 740
    self.setGeometry((screen.width()-w)//2, (screen.height()-h)//2, w, h)

# Save (closeEvent):
def closeEvent(self, event):
    settings = QSettings("USSwing", "MainWindow")
    settings.setValue("geometry", self.saveGeometry())
    # Note: windowState is NOT saved
```

> Default size: **1180 × 740 px**. No separate `restore_geometry()` method — geometry restoration is inline in `__init__`.

### Feed Toggle State Machine

```
[DISCONNECTED]
    "Connect Feed" (neutral)  ──► user clicks ──►  svc.connect_feed()
         ▲                                              │
         │                                    svc.feed_status_changed("reconnecting")
         │                                              │
         │                                    [RECONNECTING]
         │                                    "⟳ Connecting…" (yellow, disabled)
         │                                              │
         │                                    svc.feed_status_changed("connected")
         │                                              │
         └──── user clicks Yes on QMessageBox ◄── [CONNECTED]
                     svc.disconnect_feed()         "🟢 Connected" (green)
```

### Circuit Breaker

```python
def on_circuit_breaker(self, active: bool) -> None:
    self._execution_panel.on_circuit_breaker(active)
    # Delegated entirely to ExecutionPanel — MainWindow has no direct CB UI
```

---

## DD-GUI-002.001.D01 — Dashboard Panel Design

**Parent SRD:** SRD-GUI-002.001 — SRD-GUI-002.005
**Status:** Implemented
**Last Updated:** 2026-03-17

### PositionTableModel

```python
class PositionTableModel(QAbstractTableModel):
    _BASE_COLS = ["Symbol", "Qty", "Avg Entry", "Current", "P&L ($)", "P&L %",
                  "Stop", "Target", "State"]   # 9 columns
    _USER_COL  = ["User"]                       # prepended when show_user=True

    def __init__(self, parent: Any = None) -> None

    # Toggle optional User column (all-users admin scope)
    def set_show_user(self, show: bool, user_labels: dict[int, str] | None = None) -> None

    # Replace all rows; emits beginResetModel / endResetModel
    def refresh(self, positions: list[OpenPosition]) -> None

    # Highlight a row in red (e.g. stop-hit warning); pass -1 to clear
    def set_highlighted_row(self, row: int) -> None

    def rowCount(self, parent=QModelIndex()) -> int
    def columnCount(self, parent=QModelIndex()) -> int      # 9 base, 10 with User
    def data(self, index: QModelIndex, role=Qt.DisplayRole) -> Any
    def headerData(self, section, orientation, role) -> Any
```

> **Column indexing note:** When `_show_user=True`, all base-column indices shift by +1. Helper methods `_display()`, `_background()`, `_foreground()` compensate via `base_col = (col - 1) if self._show_user else col`.

### PositionTableModel Colour Logic

```python
# _background(pos, col)  — base_col = P&L($) column (index 4)
if base_col == 4:
    return QColor(C.PNL_POS_BG) if pos.unrealised_pnl >= 0 else QColor(C.PNL_NEG_BG)

# base_col = State column (index 8)
if base_col == 8:
    state_bg = {"NEW": "#2a2a2a", "PARTIAL_ENTRY": "#332b00",
                "OPEN": "#1a3326", "PARTIAL_EXIT": "#332500", "CLOSED": "#1a1a1a"}
    return QColor(state_bg.get(pos.state, C.SURFACE))

# _foreground(pos, col)
if base_col == 4:  return QColor(C.GREEN) if pos.unrealised_pnl >= 0 else QColor(C.RED)
if base_col == 5:  return QColor(C.GREEN) if pos.pnl_pct >= 0 else QColor(C.RED)
if base_col == 8:  return QColor(C.STATE_*)   # per-state constant from theme.C

# Highlighted row (set_highlighted_row): BackgroundRole=#3a0a0a, ForegroundRole=C.RED
```

---

### TradeHistoryModel

```python
class TradeHistoryModel(QAbstractTableModel):
    _BASE_COLS = ["Date & Time", "Symbol", "Side", "Qty", "Entry", "Exit",
                  "P&L", "Strategy", "Mode"]   # 9 columns
    _USER_COL  = ["User"]                        # same pattern as PositionTableModel

    def __init__(self, parent: Any = None) -> None
    def set_show_user(self, show: bool, user_labels: dict[int, str] | None = None) -> None
    def refresh(self, trades: list[TradeRecord]) -> None  # sorts by entry_time desc
    def rowCount / columnCount / headerData / data  # standard interface
```

### TradeHistoryModel Colour Logic

```python
# BackgroundRole — P&L column (base_col 6)
if base_col == 6 and t.pnl is not None:
    return QColor(C.PNL_POS_BG) if t.pnl >= 0 else QColor(C.PNL_NEG_BG)

# ForegroundRole — P&L + Side columns
if base_col == 6:  return QColor(C.GREEN) if t.pnl >= 0 else QColor(C.RED)
if base_col == 2:  return QColor(C.GREEN) if t.side == "BUY" else QColor(C.RED)
```

---

## DD-GUI-004.001.D01 — Trade Execution Panel Design

**Parent SRD:** SRD-GUI-004.001 — SRD-GUI-004.006
- **Status:** Approved

### Signal-to-UI Flow

```
TradeSignal emitted by StrategyEngine
    │
    ├─ Qt signal: strategy_signal_ready(signal)
    │
    ├─ ExecutionPanel receives signal
    │   ├─ Adds row: symbol, condition status "Ready"
    │   ├─ Auto-fills recommended qty from RiskManager.calculate_position_size()
    │   └─ User-override QSpinBox defaults to recommended
    │
    ├─ User clicks "Execute Entry"
    │   ├─ If confirmation enabled → show QMessageBox
    │   ├─ Read qty from QSpinBox (override or recommended)
    │   └─ Call ExecutionRouter.route_signal(user_id, signal, quantity_override=qty)
    │
    └─ Result displayed: order_id or rejection reason
```

### Circuit Breaker UI State

```python
def on_circuit_breaker(self, active: bool):
    for row in self._entry_rows:
        row.execute_button.setEnabled(not active)
    self._cb_banner.setVisible(active)
    # Exit buttons remain enabled regardless
```

---

## DD-GUI-007.001.D01 — Log Viewer Panel Design

**Parent SRD:** SRD-GUI-007.001 — SRD-GUI-007.004
- **Status:** Implemented

### Logging Bridge Architecture

```
Python logging (any module)
    │
    ├─ QueueHandler → queue.Queue (thread-safe)
    │
    ├─ LogSignalEmitter(QObject) polls queue on QTimer(100ms)
    │   └─ Emits: new_log_entry(LogRecord)
    │
    └─ LogViewerPanel receives Qt signal
        ├─ Appends to QTextEdit with formatting
        ├─ Applies active filters (level, module, symbol)
        └─ If ERROR: emit status_bar_alert signal
```

### Buffer Management

```python
class LogBuffer:
    def __init__(self, max_entries: int = 10_000) -> None
    def append(self, record: LogRecord) -> None  # evicts oldest if full
    def get_filtered(self, level: str, module: str, symbol: str) -> list[LogRecord]
    def __len__(self) -> int
```

---

## DD-GUI-011.001.D01 — Candle Chart Viewer Design

**Parent SRD:** SRD-GUI-011.001 — SRD-GUI-011.004
**Status:** Implemented
**Last Updated:** 2026-04-09

### Public Interface

```python
class CandleChartPanel(QWidget):
    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None

    # Qt lifecycle (overridden)
    def showEvent(self, event) -> None   # triggers _refresh_symbol_list()
```

### Private Components

| Name | Type | Purpose |
|---|---|---|
| `_sym_combo` | `QComboBox` (editable) | Symbol selector, 120px, no-insert policy |
| `_sym_completer` | `QCompleter` | Case-insensitive contains-match autocomplete, max 12 items |
| `_tf_combo` | `QComboBox` | Timeframe selector — items: `["1d", "1w"]`, 70px |
| `_limit_spin` | `QSpinBox` | Bar-count limit, range 20–2000, default 500, step 50, 70px |
| `_load_btn` | `QPushButton` | "Load Chart" — triggers `_on_load()` |
| `_status_lbl` | `QLabel` | Right-side status message (symbol count / current chart info) |
| `_refresh_btn` | `QPushButton` | "↺ Refresh List" — triggers `_refresh_symbol_list()` |
| `_web` | `QWebEngineView` | Full-stretch chart rendering area |
| `_current_symbol` | `str` | Tracks last successfully loaded symbol (empty = no chart loaded yet) |
| `_current_tf` | `str` | Tracks last loaded timeframe |

### AppService Methods Used

| Method | Signature | Notes |
|---|---|---|
| `get_candle_symbols` | `() -> list[str]` | `SELECT DISTINCT symbol FROM price_1d ORDER BY symbol`; returns `[]` if DB missing |
| `get_candles_for_symbol` | `(symbol: str, timeframe: str, limit: int) -> list[dict]` | Queries `price_1d` or `price_1w`; each row: `{time, open, high, low, close, volume}` where `time` is a Unix timestamp (seconds) |

### HTML Page Architecture (`_build_html`)

```
_build_html(candle_data, volume_data, symbol, timeframe) -> str
    │
    ├── Inline JS: lightweight-charts.standalone.production.js (bundle)
    │   └── Fallback: unpkg.com CDN when bundle missing
    │
    ├── Layout (flex column, 100vh, overflow hidden):
    │   ├── #header   (6px 12px padding, C.SURFACE background)
    │   │   ├── <span>  "{symbol} — {TF}"  (bold, 13px)
    │   │   └── #bar-info  "Hover over a candle to see OHLCV" / OHLCV values
    │   ├── #chart-container  (flex:1, min-height:0)
    │   │   └── LightweightCharts.createChart()  → CandlestickSeries
    │   ├── #volume-container  (height:80px)
    │   │   └── LightweightCharts.createChart()  → HistogramSeries
    │   └── #no-data  (display:none; shown when candleData.length === 0)
    │
    └── Inline script (IIFE):
        ├── Early return → show #no-data if candleData empty
        ├── Candle chart: upColor=#26a69a, downColor=#ef5350; crosshair Normal mode
        ├── Volume chart: handleScroll/handleScale=false; timeScale.visible=false
        ├── Time-scale sync: subscribeVisibleLogicalRangeChange (bidirectional)
        ├── Crosshair tooltip: subscribeCrosshairMove → #bar-info innerHTML
        ├── fitContent() called on both charts after data load
        └── ResizeObserver: applyOptions({width, height}) on both charts on resize
```

### Volume Bar Colour Logic

```python
# In _load_chart() — volume_data list construction:
color = "#26a69a55" if candle["close"] >= candle["open"] else "#ef535055"
# Green-tinted for up-candles, red-tinted for down-candles (55 = ~33% alpha)
```

### Auto-Reload Logic

```
_tf_combo.currentIndexChanged  ──► _auto_reload_if_loaded()
_limit_spin.editingFinished    ──► _auto_reload_if_loaded()
_sym_combo.lineEdit.returnPressed ──► _on_load()

_auto_reload_if_loaded():
    if self._current_symbol:   # chart has been loaded at least once
        self._on_load()
```

### JS Bundle Path

```
gui/resources/lightweight-charts.standalone.production.js
```
Resolved at import time via `Path(__file__).parent / "resources" / "lightweight-charts.standalone.production.js"`.
Bundle is read and inlined into the HTML page so the chart works fully offline. CDN fallback (`https://unpkg.com/lightweight-charts@5.0.5/...`) activates only when the file does not exist.

---

## DD-GUI-012.001.D01 — AppService: LiveTickWorker Lifecycle & Slot Wiring

**Parent SRD:** SRD-GUI-012.001, SRD-GUI-012.003, SRD-GUI-012.004, SRD-GUI-012.005, SRD-GUI-012.006, SRD-GUI-012.007
- **Status:** Draft

### Module-Level Constants Added to app_service.py

```python
# Yahoo Finance notation → IBKR index Contract
# Tags passed to LiveTickWorker must use these Yahoo keys so _on_mktwatch_tick
# can match against self._watch[i].symbol without re-translation.
from ib_insync import Contract

_YAHOO_TO_IBKR: dict[str, Contract] = {
    "^GSPC": Contract(symbol="SPX",  secType="IND", exchange="CBOE",   currency="USD"),
    "^IXIC": Contract(symbol="COMP", secType="IND", exchange="NASDAQ", currency="USD"),
    "^DJI":  Contract(symbol="INDU", secType="IND", exchange="ECBOT",  currency="USD"),
}

def _make_stk_contract(sym: str) -> Contract:
    return Contract(symbol=sym, secType="STK", exchange="SMART", currency="USD")
```

### New AppService Instance Attributes

| Attribute | Type | Initialised | Purpose |
|---|---|---|---|
| `_tick_worker` | `LiveTickWorker \| None` | `None` in `__init__` | Holds the running worker; None when disconnected |
| `_watch_prev_close` | `dict[str, float]` | `{}` in `__init__` | Stores prev_close for Market Watch symbols; populated by one-shot yfinance fetch at connect |
| `_sp500_cache` | `frozenset[str]` | `frozenset()` in `__init__` | Cached S&P 500 symbol set; refreshed on `sp500_updated` signal |

### _on_connect_ok() Changes

```python
def _on_connect_ok(self) -> None:
    # ... existing code (account timer, live bar worker, etc.) ...

    # Fetch Market Watch prev_close once (one-shot, not on timer)
    self._fetch_mw_prev_close_once()

    # Start tick worker
    cfg = SystemConfig.load()
    self._tick_worker = LiveTickWorker(cfg.ibkr_host, cfg.ibkr_port,
                                       cfg.ibkr_tick_client_id, parent=self)
    self._tick_worker.tick_price.connect(self._on_mktwatch_tick)
    self._tick_worker.tick_price.connect(self._on_watchlist_tick)
    self._tick_worker.tick_price.connect(self._on_position_tick)
    self._tick_worker.subscription_failed.connect(self._on_tick_sub_failed)
    self._tick_worker.start()
    self._sync_tick_subscriptions()
```

`_fetch_mw_prev_close_once()` reuses `_MarketWatchWorker.run()` logic (fetch `yfinance.Ticker.fast_info` for each watch symbol) but runs it synchronously in a short-lived QThread with a `done` signal that populates `self._watch_prev_close`. This is the only remaining yfinance call for Market Watch.

### disconnect_feed() Changes

```python
def disconnect_feed(self) -> None:
    # ... existing: stop _acct_timer, _wl_timer, LiveBarWorker ...
    if self._tick_worker is not None:
        self._tick_worker.request_stop()
        self._tick_worker = None
    # Clear Market Watch LTPs → display "–"
    for item in self._watch:
        item.ltp = None
        item.change_pct = None
    self.market_watch_updated.emit()
    # Positions and watchlist retain last known prices — no clearing
```

### _sync_tick_subscriptions()

```python
def _sync_tick_subscriptions(self) -> None:
    if self._tick_worker is None:
        return
    sp500 = self._sp500_cache

    contracts: dict[str, Contract] = {}

    # 1. Market Watch (all mapped index symbols that are configured)
    for item in self._watch:
        contract = _YAHOO_TO_IBKR.get(item.symbol)
        if contract is not None:
            contracts[item.symbol] = contract

    # 2. Watchlist (S&P 500 members only)
    for sym in self._watchlist_symbols:
        if sym in sp500:
            contracts[sym] = _make_stk_contract(sym)

    # 3. Open position symbols (S&P 500 members, non-CLOSED)
    for pos in self._positions:
        if pos.symbol in sp500 and pos.state != "CLOSED":
            contracts[pos.symbol] = _make_stk_contract(pos.symbol)

    # Guard: warn if near IBKR 100-line limit
    if len(contracts) > 95:
        log.warning("[Tick] Subscription count %d near IBKR limit — "
                    "trimming position contracts", len(contracts))
        # Keep Market Watch + Watchlist; drop excess position contracts
        non_pos = {k: v for k, v in contracts.items()
                   if k in _YAHOO_TO_IBKR or k in self._watchlist_symbols}
        contracts = non_pos

    self._tick_worker.set_contracts(contracts)
```

### Tick Slot Implementations

```python
def _on_mktwatch_tick(self, tag: str, price: float) -> None:
    for item in self._watch:
        if item.symbol == tag:
            item.ltp = price
            prev = self._watch_prev_close.get(tag)
            item.change_pct = (price - prev) / prev * 100 if prev else None
            self.market_watch_updated.emit()
            return
    log.debug("[Tick] Market Watch tag not found: %s", tag)

def _on_watchlist_tick(self, tag: str, price: float) -> None:
    for item in self._watchlist:
        if item["symbol"] == tag:
            item["ltp"] = price
            prev = item.get("prev_close", 0.0)
            if prev:
                item["change"]     = price - prev
                item["change_pct"] = item["change"] / prev * 100
            self.watchlist_updated.emit()
            return

def _on_position_tick(self, tag: str, price: float) -> None:
    updated = False
    for pos in self._positions:
        if pos.symbol == tag:
            pos.current_price = price
            updated = True
    if updated:
        self.positions_updated.emit()

def _on_tick_sub_failed(self, tag: str, code: int) -> None:
    log.warning("[Tick] Subscription dropped for %s (IBKR error %d)", tag, code)
```

### Removed Code

| Removed | Reason |
|---|---|
| `_MarketWatchWorker` class | Replaced by `_on_mktwatch_tick` + one-shot prev_close fetch |
| `self._watch_timer` QTimer + `_refresh_market_watch()` + `_on_watch_data()` | Replaced by streaming tick |
| `self._mw_worker` reference | No longer needed |

### _WatchlistQuoteWorker Changes

The QTimer (`_wl_timer`) is removed for price-column updates. The `_WatchlistQuoteWorker` continues to run **once** at watchlist-load time to populate static metadata (`day_open`, `year_high`, etc.) and `prev_close`. The per-run timer that previously refreshed prices every 30 s is deleted.

---

## DD-GUI-012.001.D02 — SystemConfig & Settings Panel: ibkr_tick_client_id

**Parent SRD:** SRD-GUI-012.001, SRD-GUI-012.007 (Settings exposure)
- **Status:** Draft

### SystemConfig Change (system_store.py)

```python
@dataclass
class SystemConfig:
    ibkr_host:              str  = "127.0.0.1"
    ibkr_port:              int  = 7497
    ibkr_system_client_id:  int  = 10
    ibkr_enabled:           bool = False
    ibkr_intraday_client_id: int = 12
    ibkr_live_client_id:    int  = 13
    ibkr_tick_client_id:    int  = 14    # NEW — LiveTickWorker clientId
```

Persisted to the same JSON config as existing fields. No migration needed — `dataclasses.field(default=14)` handles missing key on first load.

### Settings Panel System Tab

The System tab already exposes `ibkr_system_client_id`, `ibkr_intraday_client_id`, and `ibkr_live_client_id` as `QSpinBox` widgets. Add a fourth row in the same pattern:

| Label | Widget | Range | Default |
|---|---|---|---|
| "Tick Data Client ID" | `QSpinBox` | 1–999 | 14 |

The spinbox is bound to `SystemConfig.ibkr_tick_client_id`. Changes take effect on the next IBKR reconnect (existing behaviour for all connection params). No immediate restart of `LiveTickWorker` on change — consistent with how other clientId fields behave.

---

## DD-GUI-013.001.D01 — Dialog Shell, Navigation & Validation Flow

**Parent SRD:** SRD-GUI-013.001
**Status:** Approved

### Class Hierarchy

```python
class StrategyBuilderDialog(QDialog):
    saved = pyqtSignal(StrategyConfig)        # emitted on successful Save

    def __init__(self, registry: list[StrategyConfig], editing: StrategyConfig | None,
                 parent: QWidget | None = None) -> None: ...

    def _on_save(self) -> None: ...           # collects every page, validates, emits saved
    def _on_cancel(self) -> None: ...         # discards, calls reject()

class _NavTree(QTreeWidget): ...              # 5 nav items, fixed width 160 px
class _PageStack(QStackedWidget): ...
class _TitleBar(QWidget): ...                 # close-only, drag-to-move
```

Pages are private widgets instantiated once in `__init__`: `_StrategyInfoPage`, `_TriggersPage`, `_SchedulerPage`, `_SettingsPage`, `_RiskPage` (already exist in the working prototype — no rewrite).

### Page Index Constants

```python
_PAGE_STRATEGY_INFO = 0
_PAGE_TRIGGER       = 1
_PAGE_SCHEDULER     = 2
_PAGE_EXECUTION     = 3
_PAGE_RISK          = 4
```

### Save Pipeline

```
_on_save():
    cfg = _collect()                        # gather values from every page
    err = _validate(cfg, registry, editing)
    if err is not None:
        _show_inline_error(err)             # red label below nav tree
        return
    self.saved.emit(cfg)
    self.accept()
```

`_validate` runs in order: name non-empty → name uniqueness (case-insensitive vs `registry`, excluding `editing.name` when editing) → schedule sanity (`end_time > start_time`, `end_date >= start_date`). First failure short-circuits.

### Dimensions

| Element | Value |
|---|---|
| Dialog min size | `820 × 560` |
| Dialog default size | `880 × 600` |
| Nav-tree width | `160 px` (fixed) |
| Save / Cancel button height | `C.BTN_H` |

---

## DD-GUI-013.002.D01 — StrategyConfig Schema

**Parent SRD:** SRD-GUI-013.002
**Status:** Approved

### Dataclass

```python
@dataclass
class StrategyConfig:
    name:               str
    mode:               str                      # 'disabled' | 'manual' | 'auto'
    capital_max:        int                      # 5..100, step 5
    start_time:         str                      # 'HH:MM'
    end_time:           str                      # 'HH:MM'
    start_date:         str                      # 'YYYY-MM-DD'
    end_date:           str                      # 'YYYY-MM-DD'
    days:               list[str]                # subset of Mon..Fri
    entry_condition:    str                      # compiled expression
    exit_condition:     str                      # compiled expression
    strategy_type:      str = ''                 # legacy preset id; '' for custom
    symbol_mode:        str = 'all'              # 'all' | 'include_only' | 'exclude_these'
    symbols_include:    list[str] = field(default_factory=list)
    symbols_exclude:    list[str] = field(default_factory=list)
    target_enabled:     bool   = False
    target_type:        str    = 'fixed'         # 'fixed' | 'trailing'
    target_value:       float  = 2.0             # percent
    stoploss_enabled:   bool   = False
    stoploss_type:      str    = 'fixed'
    stoploss_value:     float  = 1.0
    auto_trade:         bool   = False
    trade_type:         str    = 'Intraday'      # 'Intraday' | 'Positional'
    strategy_signal:    dict   = field(default_factory=_default_signal)


def _default_signal() -> dict:
    return {
        'Status':                'Inactive',
        'Execution_Time':        'None',
        'Executed_Quantity':     0,
        'Pending_Quantity':      0,
        'Order_Entry_Status':    'None',
        'Order_Entry_Timestamp': None,
        'Order_Exit_Status':     'None',
        'Order_Exit_Timestamp':  None,
    }
```

### Serialization Contract

Save: `json.dumps([asdict(c) for c in configs], indent=2)`.
Load: filter incoming dict keys by `{f.name for f in fields(StrategyConfig)}` before constructing — drops legacy / unknown keys silently.

No `schema_version` field on this dataclass for now; future schema changes will be additive (new field with default) which the key-filter pattern handles cleanly. A breaking change introduces `schema_version` at that time.

---

## DD-GUI-013.007.D01 — Trigger Builder State Machine & Expression Grammar

**Parent SRD:** SRD-GUI-013.007 — SRD-GUI-013.009
**Status:** Approved

### Chain State Machine

`_TriggersPage` holds two slots `_cond1_fn` and `_cond2_fn` (initially `""`). The visible chain is regenerated by `_rebuild_chain()` after every state mutation. The implicit state is `(bool(_cond1_fn), bool(_cond2_fn))`:

| State | Visible chain (left → right) |
|---|---|
| `(False, False)` | `[+ Add Condition 1]` |
| `(True, False)` | `[bubble: cond1] [relop ▾] [+ Add Condition 2]` |
| `(True, True)` | `[bubble: cond1] [relop ▾] [bubble: cond2] [logop ▾]` |

Compile is only enabled in `(True, True)`. Clearing cond1 also clears cond2 (cascading reset). Clearing cond2 keeps cond1.

### Compile Algorithm

```
on_compile():
    clause = f"({_cond1_fn}) {relop.text} ({_cond2_fn})"
    logop  = {'&': 'AND', '||': 'OR'}[logop_combo.text]
    if buffer.is_empty:
        buffer.set(clause)
    else:
        buffer.set(f"{buffer.text} {logop} {clause}")
    _cond1_fn = ""
    _cond2_fn = ""
    _rebuild_chain()                       # state returns to (False, False)
```

### Assign Algorithm

```
on_entry():
    if buffer.is_empty:
        show_inline_error("Compile a condition first.")
        return
    entry_condition = buffer.text
    buffer.clear()

on_exit():       # symmetric, writes exit_condition
```

### Expression Grammar (EBNF)

This grammar is the contract consumed by FO-EXE-011's `ConditionEvaluator`:

```
expression   ::= or_expr
or_expr      ::= and_expr ( 'OR'  and_expr )*
and_expr     ::= comparison ( 'AND' comparison )*
comparison   ::= term ( ('>' | '<' | '>=' | '<=' | '==' | '!=') term )?
term         ::= NUMBER | STRING | function_call | '(' expression ')'
function_call ::= INDICATOR_NAME '(' arg_list ')'
arg_list     ::= arg ( ',' arg )*
arg          ::= NUMBER | STRING
INDICATOR_NAME ::= one of the 15 catalogue names
STRING       ::= "'" [^']* "'"
NUMBER       ::= -? digit+ ('.' digit+)?
```

### Condition Selector Output

`_ConditionSelectorDialog._on_add()` builds the function-call string:

```python
parts = []
for pname, w in self._inputs.items():
    if isinstance(w, QLineEdit):
        parts.append(w.text().strip())         # bare numeric
    elif isinstance(w, QComboBox):
        parts.append(f"'{w.currentText()}'")   # single-quoted string
fn = f"{indicator.name}({', '.join(parts)})"
```

Empty `QLineEdit` blocks Add with an inline error before emission.

---

## DD-GUI-013.013.D01 — Persistence I/O

**Parent SRD:** SRD-GUI-013.013 — SRD-GUI-013.014
**Status:** Approved

### Path

```python
_STRATEGIES_PATH: Path = Path.home() / ".usswing" / "strategies.json"
```

### Load

```python
def load_strategies() -> list[StrategyConfig]:
    if not _STRATEGIES_PATH.exists():
        return []
    try:
        raw = json.loads(_STRATEGIES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []                              # silent recovery — corrupt file = empty list
    valid_keys = {f.name for f in fields(StrategyConfig)}
    out: list[StrategyConfig] = []
    for r in raw:
        cfg = StrategyConfig(**{k: v for k, v in r.items() if k in valid_keys})
        cfg.strategy_signal['Status'] = 'Inactive'
        cfg.strategy_signal['Running_Symbols'] = []
        out.append(cfg)
    return out
```

### Save (atomic)

```python
def save_strategies(configs: list[StrategyConfig]) -> None:
    _STRATEGIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STRATEGIES_PATH.with_suffix('.tmp')
    tmp.write_text(
        json.dumps([asdict(c) for c in configs], indent=2),
        encoding='utf-8',
    )
    tmp.replace(_STRATEGIES_PATH)              # atomic on Win/macOS/Linux
```

### Overwrite / Append by Name

`save_strategies()` writes the entire list verbatim — there is no per-record write API. `StrategyBuilderDialog._on_save()` therefore performs the overwrite/append decision in memory before calling `save_strategies()`:

```python
def commit(self, registry: list[StrategyConfig], cfg: StrategyConfig) -> list[StrategyConfig]:
    for i, existing in enumerate(registry):
        if existing.name.casefold() == cfg.name.casefold():
            registry[i] = cfg                  # overwrite
            return registry
    registry.append(cfg)                       # append
    return registry
```

The same `commit()` helper is reused by the FO-EXE-011 engine when it writes back `strategy_signal` runtime state, so save semantics stay consistent across writers.

---

## DD-GUI-014.002.D01 — `_ActiveCyclesModel` View-Model

**Parent SRD:** SRD-GUI-014.001 — SRD-GUI-014.004, SRD-GUI-014.011
**Status:** Approved

### Row DTO

The model holds a list of `_Row` instances — a unified representation that handles both PENDING (from `PendingSignalStore`) and live cycles (from `TradeCycleQuery`).

```python
@dataclass
class _Row:
    kind:         str               # 'pending' | 'cycle'
    key:          str               # signal_id (pending) | f"cycle:{cycle_id}" (cycle)
    state:        str               # 'PENDING' | 'OPENING' | 'OPEN' | 'CLOSING'
    time:         str               # signal-emit time or entry_time, formatted "HH:MM:SS"
    symbol:       str
    strategy:     str
    qty:          int
    entry_price:  float | None      # est. for pending; actual for cycle
    ltp:          float | None
    pnl_usd:      float | None
    pnl_pct:      float | None
    hard_stop:    float | None
    target:       float | None
    trail:        float | None
    user_id:      int
    # raw payloads kept for callbacks
    signal:       TradeSignal | None = None       # only for pending rows
    cycle_id:     int | None = None               # only for cycle rows
```

### Column Layout

```python
class Col(IntEnum):
    USER       = 0       # only visible in All-Users scope
    STATE      = 1
    TIME       = 2
    SYMBOL     = 3
    STRATEGY   = 4
    QTY        = 5
    ENTRY      = 6
    LTP        = 7
    PNL_USD    = 8
    PNL_PCT    = 9
    HARD_STOP  = 10
    TARGET     = 11
    TRAIL      = 12
    ACTIONS    = 13
```

The User column is hidden via `QTableView.setColumnHidden(Col.USER, True)` when scope is single-user; this avoids reshaping the model on scope change. `headerData()` returns "User" for `Col.USER` regardless of visibility.

### Public API

```python
class _ActiveCyclesModel(QAbstractTableModel):
    def __init__(self, query: TradeCycleQuery,
                 pending_store: PendingSignalStore,
                 parent: QObject | None = None) -> None: ...

    # Bulk
    def refresh(self) -> None: ...                 # re-queries open_cycles + pending; full reset

    # Incremental — called from event slots
    def on_pending_added(self, signal: TradeSignal) -> None: ...
    def on_pending_removed(self, signal_id: str) -> None: ...
    def on_cycle_opened(self, snap: CycleSnapshot) -> None: ...
    def on_cycle_updated(self, snap: CycleSnapshot) -> None: ...
    def on_cycle_state(self, snap: CycleSnapshot) -> None: ...   # CycleClosing / RiskUpdated
    def on_cycle_closed(self, snap: CycleSnapshot) -> None: ...
    def on_cycle_aborted(self, snap: CycleSnapshot) -> None: ...

    # Scope
    def set_scope(self, user_id: int | None) -> None: ...        # filters rows in place
```

### Index Map

```python
self._by_key: dict[str, int] = {}                  # row key → row index
```

Maintained by every incremental method. All mutations go through three private helpers:

```python
def _insert_row(self, row: _Row) -> None: ...          # beginInsertRows / endInsertRows
def _update_row(self, key: str, row: _Row) -> None: ... # emits dataChanged on changed columns only
def _remove_row(self, key: str) -> None: ...           # beginRemoveRows / endRemoveRows
```

### Incremental Update Path

```python
def on_cycle_updated(self, snap: CycleSnapshot) -> None:
    key = f"cycle:{snap.cycle_id}"
    idx = self._by_key.get(key)
    if idx is None:
        return                                         # cycle was closed/aborted before this tick arrived
    row = self._rows[idx]
    changed_cols: list[int] = []
    if row.ltp != snap.current_price:
        row.ltp = snap.current_price; changed_cols.append(Col.LTP)
    if row.pnl_usd != snap.current_pnl_usd:
        row.pnl_usd = snap.current_pnl_usd; changed_cols.append(Col.PNL_USD)
    if row.pnl_pct != snap.current_pnl_pct:
        row.pnl_pct = snap.current_pnl_pct; changed_cols.append(Col.PNL_PCT)
    if row.trail != snap.trailing_stop_level:
        row.trail = snap.trailing_stop_level; changed_cols.append(Col.TRAIL)
    if not changed_cols:
        return
    left  = self.index(idx, min(changed_cols))
    right = self.index(idx, max(changed_cols))
    self.dataChanged.emit(left, right)
```

Emits a single `dataChanged` covering only the contiguous changed-column range to minimise repaint cost during high-frequency ticks.

### Cell Formatting

| Column | `Qt.DisplayRole` format | `Qt.BackgroundRole` | `Qt.ForegroundRole` |
|---|---|---|---|
| `STATE` | badge text (PENDING / OPENING / …) | `C.AMBER` / `C.BLUE` / `C.GREEN` / `C.ORANGE` (tinted) | `C.BG` |
| `LTP` / `ENTRY` / `HARD_STOP` / `TARGET` / `TRAIL` | `"$%.2f"` (or "—" when None) | — | — |
| `PNL_USD` | `"+$%.2f"` / `"-$%.2f"` | green/red tint | `C.GREEN` / `C.RED` |
| `PNL_PCT` | `"+%.2f%%"` / `"-%.2f%%"` | — | `C.GREEN` / `C.RED` |
| `ACTIONS` | empty (delegate paints) | — | — |

`Qt.UserRole` returns the `_Row` (used by the delegate). `Qt.UserRole+1` returns the row's `state` for fast lookups during paint.

### Thread Bridging

Service events arrive on the event-bus worker thread. The panel installs Qt cross-thread relay slots on construction:

```python
self._bridge_signal = pyqtSignal(object)                 # any TradeCycleEvent
bus.subscribe(lambda evt: self._bridge_signal.emit(evt))
self._bridge_signal.connect(self._dispatch_event, Qt.QueuedConnection)
```

`_dispatch_event` runs on the GUI thread and routes by event type to the model's `on_*` methods. The model itself touches no thread primitives — Qt's queued connection guarantees GUI-thread delivery.

---

## DD-GUI-014.002.D02 — `_RowActionsDelegate`

**Parent SRD:** SRD-GUI-014.005, SRD-GUI-014.006, SRD-GUI-014.008, SRD-GUI-014.012
**Status:** Approved

### State → Button Set

| Row state | Visible buttons | Geometry (right-anchored, 6 px gap) |
|---|---|---|
| `PENDING` | `[Execute]` (82 px) · `[✕]` (28 px) | 28 px height, vertically centred |
| `OPENING` | indeterminate spinner (16 px) | centred |
| `OPEN` | `[Edit Risk ▼]` (96 px) · `[Close]` (68 px) | as above |
| `CLOSING` | indeterminate spinner | centred |

### Class Skeleton

```python
class _RowActionsDelegate(QStyledItemDelegate):
    execute_clicked      = pyqtSignal(str)               # signal_id
    dismiss_clicked      = pyqtSignal(str)               # signal_id
    edit_risk_clicked    = pyqtSignal(int)               # cycle_id (toggles expand)
    close_clicked        = pyqtSignal(int)               # cycle_id

    def __init__(self,
                 cb_state_provider: Callable[[], bool],   # AppService.circuit_breaker_active
                 parent: QObject | None = None) -> None: ...

    def paint(self, painter: QPainter,
              option: QStyleOptionViewItem,
              index: QModelIndex) -> None: ...
    def editorEvent(self, event, model, option, index) -> bool: ...
    def sizeHint(self, option, index) -> QSize: ...
```

### Hit-Test Geometry

The delegate stores per-row button rects in a per-paint-cycle dict:

```python
self._hit_rects: dict[QModelIndex, list[tuple[str, QRect]]] = {}
```

`paint()` computes rects from `option.rect` right-anchored layout, stores them, then draws. `editorEvent()` tests `MouseButtonRelease` against the stored rects and emits the appropriate signal.

### Paint Algorithm (pseudo-code)

```python
def paint(self, p, opt, idx):
    row    = idx.data(Qt.UserRole)
    state  = row.state
    cb_on  = self._cb_provider()                      # circuit-breaker flag

    p.save()
    p.setRenderHint(QPainter.Antialiasing)

    # Background — alternating row tint already painted by view; nothing here.
    btns: list[tuple[str, str, QColor]] = []          # (id, label, accent)

    if state == "PENDING":
        exec_disabled = cb_on
        btns.append(("execute", "Execute",
                     C.MUTED if exec_disabled else C.GREEN))
        btns.append(("dismiss", "✕", C.MUTED))
    elif state == "OPEN":
        btns.append(("edit",  "Edit Risk ▼", C.BLUE))
        btns.append(("close", "Close",       C.RED))
    elif state in ("OPENING", "CLOSING"):
        self._draw_spinner(p, opt.rect)               # tick angle from a panel-wide QTimer
        p.restore()
        return

    rects = self._layout_buttons(opt.rect, btns)
    self._hit_rects[idx] = list(zip([b[0] for b in btns], rects))
    for (bid, label, accent), rect in zip(btns, rects):
        disabled = (bid == "execute" and cb_on)
        self._draw_button(p, rect, label, accent, disabled)

    p.restore()
```

`_draw_button` paints a rounded rect (radius 4), 1-px border in the accent colour, label in either `C.TEXT` or `C.MUTED` based on `disabled`. Hover tracking is handled by the delegate's `QStyle.State_MouseOver` test on `opt.state`.

### Click Routing

```python
def editorEvent(self, event, model, option, index):
    if event.type() != QEvent.MouseButtonRelease:
        return False
    pos = event.pos()
    for bid, rect in self._hit_rects.get(index, []):
        if not rect.contains(pos):
            continue
        if bid == "execute":
            if self._cb_provider():
                return True                            # disabled — swallow click
            row = index.data(Qt.UserRole)
            self.execute_clicked.emit(row.signal.signal_id)
        elif bid == "dismiss":
            row = index.data(Qt.UserRole)
            self.dismiss_clicked.emit(row.signal.signal_id)
        elif bid == "edit":
            self.edit_risk_clicked.emit(index.data(Qt.UserRole).cycle_id)
        elif bid == "close":
            self.close_clicked.emit(index.data(Qt.UserRole).cycle_id)
        return True
    return False
```

### Tooltip on Disabled `[Execute]`

```python
def helpEvent(self, event, view, option, index):
    if event.type() == QEvent.ToolTip and self._cb_provider():
        row = index.data(Qt.UserRole)
        if row.state == "PENDING":
            QToolTip.showText(event.globalPos(),
                              "Circuit breaker active — no new entries", view)
            return True
    return super().helpEvent(event, view, option, index)
```

### Spinner

A panel-owned `QTimer` ticks every 50 ms while any OPENING / CLOSING row exists; on each tick it invalidates only the action-cells of those rows via `model.dataChanged.emit(idx, idx, [Qt.DisplayRole])`. Stops automatically when no spinning rows remain.

---

## DD-GUI-014.007.D01 — Inline Risk Editor

**Parent SRD:** SRD-GUI-014.007
**Status:** Approved

### Expand Mechanism

The panel uses `QTableView.setSpan` to merge the editor row across all visible columns. On `edit_risk_clicked(cycle_id)` from the delegate:

```python
def _on_edit_risk(self, cycle_id: int) -> None:
    if self._expanded_cycle_id == cycle_id:
        self._collapse_editor()
        return
    if self._expanded_cycle_id is not None:
        self._collapse_editor()
    self._expand_editor(cycle_id)
```

`_expand_editor(cycle_id)` inserts a synthetic row directly below the parent cycle row (via `_ActiveCyclesModel._insert_editor_row(cycle_id)`) and embeds a `_RiskEditorWidget` via `QTableView.setIndexWidget()`. Only one editor is open at a time; opening another collapses the first.

### `_RiskEditorWidget`

```python
class _RiskEditorWidget(QWidget):
    saved     = pyqtSignal(int, dict)        # cycle_id, fields-to-update
    cancelled = pyqtSignal(int)

    def __init__(self, snap: CycleSnapshot, parent: QWidget | None = None) -> None: ...

    def show_error(self, message: str) -> None: ...   # called by panel on InvariantViolation
```

Constructed from the current `CycleSnapshot` (passed in by the panel from `TradeCycleQuery.cycle(cycle_id)`).

### Layout

```
┌─ Edit Risk — AAPL (cycle 1042) ──────────────────────────────────────────────┐
│                                                                              │
│  Hard Stop   [ 179.00 ↑↓ ]      Target    [ 189.00 ↑↓ ]                     │
│  Trail Mode  [ $ ▾ ]   Trail Offset  [ 2.50 ↑↓ ]                            │
│                                                                              │
│  [ inline error label — hidden by default, red text ]                        │
│                                                                              │
│  [Save]  [Cancel]                                                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Control | Type | Range (anchored to `snap.current_price`) | Step | Decimals |
|---|---|---|---|---|
| Hard Stop | `QDoubleSpinBox` | `0.01 .. current_price` | 0.05 | 2 |
| Target | `QDoubleSpinBox` | `current_price .. 1_000_000` | 0.05 | 2 |
| Trail Mode | `QComboBox` | `$` / `%` | — | — |
| Trail Offset | `QDoubleSpinBox` | `0.01 .. 999.99` | 0.05 | 2 |

The spinbox range bounds enforce FO-EXE-012 §10 invariants locally: HSL cannot be set above current_price; target cannot be below; trail offset cannot be zero. The user gets immediate visual feedback (spinbox clamps) before Save is even pressed.

### Save Flow

```python
def _on_save(self) -> None:
    fields = self._collect_changed_fields(self._snap)        # only diff vs snapshot
    if not fields:
        self.cancelled.emit(self._snap.cycle_id)
        return
    self.saved.emit(self._snap.cycle_id, fields)
```

The panel handles `saved`:

```python
def _on_editor_saved(self, cycle_id: int, fields: dict) -> None:
    try:
        snap = self._cycle_cmd.update_risk(cycle_id, **fields)
    except InvariantViolation as e:
        self._editor.show_error(str(e))                      # keep editor open
        return
    self._collapse_editor()
    # The CycleUpdated event from update_risk drives the row repaint;
    # no manual model update needed here.
```

### Inline Error Rendering

```python
def show_error(self, message: str) -> None:
    self._err_lbl.setText(message)
    self._err_lbl.setVisible(True)
    self._err_lbl.setStyleSheet(f"color: {C.RED}; font-size: 9pt;")
    # auto-clear on next field edit
    for w in (self._hsl, self._target, self._trail_offset, self._trail_mode):
        w.valueChanged.connect(self._clear_error) if hasattr(w, "valueChanged") \
            else w.currentTextChanged.connect(self._clear_error)
```

### Collapse / Cleanup

```python
def _collapse_editor(self) -> None:
    if self._expanded_cycle_id is None:
        return
    self._model._remove_editor_row(self._expanded_cycle_id)
    self._editor.deleteLater()
    self._editor = None
    self._expanded_cycle_id = None
```

Editor row removal is synchronous so a subsequent `_expand_editor` for a different cycle never sees a stale embedded widget. `deleteLater` prevents reentrancy if Save was triggered by a keypress that is still propagating.

### Race with Cycle Closure

If a `CycleClosed` event arrives for the cycle whose editor is open:

```python
def on_cycle_closed(self, snap: CycleSnapshot) -> None:
    self._model.on_cycle_closed(snap)
    if snap.cycle_id == self._expanded_cycle_id:
        self._collapse_editor()                              # silently dismiss editor
```

No confirmation is shown — the cycle's already gone; the editor was about to fail anyway. The panel logs DEBUG `[Panel] editor auto-dismissed for closed cycle {id}`.
