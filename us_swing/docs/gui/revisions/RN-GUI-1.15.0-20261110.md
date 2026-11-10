# Revision Note — RN-GUI-1.15.0-20261110

**Version:** 1.15.0
**Date:** 2026-11-10
**Tool:** GUI
**Artifact:** FO-GUI-035 / SRD-GUI-035.012
**Type:** Enhancement

---

## Summary

AI Desk → Team at work now matches the Final draft design look. Pipeline cards have an icon, a clear border and dot chips; drawn arrows join the columns; the run numbers are stat tiles; Live, Event log and Team are underline tabs with icons; Right now, the pipeline, the wheel and the profile sit in bordered panels; chevron icons replace the platform arrows. Data and actions do not change.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-035.001.M01 | `gui/ai_desk_team.py` | Card icons and borders, `FlowArrow`, stat tiles, tabs, panels, Right now dot |
| MD-GUI-035.007.M04 | `gui/ai_desk_team_pane.py` | `panel()`, `chip_style()`, `chip_text()`, `tab_style()`, chevron arrows, avatar shape |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-035.012 | Team at work clean look | Implemented |

---

## Tests

UT-GUI-035.002.M01.T01 updated for the stat tile values. AI Desk and sidebar suites: 89 pass, 1 fail (`test_main_window_lists_screens`, already failing on main — T141).
