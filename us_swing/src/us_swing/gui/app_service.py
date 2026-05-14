"""Module: MD-GUI-000.002, MD-GUI-004.001.M02 — app_service.py
Parent SRD: SRD-GUI-000.001, SRD-GUI-004.009, SRD-GUI-008.001–SRD-GUI-008.004,
            SRD-GUI-006.011–SRD-GUI-006.014

Application service — single source of truth for GUI state.

Account monitoring mode
───────────────────────
When connected to IBKR (live or paper Gateway), ``_AccountDataWorker`` polls
account equity, open positions, and unrealized PnL every 30 s.  The four KPI
cards (Today P&L, Capital Utilised, Open Positions, Account Equity) display
real data from the connected account.

Execution is permanently disabled at the tool level — no orders are sent to
IBKR regardless of the connected account type (live or paper).

Live position price streaming
──────────────────────────────
``_IBKRLiveSession`` owns a persistent ``IB()`` instance in a dedicated
QThread / asyncio event loop.  On each ``pendingTickersEvent`` it emits
``price_tick(symbol, price)`` which ``_on_live_price`` uses to update
``current_price`` on all matching open positions (IBKR + paper) and emit
``positions_updated``.  Subscriptions are synced on every account-data
refresh via ``_sync_live_subscriptions``.  The session auto-reconnects on
disconnect with exponential back-off (1 s → 30 s cap).

Paper trading (algo-side simulation)
─────────────────────────────────────
When a user's ``mode = 'paper'``, ``execute_signal()`` simulates fills locally
without contacting the broker.  This is an **algo-tool paper mode**, not IBKR
Paper Trading — position records are written locally with ``mode='paper'``.

Replaces the demo data backend.  All data accessors return real (initially
empty) data; positions and trades populate once a feed connection is
established. Users are persisted to ``~/.usswing/users.json``.

Feed connection architecture
────────────────────────────
``AppService`` owns the ``ConnectionStatus`` enum instance so any widget or
subsystem can query ``svc.connection_status`` for type-safe failsafe checks:

    if svc.connection_status is not ConnectionStatus.CONNECTED:
        ...  # guard against stale data

The ``feed_status_changed(str)`` signal broadcasts the raw ``ConnectionStatus.value``
string so legacy string comparisons in existing panels continue to work.

Candle database architecture
────────────────────────────
``~/.usswing/candles.db`` (SQLite) stores daily and weekly OHLCV for all
S&P 500 symbols.  AppService owns the status-check and download workers;
the GUI Database tab binds to the signals they emit.

Download source: IBKR (ib_insync). Requires CONNECTED status before start.
Checkpoint file: ``~/.usswing/candle_download_checkpoint.json`` persists
download progress so an interrupted download can resume from the last
completed symbol.  The last 5 completed symbols are re-verified against
the DB on resume to catch partial writes.
"""
from __future__ import annotations

import asyncio
import datetime
import enum
import json
import logging
import sqlite3
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from us_swing.execution.intraday_candle_loader import IntradayCandleLoader
    from us_swing.universe.store import Sp500Meta

_log = logging.getLogger(__name__)

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from us_swing.data.market_calendar import ET as _ET, get_exchange_status as _get_exchange_status
from us_swing.monitoring.connectivity import NetWatcher

from us_swing.data.models import (
    AccountState,
    ConnectionStatus,
    FilteredStockEntry,
    MarketWatchItem,
    OpenPosition,
    RiskConfig,
    ScreenerResult,
    TradeRecord,
    TradeSignal,
    UserProfile,
    WatchlistItem,
)
from us_swing.gui.system_store import SystemConfig, load_system_config
from us_swing.gui.user_store import load_users, next_user_id, save_users


# ── Default screener filter definitions (configuration, not data) ─────────────

# ── Background TCP probe worker ──────────────────────────────────────────────

class _ConnectWorker(QThread):
    """Probes host:port in a background thread; emits succeeded or failed."""

    succeeded = pyqtSignal()
    failed    = pyqtSignal(str)  # human-readable reason

    def __init__(self, host: str, port: int) -> None:
        super().__init__()
        self._host = host
        self._port = port

    def run(self) -> None:
        try:
            with socket.create_connection((self._host, self._port), timeout=4):
                pass
            self.succeeded.emit()
        except OSError as exc:
            self.failed.emit(str(exc))


class _AccountDataWorker(QThread):
    """Reads live account state from IBKR (ib_insync) and disconnects.

    Fetches: NetLiquidation (equity), portfolio positions with market value
    and unrealized PnL.  Uses a dedicated clientId so it doesn't collide
    with the candle-download connection.

    Execution is NOT performed here — this is read-only account monitoring.
    """

    done   = pyqtSignal(object, list)   # (AccountState, list[OpenPosition])
    failed = pyqtSignal(str)

    def __init__(self, host: str, port: int, client_id: int) -> None:
        super().__init__()
        self._host      = host
        self._port      = port
        self._client_id = client_id

    def run(self) -> None:
        try:
            asyncio.run(self._async_run())
        except Exception as exc:
            self.failed.emit(str(exc))

    async def _async_run(self) -> None:
        import math

        try:
            from ib_insync import IB  # type: ignore[import]
        except ImportError:
            self.failed.emit("ib_insync not installed — account data unavailable.")
            return

        ib = IB()
        try:
            await ib.connectAsync(self._host, self._port,
                                  clientId=self._client_id, timeout=5)
            await asyncio.sleep(1.5)  # allow accountUpdates subscription to populate

            # ── Account summary ──────────────────────────────────────────────
            # IBKR returns each tag multiple times — once per currency.
            # Prefer the BASE row (the broker's display currency); fall back to
            # the first non-empty value so we always get one number per tag.
            summary_items = await ib.accountSummaryAsync()
            tag_vals: dict[str, dict[str, str]] = {}
            for item in summary_items:
                tag_vals.setdefault(item.tag, {})[item.currency] = item.value

            def _tag(name: str) -> float:
                vals = tag_vals.get(name, {})
                if not vals:
                    return 0.0
                raw = vals.get("BASE") or next(iter(vals.values()), "0")
                try:
                    return float(raw or 0)
                except (ValueError, TypeError):
                    return 0.0

            equity               = _tag("NetLiquidation")
            # Explicit > 0 check: avoid the `0.0 or equity` falsy trap that
            # causes sod_equity to equal equity when the tag is missing/zero,
            # which would make the equity-delta fallback always produce 0.
            sod_equity_raw       = _tag("PreviousEquityWithLoanValue")
            sod_equity           = sod_equity_raw if sod_equity_raw > 0.0 else equity
            excess_liquidity     = _tag("ExcessLiquidity")
            total_cash_value     = _tag("TotalCashValue")
            gross_position_value = _tag("GrossPositionValue")

            # ── Portfolio (positions with live market value) ──────────────────
            portfolio  = ib.portfolio()
            open_val   = 0.0
            positions: list[OpenPosition] = []

            for pi in portfolio:
                qty = int(pi.position)
                if qty == 0:
                    continue
                sym      = pi.contract.symbol
                avg_cost = pi.averageCost
                mv       = pi.marketValue
                ltp      = abs(mv / qty) if qty else 0.0

                open_val  += abs(mv)

                positions.append(OpenPosition(
                    symbol          = sym,
                    user_id         = 1,
                    quantity        = abs(qty),
                    average_price   = avg_cost,
                    stop_loss       = 0.0,
                    target_price    = 0.0,
                    mode            = "live",
                    state           = "OPEN",
                    current_price   = ltp,
                    strategy_id     = "IBKR",
                    filled_quantity = abs(qty),
                    total_quantity  = abs(qty),
                ))

            acct = AccountState(
                user_id             = 1,
                equity              = equity,
                start_of_day_equity = sod_equity,
                open_position_value = open_val,
                daily_pnl           = sum(p.unrealised_pnl for p in positions),
                excess_liquidity    = excess_liquidity,
                total_cash_value     = total_cash_value,
                gross_position_value = gross_position_value,
            )
            self.done.emit(acct, positions)

        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if ib.isConnected():
                ib.disconnect()


class _ReadinessWorker(QThread):
    """Checks intraday candle readiness from the local DB off the main thread.

    Opens its own ``DatabaseManager`` so it never shares a SQLite connection
    with the ``IntradayCandleLoader`` that starts after this worker completes.
    Emits ``done`` with ``True`` (enough history) or ``None`` (⟳ — needs fetch)
    per symbol.
    """

    done = pyqtSignal(dict)  # dict[str, bool | None]

    def __init__(
        self,
        db_path: Path,
        symbols: list[str],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._symbols = symbols

    def run(self) -> None:
        result: dict[str, bool | None] = {}
        try:
            from us_swing.config.settings import DataConfig
            from us_swing.data.providers.dummy_provider import DummyProvider
            from us_swing.data.engine import HistoricalDataEngine
            from us_swing.db.manager import DatabaseManager
            from us_swing.execution.intraday_candle_loader import check_candle_readiness

            db = DatabaseManager(f"sqlite:///{self._db_path}")
            db.create_schema()
            # DummyProvider: aggregate_timeframe is pure computation — no network I/O.
            hist = HistoricalDataEngine(DummyProvider(), db, DataConfig())
            report = check_candle_readiness(self._symbols, db, hist)
            result = {s: (True if r.ready else None) for s, r in report.items()}
        except Exception:
            _log.exception("[Candles] Failed to check readiness from local database")
        self.done.emit(result)


class _MarketWatchWorker(QThread):
    """Fetches latest quotes for a list of symbols via yfinance in a background thread."""

    done = pyqtSignal(list)   # list[dict] — one dict per symbol

    def __init__(self, symbols: list[str]) -> None:
        super().__init__()
        self._symbols = symbols

    def run(self) -> None:
        try:
            import yfinance as yf  # already a project dependency
            results: list[dict] = []
            for sym in self._symbols:
                try:
                    info = yf.Ticker(sym).fast_info
                    ltp        = float(getattr(info, "last_price",       0) or 0)
                    prev_close = float(getattr(info, "previous_close",   0) or 0)
                    change_pct = ((ltp - prev_close) / prev_close * 100) if prev_close else 0.0
                    results.append({"symbol": sym, "ltp": ltp,
                                    "prev_close": prev_close, "change_pct": change_pct})
                except Exception:
                    results.append({"symbol": sym, "ltp": 0.0,
                                    "prev_close": 0.0, "change_pct": 0.0})
            self.done.emit(results)
        except Exception:
            self.done.emit([])


class _WatchlistQuoteWorker(QThread):
    """Fetches full quote data for watchlist symbols via yfinance in a background thread."""

    done = pyqtSignal(list)   # list[dict] — one dict per symbol

    def __init__(self, symbols: list[str]) -> None:
        super().__init__()
        self._symbols = symbols

    def run(self) -> None:
        try:
            import yfinance as yf
            results: list[dict] = []
            for sym in self._symbols:
                try:
                    fi = yf.Ticker(sym).fast_info
                    ltp        = float(getattr(fi, "last_price",    0) or 0)
                    prev_close = float(getattr(fi, "previous_close",0) or 0)
                    change     = ltp - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0.0
                    results.append({
                        "symbol":     sym,
                        "ltp":        ltp,
                        "prev_close": prev_close,
                        "change":     change,
                        "change_pct": change_pct,
                        "day_open":   float(getattr(fi, "open",      0) or 0),
                        "day_high":   float(getattr(fi, "day_high",  0) or 0),
                        "day_low":    float(getattr(fi, "day_low",   0) or 0),
                        "volume":     int(getattr(fi, "volume",      0) or 0),
                        "year_high":  float(getattr(fi, "year_high", 0) or 0),
                        "year_low":   float(getattr(fi, "year_low",  0) or 0),
                        "market_cap": float(getattr(fi, "market_cap",0) or 0),
                    })
                except Exception:
                    results.append({
                        "symbol": sym, "ltp": 0.0, "prev_close": 0.0,
                        "change": 0.0, "change_pct": 0.0, "day_open": 0.0,
                        "day_high": 0.0, "day_low": 0.0, "volume": 0,
                        "year_high": 0.0, "year_low": 0.0, "market_cap": 0.0,
                    })
            self.done.emit(results)
        except Exception:
            self.done.emit([])


class _IBKRLiveSession(QThread):
    """Persistent IBKR connection for streaming live market-data ticks.

    Owns a single long-lived IB() in a dedicated asyncio event loop so the
    Qt main thread is never blocked.  Reconnects automatically on disconnect
    with exponential back-off (1 s → 30 s cap).

    Thread-safety:
    - ``_stop_event`` is a ``threading.Event`` — safe to set from any thread.
    - ``request_stop`` also calls ``loop.call_soon_threadsafe(loop.stop)`` to
      interrupt any in-progress ``connectAsync`` immediately rather than waiting
      for the 0.2 s poll boundary.
    - ``subscribe_symbols`` / ``unsubscribe_symbols`` post coroutines into the
      running loop via ``asyncio.run_coroutine_threadsafe``.
    - ``price_tick`` / ``session_connected`` are cross-thread Qt signals —
      PyQt6 marshals them to the main thread automatically.
    """

    price_tick        = pyqtSignal(str, float)  # (symbol, last_price)
    session_connected    = pyqtSignal()
    session_disconnected = pyqtSignal()

    _MAX_BACKOFF = 30.0

    def __init__(
        self,
        host: str,
        port: int,
        client_id: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._host       = host
        self._port       = port
        self._client_id  = client_id
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ib: Any = None              # ib_insync.IB — set inside run()
        self._ticker_map: dict[str, Any] = {}  # symbol → ib_insync.Ticker
        self._dead_symbols: set[str] = set()   # symbols that returned Error 200 — never re-subscribed

    # ── Public API — safe to call from the Qt main thread ────────────────────

    def request_stop(self) -> None:
        self._stop_event.set()
        loop = self._loop
        if loop and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)

    def subscribe_symbols(self, symbols: set[str]) -> None:
        loop = self._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._do_subscribe(frozenset(symbols)), loop
            )

    def unsubscribe_symbols(self, symbols: set[str]) -> None:
        loop = self._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._do_unsubscribe(frozenset(symbols)), loop
            )

    # ── QThread entry point ───────────────────────────────────────────────────

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except RuntimeError:
            pass  # loop.stop() called from request_stop() during connectAsync
        finally:
            self._loop.close()
            asyncio.set_event_loop(None)
            self._loop = None

    # ── Internal async machinery ──────────────────────────────────────────────

    async def _main(self) -> None:
        try:
            from ib_insync import IB  # type: ignore[import]
        except ImportError:
            _log.warning("[Feed] ib_insync not installed — live price streaming unavailable")
            return

        self._ib = IB()
        backoff = 1.0

        while not self._stop_event.is_set():
            try:
                await self._ib.connectAsync(
                    self._host, self._port,
                    clientId=self._client_id, timeout=10,
                )
                backoff = 1.0
                self._ib.pendingTickersEvent += self._on_pending_tickers
                self._ib.errorEvent += self._on_mkt_error  # type: ignore[operator]
                self.session_connected.emit()

                while self._ib.isConnected() and not self._stop_event.is_set():
                    await asyncio.sleep(0.2)

                self._ib.pendingTickersEvent -= self._on_pending_tickers
                self._ib.errorEvent -= self._on_mkt_error  # type: ignore[operator]
                self._ticker_map.clear()
                self.session_disconnected.emit()

            except Exception:
                self.session_disconnected.emit()

            if self._stop_event.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self._MAX_BACKOFF)

        if self._ib and self._ib.isConnected():
            self._ib.disconnect()

    def _on_pending_tickers(self, tickers: Any) -> None:
        # Called on the asyncio event-loop thread (not the Qt main thread).
        # Only emit the cross-thread signal here — do not access Qt objects directly.
        for ticker in tickers:
            contract = getattr(ticker, "contract", None)
            if contract is None:
                continue
            sym = getattr(contract, "symbol", None)
            if not sym:
                continue
            price = getattr(ticker, "last", None)
            if price and price > 0:
                self.price_tick.emit(sym, float(price))

    def _on_mkt_error(self, req_id: int, error_code: int, *_: Any) -> None:
        # Called on the asyncio event-loop thread. Safe to mutate _ticker_map here.
        if error_code != 200:
            return
        sym = next(
            (s for s, t in list(self._ticker_map.items()) if getattr(t, "reqId", -1) == req_id),
            None,
        )
        if sym is None:
            return
        _log.info("[Feed] %s is not available on US exchanges — price streaming skipped", sym)
        ticker = self._ticker_map.pop(sym, None)
        if ticker is not None:
            contract = getattr(ticker, "contract", None)
            if contract is not None and self._ib:
                self._ib.cancelMktData(contract)
        self._dead_symbols.add(sym)

    async def _do_subscribe(self, symbols: frozenset[str]) -> None:
        if not self._ib or not self._ib.isConnected():
            return
        try:
            from ib_insync import Stock  # type: ignore[import]
        except ImportError:
            return
        for sym in symbols - set(self._ticker_map) - self._dead_symbols:
            contract = Stock(sym, "SMART", "USD")
            self._ticker_map[sym] = self._ib.reqMktData(contract, "", False, False)

    async def _do_unsubscribe(self, symbols: frozenset[str]) -> None:
        if not self._ib or not self._ib.isConnected():
            return
        for sym in list(symbols & set(self._ticker_map)):
            ticker = self._ticker_map.pop(sym)
            contract = getattr(ticker, "contract", None)
            if contract is not None:
                self._ib.cancelMktData(contract)


class _Sp500RefreshWorker(QThread):
    """Downloads the S&P 500 universe from Wikipedia in a background thread."""

    done   = pyqtSignal(list)   # list[Sp500Record]
    failed = pyqtSignal(str)    # error message

    def __init__(self, *, force: bool = False) -> None:
        super().__init__()
        self._force = force

    def run(self) -> None:
        try:
            from us_swing.universe.store import load_sp500
            records = load_sp500(force_refresh=self._force)
            self.done.emit(records)
        except Exception as exc:
            self.failed.emit(str(exc))


# ── Candle database — types and helpers ──────────────────────────────────────

_CANDLE_DB_PATH: Path         = Path.home() / ".usswing" / "candles.db"
_CHECKPOINT_PATH: Path        = Path.home() / ".usswing" / "candle_download_checkpoint.json"
_FAILED_SYMBOLS_PATH: Path    = Path.home() / ".usswing" / "candle_failed_symbols.json"
_CANDLE_SYMBOL_PAUSE_S: float = 1.0    # seconds between IBKR historical requests
_CANDLE_COVERAGE_THRESHOLD: float = 0.95  # 95% symbol coverage = CURRENT
_RESUME_VERIFY_COUNT: int     = 5      # re-check last N completed symbols on resume


class CandleDbStatus(enum.Enum):
    """Lifecycle status of the local candle database."""
    EMPTY   = "empty"    # no price_1d / price_1w rows at all
    PARTIAL = "partial"  # data exists but behind last trading day or < 95% coverage
    CURRENT = "current"  # max(datetime) == last trading day AND coverage ≥ 95%


@dataclass
class CandleDbInfo:
    """Snapshot of candle database state, returned by _CandleDbStatusWorker."""
    status: CandleDbStatus
    last_trading_day: str          # "YYYY-MM-DD"
    first_candle_date: str | None  # "YYYY-MM-DD" or None
    last_candle_date:  str | None  # "YYYY-MM-DD" or None
    symbols_1d:        int         # distinct symbols in price_1d
    symbols_1w:        int         # distinct symbols in price_1w
    total_1d:          int         # total rows in price_1d
    total_1w:          int         # total rows in price_1w
    universe_size:     int         # expected symbol count from S&P 500 universe


def _compute_last_trading_day() -> datetime.date:
    """Return the most recent completed NYSE trading day.

    A day counts as "completed" only after 16:00 ET.  Today is included
    once the closing bell has passed; otherwise yesterday's session is used.
    Weekends and NYSE_HOLIDAYS (from market_calendar) are skipped.
    """
    from us_swing.data.market_calendar import ET, NYSE_HOLIDAYS
    now_et = datetime.datetime.now(ET)
    candidate = now_et.date()
    # If market hasn't closed yet today, move back one day before searching.
    if now_et.time() < datetime.time(16, 0):
        candidate -= datetime.timedelta(days=1)
    for _ in range(14):   # max 14 days back (covers any holiday cluster)
        if (candidate.weekday() < 5                                   # Mon–Fri
                and (candidate.month, candidate.day) not in NYSE_HOLIDAYS):
            return candidate
        candidate -= datetime.timedelta(days=1)
    return candidate   # fallback (shouldn't reach)


def _ensure_candle_tables(conn: sqlite3.Connection) -> None:
    """Create price_1d and price_1w tables if they don't exist."""
    for tbl in ("price_1d", "price_1w"):
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl} (
                symbol   TEXT NOT NULL,
                datetime TEXT NOT NULL,
                open     REAL,
                high     REAL,
                low      REAL,
                close    REAL,
                volume   INTEGER,
                PRIMARY KEY (symbol, datetime)
            )
        """)
    conn.commit()


# ── Checkpoint helpers ────────────────────────────────────────────────────────

def _save_checkpoint(
    start_date: datetime.date,
    end_date: datetime.date,
    mode: str,
    symbols_done: list[str],
    symbols_todo: list[str],
) -> None:
    """Persist download progress to checkpoint file."""
    _CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version":     1,
        "start_date":  start_date.isoformat(),
        "end_date":    end_date.isoformat(),
        "mode":        mode,
        "symbols_done": symbols_done,
        "symbols_todo": symbols_todo,
        "created_at":  datetime.datetime.now().isoformat(timespec="seconds"),
    }
    _CHECKPOINT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_checkpoint() -> dict | None:
    """Return checkpoint dict if file exists and is valid, else None."""
    if not _CHECKPOINT_PATH.exists():
        return None
    try:
        data = json.loads(_CHECKPOINT_PATH.read_text(encoding="utf-8"))
        if data.get("version") != 1:
            return None
        # Validate required fields
        for key in ("start_date", "end_date", "mode", "symbols_done", "symbols_todo"):
            if key not in data:
                return None
        return data
    except Exception:
        return None


def _delete_checkpoint() -> None:
    """Remove the checkpoint file if it exists."""
    try:
        _CHECKPOINT_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def _verify_resume_symbols(
    symbols_done: list[str],
    end_date: datetime.date,
) -> list[str]:
    """Check the last N completed symbols against the DB.

    Returns a list of symbols whose last candle date is more than 5
    calendar days before ``end_date`` — these should be re-downloaded.
    """
    if not _CANDLE_DB_PATH.exists() or not symbols_done:
        return []
    to_recheck = symbols_done[-_RESUME_VERIFY_COUNT:]
    stale: list[str] = []
    try:
        conn = sqlite3.connect(str(_CANDLE_DB_PATH))
        threshold = end_date - datetime.timedelta(days=5)
        for sym in to_recheck:
            row = conn.execute(
                "SELECT MAX(datetime) FROM price_1d WHERE symbol = ?", (sym,)
            ).fetchone()
            if not row or not row[0]:
                stale.append(sym)
            else:
                last_dt = datetime.date.fromisoformat(row[0][:10])
                if last_dt < threshold:
                    stale.append(sym)
        conn.close()
    except Exception:
        pass
    return stale


# ── Background worker: query DB status ───────────────────────────────────────

class _CandleDbStatusWorker(QThread):
    """Reads candle DB stats from disk and emits a CandleDbInfo object."""

    done   = pyqtSignal(object)   # CandleDbInfo
    failed = pyqtSignal(str)

    def __init__(self, universe_size: int) -> None:
        super().__init__()
        self._universe_size = universe_size

    def run(self) -> None:
        try:
            last_trading_day = _compute_last_trading_day()
            ltd_str = last_trading_day.strftime("%Y-%m-%d")

            db_path = _CANDLE_DB_PATH
            if not db_path.exists():
                self.done.emit(CandleDbInfo(
                    status=CandleDbStatus.EMPTY,
                    last_trading_day=ltd_str,
                    first_candle_date=None,
                    last_candle_date=None,
                    symbols_1d=0,
                    symbols_1w=0,
                    total_1d=0,
                    total_1w=0,
                    universe_size=self._universe_size,
                ))
                return

            conn = sqlite3.connect(str(db_path))
            _ensure_candle_tables(conn)

            def _stats(table: str) -> tuple[int, int, str | None, str | None]:
                row = conn.execute(
                    f"SELECT COUNT(DISTINCT symbol), COUNT(*), MIN(datetime), MAX(datetime) FROM {table}"
                ).fetchone()
                syms  = row[0] or 0
                total = row[1] or 0
                first = row[2][:10] if row[2] else None   # "YYYY-MM-DD"
                last  = row[3][:10] if row[3] else None
                return syms, total, first, last

            syms_1d, total_1d, first_1d, last_1d = _stats("price_1d")
            syms_1w, total_1w, first_1w, last_1w = _stats("price_1w")
            conn.close()

            # Aggregate across both timeframes
            first_date = first_1d or first_1w
            last_date  = last_1d  or last_1w
            total_syms = max(syms_1d, syms_1w)

            if total_syms == 0:
                status = CandleDbStatus.EMPTY
            else:
                coverage_ok = (
                    self._universe_size > 0
                    and total_syms / self._universe_size >= _CANDLE_COVERAGE_THRESHOLD
                )
                date_ok = last_date == ltd_str if last_date else False
                status = CandleDbStatus.CURRENT if (coverage_ok and date_ok) else CandleDbStatus.PARTIAL

            self.done.emit(CandleDbInfo(
                status=status,
                last_trading_day=ltd_str,
                first_candle_date=first_date,
                last_candle_date=last_date,
                symbols_1d=syms_1d,
                symbols_1w=syms_1w,
                total_1d=total_1d,
                total_1w=total_1w,
                universe_size=self._universe_size,
            ))
        except Exception as exc:
            self.failed.emit(str(exc))


# ── Background worker: download candles ──────────────────────────────────────

class _CandleDownloadWorker(QThread):
    """Downloads Daily + Weekly OHLCV for all symbols via IBKR (ib_insync)
    and stores them in ``~/.usswing/candles.db``.

    Supports checkpoint/resume: after each symbol, progress is written to
    ``~/.usswing/candle_download_checkpoint.json``.  A clean finish deletes
    the file; a stop/error leaves it so the next call can resume.

    Emits:
        progress(symbol, done, total)  — after each symbol starts
        finished(inserted_1d, inserted_1w)
        failed(reason)  — reason prefix ``IBKR_NOT_CONNECTED`` or
                          ``IBKR_DISCONNECTED`` triggers paused handling
                          in AppService
    """

    progress      = pyqtSignal(str, int, int)  # symbol, done index, total
    finished      = pyqtSignal(int, int)       # total_1d inserted, total_1w inserted
    failed        = pyqtSignal(str)
    symbol_failed = pyqtSignal(str, str)       # symbol, reason

    def __init__(
        self,
        symbols:          list[str],
        start_date:       datetime.date,
        end_date:         datetime.date,
        mode:             str,   # "full" | "delta"
        ibkr_host:        str,
        ibkr_port:        int,
        ibkr_client_id:   int,
        benchmark_symbol: str = "SPY",
    ) -> None:
        super().__init__()
        self._symbols          = symbols
        self._start_date       = start_date
        self._end_date         = end_date
        self._mode             = mode
        self._ibkr_host        = ibkr_host
        self._ibkr_port        = ibkr_port
        self._ibkr_client_id   = ibkr_client_id
        self._benchmark_symbol = benchmark_symbol
        self._stop_flag        = False

    def request_stop(self) -> None:
        """Signal the worker to stop after the current symbol completes."""
        self._stop_flag = True

    def run(self) -> None:
        """Entry point: runs the async download loop in a new event loop."""
        try:
            asyncio.run(self._async_run())
        except Exception as exc:
            self.failed.emit(str(exc))

    # ── Async implementation ──────────────────────────────────────────────────

    async def _async_run(self) -> None:
        try:
            from ib_insync import IB  # type: ignore[import]
        except ImportError:
            self.failed.emit(
                "IBKR_NOT_INSTALLED: ib_insync package required. "
                "Run: pip install ib_insync"
            )
            return

        ib = IB()
        try:
            await ib.connectAsync(
                self._ibkr_host, self._ibkr_port,
                clientId=self._ibkr_client_id,
                timeout=10,
            )
        except Exception as exc:
            self.failed.emit(f"IBKR_NOT_CONNECTED: {exc}")
            return

        try:
            await self._download_all(ib)
        except Exception as exc:
            reason = str(exc)
            if not ib.isConnected():
                self.failed.emit("IBKR_DISCONNECTED")
            else:
                self.failed.emit(reason)
        finally:
            ib.disconnect()

    async def _download_benchmark(self, ib: object) -> None:
        """Fetch 2 years of 1d + 1w bars for the benchmark symbol (e.g. SPY).

        Non-fatal: logs a symbol_failed warning on error and continues.
        Benchmark rows are stored in the same price_1d / price_1w tables as
        constituent stocks; they are identifiable by their symbol string alone.
        """
        from ib_insync import Stock  # type: ignore[import]

        symbol = self._benchmark_symbol
        if not symbol:
            return

        end_dt_str = self._end_date.strftime("%Y%m%d 23:59:59")
        try:
            contract = Stock(symbol, "SMART", "USD")
            bars_1d = await ib.reqHistoricalDataAsync(  # type: ignore[attr-defined]
                contract,
                endDateTime=end_dt_str,
                durationStr="2 Y",
                barSizeSetting="1 day",
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
            )
            bars_1w = await ib.reqHistoricalDataAsync(  # type: ignore[attr-defined]
                contract,
                endDateTime=end_dt_str,
                durationStr="2 Y",
                barSizeSetting="1 week",
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
            )
            if not bars_1d and not bars_1w:
                self.symbol_failed.emit(symbol, "BENCHMARK_NO_DATA")
                return

            db_path = _CANDLE_DB_PATH
            conn = sqlite3.connect(str(db_path))
            cur  = conn.cursor()
            for bar in bars_1d:
                dt_str = _bar_date_str(bar.date)
                cur.execute(
                    "INSERT OR REPLACE INTO price_1d VALUES (?,?,?,?,?,?,?)",
                    (symbol, dt_str,
                     float(bar.open), float(bar.high),
                     float(bar.low),  float(bar.close),
                     int(bar.volume)),
                )
            for bar in bars_1w:
                dt_str = _bar_date_str(bar.date)
                cur.execute(
                    "INSERT OR REPLACE INTO price_1w VALUES (?,?,?,?,?,?,?)",
                    (symbol, dt_str,
                     float(bar.open), float(bar.high),
                     float(bar.low),  float(bar.close),
                     int(bar.volume)),
                )
            conn.commit()
            conn.close()
        except Exception as exc:
            self.symbol_failed.emit(symbol, f"BENCHMARK_ERROR: {exc}")

    async def _download_all(self, ib: object) -> None:
        from ib_insync import Stock  # type: ignore[import]

        db_path = _CANDLE_DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        _ensure_candle_tables(conn)
        conn.close()

        # ── Benchmark symbol (SPY) — downloaded first, before the universe loop ─
        if self._mode in ("full", "delta") and self._benchmark_symbol:
            await self._download_benchmark(ib)

        # Duration strings for IBKR reqHistoricalData
        # IBKR rule: durations > 365 days or > 52 weeks must be expressed in years.
        duration_days = (self._end_date - self._start_date).days + 5
        duration_weeks = max((duration_days // 7) + 2, 4)
        duration_years = max((duration_days // 365) + 1, 1)
        if duration_days > 365:
            ibkr_duration_1d = f"{duration_years} Y"
        else:
            ibkr_duration_1d = f"{duration_days} D"
        if duration_weeks > 52:
            ibkr_duration_1w = f"{duration_years} Y"
        else:
            ibkr_duration_1w = f"{duration_weeks} W"
        end_dt_str = self._end_date.strftime("%Y%m%d 23:59:59")

        # Build mutable done/todo lists (checkpoint may have pre-populated them)
        symbols_done: list[str] = []
        symbols_todo: list[str] = list(self._symbols)

        total        = len(symbols_todo)
        inserted_1d  = 0
        inserted_1w  = 0
        done_count   = 0

        for symbol in symbols_todo:
            if self._stop_flag:
                break

            self.progress.emit(symbol, done_count, total)

            try:
                # IBKR uses a space instead of a dot in symbols (e.g. BRK.B → BRK B)
                ibkr_symbol = symbol.replace(".", " ")
                contract = Stock(ibkr_symbol, "SMART", "USD")

                bars_1d = await ib.reqHistoricalDataAsync(  # type: ignore[attr-defined]
                    contract,
                    endDateTime=end_dt_str,
                    durationStr=ibkr_duration_1d,
                    barSizeSetting="1 day",
                    whatToShow="TRADES",
                    useRTH=True,
                    formatDate=1,
                )
                bars_1w = await ib.reqHistoricalDataAsync(  # type: ignore[attr-defined]
                    contract,
                    endDateTime=end_dt_str,
                    durationStr=ibkr_duration_1w,
                    barSizeSetting="1 week",
                    whatToShow="TRADES",
                    useRTH=True,
                    formatDate=1,
                )

                # Check for empty response (IBKR returned no data)
                if not bars_1d and not bars_1w:
                    self.symbol_failed.emit(symbol, "NO_DATA")
                else:
                    # Write to DB atomically per symbol
                    conn = sqlite3.connect(str(db_path))
                    cur  = conn.cursor()

                    for bar in bars_1d:
                        dt_str = _bar_date_str(bar.date)
                        cur.execute(
                            "INSERT OR REPLACE INTO price_1d VALUES (?,?,?,?,?,?,?)",
                            (symbol, dt_str,
                             float(bar.open), float(bar.high),
                             float(bar.low),  float(bar.close),
                             int(bar.volume)),
                        )
                        inserted_1d += 1

                    for bar in bars_1w:
                        dt_str = _bar_date_str(bar.date)
                        cur.execute(
                            "INSERT OR REPLACE INTO price_1w VALUES (?,?,?,?,?,?,?)",
                            (symbol, dt_str,
                             float(bar.open), float(bar.high),
                             float(bar.low),  float(bar.close),
                             int(bar.volume)),
                        )
                        inserted_1w += 1

                    conn.commit()
                    conn.close()

            except Exception as exc:
                reason = str(exc) if str(exc) else type(exc).__name__
                self.symbol_failed.emit(symbol, reason)

            # Update checkpoint after each symbol (regardless of success/skip)
            done_count += 1
            symbols_done.append(symbol)
            remaining = symbols_todo[done_count:]
            _save_checkpoint(
                self._start_date, self._end_date, self._mode,
                symbols_done, remaining,
            )

            # Per-symbol rate-limit pause; interruptible in 0.1 s steps
            if not self._stop_flag:
                steps = int(_CANDLE_SYMBOL_PAUSE_S / 0.1)
                for _ in range(steps):
                    if self._stop_flag:
                        break
                    await asyncio.sleep(0.1)

            # Check live IBKR connection
            if not ib.isConnected():  # type: ignore[attr-defined]
                self.failed.emit("IBKR_DISCONNECTED")
                return

        if not self._stop_flag:
            _delete_checkpoint()
            self.finished.emit(inserted_1d, inserted_1w)
        else:
            # Stopped by user — checkpoint persists for future resume
            self.finished.emit(inserted_1d, inserted_1w)


def _bar_date_str(bar_date: object) -> str:
    """Convert an ib_insync bar date (date or datetime) to ISO string."""
    if isinstance(bar_date, datetime.datetime):
        return bar_date.strftime("%Y-%m-%dT%H:%M:%S")
    if isinstance(bar_date, datetime.date):
        return bar_date.strftime("%Y-%m-%dT00:00:00")
    # Fallback: string from IBKR formatted as YYYYMMDD
    s = str(bar_date)
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}T00:00:00"
    return s


_DEFAULT_PAPER_EQUITY: float = 100_000.0

# ── Default Market Watch symbols (top 3 US indices) ───────────────────────────

_DEFAULT_WATCH: list[MarketWatchItem] = [
    MarketWatchItem("^GSPC", "S&P 500"),
    MarketWatchItem("^IXIC", "NASDAQ"),
    MarketWatchItem("^DJI",  "Dow Jones"),
]


# ── Application Service ───────────────────────────────────────────────────────

class AppService(QObject):
    """Paper-mode application service.

    All GUI panels connect to these signals and call these methods.
    Data lists are empty until a feed connection is established.
    User records are loaded from ``~/.usswing/users.json`` on startup;
    a default 'trader' profile is created on first run.
    """

    positions_updated    = pyqtSignal()          # position data changed
    account_updated      = pyqtSignal()          # account state changed
    log_message          = pyqtSignal(str, str)  # (level, message)
    viewing_changed      = pyqtSignal()          # admin scope changed
    users_changed        = pyqtSignal()          # user list mutated
    feed_status_changed  = pyqtSignal(str)       # ConnectionStatus.value string
    market_watch_updated = pyqtSignal()          # Market Watch prices refreshed
    watchlist_updated    = pyqtSignal()          # Watchlist quote data refreshed
    market_status_updated = pyqtSignal()          # NYSE/NASDAQ open-closed status
    sp500_updated         = pyqtSignal()          # S&P 500 universe loaded/refreshed
    internet_status_changed = pyqtSignal(bool)   # True = online, False = offline
    candle_db_status_changed  = pyqtSignal(object)         # CandleDbInfo
    candle_download_progress  = pyqtSignal(str, int, int)  # symbol, done, total
    candle_download_finished  = pyqtSignal(int, int)       # inserted_1d, inserted_1w
    candle_download_failed    = pyqtSignal(str)            # reason string
    candle_download_paused    = pyqtSignal(str)            # reason (IBKR disconnect)
    candle_symbol_failed      = pyqtSignal(str, str)       # symbol, reason (per-symbol)
    candle_download_failures  = pyqtSignal(object)         # list[str] — full failed list at end
    screener_results_updated  = pyqtSignal(list)           # list[FilteredStockEntry]
    intraday_load_progress    = pyqtSignal(str, int, int)  # symbol, done, total
    candle_readiness_updated  = pyqtSignal(dict)           # dict[str, bool | None]
    exchange_unavail_updated  = pyqtSignal(object)         # set[str]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._positions:   list[OpenPosition]  = []
        self._trades:      list[TradeRecord]   = []
        self._scr_results: list[ScreenerResult] = []
        self._signals:     list[TradeSignal]   = []
        self._current_failed: list[str]        = []  # per-download failure accumulator
        self._exchange_unavailable_symbols: set[str] = set()

        users = load_users()
        if not users:
            # First-run: create a default paper trader profile.
            users = [UserProfile(
                user_id=1, username="trader", display_name="Trader",
                ibkr_client_id=100, mode="paper",
                risk_config=RiskConfig(), strategy_config={}, screener_config={},
            )]
            save_users(users)
        self._users      = users
        self._active_uid = self._users[0].user_id
        self._viewing_uid: int | None = None

        self._connection_status = ConnectionStatus.DISCONNECTED
        self._system_cfg        = load_system_config()

        # ── IBKR live account cache (populated when connected) ────────────────
        self._ibkr_acct:      AccountState | None    = None
        self._ibkr_positions: list[OpenPosition]     = []
        self._acct_worker:    _AccountDataWorker | None = None

        self._acct_timer = QTimer(self)
        self._acct_timer.setInterval(30_000)   # refresh every 30 s when connected
        self._acct_timer.timeout.connect(self._refresh_account_data)

        # ── Market Watch ─────────────────────────────────────────────────────
        self._watch: list[MarketWatchItem] = [
            MarketWatchItem(w.symbol, w.display_name) for w in _DEFAULT_WATCH
        ]
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(15_000)   # refresh every 15 s when connected
        self._watch_timer.timeout.connect(self._refresh_market_watch)

        # ── Watchlist ─────────────────────────────────────────────────────────
        self._watchlist: list[WatchlistItem] = []
        self._wl_worker: _WatchlistQuoteWorker | None = None
        self._wl_timer = QTimer(self)
        self._wl_timer.setInterval(30_000)      # refresh every 30 s (yfinance, internet-only)
        self._wl_timer.timeout.connect(self._refresh_watchlist)

        # ── IBKR live market-data streaming session ──────────────────────────
        self._live_session: _IBKRLiveSession | None = None
        self._subscribed_symbols: set[str] = set()
        self._pending_prices: dict[str, float] = {}
        self._price_flush_timer = QTimer(self)
        self._price_flush_timer.setInterval(500)
        self._price_flush_timer.setSingleShot(True)
        self._price_flush_timer.timeout.connect(self._flush_pending_prices)

        # ── Market status (NYSE / NASDAQ) — always running, 60 s tick ────────
        self._market_status: dict[str, str] = {"nyse": "closed", "nasdaq": "closed"}
        self._mkt_status_timer = QTimer(self)
        self._mkt_status_timer.setInterval(60_000)
        self._mkt_status_timer.timeout.connect(self._refresh_market_status)
        self._mkt_status_timer.start()
        self._refresh_market_status()   # immediate first check

        # ── S&P 500 universe — check cache on startup ─────────────────────────
        # Runs in a deferred QTimer so the GUI is visible before any network I/O.
        self._sp500: list = []
        QTimer.singleShot(500, self._check_sp500_universe)

        # ── Internet connectivity watcher ─────────────────────────────────────
        # Tracks whether the machine can reach the public internet.
        # Stores whether the IBKR feed was connected so we can auto-reconnect
        # when connectivity is restored after an outage.
        self._was_feed_connected: bool = False
        self._mw_log_on_next_fetch: bool = False
        self._net_watcher = NetWatcher(parent=self)
        self._net_watcher.status_changed.connect(self._on_internet_status)
        self._net_watcher.start()

        # ── Intraday candle loader (SRD-EXE-006.007 / .008) ──────────────────
        self._intraday_loader: IntradayCandleLoader | None = None
        self._readiness_worker: _ReadinessWorker | None = None
        self._pending_candle_symbols: list[str] | None = None
        self.screener_results_updated.connect(self._on_screener_results_updated)
        # Trigger candle fetch for any results that were saved from a prior screener run.
        QTimer.singleShot(0, self._boot_candle_check)

    # ── Architecture-level connection status ──────────────────────────────────

    @property
    def connection_status(self) -> ConnectionStatus:
        """Typed ``ConnectionStatus`` enum — use for failsafe guards.

        Example::

            if svc.connection_status is not ConnectionStatus.CONNECTED:
                raise RuntimeError("Feed not connected")
        """
        return self._connection_status

    def get_feed_status(self) -> str:
        """Return raw ``ConnectionStatus`` value string."""
        return self._connection_status.value

    # ── Admin scope ───────────────────────────────────────────────────────────

    def set_viewing_uid(self, uid: int | None) -> None:
        """Switch admin scope.  ``None`` = aggregate all users."""
        self._viewing_uid = uid
        self.viewing_changed.emit()
        self.positions_updated.emit()
        self.account_updated.emit()

    def get_viewing_uid(self) -> int | None:
        return self._viewing_uid

    def get_user_by_id(self, uid: int) -> UserProfile | None:
        return next((u for u in self._users if u.user_id == uid), None)

    def get_user_label(self) -> str:
        if self._viewing_uid is None:
            return "All Users"
        u = self.get_user_by_id(self._viewing_uid)
        return u.username if u else "Unknown"

    # ── Data accessors ────────────────────────────────────────────────────────

    def get_positions(self, user_id: int | None = None) -> list[OpenPosition]:
        if self._ibkr_positions:
            return list(self._ibkr_positions)
        uid = user_id if user_id is not None else self._viewing_uid
        if uid is None:
            return [p for p in self._positions if p.state != "CLOSED"]
        return [p for p in self._positions if p.user_id == uid and p.state != "CLOSED"]

    def get_all_trades(self, user_id: int | None = None) -> list[TradeRecord]:
        uid = user_id if user_id is not None else self._viewing_uid
        if uid is None:
            return list(self._trades)
        return [t for t in self._trades if t.user_id == uid]

    def get_account_state(self, user_id: int | None = None) -> AccountState:
        uid = user_id if user_id is not None else self._viewing_uid
        if self._ibkr_acct is not None:
            return self._ibkr_acct
        # Disconnected — return zeros until IBKR data arrives
        return AccountState(
            user_id             = uid or 0,
            equity              = 0.0,
            start_of_day_equity = 0.0,
            open_position_value = 0.0,
            daily_pnl           = 0.0,
        )

    def get_users(self) -> list[UserProfile]:
        return list(self._users)

    def get_active_user(self) -> UserProfile:
        return next(
            (u for u in self._users if u.user_id == self._active_uid),
            self._users[0],
        )

    def get_screener_results(self) -> list[ScreenerResult]:
        return list(self._scr_results)

    def get_latest_screener_results(self) -> list[FilteredStockEntry]:
        """Return the most recent saved screener result for every known preset.

        Scans ``~/.usswing/screener_results/preset_*/`` directories and loads
        the newest date file for each preset.  Does not require a fresh run —
        results from any past date are returned.  Symbols that appear in
        multiple presets are deduped, keeping the highest score.
        """
        from us_swing.screener.storage import ScreenerResultsStorage  # noqa: PLC0415
        from us_swing.screener.manager import PresetManager            # noqa: PLC0415

        storage = ScreenerResultsStorage()
        mgr = PresetManager()
        base = Path.home() / ".usswing" / "screener_results"
        if not base.exists():
            return []

        # Build preset metadata lookup across admin + active-user presets
        preset_meta: dict[str, Any] = {}
        try:
            for p in mgr.list_admin_presets():
                preset_meta[p.id] = p
        except Exception:  # noqa: BLE001
            pass
        try:
            for p in mgr.list_user_presets(str(self._active_uid)):
                preset_meta[p.id] = p
        except Exception:  # noqa: BLE001
            pass

        best: dict[str, FilteredStockEntry] = {}
        for d in base.iterdir():
            if not d.is_dir() or not d.name.startswith("preset_"):
                continue
            preset_id = d.name[len("preset_"):]
            dates = storage.list_results(preset_id, limit=1)
            if not dates:
                continue
            try:
                result = storage.load_result(preset_id, dates[0])
            except Exception:  # noqa: BLE001
                continue

            p = preset_meta.get(preset_id)
            name: str = p.name if p else preset_id
            styles: list[str] = list(p.trading_styles) if p else []
            users: list[str] = list(p.assigned_to) if p else []

            for sym, data in result.results.items():
                if not data.get("passed", True):
                    continue
                score = float(data.get("score", 0.0))
                entry = FilteredStockEntry(
                    symbol=sym,
                    score=score,
                    trading_styles=styles,
                    assigned_users=users,
                    screener_name=name,
                    run_type=result.execution_mode,
                    date=result.date,
                )
                if sym not in best or score > best[sym].score:
                    best[sym] = entry

        return sorted(best.values(), key=lambda e: e.score, reverse=True)

    def notify_screener_results_updated(self) -> None:
        """Reload latest file-based results and emit ``screener_results_updated``.

        Called by ScreenerPanel after any successful run so the Execution panel
        refreshes without requiring the user to switch tabs.
        """
        entries = self.get_latest_screener_results()
        self.screener_results_updated.emit(entries)

    # ── Intraday candle auto-fetch (SRD-EXE-006.007 / .008) ──────────────────

    def _boot_candle_check(self) -> None:
        """Fire candle fetch on startup if saved screener results already exist."""
        entries = self.get_latest_screener_results()
        symbols = sorted({e.symbol for e in entries})
        if not symbols:
            _log.info("[Candles] No previous screener results found — skipping startup fetch")
            return
        _log.info("[Candles] Found %d stock(s) from last screener run — starting candle fetch", len(symbols))
        self._start_intraday_loader(symbols)

    def _on_screener_results_updated(self, entries: list[FilteredStockEntry]) -> None:
        symbols = sorted({e.symbol for e in entries})
        if not symbols:
            _log.info("[Candles] Screener returned no stocks — skipping candle fetch")
            return
        # No ibkr_enabled guard here — the loader tries IBKR first and falls back
        # to yfinance automatically. Historical candle download must run regardless
        # of market hours so strategy indicators have data ready at market open.
        self._start_intraday_loader(symbols)

    def _start_intraday_loader(self, symbols: list[str]) -> None:
        loader_busy = self._intraday_loader is not None and self._intraday_loader.isRunning()
        readiness_busy = (
            self._readiness_worker is not None and self._readiness_worker.isRunning()
        )
        if loader_busy or readiness_busy:
            if self._pending_candle_symbols is not None:
                _log.warning(
                    "[Candles] Previous queued batch (%d stocks) replaced with new batch"
                    " (%d stocks)",
                    len(self._pending_candle_symbols), len(symbols),
                )
            self._pending_candle_symbols = symbols
            _log.warning(
                "[Candles] Download already in progress — %d stock(s) queued for next run",
                len(symbols),
            )
            return

        # Disconnect the outgoing loader before replacing it so stale signals
        # from the previous cycle cannot fire into the new one.
        if self._intraday_loader is not None:
            try:
                self._intraday_loader.load_progress.disconnect(self.intraday_load_progress)
                self._intraday_loader.load_complete.disconnect(self._on_candle_load_complete)
            except RuntimeError:
                pass  # already disconnected (e.g. worker finished and cleaned up)

        # Disconnect the outgoing readiness worker for the same reason.
        if self._readiness_worker is not None:
            try:
                self._readiness_worker.done.disconnect()
            except RuntimeError:
                pass

        from us_swing.config.settings import DataConfig
        from us_swing.data.providers.dummy_provider import DummyProvider
        from us_swing.data.engine import HistoricalDataEngine
        from us_swing.db.manager import DatabaseManager
        from us_swing.execution.intraday_candle_loader import IntradayCandleLoader

        cfg = self._system_cfg
        db = DatabaseManager(f"sqlite:///{_CANDLE_DB_PATH}")
        db.create_schema()
        hist = HistoricalDataEngine(DummyProvider(), db, DataConfig())
        loader = IntradayCandleLoader(
            symbols=symbols,
            ibkr_host=cfg.ibkr_host,
            ibkr_port=cfg.ibkr_port,
            ibkr_client_id=cfg.ibkr_intraday_client_id,
            db=db,
            hist_engine=hist,
            parent=self,
        )
        loader.load_progress.connect(self.intraday_load_progress)
        loader.load_complete.connect(self._on_candle_load_complete)
        self._intraday_loader = loader

        # Run the readiness check first (its own DB connection), then start the
        # loader only after _on_readiness_done fires. This guarantees the initial
        # ✓/⟳ state always reaches the Candles column before the download begins,
        # eliminating any signal ordering race between the two workers.
        # `loader` is captured in the lambda so the callback always starts the
        # exact loader that was queued here, not whatever self._intraday_loader
        # happens to point to when the callback fires (TOCTOU fix).
        readiness_worker = _ReadinessWorker(_CANDLE_DB_PATH, symbols, parent=self)
        readiness_worker.done.connect(
            lambda result, _l=loader: self._on_readiness_done(result, _l)
        )
        self._readiness_worker = readiness_worker
        readiness_worker.finished.connect(lambda: setattr(self, "_readiness_worker", None))
        loader.finished.connect(lambda: setattr(self, "_intraday_loader", None))
        readiness_worker.start()
        _log.info("[Candles] Starting download for %d stock(s)", len(symbols))

    def _on_readiness_done(
        self, result: dict[str, bool | None], loader: IntradayCandleLoader
    ) -> None:
        """Receives pre-load DB readiness state and starts the captured loader."""
        self.candle_readiness_updated.emit(result)
        ready_n = sum(1 for v in result.values() if v is True)
        total_n = len(result)
        _log.info(
            "[Candles] Pre-download check: %d of %d stock(s) already have sufficient history",
            ready_n, total_n,
        )
        if loader is not self._intraday_loader:
            _log.warning(
                "[Candles] Readiness check completed but download batch was already"
                " replaced — skipping stale start"
            )
            return
        if not loader.isRunning():
            loader.start()

    def _on_candle_load_complete(self, results: list) -> None:
        readiness: dict[str, bool | None] = {r.symbol: r.ok for r in results}
        self.candle_readiness_updated.emit(readiness)

        unavail = {r.symbol for r in results if r.reason == "EXCHANGE_UNAVAILABLE"}
        if unavail != self._exchange_unavailable_symbols:
            self._exchange_unavailable_symbols = unavail
            self.exchange_unavail_updated.emit(unavail)

        failed = [r.symbol for r in results if not r.ok and r.reason != "EXCHANGE_UNAVAILABLE"]
        ok_n = len(results) - len(failed) - len(unavail)
        if unavail:
            _log.info("[Candles] %d position(s) skipped — not on US exchanges", len(unavail))
        if failed:
            _log.warning(
                "[Candles] %d stock(s) failed to download: %s", len(failed), failed
            )
        elif not unavail:
            _log.info("[Candles] All %d stock(s) are ready for strategy indicators", ok_n)
        pending = self._pending_candle_symbols
        if pending is not None:
            self._pending_candle_symbols = None
            self._start_intraday_loader(pending)

    def shutdown(self) -> None:
        """Stop background threads before app exit to avoid QThread destroy warnings."""
        self._stop_live_session()
        for thread in (self._readiness_worker, self._intraday_loader):
            if thread is not None and thread.isRunning():
                thread.quit()
                thread.wait(5000)

    def get_pending_signals(self, user_id: int | None = None) -> list[TradeSignal]:
        return list(self._signals)

    # ── Position mutations ────────────────────────────────────────────────────

    def close_position(self, symbol: str, user_id: int | None = None) -> None:
        uid = user_id if user_id is not None else self._active_uid
        for p in self._positions:
            if p.symbol == symbol and p.user_id == uid and p.state != "CLOSED":
                p.state = "CLOSED"
                pnl = p.unrealised_pnl
                u = self.get_user_by_id(uid)
                self.log_message.emit(
                    "INFO",
                    f"[{u.username if u else f'user#{uid}'}] Closed: {symbol}"
                    f"  qty={p.quantity}  exit={p.current_price:.2f}  PnL={pnl:+.2f}",
                )
                self.positions_updated.emit()
                self.account_updated.emit()
                return

    def partial_close_position(self, symbol: str, qty: int, user_id: int | None = None) -> None:
        uid = user_id if user_id is not None else self._active_uid
        for p in self._positions:
            if p.symbol == symbol and p.user_id == uid and p.state != "CLOSED":
                qty = min(qty, p.quantity)
                pnl = (p.current_price - p.average_price) * qty
                p.quantity        -= qty
                p.filled_quantity  = p.quantity
                p.total_quantity   = p.quantity
                p.state            = "CLOSED" if p.quantity <= 0 else "PARTIAL_EXIT"
                self.log_message.emit(
                    "INFO",
                    f"Partial close: {symbol}  closed={qty}"
                    f"  remaining={p.quantity}  exit={p.current_price:.2f}  PnL={pnl:+.2f}",
                )
                self.positions_updated.emit()
                self.account_updated.emit()
                return

    def set_stop_loss(self, symbol: str, price: float, user_id: int | None = None,
                      trailing: bool = False, trail_by: str = "", trail_val: float = 0.0) -> None:
        uid = user_id if user_id is not None else self._active_uid
        for p in self._positions:
            if p.symbol == symbol and p.user_id == uid and p.state != "CLOSED":
                old_sl    = p.stop_loss
                p.stop_loss = price
                if trailing:
                    self.log_message.emit(
                        "INFO",
                        f"Trailing SL set: {symbol}  price={price:.2f}"
                        f"  trail_by='{trail_by}'  trail_val={trail_val}  (prev={old_sl:.2f})",
                    )
                else:
                    self.log_message.emit(
                        "INFO",
                        f"Stop loss updated: {symbol}  SL={price:.2f}  (prev={old_sl:.2f})",
                    )
                self.positions_updated.emit()
                return

    def execute_signal(self, signal: TradeSignal, quantity: int) -> int:
        """Simulate an order locally (execution disabled at tool level — no IBKR call).

        Returns a locally-generated placeholder order ID.
        Paper mode: algo-side simulation only; no orders reach the broker.
        """
        order_id = random.randint(10_000, 99_999)
        self.log_message.emit(
            "INFO",
            f"[ALGO-PAPER] Order simulated locally: {signal.symbol}  {signal.side}"
            f"  qty={quantity}  strategy={signal.strategy_id}  order_id={order_id}"
            "  (execution disabled — not sent to broker)",
        )
        return order_id

    # ── User CRUD ─────────────────────────────────────────────────────────────

    def add_user(self, profile: UserProfile) -> UserProfile:
        new_profile = UserProfile(
            user_id         = next_user_id(self._users),
            username        = profile.username,
            display_name    = profile.display_name,
            ibkr_client_id  = profile.ibkr_client_id,
            mode            = profile.mode,
            risk_config     = profile.risk_config,
            strategy_config = profile.strategy_config,
            screener_config = profile.screener_config,
        )
        self._users.append(new_profile)
        save_users(self._users)
        self.users_changed.emit()
        return new_profile

    def update_user(self, profile: UserProfile) -> None:
        for i, u in enumerate(self._users):
            if u.user_id == profile.user_id:
                self._users[i] = profile
                break
        save_users(self._users)
        self.users_changed.emit()

    def delete_user(self, user_id: int) -> str | None:
        if user_id == self._active_uid:
            return "Cannot delete the active user."
        self._users = [u for u in self._users if u.user_id != user_id]
        save_users(self._users)
        self.users_changed.emit()
        return None

    # ── System config ─────────────────────────────────────────────────────────

    def get_system_config(self) -> SystemConfig:
        return self._system_cfg

    def save_system_config(self, cfg: SystemConfig) -> None:
        from us_swing.gui.system_store import save_system_config
        save_system_config(cfg)
        self._system_cfg = cfg
        self.log_message.emit("INFO", "System config saved.")

    # ── Feed connection ───────────────────────────────────────────────────────

    def connect_feed(self) -> None:
        """Initiate paper feed connection to IBKR TWS / Gateway.

        Transitions: DISCONNECTED → RECONNECTING → CONNECTED or DISCONNECTED (error).
        Non-blocking: uses QTimer so the UI remains responsive during handshake.

        Architectural failsafe: all callers should check ``connection_status``
        before reading live data::

            if svc.connection_status is not ConnectionStatus.CONNECTED:
                return  # no live data available
        """
        if self._connection_status in (ConnectionStatus.CONNECTED, ConnectionStatus.RECONNECTING):
            return
        self._set_status(ConnectionStatus.RECONNECTING)
        self.log_message.emit(
            "INFO",
            f"[Feed] Connecting to {self._system_cfg.ibkr_host}:{self._system_cfg.ibkr_port} …",
        )
        QTimer.singleShot(200, self._attempt_connect)

    def disconnect_feed(self) -> None:
        """Cleanly disconnect from the data feed."""
        self._acct_timer.stop()
        self._watch_timer.stop()
        self._stop_live_session()
        self._ibkr_acct      = None
        self._ibkr_positions = []
        self._set_status(ConnectionStatus.DISCONNECTED)
        self.account_updated.emit()
        self.positions_updated.emit()
        self.log_message.emit("INFO", "[Feed] Data feed disconnected.")

    # ── IBKR live account data ────────────────────────────────────────────────

    def _refresh_account_data(self) -> None:
        """Spawn _AccountDataWorker to read live equity + positions from IBKR."""
        if self._connection_status is not ConnectionStatus.CONNECTED:
            return
        if self._acct_worker and self._acct_worker.isRunning():
            return  # previous fetch still in progress
        client_id = self._system_cfg.ibkr_system_client_id + 1
        self._acct_worker = _AccountDataWorker(
            self._system_cfg.ibkr_host, self._system_cfg.ibkr_port, client_id
        )
        self._acct_worker.done.connect(self._on_account_data_ready)
        self._acct_worker.failed.connect(self._on_account_data_failed)
        self._acct_worker.start()

    def _on_account_data_ready(self, acct: AccountState, positions: list) -> None:
        self._ibkr_acct = acct
        self._ibkr_positions = list(positions)
        self._sync_live_subscriptions()
        self.account_updated.emit()
        self.positions_updated.emit()

    def _on_account_data_failed(self, reason: str) -> None:
        self.log_message.emit(
            "WARNING",
            f"[Account] Failed to read IBKR account data: {reason}",
        )

    def _attempt_connect(self) -> None:
        """Spawn a background TCP probe; result handled by _on_connect_ok / _on_connect_fail."""
        host = self._system_cfg.ibkr_host
        port = self._system_cfg.ibkr_port
        self._worker = _ConnectWorker(host, port)
        self._worker.succeeded.connect(self._on_connect_ok)
        self._worker.failed.connect(self._on_connect_fail)
        self._worker.start()

    def _on_connect_ok(self) -> None:
        host = self._system_cfg.ibkr_host
        port = self._system_cfg.ibkr_port
        self._set_status(ConnectionStatus.CONNECTED)
        self.log_message.emit(
            "INFO",
            f"[Feed] Connected to IBKR at {host}:{port} — read-only account monitoring active. "
            "Execution is disabled at tool level.",
        )
        self._start_live_session()
        self._acct_timer.start()
        self._refresh_account_data()   # immediate first fetch
        self._watch_timer.start()
        self._mw_log_on_next_fetch = True   # log symbol data once after connect
        self._refresh_market_watch()   # immediate first fetch
        if self._watchlist:
            self._wl_timer.start()
            self._refresh_watchlist()

    def _on_connect_fail(self, reason: str) -> None:
        host = self._system_cfg.ibkr_host
        port = self._system_cfg.ibkr_port
        self._set_status(ConnectionStatus.DISCONNECTED)
        self.log_message.emit(
            "WARNING",
            f"[Feed] Cannot reach IBKR Gateway at {host}:{port}. "
            "Please start IBKR TWS or Gateway and try again.",
        )

    def _set_status(self, status: ConnectionStatus) -> None:
        self._connection_status = status
        self.feed_status_changed.emit(status.value)

    # ── Internet connectivity ─────────────────────────────────────────────────

    def is_internet_online(self) -> bool:
        """Return current internet reachability (last-known probe result)."""
        return self._net_watcher.is_online()

    def _start_live_session(self) -> None:
        if self._live_session and self._live_session.isRunning():
            return
        client_id = self._system_cfg.ibkr_system_client_id + 2
        self._live_session = _IBKRLiveSession(
            self._system_cfg.ibkr_host,
            self._system_cfg.ibkr_port,
            client_id,
            self,
        )
        self._live_session.price_tick.connect(self._on_live_price)
        self._live_session.session_connected.connect(self._on_session_connected)
        self._live_session.start()

    def _stop_live_session(self) -> None:
        if self._live_session:
            # Disconnect signals before stopping so no callbacks fire after cleanup.
            self._live_session.price_tick.disconnect()
            self._live_session.session_connected.disconnect()
            self._live_session.request_stop()   # sets stop_event + wakes loop
            self._live_session.wait(3000)        # loop.stop() makes this near-instant
            self._live_session = None
        self._subscribed_symbols.clear()
        self._price_flush_timer.stop()

    def _sync_live_subscriptions(self) -> None:
        """Diff open-position and watchlist symbols against the current subscription set and update."""
        if not self._live_session or not self._live_session.isRunning():
            return
        wanted: set[str] = (
            {p.symbol for p in self._ibkr_positions}
            | {p.symbol for p in self._positions if p.state != "CLOSED"}
            | {w.symbol for w in self._watchlist}
        )
        to_sub   = wanted - self._subscribed_symbols
        to_unsub = self._subscribed_symbols - wanted
        if to_sub:
            self._live_session.subscribe_symbols(to_sub)
            self._subscribed_symbols |= to_sub
        if to_unsub:
            self._live_session.unsubscribe_symbols(to_unsub)
            self._subscribed_symbols -= to_unsub

    def _on_session_connected(self) -> None:
        self.log_message.emit("INFO", "[Feed] Position prices streaming live")
        # The IB session's ticker_map was cleared on the previous disconnect, so
        # reset our subscription tracking and re-subscribe all current positions.
        self._subscribed_symbols.clear()
        self._sync_live_subscriptions()

    def _on_live_price(self, symbol: str, price: float) -> None:
        # Buffer incoming ticks and flush to positions at most every 500 ms
        # to avoid repainting the positions table on every individual tick.
        self._pending_prices[symbol] = price
        if not self._price_flush_timer.isActive():
            self._price_flush_timer.start()

    def _flush_pending_prices(self) -> None:
        if not self._pending_prices:
            return
        prices = self._pending_prices
        self._pending_prices = {}
        updated = False
        for p in self._positions:
            if p.state != "CLOSED" and p.symbol in prices:
                p.current_price = prices[p.symbol]
                updated = True
        for p in self._ibkr_positions:
            if p.symbol in prices:
                p.current_price = prices[p.symbol]
                updated = True
        if updated:
            self.positions_updated.emit()
        wl_updated = False
        for item in self._watchlist:
            if item.symbol in prices:
                item.ltp = prices[item.symbol]
                item.change = item.ltp - item.prev_close
                item.change_pct = (
                    (item.change / item.prev_close * 100) if item.prev_close else 0.0
                )
                wl_updated = True
        if wl_updated:
            self.watchlist_updated.emit()

    def _on_internet_status(self, online: bool) -> None:
        """Called by NetWatcher when reachability flips."""
        self.internet_status_changed.emit(online)
        if online:
            self.log_message.emit("INFO", "[Network] Internet connectivity restored.")
            # Auto-reconnect IBKR feed if it was active before the outage.
            if self._was_feed_connected and \
                    self._connection_status is ConnectionStatus.DISCONNECTED:
                self.log_message.emit(
                    "INFO",
                    "[Network] Reconnecting data feed automatically…",
                )
                self.connect_feed()
        else:
            self.log_message.emit(
                "WARNING",
                "[Network] ⚠  Internet connection lost — market data paused.",
            )
            # Remember whether feed was active so we can restore it later.
            self._was_feed_connected = (
                self._connection_status is ConnectionStatus.CONNECTED
            )

    # ── Market Watch ─────────────────────────────────────────────────────────

    def get_market_watch(self) -> list[MarketWatchItem]:
        """Return current Market Watch items (up to 3)."""
        return list(self._watch)

    def set_market_watch_symbols(self, items: list[tuple[str, str]]) -> None:
        """Replace watch list.  items = [(symbol, display_name), …] max 3."""
        self._watch = [
            MarketWatchItem(sym, name) for sym, name in items[:3]
        ]
        self.market_watch_updated.emit()
        if self._connection_status is ConnectionStatus.CONNECTED:
            self._refresh_market_watch()

    def _refresh_market_watch(self) -> None:
        """Fetch latest quotes for all watch symbols via yfinance (non-blocking via QThread)."""
        if not self._watch:
            return
        symbols = [w.symbol for w in self._watch]
        worker = _MarketWatchWorker(symbols)
        worker.done.connect(self._on_watch_data)
        worker.start()
        self._mw_worker = worker  # keep reference to avoid GC

    def _on_watch_data(self, results: list) -> None:
        lookup = {r["symbol"]: r for r in results}
        for item in self._watch:
            if item.symbol in lookup:
                d = lookup[item.symbol]
                item.ltp        = d["ltp"]
                item.prev_close = d["prev_close"]
                item.change_pct = d["change_pct"]
        self.market_watch_updated.emit()

        if self._mw_log_on_next_fetch:
            self._mw_log_on_next_fetch = False
            mkt_status = self._market_status.get("nyse", "closed")
            _status_label = {
                "open":        "Market OPEN",
                "pre_market":  "Pre-Market",
                "after_hours": "After-Hours",
                "closed":      "Market CLOSED",
            }
            status_str = _status_label.get(mkt_status, mkt_status.capitalize())
            for item in self._watch:
                if item.ltp:
                    sign = "+" if item.change_pct >= 0 else ""
                    ltp_str = f"${item.ltp:,.2f}"
                    chg_str = f"{sign}{item.change_pct:.2f}%"
                else:
                    ltp_str, chg_str = "–", "–"
                log_level = "INFO" if mkt_status == "open" else "WARNING"
                self.log_message.emit(
                    log_level,
                    f"[Market Watch] {item.display_name:<12} {status_str:<14}"
                    f"  LTP {ltp_str:>12}   Change {chg_str}",
                )

    # ── Watchlist ─────────────────────────────────────────────────────────────

    def get_watchlist_items(self) -> list[WatchlistItem]:
        return list(self._watchlist)

    def add_to_watchlist(self, symbol: str) -> None:
        symbol = symbol.upper().strip()
        if not symbol or any(w.symbol == symbol for w in self._watchlist):
            return
        self._watchlist.append(WatchlistItem(symbol=symbol))
        self.watchlist_updated.emit()
        if not self._wl_timer.isActive():
            self._wl_timer.start()
        self._refresh_watchlist()
        self._sync_live_subscriptions()

    def remove_from_watchlist(self, symbol: str) -> None:
        self._watchlist = [w for w in self._watchlist if w.symbol != symbol]
        if not self._watchlist:
            self._wl_timer.stop()
        self.watchlist_updated.emit()
        self._sync_live_subscriptions()

    def _refresh_watchlist(self) -> None:
        if not self._watchlist:
            return
        symbols = [w.symbol for w in self._watchlist]
        worker = _WatchlistQuoteWorker(symbols)
        worker.done.connect(self._on_watchlist_data)
        worker.start()
        self._wl_worker = worker

    def _on_watchlist_data(self, results: list) -> None:
        lookup = {r["symbol"]: r for r in results}
        for item in self._watchlist:
            if item.symbol in lookup:
                d = lookup[item.symbol]
                item.ltp        = d["ltp"]
                item.prev_close = d["prev_close"]
                item.change     = d["change"]
                item.change_pct = d["change_pct"]
                item.day_open   = d["day_open"]
                item.day_high   = d["day_high"]
                item.day_low    = d["day_low"]
                item.volume     = d["volume"]
                item.year_high  = d["year_high"]
                item.year_low   = d["year_low"]
                item.market_cap = d["market_cap"]
        self.watchlist_updated.emit()

    # ── Market status ─────────────────────────────────────────────────────────

    def get_market_status(self) -> dict[str, str]:
        """Return current exchange status dict: {'nyse': status, 'nasdaq': status}.

        Possible status values:
            ``'open'`` — regular trading hours (09:30–16:00 ET)
            ``'pre_market'`` — pre-market session (04:00–09:30 ET)
            ``'after_hours'`` — after-hours session (16:00–20:00 ET)
            ``'closed'`` — market closed (weekends, holidays, overnight)
        """
        return dict(self._market_status)

    def _refresh_market_status(self) -> None:
        """Recompute NYSE/NASDAQ status from current Eastern Time and emit signal.

        Emits a log_message whenever the status transitions so the user sees a
        notification in the log panel (e.g. market opens, closes, pre-market starts).
        """
        _labels = {
            "open":        "🟢 Market OPEN — Regular trading hours (09:30–16:00 ET)",
            "pre_market":  "🟠 Pre-Market session started (04:00–09:30 ET)",
            "after_hours": "🟡 After-Hours session started (16:00–20:00 ET)",
            "closed":      "🔴 Market CLOSED",
        }
        now_et = datetime.datetime.now(_ET)
        status = _get_exchange_status(now_et)
        prev   = self._market_status.get("nyse", "")
        # NYSE and NASDAQ share identical trading hours
        self._market_status = {"nyse": status, "nasdaq": status}
        self.market_status_updated.emit()
        # Only log on state transitions AND only when feed is connected
        if (
            status != prev
            and prev != ""
            and self._connection_status is ConnectionStatus.CONNECTED
        ):
            msg = _labels.get(status, f"Market status: {status}")
            level = "INFO" if status == "open" else "WARNING" if status == "closed" else "INFO"
            self.log_message.emit(level, f"[Market] {msg}")

    # ── S&P 500 universe ──────────────────────────────────────────────────────

    def get_sp500_universe(self) -> list:
        """Return cached S&P 500 records (list of Sp500Record).  May be empty
        on first run before the background check completes."""
        return list(self._sp500)

    def get_sp500_meta(self) -> Sp500Meta:
        """Return Sp500Meta (last_fetched, source, count, is_stale)."""
        from us_swing.universe.store import get_meta
        return get_meta()

    def refresh_sp500_universe(self) -> None:
        """Force-refresh the S&P 500 universe from Wikipedia (runs in QThread)."""
        self._run_sp500_refresh(force=True)

    def _check_sp500_universe(self) -> None:
        """Called once 500 ms after startup — loads cache or triggers download."""
        self._run_sp500_refresh(force=False)

    def _run_sp500_refresh(self, *, force: bool) -> None:
        from us_swing.universe.store import get_meta
        meta = get_meta()
        if not force and not meta.is_stale():
            # Cache is fresh — load synchronously (disk read only, fast)
            from us_swing.universe.store import load_sp500
            self._sp500 = load_sp500()
            self.sp500_updated.emit()
            self.log_message.emit(
                "INFO",
                f"[Universe] S&P 500 loaded from cache — {len(self._sp500)} tickers"
                f"  (last fetched: {meta.age_str()})",
            )
        else:
            # Stale or forced — download in background thread
            worker = _Sp500RefreshWorker(force=force)
            worker.done.connect(self._on_sp500_done)
            worker.failed.connect(self._on_sp500_failed)
            worker.start()
            self._sp500_worker = worker   # keep reference

    def _on_sp500_done(self, records: list) -> None:
        self._sp500 = records
        self.sp500_updated.emit()
        meta = self.get_sp500_meta()
        self.log_message.emit(
            "INFO",
            f"[Universe] S&P 500 refreshed from Wikipedia — {len(records)} tickers"
            f"  (saved to ~/.usswing/sp500_universe.csv)",
        )
        from us_swing.universe.store import ibkr_csv_exists
        if not ibkr_csv_exists():
            self.log_message.emit(
                "WARNING",
                "[Universe] IBKR contract IDs not yet generated. "
                "Run:  python -m us_swing.scripts.qualify_sp500_ibkr",
            )

    def _on_sp500_failed(self, reason: str) -> None:
        self.log_message.emit(
            "WARNING",
            f"[Universe] Could not refresh S&P 500 list — {reason}. "
            "Check network connectivity.",
        )

    # ── Candle database ───────────────────────────────────────────────────────

    def get_last_trading_day(self) -> str:
        """Return the most recent completed NYSE trading day as 'YYYY-MM-DD'."""
        return _compute_last_trading_day().isoformat()

    def get_candle_symbol_coverage(self) -> "dict[str, str | None]":
        """Return {symbol: last_1d_candle_date} from candles.db.

        Fast synchronous read (single GROUP BY query).  Returns an empty dict
        if the database does not exist or cannot be read.
        """
        if not _CANDLE_DB_PATH.exists():
            return {}
        try:
            conn = sqlite3.connect(str(_CANDLE_DB_PATH))
            rows = conn.execute(
                "SELECT symbol, MAX(datetime) FROM price_1d GROUP BY symbol"
            ).fetchall()
            conn.close()
            return {sym: dt[:10] if dt else None for sym, dt in rows}
        except Exception:
            return {}

    def get_candle_symbols(self) -> list[str]:
        """Return sorted list of all symbols that have data in price_1d."""
        if not _CANDLE_DB_PATH.exists():
            return []
        try:
            conn = sqlite3.connect(str(_CANDLE_DB_PATH))
            rows = conn.execute(
                "SELECT DISTINCT symbol FROM price_1d ORDER BY symbol"
            ).fetchall()
            conn.close()
            return [r[0] for r in rows]
        except Exception:
            return []

    def get_candles_bulk(
        self,
        symbols: list[str],
        timeframe: str = "1d",
        limit: int = 200,
    ) -> "dict[str, list[dict]]":
        """Bulk-fetch OHLCV for multiple symbols in one DB round-trip.

        Returns ``{symbol: [{"open": …, "high": …, "low": …, "close": …,
        "volume": …}, …]}`` ordered oldest-first, capped at *limit* bars.
        Missing symbols are absent from the result (not present in DB).
        """
        if not _CANDLE_DB_PATH.exists() or not symbols:
            return {}
        table = "price_1d" if timeframe == "1d" else "price_1w"
        from collections import defaultdict
        grouped: "dict[str, list[dict]]" = defaultdict(list)
        try:
            conn = sqlite3.connect(str(_CANDLE_DB_PATH))
            chunk_size = 500   # stay below SQLite's 999 host-parameter limit
            for i in range(0, len(symbols), chunk_size):
                chunk = symbols[i : i + chunk_size]
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT symbol, datetime, open, high, low, close, volume "
                    f"FROM {table} WHERE symbol IN ({placeholders}) "
                    f"ORDER BY symbol, datetime",
                    chunk,
                ).fetchall()
                for sym, dt, o, h, l, c, v in rows:
                    grouped[sym].append(
                        {"datetime": dt, "open": o or 0.0, "high": h or 0.0,
                         "low": l or 0.0, "close": c or 0.0,
                         "volume": int(v or 0)}
                    )
            conn.close()
        except Exception:
            return {}
        return {sym: bars[-limit:] for sym, bars in grouped.items()}

    def get_candles_for_symbol(
        self,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 500,
    ) -> list[dict]:
        """Return OHLCV rows for *symbol* from candles.db.

        Args:
            symbol:    Ticker symbol (e.g. "AAPL").
            timeframe: "1d" or "1w" — which price table to query.
            limit:     Maximum number of most-recent bars to return.

        Returns:
            List of dicts with keys: time, open, high, low, close, volume.
            ``time`` is a Unix timestamp (seconds) as required by
            TradingView Lightweight Charts.  Returns [] on any error.
        """
        if not _CANDLE_DB_PATH.exists():
            return []
        table = "price_1d" if timeframe == "1d" else "price_1w"
        try:
            conn = sqlite3.connect(str(_CANDLE_DB_PATH))
            rows = conn.execute(
                f"SELECT datetime, open, high, low, close, volume "
                f"FROM {table} WHERE symbol = ? "
                f"ORDER BY datetime DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
            conn.close()
        except Exception:
            return []

        result: list[dict] = []
        for dt_str, o, h, l, c, v in reversed(rows):
            # datetime stored as "YYYY-MM-DD" — convert to Unix timestamp (UTC noon)
            try:
                dt = datetime.datetime.strptime(dt_str[:10], "%Y-%m-%d")
                ts = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
            except ValueError:
                continue
            result.append({"time": ts, "open": o, "high": h, "low": l, "close": c, "volume": v})
        return result

    def get_intraday_candles_for_symbol(
        self,
        symbol: str,
        timeframe: str = "3m",
        limit_1m: int = 10_000,
    ) -> list[dict[str, Any]]:
        """Return aggregated intraday OHLCV rows for *symbol* from price_1m.

        Reads 1-minute bars from candles.db and aggregates to *timeframe*
        (``"3m"`` or ``"15m"``).  Returns an empty list on any error or when
        no 1m data exists for the symbol.

        Args:
            symbol:    Ticker symbol (e.g. "AAPL").
            timeframe: ``"3m"`` or ``"15m"``.
            limit_1m:  Maximum raw 1m rows to fetch before aggregation.

        Returns:
            List of dicts with keys: time, open, high, low, close, volume.
            ``time`` is a Unix timestamp (seconds, UTC) as required by
            TradingView Lightweight Charts.
        """
        _TF_MINUTES: dict[str, int] = {"3m": 3, "15m": 15}
        minutes = _TF_MINUTES.get(timeframe)
        if minutes is None or not _CANDLE_DB_PATH.exists():
            return []
        try:
            conn = sqlite3.connect(str(_CANDLE_DB_PATH))
            rows = conn.execute(
                "SELECT datetime, open, high, low, close, volume "
                "FROM price_1m WHERE symbol = ? "
                "ORDER BY datetime DESC LIMIT ?",
                (symbol, limit_1m),
            ).fetchall()
            conn.close()
        except Exception:
            return []

        if not rows:
            return []

        # Parse and sort ascending
        parsed: list[tuple[int, float, float, float, float, float]] = []
        for dt_str, o, h, lo, c, v in reversed(rows):
            try:
                dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S").replace(
                    tzinfo=datetime.timezone.utc
                )
                ts = int(dt.timestamp())
            except ValueError:
                continue
            parsed.append((ts, float(o or 0), float(h or 0), float(lo or 0), float(c or 0), float(v or 0)))

        # Bucket 1m bars into target-timeframe groups
        groups: dict[int, list[tuple[int, float, float, float, float, float]]] = {}
        for bar in parsed:
            bucket = (bar[0] // 60) // minutes
            groups.setdefault(bucket, []).append(bar)

        result: list[dict[str, Any]] = []
        for bucket in sorted(groups):
            group = groups[bucket]
            if len(group) < minutes:
                continue  # skip incomplete trailing bar
            result.append({
                "time":   group[0][0],
                "open":   group[0][1],
                "high":   max(b[2] for b in group),
                "low":    min(b[3] for b in group),
                "close":  group[-1][4],
                "volume": sum(b[5] for b in group),
            })
        return result

    def refresh_candle_db_status(self) -> None:
        """Trigger a background check of the candle database state.

        Emits ``candle_db_status_changed(CandleDbInfo)`` when complete.
        Safe to call at any time; queues a new worker even if one is running.
        """
        worker = _CandleDbStatusWorker(universe_size=len(self._sp500))
        worker.done.connect(self._on_candle_status_done)
        worker.failed.connect(self._on_candle_status_failed)
        worker.start()
        self._candle_status_worker = worker   # keep reference

    def has_candle_checkpoint(self) -> bool:
        """Return True if an interrupted download checkpoint exists."""
        return _CHECKPOINT_PATH.exists()

    def get_failed_symbols(self) -> "list[str]":
        """Return the persisted list of symbols that failed in the last download."""
        if not _FAILED_SYMBOLS_PATH.exists():
            return []
        try:
            data = json.loads(
                _FAILED_SYMBOLS_PATH.read_text(encoding="utf-8")
            )
            return list(data.get("symbols", []))
        except Exception:
            return []

    def has_failed_symbols(self) -> bool:
        """Return True if a non-empty failed-symbols file exists."""
        return bool(self.get_failed_symbols())

    def clear_failed_symbols(self) -> None:
        """Delete the persisted failed-symbols file."""
        _FAILED_SYMBOLS_PATH.unlink(missing_ok=True)

    def reset_candle_db(self) -> None:
        """Delete the candle DB and all ancillary files, then recreate empty tables.

        Stops any running download first.  After completion emits
        ``candle_db_status_changed`` so the UI refreshes automatically.
        """
        # Stop any in-progress download
        self.stop_candle_download()

        # Delete DB and ancillary files
        _CANDLE_DB_PATH.unlink(missing_ok=True)
        _delete_checkpoint()
        _FAILED_SYMBOLS_PATH.unlink(missing_ok=True)

        # Recreate empty schema
        _CANDLE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_CANDLE_DB_PATH))
        _ensure_candle_tables(conn)
        conn.close()

        self.log_message.emit(
            "INFO",
            "[CandleDB] Database reset — all candle data deleted and schema recreated.",
        )

        # Refresh status so UI reflects the now-empty DB
        self.refresh_candle_db_status()

    def start_candle_download(
        self,
        start_date: datetime.date,
        mode: str = "full",
        symbols: "list[str] | None" = None,
    ) -> None:
        """Start (or resume) a candle download.

        Requires IBKR feed to be CONNECTED (SRD-GUI-006.012).  Checks for an
        existing checkpoint and resumes from the last completed symbol if the
        mode and start_date match (SRD-GUI-006.013).

        Args:
            start_date: First date to fetch (only used in ``"full"`` mode;
                        delta mode computes start from last candle date).
            mode:       ``"full"`` rebuilds from ``start_date``; ``"delta"``
                        extends from the DB's current last candle date;
                        ``"fix"`` re-downloads a specific ``symbols`` list.
            symbols:    When provided (``mode="fix"``), download only these
                        symbols; bypasses universe lookup and checkpoint logic.
        """
        # ── Reset per-run failure accumulator (SRD-GUI-006.015) ──────────────
        self._current_failed = []

        # ── IBKR connection gate (SRD-GUI-006.012) ────────────────────────────
        if self._connection_status is not ConnectionStatus.CONNECTED:
            self.log_message.emit(
                "WARNING",
                "[CandleDB] IBKR Gateway not connected — connect the feed first.",
            )
            self.candle_download_failed.emit("IBKR_NOT_CONNECTED")
            return

        end_date = _compute_last_trading_day()
        resuming = False

        # ── Fix mode: download a specific symbols list directly ───────────────
        if symbols is not None:
            symbols_to_download = symbols
        else:
            # ── Universe must be loaded ───────────────────────────────────────
            all_symbols = [r.symbol for r in self._sp500]
            if not all_symbols:
                self.log_message.emit(
                    "WARNING",
                    "[CandleDB] S&P 500 universe not loaded yet — "
                    "refresh the Universe tab first.",
                )
                self.candle_download_failed.emit("UNIVERSE_NOT_LOADED")
                return

            # Delta mode: start from last known candle date + 1 day
            if mode == "delta":
                last = self._last_known_candle_date()
                if last:
                    start_date = last + datetime.timedelta(days=1)
                    if start_date > end_date:
                        self.log_message.emit(
                            "INFO", "[CandleDB] Delta: database already up to date."
                        )
                        return

            # ── Checkpoint / resume (SRD-GUI-006.013) ────────────────────────
            symbols_to_download = all_symbols
            checkpoint = _load_checkpoint()
            if (
                checkpoint
                and checkpoint["mode"] == mode
                and checkpoint["start_date"] == start_date.isoformat()
            ):
                # Re-verify the last N completed symbols before resuming
                stale = _verify_resume_symbols(checkpoint["symbols_done"], end_date)
                symbols_done_set = set(checkpoint["symbols_done"]) - set(stale)
                symbols_todo = [s for s in all_symbols if s not in symbols_done_set]
                symbols_to_download = symbols_todo
                resuming = True
                self.log_message.emit(
                    "INFO",
                    f"[CandleDB] Resuming download — "
                    f"{len(checkpoint['symbols_done'])} already done, "
                    f"{len(stale)} stale (will re-download), "
                    f"{len(symbols_to_download)} remaining.",
                )
            else:
                # Fresh start — discard any stale checkpoint
                _delete_checkpoint()

        cfg = self._system_cfg
        worker = _CandleDownloadWorker(
            symbols=symbols_to_download,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
            ibkr_host=cfg.ibkr_host,
            ibkr_port=cfg.ibkr_port,
            ibkr_client_id=cfg.ibkr_system_client_id,
            benchmark_symbol=cfg.benchmark_symbol,
        )
        worker.progress.connect(self._on_candle_progress)
        worker.finished.connect(self._on_candle_finished)
        worker.failed.connect(self._on_candle_failed)
        worker.symbol_failed.connect(self._on_candle_symbol_failed)
        worker.start()
        self._candle_dl_worker = worker
        action = "Resuming" if resuming else "Starting"
        self.log_message.emit(
            "INFO",
            f"[CandleDB] {action} download — {len(symbols_to_download)} symbols"
            f"  from {start_date}  to {end_date}  mode={mode}",
        )

    def stop_candle_download(self) -> None:
        """Request a graceful stop of any running download worker.

        Checkpoint is preserved so the download can be resumed later.
        """
        worker = getattr(self, "_candle_dl_worker", None)
        if worker and worker.isRunning():
            worker.request_stop()
            self.log_message.emit(
                "INFO",
                "[CandleDB] Download stop requested — "
                "checkpoint saved for resume.",
            )

    def _last_known_candle_date(self) -> datetime.date | None:
        """Return the most recent date present in price_1d, or None."""
        db_path = _CANDLE_DB_PATH
        if not db_path.exists():
            return None
        try:
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                "SELECT MAX(datetime) FROM price_1d"
            ).fetchone()
            conn.close()
            if row and row[0]:
                return datetime.date.fromisoformat(row[0][:10])
        except Exception:
            pass
        return None

    def _on_candle_status_done(self, info: object) -> None:
        self.candle_db_status_changed.emit(info)

    def _on_candle_status_failed(self, reason: str) -> None:
        self.log_message.emit(
            "WARNING", f"[CandleDB] Status check failed — {reason}"
        )

    def _on_candle_progress(self, symbol: str, done: int, total: int) -> None:
        self.candle_download_progress.emit(symbol, done, total)

    def _on_candle_symbol_failed(self, symbol: str, reason: str) -> None:
        """Accumulate per-symbol failures and broadcast to GUI (SRD-GUI-006.015)."""
        self._current_failed.append(symbol)
        self.candle_symbol_failed.emit(symbol, reason)
        self.log_message.emit(
            "WARNING", f"[CandleDB] Symbol {symbol} failed — {reason}"
        )

    def _on_candle_finished(self, inserted_1d: int, inserted_1w: int) -> None:
        # Persist or clear failed-symbols file (SRD-GUI-006.015)
        if self._current_failed:
            import datetime as _dt
            _FAILED_SYMBOLS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _FAILED_SYMBOLS_PATH.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "symbols": self._current_failed,
                        "created_at": _dt.datetime.now(
                            _dt.timezone.utc
                        ).isoformat(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        else:
            _FAILED_SYMBOLS_PATH.unlink(missing_ok=True)

        self.candle_download_failures.emit(list(self._current_failed))
        self.candle_download_finished.emit(inserted_1d, inserted_1w)
        self.log_message.emit(
            "INFO",
            f"[CandleDB] Download complete — "
            f"{inserted_1d:,} daily bars · {inserted_1w:,} weekly bars inserted."
            + (
                f"  ({len(self._current_failed)} symbols failed)"
                if self._current_failed
                else ""
            ),
        )
        # Auto-refresh status after download
        self.refresh_candle_db_status()

    def _on_candle_failed(self, reason: str) -> None:
        if reason.startswith("IBKR_DISCONNECTED"):
            # Mid-download disconnect — emit paused, not failed (SRD-GUI-006.014)
            self.candle_download_paused.emit(reason)
            self.log_message.emit(
                "WARNING",
                "[CandleDB] Download paused — IBKR connection lost. "
                "Checkpoint saved; reconnect and click Resume.",
            )
        else:
            self.candle_download_failed.emit(reason)
            self.log_message.emit(
                "WARNING", f"[CandleDB] Download failed — {reason}"
            )
