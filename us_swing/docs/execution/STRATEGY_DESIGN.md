# Strategy Engine — Design & GUI Specification

**Tool:** EXE  
**Date:** 2026-05-19  
**Scope:** Strategy protocol, built-in strategies, Settings configuration UI, Execution Panel signal flow, Exit architecture

---

## 1. Architecture

### 1.1 Entry Path — Three Layers

The entry path spans three layers. The GUI only touches the first and last:

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 1 — Strategy Foundation        core/strategies/        │
│  StrategyProtocol · StrategyRegistry · Built-in strategies    │
└──────────────────────────────────────────────────────────────┘
                           │ StrategySignal
┌──────────────────────────────────────────────────────────────┐
│  Layer 2 — Evaluation Engine          execution/              │
│  StrategyEngine — fires on each 3m bar close                  │
└──────────────────────────────────────────────────────────────┘
                           │ TradeSignal (manual) or direct order (auto)
┌──────────────────────────────────────────────────────────────┐
│  Layer 3 — Order Execution            execution/              │
│  RiskManager · ExecutionRouter · PaperEngine / IBKR           │
└──────────────────────────────────────────────────────────────┘
```

**Key invariant:** Strategies live in `core/strategies/` so the future BKT (backtesting)
tool can import the same classes without depending on `execution/`. A strategy never
knows whether it is running live, in paper mode, or in a backtest — it only sees candle
data and returns a signal.

---

### 1.2 Exit Architecture — Three Independent Paths

Once a position is open, **three independent paths** can close it. They operate in parallel; the first to fire wins. A position can only be closed once — whichever path triggers first causes the `PositionTracker` to mark the position CLOSED, and the other two paths stop watching that symbol.

```
                    ┌─────────────────────────────────────────────┐
                    │           OPEN POSITION (any symbol)         │
                    └──────┬──────────────────┬────────────────────┘
                           │                  │                  │
              ─────────────┼──────────────────┼──────────────────┼───────────
              Path 1        │  Path 2          │  Path 3          │
              STRATEGY      │  PRICE-LEVEL     │  MANUAL          │
              ─────────────┼──────────────────┼──────────────────┼───────────
                           │                  │                  │
              StrategyEngine│  PositionExit    │  User clicks     │
              compute()     │  Monitor         │  [Close] button  │
              action="exit" │  on each tick    │  in Position     │
              every 3m bar  │                  │  Monitor         │
                           │                  │                  │
              Mode-check    │  NO mode check   │  Confirmation    │
              applies:      │  ALWAYS fires    │  dialog, then    │
              Manual →      │  immediate MKT   │  MKT SELL        │
              Pending card  │  SELL directly   │                  │
              Auto →        │  to Execution    │                  │
              direct order  │  Router          │                  │
                           │                  │                  │
              User can      │  Cannot be       │  Always          │
              "Keep Holding"│  suppressed or   │  user-initiated  │
              (suppresses   │  delayed by mode │                  │
              this path)    │                  │                  │
```

**Safety rule:** Paths 2 and 3 are completely independent of strategy mode. A stop hit
while the strategy is in Manual mode fires immediately — the trader is never required to
click Approve for a stop-loss or trailing-stop exit. Only Path 1 (strategy signal exit)
is subject to mode-based routing.

#### Path 2 in detail — PositionExitMonitor

`PositionExitMonitor` (in `execution/position_exit_monitor.py`) subscribes to
`LiveTickWorker.tick_price`. On every price tick for a symbol with an open position:

1. **Update trailing stop** — if trailing stop is enabled for this position and
   `price − trail_offset > current_trailing_stop`, raise the trailing stop to
   `price − trail_offset`. Trailing stops only move in the profitable direction.

2. **Compute effective stop** — `effective_stop = max(fixed_sl, trailing_stop_level)`.
   If trailing stop is disabled, `effective_stop = fixed_sl`.

3. **Check exit condition** — if `price ≤ effective_stop`, call
   `ExecutionEngine.exit_position(symbol, reason)` immediately.
   `reason` is `'fixed_sl'` or `'trailing_sl'` depending on which level was hit.

4. **No bar-close dependency** — this check runs on every 5-second tick, not just on
   3-minute bar closes. A gap-down that skips the stop level still triggers on the
   first tick below the effective stop.

#### Exit configuration — set per position after entry

When a position opens, the trader configures its exit behaviour in the Position Monitor
panel (§8). The three exit types are not mutually exclusive — all three can be active
simultaneously. Whichever fires first closes the position.

| Exit type | Configured where | Fires when |
|---|---|---|
| Fixed SL | Stop column in Position Monitor (editable spinbox) | Tick price ≤ stop value |
| Trailing SL | Exit config expand row in Position Monitor | Tick price ≤ current trailing level |
| Strategy exit | Strategy mode in Settings → Strategies | `compute()` returns `"exit"` on bar close |
| Manual close | [Close] button in Position Monitor | User clicks and confirms |

---

## 2. Strategy Protocol — The Buildable Template

Every strategy is a Python class that follows this protocol. The template below is the
canonical pattern — when building a new strategy, copy it and fill in `Params` and
`compute()` only.

```python
from __future__ import annotations
from typing import ClassVar, Literal
from dataclasses import dataclass, field
import pandas as pd
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class TargetLevel:
    price:      float
    exit_pct:   float            # fraction of open qty to sell at this level, e.g. 0.5 = sell 50%
    stop_after: float | None = None  # new stop to apply to the remaining position after this target is hit


@dataclass(frozen=True)
class StrategySignal:
    action:               Literal["entry", "exit", "hold", "scale_in"]
    stop_loss:            float | None = None
    target:               float | None = None          # single full-exit target — used by simple strategies
    targets:              list[TargetLevel] = field(default_factory=list)  # multi-target exits; overrides target when non-empty
    update_trailing_stop: float | None = None          # new stop level to apply to the open position (paired with "hold")
    scale_in_qty_pct:     float | None = None          # fraction of original position size to add (paired with "scale_in")
    metadata:             dict = field(default_factory=dict)


# Action reference:
#   "entry"    — open a new position; stop_loss and target/targets required
#   "exit"     — close the full open position immediately
#   "hold"     — no order; update_trailing_stop may carry a new stop level
#   "scale_in" — add to an existing position; scale_in_qty_pct carries the add size


class StrategyProtocol:
    """
    Copy this template to build a new strategy.
    Only Params and compute() need to be implemented.
    Register with @StrategyRegistry.register at class definition.
    """
    name:         ClassVar[str]             # unique snake_case identifier
    description:  ClassVar[str]             # one-line shown in Settings UI
    timeframes:   ClassVar[list[str]]       # e.g. ["3m", "15m"] — drives candle fetch

    class Params(BaseModel):
        # Declare every user-tweakable parameter here.
        # Field(ge=, le=) sets spinbox bounds in the Settings UI automatically.
        pass

    param_schema: ClassVar[type[BaseModel]]  # = Params

    def __init__(self, params: dict) -> None:
        self._p = self.param_schema(**params)

    def compute(self, candles: dict[str, pd.DataFrame]) -> StrategySignal:
        """
        Args:
            candles: keyed by timeframe string, e.g. {"3m": df, "15m": df}.
                     Each DataFrame has columns: open, high, low, close, volume.
                     Rows are sorted oldest-first; iloc[-1] is the just-closed bar.
        Returns:
            StrategySignal — action is one of "entry", "exit", "hold", "scale_in".
            Strategies are position-unaware: compute() receives only candles. The
            StrategyEngine handles routing based on whether a position is already open.
        """
        raise NotImplementedError
```

### How params render in the Settings UI automatically

| Pydantic field type | Widget rendered |
|---------------------|-----------------|
| `int` with `ge`/`le` | `QSpinBox` bounded to Field range |
| `float` with `ge`/`le` | `QDoubleSpinBox` |
| `str` with `choices=[...]` | `QComboBox` |
| `str` (no choices) | `QLineEdit` |
| `bool` | `QCheckBox` |

No GUI code changes are needed when a new strategy is added to the registry.

---

## 3. Built-in Strategies

### BOSS EMA

Entry when price is above EMA200 on the higher timeframe **and** EMA13 crosses above
EMA50 on the lower timeframe. Exit when EMA13 crosses back below EMA50.

```python
@StrategyRegistry.register
class BossEmaStrategy(StrategyProtocol):
    name        = "boss_ema"
    description = "EMA trend cross with multi-timeframe filter"
    timeframes  = ["3m", "15m"]

    class Params(BaseModel):
        fast_ema:      int = Field(13,  ge=3,  le=50,  description="Fast EMA period")
        slow_ema:      int = Field(200, ge=50, le=500, description="Slow EMA period")
        cross_ema:     int = Field(50,  ge=10, le=200, description="Cross EMA period")
        ltf_timeframe: str = Field("3m",  description="Entry timeframe")
        htf_timeframe: str = Field("15m", description="Trend filter timeframe")

    param_schema = Params

    def compute(self, candles: dict[str, pd.DataFrame]) -> StrategySignal:
        ltf = candles[self._p.ltf_timeframe]
        htf = candles[self._p.htf_timeframe]

        ema_fast  = ltf["close"].ewm(span=self._p.fast_ema).mean()
        ema_cross = ltf["close"].ewm(span=self._p.cross_ema).mean()
        ema_slow  = htf["close"].ewm(span=self._p.slow_ema).mean()

        trend_up   = htf["close"].iloc[-1] > ema_slow.iloc[-1]
        cross_now  = ema_fast.iloc[-1] > ema_cross.iloc[-1]
        cross_prev = ema_fast.iloc[-2] <= ema_cross.iloc[-2]

        if trend_up and cross_now and cross_prev:
            swing_low  = ltf["low"].iloc[-10:].min()
            stop       = swing_low * 0.998
            risk       = ltf["close"].iloc[-1] - stop
            return StrategySignal("entry", stop_loss=stop, target=ltf["close"].iloc[-1] + risk * 2)

        if not cross_now:
            return StrategySignal("exit")

        return StrategySignal("hold")
```

### BOSS ADX

Entry when ADX confirms a trend on the higher timeframe, choppiness index is below
threshold, and RSI is not overbought. Exit on ADX collapse.

```python
@StrategyRegistry.register
class BossAdxStrategy(StrategyProtocol):
    name        = "boss_adx"
    description = "ADX trend filter with choppiness and RSI guards"
    timeframes  = ["3m", "15m"]

    class Params(BaseModel):
        adx_period:    int   = Field(14, ge=5,  le=50)
        adx_threshold: float = Field(25, ge=15, le=50, description="Min ADX for entry")
        chop_threshold: float = Field(50, ge=30, le=65, description="Max choppiness index")
        rsi_period:    int   = Field(14, ge=5,  le=30)
        rsi_overbought: int  = Field(65, ge=55, le=80)
        ltf_timeframe: str   = Field("3m")
        htf_timeframe: str   = Field("15m")

    param_schema = Params

    def compute(self, candles: dict[str, pd.DataFrame]) -> StrategySignal:
        # ... ADX + choppiness + RSI evaluation ...
        return StrategySignal("hold")
```

### EMA Crossover (reference template)

The simplest possible implementation — single timeframe, two EMAs. Useful as the
baseline to validate the protocol and as a starting point for new strategies.

```python
@StrategyRegistry.register
class EmaCrossoverStrategy(StrategyProtocol):
    name        = "ema_crossover"
    description = "Fast/slow EMA crossover on a single timeframe"
    timeframes  = ["3m"]

    class Params(BaseModel):
        fast_period: int = Field(9,  ge=3, le=50)
        slow_period: int = Field(21, ge=5, le=200)
        timeframe:   str = Field("3m")

    param_schema = Params

    def compute(self, candles: dict[str, pd.DataFrame]) -> StrategySignal:
        df   = candles[self._p.timeframe]
        fast = df["close"].ewm(span=self._p.fast_period).mean()
        slow = df["close"].ewm(span=self._p.slow_period).mean()

        cross_up   = fast.iloc[-1] > slow.iloc[-1] and fast.iloc[-2] <= slow.iloc[-2]
        cross_down = fast.iloc[-1] < slow.iloc[-1] and fast.iloc[-2] >= slow.iloc[-2]

        if cross_up:
            return StrategySignal("entry", stop_loss=df["low"].iloc[-3:].min())
        if cross_down:
            return StrategySignal("exit")
        return StrategySignal("hold")
```

---

## 4. Settings → Strategies Tab

### Layout

```
Settings
 Users │ Strategies │ System │ Universe │ Database
───────────────────────────────────────────────────

  Strategy Library                  [💾 Save Changes]

  ┌─ BOSS EMA ────────────────────────────────────────┐
  │  EMA trend cross with multi-timeframe filter       │
  │  Uses: 3m (entry) · 15m (trend filter)             │
  │                                                    │
  │  Mode:  [ Disabled ]  [ Manual ]  [● Auto ]        │
  │                                                    │
  │  Fast EMA     [ 13 ↑↓]    Slow EMA    [200 ↑↓]   │
  │  Cross EMA    [ 50 ↑↓]    LTF Frame   [ 3m ▼ ]   │
  │  HTF Frame    [15m ▼ ]                             │
  └────────────────────────────────────────────────────┘

  ┌─ BOSS ADX ────────────────────────────────────────┐
  │  ADX trend filter with choppiness and RSI guards   │
  │  Uses: 3m (entry) · 15m (trend)                   │
  │                                                    │
  │  Mode:  [● Disabled ]  [ Manual ]  [ Auto ]        │
  │  ╌╌╌╌╌ Disabled — parameters locked ╌╌╌╌╌╌╌╌╌╌╌  │
  │                                                    │
  │  ADX Threshold [ 25 ↑↓]   ADX Period  [ 14 ↑↓]   │
  │  Chop Limit    [ 50 ↑↓]   RSI Period  [ 14 ↑↓]   │
  │  RSI Overbought[ 65 ↑↓]   LTF Frame   [ 3m ▼ ]   │
  │  HTF Frame     [15m ▼ ]                            │
  └────────────────────────────────────────────────────┘

  ┌─ EMA CROSSOVER ───────────────────────────────────┐
  │  Fast/slow EMA crossover on a single timeframe     │
  │  Uses: single timeframe                            │
  │                                                    │
  │  Mode:  [● Disabled ]  [ Manual ]  [ Auto ]        │
  │  ╌╌╌╌╌ Disabled — parameters locked ╌╌╌╌╌╌╌╌╌╌╌  │
  │                                                    │
  │  Fast Period   [  9 ↑↓]   Slow Period [ 21 ↑↓]   │
  │  Timeframe     [ 3m ▼ ]                            │
  └────────────────────────────────────────────────────┘
```

### Mode Reference

| Mode | Strategy evaluates? | Signal destination | Order placed? |
|------|--------------------|--------------------|---------------|
| **Disabled** | No | — | No |
| **Manual** | Yes | Pending Signals list (user reviews) | Only on user click |
| **Auto** | Yes | Directly to ExecutionRouter | Immediately, no confirmation |

### Interaction Rules

| User action | Effect |
|-------------|--------|
| Switch to Disabled | Params grey out, "parameters locked" bar appears, strategy removed from next evaluation cycle |
| Switch to Disabled with open positions | Params grey out; existing open positions keep their current stop/target but receive **no further exit signals** from this strategy — trader must manage those positions manually or via the Position Monitor Close button |
| Switch Auto → Manual with open positions | Existing positions retain auto-exit routing (they were opened in Auto; their exits continue direct to `ExecutionRouter`); only NEW signals generated after the switch appear in Pending Signals |
| Switch Manual → Auto with pending signals | All pending signals currently in the queue are submitted immediately without further confirmation; subsequent signals route directly to `ExecutionRouter` |
| Switch to Manual or Auto (no open positions) | Params become editable, strategy added to evaluation immediately on next bar |
| Edit any param | Card border turns amber ("unsaved changes") |
| Click Save Changes | Configs written to DB, amber borders clear |
| New strategy registered in code | Card auto-appears on next app launch — no GUI changes needed |

---

## 5. Execution Panel — Signal Display

### Pending Signals (Manual strategies only)

The `_SignalRow` widget has the following badge states and button layout:

| Addition | Where | Detail |
|----------|-------|--------|
| Bar timestamp | Below `strategy_id` label (muted 8pt) | "3m bar 14:12" |
| STALE badge state | Status badge colour | Amber text, Execute button at 60% opacity |
| EXIT badge state | Status badge colour + button label | Orange badge, button reads "Execute SELL" |
| **[✕] Dismiss button** | Top-right corner of every ENTRY row (READY and STALE) | Muted icon; removes signal from Pending list and logs `[Execution] User dismissed signal for {symbol}` at INFO |
| **[Keep Holding] button** | Right of "Execute SELL" on EXIT rows | Suppresses the exit order; system auto-attaches a trailing stop to the position as a safety net |

```
┌─ Pending Signals ──────────────────────────────────────────────┐
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  AAPL            Entry   $182.50    Rec. Qty        [✕] │  │
│  │  boss_ema · BUY  Stop    $179.00    [ 25 ↑↓]           │  │
│  │  ⬤ READY         Target  $189.00    (overridden)       │  │
│  │  3m bar 14:12    R/R     1.9 ×      [Execute BUY]      │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  NVDA            Entry   $875.00    Rec. Qty        [✕] │  │
│  │  boss_ema · BUY  Stop    $855.00    [  8 ↑↓]           │  │
│  │  ⚠ STALE         Target  $915.00                       │  │
│  │  3m bar 13:57    R/R     2.0 ×      [Execute BUY]      │  │  ← dimmed
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  AAPL            EXIT signal                            │  │
│  │  boss_ema · SELL Full qty: 25 shares                    │  │
│  │  ⬤ EXIT          Est. P&L: +$133                       │  │
│  │  3m bar 15:03    [Execute SELL]    [Keep Holding]       │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  3 signal(s) pending — review and execute above                │
└────────────────────────────────────────────────────────────────┘
```

**STALE confirmation dialog:**
```
⚠ Signal is stale — conditions changed since generation.
Submit BUY 8 × NVDA @ MKT?
Entry ~$875.00  |  Stop $855.00  |  Target $915.00

[Cancel]   [Force Execute]
```

**Keep Holding confirmation dialog:**
```
⚠ Exit signal suppressed — position remains open.
A trailing stop will be attached automatically to protect capital.
Trailing stop level: $184.00  (based on last bar low)

[Cancel]   [Keep Holding + Attach Stop]
```

---

### Scale-In Proposal Card (Manual mode — `scale_in` action)

Appears in Pending Signals when a strategy emits `action = "scale_in"` and a position is already open. Distinct visual treatment from entry rows: blue-tinted border, "SCALE-IN" badge.

```
┌─────────────────────────────────────────────────────────────┐
│  AAPL             SCALE-IN  +$3,640    Add Qty          [✕] │
│  boss_ema · BUY   Current:  25 shares  [ 12 ↑↓]            │
│  ⬤ MOMENTUM       New stop  $181.00    (auto-calc)          │
│  3m bar 14:27     R/R 2.3×             [Add to Position]    │
└─────────────────────────────────────────────────────────────┘
```

- "Add Qty" spinbox: defaults to `scale_in_qty_pct × original_qty`, user can override
- "New stop" shows the stop for the combined position (strategy-returned `stop_loss`)
- [✕] Dismiss removes the scale-in proposal without affecting the open position
- [Add to Position] routes a new BUY order through `RiskManager.can_scale_in()` check then `ExecutionRouter`

---

### Partial Liquidation Proposal Card (Manual mode — TP1 hit)

Appears in Pending Signals when a strategy emits a `targets` list and the first `TargetLevel.price` is breached. Distinct from full EXIT: teal-tinted border, "TP1" badge. Remaining shares stay open.

```
┌─────────────────────────────────────────────────────────────┐
│  AAPL             TP1 HIT   Sell 50%   Sell Qty         [✕] │
│  boss_ema · SELL  Current:  25 shares  [ 12 ↑↓]            │
│  ⬤ TP1            Remain:   13 shares  (auto: 50%)          │
│  3m bar 14:48     Est. P&L: +$412      Stop after: $182.50  │
│                   [Execute TP1 Sell]   [Skip / Hold Full]   │
└─────────────────────────────────────────────────────────────┘
```

- "Sell Qty" spinbox: defaults to `TargetLevel.exit_pct × open_qty`; user can change the amount
- "Stop after" shows `TargetLevel.stop_after` — the new stop that will be applied to remaining shares after the partial sell
- [Skip / Hold Full] dismisses the TP1 proposal; position stays fully open; next bar re-evaluates
- After TP1 executes, the system watches for TP2 (next `TargetLevel` in the list) or strategy exit on remaining shares

### Auto Executed Today (below Pending Signals)

Auto-mode signals bypass the Pending list entirely. This read-only log provides visibility:

```
┌─ Auto Executed Today ──────────────────────────────────────┐
│  ✓  AAPL   boss_ema · BUY    25 × @$182.50   14:12        │
│  ✓  MSFT   boss_ema · BUY    10 × @$415.00   14:15        │
│  ✓  AAPL   boss_ema · EXIT   25 × @$187.80   15:03        │
└────────────────────────────────────────────────────────────┘
```

Rules:
- Read-only — no Execute button, no qty spinbox
- Entries appear in real time as auto signals fire
- Resets at session start (midnight)
- Clicking any row highlights the symbol in the Filtered Stocks table on the left

---

## 6. End-to-End Workflow

### Setup
- Universe: 500 S&P stocks in DB
- Screener runs 09:15 ET → 12 stocks pass today
- BOSS EMA configured: `fast=13, slow=200, cross=50, ltf=3m, htf=15m`, mode = **Auto**
- BOSS ADX mode = **Manual**

---

### Step 1 — Configure (Settings → Strategies)

```
User opens Settings → Strategies
  Sets BOSS EMA → [● Auto]  +  params as above
  Sets BOSS ADX → [● Manual]
  Clicks [💾 Save Changes]
    ↓
candles.db (~/.usswing/candles.db): strategy_configs
    boss_ema  → { mode: "auto",   params: {fast_ema:13, slow_ema:200, ...} }
    boss_adx  → { mode: "manual", params: {adx_threshold:25, ...} }
```

---

### Step 2 — Market Opens, Evaluation Begins

```
09:30 ET — LiveBarWorker starts emitting bar_closed signals

On each 3m bar close:
  StrategyEngine.evaluate(symbol, candles, active_configs)
    For each of the 12 filtered symbols:
      candles = { "3m": df[-200 bars], "15m": df[-100 bars] }
      BossEmaStrategy(params).compute(candles)   → StrategySignal
      BossAdxStrategy(params).compute(candles)   → StrategySignal
```

---

### Step 3 — Signal Fires (branch on mode)

```
14:12 ET — AAPL 3m bar closes

BossEmaStrategy.compute(candles):
  ✓ AAPL close $182.50 > EMA200 ($178.20) on 15m  → trend up
  ✓ EMA13 crossed above EMA50 on 3m               → entry trigger
  → StrategySignal(action="entry", stop_loss=179.00, target=189.00)

                    ┌─ mode = "auto" ─────────────────────────┐
                    │  RiskManager.validate() → pass           │
                    │  recommended_qty = 25                    │
                    │  ExecutionRouter → PaperEngine/IBKR      │
                    │  PositionTracker: AAPL position opened   │
                    │  MonitoringSession: AAPL → ENTERED       │
                    │  Auto Executed log: ✓ AAPL BUY 25×@182.50│
                    └──────────────────────────────────────────┘

14:12 ET — TSLA 3m bar closes

BossAdxStrategy.compute(candles):
  ✓ ADX = 28.4 > threshold 25
  ✓ Choppiness = 44.2 < limit 50
  ✓ RSI = 58 < overbought 65
  → StrategySignal(action="entry", stop_loss=238.00, target=260.00)

                    ┌─ mode = "manual" ───────────────────────┐
                    │  TradeSignal added to pending_signals    │
                    │  ExecutionPanel refreshes                │
                    │  TSLA row → ⬤ READY | boss_adx · BUY   │
                    │  → waits for user                        │
                    └──────────────────────────────────────────┘
```

---

### Step 4 — User Executes Manual Signal

```
User sees TSLA in Pending Signals:
  TSLA | boss_adx · BUY | ⬤ READY | Entry $245.00 | Stop $238.00 | Target $260.00 | R/R 2.1×

Leaves qty at recommended 15
Clicks [Execute BUY]
  ↓
Confirmation:
  "Submit BUY 15 × TSLA @ MKT?
   Entry ~$245.00  |  Stop $238.00  |  Target $260.00"
  [Cancel]  [Confirm]
  ↓
User clicks Confirm
  ↓
ExecutionRouter → PaperEngine / IBKR order
Signal removed from Pending Signals
PositionTracker: TSLA position opened
MonitoringSession: TSLA → ENTERED
```

---

### Step 5 — Staleness (NVDA example)

```
14:12 — NVDA signal generated by boss_ema → ⬤ READY
14:15 — next 3m bar closes

StrategyEngine re-evaluates NVDA:
  BossEmaStrategy.compute() → action="hold"  (EMA cross weakened)
    ↓
  pending_signal["NVDA"].fresh = False
  NVDA row badge → ⚠ STALE (amber)
  Execute button → 60% opacity

14:21 — another bar closes
  BossEmaStrategy.compute() → action="entry" again (cross re-confirmed)
    ↓
  pending_signal["NVDA"].fresh = True
  NVDA row badge → ⬤ READY (green)
  Execute button → full opacity
```

---

### Step 6 — Exit Signal

```
Next trading day, 3m bar closes for AAPL (auto position)

BossEmaStrategy.compute(candles):
  EMA13 crosses below EMA50 → exit condition
  → StrategySignal(action="exit")

mode = "auto":
  ExecutionRouter → SELL 25 × AAPL @ MKT
  PositionTracker: AAPL position closed, PnL calculated
  MonitoringSession: AAPL → EXITED
  Auto Executed log: ✓ AAPL boss_ema · EXIT 25×@$187.80 15:03
```

---

## 7. Full Data Flow Diagram

```
Settings Tab              Backend                    Execution Panel
────────────              ───────                    ───────────────

User saves config
  boss_ema = Auto
  boss_adx = Manual
       │
       ▼
  candles.db: strategy_configs
       │
       └──────────────► StrategyEngine loads configs on startup
                                   │
                       LiveBarWorker: bar_closed(symbol, bar)
                                   │
                       For each symbol × each enabled strategy:
                         strategy.compute(candles)
                                   │
                         StrategySignal(action="entry")
                                   │
                    ┌──────────────┴──────────────┐
               mode="manual"               mode="auto"
                    │                            │
             TradeSignal                   RiskManager
             → pending list                validates
                    │                            │
                    ▼                      ExecutionRouter
             ⬤ READY row                        │
             in Pending Signals            Order placed
                    │                            │
             User clicks                   Auto Executed
             Execute                       row added:
                    │                      ✓ AAPL BUY
             Confirmation                  25×@182.50
             dialog                        14:12
                    │
             Order placed
             Row removed
             from Pending
```

---

## 8. Position Monitor Panel

The Position Monitor is a persistent panel showing all currently open positions. It is
always visible during trading hours alongside the Execution Panel. Each position row is
expandable to reveal its full exit configuration — the three exit paths (§1.2) are
configured here, per position, after entry.

### Layout — Position Table

```
┌─ Open Positions ─────────────────────────────────────────────────────────────────────────────┐
│  2 open  ·  Capital in use: $40,750  ·  Available: $59,250  ·  Max: 50%  ·  Can enter: Yes  │
├────────┬────────────┬──────┬─────────┬──────────┬──────────────────┬──────────┬────────┬────┤
│ Symbol │ Strategy   │ Qty  │ Entry   │ Current  │ Effective Stop   │ Target   │ P&L    │    │
├────────┼────────────┼──────┼─────────┼──────────┼──────────────────┼──────────┼────────┼────┤
│ AAPL   │ boss_ema   │  25  │ $182.50 │ $187.20  │ 📍 $184.70 trail │[189.00↑↓]│ +$117↑ │[▼] │
│ TSLA   │ boss_adx   │  15  │ $245.00 │ $241.30  │ 🔒 $238.00 fixed │[260.00↑↓]│  -$57↓ │[▼] │
└────────┴────────────┴──────┴─────────┴──────────┴──────────────────┴──────────┴────────┴────┘
```

- **🔒 fixed** — Fixed SL is the effective stop (trailing not enabled or not yet risen above fixed SL)
- **📍 trail** — Trailing stop has risen above the fixed SL and is now the effective stop
- **Effective Stop** column is read-only display; the underlying values are edited in the expand row below
- **[▼]** button expands the Exit Configuration row for that position; collapses with **[▲]**

---

### Exit Configuration Row (expanded per position)

Clicking [▼] on a position row reveals its three exit controls. Closing the row does not
change any values — changes take effect immediately when the spinbox loses focus or the
toggle is flipped.

```
  AAPL — Exit Configuration
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                                                                             │
  │  Fixed Stop-Loss          [$179.00 ↑↓]   ● Active  (floor — never removed) │
  │                                                                             │
  │  Trailing Stop            [● Enabled ]                                     │
  │    Mode    [$ Amount ▼]   Trail offset   [  $2.50 ↑↓]                      │
  │    Current level  $184.70  (updated 14:27 · highest seen: $187.20)          │
  │                                                                             │
  │  Strategy Exit            boss_ema   ● Watching (Auto — fires direct)       │
  │    Override: if strategy fires exit → [Auto ▼]  (Auto / Send to Pending)   │
  │                                                                             │
  │                                        [Close Position]                    │
  └─────────────────────────────────────────────────────────────────────────────┘
```

#### Fixed Stop-Loss controls

| Field | Behaviour |
|---|---|
| Stop price spinbox | Editable at any time. Takes effect on next tick. Cannot be set above current price. |
| "Active" badge | Always present — the Fixed SL can never be disabled once a position is open. It is the unconditional capital floor. |
| Stop turns red | When `current_price` is within 1% of the stop value. |

#### Trailing Stop controls

| Field | Behaviour |
|---|---|
| Enable toggle | Off by default. When turned on, the current `highest_price_since_entry` is used as the first reference point. |
| Mode dropdown | **$ Amount** — `trail_level = highest_price − offset_$`. **% Amount** — `trail_level = highest_price × (1 − offset_pct / 100)`. |
| Trail offset spinbox | The dollar or percent distance to trail behind the highest price. |
| Current level | Read-only display of the live `trailing_stop_level`. Updates on each tick when a new high is set. |
| Highest seen | Read-only. The highest `tick_price` recorded since this position opened. |
| Effective stop update | When `trailing_stop_level > fixed_sl`, the Effective Stop column switches from 🔒 to 📍 and the trailing level is shown. |
| Disable trailing | Toggling off freezes the trailing level as a new Fixed SL (it does not revert to the old fixed SL). The trader is prompted: *"Lock trailing stop at $184.70 as new fixed stop? [Yes] [Cancel]"* |

**How trailing stop and fixed SL interact:**

```
  Entry $182.50  ·  Fixed SL $179.00  ·  Trail offset $2.50

  Price rises to $185.00  →  trail level = $185.00 − $2.50 = $182.50
                              effective_stop = max($179.00, $182.50) = $182.50  (📍 trail)

  Price rises to $188.00  →  trail level = $188.00 − $2.50 = $185.50
                              effective_stop = $185.50  (📍 trail)

  Price drops to $185.40  →  trail level unchanged (only moves up)
                              effective_stop still $185.50

  Price drops to $185.40  →  $185.40 ≤ $185.50  →  PositionExitMonitor fires SELL
                              reason = 'trailing_sl'
```

#### Strategy Exit Override

| Control | Behaviour |
|---|---|
| Strategy name + mode badge | Shows which strategy is watching this position and its current mode |
| Override dropdown | **Auto** (default) — strategy exit respects the strategy's mode setting (Auto fires direct, Manual shows card). **Send to Pending** — forces Manual mode for strategy exits on this position regardless of the strategy's global mode. Useful when a trader wants auto entries but manual exit approval for a specific trade. |

---

### Single-Position Close Confirmation Dialog

Triggered by [Close Position] in the expand row or [▼] → Close:

```
Close position?
Submit SELL 25 × AAPL @ MKT

Entry $182.50  ·  Current ~$187.20  ·  Est. P&L: +$117
Exit type: Manual

[Cancel]   [Confirm Close]
```

- Routes through `ExecutionEngine.close_position(symbol, user_id, reason='manual')`
- Recorded in `trades` with `trade_origin = 'manual'` and `exit_reason = 'manual'`
- Position Monitor row removed immediately on confirmation (before fill confirmation)

---

### Manual Entry Row

A collapsed "+ Add Trade" row at the bottom of the Open Positions table expands to a
manual entry form. A manually entered position has no driving strategy — its only active
exit paths are Fixed SL, Trailing SL (if enabled), and Manual Close.

```
┌─ Add Trade ───────────────────────────────────────────────────────────────────────────────┐
│  Ticker [AAPL ]  Qty [10↑↓]  Fixed SL [$180.00↑↓]  Target [$192.00↑↓]  [Submit BUY]     │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

- Capital check via `RiskManager.can_enter_new()` before submission; rejection shown inline
- Position created with `trade_origin = 'manual'`
- `PositionExitMonitor` begins watching this position immediately on fill confirmation
- Strategy Exit column in the expand row shows "None — manual position; no strategy watching"

### Pre-Market Readiness Bar

Displayed above the Open Positions table before 09:30 ET:

```
┌─ Session Readiness ──────────────────────────────────────────────────────────────────────────┐
│  Candles  ✓ 12/12 ready   Strategies  BOSS EMA: Auto  ·  BOSS ADX: Manual  ·  EMA Cross: Off │
│  Capital  $100,000 available (0 positions open)   Circuit Breaker  ✓ Clear                   │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

- "Circuit Breaker" shows green "✓ Clear" normally; switches to red "⛔ Triggered — restart required" when `circuit_breaker_active = True`
- Disappears at 09:30 ET when the live feed starts; re-appears after 16:00 ET

---

## 9. Strategy Lifecycle & Persistence

### 9.1 The Core Problem

Every day the screener produces a fresh watchlist. Some symbols will enter a position,
some will never trigger, some will fail mid-entry. Meanwhile the user may want to adjust
BOSS EMA parameters after observing a few trades. But a position already open was entered
under a specific set of params — changing them mid-trade would invalidate the exit logic
(e.g., the EMA cross that triggers the exit is computed with the same periods used at
entry). The tool also shuts down EOD and restarts next morning, so all of this state must
survive a full session boundary.

Two invariants must hold:
1. **Parameter immutability per cycle** — a position's entry and exit are always evaluated
   with the exact params that were active at the moment of entry. Global param changes in
   Settings only apply to new entries, never to open positions.
2. **Full cross-session persistence** — every relevant state (open positions, their frozen
   params, the daily watchlist, failure reasons) is written to the DB before shutdown and
   fully restored on next startup.

---

### 9.2 Parameter Snapshot Model

When a position opens, the `ExecutionEngine` immediately writes a snapshot of the
strategy's current params into the position row:

```
positions table
───────────────────────────────────────────────────────────────
position_id │ symbol │ strategy_id │ strategy_params_snapshot  │ ...
───────────────────────────────────────────────────────────────
1001        │ AAPL   │ boss_ema    │ {"fast_ema":13,"slow_ema":200,"cross_ema":50,...} │
1002        │ TSLA   │ boss_ema    │ {"fast_ema":13,"slow_ema":200,"cross_ema":50,...} │
```

When the `StrategyEngine` evaluates an **open** position on a bar close, it loads the
snapshot from the position row instead of the current global config:

```
StrategyEngine.evaluate(symbol, candles, position):
    if position is open:
        params = position.strategy_params_snapshot   ← frozen
    else:
        params = strategy_configs[strategy_id].params  ← current global
    signal = BossEmaStrategy(params).compute(candles)
```

This means two open positions can be running different param sets simultaneously, which is
correct — each reflects the market conditions at the time that particular entry was made.

#### What "cycle complete" means

A cycle starts when a position opens (`status = OPEN`) and ends when it closes
(`status = CLOSED`, regardless of exit reason: strategy, stop, trailing, or manual).
The snapshot is discarded when the position closes. Closed trade records in the `trades`
table retain the snapshot for backtesting and review.

#### Global param change with open positions

When the user edits BOSS EMA params in Settings and clicks Save:
- `strategy_configs` is updated → applies to the next new entry signal
- All open positions with `strategy_id = boss_ema` are **not** touched — their
  `strategy_params_snapshot` columns are unchanged
- The Settings card shows a warning badge (see §9.5)

---

### 9.3 Daily Stock Tracking — MonitoringSession

Each trading day the engine maintains a `monitoring_sessions` table. Every symbol that
the screener passes gets a row with a lifecycle state. This is the cross-session
persistence layer for the daily watchlist.

#### Lifecycle states

```
        ┌─────────────────────────────────────────────────────────┐
        │                   SCREENER PASSES                        │
        └──────────────────────────┬──────────────────────────────┘
                                   │
                              WATCHING
                           (in universe,
                            no signal yet)
                          /            \
                         /              \
              signal fired           no signal
              RiskManager OK         by EOD
                   │                     │
               ENTERED               DROPPED
           (position open)       (watchlist pruned
                │                  next morning)
          ┌─────┴──────┐
          │             │
        EXIT           FAILED
       CYCLE            │
      COMPLETE     entry attempt
    (trade closed)  rejected/error
```

| State | Set when | Next-day behaviour |
|---|---|---|
| `WATCHING` | Screener passes the symbol; no position open | Re-evaluated against fresh screener output |
| `ENTERED` | Position open | Engine reloads position + frozen params; continues monitoring |
| `EXIT_COMPLETE` | Position closed (any exit path) | Row archived; symbol can re-enter WATCHING if it passes screener again |
| `FAILED` | Order rejected by broker, fill timeout, `RiskManager` block | Logged with reason; re-enters WATCHING next day if screener still passes |
| `DROPPED` | Symbol no longer passes screener and had no open position | Row archived; no next-day action |

#### Table schema (design intent, not final DDL)

```
monitoring_sessions
───────────────────────────────────────────────────────────────────────
session_date │ symbol │ strategy_id │ status        │ failure_reason │ position_id
───────────────────────────────────────────────────────────────────────
2026-05-19   │ AAPL   │ boss_ema    │ ENTERED        │ —              │ 1001
2026-05-19   │ TSLA   │ boss_ema    │ ENTERED        │ —              │ 1002
2026-05-19   │ NVDA   │ boss_ema    │ WATCHING       │ —              │ —
2026-05-19   │ MSFT   │ boss_ema    │ FAILED         │ RiskManager: daily loss limit reached │ —
2026-05-19   │ AMZN   │ boss_ema    │ DROPPED        │ screener: no longer qualifies │ —
```

---

### 9.4 EOD Shutdown / Next-Day Startup Sequence

#### EOD (after 16:00 ET)

```
1. LiveBarWorker stops — no more bar_closed signals
2. PositionExitMonitor stops — no more tick monitoring
3. For each WATCHING symbol with no triggered signal today:
     monitoring_sessions[today][symbol].status = DROPPED
     (or leave as WATCHING if we want to keep it tomorrow — see note below)
4. Pending signals queue cleared (transient — not persisted)
5. "Auto Executed Today" log cleared (day-scoped UI only)
6. DB flush: all positions, monitoring_sessions, trades committed
```

> **WATCHING carry-forward rule:** A WATCHING symbol stays WATCHING across the session
> boundary as long as it still passes the screener next morning. The engine does not
> force DROPPED just because no signal fired today — a swing setup can take multiple days
> to trigger. DROPPED only applies when the symbol is explicitly removed from the
> screener's output.

#### Next-Day Startup

```
1. Load strategy_configs → current params + mode for each strategy
2. Load open positions (status = OPEN):
     For each position:
       bind frozen params from strategy_params_snapshot
       re-attach PositionExitMonitor with saved stop/trailing config
3. Screener runs (or last-night's output is used until 09:15)
4. Build monitoring_sessions for today:
     a. Carry over ENTERED positions (already loaded in step 2)
     b. For each screener symbol not already ENTERED:
          look up yesterday's session row
          if WATCHING or FAILED → set status = WATCHING (new signal evaluation pending)
          if new symbol → insert WATCHING row
5. StrategyEngine ready — begins evaluating on first bar_closed after 09:30 ET
```

---

### 9.5 Settings UI — Params Drift Warning

When the user opens Settings → Strategies, if BOSS EMA's global params differ from the
snapshot stored in any open position, the card shows an informational badge:

```
  ┌─ BOSS EMA ─────────────────────────────────────────────────────────┐
  │  EMA trend cross with multi-timeframe filter                        │
  │  Mode:  [ Disabled ]  [ Manual ]  [● Auto ]                        │
  │                                                                     │
  │  ⚠ 2 open positions using prior params (slow_ema: 200)             │
  │    Current setting (slow_ema: 150) applies to new entries only.    │
  │                                                                     │
  │  Fast EMA   [ 13 ↑↓]    Slow EMA   [150 ↑↓]   ← current global   │
  │  Cross EMA  [ 50 ↑↓]    LTF Frame  [ 3m ▼ ]                       │
  │  HTF Frame  [15m ▼ ]                                               │
  └─────────────────────────────────────────────────────────────────────┘
```

Rules:
- Warning badge is informational only — no blocking prompt
- Hovering the badge shows a tooltip listing the open symbols and their snapshot values
- Warning disappears automatically when all positions using older params close
- The user cannot force a snapshot update — the only way is to close and re-enter

---

### 9.6 Failure Tracking

When an entry attempt fails (broker rejection, risk block, fill timeout), the engine:
1. Sets `monitoring_sessions[today][symbol].status = FAILED`
2. Writes a plain-English `failure_reason` string (user-visible, not a code)
3. Logs at `WARNING` level: `[Execution] Entry blocked for {symbol} — {reason}`

Common failure reasons:

| Source | Example message |
|---|---|
| `RiskManager` | `daily loss limit reached — no new entries until tomorrow` |
| `RiskManager` | `position size exceeds 10% of capital — reduced qty rejected` |
| `ExecutionRouter` | `order rejected by broker — outside regular trading hours` |
| `ExecutionRouter` | `fill confirmation timeout — position not confirmed` |
| Manual dismiss | `user dismissed signal — no entry attempted` |

Failed symbols re-enter `WATCHING` next morning if the screener still passes them —
the system does not permanently blacklist a symbol for a single-day failure.

---

### 9.7 Database Schema

**Database:** `~/.usswing/candles.db` (SQLite) — the single app database shared by all tools.

#### New tables — add to `schema.py`

```python
strategy_configs = sa.Table(
    "strategy_configs",
    metadata,
    sa.Column("strategy_id", sa.Text, primary_key=True),              # "boss_ema"
    sa.Column("mode",        sa.Text, nullable=False,
              server_default="disabled"),                              # "disabled"|"manual"|"auto"
    sa.Column("params_json", sa.Text, nullable=False,
              server_default="{}"),                                    # Pydantic Params.model_dump() JSON
    sa.Column("updated_at",  sa.Text, nullable=False),                # ISO-8601 UTC
)

strategy_config_history = sa.Table(
    "strategy_config_history",
    metadata,
    sa.Column("id",          sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("strategy_id", sa.Text, nullable=False),
    sa.Column("mode",        sa.Text, nullable=False),
    sa.Column("params_json", sa.Text, nullable=False),
    sa.Column("changed_at",  sa.Text, nullable=False),                # ISO-8601 UTC — append-only
)
```

#### Additive columns — existing tables (via `migrate_lifecycle_columns`)

```python
# positions: frozen strategy params at time of entry
("positions",          "strategy_params_snapshot", "TEXT"),

# monitoring_session: which strategy owns this row + why entry failed
("monitoring_session", "strategy_id",              "TEXT"),
("monitoring_session", "failure_reason",            "TEXT"),
```

Added through the same idempotent `ALTER TABLE` migration already in `schema.py` —
safe to run on every startup, no-op if columns already exist.

#### Full table picture after migration

```
candles.db
├── universe
├── users
├── watchlist
├── trades
├── positions                   + strategy_params_snapshot TEXT
├── monitoring_session          + strategy_id TEXT
│                               + failure_reason TEXT
├── price_1m / price_3m / price_15m / price_1d / price_1w
├── strategy_configs            ← NEW
└── strategy_config_history     ← NEW
```

---

## 10. File Layout After Implementation

```
us_swing/src/us_swing/
├── core/
│   └── strategies/
│       ├── __init__.py
│       ├── _protocol.py        ← StrategyProtocol, StrategySignal, TargetLevel
│       ├── _registry.py        ← StrategyRegistry singleton
│       └── built_in/
│           ├── __init__.py     ← imports all built-ins (triggers registration)
│           ├── boss_ema.py
│           ├── boss_adx.py
│           └── ema_crossover.py
└── execution/
    ├── strategy_engine.py      ← evaluation loop; routes entry/exit/hold/scale_in by mode
    ├── risk_manager.py         ← validate_signal(), calculate_position_size(),
    │                              can_enter_new(), can_scale_in(), max_concurrent check
    ├── execution_engine.py     ← submit_order(), close_position(), handle_order_fill()
    ├── position_tracker.py     ← update_stop(), update_target() for manual overrides
    ├── paper_engine.py
    └── execution_router.py     ← live vs paper switch; scale-in and partial-exit routing

us_swing/src/us_swing/gui/
├── settings_panel.py           ← _StrategiesTab (auto-renders from Params; mode-switch rules)
├── execution_panel.py          ← _SignalRow: +Dismiss [✕], +Keep Holding on EXIT rows
│                                  +_ScaleInProposalCard, +_PartialLiquidationCard
│                                  +_AutoExecutedPane
└── position_monitor.py         ← _PositionMonitorPane: live P&L table, editable stop/target,
                                   per-row Close button, Manual Entry form,
                                   Pre-Market Readiness Bar
```
