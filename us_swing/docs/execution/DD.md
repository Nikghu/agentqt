# Design Document — Execution & Risk Management (EXE)

**Document ID:** DD-EXE
**Version:** 1.12.0
**Traces To:** SRD-EXE v1.17.0
**Status:** Draft
**Last Updated:** 2026-06-09
**Project:** US Swing Trading System

> v1.12.0: DD-EXE-017.* added — effective-capital resolution, capital-max sizing, blocking-vs-advisory risk split, daily-loss aggregation, rex auto-reset on start + display fix.
> v1.11.0: DD-EXE-016.* added — ingestion-driven monitoring-lifecycle seam, `trade_cycles` carryover repoint, `positions` table drop.
> v1.10.0: DD-EXE-015.* added — BrokerAdapter (translation/selection/routing) + broker-agnostic Order Ingestion pipeline.
> v1.9.0: DD-EXE-013.001.D01 added — Strategy Run Lifecycle engine evaluation decision tree.
> v1.8.0: DD-EXE-011.016.D01 added — Per-Symbol Re-Execution Counter (rex_count enforcement).
> v1.7.0: DD-EXE-012.* added — Trade Cycle Ledger (table DDL, repository, tick throttle, exit-trigger emission).
> v1.6.0: DD-EXE-011.* added — Strategy Engine (threading layout, `_StrategyContext`, `ConditionEvaluator`, mode router).

---

# FO-EXE-001 — Risk-Controlled Order Submission

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

# FO-EXE-002 — Position Tracking & Exit Execution

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

# FO-EXE-003 — Daily Loss Circuit Breaker & Emergency Controls

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

# FO-EXE-004 — Paper Trading Mode

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

# FO-EXE-005 — Position State Machine & Capital Availability Check

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

# FO-EXE-006 — Intraday Candle Readiness for Execution

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

## DD-EXE-006.010.D01 — Execution Candle Read-Path (Aggregate-on-Read)

**Parent SRD:** SRD-EXE-006.010

**Problem.** The strategy engine evaluates conditions against a
`dict[str, pd.DataFrame]` of candles keyed by timeframe (SRD-EXE-011.006),
supplied by `AppService._get_candles_df(symbol)` (candles_provider) and
`AppService._get_latest_bar(symbol, tf)` (bar_provider). The original code read
only the materialised `price_3m` / `price_15m` tables, which are written **only**
by the FO-EXE-007 live feed (RTH, a few bars at a time). Phase 1 (FO-EXE-006)
downloads deep 1 m history into `price_1m` but never persists derived 3 m / 15 m
bars — `_validate_candle_counts` aggregates them only to count for the readiness
gate, then discards them. Outside a long live session the engine therefore sees
far fewer bars than an indicator needs (e.g. RSI(14) on 3 m needs at least 15
bars, otherwise it returns NaN, the condition never fires, and no signal is
enqueued).

**Design.** Surface 3 m / 15 m by aggregating `price_1m` on read, merged with any
live `price_{tf}` rows. `price_1m` is the single source of truth for historical
depth; the live tables become a freshness cache. Reuses the pure
`HistoricalDataEngine.aggregate_timeframe` already used by validation.

New module-level functions in `execution/intraday_candle_loader.py`:

```
assemble_execution_bars(db, hist, symbol, tf, lookback_days=30) -> list[OHLCVBar]
    now          = utcnow()
    window_start = now - lookback_days
    bars_1m      = db.fetch_bars(symbol, "1m", window_start, now)
    derived      = hist.aggregate_timeframe(symbol, tf, bars_1m) if bars_1m else []
    live         = db.fetch_bars(symbol, tf, window_start, now)
    return _merge_bars(derived, live)        # union by datetime, live wins, asc

load_execution_frames(db, hist, symbol, timeframes=("3m","15m")) -> dict[str, pd.DataFrame]
    {tf: _bars_to_frame(bars) for tf in timeframes if (bars := assemble_execution_bars(...))}

load_latest_execution_bar(db, hist, symbol, tf) -> OHLCVBar | None
    None when tf not in ("3m","15m"); else last of assemble_execution_bars(...) or None
```

`_merge_bars` de-duplicates on `bar.datetime` (live overrides derived for the
same timestamp) and returns ascending order. `_bars_to_frame` builds the columns
the evaluator consumes: `datetime, open, high, low, close, volume`.

**Window.** `lookback_days = 30` (= `_FULL_FETCH_CAL_DAYS`, approximately 21
trading days) yields at least 390 bars for both 3 m and 15 m (SRD-EXE-006.003)
and matches the download window, so all stored depth is used.

**Cross-tool wiring (`gui/app_service.py`).** `_get_candles_df` /
`_get_latest_bar` become thin wrappers over the new functions, using a
lazily-constructed, cached `(DatabaseManager, HistoricalDataEngine)` pair built
once over `candles.db` with a `DummyProvider` (aggregation is pure — no provider
I/O). Caching avoids per-tick engine construction; the SQLAlchemy engine is
thread-safe for the executor-thread calls.

**Cost.** Approximately 21 trading days of 1 m (~8 k rows) aggregated per symbol
per tick; single-pass linear, under 10 ms — acceptable for the per-minute
evaluation cadence over the screened set.

---

# FO-EXE-007 — Live 3m Candle Formation During Trading Hours

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

---

# FO-EXE-008 — Live Market Data Tick Worker

## DD-EXE-008.001.D01 — LiveTickWorker Internal Architecture

**Parent SRD:** SRD-EXE-008.001, SRD-EXE-008.003, SRD-EXE-008.005, SRD-EXE-008.006
- **Status:** Draft

### Class Skeleton

```python
class LiveTickWorker(QThread):
    tick_price         = pyqtSignal(str, float)   # (tag, last_price)
    subscription_failed = pyqtSignal(str, int)    # (tag, ibkr_error_code)

    def __init__(self, host: str, port: int, client_id: int,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._host       = host
        self._port       = port
        self._client_id  = client_id
        self._stop_event = threading.Event()
        self._lock       = threading.Lock()
        # Subscription state (all guarded by _lock):
        self._active:       dict[str, Contract] = {}     # tag → Contract
        self._tickers:      dict[str, Ticker]   = {}     # tag → Ticker
        self._tag_by_conid: dict[int, str]      = {}     # conId → tag
        self._reqid_to_tag: dict[int, str]      = {}     # reqId → tag

    def run(self) -> None:
        asyncio.run(self._async_run())

    async def _async_run(self) -> None:
        ib = IB()
        await self._connect_with_retry(ib)
        ib.pendingTickersEvent += self._on_pending_tickers
        ib.errorEvent          += self._on_ibkr_error
        while not self._stop_event.is_set():
            await asyncio.sleep(0.05)
        # Teardown
        with self._lock:
            for ticker in self._tickers.values():
                ib.cancelMktData(ticker.contract)
        await ib.disconnectAsync()
```

### Internal State Tables

| Dict | Key type | Value type | Purpose |
|---|---|---|---|
| `_active` | `str` (tag) | `Contract` | Caller-desired subscription set; source of truth for reconciliation |
| `_tickers` | `str` (tag) | `Ticker` | ib_insync Ticker returned by `reqMktData`; used for cancellation |
| `_tag_by_conid` | `int` (conId) | `str` (tag) | Fast lookup in `pendingTickersEvent` (O(1) per ticker) |
| `_reqid_to_tag` | `int` (reqId) | `str` (tag) | Maps IBKR error reqId back to caller tag for `subscription_failed` |

All four dicts are guarded by `_lock`. `_on_pending_tickers` reads `_tag_by_conid` under the lock; it does NOT hold the lock during signal emission (avoiding deadlock with the GUI thread).

### asyncio / QThread Pattern

Matches `LiveBarWorker` exactly: `QThread.run()` calls `asyncio.run()`, which owns the event loop for the worker's lifetime. `set_contracts()` is called from the GUI thread and schedules work on the ib_insync event loop via `ib.schedule()` (or direct call under lock, since ib_insync is thread-safe for `reqMktData`/`cancelMktData` calls when not inside an async context).

### ClientId Collision Retry (`_connect_with_retry`)

```python
async def _connect_with_retry(self, ib: IB) -> None:
    client_id = self._client_id
    for attempt in range(4):   # 1 initial + 3 retries
        try:
            await ib.connectAsync(self._host, self._port, clientId=client_id)
            return
        except ConnectionRefusedError:
            raise   # TWS not running — fatal, don't retry
        # Error 326 arrives via errorEvent, not as an exception;
        # detect via ib.isConnected() == False after connect attempt
        if not ib.isConnected() and attempt < 3:
            log.warning("[Tick] ClientId %d in use — retrying with %d",
                        client_id, client_id + 1)
            client_id += 1
    log.error("[Tick] Cannot connect — all clientId slots in use")
    self._stop_event.set()
```

---

## DD-EXE-008.001.D02 — set_contracts() Reconciliation & Tick Handler

**Parent SRD:** SRD-EXE-008.002, SRD-EXE-008.003, SRD-EXE-008.004
- **Status:** Draft

### Reconciliation Algorithm

```python
_SUB_BATCH = 10
_SUB_PAUSE = 0.20   # seconds

def set_contracts(self, contracts: dict[str, Contract]) -> None:
    with self._lock:
        current_tags = set(self._active)
        new_tags     = set(contracts)
        to_add    = new_tags - current_tags
        to_remove = current_tags - new_tags

        # Unsubscribe removed tags
        for tag in to_remove:
            ib.cancelMktData(self._tickers.pop(tag).contract)
            self._active.pop(tag)
            # _tag_by_conid and _reqid_to_tag cleaned in _on_ibkr_error
            # or on next pendingTickersEvent miss — safe to leave stale

        # Subscribe new tags in batches
        batch: list[tuple[str, Contract]] = []
        for tag in to_add:
            batch.append((tag, contracts[tag]))
            if len(batch) == _SUB_BATCH:
                self._subscribe_batch(batch)
                time.sleep(_SUB_PAUSE)
                batch.clear()
        if batch:
            self._subscribe_batch(batch)

        self._active = dict(contracts)   # update desired set
```

`_subscribe_batch` calls `ib.reqMktData(contract, "", False, False)` for each pair, populates `_tickers[tag]`, `_tag_by_conid[ticker.contract.conId]`, and `_reqid_to_tag[ticker.reqId]` under the same lock.

### pendingTickersEvent Handler

```python
def _on_pending_tickers(self, tickers: set[Ticker]) -> None:
    for ticker in tickers:
        with self._lock:
            tag = self._tag_by_conid.get(ticker.contract.conId)
        if tag is None:
            continue
        price = ticker.last
        if isnan(price) or price <= 0:
            price = ticker.close
        if isnan(price) or price <= 0:
            continue   # no valid price yet — suppress emission
        self.tick_price.emit(tag, price)   # cross-thread signal queue
```

### Error Handler

```python
def _on_ibkr_error(self, reqId: int, code: int, msg: str,
                   contract: Contract) -> None:
    if code not in {200, 354, 420}:
        log.warning("[Tick] IBKR error %d for reqId %d: %s", code, reqId, msg)
        return
    with self._lock:
        tag = self._reqid_to_tag.pop(reqId, None)
        if tag is None:
            return
        self._tickers.pop(tag, None)
        self._active.pop(tag, None)
        # Remove stale conId entry (contract.conId may be 0 if unknown)
        self._tag_by_conid = {k: v for k, v in self._tag_by_conid.items()
                              if v != tag}
    self.subscription_failed.emit(tag, code)
    log.warning("[Tick] Subscription failed for %s (code %d)", tag, code)
```

### Edge Cases

| Scenario | Behaviour |
|---|---|
| `set_contracts({})` called while worker running | All subscriptions cancelled; `_active` becomes `{}` |
| Same tag appears in successive `set_contracts` calls | No duplicate `reqMktData` — `to_add` excludes existing tags |
| conId is 0 at reqMktData return time | `_tag_by_conid` populated lazily on first `pendingTickersEvent` where `ticker.contract.conId` becomes non-zero |
| `ticker.last` and `ticker.close` both NaN | Signal suppressed; handler called again on next price update |

---

# FO-EXE-009 — Intraday Monitoring Session Ledger & Lifecycle

## DD-EXE-009.001.D01 — Schema Additions & Idempotent Migration

**Parent SRD:** SRD-EXE-009.001, SRD-EXE-009.002, SRD-EXE-009.003
- **Status:** Draft

### `monitoring_session` Table Definition (addition to `db/schema.py`)

```python
monitoring_session = Table(
    "monitoring_session",
    metadata,
    Column("session_date",    Text,  nullable=False),
    Column("symbol",          Text,  nullable=False),
    Column("preset_id",       Text,  nullable=False),
    Column("run_timestamp",   Text,  nullable=False),
    Column("added_at",        Text,  nullable=False),
    Column("lifecycle_state", Text,  nullable=False, server_default="MONITORING"),
    Column("entered_at",      Text,  nullable=True),
    Column("exited_at",       Text,  nullable=True),
    Column("evicted_at",      Text,  nullable=True),
    Column("trade_id",        Text,  nullable=True),
    PrimaryKeyConstraint("session_date", "symbol", name="pk_monitoring_session"),
)
Index("idx_monitoring_session_state",  monitoring_session.c.lifecycle_state)
Index("idx_monitoring_session_symbol", monitoring_session.c.symbol)
```

Applied via the existing `create_schema(engine, checkfirst=True)` — additive, no-op on already-provisioned DBs.

### `trades` and `positions` Column Migration

`db/schema.py` declares the columns on the table objects so fresh DBs get them via `create_schema`. Existing DBs run a one-shot idempotent migration on app start:

```python
def migrate_lifecycle_columns(engine: Engine) -> None:
    """Add lifecycle columns to trades + positions if missing. Idempotent."""
    with engine.begin() as conn:
        existing_trades = {row["name"] for row in conn.execute(text("PRAGMA table_info(trades)")).mappings()}
        if "trade_origin" not in existing_trades:
            conn.execute(text("ALTER TABLE trades ADD COLUMN trade_origin TEXT"))
        if "monitoring_session_date" not in existing_trades:
            conn.execute(text("ALTER TABLE trades ADD COLUMN monitoring_session_date TEXT"))

        existing_positions = {row["name"] for row in conn.execute(text("PRAGMA table_info(positions)")).mappings()}
        if "origin" not in existing_positions:
            conn.execute(text("ALTER TABLE positions ADD COLUMN origin TEXT"))
        if "anchor_session_date" not in existing_positions:
            conn.execute(text("ALTER TABLE positions ADD COLUMN anchor_session_date TEXT"))
```

Called once from `DatabaseManager.__init__` after `create_schema(...)`. Legacy rows keep NULL — all lifecycle queries explicitly filter `origin = 'system'` / `trade_origin = 'system'`, so NULL rows are naturally excluded.

### State Enum (application-layer)

```python
class LifecycleState(str, Enum):
    MONITORING = "MONITORING"
    ENTERED    = "ENTERED"
    SKIPPED    = "SKIPPED"
    EVICTED    = "EVICTED"
    EXITED     = "EXITED"

class TradeOrigin(str, Enum):
    SYSTEM = "system"
    MANUAL = "manual"

class Side(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"
```

DB stores raw strings; `_repository` validates on read.

---

## DD-EXE-009.001.D02 — `_repository.py` — DB Access Layer

**Parent SRD:** SRD-EXE-009.001, SRD-EXE-009.005, SRD-EXE-009.006, SRD-EXE-009.007, SRD-EXE-009.009, SRD-EXE-009.012
- **Status:** Draft

Only file under `core/monitoring_session/` that imports SQLAlchemy. Wraps every DB operation in a typed method so `_service.py` stays SQL-free.

### Public Interface

```python
class MonitoringRepository:
    def __init__(self, engine: Engine) -> None: ...

    # Ledger
    def insert_monitoring_rows(
        self,
        session_date: date,
        preset_id: str,
        run_timestamp: str,
        symbols: Sequence[str],
    ) -> tuple[str, ...]:
        """Returns symbols actually inserted (ON CONFLICT DO NOTHING semantics)."""

    def fetch_earliest_open_monitoring_row(self, symbol: str) -> MonitoringSessionRow | None:
        """Earliest MONITORING row across all session_dates for symbol."""

    def transition_to_entered(
        self,
        session_date: date,
        symbol: str,
        entered_at: str,
        trade_id: str,
    ) -> None: ...

    def transition_to_exited(
        self,
        session_date: date,
        symbol: str,
        exited_at: str,
    ) -> None: ...

    def bulk_skip_stale_monitoring(self, today: date) -> int:
        """UPDATE ... SET state='SKIPPED' WHERE session_date < today AND state='MONITORING'. Returns row count."""

    def evict_symbol_atomic(self, symbol: str, evicted_at: str) -> tuple[str, ...]:
        """Single transaction: DELETE from price_1m/3m/15m + UPDATE ledger rows to EVICTED.
        Returns the session_dates marked EVICTED. Raises ReconcileError on any failure."""

    def fetch_history(self, symbol: str, days: int) -> tuple[MonitoringSessionRow, ...]: ...
    def fetch_session(self, session_date: date, symbol: str) -> MonitoringSessionRow | None: ...

    # Positions / trades
    def open_system_position_symbols(self) -> frozenset[str]:
        """SELECT symbol FROM positions WHERE state != 'CLOSED' AND origin = 'system'."""

    def has_open_system_position(self, symbol: str) -> bool: ...

    def insert_trade_with_anchor(
        self,
        trade_id: str,
        symbol: str,
        side: Side,
        qty: int,
        price: float,
        fill_time: str,
        origin: TradeOrigin,
        anchor_session_date: str | None,
    ) -> None: ...

    def upsert_position_with_anchor(
        self,
        symbol: str,
        qty_delta: int,
        side: Side,
        price: float,
        origin: TradeOrigin,
        anchor_session_date: str | None,
    ) -> PositionSnapshot:
        """Updates positions.quantity, state, average_price, origin, anchor_session_date.
        Returns post-update snapshot so caller can decide if the fill closes the position."""

    # Diagnostics
    def entered_symbols(self) -> frozenset[str]:
        """SELECT symbol FROM monitoring_session WHERE lifecycle_state = 'ENTERED'."""
```

### `evict_symbol_atomic` Implementation

```python
def evict_symbol_atomic(self, symbol: str, evicted_at: str) -> tuple[str, ...]:
    with self._engine.begin() as conn:        # SAVEPOINT-style single transaction
        for tf in ("price_1m", "price_3m", "price_15m"):
            conn.execute(
                text(f"DELETE FROM {tf} WHERE symbol = :sym"),
                {"sym": symbol},
            )
        result = conn.execute(
            text(
                "UPDATE monitoring_session "
                "SET lifecycle_state = 'EVICTED', evicted_at = :ts "
                "WHERE symbol = :sym "
                "  AND lifecycle_state IN ('SKIPPED', 'MONITORING') "
                "  AND session_date < :today "
                "RETURNING session_date"
            ),
            {"sym": symbol, "ts": evicted_at, "today": _today_str_et()},
        )
        return tuple(row[0] for row in result)
    # SQLAlchemy auto-rollback on exception; caller wraps in retry-once
```

SQLite supports `RETURNING` from 3.35.0+; project pins ≥ 3.39.

### Thread Safety

All methods are stateless on the repository (no caches). SQLAlchemy's `Engine` connection pool serialises writes via SQLite's process-wide lock; reads use shared connections. Repository is safe to share across threads — `_service` holds one instance per `MonitoringSessionService`.

---

## DD-EXE-009.002.D01 — `_service.py` — Lifecycle State Machine

**Parent SRD:** SRD-EXE-009.004, SRD-EXE-009.005, SRD-EXE-009.006, SRD-EXE-009.007, SRD-EXE-009.008, SRD-EXE-009.009, SRD-EXE-009.010
- **Status:** Draft

### Class Skeleton

```python
class MonitoringSessionService:                # implements MonitoringQuery + MonitoringCommand
    def __init__(
        self,
        repo: MonitoringRepository,
        bus:  MonitoringEventBus,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        today_provider: Callable[[], date] = _today_et,
    ) -> None:
        self._repo  = repo
        self._bus   = bus
        self._clock = clock
        self._today = today_provider
        self._lock  = threading.RLock()
        self._reconcile_lock     = threading.Lock()
        self._reconcile_running_for: date | None = None
```

`clock` and `today_provider` are injected for deterministic tests.

### `on_screener_results` Algorithm

```python
def on_screener_results(self, result: ScreenerRunResult) -> KeepSet:
    today = self._today()
    symbols = sorted({s for s, r in result.results.items() if r.get("passed")})
    with self._lock:
        inserted = self._repo.insert_monitoring_rows(
            session_date=today,
            preset_id=result.preset_id,
            run_timestamp=result.run_timestamp,
            symbols=symbols,
        )
    for symbol in inserted:
        self._bus.publish(SymbolStartedMonitoring(
            event_id=str(uuid4()),
            occurred_at=self._clock().isoformat(),
            symbol=symbol,
            session_date=str(today),
            preset_id=result.preset_id,
            run_timestamp=result.run_timestamp,
            schema_version=1,
        ))
    return KeepSet(
        filtered=frozenset(symbols),
        carryover=self._repo.open_system_position_symbols(),
        as_of=today,
        schema_version=1,
    )
```

### `on_fill` Decision Tree

```
on_fill(fill):
    if fill.origin == MANUAL:
        repo.insert_trade_with_anchor(..., origin=MANUAL, anchor=None)
        repo.upsert_position_with_anchor(..., origin=MANUAL, anchor=None)
        return                                              # SRD-009.008 (a)

    # origin == SYSTEM
    with self._lock:
        has_open = repo.has_open_system_position(fill.symbol)

        if not has_open and fill.side == BUY:
            anchor = repo.fetch_earliest_open_monitoring_row(fill.symbol)
            if anchor is None:
                log.error("[Lifecycle] System BUY for %s without monitoring row", fill.symbol)
                # Defensive: still record the trade with anchor=None so audit is preserved.
                repo.insert_trade_with_anchor(..., origin=SYSTEM, anchor=None)
                repo.upsert_position_with_anchor(..., origin=SYSTEM, anchor=None)
                return
            # First-BUY transition (SRD-009.005)
            anchor_date = anchor.session_date
            repo.transition_to_entered(anchor_date, fill.symbol,
                                       entered_at=fill.fill_time, trade_id=fill.trade_id)
            repo.insert_trade_with_anchor(..., origin=SYSTEM, anchor=anchor_date)
            snap = repo.upsert_position_with_anchor(..., origin=SYSTEM, anchor=anchor_date)
            event = SymbolEnteredPosition(...)
            self._bus.publish(event)
            return

        # has_open == True  →  scale-in / scale-out / close
        anchor_date = repo.position_anchor(fill.symbol)
        repo.insert_trade_with_anchor(..., origin=SYSTEM, anchor=anchor_date)
        snap = repo.upsert_position_with_anchor(..., origin=SYSTEM, anchor=anchor_date)

        if snap.state == "CLOSED":
            # Exit transition (SRD-009.007)
            repo.transition_to_exited(anchor_date, fill.symbol, exited_at=fill.fill_time)
            self._bus.publish(SymbolExitedPosition(
                symbol=fill.symbol, anchor_session_date=anchor_date,
                exit_trade_id=fill.trade_id, exit_time=fill.fill_time,
                realised_pnl=snap.realised_pnl, ...))
        else:
            # Scale-in or scale-out (SRD-009.006)
            self._bus.publish(SymbolPositionScaled(
                symbol=fill.symbol, anchor_session_date=anchor_date,
                trade_id=fill.trade_id, side=fill.side, fill_qty=fill.qty,
                new_position_state=snap.state, fill_time=fill.fill_time, ...))
```

The `self._lock` (`RLock`) guards the decision-tree window so two concurrent `on_fill` calls for the same symbol see a consistent `has_open_system_position` reading. All repository methods involved in a single call execute in one DB transaction — SQLite serialises writes process-wide, so the lock plus the transaction yield the invariant required by SRD-EXE-009.009.

### `MonitoringQuery` Read Methods

```python
def keep_set(self, today: date) -> KeepSet:
    return KeepSet(
        filtered=self._latest_filtered_for(today),
        carryover=self._repo.open_system_position_symbols(),
        as_of=today, schema_version=1,
    )

def open_system_positions(self) -> frozenset[str]:
    return self._repo.open_system_position_symbols()

def has_open_system_position(self, symbol: str) -> bool:
    return self._repo.has_open_system_position(symbol)

def check_invariant(self) -> InvariantReport:
    a = self._repo.entered_symbols()
    b = self._repo.open_system_position_symbols()
    return InvariantReport(
        ok=(a == b),
        only_in_a=tuple(sorted(a - b)),
        only_in_b=tuple(sorted(b - a)),
        schema_version=1,
    )
```

`_latest_filtered_for(today)` calls into the existing `ScreenerResultsStorage.load_for_execution(preset_id=SystemConfig.active_screener_preset_id, today=today)`.

### Anchor Resolution Rule

"Earliest open `MONITORING` row" = `SELECT * FROM monitoring_session WHERE symbol = :sym AND lifecycle_state = 'MONITORING' ORDER BY session_date ASC LIMIT 1`. Once consumed by an entry, that row becomes `ENTERED` and is no longer "open" for future fills (which see `has_open_system_position == True` instead).

---

## DD-EXE-009.002.D02 — `_events.py` — Sealed Event Union & In-Process Bus

**Parent SRD:** SRD-EXE-009.011
- **Status:** Draft

### Event Dataclasses

```python
@dataclass(frozen=True, slots=True)
class _EventBase:
    event_id:       str   # UUID4 hex
    occurred_at:    str   # ISO-8601 UTC
    schema_version: int = 1

@dataclass(frozen=True, slots=True)
class SymbolStartedMonitoring(_EventBase):
    symbol:        str = ""
    session_date:  str = ""
    preset_id:     str = ""
    run_timestamp: str = ""

@dataclass(frozen=True, slots=True)
class SymbolEnteredPosition(_EventBase):
    symbol:               str = ""
    anchor_session_date:  str = ""
    trade_id:             str = ""
    fill_qty:             int = 0
    fill_time:            str = ""

@dataclass(frozen=True, slots=True)
class SymbolPositionScaled(_EventBase):
    symbol:               str = ""
    anchor_session_date:  str = ""
    trade_id:             str = ""
    side:                 Side = Side.BUY
    fill_qty:             int = 0
    new_position_state:   str = ""
    fill_time:            str = ""

@dataclass(frozen=True, slots=True)
class SymbolExitedPosition(_EventBase):
    symbol:               str = ""
    anchor_session_date:  str = ""
    exit_trade_id:        str = ""
    exit_time:            str = ""
    realised_pnl:         float = 0.0

@dataclass(frozen=True, slots=True)
class SymbolSkipped(_EventBase):
    symbol:       str = ""
    session_date: str = ""

@dataclass(frozen=True, slots=True)
class SymbolEvicted(_EventBase):
    symbol:                 str = ""
    evicted_session_dates:  tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class ReconcileCompleted(_EventBase):
    report: ReconcileReport = field(default_factory=lambda: ReconcileReport(
        0, 0, 0, 0, (), 0, (), 1))

MonitoringEvent = (
    SymbolStartedMonitoring | SymbolEnteredPosition | SymbolPositionScaled |
    SymbolExitedPosition  | SymbolSkipped         | SymbolEvicted        |
    ReconcileCompleted
)
```

The `_EventBase` default args + concrete-class additional defaults are required because `frozen=True` dataclasses with a non-default `_EventBase` field would forbid subclasses adding fields without defaults; pinning defaults here keeps the inheritance chain valid in Python 3.11.

### Subscription & Dispatch

```python
@dataclass
class Subscription:
    _bus:        "_InProcessBus"
    _event_type: type
    _handler:    Callable[[Any], None]
    _alive:      bool = True

    def cancel(self) -> None:
        if self._alive:
            self._bus._unregister(self._event_type, self._handler)
            self._alive = False


class _InProcessBus:                          # implements MonitoringEventBus
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable) -> Subscription:
        with self._lock:
            self._handlers[event_type].append(handler)
        return Subscription(self, event_type, handler)

    def publish(self, event: MonitoringEvent) -> None:
        with self._lock:
            handlers = list(self._handlers.get(type(event), ()))
        for h in handlers:                    # outside the lock — handlers may re-enter
            try:
                h(event)
            except Exception as exc:
                log.error("[Lifecycle] Handler %s raised on %s: %r",
                          getattr(h, "__qualname__", repr(h)),
                          type(event).__name__, exc)
```

Dispatch is synchronous on the publishing thread. Handlers are responsible for their own non-blocking behaviour (e.g., GUI handlers must `QMetaObject.invokeMethod(..., Qt.QueuedConnection)` to hop to the GUI thread). One bad handler cannot block sibling handlers — exceptions are caught and logged.

### Why a Plain `list[Callable]`, Not `WeakSet`

GUI bridges register a bound method as the handler; bound methods are non-hashable for `WeakSet` and need `WeakMethod`. Choosing `WeakMethod` would silently drop subscriptions if the bridge dropped its reference. Instead, the bridge holds the `Subscription` object and explicitly calls `subscription.cancel()` on teardown. This makes subscription lifetimes explicit and debuggable.

---

## DD-EXE-009.003.D01 — Public Surface, Package Layout & Factory

**Parent SRD:** SRD-EXE-009.010, SRD-EXE-009.011, SRD-EXE-009.012
- **Status:** Draft

### File Layout

```
src/us_swing/core/monitoring_session/
    __init__.py          # public surface — Protocols, DTOs, events, build_default_service
    _service.py          # MonitoringSessionService concrete class
    _repository.py       # MonitoringRepository (SQLAlchemy)
    _events.py           # _InProcessBus + 7 event dataclasses + sealed union
    _scheduler.py        # pre-open trigger glue (DD-EXE-010.002.D01)
    _dto.py              # KeepSet, ReconcileReport, MonitoringSessionRow, FillEvent,
                         # InvariantReport, ReconcileError, PositionSnapshot
    _enums.py            # LifecycleState, TradeOrigin, Side
```

### `__init__.py` Public Surface

```python
"""Cross-tool monitoring-session service. The only module any non-internal
consumer should import from."""

from us_swing.core.monitoring_session._dto import (
    KeepSet, ReconcileReport, MonitoringSessionRow, FillEvent,
    InvariantReport, ReconcileError, PositionSnapshot,
)
from us_swing.core.monitoring_session._enums import (
    LifecycleState, TradeOrigin, Side,
)
from us_swing.core.monitoring_session._events import (
    MonitoringEvent,
    SymbolStartedMonitoring, SymbolEnteredPosition, SymbolPositionScaled,
    SymbolExitedPosition, SymbolSkipped, SymbolEvicted, ReconcileCompleted,
)
from us_swing.core.monitoring_session._protocols import (
    MonitoringQuery, MonitoringCommand, MonitoringEventBus, Subscription,
)

# Factory only — concrete classes are NOT re-exported
def build_default_service(
    engine: Engine,
    *,
    today_provider: Callable[[], date] | None = None,
    clock: Callable[[], datetime]       | None = None,
) -> tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]:
    from us_swing.core.monitoring_session._repository import MonitoringRepository
    from us_swing.core.monitoring_session._events     import _InProcessBus
    from us_swing.core.monitoring_session._service    import MonitoringSessionService

    bus     = _InProcessBus()
    repo    = MonitoringRepository(engine)
    service = MonitoringSessionService(
        repo=repo, bus=bus,
        today_provider=today_provider or _today_et,
        clock=clock or (lambda: datetime.now(timezone.utc)),
    )
    return service, service, bus            # one object implements query + command

__all__ = [
    "MonitoringQuery", "MonitoringCommand", "MonitoringEventBus", "Subscription",
    "KeepSet", "ReconcileReport", "MonitoringSessionRow", "FillEvent",
    "InvariantReport", "ReconcileError", "PositionSnapshot",
    "LifecycleState", "TradeOrigin", "Side",
    "MonitoringEvent",
    "SymbolStartedMonitoring", "SymbolEnteredPosition", "SymbolPositionScaled",
    "SymbolExitedPosition", "SymbolSkipped", "SymbolEvicted", "ReconcileCompleted",
    "build_default_service",
]
```

`_protocols.py` (new minor file) holds the four `Protocol` declarations; broken out to avoid a circular import between `_service.py` (implementer) and `_dto.py` (DTO consumers).

### Import-Graph Test (enforces Qt-free constraint)

```python
# tests/core/test_monitoring_session_imports.py
def test_no_pyqt6_dependency() -> None:
    """SRD-EXE-009.012: core/monitoring_session must not pull in PyQt6."""
    pkg_root = Path(__file__).parents[2] / "src" / "us_swing" / "core" / "monitoring_session"
    for py in pkg_root.rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        assert "PyQt6" not in src, f"{py.name} imports PyQt6"
        assert "pyqtSignal" not in src, f"{py.name} references pyqtSignal"

def test_consumers_only_import_from_init() -> None:
    """Underscore-prefixed modules must not be imported outside the package."""
    src_root = Path(__file__).parents[2] / "src" / "us_swing"
    banned   = re.compile(r"from\s+us_swing\.core\.monitoring_session\._\w+")
    for py in src_root.rglob("*.py"):
        if "monitoring_session" in py.parts:        # internal — allowed
            continue
        text = py.read_text(encoding="utf-8")
        assert not banned.search(text), f"{py} imports a private monitoring_session module"
```

These two tests live in `tests/core/` and run on every CI invocation.

---

# FO-EXE-010 — Pre-Open Candle DB Reconciliation

## DD-EXE-010.001.D01 — Reconciliation Algorithm

**Parent SRD:** SRD-EXE-010.001, SRD-EXE-010.002, SRD-EXE-010.003, SRD-EXE-010.005
- **Status:** Draft

### `reconcile_preopen` Top-Level

```python
def reconcile_preopen(self, today: date) -> ReconcileReport:
    if not self._reconcile_lock.acquire(blocking=False):
        log.warning("[Lifecycle] Reconcile already running — skipping duplicate call")
        return _SKIPPED_REPORT
    started_at = time.perf_counter()
    try:
        self._reconcile_running_for = today

        # ── Step 1: EOD finalize ────────────────────────────────────────
        skipped_n = self._repo.bulk_skip_stale_monitoring(today)

        # ── Step 2: compute eviction set ────────────────────────────────
        keep   = self.keep_set(today)
        ent    = self._repo.entered_symbols()              # invariant guard
        stale  = self._repo.stale_lifecycle_symbols(today) # SKIPPED ∪ MONITORING < today
        evict  = stale - keep.filtered - keep.carryover - ent

        # ── Step 3: per-symbol eviction (failure-isolated) ──────────────
        evicted_ok:    list[str] = []
        errors:        list[ReconcileError] = []
        now_iso = self._clock().isoformat()
        for symbol in sorted(evict):
            try:
                dates = self._repo.evict_symbol_atomic(symbol, evicted_at=now_iso)
                evicted_ok.append(symbol)
                self._bus.publish(SymbolEvicted(
                    event_id=str(uuid4()), occurred_at=now_iso,
                    symbol=symbol, evicted_session_dates=dates, schema_version=1,
                ))
            except sqlalchemy.exc.OperationalError as exc:
                # Retry-once for transient SQLite contention
                time.sleep(0.20)
                try:
                    dates = self._repo.evict_symbol_atomic(symbol, evicted_at=now_iso)
                    evicted_ok.append(symbol)
                    self._bus.publish(SymbolEvicted(..., dates, ...))
                except Exception as retry_exc:
                    errors.append(ReconcileError(symbol, repr(retry_exc), 1))
                    log.warning("[Lifecycle] Eviction failed for %s: %r", symbol, retry_exc)
            except Exception as exc:
                errors.append(ReconcileError(symbol, repr(exc), 1))
                log.warning("[Lifecycle] Eviction failed for %s: %r", symbol, exc)

        # ── Step 4: report & event ──────────────────────────────────────
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        report = ReconcileReport(
            filtered_n=len(keep.filtered),
            carryover_n=len(keep.carryover),
            skipped_n=skipped_n,
            evicted_n=len(evicted_ok),
            evicted_symbols=tuple(sorted(evicted_ok)),
            duration_ms=duration_ms,
            errors=tuple(errors),
            schema_version=1,
        )
        log.info(
            "[Lifecycle] Reconcile complete — %d filtered, %d carryover, "
            "%d marked skipped, %d evicted in %d ms",
            report.filtered_n, report.carryover_n, report.skipped_n,
            report.evicted_n, report.duration_ms,
        )
        self._bus.publish(ReconcileCompleted(
            event_id=str(uuid4()), occurred_at=now_iso,
            report=report, schema_version=1,
        ))
        return report
    finally:
        self._reconcile_running_for = None
        self._reconcile_lock.release()
```

### Retention Invariant Cross-Check

If `ent != self._repo.open_system_position_symbols()`, log ERROR and abort eviction for the conflicting symbols. The mismatch is reported in `ReconcileReport.errors` with `message='invariant_violation'`. The reconciler does NOT auto-repair — repair is an operator action (separate `service.repair_invariant()` admin method, future work, out of scope).

### `_SKIPPED_REPORT` Sentinel

```python
_SKIPPED_REPORT = ReconcileReport(
    filtered_n=0, carryover_n=0, skipped_n=0, evicted_n=0,
    evicted_symbols=(), duration_ms=0,
    errors=(ReconcileError("__skipped__", "already_running", 1),),
    schema_version=1,
)
```

---

## DD-EXE-010.002.D01 — Scheduler & Startup Catch-Up

**Parent SRD:** SRD-EXE-010.004
- **Status:** Draft

### `_scheduler.py` Module

```python
import zoneinfo
from datetime import datetime, time

_NY = zoneinfo.ZoneInfo("America/New_York")
_OPEN  = time(9, 15)
_CLOSE = time(16, 0)

class _ReconcileScheduler:
    def __init__(
        self,
        command: MonitoringCommand,
        bus:     MonitoringEventBus,
        cron_register: Callable[[str, Callable], None],   # injected from existing scheduler infra
    ) -> None:
        self._command  = command
        self._bus      = bus
        self._cron     = cron_register
        self._seen_for: date | None = None
        self._bus.subscribe(ReconcileCompleted, self._mark_seen)

    def start(self) -> None:
        # 09:15 ET weekdays
        self._cron("15 9 * * MON-FRI", lambda: self._fire(_today_et()))

    def maybe_run_on_startup(self) -> ReconcileReport | None:
        today = _today_et()
        now_et = datetime.now(_NY).time()
        if today.weekday() >= 5:
            return None                          # weekend
        if not (_OPEN <= now_et <= _CLOSE):
            return None                          # outside the catch-up window
        if self._seen_for == today:
            return None                          # already ran this process
        return self._fire(today)

    def _fire(self, today: date) -> ReconcileReport:
        return self._command.reconcile_preopen(today)

    def _mark_seen(self, evt: ReconcileCompleted) -> None:
        # event lacks a date field today; use the clock at completion time.
        self._seen_for = _today_et()
```

### Hook Into Existing Scheduler

The project already runs a `SchedulerService` consumed by `scheduler_dialog.py`. `_ReconcileScheduler.__init__` takes a `cron_register` callable injected by `AppService` — typically `app_service.scheduler.register_cron` — keeping `_scheduler.py` ignorant of the wider scheduler implementation. This matches the project's dependency-injection convention and keeps the module unit-testable with an in-memory cron stub.

### Single-Flight

Single-flight protection is implemented inside `MonitoringSessionService.reconcile_preopen` itself (DD-EXE-010.001.D01), not in the scheduler — so manual invocations, scheduled invocations, and startup catch-up all share the same guard.

---

## DD-EXE-010.003.D01 — AppService Handoff Wiring

**Parent SRD:** SRD-EXE-010.006, SRD-EXE-009.004
- **Status:** Draft

### `AppService.__init__` Additions

```python
def __init__(self, ...) -> None:
    ...
    # Build the lifecycle service exactly once for the process
    self._lifecycle_query, self._lifecycle_command, self._lifecycle_bus = \
        build_default_service(engine=self._db.engine)

    # Wire GUI bridge (gui/lifecycle_bridge.py — DD-EXE-009.003.D01 follow-up)
    self._lifecycle_bridge = LifecycleBridge(self._lifecycle_bus, parent=self)

    # Hook startup catch-up before LiveBarWorker.start()
    self._reconcile_scheduler = _ReconcileScheduler(
        command=self._lifecycle_command,
        bus=self._lifecycle_bus,
        cron_register=self._scheduler.register_cron,
    )
    self._reconcile_scheduler.start()
    self._reconcile_scheduler.maybe_run_on_startup()

    # Subscribe AppService to ReconcileCompleted so we can push the new
    # keep_set into the live feed before it starts subscribing.
    self._lifecycle_bus.subscribe(ReconcileCompleted, self._on_reconcile_completed)
```

### Replace `_on_screener_results_updated` Body

```python
@pyqtSlot(list)
def _on_screener_results_updated(self, entries: list[FilteredStockEntry]) -> None:
    if not entries:
        return
    # Reconstruct a ScreenerRunResult from entries (or accept the full result if
    # the signal payload is upgraded — small refactor; see implementation phase).
    result = self._latest_screener_result()
    keep   = self._lifecycle_command.on_screener_results(result)

    symbols = sorted(keep.filtered | keep.carryover)
    if not symbols:
        return

    self._start_intraday_loader(symbols)        # SRD-EXE-006.007 logic, fed from KeepSet
    if self._live_bar_worker is not None and self._live_bar_worker.isRunning():
        self._live_bar_worker.set_symbols(symbols)
```

### `_on_reconcile_completed` Handler

```python
def _on_reconcile_completed(self, evt: ReconcileCompleted) -> None:
    today  = _today_et()
    keep   = self._lifecycle_query.keep_set(today)
    symbols = sorted(keep.filtered | keep.carryover)
    log.info("[Lifecycle] Post-reconcile keep set has %d symbol(s)", len(symbols))
    if self._live_bar_worker is not None and self._live_bar_worker.isRunning():
        self._live_bar_worker.set_symbols(symbols)
    # Loader is triggered on the next screener results update — no eager fetch here
```

### Fill Routing (from `strategy_engine` / `execution_engine`)

The single fill seam is `ExecutionEngine.handle_order_fill` (existing — SRD-EXE-002.002). One additional line after the existing `PositionTracker` mutation:

```python
self._lifecycle_command.on_fill(FillEvent(
    symbol=fill.contract.symbol,
    trade_id=str(fill.execution.orderId),
    side=Side.BUY if fill.execution.side == "BOT" else Side.SELL,
    qty=int(fill.execution.shares),
    price=float(fill.execution.price),
    fill_time=fill.execution.time.isoformat(),
    origin=TradeOrigin.SYSTEM if signal.strategy_id != "manual" else TradeOrigin.MANUAL,
    schema_version=1,
))
```

The `origin` resolution uses `signal.strategy_id` for the immediate implementation; once SRD-EXE-009.002 column population is in place, the call site sets origin explicitly based on whether the order originated from `StrategyEngine` (system) or the GUI execution panel (manual).

### Process Ordering on Startup

1. `DatabaseManager.__init__` → `create_schema(...)` → `migrate_lifecycle_columns(...)`
2. `build_default_service(engine)` → returns `(query, command, bus)`
3. `_ReconcileScheduler.start()` + `maybe_run_on_startup()` — may run reconcile synchronously here
4. `LiveBarWorker` constructed but NOT yet started
5. `LiveBarWorker.start()` only after reconcile completes (or is confirmed not needed for today)

Step 3's `maybe_run_on_startup()` is synchronous to enforce the ordering. If the user opens the app mid-session, reconcile completes before any tick subscription begins — preventing the brief window where evicted symbols could re-acquire ticks.

---

# FO-EXE-011 — Strategy Engine — Concurrent Evaluation & Mode Routing

## DD-EXE-011.001.D01 — Threading, asyncio Layout & Lifecycle

**Parent SRD:** SRD-EXE-011.001 — SRD-EXE-011.003, .013
**Status:** Approved

### Package Layout

```
us_swing/src/us_swing/execution/strategy_engine/
├── __init__.py            # public re-exports: StrategyEngine, StrategyEvent union
├── _engine.py             # StrategyEngine(QThread) + asyncio bootstrap
├── _context.py            # _StrategyContext dataclass + _CycleState enum
├── _evaluator.py          # ConditionEvaluator (tokenizer + parser + indicators)
├── _router.py             # signal-queue consumer + Mode/auto_trade dispatch
├── _events.py             # sealed StrategyEvent union
└── _signals.py            # TradeSignal frozen dataclass
```

No module under this package imports `PyQt6` — checked by `import_path_guard` in tests.

### Thread / Loop Topology

```
GUI thread                                     QThread (StrategyEngine)
──────────                                     ──────────────────────────
AppService                                     asyncio.run(_async_run())
  ├─ candle_closed signal  ─── pyqtSignal ──►  _on_candle_closed (slot)
  │                                              └─ asyncio.run_coroutine_threadsafe(
  │                                                     _fanout(symbol, bar), loop)
  ├─ tick_price (FO-EXE-008) ─ pyqtSignal ──►  (not consumed here; FO-EXE-012)
  └─ engine.emergency_stop()  ─ direct call ─►  _on_emergency_stop (re-entrant)
                                                 └─ event-loop call_soon_threadsafe
```

### Top-Level Coroutine Tree

```python
async def _async_run(self) -> None:
    self._queue: asyncio.Queue[TradeSignal] = asyncio.Queue(maxsize=512)
    self._registry: dict[str, _StrategyContext] = await self._load_registry()
    await asyncio.gather(
        self._router_loop(),                 # consumes self._queue
        self._end_time_watcher_loop(),       # 30 s tick, forces EXIT at end_time
        self._emergency_drain_loop(),        # awakens on _emergency_active = True
    )
```

`_fanout(symbol, bar)` is NOT a long-running coroutine — it is scheduled fresh per bar-close event and awaits `asyncio.gather(*per_ctx_tasks)`, then exits. Per-context coroutines are lightweight (a single `_evaluate` call each); no per-strategy long-running task.

### Lifecycle

| Method | Thread | Effect |
|---|---|---|
| `start()` | caller | Inherited `QThread.start()`; spawns event-loop thread |
| `request_stop()` | caller | `call_soon_threadsafe(self._stop_event.set)`; loop unwinds; `quit()` + `wait()` |
| `emergency_stop()` | caller | Synchronous: enqueues EXIT per `Running` cycle, sets `_emergency_active`, blocks on `_quiesced_event` |
| `reload_registry()` | caller | Diffs new vs old contexts on the loop; adds/removes safely |

### Signal Wiring

| AppService signal | Engine slot | Notes |
|---|---|---|
| `candle_closed(symbol)` | `_on_candle_closed` | Slot re-enters asyncio via `run_coroutine_threadsafe` |
| `order_fill(fill_event)` (FO-EXE-002) | `_on_order_fill` | Drives `UnderEntry → Running` / `UnderExit → SquareOff` |
| `order_reject(reject_event)` (FO-EXE-002) | `_on_order_reject` | Rolls back to prior state |
| `circuit_breaker_changed(bool)` (FO-EXE-003) | `_on_circuit_breaker` | Suspends evaluation while True |

---

## DD-EXE-011.002.D01 — `_StrategyContext` & Per-Cycle State Machine

**Parent SRD:** SRD-EXE-011.002, .004, .005, .007
**Status:** Approved

### Cycle State Enum

```python
class _CycleState(StrEnum):
    INACTIVE    = "Inactive"
    ACTIVE      = "Active"
    UNDER_ENTRY = "UnderEntry"
    RUNNING     = "Running"
    UNDER_EXIT  = "UnderExit"
    SQUARE_OFF  = "SquareOff"
```

### Context Dataclass

```python
@dataclass
class _StrategyContext:
    cfg:               StrategyConfig                          # snapshot at load time
    cycles:            dict[str, _CycleState] = field(default_factory=dict)
    cycle_locks:       dict[str, asyncio.Lock] = field(default_factory=dict)
    last_entry_signal: dict[str, TradeSignal | None] = field(default_factory=dict)

    @property
    def name(self) -> str: return self.cfg.name

    def accepts(self, symbol: str) -> bool:
        m = self.cfg.symbol_mode
        if m == "all":           return True
        if m == "include_only":  return symbol in self.cfg.symbols_include
        if m == "exclude_these": return symbol not in self.cfg.symbols_exclude
        return False

    def lock_for(self, symbol: str) -> asyncio.Lock:
        return self.cycle_locks.setdefault(symbol, asyncio.Lock())

    def state(self, symbol: str) -> _CycleState:
        return self.cycles.get(symbol, _CycleState.ACTIVE)
```

### Transition Table

| From → To | Trigger | Side effect |
|---|---|---|
| `ACTIVE` → `UNDER_ENTRY` | `entry_condition` True; capital cap OK | Enqueue `TradeSignal(ENTRY)`; persist `Order_Entry_Status='pending'` |
| `UNDER_ENTRY` → `RUNNING` | `order_fill(entry)` | Persist `Status='Running'`, `Order_Entry_Timestamp`, `Executed_Quantity` |
| `UNDER_ENTRY` → `ACTIVE` | `order_reject(entry)` | Persist `Order_Entry_Status='rejected'`; DEBUG log |
| `RUNNING` → `UNDER_EXIT` | `exit_condition` True OR `ExitTrigger` from FO-EXE-012 OR `end_time` reached OR `emergency_stop()` | Enqueue `TradeSignal(EXIT, reason=…)`; persist `Order_Exit_Status='pending'` |
| `UNDER_EXIT` → `SQUARE_OFF` | `order_fill(exit)` | Persist `Status='SquareOff'`, `Order_Exit_Timestamp` |
| `UNDER_EXIT` → `RUNNING` | `order_reject(exit)` | Persist `Order_Exit_Status='rejected'` |
| `SQUARE_OFF` → `ACTIVE` | Next session window opens | Reset `cycles[symbol]` (or delete entry) |
| any → `INACTIVE` | `cfg.mode = 'disabled'` OR outside schedule | No order activity; preserves any open `RUNNING` per FO-EXE-011 §4 (positions are handled by FO-EXE-012, not closed by mode switch) |

### Lock Granularity

One `asyncio.Lock` per `(strategy_id, symbol)` — held only across the read-state → mutate-state critical section in `_evaluate` and `_on_order_*`. The lock is NOT held while awaiting `RiskManager.can_allocate()` or `queue.put()` to avoid head-of-line blocking.

### Duplicate-Signal Suppression

```python
async def _maybe_emit_entry(ctx, symbol, signal):
    async with ctx.lock_for(symbol):
        s = ctx.state(symbol)
        if s in (UNDER_ENTRY, RUNNING, UNDER_EXIT):
            log.debug("[Strategy] %s %s duplicate ENTRY suppressed", ctx.name, symbol)
            return
        ctx.cycles[symbol] = UNDER_ENTRY
        ctx.last_entry_signal[symbol] = signal
    await self._queue.put(signal)               # outside the lock
```

---

## DD-EXE-011.006.D01 — `ConditionEvaluator` Class Breakdown

**Parent SRD:** SRD-EXE-011.006
**Status:** Approved

### Class Layout

```python
class ConditionEvaluator:
    """
    Parses and evaluates the FO-GUI-013 expression grammar against candle data.
    Stateless across calls; can be shared by all contexts.
    """

    FUNCTION_MAP: ClassVar[dict[str, Callable]] = {
        "Number":        _fn_number,
        "PNL":           _fn_pnl,
        "VWAP":          _fn_vwap,
        "Price":         _fn_price,
        "RSI":           _fn_rsi,
        "ADX":           _fn_adx,
        "EMA":           _fn_ema,
        "SUPERTREND":    _fn_supertrend,
        "SWING":         _fn_swing,
        "MACD":          _fn_macd,
        "BOS_Engulfing": _fn_bos_engulfing,
        "BOSS_EMA":      _fn_boss_ema,
        "BOSS_ADX":      _fn_boss_adx,
        "BOSS_SMT":      _fn_boss_smt,
    }

    def evaluate(self,
                 expr: str,
                 candles: dict[str, pd.DataFrame],
                 symbol: str) -> bool:
        tokens = self._tokenize(expr)
        ast    = self._parse(tokens)
        return bool(self._eval(ast, candles, symbol))
```

### Three-Pass Pipeline

```
expression string
      │
      ▼  _tokenize() — single regex with named groups
[NUMBER, IDENT, STRING, OP, COMMA, LPAREN, RPAREN, AND, OR]
      │
      ▼  _parse() — recursive descent
        parse_or → parse_and → parse_comparison → parse_term
                                                  └─ NUMBER | STRING | function_call | '(' expression ')'
{type: 'BIN_OP'|'FUNC'|'NUMBER'|'STRING', ...} AST
      │
      ▼  _eval(ast, candles, symbol) — post-order
bool
```

### AST Node Schemas

```python
# AST is a dict — no class hierarchy needed
BinOpNode = dict[str, Any]    # {'type': 'BIN_OP', 'op': str, 'left': Node, 'right': Node}
FuncNode  = dict[str, Any]    # {'type': 'FUNC',   'name': str, 'args': list[Node]}
NumNode   = dict[str, Any]    # {'type': 'NUMBER', 'value': int | float}
StrNode   = dict[str, Any]    # {'type': 'STRING', 'value': str}
```

### Indicator Function Signature

Every indicator function in `FUNCTION_MAP` follows a fixed signature:

```python
def _fn_<name>(args: list[Any], candles: dict[str, pd.DataFrame], symbol: str) -> float | bool:
    # args[i] is already a primitive (int/float/str) — strings are unquoted by the tokenizer
    ...
```

Args are validated by arity at parse time (each indicator declares its expected arg count in a sibling dict `_ARITY: dict[str, int]`). Arity mismatch raises `EvaluatorError` with the offending expression.

### Reuse from Legacy `TaEvaluator.py`

The legacy file already implements tokenizer + parser correctly. Port plan:
1. Lift `tokenize()`, `parse()`, `parse_or/_and/_comparison/_term/_arg_list` verbatim into `_evaluator.py` as private methods.
2. Replace per-indicator method bodies with `pandas_ta` calls fed by the `candles[timeframe]` DataFrame for `symbol` (legacy code uses a different broker-data shape).
3. Drop the `Index`, `Underlying_Type`, `Symbol Type` ('Spot'/'RSP') indirection — US Swing is equities-only, the `Symbol Type` parameter is informational and ignored by indicators.
4. Drop `convert_time_code_v1` — timeframe strings (`'1m'`, `'3m'`, …) stay as DataFrame keys; no conversion to seconds.

### Caching

The evaluator does NOT cache indicator results across calls. Indicator values are computed once per `evaluate()` call from the supplied candles dict. Candle DataFrames are reused — the engine passes the same reference to every context evaluating that symbol on a given bar close, so pandas-internal vectorization is the only optimization needed.

---

## DD-EXE-011.009.D01 — Mode + Auto-Trade Router

**Parent SRD:** SRD-EXE-011.008 — SRD-EXE-011.011
**Status:** Approved

### Decision Matrix

| `cfg.mode` | `cfg.auto_trade` | Destination |
|---|---|---|
| `manual` | * | `PendingSignalStore.add(signal)` |
| `auto` | `False` | `PendingSignalStore.add(signal)` |
| `auto` | `True` | `RiskManager.validate()` → `ExecutionRouter.submit()` |
| `disabled` | * | Context not loaded; never reaches router |

### Router Coroutine

```python
async def _router_loop(self) -> None:
    while not self._stop_event.is_set():
        signal = await self._queue.get()
        try:
            ctx = self._registry[signal.strategy_id]
            if ctx.cfg.mode == "manual" or not ctx.cfg.auto_trade:
                self._pending_store.add(signal)              # FO-EXE-011 §7 + §11
                self._bus.publish(StrategySignalPending(signal))
            else:
                result = await self._risk.validate(signal)
                if not result.ok:
                    await self._reject_locally(ctx, signal, reason=result.reason)
                    self._bus.publish(StrategySignalDropped(signal, result.reason))
                    continue
                await self._router.submit(signal, qty=result.qty)
        finally:
            self._queue.task_done()
```

### Capital Cap Path

`RiskManager.can_allocate()` is checked at signal *emission* (`_maybe_emit_entry`, DD-EXE-011.002), BEFORE the signal lands on the queue. A cap-fail there suppresses the signal and rolls the cycle back to `ACTIVE` with a `StrategySignalDropped(reason='capital_cap')` event — never enters the router. This keeps the router's contract simple: every dequeued signal is already capital-eligible.

`RiskManager.validate()` inside the router is the broader pre-submission check (max position size, circuit breaker, daily loss limit). A failure there logs WARNING and emits `StrategySignalDropped`.

### Reject / Rollback Flow

```
Submit → ExecutionRouter
            │
   ┌────────┴────────┐
   ▼                 ▼
order_fill        order_reject
   │                 │
   ▼                 ▼
ctx.cycles[sym]   ctx.cycles[sym]
 = RUNNING         = ACTIVE
                  + StrategyErrored event
```

### End-Time Watcher

```python
async def _end_time_watcher_loop(self) -> None:
    while not self._stop_event.is_set():
        await asyncio.sleep(30)
        now_et = datetime.now(ZoneInfo("America/New_York"))
        for ctx in self._registry.values():
            if ctx.cfg.trade_type != "Intraday":
                continue
            if now_et.time() < parse_time(ctx.cfg.end_time):
                continue
            for symbol, state in list(ctx.cycles.items()):
                if state == _CycleState.RUNNING:
                    await self._force_exit(ctx, symbol, reason="end_time")
```

`_force_exit()` reuses the standard exit path — same queue, same router — but bypasses `exit_condition` evaluation. Positional strategies skip this loop entirely.

### Emergency Stop

```python
def emergency_stop(self) -> None:
    """Synchronous; blocks until every Running position reaches SquareOff."""
    fut = asyncio.run_coroutine_threadsafe(self._do_emergency_stop(), self._loop)
    fut.result(timeout=120)                                  # blocks

async def _do_emergency_stop(self) -> None:
    self._emergency_active = True
    for ctx in self._registry.values():
        for symbol, state in list(ctx.cycles.items()):
            if state == _CycleState.RUNNING:
                await self._force_exit(ctx, symbol, reason="emergency")
    await self._wait_all_quiesced()                          # awaits every UNDER_EXIT → SQUARE_OFF
    self._emergency_active = False
```

While `_emergency_active` is True, `_fanout()` short-circuits — no new entry evaluation, no new exit evaluation beyond what's already in flight.

---

## DD-EXE-011.016.D01 — Per-Symbol Re-Execution Counter (Rex Counter)

**Parent SRD:** SRD-EXE-011.016 — SRD-EXE-011.019
**Status:** Approved

### Semantic

`StrategyConfig.rex_count` is the number of *re-entries* a symbol may take under a strategy beyond its first entry. Total entries allowed per `(strategy_id, symbol)` = `rex_count + 1`. Default `rex_count = 0` therefore permits one entry then locks out further entries until a user-initiated Reset Strategy action.

The counter is stored as `remaining: int`, initialized to `cfg.rex_count`, decremented by 1 after every confirmed entry fill. The entry gate blocks when `remaining < 0` (equivalently `remaining == -1` after the final allowed entry has decremented it).

| `cfg.rex_count` | Counter walk | Total entries |
|---|---|---|
| 0 | 0 → -1 | 1 |
| 1 | 1 → 0 → -1 | 2 |
| 5 | 5 → 4 → 3 → 2 → 1 → 0 → -1 | 6 |
| N | N → … → 0 → -1 | N + 1 |

### Table DDL

```sql
CREATE TABLE IF NOT EXISTS strategy_rex_counters (
    strategy_id   TEXT      NOT NULL,
    symbol        TEXT      NOT NULL,
    remaining     INTEGER   NOT NULL,
    last_updated  TIMESTAMP NOT NULL,
    PRIMARY KEY (strategy_id, symbol)
);
CREATE INDEX IF NOT EXISTS ix_rex_strategy ON strategy_rex_counters (strategy_id);
```

The table lives in the same SQLite file (`~/.usswing/candles.db`) as `trade_cycles`. No foreign-key constraints — counters are independent of cycle state so that a Reset Strategy never has to consider open positions.

### `RexCounterRepository` Interface

```python
class RexCounterRepository:
    def __init__(self, engine: Engine) -> None: ...

    def get(self, strategy_id: str, symbol: str) -> int | None:
        """Return stored `remaining`, or None when the row is absent."""

    def decrement(self, strategy_id: str, symbol: str, *, init_value: int) -> int:
        """Insert with `init_value - 1` if missing, else `remaining -= 1`.
        Returns the new `remaining` value."""

    def reset(self, strategy_id: str) -> int:
        """DELETE all rows for `strategy_id`. Returns deleted row count."""
```

`get()` returning `None` is treated by callers as `remaining = cfg.rex_count` (first-evaluation case). `decrement()` is the only writer; the engine never UPDATEs `remaining` to a specific value other than via decrement, keeping the data flow append-only-ish.

### Entry Gate Integration in `_router.evaluate()`

The gate is placed **after** `entry_condition` fires (the expensive AST evaluation) and **before** the capital-cap check, so a blocked entry still surfaces a `StrategySignalDropped` payload with a meaningful `entry_price` for the GUI log:

```python
# inside _CycleState.ACTIVE branch, after `if not fired: return`
remaining = self._rex_counters.get(ctx.name, symbol)
if remaining is not None and remaining < 0:
    signal_pre = self._build_entry_signal(ctx, symbol, bar)
    self._bus.publish(
        StrategySignalDropped(signal=signal_pre, reason="rex_limit")
    )
    log.info("[Strategy] %s ENTRY blocked for %s — rex limit reached", ctx.name, symbol)
    return

# … existing capital-cap check follows …
```

A `None` return (no row yet) skips the gate — the symbol is on its first ever entry under this strategy. No state mutation happens on a rex-blocked drop; the cycle stays in `ACTIVE` and re-evaluation continues on subsequent bars (the gate will keep dropping).

### Counter Decrement on Entry Fill

Decrement runs inside `_router.on_order_fill()` after the `StrategyEntered` event is published:

```python
if fill.is_entry:
    ctx.cycles[fill.symbol] = _CycleState.RUNNING
    self._bus.publish(StrategyEntered(...))
    self._rex_counters.decrement(
        fill.strategy_id, fill.symbol, init_value=ctx.cfg.rex_count
    )
```

Placement after the event publish keeps the counter mutation off the GUI's critical path. The decrement is idempotent on duplicate fill events because `trade_cycles` enforces uniqueness on `entry_order_id` (SRD-EXE-012.003) — a duplicate fill never reaches `on_order_fill` twice for the same order.

### Reset Strategy Flow

`RexCounterRepository.reset(strategy_id)` is the only public surface for clearing counters. It is invoked from the GUI Reset icon (SRD-GUI-013.015) after a `QMessageBox` confirmation. The reset is one DELETE statement and is independent of any in-flight cycles — OPEN positions remain open, only the future-entry budget is cleared.

### Cross-Restart Correctness

Because the repository is queried lazily on every entry evaluation (no in-memory cache), counter state survives an engine restart automatically. A symbol that hit its limit yesterday remains locked today until the user explicitly resets.

Performance: one indexed SELECT per entry-condition firing. With ≥ 50 strategies × ≥ 500 symbols × 5 entries/day this is < 125 k SELECTs/day on a local SQLite file — negligible compared to the candle-write workload.

---

# FO-EXE-012 — Trade Cycle Ledger — Live Per-Cycle State & Persistence

## DD-EXE-012.001.D01 — Table DDL & Schema Migration

**Parent SRD:** SRD-EXE-012.001
**Status:** Approved

### Package Layout

```
us_swing/src/us_swing/execution/trade_cycle/
├── __init__.py          # public re-exports: TradeCycleQuery, TradeCycleCommand, build_default_service
├── _schema.py           # SQLAlchemy Table definition (re-exported via db/schema.py)
├── _repository.py       # DB access layer (no business logic)
├── _service.py          # lifecycle + tick-update + exit-trigger
├── _dto.py              # CycleSnapshot frozen dataclass + invariants
└── _events.py           # sealed TradeCycleEvent union
```

No `PyQt6` import anywhere under this package.

### `trade_cycles` Table

```python
trade_cycles = sa.Table(
    "trade_cycles", metadata,
    sa.Column("cycle_id",                sa.Integer, primary_key=True, autoincrement=True),
    # Identity
    sa.Column("strategy_id",             sa.Text,    nullable=False),
    sa.Column("symbol",                  sa.Text,    nullable=False),
    sa.Column("user_id",                 sa.Integer, nullable=False),
    sa.Column("monitoring_session_date", sa.Text,    nullable=False),     # FK → monitoring_session.session_date
    # Entry
    sa.Column("entry_time",              sa.Text,    nullable=False),     # ISO UTC
    sa.Column("entry_price",             sa.Float,   nullable=False),
    sa.Column("entry_qty",               sa.Integer, nullable=False),
    sa.Column("entry_order_id",          sa.Text,    nullable=False, unique=True),
    # Risk-snapshot (frozen at entry)
    sa.Column("hard_stop_loss",          sa.Float,   nullable=False),
    sa.Column("target_price",            sa.Float),                       # null when target disabled
    sa.Column("target_type",             sa.Text,    nullable=False),     # 'fixed' | 'trailing'
    sa.Column("stoploss_type",           sa.Text,    nullable=False),
    sa.Column("trailing_mode",           sa.Text),                        # '$' | '%' — null when disabled
    sa.Column("trailing_offset",         sa.Float),                       # null when disabled
    # Live
    sa.Column("current_price",           sa.Float),
    sa.Column("current_pnl_usd",         sa.Float),
    sa.Column("current_pnl_pct",         sa.Float),
    sa.Column("highest_price_seen",      sa.Float),
    sa.Column("trailing_stop_level",     sa.Float),
    sa.Column("effective_stop",          sa.Float),
    sa.Column("last_updated_at",         sa.Text),
    # Exit
    sa.Column("exit_time",               sa.Text),
    sa.Column("exit_price",              sa.Float),
    sa.Column("exit_qty",                sa.Integer),
    sa.Column("exit_order_id",           sa.Text, unique=True),
    sa.Column("exit_reason",             sa.Text),                        # see enum below
    # Outcome
    sa.Column("realized_pnl_usd",        sa.Float),
    sa.Column("realized_pnl_pct",        sa.Float),
    sa.Column("state",                   sa.Text, nullable=False,
              server_default="OPENING"),                                  # see state machine
    sa.Column("opened_at",               sa.Text, nullable=False),
    sa.Column("closed_at",               sa.Text),
)

sa.Index("idx_trade_cycles_state_symbol", trade_cycles.c.state, trade_cycles.c.symbol)
sa.Index("idx_trade_cycles_strategy_symbol_state",
         trade_cycles.c.strategy_id, trade_cycles.c.symbol, trade_cycles.c.state)
```

### Enums (string literals, validated by repository on write)

```python
CYCLE_STATES   = frozenset({"OPENING", "OPEN", "CLOSING", "CLOSED", "ABORTED"})
EXIT_REASONS   = frozenset({"strategy", "hard_sl", "target", "trailing_sl",
                             "end_time", "manual", "emergency"})
TARGET_TYPES   = frozenset({"fixed", "trailing"})
STOPLOSS_TYPES = frozenset({"fixed", "trailing"})
TRAILING_MODES = frozenset({"$", "%"})
```

Each repository write that touches one of these columns asserts membership; SQLite enforces nothing here — validation is application-side.

### Migration

Pure additive: `create_schema(engine, checkfirst=True)` in `db/schema.py` already runs on every startup. The table appears on first run; existing databases are unaffected. No `migrate_lifecycle_columns()` entry needed.

---

## DD-EXE-012.002.D01 — `_repository.py` — Query & Mutation Methods

**Parent SRD:** SRD-EXE-012.003, .007, .008, .009, .010, .013
**Status:** Approved

### Snapshot DTO

```python
@dataclass(frozen=True, slots=True)
class CycleSnapshot:
    schema_version:    int = 1
    cycle_id:          int = 0
    strategy_id:       str = ""
    symbol:            str = ""
    user_id:           int = 0
    state:             str = "OPENING"
    entry_time:        str = ""
    entry_price:       float = 0.0
    entry_qty:         int   = 0
    hard_stop_loss:    float = 0.0
    target_price:      float | None = None
    target_type:       str = "fixed"
    stoploss_type:     str = "fixed"
    trailing_mode:     str | None = None
    trailing_offset:   float | None = None
    current_price:     float | None = None
    current_pnl_usd:   float | None = None
    current_pnl_pct:   float | None = None
    highest_price_seen: float | None = None
    trailing_stop_level: float | None = None
    effective_stop:    float | None = None
    exit_time:         str | None = None
    exit_price:        float | None = None
    exit_qty:          int | None = None
    exit_reason:       str | None = None
    realized_pnl_usd:  float | None = None
    realized_pnl_pct:  float | None = None
```

### Repository Class

```python
class TradeCycleRepository:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    # ── Queries ───────────────────────────────────────────────────────────
    def open_cycles(self) -> tuple[CycleSnapshot, ...]: ...
    def cycle(self, cycle_id: int) -> CycleSnapshot | None: ...
    def history(self, *, symbol: str | None = None,
                strategy_id: str | None = None,
                days: int = 30) -> tuple[CycleSnapshot, ...]: ...
    def find_open(self, strategy_id: str, symbol: str) -> CycleSnapshot | None: ...
    def find_by_entry_order(self, entry_order_id: str) -> CycleSnapshot | None: ...

    # ── Mutations ─────────────────────────────────────────────────────────
    def insert_open(self, *, row: dict) -> CycleSnapshot: ...           # OPENING → OPEN
    def update_live(self, cycle_id: int, *, fields: dict) -> None: ...  # tick-driven; no event
    def update_state(self, cycle_id: int, new_state: str) -> CycleSnapshot: ...
    def update_risk(self, cycle_id: int, *, fields: dict) -> CycleSnapshot: ...
    def close(self, cycle_id: int, *, exit_fields: dict) -> CycleSnapshot: ...
    def abort(self, cycle_id: int, reason: str) -> CycleSnapshot: ...
```

### Transaction Boundaries

| Method | Tx | Why |
|---|---|---|
| `open_cycles()` / `cycle()` / `history()` / `find_*()` | autocommit | read-only, single SELECT |
| `insert_open()` | one tx | INSERT + same-tx `find_open` invariant check (defence vs FO-EXE-012 §9) |
| `update_live()` | autocommit | single UPDATE; batched at service layer via tick throttle |
| `update_state()` / `update_risk()` / `close()` / `abort()` | one tx | UPDATE + same-tx SELECT to return fresh `CycleSnapshot` |

### Duplicate-Open Guard

`insert_open()` runs inside a tx with `SELECT … FROM trade_cycles WHERE strategy_id=? AND symbol=? AND state IN ('OPENING','OPEN','CLOSING')` — if it returns a row, raises `DuplicateOpenCycleError` and rolls back. Guarantees the FO-EXE-012 §8 invariant under concurrent writers.

### State Machine (DB-Level)

| From → To | Repository method | Required field changes |
|---|---|---|
| (none) → `OPENING` | `insert_open(state='OPENING')` (only on signal-emit path; common path inserts as `OPEN` directly via `on_entry_fill`) | — |
| `OPENING` → `OPEN` | `update_state(cycle_id, "OPEN")` | — |
| `OPENING` → `ABORTED` | `abort(cycle_id, reason)` | `exit_reason`, `closed_at` |
| `OPEN` → `CLOSING` | `update_state(cycle_id, "CLOSING")` | — |
| `CLOSING` → `CLOSED` | `close(cycle_id, exit_fields=…)` | all exit fields + `realized_pnl_*` + `closed_at` |
| `CLOSING` → `OPEN` | `update_state(cycle_id, "OPEN")` | rollback on exit reject |

`update_state` rejects illegal transitions (e.g., `CLOSED` → anything) with `InvalidStateTransitionError`. Allowed-transitions dict is a module constant in `_repository.py`.

---

## DD-EXE-012.005.D01 — Tick Throttle & Live Update Engine

**Parent SRD:** SRD-EXE-012.005
**Status:** Approved

### Per-Cycle Throttle State

The service maintains a small in-memory accumulator per open cycle so tick updates batch without losing the latest tick.

```python
@dataclass
class _TickAccumulator:
    symbol:           str
    cycle_id:         int
    latest_price:     float
    highest_seen:     float
    last_persist_at:  float       # monotonic seconds
    dirty:            bool        # at least one tick since last persist
    flush_handle:     asyncio.TimerHandle | None = None

_THROTTLE_MS = 500
```

### Tick Path

```python
def _on_tick(self, symbol: str, price: float) -> None:
    """Called from LiveTickWorker on the GUI thread; bounces into the service loop."""
    asyncio.run_coroutine_threadsafe(self._handle_tick(symbol, price), self._loop)

async def _handle_tick(self, symbol: str, price: float) -> None:
    for acc in self._accs_for_symbol(symbol):                     # 0..N (usually 0 or 1)
        if price > acc.highest_seen:
            acc.highest_seen = price
        acc.latest_price = price
        acc.dirty        = True
        now = self._loop.time()
        elapsed = (now - acc.last_persist_at) * 1000
        if elapsed >= _THROTTLE_MS:
            await self._flush(acc)
        elif acc.flush_handle is None:
            delay = (_THROTTLE_MS - elapsed) / 1000
            acc.flush_handle = self._loop.call_later(delay,
                lambda a=acc: asyncio.create_task(self._flush(a)))
```

### Flush Path

```python
async def _flush(self, acc: _TickAccumulator) -> None:
    if not acc.dirty:
        return
    snap = self._repo.cycle(acc.cycle_id)
    if snap is None or snap.state not in ("OPEN", "CLOSING"):
        return                                                    # cycle closed concurrently
    live = self._compute_live(snap, acc.latest_price, acc.highest_seen)
    self._repo.update_live(acc.cycle_id, fields=live)
    acc.last_persist_at = self._loop.time()
    acc.dirty           = False
    acc.flush_handle    = None
    fresh = self._repo.cycle(acc.cycle_id)
    self._bus.publish(CycleUpdated(snapshot=fresh, schema_version=1))
    self._check_exit_triggers(fresh, acc.latest_price)            # DD-EXE-012.006.D01
```

### Live-Field Computation

```python
def _compute_live(self, snap: CycleSnapshot, price: float, highest: float) -> dict:
    pnl_usd = (price - snap.entry_price) * snap.entry_qty
    pnl_pct = (price - snap.entry_price) / snap.entry_price * 100.0

    if snap.trailing_mode == "$":
        trail = highest - (snap.trailing_offset or 0.0)
    elif snap.trailing_mode == "%":
        trail = highest * (1.0 - (snap.trailing_offset or 0.0) / 100.0)
    else:
        trail = None

    # Trailing only moves up: never below prior recorded level
    if trail is not None and snap.trailing_stop_level is not None:
        trail = max(trail, snap.trailing_stop_level)

    effective = max(snap.hard_stop_loss, trail) if trail is not None else snap.hard_stop_loss

    return {
        "current_price":       price,
        "current_pnl_usd":     pnl_usd,
        "current_pnl_pct":     pnl_pct,
        "highest_price_seen":  highest,
        "trailing_stop_level": trail,
        "effective_stop":      effective,
        "last_updated_at":     datetime.now(timezone.utc).isoformat(),
    }
```

### Throttle Properties

- **Last-tick-wins:** the accumulator always holds the newest price; intermediate ticks coalesce.
- **No starvation:** the trailing `call_later` guarantees a flush within `_THROTTLE_MS` even if no further ticks arrive.
- **Single-writer per cycle:** `_flush` is the only path that writes `update_live`; no per-cycle DB locks needed.
- **Skip on terminal state:** the inside-`_flush` re-fetch is the race guard against an exit-fill confirming between tick receipt and flush.

### Lifecycle of `_TickAccumulator`

| Event | Effect |
|---|---|
| `on_entry_fill` opens a cycle | Insert a new `_TickAccumulator` keyed on `cycle_id`; subscribe symbol to `LiveTickWorker` if not already |
| `CycleClosed` / `CycleAborted` | Remove the accumulator; cancel pending `flush_handle`; unsubscribe symbol if no other cycle holds it |
| Service shutdown | Flush all dirty accumulators synchronously, then discard |

---

## DD-EXE-012.006.D01 — Exit Trigger Emission & ExecutionRouter Handoff

**Parent SRD:** SRD-EXE-012.006
**Status:** Approved

### Trigger Evaluation Order

After every successful `_flush`, the service checks exit conditions in fixed precedence:

```
1. price ≥ target_price                  → reason='target'
2. price ≤ effective_stop                → reason='trailing_sl' if trailing was the floor,
                                            else 'hard_sl'
3. neither                               → no trigger
```

Target wins ties against effective_stop because a position that simultaneously crosses both is more likely profitable (gap-up + drag); preferring target avoids a paradoxical loss-exit on a profitable bar.

### Trigger Method

```python
def _check_exit_triggers(self, snap: CycleSnapshot, price: float) -> None:
    if snap.state != "OPEN":
        return                                              # already closing; one-shot
    reason: str | None = None

    if snap.target_price is not None and price >= snap.target_price:
        reason = "target"
    elif snap.effective_stop is not None and price <= snap.effective_stop:
        reason = ("trailing_sl"
                  if (snap.trailing_stop_level is not None
                      and snap.trailing_stop_level >= snap.hard_stop_loss
                      and price <= snap.trailing_stop_level)
                  else "hard_sl")

    if reason is None:
        return
    self._repo.update_state(snap.cycle_id, "CLOSING")
    self._bus.publish(ExitTrigger(cycle_id=snap.cycle_id,
                                   symbol=snap.symbol,
                                   reason=reason,
                                   trigger_price=price,
                                   schema_version=1))
```

### One-Shot Guarantee

The `state != "OPEN"` early return is the one-shot guard. Once the state has flipped to `CLOSING`, subsequent ticks that still satisfy the trigger conditions emit nothing. `update_state` is implemented as `UPDATE … WHERE state='OPEN'` (compare-and-swap pattern); concurrent triggers from a near-simultaneous tick and a strategy-driven exit are mutually exclusive — only one of them flips the state, only one `ExitTrigger` fires.

### Event Payload

```python
@dataclass(frozen=True, slots=True)
class ExitTrigger:
    cycle_id:       int
    symbol:         str
    reason:         str             # 'target' | 'hard_sl' | 'trailing_sl'
    trigger_price:  float
    schema_version: int = 1
```

`ExitTrigger` is the only event emitted by the trade-cycle service that has business-logic side effects elsewhere — every other event is informational for the GUI.

### FO-EXE-002 Handoff

`ExecutionEngine` subscribes to the bus and consumes `ExitTrigger`:

```python
def _on_exit_trigger(self, evt: ExitTrigger) -> None:
    snap = self._cycle_query.cycle(evt.cycle_id)
    if snap is None or snap.state != "CLOSING":
        return                                              # stale event
    self.submit_market_sell(
        symbol     = snap.symbol,
        qty        = snap.entry_qty,
        user_id    = snap.user_id,
        cycle_id   = snap.cycle_id,
        reason_tag = evt.reason,
    )
```

The fill confirmation for that SELL flows back through `on_exit_fill` in the service, which calls `repo.close(cycle_id, …)` and publishes `CycleClosed`.

### Bypass of Mode / auto_trade

Tick-driven exits fire regardless of the originating strategy's `Mode` or `auto_trade` — they are safety floors, not strategy decisions. The router (DD-EXE-011.009.D01) is not involved in this exit path; the service hands directly to `ExecutionEngine`.

### Failure Modes

| Failure | Behaviour |
|---|---|
| `ExitTrigger` published but no broker submission within 5 s | `ExecutionEngine` is the sole owner of submission timeouts; cycle remains `CLOSING` and the next tick re-emits no event (one-shot) |
| Broker rejects SELL | `ExecutionEngine` emits `order_reject`; service moves cycle `CLOSING` → `OPEN` via `update_state` and logs WARNING `[Cycle] {cycle_id} exit rejected — re-arming triggers` |
| Subsequent tick still satisfies trigger after rollback | A fresh `ExitTrigger` fires (state is back to `OPEN`, one-shot guard cleared) |

---

# FO-EXE-013 — Strategy Run Lifecycle

## DD-EXE-013.001.D01 — Engine Evaluation Decision Tree & StrategyRunState Rollout

**Parent SRD:** SRD-EXE-013.001 — SRD-EXE-013.008
**Status:** Draft

### Evaluation Decision Tree (per strategy × per symbol × per bar-close)

```python
async def _evaluate(ctx: _StrategyContext, symbol: str, bar: OHLCVBar) -> None:
    # Gate 1: run-state (replaces _CycleState check)
    if ctx.run_state == StrategyRunState.STOPPED:
        return                                         # SRD-EXE-013.004

    if ctx.run_state == StrategyRunState.SQUARING_OFF:
        return                                         # SRD-EXE-013.007 — forced EXITs handled by _squaring_off_loop

    # Gate 2: schedule guard (unchanged)
    if not _within_schedule(ctx, now_et()):
        return

    # Gate 3: has-open-cycle query (replaces ctx.cycles[symbol] lookup)
    has_open = self._cycle_query.has_open_cycle(ctx.cfg.strategy_id, symbol)

    if has_open:
        await self._maybe_emit_exit(ctx, symbol, bar)  # SRD-EXE-013.006
    else:
        await self._maybe_emit_entry(ctx, symbol, bar) # SRD-EXE-013.005
```

`has_open_cycle(strategy_id, symbol)` returns `True` for any cycle in `OPENING`, `OPEN`, or `CLOSING`.

### SQUARING_OFF → STOPPED Auto-Transition

```python
async def _squaring_off_loop(self) -> None:
    while not self._stop_event.is_set():
        await asyncio.sleep(2)
        for ctx in self._registry.values():
            if ctx.run_state != StrategyRunState.SQUARING_OFF:
                continue
            if self._cycle_query.open_cycles_for_strategy(ctx.cfg.strategy_id):
                continue
            ctx.run_state = StrategyRunState.STOPPED
            self._persist_run_state(ctx)
            self._bus.publish(StrategyRunStateChanged(
                strategy_id=ctx.cfg.strategy_id,
                new_state=StrategyRunState.STOPPED,
            ))
            log.info("[Strategy] %s auto-stopped — all cycles closed", ctx.cfg.name)
```

`open_cycles_for_strategy` queries `trade_cycles` for rows in `OPENING` / `OPEN` / `CLOSING` with the given `strategy_id`.

### _CycleState → StrategyRunState Equivalence Table

| Old `_CycleState` | Equivalent derivation |
|---|---|
| `INACTIVE` | `run_state == STOPPED` |
| `ACTIVE` | `run_state == RUNNING` and `has_open_cycle == False` |
| `UNDER_ENTRY` | `run_state == RUNNING` and cycle in `TradeCycleState.OPENING` |
| `RUNNING` | `run_state == RUNNING` and cycle in `TradeCycleState.OPEN` |
| `UNDER_EXIT` | `run_state == RUNNING` and cycle in `TradeCycleState.CLOSING` |
| `SQUARE_OFF` | `run_state == SQUARING_OFF` |

### Run-State Persistence

```python
def _persist_run_state(self, ctx: _StrategyContext) -> None:
    ctx.cfg.strategy_signal["run_state"] = ctx.run_state.value
    save_strategies(self._registry_path, ...)
```

Debounced to ≥ 250 ms per strategy — same guard as `strategy_signal` writeback in SRD-EXE-011.014.

### Legacy Status Migration in `_load_registry()`

```python
def _migrate_run_state(record: dict) -> StrategyRunState:
    sig = record.get("strategy_signal", {})
    if "run_state" in sig:
        return StrategyRunState(sig["run_state"])   # already migrated
    status = sig.get("Status", "Inactive")
    if status in ("Active", "Running"):
        return StrategyRunState.RUNNING
    return StrategyRunState.STOPPED
```

Resolves the FO-EXE-011 §1 contradiction (force `Active` on load vs trust verbatim): **trust verbatim wins** (decision log #3). On first load, legacy values are mapped once and `run_state` replaces `Status` in the persisted file.

---

## DD-EXE-015.001.D01 — BrokerAdapter (translation, selection, routing)

**Parent SRD:** SRD-EXE-015.001, SRD-EXE-015.004

The adapter is the only execution component that knows a concrete broker. It
satisfies the existing `ExecutionSubmitter.submit(signal, qty) -> int | None`
surface so the router (`_router.py:264`) is unchanged, while underneath it
speaks the neutral broker contract.

```python
class BrokerAdapter:
    def __init__(self, broker: Broker, ingestion: OrderIngestion) -> None:
        self._broker = broker
        self._ingestion = ingestion
        broker.on_event(self._on_broker_event)     # Broker -> Execution channel

    # ── ExecutionSubmitter surface (called by the router) ──
    def submit(self, signal: TradeSignal, qty: int) -> int | None:
        req = OrderRequest(
            client_ref = signal.signal_id,
            symbol     = signal.symbol,
            side       = OrderSide.BUY if signal.action is Action.ENTRY else OrderSide.SELL,
            quantity   = qty,
            order_type = OrderType.MARKET,
        )
        oid = self._broker.place_order(req)         # acceptance only
        self._ingestion.on_order_accepted(req, oid) # writes trades(NEW)
        return int(oid)

    # ── Broker -> Execution (async fills) ──
    def _on_broker_event(self, event: OrderEvent) -> None:
        self._ingestion.on_order_event(event)
```

**Selection** (SRD-EXE-015.004): a factory builds the adapter with `SimBroker`
or `IBKRBroker` from `users.mode` plus a system-level switch. `SimBroker` is
always constructible for per-user dry-run regardless of system mode. No
separate factory module — selection lives here at construction.

**Threading.** IBKR events arrive on the ib_insync loop; the adapter marshals
`_on_broker_event` onto the engine loop via `call_soon_threadsafe` (the same
pattern `StrategyEngine.on_order_fill` already uses).

---

## DD-EXE-015.002.D01 — Order Ingestion Pipeline

**Parent SRD:** SRD-EXE-015.002, SRD-EXE-015.003, SRD-EXE-015.005

One broker-agnostic component owns all persistence. It contains **no branch on
broker type** — `SimBroker` and `IBKRBroker` events run identical code. This is
the piece that ends the paper bypass: paper orders now write `trades` exactly
like live orders.

```python
class OrderIngestion:
    def on_order_accepted(self, req: OrderRequest, broker_order_id: str) -> None:
        # SRD-EXE-015.002 — trade_id == broker order id, state NEW, no bypass
        self._db.insert_trade(TradeRecord(
            trade_id        = broker_order_id,
            symbol          = req.symbol,
            side            = req.side.value,
            quantity        = req.quantity,
            order_state     = _to_order_state(req.side, OrderStatus.NEW),
            filled_quantity = 0,
            ...,
        ))

    def on_order_event(self, ev: OrderEvent) -> None:
        # SRD-EXE-015.003 — advance trades, feed engine, advance cycle + position
        self._db.update_trade_fill(
            trade_id        = ev.broker_order_id,
            filled_quantity = ev.filled_quantity,
            order_state     = _to_order_state(_side_of(ev), ev.status),
            exit_time       = now if _is_exit(ev) else None,
            exit_price      = ev.fill_price if _is_exit(ev) else None,
        )
        self._engine.on_order_fill(FillEvent(
            strategy_id = _strategy_of(ev.client_ref),
            symbol      = _symbol_of(ev.client_ref),
            is_entry    = _is_entry(ev),
            fill_price  = ev.fill_price or 0.0,
            fill_qty    = ev.filled_quantity,
            order_id    = int(ev.broker_order_id),
        ))
        # trade_cycles advances off the same FillEvent (FO-EXE-012); it is the
        # single live-position surface — the legacy positions table is retired
        # in Phase 6, so ingestion does not write it.
```

### Status mapping (SRD-EXE-015.005)

```python
def _to_order_state(side: OrderSide, status: OrderStatus) -> str:
    enum = E.BuyOrderState if side is OrderSide.BUY else E.SellOrderState
    try:
        return enum(status.value).value     # 1:1 — values are identical
    except ValueError:
        raise BrokerStatusError(f"No execution state for {status!r}")  # fail loud
```

`client_ref` (the originating `signal.signal_id`) is the join key the pipeline
uses to recover strategy/symbol/side and to correlate an `OrderEvent` back to
its order. `trades.trade_id == broker_order_id` keeps the order ledger joined to
`trade_cycles.entry_order_id` / `exit_order_id`, which already store that id.

---

# FO-EXE-016 — Retire `positions` Table; OrderIngestion-Driven Monitoring Lifecycle

## DD-EXE-016.001.D01 — Ingestion → Monitoring-Lifecycle Seam

**Parent SRD:** SRD-EXE-016.001, SRD-EXE-016.002, SRD-EXE-016.005

The `MONITORING → ENTERED → EXITED` ledger lives in the `monitoring_session`
table and is created (`MONITORING`) by the screener path (`on_screener_results`)
— unchanged. The two later transitions move off the dead `MonitoringCommand.on_fill`
hook and onto the live `OrderIngestion` fill path.

`OrderIngestion` already advances `trades`, the strategy engine, and `trade_cycles`
on each `OrderEvent`. We add an **optional, narrow lifecycle sink** — it performs
only the ledger transition; it never touches `positions` or `trades` (those belong
to ingestion). Two new thin `MonitoringCommand` methods wrap the existing
repository transitions:

```python
# core/monitoring_session/_service.py  (MonitoringCommand)
def mark_entered(self, symbol: str, entered_at: str, trade_id: str) -> None:
    """Flip the symbol's earliest open MONITORING row to ENTERED (idempotent)."""
    row = self._repo.fetch_earliest_open_monitoring_row(symbol)
    if row is None:
        return                       # no ledger row (e.g. unscreened manual trade)
    self._repo.transition_to_entered(
        session_date=row.session_date, symbol=symbol,
        entered_at=entered_at, trade_id=trade_id,
    )

def mark_exited(self, symbol: str, exited_at: str) -> None:
    """Flip the symbol's ENTERED row to EXITED on cycle close (idempotent)."""
    row = self._repo.fetch_entered_row(symbol)   # existing/derivable lookup
    if row is None:
        return
    self._repo.transition_to_exited(
        session_date=row.session_date, symbol=symbol, exited_at=exited_at,
    )
```

`OrderIngestion` gains an optional `lifecycle` dependency and calls it **after**
the cycle advance, gated on fill completion and direction:

```python
# execution/order_ingestion.py — inside on_order_event, after cycle advance
if self._lifecycle is not None:
    if is_entry and _is_complete_fill(order_state):
        self._lifecycle.mark_entered(symbol, fill_time, ev.broker_order_id)
    elif (not is_entry) and cycle_now_closed:
        self._lifecycle.mark_exited(symbol, fill_time)
```

`cycle_now_closed` is read from the `TradeCycleCommand` result already produced in
the same handler (the cycle reaches `CLOSED` on a completing exit fill). Both marks
are **idempotent** — re-delivery of an event must not double-transition (the ledger
transition methods already no-op when the target state is reached).

**Wiring (`app_service`):** `OrderIngestion(...)` is constructed with
`lifecycle=self._lifecycle_command` (the `MonitoringCommand` from
`build_default_service`). When the lifecycle service is unavailable the sink stays
`None` and ingestion behaves exactly as today.

## DD-EXE-016.003.D01 — Carryover Repoint to `trade_cycles`

**Parent SRD:** SRD-EXE-016.003, SRD-EXE-016.004

`MonitoringRepository.open_system_position_symbols` stops reading `positions` and
returns the symbols of all non-terminal `trade_cycles`. `core/` must not import the
execution-owned `trade_cycles` table object (layering), so the query is by table
name on the shared engine — the same pattern used by `health.py`:

```python
# core/monitoring_session/_repository.py
def open_system_position_symbols(self) -> frozenset[str]:
    stmt = sa.text(
        "SELECT DISTINCT symbol FROM trade_cycles "
        "WHERE state NOT IN ('CLOSED', 'ABORTED')"
    )
    with self._engine.connect() as conn:
        return frozenset(r[0] for r in conn.execute(stmt))
```

The engine is shared (`app_service` builds one `DatabaseManager`; the trade-cycle
service and the monitoring service use its engine), so `trade_cycles` is always in
the same database. Removed from the repository (each was read/written only by the
retired `on_fill`): `upsert_position_with_anchor`, `has_open_system_position`,
`position_anchor`, and the `positions` import. The `MonitoringQuery` surface drops
`has_open_system_position` (no external caller); `open_system_positions` survives,
now delegating to the repointed `open_system_position_symbols`.

## DD-EXE-016.006.D01 — Drop the `positions` Table

**Parent SRD:** SRD-EXE-016.006

Done **last**, alone in its own commit, only after the seam (016.001) and the
repoint (016.003) are merged and green — at that point nothing reads or writes
`positions`.

- **`db/schema.py`:** delete the `positions = sa.Table(...)` definition and its
  index; remove `positions` from `_LIFECYCLE_COLUMN_ADDITIONS` /
  `_LIFECYCLE_COLUMN_REMOVALS`. Add a one-time `DROP TABLE IF EXISTS positions` to
  the lifecycle migration so existing databases shed the table (fresh DBs simply
  never create it once it leaves the metadata).
- **`db/manager.py`:** delete `upsert_position`, `delete_position`,
  `fetch_open_positions`. `PositionRecord` (data model) may remain unused or be
  removed in the same pass if no caller survives a grep.
- **Tests:** update `tests/integration/test_lifecycle_e2e.py` and the monitoring /
  db-manager tests that assert against `positions`; delete the dead `on_fill` tests
  in `tests/core/monitoring_session/test_service.py` and the `positions`-writer /
  `position_anchor` / `has_open_system_position` cases in `test_repository.py`.

**Acceptance gate:** a grep for the `positions` `sa.Table`, `upsert_position`,
`delete_position`, or `fetch_open_positions` returns nothing outside migration
history (SRD-EXE-016.006 AC #4), the app imports, and the suite stays at baseline.

---

# FO-EXE-017 — Absolute Capital Allocation, Capital-Max Sizing & Advisory Risk Warnings

## DD-EXE-017.001.D01 — `RiskConfig` Migration & Effective-Capital Resolution

**Parent SRD:** SRD-EXE-017.001, SRD-EXE-017.002, SRD-EXE-017.014

### Data-model change

`RiskConfig.max_allocation_pct: float` (percent) is replaced by
`max_capital_value: float` (absolute dollars). The same edit lands in both
`data/models.py` and `config/settings.py`, and in the JSON (de)serializers
`gui/user_store.py::_to_dict`/`_from_dict` and `user/manager.py::_default_settings_json`.

```python
# data/models.py  (and config/settings.py mirror)
@dataclass
class RiskConfig:
    risk_per_trade_pct: float = 1.0
    max_position_value: float = 10_000.0
    max_capital_value:  float = 2_000.0   # was: max_allocation_pct = 50.0
    max_daily_loss_pct: float = 2.0
    default_order_type: str   = "MKT"
    confirm_orders:     bool  = True
```

**One-time migration on load** (`user_store._from_dict`): if the persisted JSON
still carries `max_allocation_pct` and no `max_capital_value`, drop the percent key
and fall back to the default `max_capital_value` (a percent of an unknown equity
cannot be converted to dollars deterministically, so we do not attempt a numeric
port — we log one INFO line per migrated user).

### Effective capital

A single provider resolves the dollar budget used by every sizing/cap check. It
lives on `AppService` and is injected into `RiskManager` as `account_provider`
already exists; we add a sibling `effective_capital_provider`:

```python
def effective_capital(user: UserProfile, acct: AccountState, mode: str) -> float:
    cap = user.risk_config.max_capital_value
    if mode == "paper":
        return cap
    cash = acct.total_cash_value
    if cap > cash:
        log.warning("[Risk] Max Capital ($%.0f) exceeds broker cash ($%.0f) — using $%.0f",
                    cap, cash, 0.9 * cash)
        return 0.9 * cash
    return cap
```

- Paper: budget = stored `max_capital_value`; this is also fed to
  `AccountState.equity` for paper so existing equity-based displays stay coherent.
- Live: reconcile runs **once per connect** (in the account-ready slot,
  `app_service._on_account_data_ready`), not per signal. The 90%-of-cash result is
  cached as `self._effective_capital` and read synchronously by the engine.
- The stored setting is never mutated — only the runtime value differs.

## DD-EXE-017.003.D01 — Capital-Max Position Sizing

**Parent SRD:** SRD-EXE-017.003, SRD-EXE-017.004, SRD-EXE-017.009

Replaces the fixed `qty_recommended=1` in `_router._build_entry_signal` and the
risk-per-trade formula of SRD-EXE-001.002 for the entry path.

```python
def size_for_strategy(entry_price: float, capital_max_pct: int,
                      effective_capital: float) -> int:
    if entry_price <= 0:
        return 0
    budget = effective_capital * capital_max_pct / 100.0
    return math.floor(budget / entry_price)
```

`_build_entry_signal` calls this with the owning `ctx.cfg.capital_max` and the
cached effective capital, then:

```
qty = size_for_strategy(entry_price, ctx.cfg.capital_max, eff_cap)
if qty < 1:
    publish StrategySignalDropped(signal, reason="capital_insufficient")
    log.warning("[Strategy] %s Capital Max insufficient for entry on %s", ctx.name, symbol)
    return            # no in_flight add, no enqueue
signal.qty_recommended = qty
```

Worked example (AC #1): eff_cap=$2000, capital_max=25% → budget=$500, entry=$96 →
`floor(500/96)=5`, position value `$480 ≤ $500`. Entry=$520 → `floor(500/520)=0`
→ dropped with the insufficient-capital warning (AC #2).

**Ordering in the Active branch of `_router.evaluate`:** entry fires → rex gate
(unchanged) → **size** (new; drops on `qty<1`) → `can_allocate` (now budget-based)
→ build signal with sized qty → enqueue.

## DD-EXE-017.005.D01 — Capital Cap (blocking) vs Advisory Warnings

**Parent SRD:** SRD-EXE-017.005, SRD-EXE-017.006

`can_allocate` switches its limit basis from `account.equity` to the effective
budget:

```python
def can_allocate(self, strategy_id, capital_max_pct) -> CanAllocateResult:
    if self._tracker is None:
        return CanAllocateResult(ok=True)
    limit = self._effective_capital() * capital_max_pct / 100.0   # was account.equity * pct/100
    deployed = sum(p.average_price * p.quantity
                   for p in self._tracker.get_all(self._user_id)
                   if p.strategy_id == strategy_id)
    ok = deployed < limit
    return CanAllocateResult(ok=ok, reason=None if ok else f"strategy {strategy_id!r} at capital limit")
```

**`validate_signal` becomes advisory for the three non-capital limits.** The
circuit-breaker check still blocks. Max-position and allocation breaches no longer
flip `ok=False`; instead they raise advisory events:

```python
@dataclass(frozen=True, slots=True)
class RiskWarning:
    schema_version: int
    kind: str          # "max_position" | "risk_per_trade" | "daily_loss"
    symbol: str
    message: str
```

`RiskManager.validate()` returns `ValidationResult(ok=True, qty=...)` for these
cases but publishes one `RiskWarning` per breach onto the FO-EXE-009 bus. The GUI
bridges `RiskWarning` to a debounced pop-up + Live Log line (SRD-EXE-017.013); no
order is blocked, resized, or closed.

## DD-EXE-017.007.D01 — Daily-Loss Aggregation

**Parent SRD:** SRD-EXE-017.007

The day's loss is the **sum across all active cycles** of realised + unrealised
PnL for the user, sourced from `TradeCycleQuery.open_cycles()` live fields plus the
day's closed cycles (`closed_between(start_of_day, now)`):

```python
day_pnl = sum(c.realized_pnl_usd for c in closed_today) \
        + sum(c.unrealized_pnl_usd for c in open_cycles)
threshold = -user.risk_config.max_daily_loss_pct / 100.0 * acct.start_of_day_equity
if day_pnl <= threshold and not self._daily_loss_warned:
    publish RiskWarning(kind="daily_loss", symbol="*", message=...)
    self._daily_loss_warned = True   # one warning per crossing
```

A `_daily_loss_warned` latch is reset at start-of-day (or when PnL recovers above a
small hysteresis band) so the user gets one warning per crossing, not one per tick.
This is advisory only — it does **not** trigger the FO-EXE-003 circuit breaker.

## DD-EXE-017.008.D01 — Wiring `RiskManager` into `app_service`

**Parent SRD:** SRD-EXE-017.008

Replace the `PassthroughRiskValidator()` at `app_service.py:1216`:

```python
from us_swing.execution.risk_manager import RiskManager
risk = RiskManager(
    config=self.get_active_user().risk_config,
    account_provider=lambda: self.get_account_state(self._active_uid),
    cb_state_provider=lambda: self._circuit_breaker_active,
    user_id=self._active_uid,
    tracker=self._cycle_position_source,   # open trade_cycles → OpenPosition view
)
```

`_cycle_position_source` is a thin `_PositionSource` adapter over
`TradeCycleQuery.open_cycles()` exposing `get_all(user_id) -> Sequence[OpenPosition]`
with `strategy_id`, `average_price`, `quantity` populated from each open cycle. The
`RiskManager` is also given the `effective_capital` accessor (constructor gains an
`effective_capital_provider` callable; defaults to `account.equity` to preserve the
existing unit tests).

## DD-EXE-017.010.D01 — Rex Auto-Reset on Start & Display Fix

**Parent SRD:** SRD-EXE-017.010, SRD-EXE-017.011

### Auto-reset on STOPPED → RUNNING

`_engine._apply_run_state` resets the strategy's counters on the start edge only.
The engine already holds `self._rex_counters`:

```python
def _apply_run_state(self, strategy_id, new_state):
    ctx = self._registry.get(strategy_id)
    ...
    previous = ctx.run_state
    ctx.run_state = new_state
    if (previous is _StrategyRunState.STOPPED
            and new_state is _StrategyRunState.RUNNING
            and self._rex_counters is not None):
        deleted = self._rex_counters.reset(strategy_id)
        log.info("[Strategy] %s started — reset %d rex counter(s)", ctx.name, deleted)
    ...
```

`reset()` deletes the rows; the lazy `get()`/`decrement()` path re-creates them at
`rex_count` on the next entry, so deletion == reset to the configured budget. Pause
(`RUNNING → STOPPED`) deliberately does **not** reset. The run-end-date rollover
reaches STOPPED then RUNNING on the user's next start, so it is covered by the same
edge. The manual "Reset rex counters" action (SRD-GUI-013.015) is retained.

### Display fix (root cause of the `-1` report)

Two display defects in `gui/active_cycles_model.py`:

1. **Negative render.** The Rex cell shows the raw stored `remaining`, which is
   `-1` once a `(strategy, symbol)` is exhausted. Change the display to
   *remaining re-entries* = `max(0, remaining)`; an exhausted pair shows `0`, not
   `-1`. The blocking gate still uses the raw stored value (`< 0`), so behaviour is
   unchanged — only the painted text changes.
2. **Cross-row leakage.** The counter is keyed by `(strategy, symbol)` and shared
   across rows, so a PENDING row for a symbol that already has an OPEN cycle inherits
   the open row's exhausted value (rows 5–7 in the user's screenshot). A pending
   signal that is not itself the entry that consumed the budget shall render `—`
   rather than the shared exhausted count: when a row is PENDING **and** another row
   for the same `(strategy, symbol)` is already non-terminal, suppress the Rex value
   for the pending row.

Stored values are untouched in both fixes; only `data()` for `Col.REX` changes.
