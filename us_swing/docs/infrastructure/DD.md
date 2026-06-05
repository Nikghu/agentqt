# Design Document — Infrastructure (INF)

**Document ID:** DD-INF
**Version:** 1.2.0
**Traces To:** SRD-INF v1.5.0
**Status:** Draft
**Last Updated:** 2026-06-04
**Project:** US Swing Trading System

> v1.2.0: DD-INF-009.* added — Pluggable Broker Abstraction (universal Broker contract, SimBroker fill model, IBKRBroker event bridge).

---

## DD-INF-001.001.D01 — IBKRClient Interface Design

**Parent SRD:** SRD-INF-001.001, SRD-INF-001.002, SRD-INF-001.003, SRD-INF-001.004, SRD-INF-001.005
- **Status:** Approved

### Component Overview

`IBKRClient` wraps `ib_insync.IB`, providing a typed async interface to the broker. It is the single point of contact for all IBKR API calls. All other components receive it via dependency injection.

### Public Interface

```python
class IBKRClient:
    # Lifecycle
    async def connect(host: str, port: int, client_id: int, timeout: float = 5.0) -> None
    async def disconnect() -> None
    def is_connected() -> bool

    # Connection state observable
    def on_status_change(callback: Callable[[ConnectionStatus], None]) -> None

    # Historical data
    async def req_historical_data(
        symbol: str,
        end_datetime: datetime,
        duration: str,          # e.g. "1 Y", "5 D"
        bar_size: str,          # e.g. "1 min", "1 day"
    ) -> list[OHLCVBar]

    # Real-time bars
    def subscribe_realtime_bars(symbol: str, bar_size: int = 5) -> None
    def unsubscribe_realtime_bars(symbol: str) -> None
    def on_realtime_bar(callback: Callable[[RealtimeBar], None]) -> None

    # Orders
    async def place_order(contract: Contract, order: Order) -> int  # returns orderId
    async def cancel_order(order_id: int) -> None
    async def cancel_all_orders() -> None
    async def close_all_positions() -> None

    # Account
    async def get_account_summary() -> AccountState
    async def get_open_positions() -> list[IBKRPosition]
```

### Data Flow

```
Config (host/port/clientId)
        │
        ▼
  IBKRClient.connect()
        │
        ├─► IB.connectAsync()  ──► TCP/Socket ──► IBKR Gateway
        │
        ├─► IB.reqAccountSummary()  [validate]
        │
        └─► register disconnect handler ──► auto-reconnect loop
```

### Pacing Queue Design

- `PacingQueue`: asyncio-based FIFO queue
- Slot counter: 50 requests per 600 s rolling window
- Each `req_historical_data()` call acquires a slot before dispatching
- Expired slots are released by a background cleanup task every 10 s

### Reconnect Backoff Table

| Attempt | Delay (s) |
|---|---|
| 1 | 2 |
| 2 | 4 |
| 3 | 8 |
| 4 | 16 |
| 5–10 | 60 (cap) |

---

## DD-INF-002.001.D01 — UniverseManager Interface Design

**Parent SRD:** SRD-INF-002.001 — SRD-INF-002.004

### Public Interface

```python
@dataclass
class UniverseRecord:
    symbol: str    # 1–5 uppercase alpha
    name:   str
    sector: str

class UniverseManager:
    def __init__(db: DatabaseManager, config: UniverseConfig) -> None

    def load_universe() -> list[UniverseRecord]
    async def refresh_universe() -> RefreshResult  # {added, removed, total}
    async def schedule_refresh() -> None            # starts asyncio PeriodicTask
```

### Refresh Data Source

- Primary: Wikipedia S&P 500 table via `pandas.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")`
- Returns DataFrame with columns: `Symbol`, `Security`, `GICS Sector`
- Upsert SQL: `INSERT ... ON CONFLICT(symbol) DO UPDATE SET name=..., sector=...`

---

## DD-INF-003.001.D01 — HistoricalDataEngine Interface Design

**Parent SRD:** SRD-INF-003.001 — SRD-INF-003.005

### Public Interface

```python
@dataclass
class OHLCVBar:
    symbol:   str
    datetime: datetime
    open:     float
    high:     float
    low:      float
    close:    float
    volume:   int
    timeframe: str   # '1m', '1d', '1w', '3m', '5m', '15m', '1h', '4h'

class HistoricalDataEngine:
    def __init__(client: IBKRClient, db: DatabaseManager, config: DataConfig) -> None

    async def bootstrap_symbol(symbol: str) -> BootstrapResult
    async def bootstrap_all(universe: list[UniverseRecord], max_concurrent: int = 5) -> None
    async def update_missing_data(symbol: str) -> UpdateResult
    def aggregate_timeframe(
        symbol: str,
        target_tf: Literal['3m','5m','15m','1h','4h'],
        bars_1m: list[OHLCVBar]
    ) -> list[OHLCVBar]
```

### Aggregation Algorithm

```
group source bars by floor(bar.datetime / target_seconds)
for each group:
    bar = OHLCVBar(
        open   = group[0].open,
        high   = max(b.high for b in group),
        low    = min(b.low  for b in group),
        close  = group[-1].close,
        volume = sum(b.volume for b in group),
    )
```

### Bootstrap Sequence

```
for symbol in universe (max_concurrent async):
    1. fetch 1y 1m bars from IBKR  [paced]
    2. fetch 1y 1d bars from IBKR  [paced]
    3. fetch 1y 1w bars from IBKR  [paced]
    4. db.insert_bars(symbol, '1m', bars_1m)
    5. db.insert_bars(symbol, '1d', bars_1d)
    6. db.insert_bars(symbol, '1w', bars_1w)
    7. log progress
```

---

## DD-INF-004.001.D01 — DatabaseManager Interface Design

**Parent SRD:** SRD-INF-004.001 — SRD-INF-004.006

### Public Interface

```python
class DatabaseManager:
    def __init__(database_url: str) -> None

    # Schema
    def create_schema() -> None
    def drop_schema() -> None   # test only

    # Bars
    def insert_bars(symbol: str, timeframe: str, bars: list[OHLCVBar]) -> int  # rows inserted
    def fetch_bars(symbol: str, timeframe: str, start: datetime, end: datetime) -> list[OHLCVBar]
    def get_last_timestamp(symbol: str, timeframe: str) -> datetime | None

    # Universe
    def upsert_universe(records: list[UniverseRecord]) -> None
    def fetch_universe() -> list[UniverseRecord]

    # Trades / Positions
    def insert_trade(trade: TradeRecord) -> None
    def update_trade_exit(trade_id: int, exit_time: datetime, exit_price: float, pnl: float) -> None
    def upsert_position(pos: PositionRecord) -> None
    def delete_position(user_id: int, symbol: str) -> None
    def fetch_open_positions(user_id: int) -> list[PositionRecord]

    # Users
    def insert_user(user: UserRecord) -> int  # returns user_id
    def fetch_user(user_id: int) -> UserRecord | None
    def update_user(user_id: int, **fields) -> None
    def delete_user(user_id: int) -> None
    def fetch_all_users() -> list[UserRecord]
```

### Schema DDL (simplified)

```sql
CREATE TABLE IF NOT EXISTS universe (
    symbol TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    sector TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS price_1m (
    symbol   TEXT NOT NULL,
    datetime TEXT NOT NULL,  -- ISO 8601 UTC
    open     REAL, high REAL, low REAL, close REAL, volume INTEGER,
    PRIMARY KEY (symbol, datetime)
);
-- price_1d, price_1w: identical structure

-- watchlist table retired: GUI watchlist is in-memory only (dropped via
-- idempotent DROP TABLE IF EXISTS in migrate_lifecycle_columns).

CREATE TABLE IF NOT EXISTS users (
    user_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    ibkr_client_id  INTEGER NOT NULL UNIQUE,
    settings_json   TEXT DEFAULT '{}',
    mode            TEXT NOT NULL DEFAULT 'paper'  -- 'paper' or 'live'
);

CREATE TABLE IF NOT EXISTS trades (
    trade_id    TEXT PRIMARY KEY,   -- IBKR orderId as string
    user_id     INTEGER NOT NULL REFERENCES users(user_id),
    symbol      TEXT NOT NULL,
    entry_time  TEXT,
    entry_price REAL,
    exit_time   TEXT,
    exit_price  REAL,
    quantity    INTEGER,
    pnl         REAL,
    mode        TEXT NOT NULL DEFAULT 'paper',  -- 'paper' or 'live'
    status      TEXT DEFAULT 'SUBMITTED'
);
CREATE INDEX IF NOT EXISTS idx_trades_user_symbol ON trades(user_id, symbol);

CREATE TABLE IF NOT EXISTS positions (
    symbol        TEXT NOT NULL,
    user_id       INTEGER NOT NULL REFERENCES users(user_id),
    quantity      INTEGER,
    average_price REAL,
    stop_loss     REAL,
    target_price  REAL,
    trailing_stop REAL,
    mode          TEXT NOT NULL DEFAULT 'paper',  -- 'paper' or 'live'
    state         TEXT NOT NULL DEFAULT 'NEW',    -- NEW / PARTIAL_ENTRY / OPEN / PARTIAL_EXIT / CLOSED
    PRIMARY KEY (user_id, symbol)
);
```

---

## DD-INF-005.001.D01 — Logging & Health Check Design

**Parent SRD:** SRD-INF-005.001 — SRD-INF-005.005

### Logging Architecture

```
Root Logger (INFO)
    ├── RotatingFileHandler  → logs/us_swing_YYYY-MM-DD.log   (daily rotation, 30-day retention)
    ├── StreamHandler        → stderr (WARNING+)
    └── AlertHandler         → AlertDispatcher
            ├── console  (always on)
            ├── FileAppendHandler → logs/alerts.log
            └── WebhookHandler   → configurable URL (POST JSON)
```

### Health Check Response Schema

```json
{
  "broker_connected": true,
  "last_update": "2026-03-05T09:30:00Z",
  "universe_count": 503,
  "open_positions": 2,
  "db_reachable": true,
  "uptime_seconds": 3600
}
```

---

## DD-INF-006.001.D01 — UserManager Interface Design

**Parent SRD:** SRD-INF-006.001 — SRD-INF-006.007

### Public Interface

```python
@dataclass
class UserProfile:
    user_id:         int
    username:        str
    display_name:    str
    ibkr_client_id:  int
    mode:            str             # 'paper' or 'live'
    risk_config:     RiskConfig
    strategy_config: dict            # parsed from settings_json
    screener_config: dict            # parsed from settings_json

class UserManager:
    def __init__(db: DatabaseManager) -> None

    def create_user(username: str, display_name: str, ibkr_client_id: int, mode: str = 'paper') -> UserProfile
    def get_user(user_id: int) -> UserProfile
    def update_user(user_id: int, **kwargs) -> UserProfile
    def delete_user(user_id: int) -> None
    def list_users() -> list[UserProfile]
    def switch_mode(user_id: int, new_mode: str, confirm_token: str | None = None) -> UserProfile
```

### Settings JSON Schema

```json
{
  "risk_per_trade_pct": 1.0,
  "max_position_value": 10000,
  "max_allocation_pct": 50.0,
  "max_daily_loss_pct": 2.0,
  "default_order_type": "MKT",
  "strategy_config": {
    "breakout_enabled": true,
    "pullback_enabled": true
  },
  "screener_config": {
    "volatility_enabled": true,
    "rsi_enabled": true,
    "rsi_min": 30,
    "rsi_max": 70
  }
}
```

### Mode Switch Flow

```
switch_mode(user_id, "live", confirm_token):
    if new_mode == "live" and confirm_token != expected_token:
        raise ConfirmationRequiredError("Live mode requires confirmation")
    db.update_user(user_id, mode=new_mode)
    log INFO: f"User {user_id} switched to {new_mode} mode"
```

---

## DD-INF-007.001.D01 — DataProvider Interface Design

**Parent SRD:** SRD-INF-007.001 — SRD-INF-007.005

### Provider Protocol

```python
class DataProvider(Protocol):
    async def req_historical_data(
        symbol: str,
        end_datetime: datetime,
        duration: str,
        bar_size: str,
    ) -> list[OHLCVBar]: ...

    def subscribe_realtime_bars(symbol: str, bar_size: int = 5) -> None: ...
    def unsubscribe_realtime_bars(symbol: str) -> None: ...
    def on_realtime_bar(callback: Callable[[RealtimeBar], None]) -> None: ...
```

### IBKRProvider

```python
class IBKRProvider:
    """Delegates all calls to IBKRClient. Production provider."""
    def __init__(client: IBKRClient) -> None
    # All protocol methods delegate to self._client
```

### DummyProvider

```python
class DummyProvider:
    """Synthetic data provider for development/testing."""
    def __init__(seed: int = 42, base_price: float = 100.0, volatility: float = 0.02) -> None

    async def req_historical_data(...) -> list[OHLCVBar]:
        # Generate random-walk OHLCV bars with deterministic seed
        # Ensures: open <= high, low <= open, low <= close <= high, volume >= 0

    def subscribe_realtime_bars(symbol, bar_size=5):
        # Start asyncio timer emitting synthetic 5s bars
```

### Factory

```python
def create_provider(config: AppConfig) -> DataProvider:
    match config.data_provider:
        case "ibkr":
            return IBKRProvider(IBKRClient(config.broker))
        case "dummy":
            return DummyProvider(seed=config.dummy_seed)
        case _:
            raise ConfigurationError(f"Unknown provider: {config.data_provider}")
```

---

## DD-INF-009.001.D01 — Universal Broker Contract

**Parent SRD:** SRD-INF-009.001 — SRD-INF-009.003
- **Status:** Approved

The broker layer is a self-contained INF plugin. It imports nothing from
`us_swing.execution.*`; it speaks only neutral types. Data flows both ways
(orders down, events up) but the import dependency points one way only
(execution → broker). The broker reports fills by calling listeners it does
not own (`_emit`); the execution-side adapter is the listener.

### Neutral DTOs & enums (`broker/broker.py`)

```python
class OrderSide(StrEnum):   BUY="BUY";  SELL="SELL"
class OrderType(StrEnum):   MARKET="MARKET"; LIMIT="LIMIT"
class OrderStatus(StrEnum):
    # Values are string-identical to ExecutionEnums.Buy/SellOrderState so the
    # adapter maps 1:1 with no lookup table.
    NEW; PARTIAL_FILLED; FILLED; REJECTED; CANCELLED

@dataclass(frozen=True, slots=True)
class OrderRequest:
    client_ref: str          # caller correlation id (e.g. signal_id), echoed back
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None       # required only when order_type == LIMIT
    reference_price: float | None = None   # advisory; SimBroker fills here, live ignores

@dataclass(frozen=True, slots=True)
class OrderEvent:
    broker_order_id: str
    client_ref: str
    status: OrderStatus
    filled_quantity: int = 0
    fill_price: float | None = None
    reason: str | None = None            # set on REJECTED / CANCELLED
    schema_version: int = 1
```

### Broker ABC

```python
class Broker(ABC):
    def __init__(self) -> None:
        self._event_callbacks: list[OrderEventCallback] = []

    def on_event(self, callback) -> None:   # adapter subscribes here
        self._event_callbacks.append(callback)

    def _emit(self, event: OrderEvent) -> None:    # subclasses report progress
        for cb in self._event_callbacks: cb(event)

    @abstractmethod
    def place_order(self, request: OrderRequest) -> str:
        """Acceptance only — returns broker order id BEFORE any fill.
        Fills arrive later as OrderEvents via on_event callbacks."""

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> None: ...
```

**Lifecycle contract.** `place_order` must return before any `OrderEvent` for
that order is emitted. The minimal happy path is `NEW` (persisted on accept by
the ingestion side) → `FILLED`. Partial sequences emit `PARTIAL_FILLED`
(cumulative `filled_quantity`) before `FILLED`. Terminal states are `FILLED`,
`REJECTED`, `CANCELLED`.

---

## DD-INF-009.004.D01 — SimBroker Fill Model

**Parent SRD:** SRD-INF-009.004

```python
class SimBroker(Broker):
    """Mock exchange. Accepts orders into an in-memory book, then emits
    lifecycle events asynchronously — never a synchronous fill in place_order."""

    def __init__(self, fill_model: FillModel) -> None:
        super().__init__()
        self._book: dict[str, OrderRequest] = {}
        self._fill = fill_model
        self._next_id = int(time.time() * 1000)   # unique across restarts

    def place_order(self, request: OrderRequest) -> str:
        oid = str(self._next_id); self._next_id += 1
        self._book[oid] = request
        # schedule async resolution on the running loop; do NOT fill inline
        loop.call_soon(self._resolve, oid)
        return oid
```

**FillModel** is injectable and decides: fill price (signal price / next-bar
open / configurable slippage), timing (immediate-async / next-bar), and split
(single fill vs N partials). A test-only model can force `REJECTED` /
`PARTIAL_FILLED` / `CANCELLED` to exercise the ingestion paths. Each resolution
step calls `self._emit(OrderEvent(...))`.

---

## DD-INF-009.005.D01 — IBKRBroker Event Bridge

**Parent SRD:** SRD-INF-009.005

`IBKRBroker` holds no ib_insync logic. It depends on an `OrderGateway` seam that
delivers IBKR-native `IbkrOrderUpdate`s; the broker only translates the request
to a submission and maps IBKR statuses onto `OrderStatus`. This keeps the
testable logic free of ib_insync and lets the contract suite drive it with a
fake gateway.

```python
@dataclass(frozen=True, slots=True)
class IbkrOrderUpdate:
    broker_order_id: str
    status: str            # raw ib_insync status, e.g. "Filled"
    filled: int
    avg_fill_price: float
    reason: str = ""

class OrderGateway(Protocol):
    def submit(symbol, side, quantity, order_type, limit_price) -> str: ...
    def cancel(broker_order_id: str) -> None: ...
    def on_status(callback: Callable[[IbkrOrderUpdate], None]) -> None: ...

class IBKRBroker(Broker):
    def __init__(self, gateway: OrderGateway) -> None:
        super().__init__()
        self._gateway = gateway
        self._client_ref: dict[str, str] = {}    # broker_order_id -> client_ref
        gateway.on_status(self._on_update)

    def place_order(self, request):
        oid = self._gateway.submit(request.symbol, request.side.value,
                                   request.quantity, request.order_type.value,
                                   request.limit_price)
        self._client_ref[oid] = request.client_ref
        return oid
```

### Status mapping (the IBKR-specific logic)

| IBKR status | filled | → OrderStatus |
|---|---|---|
| `Filled` | — | `FILLED` |
| `Submitted` / `PreSubmitted` | > 0 | `PARTIAL_FILLED` |
| `Submitted` / `PreSubmitted` | 0 | *(no event — acknowledgement)* |
| `Inactive` | — | `REJECTED` |
| `Cancelled` / `ApiCancelled` / `PendingCancel` | — | `CANCELLED` |

On a mapped status `_on_update` looks up the `client_ref` and `_emit`s an
`OrderEvent`, dropping context on a terminal status. The production
`IBKRClientGateway` wraps `IBKRClient` (via the new `ib` accessor), builds the
ib_insync `Stock` + `Market`/`Limit` order, and wires `trade.statusEvent` →
`IbkrOrderUpdate`; it is live-only (`# pragma: no cover`). Both brokers pass the
same contract suite (SRD-INF-009.006).
