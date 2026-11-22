# Revision Note — RN-EXE-1.41.2-20261123

**Version:** 1.41.2
**Date:** 2026-11-23
**Tool:** EXE (+ GUI, see RN-GUI-2.8.1-20261123)
**Artifact:** FO-EXE-011 / SRD-EXE-011.027
**Type:** Bugfix

---

## Summary

The BOSS_ST Swing Lookback check allowed only 1 to 20, so a value such as 22 was refused. The check is now 1 to 500, the same range the strategy builder form offers.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-011.001.M03 | `src/us_swing/execution/strategy_engine/_evaluator.py` | Swing Lookback check 1 to 500; message "BOSS_ST: Swing Lookback must be 1 to 500" |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-011.027 | BOSS_ST trigger indicator; Swing Lookback 1–500 (reopened 2026-11-22) | Implemented |

SRD row is not edited (status Implemented).

---

## Design Decisions

- The evaluator limit matches the GUI form limit (SRD-GUI-013.024).

---

## Issues Resolved

None

---

## Test Coverage

- UT-EXE-011.027.M03.T02 (bad arguments, lookback 0 and 501 refused): Pass.
- Execution tests: 384 passed.
- App check: TODO T226 (Swing Lookback 22 accepted).
