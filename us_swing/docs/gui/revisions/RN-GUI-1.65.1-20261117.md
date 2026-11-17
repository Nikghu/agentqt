# Revision Note — RN-GUI-1.65.1-20261117

**Version:** 1.65.1
**Date:** 2026-11-17
**Tool:** GUI
**Artifact:** FO-GUI-000 / SRD-GUI-000.010
**Type:** Bugfix

---

## Summary

Small windows no longer flash at app start. The sidebar detail labels, the screener list chart box and Save As in Edit Preset were shown before they had a parent, so they appeared as tiny windows. Each widget is now shown only when needed. The PyInstaller quiet-platform runtime hook was also removed on the user's call; the built app may flash a console again on Python 3.11 (checked later, T192).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-000.010.M01 | `src/us_swing/gui/sidebar.py` | Changed: detail labels hidden until needed, not shown before parent |
| MD-GUI-000.010.M01 | `src/us_swing/gui/screener_views.py` | Changed: list chart box and Save As hidden until needed |
| MD-GUI-000.010.M01 | `src/us_swing/gui/screener_panel.py` | Changed: Save As in Edit Preset shown only when needed |
| — | `us_swing/pyi_rth_quiet_platform.py` | Removed: PyInstaller runtime hook; spec and installer yaml entries removed too |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-000.010 | No stray small windows appear at app start | Draft |

---

## Design Decisions

- A widget is hidden only when needed; never call `setVisible(cond)` before the widget has a parent.
- `pyi_rth_quiet_platform.py` removed on the user's call. `run_gui.py` still calls `quiet_platform.install()`. SRD-GUI-000.007 left as is.

---

## Issues Resolved

ISS-GUI-0020

---

## Test Coverage

UT-GUI-000.010.M01.T01–T03 — 3 cases, all Pass (`tests/gui/test_no_stray_windows.py`); T01–T03 fail on the old code. User checked the app: no flashing. Built-installer console check pending (T192).
