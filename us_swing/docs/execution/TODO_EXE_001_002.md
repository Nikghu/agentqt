# TODO — FO-EXE-001 / EXE-002 / EXE-004 / EXE-005 Implementation

**Created:** 2026-05-26  
**Session:** 50  
**Status:** COMPLETE — Session 50, 2026-05-26. 45 tests pass, ruff + mypy --strict clean, all docs updated.

---

## 0. First Actions (administrative, do these before any code)

- [x] **Update SRD.md** — change `| Draft |` → `| Approved |` for every row in:
  - Section 1: `SRD-EXE-001.001` – `SRD-EXE-001.006`
  - Section 2: `SRD-EXE-002.001` – `SRD-EXE-002.005`
  - Section 4: `SRD-EXE-004.001` – `SRD-EXE-004.005`
  - Section 5: `SRD-EXE-005.001` – `SRD-EXE-005.006`

- [x] **Update `exceptions.py`** — add two new exception classes after `ConfirmationRequiredError`:
  ```python
  class OrderSubmissionError(USSwingError):
      """IBKR order submission failed or timed out."""

  class InvalidStateTransitionError(USSwingError):
      """Attempted an illegal position state transition."""
  ```

- [x] **Update `data/models.py`** — add `trade_id: str = ""` field to `OpenPosition` dataclass (after `strategy_id`). Needed by `PositionTracker` to link fills to trade records on exit.

---

## 1. Implementation Order (dependency-driven)

### 1a. `execution/risk_manager.py`  ← MD-EXE-001.001.M01

**Class:** `RiskManager`

**Constructor:**
```python
def __init__(
    self,
    config: RiskConfig,             # from data/models.py
    account_provider: Callable[[], AccountState],
    cb_state_provider: Callable[[], bool],   # True = circuit breaker active
    user_id: int,
    tracker: PositionTracker | None = None,  # needed for can_allocate
) -> None
```

**Must implement `RiskValidator` protocol** (`strategy_engine/_protocols.py`):
- `validate(signal: EngineTradeSignal) -> ValidationResult`
  - Internally calls `account_provider()` + `cb_state_provider()`
  - Calls `validate_signal()`, then `calculate_position_size()` for qty
  - Returns `ValidationResult(ok=True, qty=n)` or `ValidationResult(ok=False, reason=...)`
- `can_allocate(strategy_id: str, capital_max_pct: int) -> CanAllocateResult`
  - Sums `average_price × quantity` for all positions where `position.strategy_id == strategy_id`
  - Returns False if deployed ≥ `equity × capital_max_pct / 100`

**Additional public methods (SRD-EXE-001.001/.002, SRD-EXE-005.004):**
- `validate_signal(signal, account_state: AccountState, cb_active: bool) -> ValidationResult`
  - Check 1: `cb_active` → `ok=False, reason="circuit breaker active"`
  - Check 2: position_value > `config.max_position_value` → reject
  - Check 3: `deployed + required > equity × max_allocation_pct/100` → reject
- `calculate_position_size(signal, account_state: AccountState) -> int`
  - Formula: `floor((equity × risk_per_trade_pct/100) / abs(entry_price - stop_loss))`
  - Cap: `floor(max_position_value / entry_price)`
  - Return `min(formula_result, cap)` — 0 if entry_price or risk_per_share is 0
- `can_enter_new(signal, account_state: AccountState, user_id: int) -> bool`
  - Sum all open position values for `user_id` via tracker
  - Returns True if `deployed + new_required ≤ equity × max_allocation_pct/100`

**Note:** `EngineTradeSignal` = `us_swing.execution.strategy_engine._signals.TradeSignal` (NOT `data/models.py::TradeSignal`)

---

### 1b. `execution/position_tracker.py`  ← MD-EXE-002.001.M01

**Class:** `PositionTracker`

**Constructor:**
```python
def __init__(self, db: DatabaseManager) -> None:
    self._positions: dict[tuple[int, str], OpenPosition] = {}
    self._lock = threading.RLock()
```

**Valid state transitions** (raise `InvalidStateTransitionError` otherwise):
```python
_VALID_TRANSITIONS = {
    PositionState.NEW:           {PositionState.PARTIAL_ENTRY, PositionState.OPEN},
    PositionState.PARTIAL_ENTRY: {PositionState.PARTIAL_ENTRY, PositionState.OPEN},
    PositionState.OPEN:          {PositionState.PARTIAL_EXIT, PositionState.CLOSED},
    PositionState.PARTIAL_EXIT:  {PositionState.PARTIAL_EXIT, PositionState.CLOSED},
    PositionState.CLOSED:        set(),
}
```

**Public API:**
- `open(pos: OpenPosition) -> None` — add position (state=NEW), upsert DB
- `close(user_id: int, symbol: str) -> OpenPosition` — remove from memory, delete_position from DB, return the closed pos
- `update_stop(user_id: int, symbol: str, new_stop: float) -> None` — update stop_loss in memory + DB
- `update_state(user_id: int, symbol: str, new_state: PositionState, filled_qty: int | None = None) -> None` — validate transition, update, upsert DB
- `has_open(user_id: int, symbol: str) -> bool`
- `get_all(user_id: int | None = None) -> list[OpenPosition]` — None = all users
- `load_from_db(user_id: int) -> None` — restore non-CLOSED positions from DB (SRD-EXE-005.006)
- `reconcile(ibkr_positions: list[IBKRPosition]) -> list[str]` — adopt IBKR positions not in local DB, log WARNING, return adopted symbols (SRD-EXE-002.004)

---

### 1c. `execution/paper_engine.py`  ← MD-EXE-004.001.M01

**Note:** The existing `paper_broker.py` (MD-EXE-011.001.M09) is a thin EXE-011 stub — it stays. This is a new, separate full implementation.

**New dataclass `PaperFill`** (define at top of module):
```python
@dataclass(frozen=True, slots=True)
class PaperFill:
    order_id: int          # always negative
    fill_price: float
    fill_qty: int
    symbol: str
    strategy_id: str
    is_entry: bool
    mode: str = "paper"
    schema_version: int = 1
```

**Class:** `PaperEngine`

**Constructor:**
```python
def __init__(
    self,
    db: DatabaseManager,
    price_provider: Callable[[str], float | None],  # returns current market price
    on_fill: Callable[[FillEvent], None],            # FillEvent from strategy_engine/_protocols.py
    user_id: int,
) -> None:
    self._next_id = -1   # decrements: -1, -2, -3 …
```

**Public API:**
- `simulate_fill(signal: EngineTradeSignal, quantity: int, order_type: str = "MKT") -> PaperFill | None`
  - MKT: fill immediately at `price_provider(symbol)` (fallback: `signal.entry_price`)
  - LMT BUY: only fills if `market_price ≤ signal.entry_price`; fill_price = `signal.entry_price`
  - Generates negative order_id
  - Writes `TradeRecord(..., mode='paper', status='FILLED')` to DB
  - Calls `on_fill(FillEvent(...))`
  - Returns `PaperFill`
- `simulate_exit(symbol: str, quantity: int, strategy_id: str, entry_trade_id: str) -> PaperFill`
  - Fill at current market price
  - Calls `db.update_trade_exit(entry_trade_id, ...)`
  - Calls `on_fill(FillEvent(is_entry=False, ...))`
- `submit(signal: EngineTradeSignal, qty: int) -> int | None`
  - Implements `ExecutionSubmitter` protocol
  - Calls `simulate_fill(signal, qty, "MKT")`
  - Returns `fill.order_id` or None

---

### 1d. `execution/execution_router.py`  ← MD-EXE-004.001.M02

**Class:** `ExecutionRouter`

**Constructor:**
```python
def __init__(
    self,
    paper: PaperEngine,
    live: ExecutionEngine,
    mode_provider: Callable[[], str],   # returns 'paper' | 'live', checked per-signal
) -> None
```

**Public API:**
- `submit(signal: EngineTradeSignal, qty: int) -> int | None`  ← `ExecutionSubmitter` protocol
  - Reads `mode_provider()` at call time (SRD-EXE-004.005: no caching)
  - Routes to `paper.submit()` or `live.submit()`
- `route_signal(user_id: int, signal, **kwargs) -> int | None`
  - Same as submit but explicit user_id for future multi-user expansion

---

### 1e. `execution/execution_engine.py`  ← MD-EXE-001.001.M02

**Class:** `ExecutionEngine`

**Constructor:**
```python
def __init__(
    self,
    ibkr: IBKRClient,
    risk: RiskManager,
    tracker: PositionTracker,
    db: DatabaseManager,
    on_fill: Callable[[FillEvent], None],
    user_id: int,
    loop: asyncio.AbstractEventLoop | None = None,
    timeout: float = 2.0,
) -> None:
    self._cb_active = False
    self._queued: int = 0   # sentinel counter for submit()
```

**Public API:**
- `async submit_signal(signal, account_state: AccountState, quantity_override: int | None = None) -> int | None`
  - Validate via `risk.validate_signal(signal, account_state, self._cb_active)`
  - If failed: log WARNING `[Execution] Signal REJECTED for {symbol}: {reason}`, return None
  - Quantity = override if provided, else `risk.calculate_position_size(signal, account_state)`
  - Raise `ValueError` if `quantity_override ≤ 0` (SRD-EXE-005.005)
  - Build IBKR `Stock` contract + `MarketOrder` or `LimitOrder`
  - `await asyncio.wait_for(ibkr.place_order(contract, order), timeout=self._timeout)` → order_id
  - On timeout: raise `OrderSubmissionError`
  - Write `TradeRecord(trade_id=str(order_id), ..., status='SUBMITTED', mode='live')` to DB
  - Return order_id
- `submit(signal: EngineTradeSignal, qty: int) -> int | None`  ← `ExecutionSubmitter` protocol (sync wrapper)
  - `asyncio.ensure_future(self._submit_async(signal, qty))` — fires-and-forgets
  - Returns a non-None sentinel int (caller only checks `is None`)
- `exit_position(symbol: str) -> int | None`
  - Look up open position via `tracker`; if none, return None
  - Submit market SELL order for full quantity
  - Return order_id
- `handle_order_fill(fill: IBKRFill) -> None`
  - If entry fill (via order_id → trade record lookup): create `OpenPosition` (state=OPEN), `tracker.open(pos)`
  - If exit fill: `tracker.close(user_id, symbol)`, `db.update_trade_exit(...)`, emit `PositionClosedEvent` (via `on_fill`)
  - In both cases: call `on_fill(FillEvent(...))`
- `set_circuit_breaker(active: bool) -> None` — toggles `self._cb_active`

---

## 2. Test Files to Write

All tests go in `us_swing/tests/execution/`. Use in-memory SQLite (`StaticPool`).

| File | UTCD IDs covered |
|---|---|
| `test_risk_manager.py` | T01–T06 (EXE-001.001.M01) + T01–T03 (EXE-005.004.M01) |
| `test_position_tracker.py` | T01–T05 (EXE-002.001.M01) + T01–T09 (EXE-005.001.M01) |
| `test_paper_engine.py` | T01–T07 (EXE-004.001.M01) |
| `test_execution_router.py` | T01–T03 (EXE-004.001.M02) |
| `test_execution_engine.py` | T01–T07 (EXE-001.001.M02) + T01–T03 (EXE-005.005.M02) |

### DB fixture pattern (copy from `tests/execution/conftest.py` or `tests/core/monitoring_session/conftest.py`):
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

@pytest.fixture
def engine():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    from us_swing.db.schema import create_schema
    create_schema(e)
    return e

@pytest.fixture
def db(engine):
    from us_swing.db.manager import DatabaseManager
    m = DatabaseManager.__new__(DatabaseManager)
    m._engine = engine
    return m
```

---

## 3. After All Tests Pass

- [ ] Update SRD rows (001–005) Status → `Implemented`
- [ ] Update `MD.md` rows Status → `Implemented`
- [ ] Update `UTCD.md` test statuses → `Pass`
- [ ] Update `TRACE.md` — fill EXE-001, EXE-002, EXE-004, EXE-005 rows
- [ ] Write `RN-EXE-1.7.0-YYYYMMDD.md` in `docs/execution/revisions/`
- [ ] Update `CONTEXT.md §0` with new next step
- [ ] Prepend `DEVLOG.md` entry
- [ ] Retire stub wiring note: `_Router` currently uses `PaperBroker` as submitter; `AppService` wiring to `ExecutionRouter` is a follow-up task (not in this session scope)
- [ ] Commit: `feat(EXE): implement ExecutionEngine, PositionTracker, RiskManager, PaperEngine, ExecutionRouter`

---

## 4. Key Design Decisions (already made — do not re-debate)

| Decision | Detail |
|---|---|
| Two paper engines | `paper_broker.py` (EXE-011 stub, stays) + `paper_engine.py` (EXE-004, new full impl) |
| Sync `submit()` protocol | `ExecutionRouter.submit()` is sync per `ExecutionSubmitter` protocol; for live, uses `asyncio.ensure_future()` to schedule IBKR call |
| `on_fill` callback | Both `PaperEngine` and `ExecutionEngine` call `on_fill(FillEvent)` which the caller wires to `PositionTracker` + `TradeCycleService` |
| Paper order IDs | Negative integers (−1, −2, …), distinguishable from IBKR order IDs |
| trade_id on OpenPosition | Add `trade_id: str = ""` to `data/models.py::OpenPosition` to link exit fills back to the entry trade record |
| EngineTradeSignal | `strategy_engine/_signals.py::TradeSignal` — NOT `data/models.py::TradeSignal` (different classes) |
| `RiskManager` needs tracker | Injected as optional; needed for `can_allocate()` per-strategy capital check |
| Paper fills immediate | `PaperEngine.simulate_fill()` fills synchronously; `on_fill` is called before returning |
| Live fills async | `ExecutionEngine.handle_order_fill(IBKRFill)` is called externally by AppService when IBKR fires fill event |

---

## 5. Existing Files Not to Break

- `execution/paper_broker.py` — keep as-is (still used by strategy engine stub wiring)
- `execution/risk_validator.py` — keep as-is (`PassthroughRiskValidator`, still used until AppService rewires)
- `execution/strategy_engine/_protocols.py` — `ValidationResult`, `CanAllocateResult`, `RiskValidator`, `ExecutionSubmitter`, `FillEvent` — all already correct, do not modify
- `broker/client.py` — `IBKRClient.place_order(contract, order) -> int` is async, already exists

---

## 6. Imports Reference

```python
# Engine signal (NOT data/models TradeSignal)
from us_swing.execution.strategy_engine._signals import TradeSignal as EngineSignal, Action

# Protocol types
from us_swing.execution.strategy_engine._protocols import (
    ValidationResult, CanAllocateResult, FillEvent,
    RiskValidator, ExecutionSubmitter,
)

# Data models
from us_swing.data.models import (
    AccountState, RiskConfig, OpenPosition, PositionRecord,
    PositionState, TradingMode, TradeRecord, IBKRPosition, IBKRFill,
)

# Exceptions (add OrderSubmissionError, InvalidStateTransitionError first)
from us_swing.exceptions import OrderSubmissionError, InvalidStateTransitionError

# DB
from us_swing.db.manager import DatabaseManager
from us_swing.broker.client import IBKRClient
```
