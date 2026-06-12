# Revision Note — RN-EXE-1.23.0-20260612

**Tool:** EXE
**Version:** 1.23.0
**Date:** 2026-06-12
**Author:** Claude Opus 4.8 under user direction
**Phase:** Bugfix — ISS-EXE-0005 (closed-cycle realized P&L used wrong quantity)

---

## Summary

Fixes the dollar P&L frozen on a closed trade cycle. For multi-share positions
the value was computed on the sell fill's reported quantity (`exit_qty`) instead
of the held position size, so it under-counted whenever the two diverged — e.g.
a 5-share position showed the 1-share per-share difference. The P&L percentage
was always correct because it does not use quantity.

## Behaviour Changes

- `realized_pnl_usd` now equals `(exit_price − entry_price) × entry_qty` — the
  full held position. A cycle only reaches `CLOSED` on a `FILLED` full-position
  sell, so the realized quantity is invariantly `entry_qty`.
- The closed P&L is now consistent with the unrealized P&L shown while the trade
  was open (that path already used `entry_qty`).
- `exit_qty` is still recorded on the exit fields for audit; only the P&L
  multiplier changed.

## Code Changes

| File | Change | SRD |
|---|---|---|
| `execution/trade_cycle/_service.py` | `_close_cycle` realized-P&L multiplier `exit_qty` → `snap.entry_qty`; comment names the FILLED-gate invariant | SRD-EXE-012.007 |

## Acceptance — Status

| Check | Status | Evidence |
|---|---|---|
| Realized P&L uses held qty when exit_qty diverges | ✅ | `test_on_exit_fill_realized_pnl_uses_held_entry_qty` (T18) |
| Equal-qty close still correct (no regression) | ✅ | `test_on_exit_fill_closes_cycle...` (T13), 132.5 unchanged |
| `exit_qty` still persisted for audit | ✅ | code review (exit_fields line intact) |

## Tests

| Check | Result |
|---|---|
| `tests/execution/test_trade_cycle_service.py` | 24 passed (1 new) |
| `ruff` | Clean on changed files |
| `mypy` | No new errors in `_service.py` (pre-existing errors in other imported modules unchanged) |
| Full execution suite | 12 failures all pre-existing and unrelated (candle-loader, live tick worker, evaluator 14-key) — not touched by this change |

## Notes / Deviations

- SRD-EXE-012.007 was an Approved row whose formula was found wrong; it was
  corrected and re-implemented in the same session (Approved → Implemented),
  validated GO by the artifact-validator.
- DD has no realized-P&L formula row, so no DD cascade was needed.
- Two pre-existing abort tests (UT-EXE-012.002.M02.T16/T17) were missing from
  UTCD.md; reconciled while adding the new T18 to keep numbering contiguous.
- Existing wrong P&L values already in the database were left as-is — acceptable
  during the testing phase (per user); no backfill performed.
- The screenshot's out-of-range exit prices (CL $322, MNST $403) indicate a
  separate live price-feed issue, not addressed here.

---

**Commit:** pending — Refs: SRD-EXE-012.007
