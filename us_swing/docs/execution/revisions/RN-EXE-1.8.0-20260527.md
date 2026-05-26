# Revision Note — RN-EXE-1.8.0-20260527

**Version:** 1.8.0
**Date:** 2026-05-27
**Tool:** EXE (Execution & Risk Management)
**Artifact:** FO-EXE-011, FO-EXE-012 / SRD-EXE-011.001–015, SRD-EXE-012.001–013
**Type:** Refactor + Bugfix

---

## Summary

Strategy execution layer redesigned to persist and manage the complete strategy lifecycle across sessions. Added cadence-driven tick loop to `StrategyEngine` that wakes every second to evaluate strategies independently of bar-close events. Integrated with the pre-existing `TradeCycleService` (FO-EXE-012) to persist entry→exit cycles as the single source of truth for active positions and live PnL tracking. Fixed critical bugs from manual-mode testing: stopped strategies resetting on restart, improved state persistence model to keep strategies armed until explicit Stop, and added Force Exit action to prevent stalled positions. Execution Settings UI (`minute_close`, `execution_rate_sec`, `rex_count`) ported from legacy reference implementation to `StrategyConfig` in GUI dialog.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-011.001.M01 | `execution/strategy_engine/_engine.py` | Added `last_eval_at: datetime \| None` to `_StrategyContext`; added `_strategy_tick_loop()` coroutine, `_evaluate_ctx()`, `_is_time_to_evaluate()` methods; wired cadence-driven evaluation independent of bar-close; added `stop_requested()` public method to `_Router` |
| MD-EXE-011.001.M02 | `execution/strategy_engine/_context.py` | Extended `_StrategyContext` to track last-evaluation timestamp for cadence gate |
| MD-EXE-011.001.M04 | `execution/strategy_engine/_router.py` | Added `stop_requested()` method; attached `bar.close` to exit signals for accurate fill-price logging in PaperBroker |
| MD-GUI-004.001.M01 | `gui/strategy_builder_dialog.py` | Added "EXECUTION SETTINGS" section with three QSpinBoxes: `minute_close`, `execution_rate_sec`, `rex_count`; connected to `StrategyConfig` fields; fixed `_on_edit._on_saved` to call `reload_strategy_registry()` |
| MD-GUI-004.001.M01 | `gui/execution_panel.py` | Replaced `_SignalRow` card layout with unified `QTableView` backed by `PendingSignalsTableModel`; added per-row Execute and Force Exit buttons; exited-today rows persist until next-day pre-open cleanup |
| MD-GUI-004.001.M01 | `gui/app_service.py` | Eagerly built shared `_db_engine` + `_lifecycle_bus` on boot; instantiated `TradeCycleService`, rehydrated `_positions` + `_trades` from trade-cycle ledger; added `get_latest_close()`, `force_exit_position()`, `get_active_strategy_positions()`, `get_recent_closed_cycles()` helper methods; connected `reload_strategy_registry()` callback from execution panel |
| MD-EXE-011.001.M04 | `gui/strategy_table_model.py` | Added `running_override: set[str]` to show "Running" badge when open cycles exist regardless of `Status` config; added `get_strategies_with_open_cycles()`, `get_open_symbols_for_strategy(name)` queries |
| — | `gui/pending_signals_table_model.py` | **New file.** `PendingSignalsTableModel(QAbstractTableModel)` with KIND enum (PENDING_ENTRY, PENDING_EXIT, RUNNING, EXITED); 7-column table (Symbol, Strategy, Type, Price, Quantity, PnL, Time); row-selection context-menu actions |

---

## Strategy State Persistence Model (Clarified)

The following changes fix the "entry fires again on restart" bug and establish strategies as persistent across sessions:

- **Status field is the runtime arming flag.** `Status ∈ {Active, Inactive, Running}` determines whether the engine evaluates a strategy; `Inactive` blocks all signals.
- **Status value is not reset on startup.** Saved `Status` from the prior session is the source of truth; the engine does not auto-promote to `Running` on restart.
- **New strategies default to `Status = Active` if mode==auto, `Inactive` if mode==manual.** This is set once at creation time.
- **Mode field is never touched by Play/Stop buttons.** Only `Status` changes; `Mode` stays as configured in the dialog.
- **Stop button is gated by open-position check.** If any cycles are open (`TradeCycleService.open_cycles(strategy_id, symbol)`), a `QMessageBox.warning` is shown and the Stop is refused. User must Force Exit manually first.
- **`running_override` visual fallback:** If `Status == Inactive` but open cycles exist for the strategy, the badge shows "Running" to signal to the user that action is needed.

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-011.001 | Registry load on startup, Status forced Active | Implemented |
| SRD-EXE-011.002–003 | Bar-close trigger, symbol-scope filter | Implemented |
| SRD-EXE-011.004–007 | Schedule guard, expression evaluator, signal emission, mode routing | Implemented |
| SRD-EXE-011.008–010 | No pyramiding, capital cap, end-time SquareOff | Implemented |
| SRD-EXE-011.011–013 | Emergency stop, Status persistence, GUI isolation | Implemented |
| SRD-EXE-011.014 | Concurrency safety | Implemented |
| SRD-EXE-011.015 | Cadence-driven evaluation (NEW — re-evaluation via 1s tick loop) | Implemented |
| SRD-EXE-012.001–013 | Trade cycle ledger schema, lifecycle, persistence | Implemented |

---

## Design Decisions

- **Trade Cycle Service as source of truth:** FO-EXE-012 `trade_cycles` table replaces ad-hoc position tracking; every entry→exit cycle is persisted and live-updated on each tick from `LiveTickWorker`.
- **Cadence gate in engine loop:** 1-second wake cycle with `last_eval_at` timestamp gates re-evaluation per strategy to avoid re-triggering on every candle-close event when the same candle is re-broadcast.
- **Strategy lifecycle is session-independent:** Strategies persist across application restarts with their prior `Status` preserved; only explicit Stop (with position verification) deactivates.
- **Single-flight reconciliation:** Pre-open DB reconciliation (FO-EXE-010) runs once per day, ensuring evicted symbols do not interfere with the live feed or strategy evaluation.
- **GUI bridges events, core is headless:** `core/monitoring_session/` and `execution/trade_cycle/` use Protocol-typed services and sealed event unions; GUI wires `PyQt6` signals at the boundary only.

---

## Issues Resolved

- **Bug: Entry fired again on restart** — Root cause: `load_strategies()` reset `Status` to `"Running"` on every startup, causing previously-exited entries to re-trigger. **Fix:** Load saved `Status` as-is; do not auto-promote.
- **Bug: Cannot stop strategy with open positions** — Root cause: Stop button had no guard. **Fix:** Check `TradeCycleService.open_cycles(strategy_id)` before allowing Stop; show warning if cycles are open.
- **Bug: Stalled positions prevented next entry** — Root cause: Duplicate-open-cycle check in engine was insufficient. **Fix:** `TradeCycleService` enforces exactly one open cycle per `(strategy_id, symbol)` pair.

---

## Test Coverage

FO-EXE-011 unit tests (38 cases across 3 modules, all passing as of Session 50):
- `UT-EXE-011.001.M01.T01–T13` — StrategyEngine tick loop, cadence gate, state transitions
- `UT-EXE-011.001.M02.T01–T09` — StrategyContext lifecycle, last-eval tracking
- `UT-EXE-011.001.M03.T01–T16` — Expression evaluator, condition parsing, operator precedence

FO-EXE-012 unit tests (29 cases across 6 modules, all passing as of Session 50):
- `UT-EXE-012.001.M01–M06.T01–T29` — Trade cycle schema, open/close/abort states, tick update throttling, risk enforcement, persistence

Integration tests (5 scenarios, all passing):
- Monitoring session + trade cycle end-to-end (entry → live updates → exit)
- Duplicate-filter case (symbol re-emitted while already held)
- Pre-open reconciliation eviction with carryover position retention

---

## Cross-Tool Impact

**GUI (FO-GUI-004, FO-GUI-013, FO-GUI-014):**
- Strategy Builder dialog: Added "EXECUTION SETTINGS" section with 3 new fields
- Execution Panel: Replaced card-based pending signals with unified table model
- Strategy Table: Added `running_override` visual badge for clarity when positions are open but strategy Status is Inactive
- Active Cycles Panel: New rows for each open trade cycle (FO-GUI-014)

**Infrastructure (FO-INF, cross-tool):**
- `TradeCycleService` (FO-EXE-012) now instantiated at `AppService` boot
- `MonitoringSessionService` (FO-EXE-009) rehydrated from ledger on startup
- Shared event bus routes all lifecycle and trade-cycle events

---

## Notes

- **`rex_count` enforcement is NOT in scope.** Field is captured in `StrategyConfig` but engine does not gate on it. No entry counter, no reset action, no per-cycle limit check. Enforcement deferred to the next session (see `MEMORY.md` for `feature_rex_count_enforcement.md` breakdown).
- **Migration to `TradeCycleService`:** Legacy `strategy_cycle_store.py` was deleted and its schema replaced by the richer FO-EXE-012 schema. All cycle state now flows through `TradeCycleService.on_entry_fill()` / `on_exit_fill()` / `on_tick_update()` interfaces.
- **Status persistence via registry write:** Every state transition in `StrategyEngine._evaluate_ctx()` calls `strategy_registry.update_status(strategy_id, status, metadata)` so the GUI Status badge updates without polling.

---
