# Revision Note — RN-GUI-1.16.0-20261110

**Version:** 1.16.0
**Date:** 2026-11-10
**Tool:** GUI
**Artifact:** FO-GUI-034 / SRD-GUI-034.065–.066
**Type:** Enhancement

---

## Summary

AI Desk gets the console card look of design Option A. The header has an icon, a state note, a dot state chip, one joined Start / Pause / Resume / Stop group and four tiles (Last run, Next run in ET and IST, AI spend today, Month budget). Hiring, Pages, Reports, Results, Cost & budget and Desk settings use stat tiles and titled icon cards. Command and Team at work are not changed. Data and actions do not change.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-034.065.M39 | `gui/ai_desk_console.py` | New: tiles, bars, icon cards, button looks, joined group |
| MD-GUI-034.059.M33 | `gui/ai_desk.py` | Header card, state note, four tiles |
| MD-GUI-034.002.M02 | `gui/desk_control.py` | Dot state chip, joined control group |
| MD-GUI-034.060.M34 | `core/desk_overview.py`, `core/desk_contract.py` | `next_evening_run()`; `EVENING_RUN` shared with `desk/clock.py` |
| MD-GUI-034.027.M21 | `gui/ai_desk_hiring.py` | Seat tiles, Hires / Start hire / Shadow report cards |
| MD-GUI-034.022.M19 | `gui/ai_desk_pages.py` | List and preview cards |
| MD-GUI-034.037.M25 | `gui/ai_desk_results.py` | Total tiles replace the summary line; table cards |
| MD-GUI-034.009.M08 | `gui/ai_desk_sections3.py` | Reports, Cost and Settings cards |
| MD-GUI-034.016.M15 | `gui/ai_desk_settings.py` | Claude Code CLI, OpenRouter API and Seats cards |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-034.065 | AI Desk header console look | Implemented |
| SRD-GUI-034.066 | Section tiles and icon cards | Implemented |

---

## Tests

5 new tests (`tests/gui/test_ai_desk_console.py`); 4 tests updated for tiles. AI Desk suites: 65 pass. Desk and core suites pass. Full GUI suite: 866 pass, 1 fail (`test_main_window_lists_screens`, already failing on main — T141).
