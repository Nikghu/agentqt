# Issue Report — ISS-EXE-0004

**Tool:** EXE (Execution) + GUI (display)
**Severity:** Medium (display only — order execution is correct)
**Status:** Resolved
**Date Opened:** 2026-06-10
**Date Resolved:** 2026-06-10
**Reporter:** User (USSwing)
**Resolution:** RN-EXE-1.22.0-20260610

---

## Symptom

When an exit condition fired for an open position (e.g. CNC, held qty 7), the
Active Trades panel showed the pending exit incorrectly:

1. Confirm dialog read **"Submit BUY 0 × CNC @ MKT?"** — wrong verb (BUY) and
   wrong quantity (0).
2. The pending exit row **QTY column showed 1**, not the held 7.
3. The **▶ Execute button stayed green** even though it is a sell.

Clicking ▶ → Yes closed the trade correctly (Sell 7, confirmed in Trade History),
so the backend was right — only the GUI presentation was wrong.

## Root Cause

The engine's EXIT `TradeSignal` was built **without `qty_recommended`**
(`_router.py` strategy-exit and `_force_exit` construction sites). Per
SRD-EXE-011.020 the field defaults to `1` (a manual-mode testing placeholder), and
the confirm dialog used `qty_recommended or 0`. So a pending exit carried no real
quantity.

Compounding it, the Active Trades panel assumed every pending signal is a **BUY
entry**: the confirm text hardcoded `"Submit BUY"` (active_cycles_panel.py) and the
`_RowActionsDelegate` painted the ▶ button `C.GREEN` unconditionally — neither
looked at `signal.action`.

## Fix

- **EXE (SRD-EXE-011.021):** every EXIT signal now sets
  `qty_recommended = _open_cycle_qty(strategy_id, symbol)`, reading `entry_qty`
  from the matching open cycle via `cycle_query.open_cycles_for_strategy`. Covers
  the strategy-exit path and forced exits (end-time / square-off / emergency). This
  alone fixes both the QTY column and the dialog number (both read
  `qty_recommended`).
- **GUI (SRD-GUI-014.015):** the confirm dialog verb is now action-aware
  (`Sell` for EXIT, `Buy` for ENTRY) and the ▶ Execute button paints `C.RED` for an
  exit, `C.GREEN` for an entry (`C.MUTED` while the circuit breaker is active).

## Affected Artifacts

| Artifact | Change |
|---|---|
| SRD-EXE-011.021 | New (Approved → Implemented) — exit signal carries open-cycle qty |
| SRD-GUI-014.015 | New (Approved → Implemented) — action-aware dialog verb + button colour; refines SRD-GUI-014.005 |
| UT-EXE-011.001.M04.T21, T22 | New — exit-qty tests (Pass) |
| `execution/strategy_engine/_router.py` | `_open_cycle_qty` helper; `qty_recommended` set on both EXIT signals |
| `gui/active_cycles_panel.py` | Action-aware dialog verb; exit/entry button colour in delegate |

## Notes / Deviations

- SRD-GUI-014.005 (Approved, user-frozen) hardcoded `BUY`; rather than edit a frozen
  Approved row, a new superseding row SRD-GUI-014.015 was added — consistent with the
  codebase pattern (SRD-EXE-017.011 superseding SRD-GUI-014.013).
- The button colour is GUI-thread paint only; verified by inspection. The router
  quantity is unit-tested (T21/T22).
