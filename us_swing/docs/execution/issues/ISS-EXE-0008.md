# Issue Report — ISS-EXE-0008

**Tool:** EXE (Execution)
**Severity:** Medium (audit-only ERROR log; positions remain correct, but the monitoring ledger is out of sync for any re-entered symbol)
**Status:** Resolved
**Date Opened:** 2026-06-12
**Date Resolved:** 2026-06-12
**Reporter:** User (repeated "[Lifecycle] Invariant violation during reconcile" ERROR logs for CCL and SW)
**Resolution:** RN-EXE-1.28.0-20260612

---

## Symptom

The daily reconcile logged an ERROR for two symbols:

```
[Lifecycle] Invariant violation during reconcile: symbol=CCL
[Lifecycle] Invariant violation during reconcile: symbol=SW
```

Database evidence (`candles.db`, 2026-06-12):

| symbol | trade_cycles | monitoring_session |
|---|---|---|
| CCL | #27 CLOSED (20:45→20:46); **#33 OPEN (re-entered 22:17)** | one row, `EXITED`, trade_id = #27's order |
| SW  | #29 CLOSED (20:47→16:00); **#32 OPEN (re-entered 22:17)** | one row, `EXITED`, trade_id = #29's order |

Both symbols were entered, exited, then **re-entered the same day** by strategy
SUPERTREND. The open re-entry cycle had no `ENTERED` ledger row. (RCL, entered
once and never exited, did **not** error — its row was still `ENTERED`.)

## Root Cause

`MonitoringSessionService.mark_entered` (`core/monitoring_session/_service.py`)
resolved the ledger row to advance via `fetch_earliest_open_monitoring_row`,
which matches **only rows still in `MONITORING` state**:

```python
row = self._repo.fetch_earliest_open_monitoring_row(symbol)
if row is None:
    return            # silent no-op
```

The `monitoring_session` ledger holds one row per `(session_date, symbol)`. After
a symbol's first round-trip the row is `EXITED`. A same-day re-entry therefore
finds no `MONITORING` row and silently no-ops, so the re-opened cycle is left with
no `ENTERED` record. The daily reconcile computes
`orphan_open = carryover − entered` (open cycles minus ledger-`ENTERED` symbols)
and reports each orphan as `invariant_violation`. The reconcile deliberately does
not heal this direction (it never closes an open position), so it only logs.

## Fix

`mark_entered` falls back to re-arming the symbol's most-recent `EXITED` row back
to `ENTERED` when no open `MONITORING` row exists (SRD-EXE-016.007):

```python
row = self._repo.fetch_earliest_open_monitoring_row(symbol)
if row is None:
    row = self._repo.fetch_latest_exited_row(symbol)   # same-day re-entry
if row is None:
    return
self._repo.transition_to_entered(...)
```

`transition_to_entered` now also clears `exited_at` (sets it `NULL`) so a re-armed
row carries no stale exit timestamp. The method stays a no-op for a symbol with
neither a `MONITORING` nor an `EXITED` row.

## Affected Artifacts

| Artifact | Change |
|---|---|
| SRD-EXE-016.007 | **New** (Approved) — same-day re-entry re-arms an `EXITED` row back to `ENTERED` |
| DD-EXE-016.007.D01 | **New** — re-arm design + `exited_at` clear |
| MD-EXE-016.001.M01 | `mark_entered` re-arm fallback noted |
| MD-EXE-016.003.M04 | `fetch_latest_exited_row` added; `transition_to_entered` clears `exited_at` |
| `core/monitoring_session/_service.py` | `mark_entered` falls back to `fetch_latest_exited_row` |
| `core/monitoring_session/_repository.py` | `fetch_latest_exited_row` added; `transition_to_entered` sets `exited_at=None` |
| UT-EXE-016.007.M01.T01 | New positive — same-day re-entry re-arms `EXITED → ENTERED` (Pass) |
| UT-EXE-016.007.M01.T02 | New negative — no `MONITORING`/`EXITED` row stays a no-op (Pass) |

## Notes / Deviations

- Existing rows left in place: the CCL/SW ledger rows that triggered the log will
  re-arm to `ENTERED` on the next entry fill or stay `EXITED`; no historical data
  is corrupted (the open cycles in `trade_cycles` were always correct).
- `fetch_latest_exited_row` has no date filter, so in principle a prior-day
  `EXITED` row could be resurrected if `mark_entered` were ever called for a
  symbol not screened today. This is safe under the current caller (entries fire
  only for symbols monitored today, which carry a fresh `MONITORING` row handled
  by the first branch). Flagged by code review as a caller-side invariant to
  revisit if `mark_entered` gains a non-screened caller.
