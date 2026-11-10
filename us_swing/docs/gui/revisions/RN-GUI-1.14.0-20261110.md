# Revision Note — RN-GUI-1.14.0-20261110

**Version:** 1.14.0
**Date:** 2026-11-10
**Tool:** GUI
**Artifact:** FO-GUI-018 / SRD-GUI-018.012
**Type:** Feature

---

## Summary

The AI Desk section menu (Command, Team at work, Hiring, Pages, Reports, Results, Cost & budget, Desk settings) moves from its own 190 px column into the left sidebar, under the AI Desk item. It shows only while AI Desk is open and the sidebar shows labels (expanded, or on hover when small). The AI Desk page gets the freed width. Group headings are dropped so the menu fits without a scroll bar. The user chose this layout on 2026-11-10.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-018.012.M05 | `gui/sidebar.py` | `add_sub_nav()` and `_sync_subs()` |
| MD-GUI-034.009.M08 | `gui/ai_desk.py` | List no longer in the page layout; `nav` property; no headings; tighter rows |
| MD-GUI-018.005.M03 | `gui/main_window.py` | Places the AI Desk list under item 6 |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-018.012 | Screen sub-menu under its sidebar item | Implemented |

---

## Tests

UT-GUI-018.012.M05.T01–T02 added; UT-GUI-034.059.M33.T01 updated. Sidebar and AI Desk suites: 65 pass, 1 fail (`test_main_window_lists_screens`, already failing on main — T141).
