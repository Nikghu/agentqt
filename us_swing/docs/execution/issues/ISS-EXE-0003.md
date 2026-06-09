# Issue — ISS-EXE-0003

**Tool:** EXE
**Reported:** 2026-06-09
**Severity:** Low (log noise — no data impact)
**Status:** Resolved
**Area:** `core/monitoring_session/_service.py` — pre-open reconcile

---

## Symptom

After running the tool, the pre-open reconcile logged two `ERROR` lines for a
symbol that was then immediately and successfully self-healed:

```
ERROR [Lifecycle] Invariant violation — ledger ENTERED ['CVS'] open positions []
ERROR [Lifecycle] Invariant mismatch during reconcile: only_in_a=('CVS',) only_in_b=()
WARNING [Lifecycle] Healed an orphaned trade record for CVS — no open position, marking it closed
```

`CVS` was a stranded `ENTERED` ledger row with no open position (a close that
never flipped the ledger, from before the live `wire_cycle_ledger_projection`
landed). The reconcile heal (PR #36 / RN-EXE-1.19.0) correctly flipped it to
`EXITED` — so the data was fine, but the two `ERROR` lines wrongly signalled a
failure for a condition that auto-recovered.

## Root Cause

`reconcile_preopen` ran a "defensive invariant check" block that called
`check_invariant()` (which logs `ERROR`) and then logged a second `ERROR`
whenever `entered != keep.carryover`. That condition is also true for the
**healable** stranded-ENTERED case, so the block fired `ERROR` ×2 one step
before the per-symbol loop healed the row and logged the correct `WARNING`.

Per the project logging rules, `ERROR` = "a feature failed and needs user
attention." A self-healed orphan does not meet that bar.

## Fix

Removed the redundant summary block. The per-symbol loop already logs the right
levels: `WARNING` for a healed stranded-ENTERED row, `ERROR` only for the
genuinely un-healable case (an open cycle with no `ENTERED` ledger row).
`check_invariant()` keeps its own `ERROR` for standalone invariant queries.

## Verification

- New `UT-EXE-009.002.M02.T17e` — a healable orphan reconcile logs `WARNING`
  and **no** `ERROR`.
- Existing T17 / T17b unchanged (assert on `ReconcileReport`, not logs) — pass.
- `tests/core/monitoring_session/test_service.py` 22 pass; ruff + mypy clean.

RN: RN-EXE-1.20.1-20260609.
