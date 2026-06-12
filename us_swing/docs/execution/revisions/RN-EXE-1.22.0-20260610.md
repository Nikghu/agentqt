# Revision Note — RN-EXE-1.22.0-20260610

**Tool:** EXE (+ GUI)
**Version:** 1.22.0
**Date:** 2026-06-10
**Author:** Claude Opus 4.8 under user direction
**Phase:** Bugfix — ISS-EXE-0004 (pending exit shows wrong qty / verb / colour)

---

## Summary

Fixes the Active Trades display of a **pending exit** signal. The order itself was
always correct (Trade History closed the full position), but the GUI showed a wrong
quantity, the verb "BUY", and a green ▶ button for a sell. Root cause: the engine's
EXIT `TradeSignal` never carried a quantity, and the panel assumed every pending
signal is a BUY entry.

## Behaviour Changes

- Every EXIT signal now carries `qty_recommended` = the held quantity of the open
  cycle (`entry_qty`). The pending exit row's **QTY** and the confirm dialog's number
  now show the real position size (e.g. 7), not the `1`/`0` placeholder.
- The confirm dialog verb is **action-aware**: `Sell N × SYM` for an exit,
  `Buy N × SYM` for an entry.
- The ▶ Execute button is **red** for a sell/exit and **green** for a buy/entry
  (muted while the circuit breaker is active).

## Code Changes

| File | Change | SRD |
|---|---|---|
| `execution/strategy_engine/_router.py` | New `_open_cycle_qty()`; `qty_recommended` set on the strategy-exit and `_force_exit` signals | SRD-EXE-011.021 |
| `gui/active_cycles_panel.py` | Confirm dialog verb from `signal.action`; ▶ button colour red(exit)/green(entry) in `_RowActionsDelegate`; import `Action` | SRD-GUI-014.015 |

## Acceptance — Status

| Check | Status | Evidence |
|---|---|---|
| Pending exit row QTY = held position qty | ✅ | `test_exit_signal_carries_open_cycle_qty` (T21) |
| Forced (end-time) exit carries qty | ✅ | `test_forced_exit_carries_open_cycle_qty` (T22) |
| Dialog says "Sell N × SYM" for exits | ✅ | `active_cycles_panel.py` verb from `Action.EXIT` (inspection) |
| ▶ button red for sell, green for buy | ✅ | delegate paint from `row.signal.action` (inspection) |

## Tests

| Check | Result |
|---|---|
| `tests/execution/test_strategy_router.py` | 27 passed (2 new) |
| Full execution + gui suites | 209 passed; 21 failures all pre-existing (candle-loader aggregation, live tick worker, evaluator 14-key, app_service tick — verified identical with changes stashed) |
| `ruff` | Clean on changed files |
| `mypy` | No new errors (router clean; panel's pre-existing PyQt-stub errors unchanged) |

## Notes / Deviations

- SRD-GUI-014.005 (Approved, user-frozen) hardcoded `BUY`. Instead of editing a frozen
  row, new superseding rows SRD-EXE-011.021 + SRD-GUI-014.015 were added — consistent
  with the SRD-EXE-017.011 → SRD-GUI-014.013 precedent.
- Router fix is the single source: both the model QTY and the dialog number read
  `qty_recommended`, so fixing the signal fixes both display points.

---

**Commit:** pending — Refs: SRD-EXE-011.021, SRD-GUI-014.015
