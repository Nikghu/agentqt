# Revision Note — RN-GUI-1.12.0-20261107

**Version:** 1.12.0
**Date:** 2026-11-07
**Tool:** GUI
**Artifact:** FO-GUI-034 / SRD-GUI-034.059–.064 (and reopened SRD-GUI-034.034–.036)
**Type:** Feature

---

## Summary

AI Desk now looks like the approved design (Option 1, screen 1B). The section list is grouped (TALK, TEAM, WORK, CREATE, REVIEW, SETUP) with a waiting-ask count on Command. The header shows the last run and today's AI spend with a month budget bar. The lead chat shows bubbles. Command's approvals are feed cards, Today's runs is real (no more sample table) and a Team now line shows employee counts.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-034.059.M33 | `gui/ai_desk.py` | Grouped list, Command badge, header chips and spend bar, chart signal |
| MD-GUI-034.060.M34 | `core/desk_overview.py` (new) | Today's runs, last run, spend, team counts |
| MD-GUI-034.061.M35 | `gui/ai_desk_chat.py` | Chat bubbles, "Message the lead" |
| MD-GUI-034.062.M36 | `gui/ai_desk_hiring.py` | `WaitingBox` of feed cards replaces `TradePickRow` |
| MD-GUI-034.062.M36 | `gui/ai_desk_sections.py` | `runs_box`, `team_line`, real Command frame |
| MD-GUI-034.062.M36 | `gui/floor_feed.py`, `core/desk_feed.py` | Qty on pick cards; `ask_cards()` |
| MD-GUI-034.059.M33 | `gui/main_window.py` | AI Desk chart link to Charts |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-034.059 | Grouped section list and Command badge | Implemented |
| SRD-GUI-034.060 | Header: last run and AI spend bar | Implemented |
| SRD-GUI-034.061 | Chat bubbles | Implemented |
| SRD-GUI-034.062 | Approval cards in Command | Implemented |
| SRD-GUI-034.063 | Real Today's runs | Implemented |
| SRD-GUI-034.064 | Team now line | Implemented |
| SRD-GUI-034.034–.036 | Reopened by user; trade picks now as cards, same rules | Implemented |

---

## Design Decisions

- The heading stays "Approvals waiting" (SRD-GUI-034.031 names it); the count is added.
- No "Next wake" chip: the wake times live in the desk process, which the GUI must not import.
- Event runs are one summed row with the worst result.

---

## Tests

9 new tests Pass (`tests/gui/test_ai_desk_design.py`); trade pick and hire approval tests moved to cards. GUI, desk and market suites pass except the old sidebar list test (same on main).
