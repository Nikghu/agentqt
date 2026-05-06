# Design Document — Execution & Risk Management (EXE)

**Document ID:** DD-EXE
**Version:** 1.2.0
**Traces To:** SRD-EXE v1.2.0
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
        """Aggregate 3m/5m/1h and verify ≥ min_candles each."""
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
        │      HistoricalDataEngine.aggregate_timeframe(symbol, '5m')  → count ≥ 390?
        │      HistoricalDataEngine.aggregate_timeframe(symbol, '1h')  → count ≥ 390?
        │
        │      emit load_progress(symbol, i, total)
        │
        └─ emit load_complete(results)
```

### IBKR Paging Strategy (Full Fetch)

IBKR limits 1m bar requests to 30 calendar days per call. To obtain 65 trading days:

```
end_date = today
pages = ceil(65 × 7/5 ÷ 30)  ≈ 4 pages   [65 trading days ≈ 91 calendar days]

for page in range(pages):
    duration = "30 D"
    end_dt   = end_date - (page × 30 calendar days)
    bars     = ibkr.req_historical_data(symbol, end_dt, duration, '1 min')
    db.insert_bars(symbol, '1m', bars)
```

Pages are fetched newest-first; the pacing queue enforces ≤ 50 requests per 10-min window.

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
    candles_5m:   int
    candles_1h:   int
    last_1m_bar:  datetime | None
    ready:        bool    # True iff all three counts ≥ min_candles (default 390)

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

-- 5m count  
SELECT COUNT(*) FROM price_1m
 WHERE symbol = :sym
   AND datetime >= :cutoff_5m;

-- 1h count
SELECT COUNT(*) FROM price_1m
 WHERE symbol = :sym
   AND datetime >= :cutoff_1h;
```

Counts are approximate (assumes continuous bars). For validation, `aggregate_timeframe()` produces the exact count; `get_readiness_report()` uses the fast COUNT path for UI display.
