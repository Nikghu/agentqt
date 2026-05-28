# Revision Note — EXE 1.13.0 (Final_Execution.md Phase 2)

**RN ID:** RN-EXE-1.13.0-20260528
**Date:** 2026-05-28
**Author:** Claude (Opus 4.7) — automated
**Type:** Refactor (typed-enum promotion)
**Tool:** EXE
**Parent FO:** FO-EXE-012 — Trade Cycle Ledger
**Plan:** PLAN-EXE-Final-Execution §5.2

---

## Summary

Phase 2 of the state-enum consolidation plan: promote `CycleSnapshot.state`
from a free-string field to a typed `ExecutionEnums.TradeCycleState`.  The
five legacy frozensets (`CYCLE_STATES`, `NON_TERMINAL_STATES`,
`TERMINAL_STATES`) are removed; their callers now use the enum directly
with `is_terminal()` / `is_non_terminal()` instance methods.  Wire values
are unchanged — SQLite storage stays string, DB rows are coerced into the
enum at the repository boundary.

## Functional changes

1. **`ExecutionEnums.TradeCycleState`** — gains two instance methods:
   `is_terminal()` (returns True for CLOSED/ABORTED) and `is_non_terminal()`
   (logical inverse).
2. **`CycleSnapshot.state`** — field type changes from `str` to
   `ExecutionEnums.TradeCycleState`; default value becomes
   `TradeCycleState.OPENING`.
3. **`_dto.py`** — `CYCLE_STATES`, `NON_TERMINAL_STATES`,
   `TERMINAL_STATES` frozensets deleted.  Replaced with derived tuples
   `NON_TERMINAL_STATE_VALUES` / `TERMINAL_STATE_VALUES` (computed from
   the enum) for SQLAlchemy `in_()` queries that still need wire strings.
   New helper `coerce_state(value)` accepts enum or string and returns
   the enum; raises `ValueError` on unknown input.
4. **`_repository.py`** — `_ALLOWED_TRANSITIONS` re-keyed by enum members;
   `update_state`, `close`, `abort` operate on enum; `_row_to_snapshot`
   coerces the raw DB string into the enum before constructing the DTO.
5. **`_service.py`** — every literal state comparison (`"OPEN"`,
   `"CLOSING"`, `NON_TERMINAL_STATES`) replaced with enum members or
   `state.is_non_terminal()`.  Insert payload uses
   `TradeCycleState.OPEN.value`.
6. **`exit_reasons`** — `EXIT_REASONS` frozenset gains `"squaring_off"`
   to cover the Phase 1 forced-exit path.
7. **Package surface** — `trade_cycle/__init__.py` re-exports
   `TradeCycleState` instead of the deleted frozensets; downstream
   consumers (active_cycles_model, ExecutionService) continue to work
   unchanged because `StrEnum` compares equal to its string value.

## Files changed

| File | Change |
|---|---|
| `execution/_enums.py` | Add `is_terminal()`/`is_non_terminal()` on `TradeCycleState` |
| `execution/trade_cycle/_dto.py` | Drop CYCLE_STATES/NON_TERMINAL_STATES/TERMINAL_STATES; add `coerce_state`; type `CycleSnapshot.state` |
| `execution/trade_cycle/_repository.py` | Re-key `_ALLOWED_TRANSITIONS`; coerce DB rows; enum-typed state mutators |
| `execution/trade_cycle/_service.py` | Replace string comparisons with enum members; `is_non_terminal` guard in `update_risk` |
| `execution/trade_cycle/__init__.py` | Re-export `TradeCycleState`; drop old frozensets |
| `tests/execution/test_trade_cycle_schema_dto.py` | New tests T02-T05: enum values, terminal helpers, negative `coerce_state` |

## SRDs implemented

| SRD | Status |
|---|---|
| SRD-EXE-012.010 | Approved → Implemented |
| SRD-EXE-012.011 | Approved → Implemented |

## Tests

| Module | Result |
|---|---|
| `test_trade_cycle_schema_dto.py` | 8 pass (added T02-T05 for enum surface) |
| `test_trade_cycle_repository.py` | All pass (state comparisons still work via StrEnum) |
| `test_trade_cycle_service.py` | All pass |
| `test_strategy_*` | All pass (Phase 1 carried forward) |
| `test_enums.py` | All pass |

Full execution-tests result excluding pre-existing failures: **148 passed**.
Pre-existing failures on `main`: unchanged from Phase 1 RN.

## Lint / type

- `ruff check` — clean on `execution/trade_cycle/`, `execution/_enums.py`.
- `mypy --strict` — clean on every file touched by Phase 2.

## Behavioural delta

- **No DB schema change** — stored strings remain "OPENING" / "OPEN" /
  "CLOSING" / "CLOSED" / "ABORTED" as before.
- **No GUI visual change** — active_cycles_model's `_STATE_BG` dict keyed
  by string keeps working because `TradeCycleState("OPEN") == "OPEN"`.
- **Negative behaviour now caught at boundary** — passing an unknown
  state string into `coerce_state` (called by `_row_to_snapshot`,
  `update_state`, etc.) raises `ValueError` immediately, instead of
  failing later when an SQL constraint or business-logic check sees the
  value.

## Out of scope (deferred)

- Phase 3 — `PositionState` → `BuyOrderState` + `SellOrderState` split.
- Phase 4 — `LifecycleState` move from `core/monitoring_session/_enums.py`
  into `ExecutionEnums`.
