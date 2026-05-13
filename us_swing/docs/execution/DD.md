# Design Document — Execution & Risk Management (EXE)

**Document ID:** DD-EXE
**Version:** 1.3.0
**Traces To:** SRD-EXE v1.3.0
**Status:** Draft
**Last Updated:** 2026-05-06
**Project:** US Swing Trading System

---

## DD-EXE-001.001.D01 — RiskManager Interface Design

**Parent SRD:** SRD-EXE-001.001 — SRD-EXE-001.006

### Public Interface

```python
@dataclass
class AccountState:
    equity:            float
    start_of_day_equity: float
    open_position_value: float   # sum of all open position market values
    user_id:           int       # scoped to active user

@dataclass
class ValidationResult:
    ok:     bool
    reason: str   # '' if ok=True

class RiskManager:
    def __init__(config: RiskConfig) -> None

    def validate_signal(
        signal: TradeSignal,
        account_state: AccountState,
        circuit_breaker_active: bool,
    ) -> ValidationResult

    def can_enter_new(
        signal: TradeSignal,
        account_state: AccountState,
        user_id: int,
    ) -> bool  # convenience wrapper: validate + capital check

    def calculate_position_size(
        signal: TradeSignal,
        account_state: AccountState,
    ) -> int  # floor, in shares

@dataclass
class RiskConfig:
    risk_per_trade_pct:   float = 1.0    # % of equity risked per trade
    max_position_value:   float = 10_000 # hard cap in dollars per position
    max_capital_pct:      float = 50.0   # % of equity max deployed
    max_daily_loss_pct:   float = 2.0    # % of start-of-day equity
```

### Validation Logic

```
if circuit_breaker_active:
    return ValidationResult(False, "circuit breaker active")

required_value = entry_price × calculate_position_size(signal, account_state)
projected_deployment = account_state.open_position_value + required_value

if projected_deployment > account_state.equity × (max_capital_pct / 100):
    return ValidationResult(False, f"capital allocation limit: {projected_deployment:.0f} > {limit:.0f}")

return ValidationResult(True, "")
```

### Position Size Calculation

```
risk_dollars = account_state.equity × (risk_per_trade_pct / 100)
risk_per_share = abs(signal.entry_price - signal.stop_loss)
raw_shares = risk_dollars / risk_per_share          (float)
cap_shares  = max_position_value / signal.entry_price (float)
return floor(min(raw_shares, cap_shares))            (int)
```

---

## DD-EXE-001.001.D02 — ExecutionEngine Interface Design

**Parent SRD:** SRD-EXE-001.003, SRD-EXE-001.004, SRD-EXE-002.003

### Public Interface

```python
class ExecutionEngine:
    def __init__(
        client: IBKRClient,
        risk_manager: RiskManager,
        position_tracker: PositionTracker,
        db: DatabaseManager,
        config: RiskConfig,
        user_id: int,
        mode: str,             # 'live' | 'paper'
    ) -> None

    async def submit_signal(
        signal: TradeSignal,
        account_state: AccountState,
        quantity_override: int | None = None,
    ) -> int | None
    async def exit_position(symbol: str) -> int | None
    async def handle_order_fill(fill: IBKRFill) -> None
```

### Signal Submission Flow

```
ExecutionEngine.submit_signal(signal, account_state, quantity_override=None)
    │
    ├─1. RiskManager.validate_signal()
    │       └► REJECTED → log WARNING, return None
    │
    ├─2. quantity_override or RiskManager.calculate_position_size()
    │       └► if override: must still pass capital check via can_enter_new()
    │
    ├─3. if mode == 'paper': PaperEngine.simulate_fill()
    │    else: IBKRClient.place_order(contract, MKT/LMT order)
    │       └► timeout → raise OrderSubmissionError
    │
    ├─4. DatabaseManager.insert_trade(TradeRecord with user_id, mode)
    │
    └─5. return order_id (ibkr or paper-generated)
```

### Fill Handler Flow

```
handle_order_fill(fill):
    if fill is ENTRY fill:
        pos = OpenPosition(symbol, quantity, avg_price, stop, target)
        PositionTracker.open(pos)
        log INFO: "Position opened: {symbol} x{quantity} @ {price}"

    if fill is EXIT fill:
        pos = PositionTracker.close(symbol)
        pnl = (fill.avg_price - pos.avg_price) * pos.quantity
        DatabaseManager.update_trade_exit(fill.order_id, fill.time, fill.avg_price, pnl)
        emit PositionClosedEvent(symbol, pnl, strategy_id, duration)
        DailyPnLTracker.add(pnl)
        log INFO: "Position closed: {symbol} PnL={pnl:.2f}"
```

---

## DD-EXE-002.001.D01 — PositionTracker Design

**Parent SRD:** SRD-EXE-002.001 — SRD-EXE-002.005

### Public Interface

```python
@dataclass
class OpenPosition:
    symbol:        str
    user_id:       int
    quantity:      int
    filled_quantity: int         # partial fill tracking
    total_quantity:  int         # target total quantity
    avg_price:     float
    stop_loss:     float
    target_price:  float
    trailing_stop: float | None
    strategy_id:   str
    entry_time:    datetime
    state:         str           # NEW | PARTIAL_ENTRY | OPEN | PARTIAL_EXIT | CLOSED
    mode:          str           # 'live' | 'paper'

class PositionTracker:
    def open(pos: OpenPosition) -> None
    def close(user_id: int, symbol: str) -> OpenPosition
    def update_stop(user_id: int, symbol: str, new_stop: float) -> None
    def update_state(user_id: int, symbol: str, new_state: str, filled_qty: int | None = None) -> None
    def has_open(user_id: int, symbol: str) -> bool
    def get_all(user_id: int | None = None) -> list[OpenPosition]
    def load_from_db(user_id: int) -> None  # restore non-CLOSED positions on startup
    def reconcile(ibkr_positions: list[IBKRPosition]) -> list[str]  # returns adopted symbols
```

### Thread Safety

`PositionTracker` uses `threading.RLock` for all mutations. Readers (`has_open`, `get_all`) acquire the same lock to ensure consistency. The internal dict is keyed by `(user_id, symbol)` tuple.

---

## DD-EXE-004.001.D01 — PaperEngine Design

**Parent SRD:** SRD-EXE-004.001 — SRD-EXE-004.005

### Public Interface

```python
class PaperEngine:
    def __init__(
        data_provider: DataProvider,
        position_tracker: PositionTracker,
        db: DatabaseManager,
        user_id: int,
    ) -> None

    async def simulate_fill(
        signal: TradeSignal,
        quantity: int,
        order_type: str,       # 'MKT' | 'LMT'
    ) -> PaperFill

    async def simulate_exit(
        symbol: str,
    ) -> PaperFill
```

### Fill Simulation Logic

```
simulate_fill(signal, quantity, order_type):
    market_price = await data_provider.get_current_price(signal.symbol)

    if order_type == 'MKT':
        fill_price = market_price
    elif order_type == 'LMT':
        if signal.side == 'BUY' and market_price <= signal.limit_price:
            fill_price = signal.limit_price
        elif signal.side == 'SELL' and market_price >= signal.limit_price:
            fill_price = signal.limit_price
        else:
            → queue pending limit order; check on next price update

    paper_order_id = generate_paper_id()   # monotonic counter, negative to distinguish from IBKR
    fill = PaperFill(order_id=paper_order_id, symbol, quantity, fill_price, timestamp=now())
    return fill
```

### ExecutionRouter

```python
class ExecutionRouter:
    """Selects PaperEngine or live ExecutionEngine per user mode."""
    def __init__(
        live_engine: ExecutionEngine,
        paper_engine: PaperEngine,
        user_manager: UserManager,
    ) -> None

    async def route_signal(user_id: int, signal: TradeSignal, **kwargs) -> int | None:
        mode = user_manager.get_user(user_id).mode
        if mode == 'paper':
            return await paper_engine.simulate_fill(signal, **kwargs)
        return await live_engine.submit_signal(signal, **kwargs)
```

---

## DD-EXE-005.001.D01 — Position State Machine Design

**Parent SRD:** SRD-EXE-005.001 — SRD-EXE-005.003, SRD-EXE-005.006

### State Transition Diagram

```
       submit_order()
            │
            ▼
         ┌─────┐
         │ NEW │
         └──┬──┘
            │  partial entry fill
            ▼
  ┌─────────────────┐
  │ PARTIAL_ENTRY   │◄── additional partial fills
  └────────┬────────┘
           │  final entry fill (filled == total)
           ▼
        ┌──────┐
        │ OPEN │
        └──┬───┘
           │  partial exit fill
           ▼
  ┌────────────────┐
  │ PARTIAL_EXIT   │◄── additional partial exit fills
  └────────┬───────┘
           │  final exit fill (remaining == 0)
           ▼
       ┌────────┐
       │ CLOSED │
       └────────┘
```

### Valid Transitions

| From | To | Trigger |
|---|---|---|
| NEW | PARTIAL_ENTRY | Partial entry fill received |
| NEW | OPEN | Full entry fill received |
| PARTIAL_ENTRY | PARTIAL_ENTRY | Another partial entry fill |
| PARTIAL_ENTRY | OPEN | Final entry fill (filled == total) |
| OPEN | PARTIAL_EXIT | Partial exit fill received |
| OPEN | CLOSED | Full exit fill received |
| PARTIAL_EXIT | PARTIAL_EXIT | Another partial exit fill |
| PARTIAL_EXIT | CLOSED | Final exit fill (remaining == 0) |

### InvalidStateTransitionError

Any transition not in the table above raises `InvalidStateTransitionError(current_state, attempted_state)`.

### update_state Implementation

```python
def update_state(self, user_id: int, symbol: str, new_state: str, filled_qty: int | None = None):
    with self._lock:
        pos = self._positions[(user_id, symbol)]
        if (pos.state, new_state) not in VALID_TRANSITIONS:
            raise InvalidStateTransitionError(pos.state, new_state)
        pos.state = new_state
        if filled_qty is not None:
            pos.filled_quantity = filled_qty
        self._db.update_position_state(user_id, symbol, new_state, filled_qty)
```

### Startup Restore

```python
def load_from_db(self, user_id: int):
    rows = self._db.get_positions(user_id, exclude_state='CLOSED')
    with self._lock:
        for row in rows:
            self._positions[(user_id, row.symbol)] = OpenPosition(**row)
```

---

## DD-EXE-003.001.D01 — Circuit Breaker & Emergency Shutdown Design

**Parent SRD:** SRD-EXE-003.001 — SRD-EXE-003.006

### Public Interface

```python
class DailyPnLTracker:
    def add(pnl: float) -> None
    def reset() -> None               # called at market open each day
    @property
    def daily_pnl(self) -> float

class CircuitBreaker:
    def __init__(config: RiskConfig) -> None
    def check(daily_pnl: float, start_of_day_equity: float) -> bool

class EmergencyShutdown:
    def __init__(
        client: IBKRClient,
        position_tracker: PositionTracker,
        live_engine: LiveEngine,
        db: DatabaseManager,
    ) -> None

    async def run(reason: str) -> None
```

### EmergencyShutdown Sequence

```
EmergencyShutdown.run(reason):
    1. set circuit_breaker_active = True   [atomic flag]
    2. await IBKRClient.cancel_all_orders()
    3. for symbol in PositionTracker.get_all():
           await ExecutionEngine.exit_position(symbol)
    4. await LiveEngine.stop()
    5. log CRITICAL: f"Emergency shutdown: {reason}"
    6. AlertDispatcher.send(CRITICAL, reason)
    7. write shutdown summary → logs/shutdown_{timestamp}.json
    8. sys.exit(1)
```

### Shutdown Summary JSON Schema

```json
{
  "timestamp": "2026-03-05T15:45:00Z",
  "trigger": "daily_loss_limit",
  "positions_closed": ["AAPL", "MSFT"],
  "daily_pnl": -2000.50,
  "ibkr_errors": [],
  "duration_seconds": 8.2
}
```

### Kill-Switch Registration (main.py)

```python
import signal
shutdown = EmergencyShutdown(...)
signal.signal(signal.SIGTERM, lambda *_: asyncio.run(shutdown.run("SIGTERM")))
```

---

## DD-EXE-006.001.D01 — IntradayCandleLoader Design

**Parent SRD:** SRD-EXE-006.001 — SRD-EXE-006.005

### Public Interface

```python
@dataclass
class CandleLoadResult:
    symbol:  str
    ok:      bool
    reason:  str   # '' if ok; error or 'insufficient_candles:3m:312' if failed

class IntradayCandleLoader(QThread):
    """Background worker: delta-fetches 1m bars and validates intraday candle counts."""

    load_progress  = pyqtSignal(str, int, int)        # symbol, done, total
    load_complete  = pyqtSignal(list)                  # list[CandleLoadResult]

    def __init__(
        self,
        symbols:            list[str],
        ibkr_client:        IBKRClient,
        db:                 DatabaseManager,
        hist_engine:        HistoricalDataEngine,
        min_candles:        int = 390,
        full_fetch_days:    int = 65,
    ) -> None

    def run(self) -> None
        """QThread entry: iterates symbols, calls _fetch_symbol + _validate."""

    def _fetch_symbol(self, symbol: str) -> None
        """Delta-fetch 1m bars. Pages across IBKR 30-cal-day limit if full fetch."""

    def _validate_candle_counts(self, symbol: str) -> CandleLoadResult
        """Aggregate 3m/15m and verify ≥ min_candles each."""
```

### Data Flow

```
stock_list_ready event
        │
        ▼
IntradayCandleLoader.load(symbols)           ← QThread.start()
        │
        ├─ for each symbol:
        │      DatabaseManager.get_last_timestamp(symbol, '1m')
        │            │
        │            ├─ None   → full fetch (65 trading days, paged)
        │            └─ ts     → delta fetch (ts → now)
        │
        │      IBKRClient.req_historical_data(symbol, '1m', duration)
        │            │ pacing queue (SRD-INF-001.005)
        │            ▼
        │      DatabaseManager.insert_bars(symbol, '1m', bars)   [INSERT OR IGNORE]
        │
        │      HistoricalDataEngine.aggregate_timeframe(symbol, '3m')  → count ≥ 390?
        │      HistoricalDataEngine.aggregate_timeframe(symbol, '15m') → count ≥ 390?
        │
        │      emit load_progress(symbol, i, total)
        │
        └─ emit load_complete(results)
```

### IBKR Paging Strategy (Full Fetch)

IBKR limits 1m bar requests to 30 calendar days per call. The required window (30 calendar days ≈ 21 trading days) fits in a **single page** — no paging logic is exercised on a fresh fetch. The paged path remains in place for delta fetches where the gap exceeds 30 calendar days.

```
end_date = today
duration = "30 D"   # single request — no loop needed for fresh fetch
bars     = ibkr.req_historical_data(symbol, end_date, duration, '1 min')
db.insert_bars(symbol, '1m', bars)
```

The pacing queue enforces ≤ 50 requests per 10-min window.

### Error Handling

| Exception | Action |
|---|---|
| `IBKRPacingError` | caught; symbol added to failed list; reason = `'pacing_error'` |
| `IBKRHistoricalDataError` | caught; symbol added to failed list; reason = IBKR error message |
| `DatabaseError` | caught; symbol added to failed list; reason = `'db_write_error'` |
| All others | caught as `Exception`; symbol added to failed list; reason = repr(e) |

---

## DD-EXE-006.001.D02 — Readiness Report API Design

**Parent SRD:** SRD-EXE-006.006

### Public Interface

```python
@dataclass
class SymbolReadiness:
    symbol:       str
    candles_3m:   int
    candles_15m:  int
    last_1m_bar:  datetime | None
    ready:        bool    # True iff both counts ≥ min_candles (default 390)

class IntradayCandleLoader:
    def get_readiness_report(
        self,
        symbols: list[str],
        min_candles: int = 390,
    ) -> dict[str, SymbolReadiness]
```

### Query Strategy

For each symbol, three COUNT queries are issued against the aggregated-view or materialized table:

```sql
-- 3m count
SELECT COUNT(*) FROM price_1m
 WHERE symbol = :sym
   AND datetime >= :cutoff_3m;   -- cutoff = now - 390×3 minutes

-- 15m count
SELECT COUNT(*) FROM price_1m
 WHERE symbol = :sym
   AND datetime >= :cutoff_15m;  -- cutoff = now - 390×15 minutes
```

Counts are approximate (assumes continuous bars). For validation, `aggregate_timeframe()` produces the exact count; `get_readiness_report()` uses the fast COUNT path for UI display.

---

## DD-EXE-007.001.D01 — `price_3m` Schema Extension

**Parent SRD:** SRD-EXE-007.001

### Table Definition (addition to `db/schema.py`)

```python
price_3m = sa.Table(
    "price_3m",
    metadata,
    sa.Column("symbol",   sa.Text,    nullable=False),
    sa.Column("datetime", sa.Text,    nullable=False),   # ISO 8601 UTC string
    sa.Column("open",     sa.Float),
    sa.Column("high",     sa.Float),
    sa.Column("low",      sa.Float),
    sa.Column("close",    sa.Float),
    sa.Column("volume",   sa.Integer),
    sa.PrimaryKeyConstraint("symbol", "datetime"),
)
```

Add to `_PRICE_INDEXES`:

```python
sa.Index("idx_price_3m_sym_dt", price_3m.c.symbol, price_3m.c.datetime),
```

Add to `PRICE_TABLES`:

```python
PRICE_TABLES: dict[str, sa.Table] = {
    "1m": price_1m,
    "1d": price_1d,
    "1w": price_1w,
    "3m": price_3m,   # ← Phase 2 addition
}
```

### Migration Strategy

`create_schema(engine, checkfirst=True)` is additive — SQLAlchemy emits `CREATE TABLE IF NOT EXISTS`. Existing `price_1m`, `price_1d`, `price_1w` tables and all data are untouched. No explicit migration script needed.

### Effect on `DatabaseManager`

All three `DatabaseManager` methods that dispatch via `PRICE_TABLES[timeframe]` — `insert_bars()`, `get_last_timestamp()`, `get_bars()` — work for `timeframe='3m'` automatically once `PRICE_TABLES["3m"]` is registered. No changes to `manager.py`.

---

## DD-EXE-007.001.D02 — `PartialBar` Dataclass & `LiveCandleAggregator` Interface

**Parent SRD:** SRD-EXE-007.002, SRD-EXE-007.003

### `PartialBar` Dataclass

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

from us_swing.data.models import OHLCVBar


@dataclass(slots=True)
class PartialBar:
    """In-memory accumulator for the current 3-minute window."""
    symbol:       str
    window_start: datetime   # UTC, floor-aligned to 3 min in ET
    open:         float
    high:         float
    low:          float
    close:        float
    volume:       int
    tick_count:   int        # number of 5-second bars received this window

    def to_ohlcv_bar(self) -> OHLCVBar:
        return OHLCVBar(
            symbol=self.symbol,
            datetime=self.window_start,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            timeframe="3m",
        )
```

`window_start` is always the ET-floor expressed in UTC (e.g. 09:30 ET = 13:30 UTC in summer). Storing in UTC ensures `DatabaseManager.insert_bars()` datetime serialisation is consistent with `price_1m`.

### `LiveCandleAggregator` Public Interface

```python
from PyQt6.QtCore import QThread, pyqtSignal
from us_swing.broker.client import IBKRClient
from us_swing.db.manager import DatabaseManager


class LiveCandleAggregator(QThread):
    """Accumulates IBKR 5-second real-time bars into live 3m candles."""

    candle_updated = pyqtSignal(str, object)   # (symbol, PartialBar)
    candle_closed  = pyqtSignal(str, object)   # (symbol, OHLCVBar)

    def __init__(
        self,
        ibkr: IBKRClient,
        db:   DatabaseManager,
    ) -> None: ...

    def run(self) -> None:
        """Register IBKR callback, start 60-second session-end timer, enter Qt loop."""

    def set_symbols(self, symbols: list[str]) -> None:
        """Diff-and-subscribe: add/remove IBKR subscriptions, clear orphan partials."""

    def on_disconnect(self) -> None:
        """Discard all partial bars; clear subscription set."""

    def on_reconnect(self, symbols: list[str]) -> None:
        """Re-subscribe to symbols; fresh partials start on next 3m boundary."""
```

### Thread Ownership

```
┌─────────────────────────────────────────────────────────────┐
│ GUI thread                                                  │
│   app_service.py → aggregator.set_symbols([...])           │
│                  → aggregator.on_disconnect()               │
│                  → aggregator.on_reconnect([...])           │
│   receives: candle_updated / candle_closed via Qt signal    │
└──────────────────────────┬──────────────────────────────────┘
                           │ QThread / Qt event loop
┌──────────────────────────▼──────────────────────────────────┐
│ LiveCandleAggregator thread                                 │
│   run() → ibkr.on_realtime_bar(self._on_realtime_bar)      │
│         → QTimer(60 s) → _check_session_end()              │
│   _lock protects: _subscribed, _partials                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ IBKR callback (ib_insync thread)
┌──────────────────────────▼──────────────────────────────────┐
│ IBKR / ib_insync event thread                               │
│   calls _on_realtime_bar(symbol, RealtimeBar)               │
│   acquires _lock; updates _partials; releases _lock         │
│   emits candle_updated / candle_closed outside lock         │
└─────────────────────────────────────────────────────────────┘
```

`_lock` is a `threading.Lock` (not `RLock`) — `_on_realtime_bar` never re-enters itself.

---

## DD-EXE-007.001.D03 — Tick Processing, Window Boundary, and Bar Close

**Parent SRD:** SRD-EXE-007.004, SRD-EXE-007.005, SRD-EXE-007.006

### Helper: `_floor_3m(dt_utc)`

```python
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

_ET = ZoneInfo("America/New_York")

def _floor_3m(dt_utc: datetime) -> datetime:
    """Floor a UTC datetime to the nearest 3-minute ET boundary; return UTC."""
    dt_et = dt_utc.astimezone(_ET)
    floored_et = dt_et.replace(
        minute=(dt_et.minute // 3) * 3,
        second=0,
        microsecond=0,
    )
    return floored_et.astimezone(timezone.utc)
```

Examples (ET summer, UTC-4):

| `bar.datetime` (UTC) | ET equivalent | `_floor_3m` result (UTC) |
|---|---|---|
| 13:31:45 | 09:31:45 ET | 13:30:00 UTC (09:30 ET) |
| 13:33:00 | 09:33:00 ET | 13:33:00 UTC (09:33 ET) |
| 13:34:59 | 09:34:59 ET | 13:33:00 UTC (09:33 ET) |

### `set_symbols()` — Diff-and-Subscribe

```python
def set_symbols(self, symbols: list[str]) -> None:
    new_set = set(symbols)
    with self._lock:
        to_add    = new_set - self._subscribed
        to_remove = self._subscribed - new_set
        for sym in to_add:
            self._ibkr.subscribe_realtime_bars(sym)
            self._subscribed.add(sym)
        for sym in to_remove:
            self._ibkr.unsubscribe_realtime_bars(sym)
            self._subscribed.discard(sym)
            self._partials.pop(sym, None)   # drop orphan partial bar
```

Lock is held throughout to prevent `_on_realtime_bar` processing a symbol mid-removal.

### `_on_realtime_bar()` — Full Processing Sequence

```python
def _on_realtime_bar(self, symbol: str, bar: RealtimeBar) -> None:
    if not _is_rth(bar.datetime):
        return

    window_start   = _floor_3m(bar.datetime)
    partial_to_close: PartialBar | None = None

    with self._lock:
        if symbol not in self._subscribed:
            return

        existing = self._partials.get(symbol)

        if existing is None:
            # First tick for this symbol this session
            self._partials[symbol] = PartialBar(
                symbol=symbol, window_start=window_start,
                open=bar.open, high=bar.high, low=bar.low, close=bar.close,
                volume=bar.volume, tick_count=1,
            )

        elif window_start == existing.window_start:
            # Same 3m window — update running OHLCV
            existing.high   = max(existing.high, bar.high)
            existing.low    = min(existing.low,  bar.low)
            existing.close  = bar.close
            existing.volume += bar.volume
            existing.tick_count += 1

        else:
            # New 3m window — stash old partial for close, start fresh
            partial_to_close = existing
            self._partials[symbol] = PartialBar(
                symbol=symbol, window_start=window_start,
                open=bar.open, high=bar.high, low=bar.low, close=bar.close,
                volume=bar.volume, tick_count=1,
            )

        current_partial = self._partials[symbol]

    # ── Outside lock: DB write + signal emission ──────────────────────────
    if partial_to_close is not None:
        self._close_bar(symbol, partial_to_close)
    self.candle_updated.emit(symbol, current_partial)
```

Lock is released before DB write and signal emission to prevent GUI event-loop deadlock.

### `_close_bar()` — Finalise, Persist, Emit

```python
def _close_bar(self, symbol: str, partial: PartialBar) -> None:
    bar = partial.to_ohlcv_bar()
    self._db.insert_bars(symbol, "3m", [bar])          # idempotent INSERT OR IGNORE
    self.candle_closed.emit(symbol, bar)
    log.debug(
        "3m closed: %s @ %s O=%.2f H=%.2f L=%.2f C=%.2f V=%d",
        symbol, partial.window_start.isoformat(),
        partial.open, partial.high, partial.low, partial.close, partial.volume,
    )
```

`_close_bar` is called only from `_on_realtime_bar` (lock already released) and from `on_disconnect` (lock also released before call). It must never be called while `_lock` is held.

### Data Flow Diagram

```
IBKRClient.subscribe_realtime_bars(sym)
        │  every 5 seconds
        ▼
_on_realtime_bar(symbol, RealtimeBar)
        │
        ├─ _is_rth()? No  → return (discard)
        │
        ├─ _floor_3m(bar.datetime) → window_start
        │
        ├─[acquire _lock]
        │   same window?  → update PartialBar.high/low/close/volume
        │   new window?   → stash old, create fresh PartialBar
        │   no partial?   → create first PartialBar
        │[release _lock]
        │
        ├─ old partial?  → _close_bar()
        │       ├─ DatabaseManager.insert_bars(sym, '3m', [bar])
        │       └─ emit candle_closed(sym, OHLCVBar)
        │
        └─ emit candle_updated(sym, PartialBar)
                │
                ├─► StrategyEngine — evaluates live signal on each closed bar
                └─► GUI Chart Panel — renders live in-progress candle
```

---

## DD-EXE-007.001.D04 — RTH Guard & Session-End Discard

**Parent SRD:** SRD-EXE-007.007
- **Status:** Approved

### `_is_rth()` Implementation

```python
from datetime import time as dtime

_RTH_OPEN  = dtime(9, 30, 0)
_RTH_CLOSE = dtime(16, 0, 0)

def _is_rth(dt_utc: datetime) -> bool:
    """True if dt falls within Regular Trading Hours (ET, Mon–Fri)."""
    dt_et = dt_utc.astimezone(_ET)
    if dt_et.weekday() >= 5:          # Saturday=5, Sunday=6
        return False
    t = dt_et.time().replace(tzinfo=None)
    return _RTH_OPEN <= t < _RTH_CLOSE
```

`zoneinfo` handles DST transitions transparently — no manual offset arithmetic. Summer (EDT, UTC-4) and winter (EST, UTC-5) are both correct.

### Session-End QTimer

`run()` creates a `QTimer` set to fire every 60 seconds:

```python
def run(self) -> None:
    self._ibkr.on_realtime_bar(self._on_realtime_bar)
    self._session_timer = QTimer()
    self._session_timer.setInterval(60_000)   # 60 s
    self._session_timer.timeout.connect(self._check_session_end)
    self._session_timer.start()
    self.exec()   # Qt event loop
```

### `_check_session_end()`

```python
def _check_session_end(self) -> None:
    now_utc = datetime.now(timezone.utc)
    if _is_rth(now_utc):
        return

    with self._lock:
        n = len(self._partials)
        self._partials.clear()
    if n:
        log.info("RTH ended — %d partial bar(s) discarded", n)
```

Partial bars are discarded without calling `_close_bar` — no incomplete candle is persisted. The timer continues running; on the next trading day, new partial bars begin naturally on the first incoming tick.

### Edge Cases

| Scenario | Behaviour |
|---|---|
| DST spring-forward (clocks skip 2:00→3:00 AM ET) | `_is_rth` unaffected — market hours are 09:30–16:00 ET regardless of offset |
| Federal holiday (market closed, IBKR sends no bars) | No ticks arrive; `_partials` stays empty; timer fires but `_is_rth` returns False (weekday but IBKR silent — no action needed) |
| Bar straddles 16:00 boundary (arrives at 15:59:55) | `_is_rth` returns True; bar is processed. Next bar at 16:00:05 is discarded by `_is_rth` returning False |

---

## DD-EXE-007.001.D05 — Disconnect, Reconnect & Readiness Report Update

**Parent SRD:** SRD-EXE-007.008, SRD-EXE-007.009

### Disconnect Sequence

```python
def on_disconnect(self) -> None:
    with self._lock:
        n = len(self._partials)
        self._partials.clear()
        self._subscribed.clear()   # IBKR tears down subscriptions on its side
    log.warning("Feed disconnected — %d partial bar(s) discarded", n)
```

`_subscribed` is cleared because the IBKR connection is gone — all subscription handles are invalid. When `on_reconnect` calls `set_symbols()`, it starts with an empty `_subscribed` set, so every symbol is treated as a new subscription.

### Reconnect Sequence

```python
def on_reconnect(self, symbols: list[str]) -> None:
    self.set_symbols(symbols)   # re-subscribes all; partials start on next 3m boundary
    log.info("Feed reconnected — subscribed to %d symbol(s)", len(symbols))
```

No historical gap-fill is performed. Gaps in `price_3m` between the disconnect and reconnect times are expected and acceptable — Phase 1 (`IntradayCandleLoader`) is responsible for back-filling missing bars in the next pre-session run.

### Readiness Report — `candles_3m` Count Update (SRD-EXE-007.009)

Phase 1's `get_readiness_report` computes `candles_3m` by time-windowed COUNT on `price_1m`. Phase 2 persists completed 3m bars to `price_3m`. To reflect live bars in the readiness count, update `get_readiness_report` to query `price_3m` directly for the `candles_3m` field:

```python
# Phase 2 replacement for the candles_3m query in get_readiness_report():

SELECT COUNT(*) FROM price_3m
 WHERE symbol = :sym;
-- No time cutoff needed — every row in price_3m is a valid completed 3m bar
```

For `candles_15m`, the existing time-windowed COUNT on `price_1m` is unchanged — Phase 2 only forms 3m bars, not 15m.

### Updated `SymbolReadiness` Query Strategy

| Field | Source (Phase 1) | Source (Phase 2) |
|---|---|---|
| `candles_3m` | `COUNT(*) FROM price_1m WHERE datetime >= cutoff_3m` (approximate) | `COUNT(*) FROM price_3m` (exact; no cutoff) |
| `candles_15m` | `COUNT(*) FROM price_1m WHERE datetime >= cutoff_15m` | unchanged |
| `last_1m_bar` | `MAX(datetime) FROM price_1m WHERE symbol = :sym` | unchanged |
| `ready` | both counts ≥ 390 | unchanged logic; now `candles_3m` is exact |
