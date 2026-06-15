# Revision Note — RN-EXE-1.26.0-20260612

**Version:** 1.26.0
**Date:** 2026-06-12
**Tool:** EXE
**Artifact:** SRD-EXE-014.007 / ISS-EXE-0007
**Type:** Fix

---

## Summary

Fixed a critical exit-routing defect: with more than one open position, closing
one position exited a different one at the wrong price. `on_exit_fill` resolved
the target cycle as the oldest open cycle lacking an exit order id, ignoring
symbol and strategy. It now resolves by `(strategy_id, symbol)` — unique among
open cycles — so an exit always closes the position it was raised for. Affected
both manual closes and automatic target/SL/trailing exits.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-012.002.M02 | `src/us_swing/execution/trade_cycle/_service.py` | `on_exit_fill` takes `symbol` + `strategy_id`; target cycle matched by that pair, not "first open cycle with no exit_order_id" |
| MD-EXE-012.002.M01 | `src/us_swing/execution/trade_cycle/_protocols.py` | `TradeCycleCommand.on_exit_fill` signature += `symbol`, `strategy_id` |
| MD-EXE-015.001.M01 | `src/us_swing/execution/order_ingestion.py` | `_close_cycle` passes `ctx.symbol` / `ctx.strategy_id` into `on_exit_fill` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-014.007 | Exit fill resolves its cycle by (strategy_id, symbol), not the oldest open cycle | Implemented |

---

## Root Cause

`on_exit_fill` reached `find_by_exit_order(exit_order_id)` → None (the cycle is
never pre-stamped with the order id on the broker-fill path), then fell back to
the first open cycle with `exit_order_id is None`. With multiple open cycles this
closed the oldest one, and the clicked symbol's exit price was applied to the
wrong cycle. Full evidence in ISS-EXE-0007 (QCOM closed at PCG's price,
PNL −$371.97).

---

## Issues Resolved

ISS-EXE-0007

---

## Test Coverage

- `tests/execution/test_trade_cycle_service.py` — UT-EXE-014.007.M02.T19 (NEW):
  two open cycles (QCOM older, PCG newer); a PCG exit closes PCG and leaves QCOM
  OPEN with no exit price. Pass.
- Regression: cycle service + broker adapter + monitoring session = 50 passed;
  integration exit/lifecycle = 6 passed, 2 skipped.
- `ruff` clean on all changed files; `mypy --strict` clean on the changed files
  (only pre-existing unrelated module errors remain).

---

## Notes / Deviations

- Historical data not auto-repaired: cycle 25 (QCOM) keeps its wrong exit. Pending
  the user's decision on whether to correct/delete that row.
- Same class of defect previously existed on the auto-exit path (a trigger on one
  of several open cycles could close the wrong position); this fix covers it too,
  since both paths flow through `on_exit_fill`.

---

**Commit:** pending — Refs: SRD-EXE-014.007, ISS-EXE-0007
