# Revision Note — RN-EXE-1.20.1-20260609

**Tool:** EXE
**Version:** 1.20.1
**Date:** 2026-06-09
**Author:** Claude Opus 4.8 under user direction
**Phase:** Bug fix — ISS-EXE-0003 (self-healed orphan ledger row logged at ERROR)

---

## Summary

The pre-open reconcile logged two `ERROR` lines for an orphaned `ENTERED` ledger
row (e.g. `CVS`) that was then immediately self-healed to `EXITED`. The errors
were misleading — the condition auto-recovers and is not a failure. Removed the
redundant summary log block; the per-symbol loop already logs `WARNING` for a
healed row and reserves `ERROR` for the genuinely un-healable case (an open cycle
with no `ENTERED` row).

## Code Changes

| File | Change | MD |
|---|---|---|
| `core/monitoring_session/_service.py` | `reconcile_preopen` — removed the `entered != keep.carryover` block that called `check_invariant()` (ERROR) + logged a second ERROR before the heal. Per-symbol logging (WARNING heal / ERROR orphan) is unchanged. | MD-EXE-009.002.M02 |

## Tests

| Check | Result |
|---|---|
| `UT-EXE-009.002.M02.T17e` (new) — healable orphan logs WARNING, no ERROR | Pass |
| `tests/core/monitoring_session/test_service.py` | 22 passed |
| `ruff` / `mypy --strict` | Clean on changed file |

## SRD Note

No SRD/DD change. SRD-EXE-010.003 already specifies per-symbol invariant
reporting plus self-heal; this only corrects the log level of an expected,
self-recovering condition. No cascade required.

---

**Commit:** branch `fix/exe-lifecycle-heal-log-level` — Refs: MD-EXE-009.002.M02 (ISS-EXE-0003)
