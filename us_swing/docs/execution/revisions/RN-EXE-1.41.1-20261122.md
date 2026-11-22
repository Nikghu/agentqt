# Revision Note — RN-EXE-1.41.1-20261122

**Version:** 1.41.1
**Date:** 2026-11-22
**Tool:** EXE (also GUI)
**Artifact:** FO-EXE-011 / SRD-EXE-011.001
**Type:** Bugfix (ISS-EXE-0015)

---

## Summary

The strategy engine saved its status by replacing the whole strategies table with its in-memory list. That list left out Disabled strategies, so each save deleted them. BOSS_Short_New and BOSS_Long_New were deleted on 2026-11-20 at 11:47:02 ET, and their rules cannot be recovered. The status save now updates only each strategy's run state, and the Strategies tab reloads the engine after an add or delete.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-011.001.M01 | `src/us_swing/execution/strategy_engine/_engine.py` | Status save uses the run-state saver only; the strategies table is no longer replaced |
| MD-EXE-011.001.M01 | `src/us_swing/gui/strategy_store.py` | Existing `set_run_state(name, run_state)` (unchanged) is now the engine's status saver; it updates one strategy's run state |
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | Engine gets `registry_saver=set_run_state` |
| MD-GUI-024.004.M04 | `src/us_swing/gui/strategies_pane.py` | Engine reloads after add or delete |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-011.001 | Strategy engine owns the registry; persisted run state is trusted on load | Implemented |

SRD row is not edited (status Implemented).

---

## Design Decisions

- The engine writes only run state. Add, edit and delete of strategies go through the strategy store only.
- The deleted rules are not recoverable: backups are older and the deleted rows were overwritten.

---

## Issues Resolved

- ISS-EXE-0015 (`docs/execution/issues/ISS-EXE-0015.md`). App check open (TODO T224).

---

## Test Coverage

- New: UT-EXE-011.001.M01.T08 (status save keeps Disabled strategies).
- Status per `docs/execution/UTCD.md` (Pass).
