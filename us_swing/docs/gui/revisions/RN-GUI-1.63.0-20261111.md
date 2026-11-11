# Revision Note — RN-GUI-1.63.0-20261111

**Version:** 1.63.0
**Date:** 2026-11-11
**Tool:** GUI
**Artifact:** FO-GUI-038 / SRD-GUI-038.001–.003
**Type:** Feature

---

## Summary

The app now feeds the desk's plan stocks and SPY into its live bar feed. Held stocks come first, within the 100-stock cap. The app also writes its open trades to `desk.db` when they change, so the desk watchers can see them.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-038.001.M01 | `src/us_swing/gui/app_service.py` | Changed: desk live symbols in the bar feed; open trades published to `desk.db` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-038.001 | Live bar feed also covers desk plan stocks and SPY | Implemented |
| SRD-GUI-038.002 | Open trades written to `desk.db` at start and when they change | Implemented |
| SRD-GUI-038.003 | Adding desk stocks to the live feed logs how many were added | Implemented |

---

## Design Decisions

- The app writes only the open trades list to `desk.db`; the write runs on a background thread.
- A write that fails logs a warning and does not stop the app.

---

## Issues Resolved

None

---

## Test Coverage

UT-GUI-038.* — 5 cases, all Pass. Full suite: 12 failed (same as TODO T112), plus the old collection error in `tests/screener/test_llm_claude_screener.py` (TODO T136).
