# Revision Note — RN-EXE-1.30.0-20260617

**Version:** 1.30.0
**Date:** 2026-06-17
**Tool:** EXE
**Artifact:** FO-EXE-011, FO-EXE-012 / SRD-EXE-011.024, SRD-EXE-011.025, SRD-EXE-012.014
**Type:** Bugfix (ISS-EXE-0010)

---

## Summary

A position closed by one exit route (force-exit ■) left a stale pending exit signal (pending ►) live in the queue, so executing that pending exit on a non-OPEN position caused an `InvalidStateTransitionError` that crashed the engine — enabling a duplicate exit order to be submitted. Three single-exit guards now prevent this scenario: (1) closing a cycle by any route clears matching pending EXIT signals via `PendingSignalStore.dismiss_for`; (2) executing a pending EXIT on a non-OPEN cycle is rejected with a WARNING; and (3) an orphan or duplicate exit fill is logged and ignored instead of raising an error, so the dual exit routes can no longer place a duplicate exit order.

---

## Behaviour Changes

- **Pending exit signals are dismissed on cycle close.** When a `CycleClosed` event fires, `AppService` subscribes to it, marshals to the GUI thread, and calls `PendingSignalStore.dismiss_for(strategy_id, symbol, action=EXIT)` to drop any matching pending signals. This pairs with the existing pending-entry dismissal on open.

- **Pending exit execution validates the position is still OPEN.** Before submitting a pending EXIT signal, `AppService.execute_signal()` checks that the `(strategy_id, symbol)` pair still has an OPEN cycle. If not, the signal is dropped with a WARNING log and no order is submitted. Prevents executing a stale exit after the position has already closed.

- **Orphan and duplicate exit fills are logged and ignored.** In `TradeCycleService.on_exit_fill()`, if a fill arrives for a cycle in a non-EXIT state (already closed, no cycle exists), the event is logged at WARNING with topic `[Orders]` and the method returns `None` instead of raising `InvalidStateTransitionError`. This allows the application to survive a duplicate or out-of-order fill without crashing.

---

## Code Changes

| File | Change | SRD |
|---|---|---|
| `execution/pending_signal_store.py` | New `dismiss_for(strategy_id, symbol, action) -> int` method — removes all pending signals matching `(strategy, symbol, action)` and returns the count removed (for logging). | SRD-EXE-011.024, .025 |
| `gui/app_service.py` | Subscribe to `CycleClosed` event (published by `TradeCycleService`); in the slot `_clear_pending_exits`, marshal to GUI thread and call `self._pending_store.dismiss_for(...)` with action=EXIT. In `execute_signal()`, check that the target cycle is OPEN before executing a pending EXIT; if non-OPEN, log WARNING `"[Orders] Pending exit for {strategy}/{symbol} discarded — no OPEN cycle"` and return None without submitting. | SRD-EXE-011.024, .025 |
| `execution/trade_cycle/_service.py` | Update `on_exit_fill(fill) -> CycleSnapshot \| None` return type annotation to include `None`. Catch `InvalidStateTransitionError` when updating the cycle state on an exit fill; on catch, log WARNING `"[Orders] Orphan/duplicate exit fill for {symbol} ignored (cycle state={state})"` and return `None`. | SRD-EXE-012.014 |
| `execution/trade_cycle/_protocols.py` | Update `TradeCycleCommand.on_exit_fill` return type signature to `CycleSnapshot \| None`. | SRD-EXE-012.014 |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-011.024 | Closing a cycle by any route clears matching pending EXIT signals via `PendingSignalStore.dismiss_for` and `AppService` subscription to `CycleClosed` event, marshalled to GUI thread | Implemented |
| SRD-EXE-011.025 | `AppService.execute_signal` drops a pending EXIT with a WARNING when its `(strategy, symbol)` has no OPEN cycle | Implemented |
| SRD-EXE-012.014 | `on_exit_fill` logs a `[Orders]` WARNING and returns `None` (no `InvalidStateTransitionError`) on an orphan/duplicate exit fill | Implemented |

---

## Design Decisions

- **Three-layer guard design.** Rather than rely on a single defensive check, the fix applies three independent guards: (1) eager dismissal on close prevents a stale signal from existing; (2) execution-time validation prevents a stale signal from being acted on; (3) fill-time error suppression prevents a stale/duplicate fill from crashing the engine. The three layers provide defence in depth and handle edge cases where a signal reaches the execution layer despite prior dismissal (race condition).

- **Marshalled event handling.** The `CycleClosed` event is published by `TradeCycleService` (which runs on a background thread). The `AppService._clear_pending_exits` slot is connected with a queued signal (`_clear_pending_exits_requested`) to ensure the pending-store dismissal happens on the GUI thread, matching the pattern used for `_auto_exit_requested`.

- **Return type change.** `on_exit_fill` now returns `CycleSnapshot | None` instead of just `CycleSnapshot`. This signals the caller that the fill was ignored (an edge case) and allows the fill handler to decide whether to update downstream metrics or skip the event. The concrete path (happy case) still returns the snapshot; the error path returns `None`.

---

## Issues Resolved

| Issue | Behaviour |
|---|---|
| ISS-EXE-0010 | On 2026-06-16, a position closed by force-exit ■ left a pending exit ► live; executing that signal on the same symbol after the position closed raised `InvalidStateTransitionError`, crashing the engine and corrupting the cycle ledger. The TER 15:44 and LRCX 16:03 entries were in this corrupted state. All three guards now prevent the duplicate exit from ever reaching the broker. |

---

## Test Coverage

| Check | Result |
|---|---|
| `tests/execution/test_pending_signal_store.py::test_dismiss_for_removes_matching_exits` — UT-EXE-011.024.M01.T01 | Pass — dismiss removes only matching (strategy, symbol, action) triples |
| `tests/execution/test_pending_signal_store.py::test_dismiss_for_counts_removed` — UT-EXE-011.024.M01.T02 | Pass — return value == count of removed signals |
| `tests/gui/test_app_service_duplicate_exit.py::test_cycle_closed_dismisses_pending_exits` — UT-EXE-011.024.M01.T03 | Pass — `CycleClosed` event triggers dismissal on GUI thread |
| `tests/gui/test_app_service_duplicate_exit.py::test_execute_signal_rejects_exit_on_non_open_cycle` — UT-EXE-011.024.M01.T04 | Pass — pending EXIT rejected when cycle not OPEN |
| `tests/gui/test_app_service_duplicate_exit.py::test_execute_signal_rejects_exit_on_missing_cycle` — UT-EXE-011.025.M01.T01 | Pass — pending EXIT rejected when no cycle exists for the symbol |
| `tests/gui/test_app_service_duplicate_exit.py::test_execute_signal_logs_warning_on_exit_rejection` — UT-EXE-011.025.M01.T02 | Pass — WARNING logged with topic [Orders] |
| `tests/execution/test_trade_cycle_service.py::test_on_exit_fill_orphan_returns_none_without_raising` — UT-EXE-012.002.M02.T19 | Pass — orphan exit fill returns `None`, no exception raised |
| Full `tests/execution` + `tests/gui` | 244 passed (9 new tests); no regressions |
| `ruff` | clean on all modified files; no new violations |
| `mypy --strict` | no new errors in affected modules |

---

## Notes / Deviations

- The change to `on_exit_fill()` return type from `CycleSnapshot` to `CycleSnapshot | None` is safe because the only caller is `ExecutionEngine.handle_order_fill()`, which receives the return value but does not use it (the engine processes the `TradeCycleEvent` published by the service, not the return value). If a return value is needed in the future, the caller can use `if snapshot is not None:` guard.

- The `dismiss_for` method is idempotent and thread-safe (guarded by the same lock as all other pending-store operations), so calling it multiple times on the same event (e.g. if a `CycleClosed` is re-published or misses a subscription) is safe.

- No backward-compatibility concern: both `PendingSignalStore.dismiss_for` and the event subscription are new in this session; no existing callers are affected.

---

**Commit:** Refs: MD-EXE-011.024.M01, MD-EXE-011.025.M01, MD-EXE-012.002.M02
