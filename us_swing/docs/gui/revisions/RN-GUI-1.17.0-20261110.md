# Revision Note — RN-GUI-1.17.0-20261110

**Version:** 1.17.0
**Date:** 2026-11-10
**Tool:** GUI
**Artifact:** FO-GUI-034 / SRD-GUI-034.067
**Type:** Enhancement

---

## Summary

AI Desk sections move from the left panel to a row of underline tabs at the bottom of the header card: Command, Team at work, Hiring, Pages, Reports, Results, Cost & budget, Desk settings. The Command tab shows the waiting count. The left panel no longer shows an AI Desk menu (replaces SRD-GUI-018.012 for AI Desk).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-034.059.M33 | `gui/ai_desk.py` | Tab row, tab and list kept in step, count on the Command tab; `nav` removed |
| MD-GUI-018.012.M05 | `gui/main_window.py` | No `add_sub_nav()` call for AI Desk |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-034.067 | AI Desk section tabs | Implemented |

---

## Tests

2 new tests, 1 updated. Full GUI suite: 868 pass, 1 fail (`test_main_window_lists_screens`, already failing on main — T141).
