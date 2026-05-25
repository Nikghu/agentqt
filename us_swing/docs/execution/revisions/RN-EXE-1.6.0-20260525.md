# Revision Note — RN-EXE-1.6.0-20260525

**Version:** 1.6.0
**Date:** 2026-05-25
**Tool:** EXE
**Artifact:** FO-EXE-011, FO-EXE-012 / SRD-EXE-011.001–015, SRD-EXE-012.001–013
**Type:** Feature

---

## Summary

Completed comprehensive pytest test suite for FO-EXE-011 (Strategy Engine) and FO-EXE-012 (Trade Cycle Ledger). **38 tests for Strategy Engine** across 5 modules covering concurrent evaluation, mode routing, state machine transitions, and signal dispatch. **29 tests for Trade Cycle Ledger** across 3 modules covering lifecycle state machine, tick/bar updates, risk parameter mutations, and persistence. Fixed multi-threaded SQLite issue in test harness. All 67 tests pass; coverage verified.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-011.001.M01 | `us_swing/tests/execution/test_strategy_engine.py` | 12 tests covering _StrategyEngine class: registry load, bar-close trigger, symbol-scope filter, concurrent evaluation |
| MD-EXE-011.001.M02 | `us_swing/tests/execution/test_strategy_context.py` | 8 tests covering _StrategyContext: state machine (Inactive/Active/UnderEntry/Running/UnderExit/SquareOff) transitions |
| MD-EXE-011.001.M03 | `us_swing/tests/execution/test_strategy_evaluator.py` | 9 tests covering ConditionEvaluator: expression parsing, comparison operators, logical AND/OR, parentheses, indicator function calls |
| MD-EXE-011.001.M04 | `us_swing/tests/execution/test_strategy_router.py` | 5 tests covering signal queue consumer dispatch by (Mode, auto_trade) pair: Auto+True → ExecutionRouter, Manual/* → pending store |
| MD-EXE-011.001.M05 | `us_swing/tests/execution/test_strategy_events.py` | 4 tests covering StrategyEvent sealed union and event bus subscription |
| MD-EXE-012.001.M01 | `us_swing/tests/execution/test_trade_cycle_schema_dto.py` | 10 tests covering TradeCycleRow dataclass, state machine enum, DTO immutability and schema_version field |
| MD-EXE-012.002.M01 | `us_swing/tests/execution/test_trade_cycle_repository.py` | 7 tests covering lifecycle and DB persistence: insert_cycle, update_cycle_state, tick_update throttle, exit trigger evaluation |
| MD-EXE-012.002.M02 | `us_swing/tests/execution/test_trade_cycle_service.py` | 12 tests covering on_entry_fill, on_exit_fill, on_entry_failed, update_risk, event publishing (fixed multi-threaded SQLite StaticPool + check_same_thread=False) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-011.001 | Registry load, initial state force to Active | Implemented |
| SRD-EXE-011.002 | Bar-close trigger and symbol-scope filter evaluation | Implemented |
| SRD-EXE-011.003 | Schedule guard time/date/weekday validation | Implemented |
| SRD-EXE-011.004 | ConditionEvaluator expression parsing and operator precedence | Implemented |
| SRD-EXE-011.005 | Entry signal emission and UnderEntry state transition | Implemented |
| SRD-EXE-011.006 | Exit signal emission and UnderExit state transition | Implemented |
| SRD-EXE-011.007 | No-pyramiding check: second entry dropped if already in UnderEntry/Running/UnderExit | Implemented |
| SRD-EXE-011.008 | Capital cap check via RiskManager.can_allocate() | Implemented |
| SRD-EXE-011.009 | End-time SquareOff for Intraday strategies with running positions | Implemented |
| SRD-EXE-011.010 | Emergency stop enqueuing EXIT for all Running symbols | Implemented |
| SRD-EXE-011.011 | Status persistence to registry strategy_signal block | Implemented |
| SRD-EXE-011.012 | Per-(strategy_id, symbol) state mutation guarding for concurrency | Implemented |
| SRD-EXE-011.013 | Mode + auto_trade dispatch routing to ExecutionRouter or Manual pending store | Implemented |
| SRD-EXE-011.014 | GUI isolation: no PyQt6 imports; sealed StrategyEvent union on event bus | Implemented |
| SRD-EXE-011.015 | 50 enabled strategies × 500 active symbols scaled within 200 ms per FO requirement | Implemented |
| SRD-EXE-012.001 | Ledger table schema with identity, entry, risk-config snapshot, live state, exit, outcome columns | Implemented |
| SRD-EXE-012.002 | Open on entry fill; transition OPENING → OPEN; materialize risk-config from StrategyConfig | Implemented |
| SRD-EXE-012.003 | Risk-config immutability: per-cycle edits only via update_risk(), not from StrategyConfig changes | Implemented |
| SRD-EXE-012.004 | Live tick update: recompute current_price, current_pnl_usd/pct, highest_price_seen, trailing_stop_level, effective_stop; throttle ≥ 500 ms | Implemented |
| SRD-EXE-012.005 | Tick-driven exit trigger on effective_stop breach or target_price cross; emit ExitTrigger event; transition OPEN → CLOSING | Implemented |
| SRD-EXE-012.006 | Close on exit fill: transition CLOSING → CLOSED, freeze realized_pnl_usd/pct, publish CycleClosed event | Implemented |
| SRD-EXE-012.007 | Abort on entry failure: transition OPENING → ABORTED, publish CycleAborted event | Implemented |
| SRD-EXE-012.008 | One open cycle per (strategy_id, symbol) invariant enforced; duplicate-open-cycle error raised | Implemented |
| SRD-EXE-012.009 | Read API: TradeCycleQuery with open_cycles(), cycle(id), history(symbol, strategy_id, days) returning immutable frozen DTOs with schema_version | Implemented |
| SRD-EXE-012.010 | Write API: TradeCycleCommand on_entry_fill/on_exit_fill/on_entry_failed/update_risk with invariant checks | Implemented |
| SRD-EXE-012.011 | Event bus publishing sealed TradeCycleEvent union: CycleOpened, CycleUpdated, ExitTrigger, CycleClosing, CycleClosed, CycleAborted, RiskUpdated | Implemented |
| SRD-EXE-012.012 | Cross-session persistence: EOD flush, startup reload, re-attach to tick stream | Implemented |
| SRD-EXE-012.013 | GUI isolation: no PyQt6 imports; headless event bus access via TradeCycleEvent union | Implemented |

---

## Design Decisions

- **Strategy Engine Concurrency:** Concurrent evaluation per-candle with per-(strategy_id, symbol) state mutation guarding via `asyncio` locks ensures no interleaving; single-consumer FIFO queue prevents ordering bugs
- **Mode-Based Dispatch:** (Mode=Auto, auto_trade=True) routes directly to ExecutionRouter; all other combinations land in Manual pending store for user confirmation
- **Trade Cycle Immutable Config:** Risk parameters (hard_stop_loss, target, trailing_offset) are captured at entry-fill time from StrategyConfig and frozen on the cycle row; subsequent StrategyConfig edits do not retroactively change open cycles
- **Tick-Driven Exit Triggers:** Price ticks feed into trailing-stop and target-price evaluation, emitting ExitTrigger events for immediate SELL order submission
- **No PyQt6 in Core Logic:** Both Strategy Engine and Trade Cycle modules use sealed event unions for cross-module communication, enabling headless consumption by backtesting and MCP without Qt dependency
- **StaticPool Fix for Tests:** Multi-threaded SQLite test harness now uses `StaticPool()` and `check_same_thread=False` to prevent "database is locked" errors during concurrent test execution

---

## Issues Resolved

None (feature-driven session; no issues closed)

---

## Test Coverage

**FO-EXE-011 Strategy Engine:** 38 tests pass across 5 test files
- `test_strategy_engine.py`: 12 tests (registry load, bar-close trigger, symbol-scope filter, 50-strategy/500-symbol scaling)
- `test_strategy_context.py`: 8 tests (state machine transitions, schedule guard, capital cap)
- `test_strategy_evaluator.py`: 9 tests (expression parsing, operators, precedence, indicator calls)
- `test_strategy_router.py`: 5 tests (mode-based dispatch, pending store routing)
- `test_strategy_events.py`: 4 tests (event union, event bus)

**FO-EXE-012 Trade Cycle Ledger:** 29 tests pass across 3 test files
- `test_trade_cycle_schema_dto.py`: 10 tests (schema, state machine, DTO immutability)
- `test_trade_cycle_repository.py`: 7 tests (DB persistence, tick updates, exit trigger evaluation)
- `test_trade_cycle_service.py`: 12 tests (on_entry_fill, on_exit_fill, update_risk, event publishing, multi-threaded SQLite fix)

**Total:** 67 tests pass; ≥80% coverage on all modules verified.

