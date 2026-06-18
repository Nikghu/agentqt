"""Module: MD-GUI-000.002 — app_service.py
Parent SRD: SRD-GUI-000.001, SRD-GUI-008.001–SRD-GUI-008.004,
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

Paper trading (algo-side simulation)
─────────────────────────────────────
In paper mode the ``StrategyEngine`` submits orders through ``PaperBroker``,
which fills them synchronously at the signal price without contacting IBKR.
Each fill calls back into ``_on_paper_fill()``, which records the entry/exit
into the ``trade_cycles`` ledger and updates ``positions`` with ``mode='paper'``.
This is an **algo-tool paper mode**, not IBKR Paper Trading.

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
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from us_swing.execution.intraday_candle_loader import IntradayCandleLoader
    from us_swing.execution.live_bar_worker import LiveBarWorker
    from us_swing.execution.live_tick_worker import LiveTickWorker
    from us_swing.universe.store import Sp500Meta

_log = logging.getLogger(__name__)

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from us_swing.data.market_calendar import ET as _ET, get_exchange_status as _get_exchange_status
from us_swing.monitoring.connectivity import NetWatcher
from us_swing.data.models import (
    AccountState,
    ConnectionStatus,
    FilteredStockEntry,
    OHLCVBar,
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

# Lifecycle service — see FO-EXE-009 / FO-EXE-010.  Imported eagerly because the
# Protocols and DTOs are pure-Python and add no GUI dependency.
from us_swing.core.monitoring_session import (
    MonitoringCommand,
    MonitoringEventBus,
    MonitoringQuery,
    ReconcileCompleted,
    build_default_service,
    build_scheduler,
    wire_cycle_ledger_projection,
)


@dataclass(frozen=True)
class _ScreenerLifecycleAdapter:
    """Duck-typed adapter exposing the fields
    ``MonitoringSessionService.on_screener_results`` reads off a
    ``ScreenerRunResult``: ``preset_id``, ``run_timestamp``, ``results``.
    """
    preset_id:     str
    run_timestamp: str
    results:       dict[str, dict[str, Any]]


class _AppEventStream:
    """SRD-GUI-014.014 — single-callback sink that bridges typed lifecycle bus
    + Qt strategy bus into one ``subscribe(handler)`` API for the Active Trades panel.
    """

    __slots__ = ("_subscribers", "__weakref__")

    def __init__(self, *, lifecycle_bus: Any, strategy_bus: Any) -> None:
        self._subscribers: list[Callable[[object], None]] = []

        if lifecycle_bus is not None:
            from us_swing.execution.trade_cycle import (
                CycleAborted,
                CycleClosed,
                CycleClosing,
                CycleOpened,
                CycleUpdated,
                RiskUpdated,
            )
            for evt_type in (CycleOpened, CycleUpdated, CycleClosing,
                             CycleClosed, CycleAborted, RiskUpdated):
                lifecycle_bus.subscribe(evt_type, self._forward)

        if strategy_bus is not None and hasattr(strategy_bus, "event_published"):
            strategy_bus.event_published.connect(self._forward)

    def subscribe(self, handler: Callable[[object], None]) -> None:
        self._subscribers.append(handler)

    def _forward(self, event: object) -> None:
        for handler in list(self._subscribers):
            try:
                handler(event)
            except Exception:
                _log.exception("[EventStream] subscriber raised on %s",
                               type(event).__name__)


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


# ── Background worker: intraday chart read ───────────────────────────────────

class _IntradayCandleWorker(QThread):
    """Reads intraday candles off the GUI thread for the chart pane.

    Wraps :meth:`AppService.get_intraday_candles_for_symbol` so the heavy
    SQLite read + Python aggregation never blocks the Qt event loop. Emits the
    requesting ``symbol`` and ``timeframe`` back with the result so the chart
    pane can drop a result that arrived after the user switched symbols.
    """

    done = pyqtSignal(str, str, object)   # symbol, timeframe, list[dict]

    def __init__(self, svc: AppService, symbol: str, timeframe: str) -> None:
        super().__init__()
        self._svc = svc
        self._symbol = symbol
        self._timeframe = timeframe

    def run(self) -> None:
        try:
            candles = self._svc.get_intraday_candles_for_symbol(self._symbol, self._timeframe)
        except Exception:
            candles = []
        self.done.emit(self._symbol, self._timeframe, candles)


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

# ── Live tick streaming — index symbol translation ────────────────────────────

# Yahoo Finance notation → ETF proxy for IBKR tick subscriptions.
_MAX_TICK_SUBS: int = 95  # leave headroom below IBKR's ~100-line L1 limit


def _make_stk_contract(symbol: str) -> Any:
    """Return an ib_insync Stock contract for an S&P 500 equity symbol."""
    try:
        from ib_insync import Stock  # noqa: PLC0415
        return Stock(symbol.replace(".", " "), "SMART", "USD")
    except ImportError:
        return None


def _make_ind_contract(ibkr_symbol: str, exchange: str) -> Any:
    """Return an ib_insync Index contract for a Market Watch index symbol."""
    try:
        from ib_insync import Index  # noqa: PLC0415
        return Index(ibkr_symbol, exchange, "USD")
    except ImportError:
        return None


# ── Market Watch — fixed index ETF proxies ─────────────────────────────────────

_MW_SYMBOLS: list[tuple[str, str]] = [
    ("SPY", "S&P 500"),
    ("QQQ", "NASDAQ-100"),
    ("DIA", "Dow Jones"),
    ("IWM", "Russell 2000"),
]


# ── Risk position source ──────────────────────────────────────────────────────

class _CyclePositionSource:
    """Adapts open `trade_cycles` to the `RiskManager` position-source protocol."""

    def __init__(self, query: Any) -> None:
        self._query = query

    def get_all(self, user_id: int) -> list[OpenPosition]:
        if self._query is None:
            return []
        return [
            OpenPosition(
                symbol        = c.symbol,
                user_id       = c.user_id,
                quantity      = c.entry_qty,
                average_price = c.entry_price,
                stop_loss     = c.hard_stop_loss,
                target_price  = c.target_price or 0.0,
                mode          = "paper",
                strategy_id   = c.strategy_id,
            )
            for c in self._query.open_cycles()
            if c.user_id == user_id
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
    live_bar_data_updated     = pyqtSignal(str)            # symbol — 3m or 15m bar written to DB
    pending_signals_updated   = pyqtSignal()               # pending signal list changed
    pending_tick              = pyqtSignal(str, float)      # (symbol, price) — live LTP for pending rows
    strategy_status_changed   = pyqtSignal(str, str)       # (strategy_name, "entered"|"exited") — refresh nudge
    circuit_breaker_changed   = pyqtSignal(bool)           # True = breaker tripped (entries blocked)
    risk_warning_raised       = pyqtSignal(str, str)       # (kind, message) — advisory, non-blocking
    _auto_exit_requested      = pyqtSignal(int, str)       # (cycle_id, reason) — cross-thread marshal
    _arm_candle_feeds_requested = pyqtSignal(object)       # list[str] — cross-thread marshal (ISS-EXE-0009)
    _clear_pending_exits_requested = pyqtSignal(str, str)  # (strategy_id, symbol) — marshal (ISS-EXE-0010)

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
        self._circuit_breaker_active = False
        self._effective_capital_cache: float = 0.0
        self._daily_loss_warned = False
        self._margin_drift_warned = False
        self._cycle_position_source: Any = None

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
        self._mw_items: list[WatchlistItem] = [
            WatchlistItem(symbol=sym) for sym, _ in _MW_SYMBOLS
        ]
        self._mw_worker: _WatchlistQuoteWorker | None = None

        # ── Watchlist ─────────────────────────────────────────────────────────
        self._watchlist: list[WatchlistItem] = []
        self._wl_worker: _WatchlistQuoteWorker | None = None

        # ── Live tick worker (FO-GUI-012) ─────────────────────────────────────
        self._tick_worker: LiveTickWorker | None = None
        self._sp500_cache: set[str] = set()   # S&P 500 symbols, populated lazily
        self._cycle_symbols: frozenset[str] = frozenset()  # symbols of open trade cycles
        self._pending_exit_reason: str = "manual"          # reason carried into the next exit fill

        # ── Live bar worker — must be initialised before _refresh_market_status ─
        self._live_bar_worker: LiveBarWorker | None = None
        self._filtered_symbols: list[str] = []

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
        self._exec_candle_src: tuple[DatabaseManager, HistoricalDataEngine] | None = None

        # ── Monitoring session lifecycle (FO-EXE-009 / FO-EXE-010) ───────────
        # Service is built eagerly here so the SQLAlchemy engine + event bus
        # are available for the FO-EXE-012 trade-cycle service below.  The
        # lifecycle service itself is otherwise dormant until screener
        # results arrive.
        self._db:                  Any                = None
        self._db_engine:           Any                = None
        self._lifecycle_query:     MonitoringQuery    | None = None
        self._lifecycle_command:   MonitoringCommand  | None = None
        self._lifecycle_bus:       MonitoringEventBus | None = None
        self._lifecycle_scheduler: Any                | None = None
        self._lifecycle_last_run:  datetime.date      | None = None
        self._tc_query:            Any                = None
        self._tc_command:          Any                = None
        self._rex_counters:        Any                = None
        # Order pipeline (Broker_fix Phase 5): SimBroker → OrderIngestion via
        # the BrokerAdapter submitter.  Falls back to PaperBroker if the DB /
        # trade-cycle service is unavailable.
        self._broker:              Any                = None
        self._order_ingestion:     Any                = None
        self._broker_adapter:      Any                = None
        self._submitter:           Any                = None

        self.screener_results_updated.connect(self._on_screener_results_updated)
        # Trigger candle fetch for any results that were saved from a prior screener run.
        QTimer.singleShot(0, self._boot_candle_check)

        # Eagerly build engine + bus + trade-cycle service before strategy engine.
        # _on_paper_fill needs the trade-cycle command to persist entries.
        if self._ensure_lifecycle_service():
            try:
                from us_swing.execution.trade_cycle import (
                    build_default_service as build_tc_service,
                )
                self._tc_query, self._tc_command = build_tc_service(
                    self._db_engine,
                    self._lifecycle_bus,
                    set_active_symbols=self._on_cycle_symbols_changed,
                )
                # Background loop for tick-driven trail-stop bookkeeping.
                self._tc_command.start()
                # Re-attach accumulators for any cycles that survived restart.
                self._tc_command.reload()
                # Auto-exit: target/SL/trailing triggers fire on the cycle
                # background thread; marshal the SELL submit to the GUI thread.
                from us_swing.execution.trade_cycle import ExitTrigger
                self._auto_exit_requested.connect(self._handle_auto_exit)
                # Cycle-open candle-feed arming: _on_cycle_symbols_changed fires
                # on the cycle background thread; marshal the loader + live-bar
                # resubscribe to the GUI thread (ISS-EXE-0009).
                self._arm_candle_feeds_requested.connect(self._arm_candle_feeds)
                self._lifecycle_bus.subscribe(ExitTrigger, self._on_exit_trigger)
                _log.info("[TradeCycle] Service ready")
            except Exception:
                _log.exception("[TradeCycle] Service init failed")

            try:
                from us_swing.execution.strategy_engine import RexCounterRepository
                self._rex_counters = RexCounterRepository(self._db_engine)
                _log.info("[Strategy] Rex counter repository ready")
            except Exception:
                _log.exception("[Strategy] Rex counter init failed")

        # ── Strategy Engine ───────────────────────────────────────────────────
        from us_swing.execution.pending_signal_store import PendingSignalStore
        from us_swing.execution.event_bus import QtEventBus
        from us_swing.execution.strategy_engine._engine import StrategyEngine
        from us_swing.gui.strategy_builder_dialog import load_strategies, save_strategies

        # Restore positions + trade history from the trade-cycle ledger.
        self._rehydrate_positions_from_cycles()

        self._pending_store = PendingSignalStore(self)
        self._pending_store.pending_signal_added.connect(lambda _: self.pending_signals_updated.emit())
        self._pending_store.pending_signal_removed.connect(lambda _: self.pending_signals_updated.emit())
        self._pending_store.pending_signal_dismissed.connect(lambda _: self.pending_signals_updated.emit())
        self._pending_store.pending_signal_executed.connect(lambda _: self.pending_signals_updated.emit())
        # A pending symbol needs a live tick so its row shows an LTP and the
        # MARKET entry fills at the real price, not the frozen signal price.
        self._pending_store.pending_signal_added.connect(lambda _: self._sync_tick_subscriptions())
        self._pending_store.pending_signal_removed.connect(lambda _: self._sync_tick_subscriptions())
        self._pending_store.pending_signal_dismissed.connect(lambda _: self._sync_tick_subscriptions())
        self._pending_store.pending_signal_executed.connect(lambda _: self._sync_tick_subscriptions())

        # A position closed by any route (force-exit, tick exit, square-off) must
        # drop any stale pending exit signal so the user cannot fire a duplicate
        # exit from the Active Trades ► button (ISS-EXE-0010). CycleClosed fires on
        # the cycle thread; marshal the clear to the GUI thread.
        if self._lifecycle_bus is not None:
            from us_swing.execution.trade_cycle import CycleClosed
            self._clear_pending_exits_requested.connect(self._clear_pending_exits)
            self._lifecycle_bus.subscribe(CycleClosed, self._on_cycle_closed_clear_pending)

        self._event_bus = QtEventBus(self)

        # Latest live tick price per symbol — the SimBroker fills paper market
        # orders at this market price instead of a caller-supplied reference
        # (SRD-INF-009.007). Written on the GUI thread from the tick signal and
        # read on the engine thread inside place_order, so guard both with a lock.
        self._last_tick_price: dict[str, float] = {}
        self._last_tick_price_lock = threading.Lock()

        # Order submitter: the new broker pipeline when the DB + trade-cycle
        # service are available; otherwise the legacy in-memory PaperBroker so
        # the app still runs without a candle DB.
        if self._db is not None and self._tc_command is not None:
            from us_swing.execution.broker_adapter import BrokerAdapter
            from us_swing.execution.broker_factory import build_broker
            from us_swing.execution.order_ingestion import OrderIngestion

            # Mode + broker are hard-coded until the Settings UI lands; the
            # factory already routes live/IBKR so only these two values change.
            self._broker = build_broker(
                mode="paper",
                broker_name="IBKR",
                scheduler=self._schedule_on_engine_loop,
                live_client_provider=self._live_order_client,
                price_provider=self._market_price_for,
            )
            self._order_ingestion = OrderIngestion(
                ledger=self._db,
                fill_sink=lambda fill: self._strategy_engine.on_order_fill(fill),
                cycles=self._tc_command,
                lifecycle=self._lifecycle_command,
            )
            self._broker_adapter = BrokerAdapter(
                broker=self._broker,
                ingestion=self._order_ingestion,
                config_provider=self._strategy_cfg,
                user_id_provider=lambda: self._active_uid,
                session_date_provider=lambda: datetime.datetime.now().strftime("%Y-%m-%d"),
                mode_provider=lambda: "paper",            # Phase 6 wires real user mode
                exit_reason_provider=lambda: self._pending_exit_reason,
                on_event=self._on_order_event_gui,
            )
            self._submitter = self._broker_adapter
            _log.info("[Orders] Broker pipeline ready (SimBroker → trades ledger)")
        else:
            self._submitter = None
            _log.error("[Orders] Order submission unavailable — trade-cycle service or database not ready")

        from us_swing.execution.risk_manager import RiskManager
        self._cycle_position_source = _CyclePositionSource(self._tc_query)
        self._risk_manager = RiskManager(
            config=self.get_active_user().risk_config,
            account_provider=lambda: self.get_account_state(self._active_uid),
            cb_state_provider=lambda: self._circuit_breaker_active,
            user_id=self._active_uid,
            tracker=self._cycle_position_source,
            effective_capital_provider=self.effective_capital,
            warning_sink=lambda w: self._event_bus.publish(w),
        )

        self._strategy_engine = StrategyEngine(
            registry_loader=load_strategies,
            registry_saver=save_strategies,
            candles_provider=self._get_candles_df,
            bar_provider=self._get_latest_bar,
            risk=self._risk_manager,
            submitter=self._submitter,
            pending=self._pending_store,
            bus=self._event_bus,
            rex_counters=self._rex_counters,
            symbols_provider=lambda: list(self._filtered_symbols),
            cycle_query=self._tc_query,
            user_id_provider=lambda: self._active_uid,
            effective_capital_provider=self.effective_capital,
            parent=self,
        )
        self._strategy_engine.start()
        self._event_bus.event_published.connect(self._on_strategy_event)
        self.live_bar_data_updated.connect(self._strategy_engine.on_candle_closed)

        self._event_stream = _AppEventStream(
            lifecycle_bus=self._lifecycle_bus,
            strategy_bus=self._event_bus,
        )

    # ── Architecture-level connection status ──────────────────────────────────

    @property
    def rex_counters(self) -> Any:
        """`RexCounterRepository` exposing per-(strategy, symbol) re-execution counters."""
        return self._rex_counters

    @property
    def event_stream(self) -> "_AppEventStream":
        """Unified single-callback event sink for the Active Trades panel (SRD-GUI-014.014)."""
        return self._event_stream

    @property
    def cycle_query(self) -> Any:
        """FO-EXE-012 `TradeCycleQuery` for live cycle reads."""
        return self._tc_query

    @property
    def cycle_cmd(self) -> Any:
        """FO-EXE-012 `TradeCycleCommand` for live cycle mutations."""
        return self._tc_command

    @property
    def pending_store(self) -> Any:
        """FO-EXE-011 `PendingSignalStore` for awaiting-user-action signals."""
        return self._pending_store

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

    @property
    def viewing_uid(self) -> int | None:
        """Admin viewing scope; ``None`` = aggregate all users."""
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
            return [p for p in self._positions if p.quantity > 0]
        return [p for p in self._positions if p.user_id == uid and p.quantity > 0]

    def get_all_trades(self, user_id: int | None = None) -> list[TradeRecord]:
        uid = user_id if user_id is not None else self._viewing_uid
        if uid is None:
            return list(self._trades)
        return [t for t in self._trades if t.user_id == uid]

    def get_account_state(self, user_id: int | None = None) -> AccountState:
        uid = user_id if user_id is not None else self._viewing_uid
        if self._ibkr_acct is not None:
            return self._ibkr_acct
        # Paper / disconnected — seed equity from the user's absolute Max Capital
        # so capital sizing and checks have a budget to work against.
        budget = self._user_max_capital(uid)
        return AccountState(
            user_id             = uid or 0,
            equity              = budget,
            start_of_day_equity = budget,
            open_position_value = self._open_position_value(uid),
            daily_pnl           = 0.0,
            total_cash_value    = budget,
        )

    def _open_position_value(self, uid: int | None) -> float:
        """Deployed capital across the user's open cycles (entry price × qty)."""
        src = getattr(self, "_cycle_position_source", None)
        if src is None:
            return 0.0
        return sum(p.average_price * p.quantity for p in src.get_all(uid or 0))

    def margin_available(self) -> float:
        """Remaining budget = effective capital − deployed open-position value."""
        return max(0.0, self.effective_capital() - self._open_position_value(self._active_uid))

    def _user_max_capital(self, uid: int | None) -> float:
        user = next((u for u in self._users if u.user_id == uid), None)
        if user is None and self._users:
            user = self._users[0]
        return user.risk_config.max_capital_value if user is not None else 0.0

    def effective_capital(self) -> float:
        """Per-user dollar budget for sizing (FO-EXE-017).

        Paper uses the stored Max Capital. Live caps it at 90% of broker cash
        when Max Capital exceeds available cash; the stored setting is unchanged.
        """
        cap = self._user_max_capital(self._active_uid)
        user = self.get_active_user()
        if user.mode != "live" or self._ibkr_acct is None:
            return cap
        cash = self._ibkr_acct.total_cash_value
        if cap > cash:
            return 0.9 * cash
        return cap

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

            # Convert UTC run_timestamp to local HH:MM for display.
            try:
                _dt_utc = datetime.datetime.strptime(
                    result.run_timestamp, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=datetime.timezone.utc)
                run_time = _dt_utc.astimezone().strftime("%H:%M")
            except (ValueError, AttributeError):
                run_time = ""

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
                    time=run_time,
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
        self._lifecycle_record_screener(entries)
        keep_symbols = self._lifecycle_keep_symbols(symbols)
        self._filtered_symbols = keep_symbols
        self._start_intraday_loader(keep_symbols)
        self._lifecycle_reconcile_if_due()
        if self._market_status.get("nyse") == "open":
            self._start_live_bar_worker()

    def _on_screener_results_updated(self, entries: list[FilteredStockEntry]) -> None:
        symbols = sorted({e.symbol for e in entries})
        if not symbols:
            _log.info("[Candles] Screener returned no stocks — skipping candle fetch")
            return
        # FO-EXE-009 — record into the monitoring-session ledger BEFORE
        # triggering downstream consumers so they always see a consistent state.
        self._lifecycle_record_screener(entries)
        keep_symbols = self._lifecycle_keep_symbols(symbols)
        self._filtered_symbols = keep_symbols
        # No ibkr_enabled guard here — the loader tries IBKR first and falls back
        # to yfinance automatically. Historical candle download must run regardless
        # of market hours so strategy indicators have data ready at market open.
        self._start_intraday_loader(keep_symbols)
        # FO-EXE-010 — fire pre-open reconcile if today's run has not yet
        # executed.  The service's internal single-flight guard makes this safe
        # to call from any path.
        self._lifecycle_reconcile_if_due()
        # Restart live bars with the new symbol list if market is currently open.
        if self._market_status.get("nyse") == "open":
            self._start_live_bar_worker()

    # ── Monitoring session lifecycle wiring (FO-EXE-009 / FO-EXE-010) ────────
    #
    # NOTE: the order-fill seam (system fills → MonitoringCommand.on_fill) is
    # NOT wired here.  It will land in execution/execution_engine.py once
    # FO-EXE-001 / FO-EXE-002 are implemented.  Until then no system positions
    # are created, so carryover is always empty and only the screener-handoff
    # and reconcile paths exercise the service.

    def _ensure_lifecycle_service(self) -> bool:
        """Lazily construct the lifecycle service + scheduler.  Returns True if
        the service is available, False if the candle DB cannot be opened.

        Also stores ``self._db_engine`` so callers (e.g. the trade-cycle
        service) can attach to the same SQLAlchemy engine + event bus.
        """
        if self._lifecycle_command is not None:
            return True
        try:
            from us_swing.db.manager import DatabaseManager
        except Exception as exc:                                      # pragma: no cover
            _log.warning("[Lifecycle] Unable to import DB layer: %r", exc)
            return False
        try:
            _CANDLE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            # One DatabaseManager owns the engine; the trade-cycle service and the
            # order-ingestion ledger both share it (no second connection).
            self._db = DatabaseManager(f"sqlite:///{_CANDLE_DB_PATH}")
            self._db.create_schema()
            engine = self._db.engine
            query, command, bus = build_default_service(
                engine,
                filtered_provider = self._lifecycle_filtered_provider,
            )
            scheduler = build_scheduler(
                command       = command,
                bus           = bus,
                cron_register = lambda _expr, _fn: None,  # FO-EXE-010 follow-up
            )
        except Exception as exc:
            _log.warning("[Lifecycle] Service init failed: %r", exc)
            return False
        self._db_engine           = engine
        self._lifecycle_query     = query
        self._lifecycle_command   = command
        self._lifecycle_bus       = bus
        self._lifecycle_scheduler = scheduler
        bus.subscribe(ReconcileCompleted, self._on_lifecycle_reconcile_completed)
        # Project terminal trade-cycle events onto the lifecycle ledger so a
        # symbol's ENTERED row is always flipped to EXITED when its cycle ends,
        # regardless of how it closed. A non-FILLED / 0-share exit and aborts
        # bypass OrderIngestion's own mark_exited, which is what stranded the
        # ledger and produced orphaned ENTERED rows.
        from us_swing.execution.trade_cycle import CycleAborted, CycleClosed
        wire_cycle_ledger_projection(bus, command, (CycleClosed, CycleAborted))
        _log.info("[Lifecycle] Monitoring session service ready")
        return True

    def _lifecycle_filtered_provider(self, _today: datetime.date) -> frozenset[str]:
        """Resolve today's filtered set for ``MonitoringQuery.keep_set``."""
        entries = self.get_latest_screener_results()
        return frozenset(e.symbol for e in entries)

    def _lifecycle_record_screener(self, entries: list[FilteredStockEntry]) -> None:
        """Push screener entries into the monitoring-session ledger."""
        if not entries:
            return
        if not self._ensure_lifecycle_service():
            return
        # Adapter exposing the duck-typed surface
        # ``MonitoringSessionService.on_screener_results`` consumes.  Real
        # `ScreenerRunResult` carries preset_id/run_timestamp; here we derive
        # them from the entries so the integration works before the screener
        # storage layer is wired through.
        screener_name = entries[0].screener_name or "default"
        date_str      = entries[0].date or datetime.date.today().isoformat()
        result = _ScreenerLifecycleAdapter(
            preset_id     = screener_name,
            run_timestamp = f"{date_str}T00:00:00Z",
            results       = {e.symbol: {"passed": True} for e in entries},
        )
        try:
            assert self._lifecycle_command is not None
            self._lifecycle_command.on_screener_results(result)
        except Exception as exc:
            _log.warning("[Lifecycle] on_screener_results failed: %r", exc)

    def _lifecycle_keep_symbols(self, fallback: list[str]) -> list[str]:
        """Return today's keep-set as a sorted list.  Falls back to *fallback*
        if the lifecycle service is unavailable (preserves legacy behaviour)."""
        if self._lifecycle_query is None:
            return fallback
        try:
            keep = self._lifecycle_query.keep_set(datetime.date.today())
        except Exception as exc:
            _log.warning("[Lifecycle] keep_set lookup failed: %r", exc)
            return fallback
        union = keep.filtered | keep.carryover
        return sorted(union) if union else fallback

    def _lifecycle_reconcile_if_due(self) -> None:
        """Run pre-open reconcile via the scheduler's catch-up path.  Single-
        flight protection in the service makes repeated calls safe."""
        if self._lifecycle_scheduler is None:
            return
        today = datetime.date.today()
        if self._lifecycle_last_run == today:
            return
        try:
            report = self._lifecycle_scheduler.maybe_run_on_startup()
        except Exception as exc:
            _log.warning("[Lifecycle] Reconcile catch-up failed: %r", exc)
            return
        if report is not None:
            self._lifecycle_last_run = today

    def _on_lifecycle_reconcile_completed(self, _event: ReconcileCompleted) -> None:
        """Push the post-reconcile keep set into any running live bar worker."""
        if self._live_bar_worker is None or not self._live_bar_worker.isRunning():
            return
        symbols = self._lifecycle_keep_symbols(self._filtered_symbols)
        if symbols == self._filtered_symbols:
            return
        self._filtered_symbols = symbols
        try:
            self._live_bar_worker.set_symbols(symbols)
        except Exception as exc:
            _log.warning("[Lifecycle] LiveBarWorker.set_symbols failed: %r", exc)

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

    # ── Live bar worker (market-hours 5s IBKR → 1m candle feed) ─────────────

    def _start_live_bar_worker(self) -> None:
        """Start (or restart) the live bar worker for the current filtered symbols."""
        self._stop_live_bar_worker()
        if not self._filtered_symbols:
            return
        from us_swing.execution.live_bar_worker import LiveBarWorker  # noqa: PLC0415
        cfg = self._system_cfg
        worker = LiveBarWorker(
            symbols=self._filtered_symbols,
            ibkr_host=cfg.ibkr_host,
            ibkr_port=cfg.ibkr_port,
            ibkr_client_id=cfg.ibkr_live_client_id,
            db_path=str(_CANDLE_DB_PATH),
            parent=self,
        )
        worker.candle_closed.connect(self.live_bar_data_updated)
        self._live_bar_worker = worker
        worker.start()
        _log.info("[Live] Live bar worker started for %d stock(s)", len(self._filtered_symbols))

    def _stop_live_bar_worker(self) -> None:
        """Stop the running live bar worker (no-op if not running)."""
        worker = self._live_bar_worker
        if worker is None:
            return
        self._live_bar_worker = None
        try:
            worker.candle_closed.disconnect()
        except (RuntimeError, TypeError):
            pass
        try:
            worker.finished.disconnect()
        except (RuntimeError, TypeError):
            pass
        worker.request_stop()
        worker.quit()
        worker.wait(15_000)
        _log.info("[Live] Live bar worker stopped")

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
        else:
            _log.info("[Candles] All %d stock(s) are ready for strategy indicators", ok_n)
        pending = self._pending_candle_symbols
        if pending is not None:
            self._pending_candle_symbols = None
            self._start_intraday_loader(pending)

    def _execution_candle_source(
        self,
    ) -> tuple[DatabaseManager, HistoricalDataEngine] | None:
        """Lazily build and cache the candle DB handle + aggregation engine.

        Returns None when the candle database does not yet exist. The
        aggregation engine uses a ``DummyProvider`` because
        ``aggregate_timeframe`` is pure and performs no provider I/O.
        """
        if not _CANDLE_DB_PATH.exists():
            return None
        if self._exec_candle_src is None:
            from us_swing.config.settings import DataConfig
            from us_swing.data.engine import HistoricalDataEngine
            from us_swing.data.providers.dummy_provider import DummyProvider
            from us_swing.db.manager import DatabaseManager
            db = DatabaseManager(f"sqlite:///{_CANDLE_DB_PATH}")
            self._exec_candle_src = (db, HistoricalDataEngine(DummyProvider(), db, DataConfig()))
        return self._exec_candle_src

    def _get_candles_df(self, symbol: str) -> dict[str, pd.DataFrame]:
        """Build 3m/15m frames for *symbol* for strategy evaluation.

        Derives historical depth by aggregating stored 1m bars and merges any
        live 3m/15m bars (SRD-EXE-006.010), so strategies have full history
        without an active live session.
        """
        from us_swing.execution.intraday_candle_loader import load_execution_frames
        src = self._execution_candle_source()
        if src is None:
            return {}
        db, hist = src
        try:
            return load_execution_frames(db, hist, symbol)
        except Exception:
            _log.warning("[Strategy] Failed to load candle frames for %s", symbol)
            return {}

    def _get_latest_bar(self, symbol: str, tf: str) -> OHLCVBar | None:
        """Return the most recent merged bar for *symbol* at *tf* (SRD-EXE-006.010)."""
        from us_swing.execution.intraday_candle_loader import load_latest_execution_bar
        src = self._execution_candle_source()
        if src is None:
            return None
        db, hist = src
        try:
            return load_latest_execution_bar(db, hist, symbol, tf)
        except Exception:
            _log.warning("[Strategy] Failed to load latest bar for %s (%s)", symbol, tf)
            return None

    def get_pending_signals(self, user_id: int | None = None) -> list[TradeSignal]:
        from us_swing.execution.signal_bridge import engine_to_gui
        return [engine_to_gui(s) for s in self._pending_store.list()]

    # ── Position mutations ────────────────────────────────────────────────────

    def close_position(self, symbol: str, user_id: int | None = None) -> None:
        uid = user_id if user_id is not None else self._active_uid
        for p in self._positions:
            if p.symbol == symbol and p.user_id == uid and p.quantity > 0:
                p.quantity = 0
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
            if p.symbol == symbol and p.user_id == uid and p.quantity > 0:
                qty = min(qty, p.quantity)
                pnl = (p.current_price - p.average_price) * qty
                p.quantity        -= qty
                p.filled_quantity  = p.quantity
                p.total_quantity   = p.quantity
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
            if p.symbol == symbol and p.user_id == uid and p.quantity > 0:
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
        """Route the pending signal through PaperBroker and return its order ID."""
        from us_swing.execution.strategy_engine import Action, TradeSignal as EngineSignal
        from us_swing.execution.trade_cycle import TradeCycleState
        if (
            isinstance(signal, EngineSignal)
            and signal.action == Action.EXIT
            and self._tc_query is not None
            and not any(
                s.strategy_id == signal.strategy_id
                and s.symbol == signal.symbol
                and s.state is TradeCycleState.OPEN
                for s in self._tc_query.open_cycles()
            )
        ):
            self._pending_store.dismiss(signal.signal_id)
            self.log_message.emit(
                "WARNING",
                f"[Strategy] Exit signal for {signal.symbol} ignored — position already closed or exiting",
            )
            return -1
        eng_sig = self._pending_store.execute(signal.signal_id)
        if eng_sig is None:
            self.log_message.emit(
                "WARNING",
                f"[Strategy] Signal {signal.signal_id} not found in pending store",
            )
            return -1
        if self._submitter is None:
            _log.error("[Orders] Cannot submit signal — order submission is unavailable")
            return -1
        order_id = self._submitter.submit(eng_sig, quantity) or -1
        return order_id

    def reload_strategy_registry(self) -> None:
        """Reload strategy configurations from disk into the running engine."""
        self._strategy_engine.reload_registry()

    def _live_order_client(self) -> Any:
        """Return the connected order client for live trading.

        Live IBKR ordering is not connected yet (paper-only phase); the broker
        factory only calls this when ``mode='live'``, so it raises a clear error
        until live wiring is added.
        """
        raise RuntimeError(
            "Live order routing is not connected yet — the app is in paper mode"
        )

    def _schedule_on_engine_loop(self, callback: Callable[[], None]) -> None:
        """Scheduler for ``SimBroker``: defer a simulated fill onto the engine's
        asyncio loop so it lands after ``place_order`` / ``on_order_accepted``
        returns, no matter which thread submitted the order."""
        engine = getattr(self, "_strategy_engine", None)
        loop = engine.loop if engine is not None else None
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(callback)
        else:
            callback()

    def _on_order_event_gui(self, event: object) -> None:
        """Refresh GUI position / trade state from the cycle ledger after a
        broker order event.  Runs on the engine loop thread; the Qt signals
        marshal the refresh to the GUI thread."""
        from us_swing.broker.broker import OrderEvent, OrderStatus
        if not isinstance(event, OrderEvent):
            return
        if event.status not in (
            OrderStatus.FILLED,
            OrderStatus.PARTIAL_FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        ):
            return
        try:
            self._rehydrate_positions_from_cycles()
        except Exception:
            _log.exception("[Orders] Failed to refresh positions after order event")
        self.positions_updated.emit()
        self.pending_signals_updated.emit()
        if event.status is OrderStatus.FILLED:
            # OrderEvent carries no symbol or side; resolve them from the
            # just-rebuilt display lists by matching the broker order id (the
            # trades ledger row carries the BUY/SELL side).
            trade = next(
                (t for t in self._trades if t.trade_id == event.broker_order_id),
                None,
            )
            symbol = (trade.symbol if trade is not None else None) or next(
                (p.symbol for p in self._positions if p.trade_id == event.broker_order_id),
                None,
            )
            side = trade.side.capitalize() if trade is not None else ""
            subject = " ".join(part for part in (symbol or "Order", side) if part)
            self.log_message.emit(
                "INFO",
                f"[Orders] {subject} fill confirmed: {event.filled_quantity} share(s) "
                f"at {event.fill_price or 0.0:.2f}",
            )

    def _strategy_cfg(self, name: str) -> Any:
        """Return the live StrategyConfig for *name*, or None."""
        ctx = self._strategy_engine.registry.get(name) if hasattr(self, "_strategy_engine") else None
        return ctx.cfg if ctx is not None else None

    def _rehydrate_positions_from_cycles(self) -> None:
        """Restore _positions and _trades from the trade_cycles ledger on boot.

        Open cycles → OpenPosition rows for the Pending Signals table.
        Recent history (open + closed) → TradeRecord rows for Trade History.
        """
        if self._tc_query is None:
            return
        try:
            open_snaps = self._tc_query.open_cycles()
            hist_snaps = self._tc_query.history(days=30)
        except Exception:
            _log.exception("[TradeCycle] Failed to load cycles on boot")
            return
        # Rebuild, do not append: this runs on every order event, so the display
        # lists must be cleared first or each closed cycle is re-added every time.
        self._trades.clear()
        self._positions.clear()
        if not open_snaps and not hist_snaps:
            return

        from datetime import datetime as _dt
        def _parse_iso(s: str | None) -> datetime.datetime | None:
            if not s:
                return None
            try:
                return _dt.fromisoformat(s)
            except Exception:
                return None

        seen_trade_ids: set[str] = set()
        for snap in hist_snaps:
            tid = snap.entry_order_id or f"cyc-{snap.cycle_id}"
            if tid in seen_trade_ids:
                continue
            seen_trade_ids.add(tid)
            entry_dt = _parse_iso(snap.entry_time) or datetime.datetime.now()
            exit_dt  = _parse_iso(snap.exit_time)
            self._trades.append(TradeRecord(
                trade_id        = tid,
                user_id         = snap.user_id or self._active_uid,
                symbol          = snap.symbol,
                side            = "BUY",
                quantity        = snap.entry_qty,
                entry_price     = snap.entry_price,
                mode            = "paper",
                strategy_id     = snap.strategy_id,
                entry_time      = entry_dt,
                exit_price      = snap.exit_price,
                exit_time       = exit_dt,
                order_state     = "FILLED",
                filled_quantity = snap.entry_qty,
            ))
            # Closed cycle → restore its SELL row too (one row per order).
            if snap.exit_order_id or snap.exit_time:
                exit_qty = snap.exit_qty or snap.entry_qty
                self._trades.append(TradeRecord(
                    trade_id        = snap.exit_order_id or f"cyc-{snap.cycle_id}-sell",
                    user_id         = snap.user_id or self._active_uid,
                    symbol          = snap.symbol,
                    side            = "SELL",
                    quantity        = exit_qty,
                    entry_price     = snap.exit_price or 0.0,
                    mode            = "paper",
                    strategy_id     = snap.strategy_id,
                    entry_time      = exit_dt or entry_dt,
                    order_state     = "FILLED",
                    filled_quantity = exit_qty,
                ))

        for snap in open_snaps:
            entry_dt = _parse_iso(snap.entry_time) or datetime.datetime.now()
            self._positions.append(OpenPosition(
                symbol          = snap.symbol,
                user_id         = snap.user_id or self._active_uid,
                quantity        = snap.entry_qty,
                average_price   = snap.entry_price,
                stop_loss       = snap.hard_stop_loss,
                target_price    = snap.target_price or 0.0,
                mode            = "paper",
                current_price   = snap.current_price or snap.entry_price,
                strategy_id     = snap.strategy_id,
                filled_quantity = snap.entry_qty,
                total_quantity  = snap.entry_qty,
                trade_id        = snap.entry_order_id or f"cyc-{snap.cycle_id}",
                entry_time      = entry_dt,
            ))
        _log.info(
            "[TradeCycle] Restored %d open, %d historical cycle(s)",
            len(open_snaps), len(hist_snaps),
        )

    def get_active_strategy_positions(self) -> list[OpenPosition]:
        """Paper-mode positions currently open (qty > 0) — feeds the Pending Signals table."""
        return [p for p in self._positions if p.mode == "paper" and p.quantity > 0]

    def get_open_symbols_for_strategy(self, name: str) -> list[str]:
        """Return sorted list of symbols holding an open cycle under *name*.

        Consumed by the Stop button gate — if non-empty, the user must
        close the positions manually via Force Exit before the strategy
        can transition back to Inactive.
        """
        if self._tc_query is None:
            return []
        try:
            return sorted(
                s.symbol for s in self._tc_query.open_cycles()
                if s.strategy_id == name
            )
        except Exception:
            _log.exception("[TradeCycle] open-symbols lookup failed for %s", name)
            return []

    def get_strategies_with_open_cycles(self) -> set[str]:
        """Strategy names that currently hold at least one open trade cycle.

        Consumed by the Strategy Executor to surface a RUNNING badge for
        strategies that have restored positions even though their saved
        run_state is STOPPED (the engine deliberately leaves it STOPPED
        on boot so entry checks stay gated behind the user's Run click).
        """
        if self._tc_query is None:
            return set()
        try:
            return {s.strategy_id for s in self._tc_query.open_cycles()}
        except Exception:
            _log.exception("[TradeCycle] Failed to query strategies with open cycles")
            return set()

    def _build_cycle_index(self) -> dict[str, dict[str, str]]:
        """Return ``{strategy: {symbol: 'RUNNING'}}`` for engine boot restoration.

        The strategy engine calls this in ``_load_registry`` so each
        ``_StrategyContext`` is rehydrated with the per-symbol RUNNING state
        of any open cycle still persisted in the trade-cycle ledger.
        """
        out: dict[str, dict[str, str]] = {}
        if self._tc_query is None:
            return out
        try:
            for snap in self._tc_query.open_cycles():
                out.setdefault(snap.strategy_id, {})[snap.symbol] = "RUNNING"
        except Exception:
            _log.exception("[TradeCycle] Failed to build cycle index for engine boot")
        return out

    def get_latest_close(self, symbol: str, tf: str = "3m") -> float | None:
        """Return the latest closing price for *symbol* at *tf*, or None."""
        bar = self._get_latest_bar(symbol, tf)
        return float(bar.close) if bar is not None else None

    def get_recent_closed_cycles(self) -> list:
        """Cycles closed today — stay visible in the Pending Signals table
        until the next-day pre-open cleanup.

        "Today" is the local calendar day of the machine, matching the
        timestamp written by ``_on_paper_fill``.
        """
        if self._tc_query is None:
            return []
        today = datetime.datetime.now().date()
        try:
            cycles = self._tc_query.history(days=2)
        except Exception:
            _log.exception("[TradeCycle] Failed to load recent closed cycles")
            return []
        out = []
        for c in cycles:
            if c.state != "CLOSED" or not c.exit_time:
                continue
            try:
                d = datetime.datetime.fromisoformat(c.exit_time).date()
            except Exception:
                continue
            if d == today:
                out.append(c)
        return out

    def force_exit_position(
        self, strategy: str, symbol: str, reason: str = "manual",
    ) -> int | None:
        """User- or trigger-initiated paper exit for a running strategy position.

        Looks up the open cycle via TradeCycleService, builds an exit
        ``TradeSignal`` carrying the latest close as its fill price, and
        submits it through ``PaperBroker``.  ``reason`` is carried into the
        resulting exit fill so the closed cycle records the real exit cause
        (target / hard_sl / trailing_sl / manual).  Returns the simulated
        order id, or None if no open cycle exists for the pair.
        """
        if self._tc_query is None:
            return None
        snap = next(
            (
                s for s in self._tc_query.open_cycles()
                if s.strategy_id == strategy and s.symbol == symbol
            ),
            None,
        )
        if snap is None:
            return None
        last_close = self.get_latest_close(symbol, "3m")
        if last_close is not None:
            exit_price = last_close
        elif snap.current_price is not None and snap.current_price > 0:
            exit_price = snap.current_price
        else:
            exit_price = snap.entry_price
        from us_swing.execution.strategy_engine._signals import (
            Action,
            TradeSignal as EngineSignal,
        )
        eng_sig = EngineSignal(
            action      = Action.EXIT,
            symbol      = symbol,
            strategy_id = strategy,
            entry_price = float(exit_price),
            reason      = "manual_force_exit",
        )
        self._pending_exit_reason = reason
        if self._submitter is None:
            _log.error("[Orders] Cannot submit exit order — order submission is unavailable")
            return -1
        return self._submitter.submit(eng_sig, int(snap.entry_qty))

    def _on_strategy_event(self, event: object) -> None:
        """Re-broadcast a position entry/exit as a refresh nudge.

        The payload is a plain ``"entered"`` / ``"exited"`` descriptor — the
        Strategy Executor derives the RUNNING badge live from open cycles and
        ignores this string. It must never carry the legacy ``"Active"`` /
        ``"Running"`` vocabulary, which is not a valid ``StrategyRunState``.
        """
        from us_swing.execution.strategy_engine._events import (
            RiskWarning,
            StrategyEntered,
            StrategyExited,
        )
        if isinstance(event, StrategyEntered):
            self.strategy_status_changed.emit(event.strategy_id, "entered")
            self._check_daily_loss()
        elif isinstance(event, StrategyExited):
            self.strategy_status_changed.emit(event.strategy_id, "exited")
            self._check_daily_loss()
        elif isinstance(event, RiskWarning):
            self.log_message.emit("WARNING", event.message)
            self.risk_warning_raised.emit(event.kind, event.message)

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

    @property
    def circuit_breaker_active(self) -> bool:
        """True when the circuit breaker is tripped — new entries are blocked."""
        return self._circuit_breaker_active

    def set_circuit_breaker(self, active: bool) -> None:
        """Trip or reset the circuit breaker and notify listeners."""
        if self._circuit_breaker_active == active:
            return
        self._circuit_breaker_active = active
        self.circuit_breaker_changed.emit(active)
        self.log_message.emit(
            "WARNING" if active else "INFO",
            "[Risk] Circuit breaker activated — new entries blocked"
            if active else "[Risk] Circuit breaker reset — entries re-enabled",
        )

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
        # Stop live tick worker
        tw = self._tick_worker
        if tw is not None:
            self._tick_worker = None
            try:
                tw.tick_price.disconnect()
                tw.subscription_failed.disconnect()
            except (RuntimeError, TypeError):
                pass
            tw.request_stop()
            tw.quit()
            tw.wait(5_000)
        # Clear Market Watch ltp on disconnect
        for item in self._mw_items:
            item.ltp = 0.0
            item.change = 0.0
            item.change_pct = 0.0
        self.market_watch_updated.emit()
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
        first_fetch = self._ibkr_acct is None
        self._ibkr_acct      = acct
        self._ibkr_positions = list(positions)
        if first_fetch:
            self._reconcile_live_capital(acct)
        self.account_updated.emit()
        self.positions_updated.emit()
        self._sync_tick_subscriptions()   # update position price subscriptions
        self._check_daily_loss()
        self._reconcile_margin_drift(acct)

    def _reconcile_live_capital(self, acct: AccountState) -> None:
        """Warn once per connect if Max Capital exceeds broker cash (FO-EXE-017)."""
        user = self.get_active_user()
        if user.mode != "live":
            return
        cap = user.risk_config.max_capital_value
        cash = acct.total_cash_value
        if cap > cash:
            self.log_message.emit(
                "WARNING",
                f"[Risk] Max Capital (${cap:.0f}) exceeds broker cash (${cash:.0f}) "
                f"— using ${0.9 * cash:.0f} for trading",
            )

    def _reconcile_margin_drift(self, acct: AccountState) -> None:
        """Advisory: warn once when system margin diverges from live broker cash."""
        if self.get_active_user().mode != "live":
            return
        gap = abs(self.margin_available() - acct.total_cash_value)
        tolerance = max(1.0, 0.01 * self.effective_capital())
        if gap > tolerance:
            if not self._margin_drift_warned:
                self._margin_drift_warned = True
                msg = (f"[Risk] Margin Available (${self.margin_available():.0f}) differs "
                       f"from broker cash (${acct.total_cash_value:.0f})")
                self.log_message.emit("WARNING", msg)
                self.risk_warning_raised.emit("margin_drift", msg)
        else:
            self._margin_drift_warned = False

    def _check_daily_loss(self) -> None:
        """Advisory aggregate daily-loss warning across all active trades."""
        if self._tc_query is None:
            return
        acct = self.get_account_state(self._active_uid)
        threshold = -self.get_active_user().risk_config.max_daily_loss_pct / 100.0 \
            * acct.start_of_day_equity
        if threshold == 0.0:
            return
        open_loss = sum(c.current_pnl_usd or 0.0 for c in self._tc_query.open_cycles())
        start = datetime.datetime.now().strftime("%Y-%m-%dT00:00:00")
        end = datetime.datetime.now().strftime("%Y-%m-%dT23:59:59")
        closed_loss = sum(c.realized_pnl_usd or 0.0
                          for c in self._tc_query.closed_between(start, end))
        day_pnl = open_loss + closed_loss
        if day_pnl <= threshold:
            if not self._daily_loss_warned:
                self._daily_loss_warned = True
                msg = (f"[Risk] Daily loss ${day_pnl:.0f} has crossed your "
                       f"max daily loss limit")
                self.log_message.emit("WARNING", msg)
                self.risk_warning_raised.emit("daily_loss", msg)
        else:
            self._daily_loss_warned = False

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
        self._acct_timer.start()
        self._refresh_account_data()   # immediate first fetch

        # Start live tick worker (FO-GUI-012)
        if self._tick_worker is None:
            from us_swing.execution.live_tick_worker import LiveTickWorker  # noqa: PLC0415
            tw = LiveTickWorker(
                host=host,
                port=port,
                client_id=self._system_cfg.ibkr_tick_client_id,
                parent=self,
            )
            tw.tick_price.connect(self._record_market_price)
            tw.tick_price.connect(self._on_watchlist_tick)
            tw.tick_price.connect(self._on_position_tick)
            tw.tick_price.connect(self._on_cycle_tick)
            tw.tick_price.connect(self.pending_tick)
            tw.subscription_failed.connect(self._on_tick_sub_failed)
            tw.start()
            self._tick_worker = tw
            _log.info("[Tick] Live tick streaming started (clientId=%d)", self._system_cfg.ibkr_tick_client_id)

        self._sync_tick_subscriptions()
        self._refresh_mw_quotes()
        if self._watchlist:
            self._refresh_watchlist()      # one-shot static metadata (day_open, etc.)

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

    def get_market_watch_items(self) -> list[WatchlistItem]:
        """Return current Market Watch items (SPY, QQQ, DIA, IWM)."""
        return list(self._mw_items)

    def get_mw_symbol_names(self) -> list[tuple[str, str]]:
        """Return [(symbol, display_name), ...] for all Market Watch symbols."""
        return list(_MW_SYMBOLS)

    def _refresh_mw_quotes(self) -> None:
        symbols = [item.symbol for item in self._mw_items]
        worker = _WatchlistQuoteWorker(symbols)
        worker.done.connect(self._on_mw_data)
        worker.start()
        self._mw_worker = worker

    def _on_mw_data(self, results: list) -> None:
        lookup = {r["symbol"]: r for r in results}
        for item in self._mw_items:
            if item.symbol in lookup:
                d = lookup[item.symbol]
                item.prev_close = d["prev_close"]
                item.day_open   = d["day_open"]
                item.day_high   = d["day_high"]
                item.day_low    = d["day_low"]
                item.volume     = d["volume"]
                item.year_high  = d["year_high"]
                item.year_low   = d["year_low"]
                item.market_cap = d["market_cap"]
        self.market_watch_updated.emit()

    # ── Watchlist ─────────────────────────────────────────────────────────────

    def get_watchlist_items(self) -> list[WatchlistItem]:
        return list(self._watchlist)

    def add_to_watchlist(self, symbol: str) -> None:
        symbol = symbol.upper().strip()
        if not symbol or any(w.symbol == symbol for w in self._watchlist):
            return
        self._watchlist.append(WatchlistItem(symbol=symbol))
        self.watchlist_updated.emit()
        if self._connection_status is ConnectionStatus.CONNECTED:
            self._refresh_watchlist()          # one-shot static metadata
            self._sync_tick_subscriptions()    # subscribe new symbol

    def remove_from_watchlist(self, symbol: str) -> None:
        self._watchlist = [w for w in self._watchlist if w.symbol != symbol]
        self.watchlist_updated.emit()
        if self._connection_status is ConnectionStatus.CONNECTED:
            self._sync_tick_subscriptions()    # cancel removed symbol's subscription

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
                # LTP / change come from tick stream; populate prev_close + static fields
                item.prev_close = d["prev_close"]
                item.day_open   = d["day_open"]
                item.day_high   = d["day_high"]
                item.day_low    = d["day_low"]
                item.volume     = d["volume"]
                item.year_high  = d["year_high"]
                item.year_low   = d["year_low"]
                item.market_cap = d["market_cap"]
        self.watchlist_updated.emit()

    # ── Live tick streaming (FO-GUI-012) ──────────────────────────────────────

    def _sync_tick_subscriptions(self) -> None:
        """Rebuild the LiveTickWorker contract set from MW + watchlist + positions.

        Market Watch index contracts are always included.
        Watchlist and position contracts are gated to S&P 500 members.
        Total subscriptions are capped at _MAX_TICK_SUBS (95); position
        contracts are trimmed first if the cap is exceeded.
        """
        tw = self._tick_worker
        if tw is None:
            return

        contracts: dict[str, Any] = {}

        # Market Watch — SPY, QQQ, DIA, IWM (standard stock contracts, no S&P 500 gate)
        for item in self._mw_items:
            c = _make_stk_contract(item.symbol)
            if c is not None:
                contracts[item.symbol] = c

        # Open trade-cycle symbols — always subscribed (ungated, untrimmable);
        # live LTP/PnL and exit evaluation depend on their ticks.
        for sym in self._cycle_symbols:
            if sym not in contracts:
                c = _make_stk_contract(sym)
                if c is not None:
                    contracts[sym] = c

        # Pending-signal symbols — subscribed (ungated) so the pending row shows
        # a live LTP and the MARKET entry fills at the real price on execute.
        for sig in self._pending_store.list():
            if sig.symbol not in contracts:
                c = _make_stk_contract(sig.symbol)
                if c is not None:
                    contracts[sig.symbol] = c

        # Ensure S&P 500 cache is populated
        if not self._sp500_cache and self._sp500:
            self._sp500_cache = {r.symbol for r in self._sp500}

        # Watchlist (S&P 500 members only)
        for item in self._watchlist:
            if item.symbol in self._sp500_cache:
                c = _make_stk_contract(item.symbol)
                if c is not None:
                    contracts[item.symbol] = c

        # Positions (S&P 500 members only)
        position_contracts: dict[str, Any] = {}
        for pos in self._ibkr_positions:
            if pos.symbol in self._sp500_cache:
                c = _make_stk_contract(pos.symbol)
                if c is not None:
                    position_contracts[pos.symbol] = c

        # Cap total subscriptions — trim positions first
        mw_wl_count = len(contracts)
        remaining   = max(0, _MAX_TICK_SUBS - mw_wl_count)
        if len(position_contracts) > remaining:
            _log.warning(
                "[Tick] Subscription cap reached — trimming position contracts "
                "from %d to %d", len(position_contracts), remaining,
            )
        for sym, c in list(position_contracts.items())[:remaining]:
            contracts[sym] = c

        tw.set_contracts(contracts)

    def _on_watchlist_tick(self, tag: str, price: float) -> None:
        """Update Market Watch and Watchlist ltp/change from tick stream."""
        for item in self._mw_items:
            if item.symbol == tag:
                item.ltp = price
                prev = item.prev_close or 0.0
                if prev:
                    item.change = price - prev
                    item.change_pct = item.change / prev * 100
                self.market_watch_updated.emit()
                return
        for item in self._watchlist:
            if item.symbol == tag:
                item.ltp = price
                prev = item.prev_close or 0.0
                if prev:
                    item.change = price - prev
                    item.change_pct = item.change / prev * 100
                self.watchlist_updated.emit()
                return

    def _on_cycle_symbols_changed(self, symbols: frozenset[str]) -> None:
        """Open trade-cycle symbols changed — re-sync tick subscriptions.

        Invoked by TradeCycleService whenever a cycle opens, closes, or is
        reloaded on startup.  Open cycles are real positions we entered, so
        their symbols must always be subscribed for live LTP/PnL.

        Newly-open symbols that are not already in the screened/keep set get
        their candle feeds armed too (download + live bars), so a held position
        always has data for indicator evaluation (ISS-EXE-0009). The arming is
        marshalled to the GUI thread because this callback fires on the
        trade-cycle background thread.
        """
        if symbols == self._cycle_symbols:
            return
        new_syms = symbols - self._cycle_symbols
        self._cycle_symbols = symbols
        self._sync_tick_subscriptions()
        uncovered = sorted(s for s in new_syms if s not in self._filtered_symbols)
        if uncovered:
            self._arm_candle_feeds_requested.emit(uncovered)

    def _arm_candle_feeds(self, uncovered: list[str]) -> None:
        """Arm historical + live candle feeds for newly-open symbols (ISS-EXE-0009).

        Runs on the GUI thread (queued from `_on_cycle_symbols_changed`). Unions
        the symbols into the keep set, starts an idempotent delta-fetch download,
        and extends the live-bar subscription when a worker is running — mirroring
        the tick-feed guarantee for open positions.
        """
        fresh = [s for s in uncovered if s not in self._filtered_symbols]
        if not fresh:
            return
        self._filtered_symbols = sorted(set(self._filtered_symbols) | set(fresh))
        _log.info("[Candles] Arming candle feeds for %d held symbol(s)", len(fresh))
        self._start_intraday_loader(fresh)
        if self._live_bar_worker is not None and self._live_bar_worker.isRunning():
            self._live_bar_worker.set_symbols(self._filtered_symbols)

    def _on_cycle_tick(self, tag: str, price: float) -> None:
        """Forward live ticks to the trade-cycle service for PnL + exit evaluation."""
        if self._tc_command is not None:
            self._tc_command.on_tick(tag, price)

    def _on_exit_trigger(self, evt: object) -> None:
        """Bus subscriber for ExitTrigger — runs on the cycle background thread.

        Marshals the auto-exit onto the GUI thread via a queued signal so the
        SELL submit and DB writes happen on the main thread.
        """
        from us_swing.execution.trade_cycle import ExitTrigger
        if isinstance(evt, ExitTrigger):
            self._auto_exit_requested.emit(evt.cycle_id, evt.reason)

    def _handle_auto_exit(self, cycle_id: int, reason: str) -> None:
        """Submit the SELL for a cycle that hit a target/SL/trailing trigger (GUI thread)."""
        if self._tc_query is None:
            return
        snap = self._tc_query.cycle(cycle_id)
        if snap is None:
            return
        order_id = self.force_exit_position(snap.strategy_id, snap.symbol, reason=reason)
        if order_id is None:
            _log.warning("[TradeCycle] Auto-exit found no open cycle for %s", snap.symbol)
            return
        self.log_message.emit(
            "INFO",
            f"[Execution] Auto-exit ({reason}) submitted for {snap.symbol}",
        )

    def _on_cycle_closed_clear_pending(self, evt: object) -> None:
        """Bus subscriber for CycleClosed — runs on the cycle background thread.

        Marshals the closed cycle's ``(strategy, symbol)`` to the GUI thread so
        any stale pending exit signal is dropped on the main thread (ISS-EXE-0010).
        """
        from us_swing.execution.trade_cycle import CycleClosed
        if isinstance(evt, CycleClosed):
            self._clear_pending_exits_requested.emit(evt.snapshot.strategy_id, evt.symbol)

    def _clear_pending_exits(self, strategy_id: str, symbol: str) -> None:
        """Drop any pending exit signal for a position that just closed (GUI thread)."""
        if self._pending_store is None:
            return
        from us_swing.execution.strategy_engine import Action
        removed = self._pending_store.dismiss_for(strategy_id, symbol, Action.EXIT)
        if removed:
            _log.info(
                "[Strategy] Cleared %d stale exit signal(s) for %s — position already closed",
                len(removed), symbol,
            )

    def _record_market_price(self, tag: str, price: float) -> None:
        """Cache the latest live price per symbol for SimBroker fills (SRD-INF-009.007).

        Runs on the GUI thread via the tick signal's queued delivery.
        """
        if price > 0:
            with self._last_tick_price_lock:
                self._last_tick_price[tag] = price

    def _market_price_for(self, symbol: str) -> float | None:
        """Latest live price for *symbol*, or None — the SimBroker's price provider.

        Called on the engine thread inside ``place_order``; reads under the lock.
        """
        with self._last_tick_price_lock:
            return self._last_tick_price.get(symbol)

    def _on_position_tick(self, tag: str, price: float) -> None:
        """Update open position current_price from tick stream (SRD-GUI-012.005)."""
        for pos in self._ibkr_positions:
            if pos.symbol == tag:
                pos.current_price = price
                self.positions_updated.emit()
                return

    def _on_tick_sub_failed(self, tag: str, code: int) -> None:
        """Handle LiveTickWorker subscription_failed signal."""
        _log.warning("[Tick] Subscription rejected for %s (IBKR code %d)", tag, code)

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

        # Live bar worker lifecycle: start on market open, stop on market close.
        if status == "open" and prev != "open" and self._filtered_symbols:
            self._start_live_bar_worker()
        elif status != "open" and prev == "open":
            self._stop_live_bar_worker()

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
        self._sp500_cache = set()   # invalidate cache so it rebuilds with new universe
        if self._connection_status is ConnectionStatus.CONNECTED:
            self._sync_tick_subscriptions()   # re-subscribe positions/watchlist with updated S&P 500
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
        """Return intraday OHLCV rows for *symbol* at the requested timeframe.

        Native live bars are stored in ``price_3m`` / ``price_15m`` by
        :class:`LiveBarWorker`. Historical bars are stored in ``price_1m`` by
        the intraday loader. This method merges both sources: native rows take
        precedence; 1m bars are aggregated to fill any gaps (typically older
        history that pre-dates the live feed).

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

        native_table = f"price_{timeframe}"
        native_rows: list[tuple] = []
        agg_rows: list[tuple] = []
        try:
            conn = sqlite3.connect(str(_CANDLE_DB_PATH))
            try:
                native_rows = conn.execute(
                    f"SELECT datetime, open, high, low, close, volume "
                    f"FROM {native_table} WHERE symbol = ? ORDER BY datetime ASC",
                    (symbol,),
                ).fetchall()
            except sqlite3.OperationalError:
                native_rows = []  # table may not exist on first run
            agg_rows = conn.execute(
                "SELECT datetime, open, high, low, close, volume "
                "FROM price_1m WHERE symbol = ? "
                "ORDER BY datetime DESC LIMIT ?",
                (symbol, limit_1m),
            ).fetchall()
            conn.close()
        except Exception:
            return []

        # Index native bars by epoch second so 1m-aggregated bars can be merged in
        # at the same bucket boundary without producing duplicates.
        candles_by_ts: dict[int, dict[str, Any]] = {}

        for dt_str, o, h, lo, c, v in native_rows:
            try:
                dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S").replace(
                    tzinfo=datetime.timezone.utc
                )
                ts = int(dt.timestamp())
            except ValueError:
                continue
            candles_by_ts[ts] = {
                "time":   ts,
                "open":   float(o or 0),
                "high":   float(h or 0),
                "low":    float(lo or 0),
                "close":  float(c or 0),
                "volume": float(v or 0),
            }

        # Aggregate 1m → target timeframe and merge non-overlapping buckets
        parsed_1m: list[tuple[int, float, float, float, float, float]] = []
        for dt_str, o, h, lo, c, v in reversed(agg_rows):
            try:
                dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S").replace(
                    tzinfo=datetime.timezone.utc
                )
                ts = int(dt.timestamp())
            except ValueError:
                continue
            parsed_1m.append((ts, float(o or 0), float(h or 0), float(lo or 0), float(c or 0), float(v or 0)))

        groups: dict[int, list[tuple[int, float, float, float, float, float]]] = {}
        for bar in parsed_1m:
            bucket = (bar[0] // 60) // minutes
            groups.setdefault(bucket, []).append(bar)

        for bucket in sorted(groups):
            group = groups[bucket]
            if len(group) < minutes:
                continue  # skip incomplete trailing bar
            ts = group[0][0]
            if ts in candles_by_ts:
                continue  # native bar wins
            candles_by_ts[ts] = {
                "time":   ts,
                "open":   group[0][1],
                "high":   max(b[2] for b in group),
                "low":    min(b[3] for b in group),
                "close":  group[-1][4],
                "volume": sum(b[5] for b in group),
            }

        return [candles_by_ts[ts] for ts in sorted(candles_by_ts)]

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
