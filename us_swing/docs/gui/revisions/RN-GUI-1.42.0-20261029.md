# Revision Note — RN-GUI-1.42.0-20261029

**Version:** 1.42.0
**Date:** 2026-10-29
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.013
**Type:** Feature

---

## Summary

The Backtest Stocks tab now shows the session each list is traded for, and the data day it was built from. Before, one date was shown and it was easy to read the wrong day. Columns are now Session, Data up to and Stocks. The backend change is in RN-BKT-1.5.0-20261029 (SRD-BKT-002.051).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Stocks tab columns Session / Data up to / Stocks; heading "STOCKS FOR SESSION X · DATA UP TO Y CLOSE · N" |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.013 | Stocks tab shows Session, Data up to and Stocks for each screener day | Implemented |

---

## Design Decisions

- User (2026-10-29): session = the day the list is traded (see SRD-BKT-002.051).

---

## Issues Resolved

None

---

## Test Coverage

- New: UT-GUI-031.013.M03.T01 — Pass.
- With `tests/backtest` (126 passed in total). `ruff` clean; `mypy` no errors in changed files.
- Real-window check: MCHP shown under session 2026-10-06, data 2026-10-05.
