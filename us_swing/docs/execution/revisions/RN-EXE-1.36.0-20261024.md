# Revision Note — RN-EXE-1.36.0-20261024

**Version:** 1.36.0
**Date:** 2026-10-24
**Tool:** EXE
**Artifact:** FO-EXE-020 (part of FO-GUI-025, Phase 4 of 5) / SRD-EXE-020.007–.008
**Type:** Feature

---

## Summary

Adds the equity curve used by the dashboard Account Equity band. The curve is built from the closed cycles for longer ranges, and from today's equity snapshots plus a live point for 1D. `AppService.get_equity_curve(range)` returns the viewing scope's curve using market time zone boundaries.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-020.001.M01 | `us_swing/src/us_swing/execution/equity_snapshot.py` | Added frozen `CurvePoint` and `curve_from_closed()` (steps at each close, ends at current equity) |
| MD-EXE-020.004.M02 | `us_swing/src/us_swing/gui/app_service.py` | Added `get_equity_curve(range_key)`; 1D from snapshots plus live point; longer ranges from closed cycles; no DB read on every account update |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-020.007 | Pure curve from closed cycles, starting at equity minus realised P&L in range and ending at current equity | Implemented |
| SRD-EXE-020.008 | `get_equity_curve(range_key)` for 1D, 1W, 1M, 3M, YTD for the viewing scope | Implemented |

---

## Design Decisions

- Longer-range curve uses realised P&L only; it ignores unrealised P&L and deposits (known limit).
- One market time zone is used for all range boundaries.

---

## Issues Resolved

None

---

## Test Coverage

6 UT cases (UT-EXE-020.007–.008) — all Pass (2 for .007, 4 for .008). Part of suite 1012 passed, 2 skipped.
