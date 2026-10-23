# Revision Note — RN-GUI-1.10.0-20261023

**Version:** 1.10.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-018 / SRD-GUI-018.001–007
**Type:** Feature

---

## Summary

Phase 2 of the Carbon Workspace redesign. The top navigation tabs and the admin context strip are replaced by a left sidebar with icon and label buttons, a collapse toggle and an account footer. The sidebar has a mini mode, auto-shrinks Execution and Chart, and reveals on hover without moving content.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-018.001.M01 | `gui/sidebar.py` | New left sidebar: nav buttons, collapse, mini mode, account footer |
| MD-GUI-018.006.M02 | `gui/reveal.py` | New RevealController: 200 ms hover reveal of registered widgets |
| MD-GUI-018.005.M03 | `gui/main_window.py` | Top tabs and context strip removed; sidebar wired; index prices moved to title bar; screen slide-in |
| — | `gui/theme.py` | Sidebar QSS added to all three themes |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-018.001 | Left sidebar replaces top navigation tabs | Implemented |
| SRD-GUI-018.002 | Sidebar mini mode 200 ↔ 56 px, saved in settings | Implemented |
| SRD-GUI-018.003 | Execution and Chart auto-shrink; user choice never overridden | Implemented |
| SRD-GUI-018.004 | Hover peek overlays the sidebar without moving content | Implemented |
| SRD-GUI-018.005 | Account footer shows scope, mode, IBKR, risk and capital | Implemented |
| SRD-GUI-018.006 | Reveal animates registered widgets 200 ms | Implemented |
| SRD-GUI-018.007 | Screen change slides in 24 px to 0 over 180 ms | Implemented |

---

## Design Decisions

- Hover peek floats the full sidebar over a width-reserving slot, so content does not move.
- Screen slide uses position only, no opacity, because of web views.
- Slide animation is stopped and deleted on replace (reviewer fix).
- SRD-GUI-018.* supersede layout parts of SRD-GUI-001.001, SRD-GUI-000.003 and the location of SRD-GUI-000.006. Old rows are unchanged per the status guard.

---

## Issues Resolved

None

---

## Test Coverage

9 new tests in `tests/gui/test_sidebar_shell.py`. Full GUI suite: 275 passed.

---

## Notes

- Deferred to Phase 3: right icon strip.
- Left out (minimal scope): animations on/off and sidebar mode setting.
- Phases 3–4 (panels with Exit drawer, Charts MDI) pending.
