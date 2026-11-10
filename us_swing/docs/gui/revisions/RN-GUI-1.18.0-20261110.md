# Revision Note — RN-GUI-1.18.0-20261110

**Version:** 1.18.0
**Date:** 2026-11-10
**Tool:** GUI
**Artifact:** FO-GUI-035 / SRD-GUI-035.013–.014
**Type:** Enhancement

---

## Summary

The AI Desk no longer uses small coloured dots for status. A thin 3 px bar on the left edge, in the status colour, now shows the state. This covers the status pills (Failed, Done, Fired, No call, Asleep), the desk state chip (Sleeping, Off), the Last run tile, the Right now line and the This run and history lines. The user chose Option 3 out of 4 mock-ups.

The selected pipeline card and the selected Team row no longer use the amber border. They show a slightly lighter fill and a grey border (user chose Option A).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-035.007.M04 | `gui/ai_desk_team_pane.py` | `chip_style(key)` left bar; `chip_text(label)`; new `bar_style()`, `bar_rows()`, `lift_fill()`; wheel centre band uses the lift |
| MD-GUI-035.001.M01 | `gui/ai_desk_team.py` | Pipeline pill and Right now head use the bar; `now_dot` removed; selected card uses the lift |
| MD-GUI-035.001.M01 | `gui/ai_desk.py` | Last run value uses the bar |
| MD-GUI-035.001.M01 | `gui/desk_control.py` | Desk state chip uses the bar; `dot` removed |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-035.013 | AI Desk status bar instead of dot | Implemented |
| SRD-GUI-035.014 | Selected card lift instead of accent border | Implemented |

---

## Tests

2 new tests (UT-GUI-035.013.M04.T01, UT-GUI-035.014.M01.T01). AI Desk, Team and Floor GUI tests: 160 pass.
