# Revision Note — RN-GUI-1.15.2-20261023

**Version:** 1.15.2
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-017 / SRD-GUI-017.001
**Type:** Fix

---

## Summary

Shell icons looked small. Left sidebar icons are now 20 px (were 17 px). Right strip icons are now 20 px (were 16 px); the strip is 44 px wide with 36 px buttons (were 40 / 32), and the Log and Data badges moved with them.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-017 | `us_swing/src/us_swing/gui/sidebar.py` | Nav and collapse icons 20 px |
| MD-GUI-017 | `us_swing/src/us_swing/gui/side_panels.py` | Strip icons 20 px, strip 44 px, buttons 36 px, badge positions |

---

## Issues Resolved

- Sidebar and strip icons looked very small (user feedback).

---

## Test Coverage

No new tests (style only). GUI suite: 305 passed. Checked by a real-font render.
