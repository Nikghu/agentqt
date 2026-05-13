# Design Document — GUI Module (GUI)

**Document ID:** DD-GUI
**Version:** 1.4.0
**Traces To:** SRD-GUI v2.6.0
**Status:** Draft
**Last Updated:** 2026-05-13
**Project:** US Swing Trading System

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

## DD-GUI-012.001.D01 — IBKRSession Module & Threading Topology

**Parent SRD:** SRD-GUI-012.001 — SRD-GUI-012.002
- **Status:** Draft
**Last Updated:** 2026-05-13

### Threading Model

```
┌─────────────────────────────────────────────────────────────┐
│  Qt Main Thread                                             │
│   AppService (QObject)                                      │
│     ├─ _ibkr_session: IBKRSession   (QObject, parent=self)  │
│     ├─ _on_session_account_ready()       slot               │
│     ├─ _on_session_quotes_updated()      slot               │
│     ├─ _on_session_connection_lost()     slot               │
│     └─ _on_session_connection_restored() slot               │
│   _MarketWatchYfinanceWorker (QThread, fallback only)       │
└──────────────────────────┬──────────────────────────────────┘
                           │  pyqtSignal.emit() — Qt queued
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  IBKRSession.<session_thread>  (QThread)                    │
│   asyncio event loop (created in _thread_main)              │
│     ├─ ib_insync.IB              (all ib.* calls live here) │
│     ├─ _debounce_account_task: asyncio.Task                 │
│     ├─ _coalesce_quotes_task:  asyncio.Task                 │
│     └─ _reconnect_task:        asyncio.Task | None          │
└─────────────────────────────────────────────────────────────┘
```

`IBKRSession` is a `QObject` owned by the Qt main thread; its asynchronous work executes on a dedicated `QThread`. `ib_insync` event callbacks fire on the asyncio loop inside that thread. Callbacks call `self.<signal>.emit(...)`. Because all signal/slot connections between `IBKRSession` and `AppService` are made on the Qt main thread with `Qt.ConnectionType.AutoConnection`, Qt routes every emission as a queued event to the main thread.

Only plain Python value types (`AccountState`, `OpenPosition`, `list[dict]`, `str`) cross the thread boundary via signals — no widget or `_ibkr_acct`-like main-thread object is ever touched inside the asyncio loop.

### Cross-thread call surfaces

| Direction | Mechanism |
|---|---|
| Qt → asyncio (start, stop, set_market_watch_symbols, set_watchlist_symbols) | `asyncio.run_coroutine_threadsafe(coro, self._loop)` — future discarded; errors logged inside the coroutine |
| asyncio → Qt (account_ready, quotes_updated, connection_lost, connection_restored) | `pyqtSignal.emit()` — Qt auto-queues to main-thread slots |

### Class skeleton

```python
"""
Module: MD-GUI-012.001.M01 — IBKRSession
Parent SRD: SRD-GUI-012.001
"""
from __future__ import annotations
import asyncio
import logging
from PyQt6.QtCore import QObject, QThread, pyqtSignal

_log = logging.getLogger(__name__)


class IBKRSession(QObject):
    # Public signals
    account_ready       = pyqtSignal(object, list)   # (AccountState, list[OpenPosition])
    quotes_updated      = pyqtSignal(list)           # list[dict]
    connection_lost     = pyqtSignal(str)
    connection_restored = pyqtSignal()

    def start(self, host: str, port: int, client_id: int) -> None: ...
    def stop(self) -> None: ...
    def set_market_watch_symbols(self, symbols: list[str]) -> None: ...
    def set_watchlist_symbols(self, symbols: list[str]) -> None: ...

    def _thread_main(self) -> None: ...                      # QThread.started
    async def _connect_and_subscribe(self) -> None: ...
    async def _apply_symbol_delta(self,
                                  new_mw: set[str] | None = None,
                                  new_wl: set[str] | None = None) -> None: ...
    async def _debounce_account(self) -> None: ...
    async def _coalesce_quotes(self) -> None: ...
    async def _reconnect_loop(self) -> None: ...
    async def _shutdown(self) -> None: ...
```

### start / stop lifecycle

`start(host, port, client_id)` is idempotent: returns immediately when `self._session_thread is not None`. Otherwise it creates `QThread()`, connects `started` to `_thread_main`, and calls `self._session_thread.start()`. `_thread_main` creates `self._loop = asyncio.new_event_loop()`, sets it as current, runs `_connect_and_subscribe()` to completion, then `self._loop.run_forever()` until `_shutdown` calls `loop.stop()`.

`stop()` sets `self._stopping = True`, schedules `_shutdown` via `run_coroutine_threadsafe`, then `self._session_thread.wait(3000)`. If the thread is still alive after 3 s, it is `terminate()`-ed and a WARNING is logged. `_shutdown` cancels `_debounce_account_task`, `_coalesce_quotes_task`, and `_reconnect_task` (gathered with `return_exceptions=True`), calls `self._ib.disconnect()`, and finally `self._loop.stop()`.

---

## DD-GUI-012.001.D02 — Subscription & Coalescing

**Parent SRD:** SRD-GUI-012.004 — SRD-GUI-012.006
- **Status:** Draft
**Last Updated:** 2026-05-13

### Account subscription

`_connect_and_subscribe` calls:

```python
self._ib.reqAccountUpdates(True, "")
self._ib.accountValueEvent     += self._on_account_event
self._ib.updatePortfolioEvent  += self._on_account_event
self._ib.accountSummaryEvent   += self._on_account_event
```

Each handler schedules `_debounce_account()` if no task is already pending:

```python
async def _on_account_event(self, *args: object) -> None:
    if self._debounce_account_task and not self._debounce_account_task.done():
        return
    self._debounce_account_task = asyncio.create_task(self._debounce_account())

async def _debounce_account(self) -> None:
    await asyncio.sleep(0.05)   # 50 ms debounce
    acct, positions = self._build_account_snapshot()
    self.account_ready.emit(acct, positions)
```

`_build_account_snapshot` mirrors the field extraction already present in the (to-be-deleted) `_AccountDataWorker._async_run` — same `tag_vals` flatten, same `OpenPosition` construction from `ib.portfolio()`.

### Market-data subscription

For every symbol in `self._mw_symbols ∪ self._wl_symbols` that does **not** start with `^`:

```python
contract = Stock(sym, "SMART", "USD")
ticker   = self._ib.reqMktData(contract, "", False, False)
self._tickers[sym] = ticker
```

The handler:

```python
self._ib.pendingTickersEvent += self._on_pending_tickers

async def _on_pending_tickers(self, _tickers: object) -> None:
    if self._coalesce_quotes_task and not self._coalesce_quotes_task.done():
        return
    self._coalesce_quotes_task = asyncio.create_task(self._coalesce_quotes())

async def _coalesce_quotes(self) -> None:
    await asyncio.sleep(0.25)   # 250 ms tick coalescing
    rows: list[dict] = []
    for sym, t in self._tickers.items():
        ltp = _last_or_close(t)
        rows.append({"symbol": sym, "ltp": ltp, "change_pct": _change_pct(t),
                     "previous_close": t.close, "source": "ibkr"})
    self.quotes_updated.emit(rows)
```

### Symbol-set mutation

```python
def set_market_watch_symbols(self, symbols: list[str]) -> None:
    asyncio.run_coroutine_threadsafe(
        self._apply_symbol_delta(new_mw=set(symbols)), self._loop)

async def _apply_symbol_delta(
    self,
    new_mw: set[str] | None = None,
    new_wl: set[str] | None = None,
) -> None:
    if new_mw is not None:
        self._mw_symbols = new_mw
    if new_wl is not None:
        self._wl_symbols = new_wl

    union_new = {s for s in (self._mw_symbols | self._wl_symbols)
                 if not s.startswith("^")}
    union_old = set(self._tickers.keys())

    for sym in union_old - union_new:
        self._ib.cancelMktData(self._tickers[sym].contract)
        del self._tickers[sym]
    for sym in union_new - union_old:
        contract = Stock(sym, "SMART", "USD")
        self._tickers[sym] = self._ib.reqMktData(contract, "", False, False)
```

The `^`-prefix filter lives **inside** `_apply_symbol_delta` so no upstream caller can leak index symbols through to `reqMktData`.

---

## DD-GUI-012.001.D03 — Reconnect State Machine

**Parent SRD:** SRD-GUI-012.007
- **Status:** Draft
**Last Updated:** 2026-05-13

### States and transitions

```
states: IDLE → CONNECTING → ACTIVE
                              │
                              ▼  (ib.disconnectedEvent while not _stopping)
                         RECONNECTING ──── 10 consecutive fails ──► FAILED
                              │
                              ▼  (connectAsync ok + resubscribe)
                            ACTIVE
```

| State | Entry trigger | Exit action |
|---|---|---|
| IDLE | Constructor | `start()` advances to CONNECTING |
| CONNECTING | `start()` | On success → ACTIVE; on failure → RECONNECTING |
| ACTIVE | First `_connect_and_subscribe()` completes | Steady-state; no transition unless disconnect |
| RECONNECTING | `ib.disconnectedEvent` | `connection_lost.emit(reason)`; spawn `_reconnect_loop` |
| FAILED | 10 failed reconnects | `connection_lost.emit("Max reconnect attempts reached")`; `_loop.stop()` |

### Reconnect loop

```python
async def _reconnect_loop(self) -> None:
    import random
    BASE, MAX_DELAY, MAX_ATTEMPTS = 2.0, 30.0, 10
    self._reconnect_attempt = 0
    while not self._stopping and self._reconnect_attempt < MAX_ATTEMPTS:
        delay = min(BASE * (2 ** self._reconnect_attempt), MAX_DELAY)
        delay *= random.uniform(0.8, 1.2)
        await asyncio.sleep(delay)
        self._reconnect_attempt += 1
        try:
            await self._ib.connectAsync(self._host, self._port,
                                        clientId=self._client_id, timeout=5)
            await self._connect_and_subscribe()
            self._reconnect_attempt = 0
            self.connection_restored.emit()
            return
        except Exception as exc:
            _log.warning("[Feed] Reconnect attempt %d failed: %s",
                         self._reconnect_attempt, exc)
    if not self._stopping:
        self.connection_lost.emit("Max reconnect attempts reached")
        self._stopping = True
        self._loop.stop()
```

Backoff timing lives inside the asyncio task; no `QTimer` is involved. AppService bridges the signals to `feed_status_changed`:

- `connection_lost(reason)` → `_set_status(RECONNECTING)` + log
- `connection_restored()` → `_set_status(CONNECTED)` + log
- Final `connection_lost("Max reconnect …")` → `_set_status(DISCONNECTED)` + release `_ibkr_session` reference + start yfinance fallback timer

No new `ConnectionStatus` enum values are added; existing `CONNECTED`, `RECONNECTING`, `DISCONNECTED` cover the full surface.

---

## DD-GUI-012.001.D04 — AppService Bridge & Field Deltas

**Parent SRD:** SRD-GUI-012.003, SRD-GUI-012.008, SRD-GUI-012.009, SRD-GUI-012.011, SRD-GUI-012.012
- **Status:** Draft
**Last Updated:** 2026-05-13

### Bridge slots (added)

```python
def _on_session_account_ready(
    self, acct: AccountState, positions: list[OpenPosition]
) -> None:
    if self._ibkr_session is None:
        return                                          # late-arriving emit
    self._ibkr_acct      = acct
    self._ibkr_positions = list(positions)
    self.account_updated.emit()
    self.positions_updated.emit()

def _on_session_quotes_updated(self, rows: list[dict]) -> None:
    if self._ibkr_session is None:
        return
    by_sym = {r["symbol"]: r for r in rows}
    # Update Market Watch
    for item in self._watch:
        r = by_sym.get(item.symbol)
        if r is not None:
            item.ltp = r["ltp"]; item.change_pct = r["change_pct"]
    # Update Watchlist
    for item in self._watchlist:
        r = by_sym.get(item.symbol)
        if r is not None:
            self._wl_quotes[item.symbol] = r
    # Index carve-out — any ^-prefixed symbol missing from IBKR rows
    missing = [it.symbol for it in self._watch
               if it.symbol.startswith("^") and it.symbol not in by_sym]
    if missing:
        self._spawn_yfinance_for(missing)
    self.market_watch_updated.emit()
    self.watchlist_updated.emit()

def _on_session_connection_lost(self, reason: str) -> None:
    self._set_status(ConnectionStatus.RECONNECTING)
    self.log_message.emit("WARNING", f"[Feed] Connection lost — {reason}; reconnecting")

def _on_session_connection_restored(self) -> None:
    self._set_status(ConnectionStatus.CONNECTED)
    self.log_message.emit("INFO", "[Feed] Connection restored")
```

The first line of `_on_session_account_ready` and `_on_session_quotes_updated` guards against late-arriving emissions queued by Qt before `disconnect_feed` finishes detaching slots.

### connect_feed → session.start wiring

`_on_connect_ok` body, post-refactor:

```python
self._set_status(ConnectionStatus.CONNECTED)
self.log_message.emit("INFO", f"[Feed] Connected to IBKR at {host}:{port}")
self._ibkr_session = IBKRSession(parent=self)
self._ibkr_session.account_ready.connect(self._on_session_account_ready)
self._ibkr_session.quotes_updated.connect(self._on_session_quotes_updated)
self._ibkr_session.connection_lost.connect(self._on_session_connection_lost)
self._ibkr_session.connection_restored.connect(self._on_session_connection_restored)
self._ibkr_session.start(
    self._system_cfg.ibkr_host,
    self._system_cfg.ibkr_port,
    self._system_cfg.ibkr_system_client_id,
)
self._ibkr_session.set_market_watch_symbols([it.symbol for it in self._watch])
if self._watchlist:
    self._ibkr_session.set_watchlist_symbols([it.symbol for it in self._watchlist])
```

`disconnect_feed` body:

```python
if self._ibkr_session is not None:
    self._ibkr_session.account_ready.disconnect(self._on_session_account_ready)
    self._ibkr_session.quotes_updated.disconnect(self._on_session_quotes_updated)
    self._ibkr_session.connection_lost.disconnect(self._on_session_connection_lost)
    self._ibkr_session.connection_restored.disconnect(self._on_session_connection_restored)
    self._ibkr_session.stop()
    self._ibkr_session = None
self._ibkr_acct      = None
self._ibkr_positions = []
self._set_status(ConnectionStatus.DISCONNECTED)
self.account_updated.emit()
self.positions_updated.emit()
self._yf_fallback_timer.start()
```

### Field deltas in `AppService`

| Action | Field | Type | Reason |
|---|---|---|---|
| DELETE | `_acct_worker` | `_AccountDataWorker \| None` | Worker class deleted |
| DELETE | `_acct_timer` | `QTimer` | Replaced by push |
| DELETE | `_mw_worker` | `_MarketWatchWorker \| None` | Worker class deleted |
| DELETE | `_watch_timer` | `QTimer` | Replaced by push |
| DELETE | `_wl_worker` | `_WatchlistQuoteWorker \| None` | Worker class deleted |
| DELETE | `_wl_timer` | `QTimer` | Replaced by push |
| DELETE | `_mw_log_on_next_fetch` | `bool` | Tied to deleted timer |
| ADD | `_ibkr_session` | `IBKRSession \| None` | Session reference |
| ADD | `_yf_fallback_timer` | `QTimer` | 30 s tick when DISCONNECTED |
| ADD | `_yf_worker` | `_MarketWatchYfinanceWorker \| None` | Fallback worker |
| KEEP | `_ibkr_acct`, `_ibkr_positions`, `_watch`, `_watchlist`, `_wl_quotes`, `_connection_status`, `_was_feed_connected` | — | Unchanged contract |

`set_market_watch_symbols()` and `set_watchlist()` in `AppService` gain one line each at end:

```python
if self._ibkr_session is not None:
    self._ibkr_session.set_market_watch_symbols([it.symbol for it in self._watch])
```

### ClientId allocation (SRD-GUI-012.011)

- **Persistent session:** `system_cfg.ibkr_system_client_id`
- **Candle download (unchanged):** `system_cfg.ibkr_intraday_client_id`
- **Live-bar worker (unchanged):** `system_cfg.ibkr_live_client_id`
- **Removed from `SystemConfig` dataclass:** `ibkr_mw_client_id`, `ibkr_wl_client_id`. JSON-load layer ignores extra keys, so existing `system_config.json` files load without error.

---

## DD-GUI-012.001.D05 — yfinance Fallback & Build Order

**Parent SRD:** SRD-GUI-012.009, SRD-GUI-012.010, SRD-GUI-012.012
- **Status:** Draft
**Last Updated:** 2026-05-13

### `_MarketWatchYfinanceWorker(QThread)`

Replaces both deleted workers with a single class. Accepts a combined `symbols: list[str]` and emits `done = pyqtSignal(list)` whose payload schema matches the IBKR `quotes_updated` row dict (`symbol`, `ltp`, `change_pct`, `previous_close`, plus the existing `year_high`, `year_low`, `market_cap` from `yfinance.fast_info` for watchlist consumers).

```python
class _MarketWatchYfinanceWorker(QThread):
    done = pyqtSignal(list)
    def __init__(self, symbols: list[str]) -> None: ...
    def run(self) -> None: ...
```

### Triggering & stopping

| Condition | Action |
|---|---|
| `_set_status(DISCONNECTED)` | Start `_yf_fallback_timer` (30 s); immediate first fetch |
| `_set_status(CONNECTED)` | Stop `_yf_fallback_timer`; disconnect `_yf_worker.done` if still running |
| Index-symbol carve-out | One-shot `_MarketWatchYfinanceWorker(missing_symbols)` regardless of state |

The 30 s interval supersedes the prior 10 s and 15 s timers — offline path is intentionally less aggressive than the (now push-based) connected path.

### Build order

| Step | Files | Description |
|---|---|---|
| 1 | `system_store.py`, `config/settings.py` | Remove `ibkr_mw_client_id`, `ibkr_wl_client_id` dataclass fields. Existing JSON ignored gracefully. |
| 2 | `gui/ibkr_session.py` (new) | Full `IBKRSession` implementation. Zero imports from `app_service.py`. Independently ruff+mypy clean. |
| 3 | `gui/app_service.py` (add only) | Add `_MarketWatchYfinanceWorker`; import `IBKRSession`; add four bridge slots as no-ops on stale `_ibkr_session`. Existing workers still present. |
| 4 | `gui/app_service.py` (wire) | Replace `_on_connect_ok` and `disconnect_feed` bodies to drive the session. Old timers still defined but no longer started. |
| 5 | `gui/app_service.py` (delete) | Delete `_AccountDataWorker`, `_MarketWatchWorker`, `_WatchlistQuoteWorker`, `_refresh_account_data`, `_refresh_market_watch`, `_refresh_watchlist`, `_on_account_data_failed`, and the seven obsolete fields. |
| 6 | `gui/app_service.py` (delta wiring) | Add `set_market_watch_symbols` / `set_watchlist` forwarding to session; add index-symbol carve-out path in `_on_session_quotes_updated`. |
| 7 | `tests/gui/test_ibkr_session.py` | Unit tests for reconnect state machine (mock `IB`), debounce timing, symbol-delta logic, signal-late-arrival guard. |

Steps 1 and 2 may proceed in parallel. Steps 3–6 are strictly sequential. Step 5 is gated on step 4 passing `mypy --strict` with zero references to deleted workers.

### Risk register

| # | Risk | Mitigation |
|---|---|---|
| R1 | Asyncio loop / `QThread` leak on abnormal shutdown | `disconnect_feed` always calls `_ibkr_session.stop()`; `stop()` enforces 3 s join with `QThread.terminate()` backstop; `_shutdown()` catches `asyncio.CancelledError`; `QApplication.aboutToQuit` wired to `disconnect_feed` |
| R2 | Signal delivered to `AppService` after `stop()` returns | Slots guard with `if self._ibkr_session is None: return` as first line; signals explicitly disconnected before reference release |
| R3 | `reqMktData` invoked on `^`-prefixed index symbols (IBKR error 200) | `_apply_symbol_delta` filters `[s for s in union if not s.startswith("^")]` inside the asyncio loop — upstream callers cannot leak indices through |
