# Design Document — Infrastructure (INF)

**Document ID:** DD-INF
**Version:** 1.3.0
**Traces To:** SRD-INF v1.7.0
**Status:** Draft
**Last Updated:** 2026-07-09
**Project:** US Swing Trading System

> v1.2.0: DD-INF-009.* added — Pluggable Broker Abstraction (universal Broker contract, SimBroker fill model, IBKRBroker event bridge).
> v1.3.0: DD-INF-010.001.D01 added — Notification Service Architecture (pluggable channels, event bus, formatter registry, Telegram channel, reserved inbound seam).

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

    # Watchlist
    def upsert_watchlist(symbols: list[str], date: date) -> None
    def fetch_watchlist(date: date) -> list[str]

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

CREATE TABLE IF NOT EXISTS watchlist (
    date   TEXT NOT NULL,
    symbol TEXT NOT NULL,
    PRIMARY KEY (date, symbol)
);

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

---

## DD-INF-010.001.D01 — Notification Service Architecture

**Parent SRD:** SRD-INF-010.001 — SRD-INF-010.015
- **Status:** Draft

Home: `src/us_swing/core/notifications/`. It lives in `core/` (not under a tool)
because the screener, execution, and infrastructure tools all raise events into
it, and `code-style.md` forbids direct cross-tool imports — shared services go
through `core/`. The shape mirrors the existing `core/monitoring_session/`
CQRS-lite pattern: frozen DTOs, `Protocol`-typed seams, a lightweight event bus,
no ABCs. It is a **business-event** service — distinct from FO-INF-005's
`AlertDispatcher`, which carries log-level WARNING+ alerts. The two are kept
separate on purpose; a business event (screener approved, day-end PnL) is not a
log record.

### Data flow

```
Producer (SCR/EXE/INF)         core/notifications/
   publish(event) ─────────────▶ NotificationBus
                                     │  (fan-in of events)
                                     ▼
                                 NotificationDispatcher
                                   1. format via registry
                                   2. for each enabled channel: enqueue
                                   3. per-channel failure isolated + logged
                                     │
                                     ▼  NotificationMessage
                                 NotificationChannel (Protocol)
                                   • TelegramChannel   ← only impl this phase
                                   • Email/Slack/SMS   ← future, register only
```

Import direction is one-way: producers depend on the bus + event DTOs only; they
never see the dispatcher or any channel. Adding a channel or an event type never
edits an existing file — this is the open/closed spine the feature is built for.

### Events — extensible frozen DTOs (`events.py`)

```python
@dataclass(frozen=True, slots=True)
class NotificationEvent:
    occurred_at: datetime
    schema_version: int = 1

@dataclass(frozen=True, slots=True)
class ToolStartedEvent(NotificationEvent):
    app_version: str = ""

@dataclass(frozen=True, slots=True)
class ScreenerApprovedEvent(NotificationEvent):
    symbols: tuple[str, ...] = ()      # filtered stock names
    run_id: str = ""

@dataclass(frozen=True, slots=True)
class DayEndPnLEvent(NotificationEvent):
    realized: float = 0.0
    unrealized: float = 0.0
    trade_count: int = 0
```

A new notification is a new frozen subclass here plus one formatter registration
(below). Nothing in the dispatcher, bus, or channels changes.

### Message + channel Protocol (`channel.py`)

```python
@dataclass(frozen=True, slots=True)
class NotificationMessage:
    text: str
    event_kind: str            # type name, for per-event routing/toggles

class NotificationChannel(Protocol):
    name: str
    async def send(self, message: NotificationMessage) -> None: ...
```

### TelegramChannel (`telegram_channel.py`)

```python
class TelegramChannel:
    """First concrete channel. Telegram Bot API over HTTP — no heavy SDK."""
    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str, http: httpx.AsyncClient) -> None: ...

    async def send(self, message: NotificationMessage) -> None:
        # POST https://api.telegram.org/bot<token>/sendMessage
        #   json={"chat_id": self._chat_id, "text": message.text}
        # raises on transport error; dispatcher isolates + logs it
```

### Formatter registry (`formatters.py`)

```python
Formatter = Callable[[NotificationEvent], NotificationMessage]
_REGISTRY: dict[type[NotificationEvent], Formatter] = {}

def register(event_type: type[NotificationEvent]) -> Callable[[Formatter], Formatter]:
    def deco(fn: Formatter) -> Formatter:
        _REGISTRY[event_type] = fn
        return fn
    return deco

def render(event: NotificationEvent) -> NotificationMessage:
    return _REGISTRY[type(event)](event)

@register(ScreenerApprovedEvent)
def _fmt_screener(e: ScreenerApprovedEvent) -> NotificationMessage:
    names = ", ".join(e.symbols)
    return NotificationMessage(f"[Screener] Approved {len(e.symbols)} stock(s): {names}",
                               event_kind="ScreenerApprovedEvent")
```

### Dispatcher + delivery (`dispatcher.py`)

```python
class NotificationDispatcher:
    def __init__(self, bus: NotificationBus, channels: list[NotificationChannel]) -> None:
        self._channels = channels
        self._queue: asyncio.Queue[NotificationMessage] = asyncio.Queue()
        bus.subscribe(self._on_event)

    def _on_event(self, event: NotificationEvent) -> None:
        self._queue.put_nowait(render(event))       # producer never blocks

    async def _worker(self) -> None:
        while True:
            msg = await self._queue.get()
            for ch in self._channels:
                try:
                    await self._rate_limit(ch)
                    await self._send_with_retry(ch, msg)
                except Exception:                     # isolate: one channel's failure
                    log.exception("[Notify] Delivery to %s failed", ch.name)
```

Delivery guarantees (SRD-INF-010.004/.007): the producer only enqueues — it never
blocks and never sees a channel error. The worker paces per chat (Telegram allows
roughly one message per second per chat) and retries with bounded backoff before
giving up and logging under `[Notify]`.

### Config — reuse the per-user profile (`config.py`)

Settings live in the existing `UserProfile.settings_json` (FO-INF-006), under a
`notifications` key — no parallel store:

```json
{
  "notifications": {
    "telegram": { "enabled": true, "bot_token": "…", "chat_id": "…" },
    "events": { "ToolStartedEvent": true, "ScreenerApprovedEvent": true, "DayEndPnLEvent": true }
  }
}
```

```python
@dataclass(frozen=True, slots=True)
class NotificationConfig:
    telegram_enabled: bool
    bot_token: str
    chat_id: str
    event_toggles: Mapping[str, bool]

def load_config(settings_json: Mapping[str, Any]) -> NotificationConfig: ...
```

Two users with different tokens each build their own `TelegramChannel`, so
notifications land only in that user's chat (FO-INF-010 acceptance criterion).

### Inbound two-way commands (`_inbound.py`) — SRD-INF-010.012–.015

Two-way commands are the mirror image of outbound: an inbound Telegram message
becomes a command that is routed to a read-only handler and answered. The same
per-user bot token and the worker's shared `httpx` client feed both the outbound
`TelegramChannel` and the inbound receiver — no new configuration.

**Receive — long-poll, not webhook (SRD-INF-010.012).** A desktop app has no public
URL, so webhooks are out. `TelegramPoller` calls `getUpdates` with a long timeout on
the notification loop and tracks `offset = last_update_id + 1` so each message is
handled exactly once. It runs only when Telegram is enabled.

```python
class TelegramPoller:
    def __init__(self, bot_token, chat_id, http, router, *, poll_timeout_s=25): ...

    async def run(self) -> None:
        offset = 0
        while True:
            for update in await self._get_updates(offset):
                offset = update["update_id"] + 1
                msg  = update.get("message") or {}
                text = (msg.get("text") or "").strip()
                sender = str((msg.get("chat") or {}).get("id", ""))
                if sender != self._chat_id:                 # SRD-INF-010.013
                    log.warning("[Notify] Ignoring command from unauthorized chat")
                    continue
                reply = await loop.run_in_executor(None, self._router.route, text)
                if reply:
                    await self._send(reply)
```

**Authorize (SRD-INF-010.013).** Only the configured `chat_id` is honored; every other
sender is dropped and logged. The bot never answers or leaks state to an unconfigured
chat.

**Route (SRD-INF-010.014).** `CommandRouter` parses the leading token (strips `/` and a
trailing `@botname`, lowercases), then dispatches through a table. `/help` is static;
unknown commands return a help hint; a handler error returns a plain apology (never a
stack trace). All seven commands are read-only.

```python
class CommandRouter:
    def __init__(self, port: CommandPort) -> None:
        self._table = {
            "status": port.status, "pnl": port.pnl, "positions": port.positions,
            "signals": port.signals, "screener": port.screener, "cycles": port.cycles,
        }
    def route(self, text: str) -> str | None:
        cmd = self._parse(text)                 # None for non-command text -> ignore
        if cmd is None:            return None
        if cmd == "help":          return self._help_text()
        handler = self._table.get(cmd)
        if handler is None:        return f"Unknown command /{cmd}. Send /help for the list."
        try:    return handler()
        except Exception:  log.exception("[Notify] Command /%s failed", cmd);  return "Sorry, that command failed."
```

**Query port + thread safety (SRD-INF-010.015).** The router depends only on a
`CommandPort` Protocol of six read methods returning ready text; it never imports the
GUI. The poller runs on the notification thread, but app state lives on the GUI thread,
so the GUI adapter marshals each call onto the GUI thread with a blocking queued
signal and a `concurrent.futures.Future`, keeping the asyncio loop free via
`run_in_executor`.

```python
class CommandPort(Protocol):                    # core seam, no GUI import
    def status(self) -> str: ...
    def pnl(self) -> str: ...
    def positions(self) -> str: ...
    def signals(self) -> str: ...
    def screener(self) -> str: ...
    def cycles(self) -> str: ...

class TelegramCommandBridge(QObject):           # gui/telegram_commands.py — GUI thread
    _request = pyqtSignal(str, object)          # (slot_name, Future) -> queued to GUI thread
    def status(self) -> str: return self._call("status")   # called from notif executor thread
    def _call(self, slot: str) -> str:
        fut: Future[str] = Future(); self._request.emit(slot, fut); return fut.result(timeout=10)
```

The bridge reuses existing `AppService` reads: `/status` → `get_feed_status` +
`get_market_status`; `/pnl` → `get_account_state`; `/positions` → `get_positions`;
`/signals` → `get_pending_signals`; `/screener` → `get_latest_screener_results`;
`/cycles` → `get_recent_closed_cycles` + `get_strategies_with_open_cycles`.
