"""Module: MD-INF-004.001.M03 — data/models.py
Parent SRD: SRD-INF-001.001, SRD-INF-003.001, SRD-INF-004.001, SRD-INF-006.006

Canonical domain dataclasses shared across all us_swing subsystems.
This is the single source of truth for every data contract in the system.

Rules:
- Pure data — no business logic, no I/O, no framework imports.
- GUI, DB, and API layers import from here; they never define their own
  redundant copies of these types.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime


# ── Enumerations ──────────────────────────────────────────────────────────────

class ConnectionStatus(enum.Enum):
    """IBKR broker connection state machine states."""
    CONNECTED    = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


class PositionState(enum.Enum):
    """Lifecycle state of an open position."""
    NEW           = "NEW"
    PARTIAL_ENTRY = "PARTIAL_ENTRY"
    OPEN          = "OPEN"
    PARTIAL_EXIT  = "PARTIAL_EXIT"
    CLOSED        = "CLOSED"


class TradingMode(enum.Enum):
    """Paper vs live execution mode."""
    PAPER = "paper"
    LIVE  = "live"


# ── Market data ───────────────────────────────────────────────────────────────

@dataclass
class OHLCVBar:
    """One candlestick bar for a single symbol and timeframe.

    ``timeframe`` uses the canonical string keys: ``'1m'``, ``'1d'``,
    ``'1w'``, ``'3m'``, ``'5m'``, ``'15m'``, ``'1h'``, ``'4h'``.
    """
    symbol:    str
    datetime:  datetime
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    int
    timeframe: str


# ── Universe / reference data ─────────────────────────────────────────────────

@dataclass
class UniverseRecord:
    """One S&P 500 constituent entry."""
    symbol: str   # 1–5 uppercase alpha
    name:   str
    sector: str


# ── Account ───────────────────────────────────────────────────────────────────

@dataclass
class AccountState:
    """Snapshot of an IBKR / paper account at a point in time."""
    user_id:               int
    equity:                float
    start_of_day_equity:   float
    open_position_value:   float
    daily_pnl:             float = 0.0
    excess_liquidity:      float = 0.0
    total_cash_value:      float = 0.0
    gross_position_value:  float = 0.0

    @property
    def available_capital(self) -> float:
        return self.excess_liquidity if self.excess_liquidity > 0 else self.equity - self.open_position_value

    @property
    def capital_utilisation_pct(self) -> float:
        if self.equity == 0:
            return 0.0
        # Cash not deployed = TotalCashValue; everything else is capital at work
        if self.total_cash_value > 0:
            return (self.equity - self.total_cash_value) / self.equity * 100
        return self.open_position_value / self.equity * 100


# ── Positions ─────────────────────────────────────────────────────────────────

@dataclass
class PositionRecord:
    """Persisted position row (maps 1:1 to the ``positions`` DB table)."""
    symbol:        str
    user_id:       int
    quantity:      int
    average_price: float
    stop_loss:     float
    target_price:  float
    mode:          str                   # TradingMode value
    state:         str                   # PositionState value
    trailing_stop: float = 0.0


@dataclass
class OpenPosition(PositionRecord):
    """Runtime-enriched position view used by the GUI and engine.

    Extends :class:`PositionRecord` with live price data and UI helpers.
    """
    filled_quantity: int      = 0
    total_quantity:  int      = 0
    current_price:   float    = 0.0
    strategy_id:     str      = ""
    entry_time:      datetime = field(default_factory=datetime.now)

    @property
    def unrealised_pnl(self) -> float:
        return (self.current_price - self.average_price) * self.quantity

    @property
    def pnl_pct(self) -> float:
        if self.average_price == 0:
            return 0.0
        return (self.current_price - self.average_price) / self.average_price * 100

    @property
    def days_held(self) -> int:
        return max(0, (datetime.now() - self.entry_time).days)

    @property
    def position_value(self) -> float:
        return self.current_price * self.quantity


# ── Trades ────────────────────────────────────────────────────────────────────

@dataclass
class TradeRecord:
    """Completed or in-flight trade (maps to the ``trades`` DB table)."""
    trade_id:    str
    user_id:     int
    symbol:      str
    side:        str          # "BUY" | "SELL"
    quantity:    int
    entry_price: float
    mode:        str          # TradingMode value
    strategy_id: str
    entry_time:  datetime
    exit_price:  float | None = None
    exit_time:   datetime | None = None
    pnl:         float | None = None
    status:      str          = "SUBMITTED"


# ── IBKR-specific types ───────────────────────────────────────────────────────

@dataclass
class IBKRPosition:
    """Raw position data returned by IBKR account queries."""
    symbol:        str
    quantity:      int
    average_price: float
    market_value:  float


@dataclass
class IBKRFill:
    """Single execution fill from IBKR."""
    order_id:        int
    symbol:          str
    filled_quantity: int
    fill_price:      float
    fill_time:       datetime


@dataclass
class RealtimeBar:
    """Realtime market update — either a single trade tick (open==high==low==close==price)
    or a pre-aggregated bar (e.g. 5-second bar from IBKR reqRealTimeBars).
    ``CandleBuilder`` accepts both forms transparently."""
    symbol:   str
    datetime: datetime
    open:     float
    high:     float
    low:      float
    close:    float
    volume:   int


# ── User profile ──────────────────────────────────────────────────────────────

@dataclass
class UserRecord:
    """Raw DB row from the ``users`` table.  Used only by DatabaseManager."""
    user_id:        int
    username:       str
    display_name:   str
    ibkr_client_id: int
    settings_json:  str   # raw JSON string
    mode:           str   # 'paper' | 'live'


@dataclass
class UserProfile:
    """Enriched user view with parsed settings.  Used by UserManager and GUI.

    The ``risk_config``, ``strategy_config``, and ``screener_config``
    fields are parsed from ``UserRecord.settings_json`` at load time.
    """
    user_id:         int
    username:        str
    display_name:    str
    ibkr_client_id:  int
    mode:            str          # TradingMode value
    risk_config:     "RiskConfig"
    strategy_config: dict         # parsed from settings_json["strategy_config"]
    screener_config: dict         # parsed from settings_json["screener_config"]


@dataclass
class RiskConfig:
    """Per-user risk parameters (parsed from ``settings_json``)."""
    risk_per_trade_pct: float = 1.0
    max_position_value: float = 10_000.0
    max_allocation_pct: float = 50.0
    max_daily_loss_pct: float = 2.0
    default_order_type: str   = "MKT"
    confirm_orders:     bool  = True


# ── Screener / signals ────────────────────────────────────────────────────────

@dataclass
class ScreenerResult:
    """Output row from the screener engine."""
    symbol:          str
    name:            str
    sector:          str
    composite_score: float
    rsi_pass:        bool
    volume_pass:     bool
    trend_pass:      bool
    breakout_pass:   bool
    pullback_pass:   bool


@dataclass
class FilteredStockEntry:
    """A stock that passed a screener preset run, enriched with preset metadata.

    Used by the Execution panel to show the latest screener output alongside
    pending trade signals.
    """
    symbol:         str
    score:          float
    trading_styles: list[str]
    assigned_users: list[str]
    screener_name:  str
    run_type:       str   # "manual" | "scheduled"
    date:           str   # YYYY-MM-DD


@dataclass
class TradeSignal:
    """A strategy-generated trade signal awaiting execution review."""
    symbol:          str
    side:            str    # "BUY" | "SELL"
    strategy_id:     str
    score:           float
    entry_price:     float    = 0.0
    stop_loss:       float    = 0.0
    target_price:    float    = 0.0
    recommended_qty: int      = 0
    generated_at:    datetime = field(default_factory=datetime.now)
    signal_id:       str      = ""


@dataclass
class MarketWatchItem:
    """A single Market Watch entry — index or symbol with live quote data."""
    symbol:       str            # e.g. "^GSPC", "^IXIC", "^DJI"
    display_name: str            # e.g. "S&P 500"
    ltp:          float  = 0.0  # last traded / current price
    change_pct:   float  = 0.0  # daily change %
    prev_close:   float  = 0.0  # previous close (used to compute change_pct)


@dataclass
class WatchlistItem:
    """A single Watchlist entry — user-added stock symbol with full live quote data."""
    symbol:     str
    ltp:        float = 0.0   # last traded price
    prev_close: float = 0.0
    change:     float = 0.0   # absolute $ change
    change_pct: float = 0.0   # % change
    day_open:   float = 0.0
    day_high:   float = 0.0
    day_low:    float = 0.0
    volume:     int   = 0
    year_high:  float = 0.0
    year_low:   float = 0.0
    market_cap: float = 0.0
