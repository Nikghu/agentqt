# Revision Note — RN-GUI-1.13.0-20261110

**Version:** 1.13.0
**Date:** 2026-11-10
**Tool:** GUI
**Artifact:** FO-GUI-035 / SRD-GUI-035.001–.009
**Type:** Feature

---

## Summary

AI Desk has a new **Team at work** section that shows how the AI employee team works, from real desk records. It replaces the five sample sections (Org chart, Employees, Task board, Activity, Schedule). A run bar picks a desk run. The Live tab shows the run as a pipeline of stages or as a timeline of LLM calls, one at a time, with the working employee animated. The Event log tab lists each day's events, who they woke, the result, time and cost, and opens to every LLM call. The Team tab shows a 30-day scorecard. A side pane has a rolling team picker (Follow live) and the picked employee's profile.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-035.001.M01 | `gui/ai_desk_team.py` (new) | Section, run bar, tabs, pipeline, timeline, refresh |
| MD-GUI-035.002.M02 | `core/desk_team.py` (new) | Read model from job files and desk.db |
| MD-GUI-035.006.M03 | `gui/ai_desk_team_log.py` (new) | Event log tab |
| MD-GUI-035.007.M04 | `gui/ai_desk_team_pane.py` (new) | Team wheel, profile, scorecard |
| MD-GUI-035.001.M01 | `gui/ai_desk.py` | TEAM group = Team at work, Hiring; WORK group removed |
| MD-GUI-034.009.M08 | `gui/ai_desk_sections.py`, `gui/ai_desk_sections2.py`, `gui/ai_desk_sample.py` | Removed the sample frames and data they alone used |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-035.001 | Team at work replaces five sample sections | Implemented |
| SRD-GUI-035.002 | Run bar with ET and IST start and chips | Implemented |
| SRD-GUI-035.003 | Live tab with Pipeline / Timeline switch | Implemented |
| SRD-GUI-035.004 | Pipeline with state cards | Implemented |
| SRD-GUI-035.005 | Timeline of LLM calls | Implemented |
| SRD-GUI-035.006 | Event log tab | Implemented |
| SRD-GUI-035.007 | 30-day scorecard | Implemented |
| SRD-GUI-035.008 | Team wheel and profile | Implemented |
| SRD-GUI-035.009 | Read-only refresh every 3 s while shown | Implemented |

---

## Tests

12 new UTCD tests Pass (coverage: `core/desk_team.py` 94%, `ai_desk_team.py` 90%, `ai_desk_team_log.py` 89%, `ai_desk_team_pane.py` 98%). Updated: UT-GUI-034.009.M08.T01, UT-GUI-034.010.M03.T02, UT-GUI-034.059.M33.T01, UT-GUI-034.022.M19.T03 (eight sections). Retired: UT-GUI-034.009.M08.T02 (sample seats).

## Notes

- Real data showed the 2026-11-09 evening run failed for every employee: the Claude CLI login had expired.
- `tests/gui/test_sidebar_shell.py::test_main_window_lists_screens` fails on main too (not from this change).
