# Revision Note — RN-GUI-1.28.0-20261024

**Version:** 1.28.0
**Date:** 2026-10-24
**Tool:** GUI
**Artifact:** FO-GUI-025 (Phase 5 of 5) / SRD-GUI-025.016–.018
**Type:** Bugfix

---

## Summary

Phase 5 of the dashboard tiled workspace fixes three KPI and table faults. The Open Positions table now has a Side column (LONG blue, SHORT orange) after Symbol, so a short that shows a loss is clear. An unset stop shows "No stop" and an unset target shows "—". The "P&L Today" KPI is now equity minus start-of-day equity, so it counts realised and unrealised P&L.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-025.016.M04 | `us_swing/src/us_swing/gui/position_table_model.py` | Added Side column after Symbol (LONG blue / SHORT orange); unset stop shows "No stop", unset target shows "—" |
| MD-GUI-025.001.M02 | `us_swing/src/us_swing/gui/dashboard_panel.py` | Column widths for the new Side column; "P&L Today" uses equity minus start-of-day equity |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-025.016 | Open Positions table shows a Side column (LONG or SHORT) right after Symbol | Implemented |
| SRD-GUI-025.017 | Stop shows "No stop" in amber and Target shows "—" when the value is not set | Implemented |
| SRD-GUI-025.018 | "P&L Today" KPI is equity minus start-of-day equity (realised and unrealised) | Implemented |

---

## Design Decisions

- Side is a separate column, not a colour on the Symbol, so the P&L sign reads correctly for shorts.
- An unset stop or target is any value of 0 or missing.

---

## Issues Resolved

None

---

## Test Coverage

3 UT cases (UT-GUI-025.016.M04.T01–T02, UT-GUI-025.018.M02.T01) in `tests/gui/test_dashboard_tiles.py` — all Pass.

Known limit: IBKR-synced positions have stop 0, so they show "No stop".
