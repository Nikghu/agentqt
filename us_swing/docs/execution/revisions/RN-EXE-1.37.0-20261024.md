# Revision Note — RN-EXE-1.37.0-20261024

**Version:** 1.37.0
**Date:** 2026-10-24
**Tool:** EXE
**Artifact:** FO-EXE-017 (part of FO-GUI-025, Phase 5 of 5) / SRD-EXE-017.027
**Type:** Bugfix

---

## Summary

The paper account state is now dynamic instead of fixed at Max Capital. Start-of-day equity is Max Capital, daily P&L is the realised P&L of cycles closed today (ET), and equity is Max Capital plus daily P&L plus unrealised P&L. Cash is Max Capital plus daily P&L minus deployed capital, and gross is market value. Positions are filtered to the viewing user, so other users' broker positions are not counted.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-017.016.M14 | `us_swing/src/us_swing/gui/app_service.py` | Added `_paper_account_state()` and `_realised_today()`; paper equity, cash, daily P&L and gross follow today's closed cycles and open positions |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-017.027 | Paper account state follows today's realised P&L and open positions, filtered to the user | Implemented |

---

## Design Decisions

- Daily P&L counts only cycles closed today in the market time zone (ET).
- Sizing still uses `effective_capital`; the account state is for display and KPIs only.

---

## Issues Resolved

None

---

## Test Coverage

3 UT cases (UT-EXE-017.027.M14.T01–T03) in `tests/gui/test_capital_allocation_gui.py` — all Pass. T03 covers the review fix: other users' broker positions are ignored.

Known limit: realised P&L from earlier days is not carried, so the paper account restarts at Max Capital each market day. Sizing still uses effective_capital.
