# Revision Note — RN-EXE-1.16.0-20260529

**Tool:** EXE
**Version:** 1.16.0
**Date:** 2026-05-29
**Author:** Claude Opus 4.8 under user direction
**Phase:** FO-EXE-014 completion — broker reject/cancel, OPENING-hold, order-state-gated lifecycle

---

## Summary

Implements the remaining four FO-EXE-014 requirements (`.005`–`.008`), all set to
Approved by the user before this session. These deliver the **component-level
contracts** of the broker order-state machine — handler methods, a DTO field, and
state-gating logic — that the upcoming FO-EXE-003 (CircuitBreaker) wiring will call.
This also closes the `SRD-EXE-014.008` deferral recorded in RN-EXE-1.15.0.

- **`.005` / `.006`** — `ExecutionEngine` gains `handle_order_reject` (stamps the
  `trades` row REJECTED with zero fill and signals the owning cycle to abort) and
  `handle_order_cancel` (stamps CANCELLED, preserving the partial `filled_quantity`).
  Two new broker DTOs (`IBKRReject`, `IBKRCancel`) model the events. The cycle abort
  is delivered through an injected `on_order_failed` callback, mirroring the existing
  `on_fill` injection — keeping the engine decoupled from the trade-cycle package.
- **`.007`** — `TradeCycleService.on_entry_fill` takes an `order_state` argument: a
  `PARTIAL_FILLED` entry holds the cycle in `OPENING`; a `FILLED` entry opens it
  (`OPENING → OPEN` when a partial was already held, otherwise a fresh `OPEN`).
- **`.008`** — the monitoring `FillEvent` gains an optional `order_state`, and
  `on_fill` only flips `MONITORING → ENTERED` / `ENTERED → EXITED` on a fully FILLED
  order. `order_state=None` preserves the prior behaviour, so every existing caller
  and test is unaffected.

## Artefacts Touched

| Artefact | Change |
|---|---|
| `docs/execution/SRD.md` | SRD-EXE-014.005, .006, .007, .008 cycled Approved → Implemented |
| `docs/execution/UTCD.md` | Added UT-EXE-014.005.M01.T01, .006.M01.T02, .007.M01.T01–T03, .008.M01.T01–T05 (10 cases) |
| `docs/execution/TRACE.md` v1.11.0 | New FO-EXE-014 row for .005–.008 → Implemented; RN-EXE-1.16.0 linked |

(No new DD/MD rows — consistent with the FO-EXE-014 precedent set in Phase 3, which
carried SRD + UTCD + code without DD/MD entries. Design rationale lives here.)

## Code Changes

| File | Change |
|---|---|
| `data/models.py` | Added `IBKRReject` (`order_id, symbol, reason`) and `IBKRCancel` (`order_id, symbol, filled_quantity=0`) dataclasses, mirroring `IBKRFill`. |
| `execution/execution_engine.py` | New `on_order_failed: Callable[[str, str], None] \| None` constructor param. New `handle_order_reject` (REJECTED + zero fill + abort signal) and `handle_order_cancel` (CANCELLED + preserved partial fill). |
| `execution/trade_cycle/_service.py` | `on_entry_fill` gains `order_state` (default `FILLED`); PARTIAL holds OPENING, FILLED creates/advances to OPEN, with `OPENING → OPEN` publishing `CycleUpdated`. |
| `execution/trade_cycle/_protocols.py` | `TradeCycleCommand.on_entry_fill` signature updated to match (`order_state` keyword, default `FILLED`). |
| `core/monitoring_session/_dto.py` | `FillEvent` gains optional `order_state: BuyOrderState \| SellOrderState \| None`. |
| `core/monitoring_session/_service.py` | `_is_complete_fill()` helper; `on_fill` gates ENTERED on a FILLED BUY and EXITED on a FILLED SELL. A FILLED BUY completing an earlier partial (now in the scale branch) flips a still-MONITORING row to ENTERED. |

## Acceptance Criteria — Status

| SRD | Status | Evidence |
|---|---|---|
| .005 reject → REJECTED + cycle abort | ✅ component | `UT-EXE-014.005.M01.T01`: trades row REJECTED, `filled_quantity=0`, abort callback fired. Cycle `OPENING → ABORTED` is `on_entry_failed`'s existing behaviour; its production wiring is FO-EXE-003 (see Deferred). |
| .006 cancel → CANCELLED + preserved fill | ✅ component | `UT-EXE-014.006.M01.T02`: CANCELLED, `filled_quantity=40` preserved, cycle untouched. |
| .007 OPENING-hold / FILLED-open | ✅ | `UT-EXE-014.007.M01.T01–T03`: FILLED → OPEN; PARTIAL → OPENING; partial-then-FILLED → OPEN with one `CycleUpdated`. |
| .008 order-state-gated lifecycle | ✅ | `UT-EXE-014.008.M01.T01–T05`: FILLED BUY → ENTERED; PARTIAL BUY stays MONITORING; completing FILLED → ENTERED; FILLED SELL → EXITED; unfilled SELL stays ENTERED. |

## Tests

| Check | Result |
|---|---|
| 10 new UTCD cases (above) | Pass |
| `tests/core/monitoring_session/` (full) | Pass (66) |
| `tests/execution/test_trade_cycle_service.py` | Pass (18) |
| `tests/execution/test_execution_engine.py` | Pass (12) |
| `tests/integration/test_lifecycle_e2e.py` | Pass (incl. the date-decay fix landed this session) |
| `ruff` | Clean on all changed files (also removed a pre-existing dead import in `test_trade_cycle_service.py`) |
| `mypy --strict` | Clean on the 6 changed source modules (verified with `--follow-imports=silent`; the project-wide `--strict` run surfaces only pre-existing errors in untouched modules) |

**Environment:** `TA-Lib 0.6.8` was installed (prebuilt wheel) to run the EXE suite —
this resolves the "talib not installed" collection errors noted in RN-EXE-1.14.0 /
RN-EXE-1.15.0. Installing it unmasked **12 pre-existing failures** in
`test_intraday_candle_loader.py`, `test_live_tick_worker.py`, and
`test_strategy_evaluator.py` (the last asserts a stale "14 keys" count that predates
the BOSS-strategy additions). All 12 were verified failing identically on a clean
`HEAD` with the working tree stashed — they are unrelated to this change.

## Deferred → FO-EXE-003 (CircuitBreaker)

These are production-wiring items, not component gaps; the contracts above are
implemented and tested:

- **Engine PARTIAL computation** — `ExecutionEngine.handle_order_fill` still stamps
  `FILLED` unconditionally. Computing `FILLED` vs `PARTIAL_FILLED` from the order
  total feeds `.004`'s trades-row, not `on_entry_fill` (the engine forwards a
  `strategy_engine.FillEvent` with no `order_state` and does not call `on_entry_fill`).
  Symmetric exit-order tracking does not exist yet. Belongs with the FO-EXE-003 live
  wiring.
- **app_service wiring** — `app_service.py` does not yet route live broker
  reject/cancel callbacks into `handle_order_reject` / `handle_order_cancel`, nor call
  the lifecycle `on_fill` with a real `order_state`. The paper path uses the
  `order_state=FILLED` default. The `on_order_failed → on_entry_failed(cycle_id)`
  mapping is also wired here.

## Migration Notes

No schema or data migration. The new `order_state` fields are optional / additive;
`IBKRReject` / `IBKRCancel` are new DTOs; `REJECTED` / `CANCELLED` reuse the existing
`BuyOrderState` / `SellOrderState` wire values already present in the column constraint.

---

**Commits:** managed by the user per project convention (feature branch
`feat/exe-014-reject-cancel-fill-gating`).
