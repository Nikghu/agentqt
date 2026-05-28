# Revision Note — EXE 1.12.0 (Final_Execution.md Phase 1)

**RN ID:** RN-EXE-1.12.0-20260528
**Date:** 2026-05-28
**Author:** Claude (Opus 4.7) — automated
**Type:** Refactor (state-enum consolidation)
**Tool:** EXE
**Parent FO:** FO-EXE-013 — Strategy Run Lifecycle
**Plan:** PLAN-EXE-Final-Execution §5.1

---

## Summary

Phase 1 of the state-enum consolidation plan: drop the engine-private
`_CycleState` StrEnum entirely and consolidate per-strategy runtime state
under `ExecutionEnums.StrategyRunState` (`STOPPED` / `RUNNING` / `SQUARING_OFF`).
The router now derives evaluation behaviour from the pair
`(StrategyRunState, TradeCycleQuery.has_open_cycle)` instead of a parallel
in-engine cycle-state dict.

## Functional changes

1. **`StrategyConfig.strategy_signal`** — legacy free-string `Status` key
   replaced by `run_state` (`"STOPPED"` / `"RUNNING"` / `"SQUARING_OFF"`).
   `load_strategies()` migrates legacy values once on first load:
   `"Inactive"` → `STOPPED`, `"Active"` or `"Running"` → `RUNNING`.

2. **`_StrategyContext`** — `cycles: dict[str, _CycleState]` and `_CycleState`
   removed.  New fields: `run_state: ExecutionEnums.StrategyRunState`
   (default `STOPPED`) and `in_flight: set[str]` (symbols with a signal
   awaiting fill / reject).

3. **`_Router.evaluate()`** — gates on `run_state` first
   (`STOPPED` / `SQUARING_OFF` → return), then derives entry-vs-exit branch
   from `TradeCycleQuery.has_open_cycle(strategy_id, symbol)`.  Duplicate
   suppression uses the `in_flight` set.

4. **`StrategyEngine.set_run_state()`** — new GUI-callable method.
   Transitions to `SQUARING_OFF` synchronously enqueue forced EXIT signals
   for every open cycle of the strategy (via `_Router.squaring_off_exit`).

5. **`StrategyEngine._squaring_off_loop`** — new background poller (2 s
   tick) that auto-transitions `SQUARING_OFF` → `STOPPED` once every open
   cycle for that strategy has reached a terminal state.

6. **Execution Panel ▶/■** — wired to `set_run_state()`.  Stop with open
   cycles now transitions to `SQUARING_OFF` (instead of the prior blocking
   warning), letting the engine drain cycles cleanly.

7. **TradeCycleQuery surface** — added `has_open_cycle(strategy_id, symbol)
   -> bool` and `open_cycles_for_strategy(strategy_id) -> tuple[CycleSnapshot, ...]`
   methods, implemented in `TradeCycleRepository` and surfaced through
   `TradeCycleService`.

## Files changed

| File | Change |
|---|---|
| `execution/strategy_engine/_context.py` | Drop `_CycleState`; add `run_state`, `in_flight` |
| `execution/strategy_engine/_router.py` | Replace cycle-state checks with run-state gate + `in_flight` + `cycle_query.has_open_cycle` |
| `execution/strategy_engine/_engine.py` | `_migrate_run_state` helper; `_squaring_off_loop`; `set_run_state`; cycle_query injection; drop cycle_loader |
| `execution/strategy_engine/__init__.py` | Drop `_CycleState` re-export |
| `execution/trade_cycle/_protocols.py` | Add `has_open_cycle` + `open_cycles_for_strategy` to `TradeCycleQuery` |
| `execution/trade_cycle/_repository.py` | Concrete implementations of the new query methods |
| `execution/trade_cycle/_service.py` | Service delegation for the new query methods |
| `gui/strategy_builder_dialog.py` | `_migrate_strategy_signal` helper; default factory uses `run_state`; `load_strategies` migrates legacy |
| `gui/strategy_table_model.py` | Read `run_state` instead of `Status`; `STATUS_COLORS` keyed by new values |
| `gui/execution_panel.py` | Play/Stop wired to `set_run_state`; Stop with open cycles → `SQUARING_OFF` |
| `gui/app_service.py` | Pass `cycle_query=self._tc_query` to `StrategyEngine`; drop `cycle_loader` |
| `tests/execution/test_strategy_context.py` | Drop `_CycleState` tests; assert default `run_state`, `in_flight` |
| `tests/execution/test_strategy_router.py` | Replace `ctx.cycles` mutation with `_FakeCycleQuery`; new tests T21–T25 for run_state gating |
| `tests/execution/test_strategy_engine.py` | Assert `run_state` on loaded registry |

## SRDs implemented

| SRD | Status |
|---|---|
| SRD-EXE-011.001 | Reopen → Implemented |
| SRD-EXE-011.007 | Reopen → Implemented |
| SRD-EXE-013.001 — .008 | Approved → Implemented |

## Tests

| Module | Tests | Result |
|---|---|---|
| `test_strategy_context.py` | 9 (T01–T06, T08–T09 + new) | All pass |
| `test_strategy_router.py` | 25 (T01–T20 reworked + new T21–T25 for run_state gating) | All pass |
| `test_strategy_engine.py` | 7 (T01–T07) | All pass |
| `test_enums.py` | 18 (Phase 0) | All pass |
| `test_trade_cycle_*` | 33 (unchanged) | All pass |

Total Phase 1-relevant: **145 passed** (full `test_strategy_*` + `test_trade_cycle_*` + `test_enums` + adjacent execution tests).

Pre-existing failures on `main` (not caused by this change): 22 failures in
`test_intraday_candle_loader`, `test_live_tick_worker`, `test_candle_builder`,
`test_strategy_evaluator`, `test_app_service_tick`, `test_lifecycle_e2e`,
`test_preset`, `test_repository` (monitoring_session).

## Lint / type

- `ruff check` — clean on all Phase 1 files.
- `mypy --strict` — clean on `strategy_engine/*`, `trade_cycle/*`,
  `execution/_enums.py`.

## Behavioural delta

- **Stop with open cycles** no longer pops a blocking warning — the
  strategy transitions to `SQUARING_OFF` and the engine drains open cycles
  via forced EXIT signals.  The user can still manually intervene via
  Force Exit in the Pending Signals table; the auto-drain is a defence in
  depth.
- **Restart with `RUNNING` strategy** survives the boot — prior behaviour
  forced every strategy back to `Inactive` on load.  Persisted `run_state`
  is now trusted verbatim (decision log #3 in `Final_Execution.md`).

## Out of scope (deferred)

- Phase 2 (TradeCycleState enum promotion in DTOs and repository).
- Phase 3 (`PositionState` split into `BuyOrderState` / `SellOrderState`).
- Phase 4 (`LifecycleState` internalisation under `ExecutionEnums`).
