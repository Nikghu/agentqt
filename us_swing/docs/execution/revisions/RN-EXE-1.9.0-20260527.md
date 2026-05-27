# Revision Note — RN-EXE-1.9.0-20260527

**Version:** 1.9.0
**Date:** 2026-05-27
**Tool:** EXE
**Artifact:** FO-EXE-011 / SRD-EXE-011.016–019
**Type:** Feature

---

## Summary

Implemented `rex_count` per-symbol re-execution enforcement in the Strategy Engine. A new `RexCounterRepository` manages a sibling SQLite table (`strategy_rex_counters`) tracking remaining re-entry allowances per (strategy_id, symbol). Entry signals are gated after the entry condition fires, and counters decrement on fill confirmation. Counters persist across engine restarts and can be manually reset via a GUI Reset Strategy action in the strategy table.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-011.001.M01 | `src/us_swing/execution/strategy_engine/_engine.py` | Added `rex_counters` optional constructor parameter; forwards to `_Router` |
| MD-EXE-011.001.M04 | `src/us_swing/execution/strategy_engine/__init__.py` | Re-exports `RexCounterRepository` from `_rex_counter` |
| MD-EXE-011.001.M08 | `src/us_swing/execution/strategy_engine/_rex_counter.py` | **NEW** — `RexCounterRepository` CRUD on `strategy_rex_counters` table; `get()`, `decrement()`, `reset()` methods |
| MD-EXE-011.001.M07 | `src/us_swing/execution/strategy_engine/_router.py` | Added entry gate in `evaluate()` ACTIVE branch after entry_condition; decrement call in `on_order_fill()` entry branch after `StrategyEntered` published |
| MD-GUI-004.001.M01 | `src/us_swing/gui/execution_panel.py` | Added "Reset" icon column (index 5) to strategy table, inserted reset button per row with confirmation dialog |
| MD-GUI-006.001.M01 | `src/us_swing/gui/strategy_builder_dialog.py` | Rewrote Rex Count QSpinBox tooltip text to clarify new semantic (N+1 total entries allowed) |
| MD-GUI-014.001.M02 | `src/us_swing/gui/active_cycles_model.py` | Added `Col.REX` column (13) showing live `rex_remaining` counter; wired via `StrategyEntered` event refresh |
| MD-GUI-014.001.M01 | `src/us_swing/gui/active_cycles_panel.py` | Imported `StrategyEntered`; wired dispatch to model's `on_strategy_entered` slot for targeted column refresh |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-011.016 | RexCounterRepository on sibling `strategy_rex_counters` table keyed (strategy_id, symbol) | Implemented |
| SRD-EXE-011.017 | Entry gate in `_router.evaluate()` Active branch; drop signal with `reason='rex_limit'` when counter < 0 | Implemented |
| SRD-EXE-011.018 | Decrement in `_router.on_order_fill()` entry branch after `StrategyEntered` publish | Implemented |
| SRD-EXE-011.019 | Cross-restart persistence via lazy SQL queries (no eager in-memory cache) | Implemented |

---

## Design Decisions

- **Sibling table architecture:** `strategy_rex_counters` lives in the same `candles.db` database as `trade_cycles`, allowing transactional scoping and avoiding external service dependencies
- **Lazy evaluation:** Counter state is queried fresh on each signal evaluation rather than eagerly loaded into `_StrategyContext`; reduces memory footprint and simplifies restart semantics
- **Semantic lock-in:** `rex_count = N` means N+1 total entries allowed (default N=0 → exactly 1 entry); counter walks N → N-1 → ... → 0 → -1 (blocked). Clarified in dialog tooltip
- **Reset action placement:** Per-row Reset icon in strategy table (not a global action) reflects per-strategy, per-symbol granularity of the counter
- **Active Cycles column refresh:** `StrategyEntered` event triggers targeted dataChanged emission for REX column only, avoiding full model refresh cost

---

## Issues Resolved

None

---

## Test Coverage

25 new rex tests across 2 modules:
- `tests/execution/test_rex_counter.py` — 8 unit tests (UT-EXE-011.001.M08.T01–T08): CRUD on RexCounterRepository, table DDL, index, persistence
- `tests/execution/test_strategy_router.py` — 7 new tests (UT-EXE-011.001.M01.T11–T17): router gate, decrement, full lifecycle with Reset, edge cases

**Status:** All 25 pass; 12 pre-existing unrelated failures in other modules (test_intraday_candle_loader, test_live_tick_worker, test_strategy_evaluator::test_function_map_has_exactly_14_keys) left as-is

---

## Notes

Two memory files updated for rollout planning:
- `feature_rex_count_enforcement.md` — status flipped to **IMPLEMENTED 2026-05-27**
- `feature_active_trades_panel_rollout.md` (**NEW**) — 5-step rollout plan for swapping legacy Pending Signals widget for ActiveCyclesPanel (user-facing label "Active Trades"); documents pre-rollout gaps including a deeper bus-subscribe-signature mismatch in `active_cycles_panel.py:325`
