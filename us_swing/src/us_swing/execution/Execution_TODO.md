# Execution TODO — Manual Strategy → Paper Fill End-to-End

**Target flow (Manual mode, Paper user):**
```
Candle closes → StrategyEngine evaluates entry condition
  → condition true → TradeSignal pushed to PendingSignalStore
  → "Pending Signals" tab shows new row
  → User clicks Execute
  → PaperBroker generates synthetic FillEvent
  → StrategyEngine.on_order_fill() → cycle state ACTIVE → RUNNING
  → TradeCycleService.on_entry_fill() → written to DB
  → Strategy Executor badge → "Running" for that symbol
```

**Convention in this file:**
- File paths are relative to `us_swing/src/us_swing/`
- MODULE_MAP references: `<file>::<Class>.<method>()`
- Each item is a single, self-contained edit — safe to tackle in one limited-context session
- Status: `[ ]` = not started · `[~]` = in progress · `[x]` = done

---

## Section Status

| Section | Title | Status | Notes |
|---|---|---|---|
| A | Bug Fixes | [x] | |
| B | New Foundation Stubs | [x] | |
| C | Paper Broker | [x] | |
| D | AppService — Candle Providers | [x] | |
| E | PendingSignalStore Wiring | [x] | |
| F | StrategyEngine Wiring | [x] | |
| G | Execute Button Routing | [x] | |
| H | Pending Signals Tab Live Refresh | [x] | |
| I | Strategy Executor Engine-Driven Status | [x] | |

---

## SECTION A — Bug Fixes

---

### A-01 — Fix `_StrategyContext.accepts()` wrong symbol_mode strings
**File**: `execution/strategy_engine/_context.py`
**Class/Method**: `_StrategyContext.accepts()` (line ~62)

`StrategyConfig` stores `symbol_mode` as `"all"` / `"include"` / `"exclude"` (set in `gui/strategy_builder_dialog.py:1595`). `accepts()` currently checks `"include_only"` and `"exclude_these"` — neither ever matches, so it falls through to `return False` for every symbol in include/exclude scope.

**Change**:
```python
# Before
if mode == "include_only":  →  if mode == "include":
if mode == "exclude_these": →  if mode == "exclude":
```

**Smoke test**:
1. Open Strategy Builder, set scope to "Include Only", add MRK. Save. Check log — `[Strategy] TESTING entered Running` should appear within 30 s once a candle bar fires for MRK (requires candle data).
2. Set scope to "Exclude These", add any symbol. Confirm the rest of S&P 500 symbols are accepted in the evaluator loop (no "Condition evaluation failed" for in-scope symbols).

---

### A-02 — Fix `strategy_runner.py` dead `ConditionEvaluator` left-over (mypy)
**File**: `execution/strategy_runner.py`
**Class/Method**: `_tokenize()` (line ~63), `_Token` (line ~82)

Two pre-existing `mypy --strict` errors remain in the dead local tokenizer code (lines 67, 82). The local `ConditionEvaluator`, `_tokenize`, `_TokKind`, `_Token`, `_Parser`, `_IndicatorNode`, `_CompareNode`, `_LogicalNode`, and `_compute_indicator` / `_eval_op` are now unreachable — `StrategyRunWorker` uses `_EngineEvaluator`.

**Change**: Delete all dead code from `# ── Tokenizer` down to (but not including) `# ── DataFrame candle loader`; delete `from us_swing.analysis import indicators` and `from us_swing.data.models import OHLCVBar` if no longer needed after removal.

**Smoke test**:
1. Run `python -m mypy us_swing/src/us_swing/execution/strategy_runner.py --strict` — zero errors.
2. Press Play on any strategy in the app; confirm strategy status changes and log shows `[Strategy]` lines.

---

## SECTION B — New Foundation Stubs

---

### B-01 — Create `PassthroughRiskValidator`
**New file**: `execution/risk_validator.py`
**Implements**: `RiskValidator` protocol (`execution/strategy_engine/_protocols.py::RiskValidator`)

```python
class PassthroughRiskValidator:
    def validate(self, signal: TradeSignal) -> ValidationResult:
        return ValidationResult(ok=True, qty=signal.qty_recommended)
    def can_allocate(self, strategy_id: str, capital_max_pct: int) -> CanAllocateResult:
        return CanAllocateResult(ok=True)
```

No constructor args needed. Always passes; capital checks added later.

**Smoke test**:
1. Import and instantiate in Python REPL: `from us_swing.execution.risk_validator import PassthroughRiskValidator; v = PassthroughRiskValidator()` — no error.
2. (After B-02 + F-01) `StrategyEngine` starts without raising on risk calls.

---

### B-02 — Create `QtEventBus`
**New file**: `execution/event_bus.py`
**Implements**: `EventBus` protocol (`execution/strategy_engine/_protocols.py::EventBus`)

```python
class QtEventBus(QObject):
    event_published = pyqtSignal(object)   # emits any StrategyEvent subclass

    def publish(self, event: StrategyEvent) -> None:
        # thread-safe: call_soon_threadsafe is NOT needed here — Qt signal
        # emission is thread-safe when both ends live in the same process.
        log.debug("[EventBus] %s", type(event).__name__)
        self.event_published.emit(event)
```

`AppService` connects to `event_published` in TODO I-01 to update strategy badges.

**Smoke test**:
1. `from us_swing.execution.event_bus import QtEventBus; bus = QtEventBus(); bus.publish(object())` — no error.
2. (After I-01) Log shows `[EventBus] StrategyEntered` when entry condition fires.

---

## SECTION C — Paper Broker

---

### C-01 — Create `PaperBroker`
**New file**: `execution/paper_broker.py`
**Implements**: `ExecutionSubmitter` (`execution/strategy_engine/_protocols.py::ExecutionSubmitter`)

```python
class PaperBroker:
    """Simulates IBKR fills synchronously; calls on_fill immediately."""
    def __init__(self, on_fill: Callable[[FillEvent], None]) -> None:
        self._on_fill = on_fill
        self._next_order_id = 10_001

    def submit(self, signal: TradeSignal, qty: int) -> int | None:
        order_id = self._next_order_id
        self._next_order_id += 1
        fill = FillEvent(
            strategy_id=signal.strategy_id,
            symbol=signal.symbol,
            is_entry=(signal.action == Action.ENTRY),
            fill_price=signal.entry_price or 0.0,
            fill_qty=qty,
            order_id=order_id,
        )
        log.info("[PaperBroker] Fill: %s %s ×%d @ %.2f  order_id=%d",
                 signal.symbol, signal.action, qty, fill.fill_price, order_id)
        self._on_fill(fill)
        return order_id
```

Imports needed: `FillEvent`, `TradeSignal`, `Action` from `execution/strategy_engine/_protocols.py` and `_signals.py`.

**Smoke test**:
1. Instantiate `PaperBroker(on_fill=print)` and call `submit()` with a fake signal — prints a FillEvent.
2. (After G-01 + G-02) Execute a pending signal in the GUI; log shows `[PaperBroker] Fill: MRK entry ×N @ P.PP  order_id=10001`.

---

## SECTION D — AppService: Candle Providers

---

### D-01 — Add `_get_candles_df(symbol)` to AppService
**File**: `gui/app_service.py`
**Class/Method**: `AppService` — new private method

Mirrors `execution/strategy_runner.py::_load_candles_df()`. Loads `price_3m` and `price_15m` from `~/.usswing/candles.db` for a single symbol, returns `dict[str, pd.DataFrame]`. Columns: `datetime, open, high, low, close, volume`.

```python
def _get_candles_df(self, symbol: str) -> dict[str, pd.DataFrame]:
    ...
```

Can be a direct copy-paste of `_load_candles_df()` from `strategy_runner.py` adapted as a method (replace `db_path` param with `self._CANDLE_DB_PATH` or use the same constant).

**Smoke test**:
1. In REPL (with `AppService` running), call `svc._get_candles_df("MRK")` — returns dict with "3m"/"15m" keys and non-empty DataFrames if candle data exists.
2. Returns `{}` (not an exception) when candles.db doesn't exist.

---

### D-02 — Add `_get_latest_bar(symbol, tf)` to AppService
**File**: `gui/app_service.py`
**Class/Method**: `AppService` — new private method

```python
def _get_latest_bar(self, symbol: str, tf: str) -> OHLCVBar | None:
    ...  # SELECT ... ORDER BY datetime DESC LIMIT 1
```

Used by `StrategyEngine._fanout()` as `bar_provider`.

**Smoke test**:
1. `svc._get_latest_bar("MRK", "3m")` returns an `OHLCVBar` if data exists, `None` otherwise.
2. No exception when candles.db is missing.

---

## SECTION E — PendingSignalStore Wiring

---

### E-01 — Add `pending_signals_updated` signal to AppService
**File**: `gui/app_service.py`
**Class**: `AppService` signal declarations (lines ~941–963)

Add one line:
```python
pending_signals_updated = pyqtSignal()   # pending signal list changed
```

**Smoke test**:
1. `svc.pending_signals_updated.connect(lambda: print("updated"))` — no error.
2. (After E-02) Connecting adds a pending signal and the lambda fires.

---

### E-02 — Create `PendingSignalStore` in AppService, update `get_pending_signals()`
**File**: `gui/app_service.py`
**Class/Method**: `AppService.__init__()`, `AppService.get_pending_signals()`

In `__init__`:
```python
self._pending_store = PendingSignalStore(self)
self._pending_store.pending_signal_added.connect(lambda _: self.pending_signals_updated.emit())
self._pending_store.pending_signal_removed.connect(lambda _: self.pending_signals_updated.emit())
```

Update `get_pending_signals()`:
```python
def get_pending_signals(self, user_id: int | None = None) -> list[GuiTradeSignal]:
    return [_engine_signal_to_gui(s) for s in self._pending_store.list()]
```

(Converter added in E-03.)

**Smoke test**:
1. After startup, `svc.get_pending_signals()` returns `[]` — no crash.
2. (After E-03 + F-01) Manually call `svc._pending_store.add(fake_signal)` — `pending_signals_updated` fires and `get_pending_signals()` returns one item.

---

### E-03 — Add `_engine_signal_to_gui()` converter + `signal_id` field on GUI TradeSignal
**Files**: `data/models.py`, new helper in `execution/signal_bridge.py`

**Step 1** — Add `signal_id: str = ""` field to `data.models.TradeSignal` (end of dataclass).

**Step 2** — Create `execution/signal_bridge.py`:
```python
from us_swing.execution.strategy_engine._signals import TradeSignal as EngineSignal, Action
from us_swing.data.models import TradeSignal as GuiTradeSignal

def engine_to_gui(ts: EngineSignal) -> GuiTradeSignal:
    return GuiTradeSignal(
        symbol=ts.symbol,
        side="BUY" if ts.action == Action.ENTRY else "SELL",
        strategy_id=ts.strategy_id,
        score=0.0,
        entry_price=ts.entry_price or 0.0,
        stop_loss=ts.stop_loss or 0.0,
        target_price=ts.target or 0.0,
        recommended_qty=ts.qty_recommended,
        signal_id=ts.signal_id,
    )
```

**Smoke test**:
1. `from us_swing.execution.signal_bridge import engine_to_gui` — no import error.
2. Pass a fake `EngineSignal` — returns a `GuiTradeSignal` with `signal_id` populated.

---

## SECTION F — StrategyEngine Wiring

---

### F-01 — Instantiate `StrategyEngine` in `AppService.__init__()`
**File**: `gui/app_service.py`
**Class/Method**: `AppService.__init__()`

After `self._pending_store` setup (E-02), add:
```python
from us_swing.execution.risk_validator import PassthroughRiskValidator
from us_swing.execution.event_bus import QtEventBus
from us_swing.execution.paper_broker import PaperBroker
from us_swing.execution.strategy_engine._engine import StrategyEngine
from us_swing.gui.strategy_builder_dialog import load_strategies, save_strategies

self._event_bus = QtEventBus(self)
self._paper_broker = PaperBroker(on_fill=self._on_paper_fill)
self._strategy_engine = StrategyEngine(
    registry_loader=load_strategies,
    registry_saver=save_strategies,
    candles_provider=self._get_candles_df,
    bar_provider=self._get_latest_bar,
    risk=PassthroughRiskValidator(),
    submitter=self._paper_broker,
    pending=self._pending_store,
    bus=self._event_bus,
    parent=self,
)
self._strategy_engine.start()
```

**Smoke test**:
1. Start the app — no exception on startup, log shows `[Strategy] engine ready — N active strateg(ies)`.
2. Stop the app — engine thread exits cleanly (no `QThread: Destroyed while thread is still running`).

---

### F-02 — Wire `live_bar_data_updated` → `StrategyEngine.on_candle_closed`
**File**: `gui/app_service.py`
**Class/Method**: `AppService.__init__()` — one line after F-01

```python
self.live_bar_data_updated.connect(self._strategy_engine.on_candle_closed)
```

**Smoke test**:
1. With a strategy active and candle data present, trigger a candle write (e.g. live bar worker fires). Log shows `[Strategy] engine ready` and (if condition matches) `[Strategy] TESTING entered Running`.
2. Log shows no `[Strategy] fan-out: no bar available` errors when bars exist.

---

### F-03 — Add `_on_paper_fill()` callback to AppService
**File**: `gui/app_service.py`
**Class/Method**: `AppService` — new private method

```python
def _on_paper_fill(self, fill: FillEvent) -> None:
    self._strategy_engine.on_order_fill(fill)
    self.log_message.emit(
        "INFO",
        f"[Strategy] Paper fill confirmed: {fill.symbol}  "
        f"{'entry' if fill.is_entry else 'exit'}  "
        f"qty={fill.fill_qty}  price={fill.fill_price:.2f}  order={fill.order_id}",
    )
    self.positions_updated.emit()
```

This is the callback passed to `PaperBroker.__init__()` in F-01.

**Smoke test**:
1. Execute a pending signal in the GUI → log panel shows `[Strategy] Paper fill confirmed: MRK entry qty=N price=P.PP order=10001`.
2. No exception from the engine thread (check console for tracebacks).

---

## SECTION G — Execute Button Routing

---

### G-01 — Update `AppService.execute_signal()` to dispatch through PaperBroker
**File**: `gui/app_service.py`
**Class/Method**: `AppService.execute_signal()` (line ~1588)

Current implementation just logs a random number. Replace with:
```python
def execute_signal(self, signal: GuiTradeSignal, quantity: int) -> int:
    # Pop the engine signal from the pending store by signal_id
    eng_sig = self._pending_store.execute(signal.signal_id)
    if eng_sig is None:
        self.log_message.emit("WARNING", f"[Strategy] Signal {signal.signal_id} not found in pending store")
        return -1
    order_id = self._paper_broker.submit(eng_sig, quantity) or -1
    return order_id
```

Requires `signal.signal_id` set on the GUI signal (done in E-03).

**Smoke test**:
1. Click Execute on a pending signal row → log shows `[PaperBroker] Fill: ... order_id=10001` and `[Strategy] Paper fill confirmed: ...`.
2. The pending signal row disappears from the tab after execution.

---

## SECTION H — Pending Signals Tab: Live Refresh

---

### H-01 — Make Pending Signals tab refresh dynamically
**File**: `gui/execution_panel.py`
**Class/Method**: `ExecutionPanel._build_signals_pane()`, add `ExecutionPanel._refresh_signals_pane()`

Currently `_build_signals_pane()` builds signal rows once at init from `demo.get_pending_signals()`. After F-01/F-02 signals arrive asynchronously.

**Change**:
1. Extract signal-row-building into `_refresh_signals_pane(group_layout: QVBoxLayout)`.
2. In `_build_signals_pane()`, store `self._signals_group_layout = group_layout`.
3. After building, connect: `demo.pending_signals_updated.connect(self._on_signals_updated)`.
4. Add `_on_signals_updated()`:
   ```python
   def _on_signals_updated(self) -> None:
       # clear old rows
       while self._signals_group_layout.count():
           w = self._signals_group_layout.takeAt(0).widget()
           if w: w.deleteLater()
       self._signal_rows.clear()
       # rebuild
       signals = self._demo.get_pending_signals()
       mode = self._demo.get_active_user().mode
       for sig in signals:
           row = _SignalRow(sig, mode)
           row.execute_requested.connect(self._on_execute)
           self._signal_rows.append(row)
           self._signals_group_layout.addWidget(row)
       if not signals:
           lbl = QLabel("No pending signals at this time.")
           lbl.setStyleSheet(f"color: {C.MUTED}; padding: 20px;")
           lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
           self._signals_group_layout.addWidget(lbl)
       self._status_lbl.setText(f"{len(signals)} signal(s) pending — review and execute above")
   ```

**Smoke test**:
1. With the app running, manually trigger a pending signal add (via `svc._pending_store.add(...)`) — the Pending Signals tab refreshes automatically without restarting.
2. Execute a signal → row disappears from the tab in real-time.

---

## SECTION I — Strategy Executor: Engine-Driven Status

---

### I-01 — Wire `QtEventBus` → AppService → strategy badge refresh
**File**: `gui/app_service.py`, `execution/event_bus.py`
**Class/Method**: `AppService.__init__()` + new `AppService._on_strategy_event()`

After engine creation (F-01), connect:
```python
self._event_bus.event_published.connect(self._on_strategy_event)
```

Add signal to AppService:
```python
strategy_status_changed = pyqtSignal(str, str)  # (strategy_name, new_status)
```

Add handler:
```python
def _on_strategy_event(self, event: object) -> None:
    from us_swing.execution.strategy_engine._events import StrategyEntered, StrategyExited
    if isinstance(event, StrategyEntered):
        self.strategy_status_changed.emit(event.strategy_id, "Running")
    elif isinstance(event, StrategyExited):
        self.strategy_status_changed.emit(event.strategy_id, "Active")
```

**Smoke test**:
1. Connect `svc.strategy_status_changed.connect(print)` in REPL; trigger entry condition → `("TESTING", "Running")` is printed.
2. No crash when the event is an unrecognised type.

---

### I-02 — Wire `strategy_status_changed` → `_StrategyTablePane` badge
**File**: `gui/execution_panel.py`
**Class/Method**: `_StrategyTablePane.__init__()` + `_StrategyTablePane.update_signal_status()`

In `_StrategyTablePane.__init__()` (after `self._demo = demo`):
```python
demo.strategy_status_changed.connect(self._on_engine_status)
```

Add method:
```python
def _on_engine_status(self, strategy_name: str, new_status: str) -> None:
    for cfg in self._configs:
        if cfg.name == strategy_name:
            cfg.strategy_signal["Status"] = new_status
            save_strategies(self._configs)
            break
    self._refresh_table()
```

**Smoke test**:
1. Run strategy with a condition that should fire (e.g. `Price('Spot','Last','close','3m') > 0` — always true). After a candle bar arrives, the badge in Strategy Executor flips to "Running" without pressing Play again.
2. When exit condition fires, badge returns to "Active".

---

### I-03 — Replace `StrategyRunWorker` with `StrategyEngine` in Play button
**File**: `gui/execution_panel.py`
**Class/Method**: `_StrategyTablePane._on_run()`, `_start_worker()`, `_stop_worker()`

The Play button should now toggle the strategy on/off in `StrategyEngine` instead of starting the polling `StrategyRunWorker`.

**Change `_on_run()`**:
```python
def _on_run(self, src_row: int) -> None:
    cfg = self._configs[src_row]
    current_status = cfg.strategy_signal.get("Status", "Inactive")
    if current_status == "Inactive":
        cfg.strategy_signal["Status"] = "Active"
        cfg.mode = "manual"           # re-enable in engine
    else:
        cfg.strategy_signal["Status"] = "Inactive"
        cfg.mode = "disabled"         # remove from engine
    save_strategies(self._configs)
    self._demo._strategy_engine.reload_registry()   # type: ignore[attr-defined]
    self._refresh_table()
```

**Remove**: `_run_workers: dict`, `_start_worker()`, `_stop_worker()`, `_on_worker_status()`, `_on_worker_symbols()`.

**Smoke test**:
1. Press Play on TESTING strategy → badge turns green ("Active"), engine log says `[Strategy] engine ready — 1 active strateg(ies)`. Press again → badge reverts, engine drops the strategy.
2. After Play, when a candle fires for MRK and entry condition is met, badge changes to "Running" automatically (via I-01 + I-02) — no 30-second poll delay.

---

## Summary Table

| ID | Action | File(s) | Done? |
|---|---|---|---|
| A-01 | Fix `accepts()` symbol_mode strings | `execution/strategy_engine/_context.py` | [x] |
| A-02 | Delete dead tokenizer code from strategy_runner | `execution/strategy_runner.py` | [x] |
| B-01 | Create `PassthroughRiskValidator` | `execution/risk_validator.py` (new) | [x] |
| B-02 | Create `QtEventBus` | `execution/event_bus.py` (new) | [x] |
| C-01 | Create `PaperBroker` | `execution/paper_broker.py` (new) | [x] |
| D-01 | Add `_get_candles_df()` to AppService | `gui/app_service.py` | [x] |
| D-02 | Add `_get_latest_bar()` to AppService | `gui/app_service.py` | [x] |
| E-01 | Add `pending_signals_updated` signal | `gui/app_service.py` | [x] |
| E-02 | Create `PendingSignalStore` instance, update `get_pending_signals()` | `gui/app_service.py` | [x] |
| E-03 | Add `signal_id` to `GuiTradeSignal`; create `signal_bridge.py` | `data/models.py`, `execution/signal_bridge.py` (new) | [x] |
| F-01 | Instantiate `StrategyEngine` in AppService | `gui/app_service.py` | [x] |
| F-02 | Wire `live_bar_data_updated` → engine | `gui/app_service.py` | [x] |
| F-03 | Add `_on_paper_fill()` callback | `gui/app_service.py` | [x] |
| G-01 | Update `execute_signal()` to route through PaperBroker | `gui/app_service.py` | [x] |
| H-01 | Make Pending Signals tab refresh dynamically | `gui/execution_panel.py` | [x] |
| I-01 | Wire `QtEventBus` → AppService `strategy_status_changed` | `gui/app_service.py`, `execution/event_bus.py` | [x] |
| I-02 | Wire `strategy_status_changed` → `_StrategyTablePane` badge | `gui/execution_panel.py` | [x] |
| I-03 | Replace `StrategyRunWorker` play with engine `reload_registry()` | `gui/execution_panel.py` | [x] |

**Recommended order**: A-01 → A-02 → B-01 → B-02 → C-01 → D-01 → D-02 → E-01 → E-02 → E-03 → F-01 → F-02 → F-03 → G-01 → H-01 → I-01 → I-02 → I-03
