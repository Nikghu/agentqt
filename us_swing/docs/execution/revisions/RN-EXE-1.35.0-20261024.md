# Revision Note — RN-EXE-1.35.0-20261024

**Version:** 1.35.0
**Date:** 2026-10-24
**Tool:** EXE
**Artifact:** FO-EXE-020 / SRD-EXE-020.001–.006
**Type:** Feature

---

## Summary

The app now saves an account equity snapshot every 5 minutes while the market is open, plus one closing point at 16:00 ET, so the dashboard can show equity over time. This is Phase 3 of 5 of FO-GUI-025 (dashboard tiles). Snapshots are stored in a new `equity_snapshots` table, keyed by user and 5-minute slot, and a daily prune keeps 30 days.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-020.001.M01 | `src/us_swing/execution/equity_snapshot.py` (new) | `equity_snapshots` table and index, frozen `EquitySnapshot`, `slot_iso()`, `EquitySnapshotRepository` with `record`, `record_many`, `between`, `prune`. |
| MD-EXE-020.001.M01 | `src/us_swing/db/schema.py` | Registers the table for `create_schema` and `drop_schema`. |
| MD-EXE-020.004.M02 | `src/us_swing/gui/app_service.py` | Store created and pruned at DB init; 60 s timer saves all users per slot; daily prune; `get_equity_snapshots(since_iso)`. |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-020.001 | Table `equity_snapshots` holds user, time, equity, cash and unrealised P&L, keyed by user and time. | Implemented |
| SRD-EXE-020.002 | `record` saves one row per user per 5-minute slot; `record_many` saves a whole slot in one transaction. | Implemented |
| SRD-EXE-020.003 | `between` returns points in time order, all users summed per slot, or one user. | Implemented |
| SRD-EXE-020.004 | While the market is open, one snapshot per user every 5 minutes, plus one closing slot; failed save logs one warning per slot. | Implemented |
| SRD-EXE-020.005 | Rows older than 30 days are deleted at start and once a day. | Implemented |
| SRD-EXE-020.006 | `get_equity_snapshots(since_iso)` returns points for the viewing user (all users when none). | Implemented |

---

## Design Decisions

- One transaction per slot: all users are saved together, so a slot is never half-written.
- A live IBKR account is saved once, under the active user.
- Database writes run in batches off the per-tick path, so the GUI thread does not block on each user.
- Known limit: paper equity is still the user's Max Capital until FO-GUI-025 Phase 5. Unrealised P&L is stored in its own column.

---

## Issues Resolved

None

---

## Test Coverage

17 unit tests UT-EXE-020.* in `tests/execution/test_equity_snapshot.py` — all Pass. Execution, GUI, core, integration and infrastructure suites: 996 passed, 2 skipped. Code review: no HIGH; 4 MEDIUM and LOW items fixed.
