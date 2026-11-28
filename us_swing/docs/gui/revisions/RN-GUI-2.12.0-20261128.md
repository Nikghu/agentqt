# Revision Note — RN-GUI-2.12.0-20261128

**Version:** 2.12.0
**Date:** 2026-11-28
**Tool:** GUI
**Artifact:** FO-GUI-031, FO-GUI-013, FO-GUI-006 / SRD-GUI-031.095–.097, SRD-GUI-013.025, SRD-GUI-006.024
**Type:** Feature + Bugfix

---

## Summary

Backtest Trade list now shows Cumulative P&L and a Cumulative P&L % and Sector column. Grow with P&L tick boxes appear in the backtest setup, the strategy builder and the user risk settings. Small fixes: setup help lines wrap, disabled tick boxes look greyed in all themes, and ticked boxes fill blue in the VS Code theme.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.002.M02 | `us_swing/src/us_swing/gui/backtest_builder.py` | Setup cards wrap help lines; Grow with P&L tick box in the Money card (SRD-GUI-031.097) |
| MD-GUI-031.053.M07 | `us_swing/src/us_swing/gui/backtest_trade_list.py`, `gui/backtest_workspace.py` | Total P&L renamed Cumulative P&L; Cumulative P&L % and Sector columns (SRD-GUI-031.095–.096) |
| MD-GUI-031.055.M09 | `us_swing/src/us_swing/gui/backtest_reports.py` | Report details row shows Grow with P&L (SRD-GUI-031.097) |
| MD-GUI-013.001.M01 | `us_swing/src/us_swing/gui/strategy_builder_dialog.py` | Grow with P&L tick box next to Per-Trade Size (SRD-GUI-013.025) |
| MD-GUI-006.001.M01 | `us_swing/src/us_swing/gui/settings_panel.py` | Grow all strategies with P&L tick box in user risk settings (SRD-GUI-006.024) |
| MD-GUI-017.001.M02 | `us_swing/src/us_swing/gui/theme.py` | Greyed disabled tick boxes in all themes; ticked boxes fill blue (#007acc) in the VS Code theme |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.095 | Backtest Trade list shows Cumulative P&L (was Total P&L) on each Exit row | Implemented |
| SRD-GUI-031.096 | Trade list adds Cumulative P&L % and a Sector column | Implemented |
| SRD-GUI-031.097 | Backtest Money card has a Grow with P&L tick box, saved in the run plan and shown in Report details | Implemented |
| SRD-GUI-013.025 | Strategy builder shows a Grow with P&L tick box next to Per-Trade Size | Implemented |
| SRD-GUI-006.024 | User risk settings show a Grow all strategies with P&L tick box | Implemented |

---

## Design Decisions

- Disabled tick boxes are greyed in every theme.
- VS Code theme: Strategies table and Sectors list tick boxes fill blue (#007acc) when ticked.

---

## Issues Resolved

None

---

## Test Coverage

- Pass: UT-GUI-031.095.M07.T01, UT-GUI-031.097.M02.T01, UT-GUI-031.097.M09.T01, UT-GUI-013.025.M01.T01, UT-GUI-006.024.M01.T01.

---

## Open items

- User check T273 (Cumulative P&L columns).
- User check T271 (VS Code theme tick boxes fill blue).
