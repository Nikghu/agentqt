# Revision Note — RN-EXE-1.28.0-20260612

**Version:** 1.28.0
**Date:** 2026-06-12
**Tool:** EXE
**Artifact:** SRD-EXE-016.007
**Type:** Bugfix (ISS-EXE-0008)

---

## Summary

A same-day re-entry left an open `trade_cycle` with no `ENTERED`
`monitoring_session` ledger row, so the daily reconcile logged
`[Lifecycle] Invariant violation during reconcile` for the re-entered symbols
(seen for CCL and SW on 2026-06-12). `mark_entered` only advanced rows still in
`MONITORING` state, so once a symbol had been entered and exited the same day its
row was `EXITED` and a second entry silently no-opped. `mark_entered` now re-arms
the most-recent `EXITED` row back to `ENTERED` when no open `MONITORING` row
exists, keeping the reconcile invariant (open position ⇒ `ENTERED` row).

---

## Behaviour Changes

- **Same-day re-entry tracked.** A completed entry fill for a symbol that was
  already entered and exited today re-arms its `EXITED` ledger row to `ENTERED`
  (with the new `trade_id`) instead of leaving it `EXITED`.
- **`exited_at` cleared on (re-)entry.** `transition_to_entered` now sets
  `exited_at = NULL`, so a re-armed `ENTERED` row carries no stale exit timestamp.
  No effect on the normal `MONITORING → ENTERED` path (it was already `NULL`).
- **No more spurious reconcile ERROR.** Re-entered symbols no longer appear in
  `orphan_open`, so the invariant-violation ERROR stops firing for them.
- Unchanged: first entries, exits, idempotency, and the no-op for an unscreened
  symbol with no ledger row.

---

## Code Changes

| File | Change | SRD |
|---|---|---|
| `core/monitoring_session/_service.py` | `mark_entered` falls back to `fetch_latest_exited_row(symbol)` when no open `MONITORING` row exists, then re-arms it to `ENTERED` | SRD-EXE-016.007 |
| `core/monitoring_session/_repository.py` | New `fetch_latest_exited_row(symbol)` (latest `EXITED` row, `session_date DESC`); `transition_to_entered` now sets `exited_at=None` | SRD-EXE-016.007 |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-016.007 | On a completed entry fill with no open `MONITORING` row, `mark_entered` re-arms the most-recent `EXITED` row back to `ENTERED` (same-day re-entry) | Implemented |

---

## Tests

| Check | Result |
|---|---|
| `tests/core/monitoring_session/test_service.py` — UT-EXE-016.007.M01.T01 (re-arm `EXITED → ENTERED`) + T02 (no-op without `MONITORING`/`EXITED`) | 24 passed |
| `ruff` | clean on changed files |
| `mypy --strict` | clean on `_service.py` and `_repository.py` |
| Code review (`code-reviewer`) | APPROVE — no BLOCK issues |

---

## Notes / Deviations

- `fetch_latest_exited_row` has no date filter. Under the current caller this is
  safe — entries fire only for symbols monitored today, which carry a fresh
  `MONITORING` row handled by the first branch — but a future non-screened caller
  of `mark_entered` could resurrect a prior-day `EXITED` row. Recorded in
  ISS-EXE-0008 as a caller-side invariant to revisit.
- The 12 unrelated test failures in `tests/execution` (candle loader, tick worker,
  strategy-evaluator function-map count) pre-date this change and were already
  present in the working tree; none import `monitoring_session`.

---

**Commit:** pending — Refs: SRD-EXE-016.007
