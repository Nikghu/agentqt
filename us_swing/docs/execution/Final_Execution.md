# Final Execution Refactor Plan — State Enum Consolidation

**Document ID:** PLAN-EXE-Final-Execution
**Version:** 1.0.0
**Status:** Draft
**Created:** 2026-05-28
**Owner:** EXE tool
**Author:** Claude (Sonnet 4.6) under user direction

> Authoritative refactor plan to consolidate strategy / trade / order / monitoring state machines into a single canonical enum container.  Each Phase below is sized to fit in one focused Sonnet session.  Phases are sequenced; do not skip ahead.

---

## 0. Context

Five overlapping state vocabularies exist today (see analysis in DEVLOG 2026-05-28).  This plan replaces them with **five clearly-scoped enums + one Action enum**, all grouped under a single container class `ExecutionEnums`.

### Why this matters
- `_CycleState` (engine) and `CYCLE_STATES` (ledger) collide on the word "cycle" but describe different things.
- `PositionState` (NEW/PARTIAL_ENTRY/OPEN/PARTIAL_EXIT/CLOSED) conflates BUY and SELL order progress on a single axis — partial-fill visibility on the Trade History side is lost.
- `strategy_signal.Status` is a free string (`"Inactive"/"Active"/"Running"`) with a documented contradiction between FO-EXE-011 §1 (force `Active` on load) and `strategy_builder_dialog.py:238` (trust verbatim).
- `LifecycleState` (monitoring_session) is correctly scoped but currently lives in `core/monitoring_session/_enums.py` rather than the unified execution-enum surface; it should be moved and made fully derivable from order events.

### Goal
A reader looking at any one line of execution code can answer **"what state is this referring to?"** with zero ambiguity.

---

## 1. Final Enum Design

### 1.1 Single container class

**File:** `us_swing/src/us_swing/execution/_enums.py`

```python
"""
Module: MD-EXE-XXX.001.M01 — execution/_enums.py
Parent SRD: SRD-EXE-013, SRD-EXE-014, updated SRD-EXE-009, SRD-EXE-011, SRD-EXE-012

Single source of truth for every execution-related state machine.
Import as: from us_swing.execution import ExecutionEnums as E
"""
from __future__ import annotations

from enum import StrEnum


class ExecutionEnums:
    """Container for every execution-domain state enum.

    Access pattern:
        from us_swing.execution import ExecutionEnums as E
        if cycle.state == E.TradeCycleState.OPEN: ...
    """

    class StrategyRunState(StrEnum):
        """Per-strategy lifecycle, persisted in strategy registry."""
        STOPPED      = "STOPPED"
        RUNNING      = "RUNNING"
        SQUARING_OFF = "SQUARING_OFF"

    class TradeCycleState(StrEnum):
        """Per Entry→Exit pair, persisted in trade_cycles.state."""
        OPENING = "OPENING"
        OPEN    = "OPEN"
        CLOSING = "CLOSING"
        CLOSED  = "CLOSED"
        ABORTED = "ABORTED"

    class BuyOrderState(StrEnum):
        """Per BUY order to broker, persisted in trades.order_state for side='BUY'."""
        NEW            = "NEW"
        PARTIAL_FILLED = "PARTIAL_FILLED"
        FILLED         = "FILLED"
        REJECTED       = "REJECTED"
        CANCELLED      = "CANCELLED"

    class SellOrderState(StrEnum):
        """Per SELL order to broker, persisted in trades.order_state for side='SELL'."""
        NEW            = "NEW"
        PARTIAL_FILLED = "PARTIAL_FILLED"
        FILLED         = "FILLED"
        REJECTED       = "REJECTED"
        CANCELLED      = "CANCELLED"

    class LifecycleState(StrEnum):
        """Per (session_date, symbol) audit row.  Internal — NOT shown in UI."""
        MONITORING = "MONITORING"
        ENTERED    = "ENTERED"
        SKIPPED    = "SKIPPED"
        EVICTED    = "EVICTED"
        EXITED     = "EXITED"

    class Action(StrEnum):
        """Direction of a TradeSignal emitted by the engine."""
        ENTRY = "entry"
        EXIT  = "exit"
```

### 1.2 Enums explicitly DELETED

| Old enum | Replaced by | Reason |
|---|---|---|
| `_CycleState` (engine) | (none — derived from `StrategyRunState` + cycle presence) | Redundant; engine derives evaluation behaviour |
| `PositionState` (data/models) | `BuyOrderState` + `SellOrderState` | Single axis split into two side-scoped axes |
| `CYCLE_STATES` frozenset | `ExecutionEnums.TradeCycleState` | Promote to typed StrEnum |
| `strategy_signal.Status` strings | `ExecutionEnums.StrategyRunState` | Replace free strings with enum |

### 1.3 Orthogonal enums kept as-is (NOT moved)

| Enum | Location | Reason kept separate |
|---|---|---|
| `TradingMode` (PAPER / LIVE) | `data/models.py` | Cross-cutting; not execution-state |
| `TradeOrigin` (system / manual) | `core/monitoring_session/_enums.py` | Cross-cutting; used by screener too |
| `Side` (BUY / SELL) | `core/monitoring_session/_enums.py` | Pure direction label |
| `ConnectionStatus` | `data/models.py` | IBKR infra, not execution-state |

---

## 2. Flow Charts

### 2.1 StrategyRunState — lifecycle

```
                                    ┌──────────────────────┐
                                    │ stop_strategy()      │
                                    │ (no open cycles)     │
                                    ▼                      │
                              ┌───────────┐                │
       create_strategy() ───▶│  STOPPED  │◀───────────────┤
                              └─────┬─────┘                │
                                    │                      │
                                    │ user clicks ▶ Play   │
                                    ▼                      │
                              ┌───────────┐                │
                              │  RUNNING  │                │
                              └─────┬─────┘                │
                                    │                      │
                                    │ user clicks ■        │
                                    │ AND open cycles      │
                                    │ exist OR end_time    │
                                    ▼                      │
                              ┌──────────────┐             │
                              │ SQUARING_OFF │             │
                              └──────┬───────┘             │
                                     │                     │
                                     │ all open cycles     │
                                     │ reach terminal      │
                                     └─────────────────────┘
```

**Persistence:** survives app restart.  Replaces the contradiction between FO-EXE-011 §1 ("force Active on load") and the strategy_builder_dialog "trust verbatim" — resolution: **trust verbatim**.

### 2.2 TradeCycleState — lifecycle

```
                  entry signal accepted by RiskManager
                  ▼
            ┌──────────┐                                  ┌──────────┐
            │ OPENING  │── BuyOrder REJECTED or ────────▶│ ABORTED  │ (terminal)
            └────┬─────┘    fill timeout                  └──────────┘
                 │
                 │ BuyOrder reaches FILLED
                 ▼
            ┌──────────┐
            │   OPEN   │── live PnL, trail stop, etc.
            └────┬─────┘
                 │
                 │ any exit trigger:
                 │ strategy / hard_sl / target / trailing_sl /
                 │ end_time / manual / emergency
                 ▼
            ┌──────────┐
            │ CLOSING  │── SellOrder REJECTED ──▶ back to OPEN
            └────┬─────┘
                 │
                 │ SellOrder reaches FILLED
                 ▼
            ┌──────────┐
            │  CLOSED  │ (terminal — realized PnL frozen)
            └──────────┘
```

### 2.3 BuyOrderState — broker-side state machine

```
   submit BUY to broker
   ▼
┌──────┐    partial fill arrives    ┌────────────────┐
│ NEW  │───────────────────────────▶│ PARTIAL_FILLED │
└──┬───┘                            └────────┬───────┘
   │                                         │
   │ broker rejects                          │ remaining qty fills
   │ ◀─── (no fills yet)                     │
   │                                         ▼
   │                                  ┌──────────┐
   │                                  │  FILLED  │ (terminal — all qty filled)
   │                                  └──────────┘
   │
   ├────▶ ┌──────────┐
   │      │ REJECTED │ (terminal — broker rejected order, qty filled = 0)
   │      └──────────┘
   │
   └────▶ ┌───────────┐
          │ CANCELLED │ (terminal — user / system cancelled; qty filled may be > 0)
          └───────────┘
```

**Note:** `CANCELLED` after a partial fill means *some* shares were bought; the position has that partial qty but the order itself is terminal.

### 2.4 SellOrderState — broker-side state machine

Identical shape to BuyOrderState — same five states, same transitions.  Lives in the same `trades` row but with `side='SELL'`.

### 2.5 LifecycleState (monitoring_session) — driven by order events

```
                                    Screener picks symbol on session_date D
                                    ▼
                              ┌──────────────┐
                              │  MONITORING  │
                              └──────┬───────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
       first system BUY        end of day               reconciler runs
       reaches FILLED          never entered            next morning, symbol
       (BuyOrderState.FILLED   (or PARTIAL_FILLED       not in keep_set
        or PARTIAL_FILLED      with qty > 0)
        with qty > 0)
              │                      │                      │
              ▼                      ▼                      ▼
       ┌──────────┐            ┌──────────┐          ┌──────────┐
       │ ENTERED  │            │ SKIPPED  │─────────▶│ EVICTED  │
       └────┬─────┘            └──────────┘          └──────────┘
            │                                          (candles
            │  SellOrder closing the position           hard-deleted)
            │  reaches FILLED (position qty → 0)
            ▼
       ┌──────────┐
       │  EXITED  │
       └──────────┘
```

**Key change vs current model:** LifecycleState transitions are now triggered exclusively by `BuyOrderState`/`SellOrderState` events through the existing `MonitoringCommand.on_fill()` hook — no separate state logic.  The enum is internal; not shown in any user-visible panel.

### 2.6 Full end-to-end 3-day scenario

```
┌──────────────┬──────────────────────────────────────────────────────────────────────────────────┐
│   Event      │ StrategyRun   TradeCycle   BuyOrder      SellOrder    Lifecycle    UI surface     │
├──────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ DAY 1 09:00                                                                                       │
│ User ▶ Play  │ STOPPED       ─            ─            ─            ─            Strategy Exec:  │
│              │ → RUNNING                                                          "RUNNING"      │
│                                                                                                   │
│ 09:15 screener picks AAPL                                                                         │
│              │ RUNNING       ─            ─            ─            MONITORING   (no Active row) │
│                                                                                                   │
│ Bar closes, RSI=45 — no entry condition met                                                       │
│              │ RUNNING       ─            ─            ─            MONITORING   (no change)     │
│                                                                                                   │
│ DAY 1 16:00 EOD                                                                                   │
├──────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ DAY 2 09:15 screener picks AAPL again                                                             │
│              │ RUNNING       ─            ─            ─            +MONITORING  (audit only)    │
│                                                                                  (Day2 row)      │
│                                                                                                   │
│ 10:42 RSI=27 fires — signal emitted (Manual mode → PendingSignalStore)                           │
│              │ RUNNING       ─            ─            ─            MONITORING   Active Trades:  │
│                                                                                  PENDING AAPL    │
│                                                                                                   │
│ 10:42:30 user clicks ▶ Execute                                                                    │
│              │ RUNNING       OPENING      NEW          ─            MONITORING   Active Trades:  │
│              │                (cycle #42)  (order #871)                            OPENING        │
│              │                                                                    Trade History:  │
│              │                                                                    NEW BUY row     │
│                                                                                                   │
│ 10:42:31 IBKR partial-fills 50/100                                                                │
│              │ RUNNING       OPENING      PARTIAL_     ─            MONITORING   Active Trades:  │
│              │                            FILLED                                   OPENING        │
│              │                                                                    Trade History:  │
│              │                                                                    PARTIAL_FILLED  │
│                                                                                                   │
│ 10:42:33 IBKR fills remaining 50                                                                  │
│              │ RUNNING       OPEN         FILLED       ─            ENTERED      Active Trades:  │
│              │                                                       (Day2 AAPL)   OPEN           │
│              │                                                                    Trade History:  │
│              │                                                                    FILLED          │
│                                                                                                   │
│ 12:00-16:00 ticks (live PnL, trailing stop moves)                                                 │
│              │ RUNNING       OPEN         FILLED       ─            ENTERED      Active Trades:  │
│              │                                                                    LTP/PnL update  │
├──────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ DAY 3 11:30 tick hits trailing stop                                                               │
│              │ RUNNING       CLOSING      FILLED       NEW          ENTERED      Active Trades:  │
│              │                                         (order #893)                CLOSING        │
│              │                                                                    Trade History:  │
│              │                                                                    NEW SELL row    │
│                                                                                                   │
│ 11:30:02 SELL partial-fills 40/100                                                                │
│              │ RUNNING       CLOSING      FILLED       PARTIAL_     ENTERED      Active Trades:  │
│              │                                         FILLED                      CLOSING        │
│              │                                                                    Trade History:  │
│              │                                                                    PARTIAL_FILLED  │
│                                                                                                   │
│ 11:30:04 SELL fills remaining 60                                                                  │
│              │ RUNNING       CLOSED       FILLED       FILLED       EXITED       Active Trades:  │
│              │                (terminal)                              (Day2 AAPL)  row removed    │
│              │                                                                    Trade History:  │
│              │                                                                    BUY + SELL both │
│              │                                                                    FILLED          │
│                                                                                                   │
│ User clicks ■ Stop                                                                                │
│              │ RUNNING       (no open    ─            ─            EXITED       Strategy Exec:  │
│              │ → STOPPED      cycles)                                              "STOPPED"      │
└──────────────┴──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. State Relationship Matrix

Which enums are correlated, which are independent?

| ↓ depends on / triggers → | StrategyRun | TradeCycle | BuyOrder | SellOrder | Lifecycle |
|---|---|---|---|---|---|
| **StrategyRun** | — | RUNNING required to create new cycles | — | — | — |
| **TradeCycle** | — | — | OPENING→OPEN driven by BuyOrder→FILLED | CLOSING→CLOSED driven by SellOrder→FILLED | ENTERED triggered by first BUY fill |
| **BuyOrder** | — | — | — | — | first FILLED with qty>0 → MONITORING→ENTERED |
| **SellOrder** | — | — | — | — | FILLED that brings position qty→0 → ENTERED→EXITED |
| **Lifecycle** | — | — | — | — | — |

**Read:** "A row depends on / is triggered by the column".  Empty cells mean *independent*.

---

## 4. Refactor Sequence (5 Phases)

> **Rule:** complete each phase fully (requirements → DB → code → GUI → tests) before starting the next.  No phase skipping; no merging phases.

| Phase | Title | Estimated Sessions | Risk |
|---|---|---|---|
| **Phase 0** | Foundation — `ExecutionEnums` container | 1 | Low |
| **Phase 1** | StrategyRunState rollout | 2 | High (drops `_CycleState`, touches engine) |
| **Phase 2** | TradeCycleState promotion | 1 | Low |
| **Phase 3** | BuyOrderState / SellOrderState split | 2 | Medium (DB schema change) |
| **Phase 4** | LifecycleState internalisation | 1 | Low |

**Total:** ~7 Sonnet sessions to land safely.

Within each Phase the substeps follow the **fixed order**:

```
1. Requirements (FO / SRD / DD / MD edits)
2. Database (schema + migration)
3. Code (engine, services, repositories)
4. GUI (panels, models, widgets)
5. Tests (UTCD pass + integration)
```

---

## 5. Per-Phase Detail

### Phase 0 — Foundation

**Goal:** create `ExecutionEnums` as a parallel surface; old enums remain.  Pure additive.

#### 5.0.1 Files to create
| File | Purpose |
|---|---|
| `us_swing/src/us_swing/execution/_enums.py` | The container class (see §1.1) |
| `us_swing/tests/execution/test_enums.py` | Trivial value/name assertions |

#### 5.0.2 Files to edit
| File | Edit |
|---|---|
| `us_swing/src/us_swing/execution/__init__.py` | Export `ExecutionEnums` |

#### 5.0.3 Acceptance
- `from us_swing.execution import ExecutionEnums as E` works
- `E.TradeCycleState.OPEN == "OPEN"` (StrEnum equality)
- Old enums (`_CycleState`, `CYCLE_STATES`, `PositionState`, `LifecycleState` in core) **still importable and unchanged**
- `ruff` + `mypy --strict` clean
- No production code yet uses the new container

#### 5.0.4 Out of scope
- Any deletion
- Any migration

---

### Phase 1 — StrategyRunState rollout

**Goal:** introduce `StrategyRunState` as the only strategy-runtime vocabulary.  Drop `_CycleState`.  Engine derives evaluation behaviour from `(StrategyRunState, has_open_cycle)`.

#### 5.1.1 Requirements
| Artifact | Action |
|---|---|
| `docs/execution/FO.md` | Add **FO-EXE-013: Strategy Run Lifecycle** (Status=Draft) |
| `docs/execution/SRD.md` | Add SRD rows under FO-EXE-013 (Draft) |
| `docs/execution/SRD.md` | Mark SRD-EXE-011.001 as **Reopen** — paragraph "force `strategy_signal.Status = Active`" is removed; persistence is trusted verbatim |
| `docs/execution/DD.md` | Document the engine evaluation-decision derivation |
| `docs/execution/MD.md` | Update MD rows that referenced `_CycleState` |

**FO-EXE-013 acceptance criteria draft:**
1. Pressing ▶ Play on a STOPPED strategy persists `run_state = RUNNING`; survives restart.
2. Pressing ■ Stop with no open cycles transitions RUNNING → STOPPED immediately.
3. Pressing ■ Stop with one or more open cycles transitions RUNNING → SQUARING_OFF; the engine emits forced EXIT signals for every Running pair; on last cycle reaching terminal (CLOSED / ABORTED), state auto-transitions to STOPPED.
4. Strategy in STOPPED produces zero `TradeSignal` events regardless of candle close / tick events.
5. Strategy in RUNNING evaluates entry condition only when no open cycle exists for `(strategy_id, symbol)`.
6. Strategy in RUNNING with an open cycle for `(strategy_id, symbol)` in `TradeCycleState.OPEN` evaluates exit condition only.
7. Strategy in SQUARING_OFF emits no new ENTRY signals (only forced EXITs).

#### 5.1.2 Database
| Table | Change |
|---|---|
| `strategies.json` (file-backed registry) | Replace `strategy_signal.Status` (free string) with `run_state` (StrategyRunState value).  Migration: on first load, map `"Inactive"→STOPPED`, `"Active"/"Running"→RUNNING`. |

> Decision point: keep file-backed registry or migrate to SQLite?  **Plan recommendation:** stay file-backed for Phase 1 to limit blast radius; SQLite migration is a separate task.

#### 5.1.3 Code
| File | Change |
|---|---|
| `gui/strategy_builder_dialog.py` | Replace `strategy_signal` dict with typed dataclass holding `run_state: ExecutionEnums.StrategyRunState`.  Load mapping per migration above. |
| `execution/strategy_engine/_context.py` | **Delete `_CycleState`**.  `_StrategyContext` no longer holds a `cycles: dict[str, _CycleState]` field. |
| `execution/strategy_engine/_engine.py` | Replace per-symbol state checks with: `if strategy.run_state != RUNNING: skip; if cycle_query.has_open_cycle(strategy_id, symbol): evaluate exit; else: evaluate entry`. |
| `execution/strategy_engine/__init__.py` | Drop `_CycleState` export |
| Any test importing `_CycleState` | Migrate to the new derivation |

#### 5.1.4 GUI
| File | Change |
|---|---|
| `gui/execution_panel.py` (or wherever Play/Stop lives) | Wire ▶/■ buttons to a `set_run_state()` call; show badge bound to `StrategyRunState` |
| `gui/strategy_table_model.py` | Replace "Status" column source with `run_state` |

#### 5.1.5 Acceptance
- Removing `_CycleState` does not regress any UTCD-EXE-011 test
- Restart with one `RUNNING` strategy preserves state
- Pressing Stop with an OPEN cycle correctly triggers SQUARING_OFF then STOPPED

---

### Phase 2 — TradeCycleState promotion

**Goal:** replace the `CYCLE_STATES` frozenset and free-string `state` columns with `ExecutionEnums.TradeCycleState`.  Same wire values; type-safe.

#### 5.2.1 Requirements
| Artifact | Action |
|---|---|
| `docs/execution/SRD.md` | Mark SRD-EXE-012.010/.011 as **Reopen** — DTO field type changes from `str` to `TradeCycleState` |
| `docs/execution/DD.md` | Note: TradeCycle is the **trader-facing** state — the only one in the Active Trades badge |

#### 5.2.2 Database
No schema change.  Stored values stay the same strings (`"OPENING"`, `"OPEN"`, ...).

#### 5.2.3 Code
| File | Change |
|---|---|
| `execution/trade_cycle/_dto.py` | Delete the `CYCLE_STATES` frozenset, `NON_TERMINAL_STATES`, `TERMINAL_STATES`; replace with `ExecutionEnums.TradeCycleState` and helper classmethods (`is_terminal()`, `is_non_terminal()`) |
| `execution/trade_cycle/_dto.py` | `CycleSnapshot.state: str` → `state: ExecutionEnums.TradeCycleState` |
| `execution/trade_cycle/_repository.py` | Use enum in queries / inserts (StrEnum auto-converts) |
| `execution/trade_cycle/_service.py` | Replace string comparisons with enum members |
| `gui/active_cycles_model.py` | The `_STATE_BG` dict already keys by string; keep — StrEnum compares equal to its string value.  Add explicit imports for clarity. |

#### 5.2.4 GUI
No visual change.  Active Trades panel keeps its existing badge rendering.

#### 5.2.5 Acceptance
- All existing UTCD-EXE-012 tests pass unchanged
- New negative test: passing an unknown string to `CycleSnapshot.state` raises immediately (type-check)

---

### Phase 3 — BuyOrderState / SellOrderState split

**Goal:** delete `PositionState`.  Track broker-order state on the `trades` table per side; Trade History panel shows order state instead of derived position state.  No PnL on Trade History.

#### 5.3.1 Requirements
| Artifact | Action |
|---|---|
| `docs/execution/FO.md` | Add **FO-EXE-014: Broker Order State Machine** (Draft) |
| `docs/execution/SRD.md` | Add SRD rows under FO-EXE-014 |
| `docs/execution/SRD.md` | Mark SRD-EXE-005 as **Reopen** — `PositionState` is removed; position tracking becomes "net qty > 0 = open" |
| `docs/gui/FO.md` | Update **FO-GUI-014** Trade History column list — drop PnL column, add OrderState column |
| `docs/gui/SRD.md` | Update SRDs to match |

**FO-EXE-014 acceptance criteria draft:**
1. Submitting a BUY to the broker creates one `trades` row with `side='BUY'`, `order_state='NEW'`.
2. Each broker fill event updates the same row: `NEW → PARTIAL_FILLED → FILLED`.
3. Broker rejection → `order_state='REJECTED'`; broker cancel → `order_state='CANCELLED'`.
4. SELL orders follow the identical state machine, with `side='SELL'`.
5. Trade History panel shows one row per BUY or SELL with: `Time | Symbol | Side | Qty | Filled | Avg Price | OrderState | Mode`.  **No P&L column.**

#### 5.3.2 Database
| Table | Change |
|---|---|
| `trades` | Drop `status` text column (or rename) and add `order_state` TEXT NOT NULL DEFAULT 'NEW' constrained to `BuyOrderState`/`SellOrderState` values |
| `trades` | Add `filled_quantity INTEGER NOT NULL DEFAULT 0` |
| `trades` | Drop `pnl` column from the panel surface (still in `trade_cycles.realized_pnl_usd`) |
| `positions` | Drop `state` text column (now derivable: `state = 'OPEN' if quantity > 0 else 'CLOSED'`) |
| Migration | Idempotent PRAGMA + ALTER TABLE in `migrate_lifecycle_columns()` |

> **Backfill rule:** existing `trades.status` values map: `"SUBMITTED"→NEW`, `"FILLED"→FILLED`, `"CLOSED"→FILLED`.  Existing `positions.state="CLOSED"` rows can be left untouched (column dropped after backfill verification).

#### 5.3.3 Code
| File | Change |
|---|---|
| `data/models.py` | **Delete `PositionState`**.  `PositionRecord.state` field removed.  Add `filled_quantity` to `TradeRecord`; add `order_state: BuyOrderState \| SellOrderState`. |
| `execution/paper_engine.py` | Replace `status="FILLED"` with `order_state=BuyOrderState.FILLED` etc.  Emit partial-fill updates if simulating multi-step fills. |
| `execution/execution_engine.py` | On every broker fill event, update the right `order_state` and `filled_quantity` on the matching `trades` row |
| `execution/trade_cycle/_service.py` | OPENING→OPEN transition keyed on `BuyOrderState.FILLED` (or PARTIAL_FILLED with qty>0 if you want eager open).  Plan default: **strict — wait for FILLED.** |
| `core/monitoring_session/_service.py` | `on_fill` consumes `(side, order_state)` to drive `LifecycleState` transitions |
| `gui/app_service.py:1909,2009` | Remove the duplicate write path — `trade_cycles` is canonical for PnL; `trades` is canonical for order state |

#### 5.3.4 GUI
| File | Change |
|---|---|
| `gui/position_table_model.py::TradeHistoryModel` | Replace columns: `_BASE_COLS = ["Date & Time", "Symbol", "Side", "Qty", "Filled", "Avg Price", "Order State", "Strategy", "Mode"]`.  **Remove `P&L`.** |
| `gui/dashboard_panel.py` | Update Trade History tab to bind to new model columns |
| (verify) `gui/active_cycles_panel.py` | No change — Active Trades panel was already using TradeCycleState, not PositionState |

#### 5.3.5 Acceptance
- BUY order rejected by broker → `trades.order_state='REJECTED'`, cycle moves OPENING→ABORTED
- BUY order partial-fill (50/100) then full-fill → two `trades.order_state` UPDATE events visible in Trade History
- SELL cancelled after partial fill → `trades.order_state='CANCELLED'`, `filled_quantity=40`; cycle still OPEN with qty=60 remaining
- Trade History panel renders no PnL column

---

### Phase 4 — LifecycleState internalisation

**Goal:** move `LifecycleState` into `ExecutionEnums` (single source of truth); verify it's invisible to all user-facing panels; ensure every transition is triggered by a `BuyOrderState`/`SellOrderState` event, not by separate logic paths.

#### 5.4.1 Requirements
| Artifact | Action |
|---|---|
| `docs/execution/SRD.md` | Reopen SRD-EXE-009.012 — LifecycleState moves into `ExecutionEnums`; rules unchanged |

#### 5.4.2 Database
No change.

#### 5.4.3 Code
| File | Change |
|---|---|
| `execution/_enums.py` | Already added in Phase 0 |
| `core/monitoring_session/_enums.py` | Delete `LifecycleState`; re-export from `us_swing.execution import ExecutionEnums` for backwards compat OR update all importers (preferred) |
| `core/monitoring_session/_service.py` | Verify every transition is invoked through `on_fill(side, order_state, qty)` and not through any other entry point |
| Any importer of `core.monitoring_session._enums.LifecycleState` | Migrate to `ExecutionEnums.LifecycleState` |

#### 5.4.4 GUI
**Audit only** — confirm no panel imports `LifecycleState` for display.  (Pre-audit shows none — this phase is just verification + the import move.)

#### 5.4.5 Acceptance
- `LifecycleState.ENTERED` always co-occurs with a `BuyOrderState` event in the same `on_fill()` call (asserted in integration test)
- Greps confirm no GUI module imports `LifecycleState`
- Old import path `from us_swing.core.monitoring_session import LifecycleState` either works through re-export or is fully removed

---

## 6. Cross-Cutting Rules

### 6.1 Coding style (apply to every Phase)
- Every state-checking function: ≤ 8 lines.  If longer, split.
- Every enum comparison uses the enum member, never the bare string.  Bad: `if state == "OPEN":`  Good: `if state == E.TradeCycleState.OPEN:`
- Every public function touching state takes / returns the typed enum, never `str`.
- One concept per file.  `_enums.py` holds enums only; no helpers.
- `__slots__` on every dataclass in `trade_cycle/_dto.py`.
- No comments restating obvious code.  Comments only for non-obvious invariants.

### 6.2 Backwards compatibility during phases
Between phases the old enums remain importable.  Each Phase's "delete" step is the LAST thing in that Phase — landed only after all callers migrated.

### 6.3 Test strategy
- Phase 0: pure unit test on `_enums.py`
- Phase 1: integration test for Play / Stop / SquaringOff round-trip with one open cycle
- Phase 2: existing UTCD-EXE-012 suite must pass unchanged
- Phase 3: new UTCD entries for `BuyOrderState` / `SellOrderState` state machines (NEW→PARTIAL_FILLED→FILLED, NEW→REJECTED, PARTIAL_FILLED→CANCELLED)
- Phase 4: invariant test — `LifecycleState.ENTERED` count == open system position count

### 6.4 Commit convention per Phase
One commit per substep (req → DB → code → GUI → tests).  Final commit per Phase: `feat(EXE): Phase N — <title>`.

### 6.5 Documentation per Phase
At the end of each Phase, write a Revision Note: `docs/execution/revisions/RN-EXE-X.Y.Z-YYYYMMDD.md`.

---

## 7. Decision Log

| # | Decision | Rationale | Date |
|---|---|---|---|
| 1 | Split `PositionState` into `BuyOrderState` + `SellOrderState` | User requirement; Trade History needs per-side broker-order visibility | 2026-05-28 |
| 2 | Drop `_CycleState` entirely (not just rename) | Engine can derive behaviour from `(StrategyRunState, has_open_cycle)` | 2026-05-28 |
| 3 | Resolve FO-EXE-011 §1 contradiction in favour of "trust persisted state" | Matches user's mental model of "press Play, strategy runs across days" | 2026-05-28 |
| 4 | `LifecycleState` stays internal — no UI surface | User said TradeCycle state is sufficient for the trader; LifecycleState is audit | 2026-05-28 |
| 5 | All enums in one container class `ExecutionEnums` | User explicit ask — one canonical surface | 2026-05-28 |
| 6 | Phase order: req → DB → code → GUI | User explicit ask — fix root first | 2026-05-28 |
| 7 | Trade History panel removes PnL column | User explicit ask — order-state only, PnL lives in TradeCycle / Dashboard KPIs | 2026-05-28 |
| 8 | File-backed strategy registry stays file-backed for Phase 1 | Limit blast radius; SQLite migration is a separate future task | 2026-05-28 |

---

## 8. How to use this plan in a Sonnet session

When starting a new session, paste:
```
Continue Final_Execution.md — start Phase N.
Read us_swing/docs/execution/Final_Execution.md §5.N before doing anything.
```

The agent will follow the substep order (requirements → DB → code → GUI → tests) and produce one commit per substep.

---

**End of plan.**
