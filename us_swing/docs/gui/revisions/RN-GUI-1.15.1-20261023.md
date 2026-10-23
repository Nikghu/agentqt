# Revision Note — RN-GUI-1.15.1-20261023

**Version:** 1.15.1
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-017 / SRD-GUI-017.001
**Type:** Fix

---

## Summary

Shell text was smaller than the Carbon Workspace mockup. Sidebar items now use 10pt (were 9pt from the global button rule), the account footer 8.5pt (was 8pt), the title bar brand 10pt with normal letter spacing (was 9pt, spaced), and the index ticker 8.5pt names with 9pt / 8.5pt IBM Plex Mono prices and changes (names were 7pt, prices bold).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-017 | `us_swing/src/us_swing/gui/theme.py` | `side_btn` 10pt, `side_footer` 8.5pt, `top_brand` 10pt in all three themes |
| MD-GUI-019.002.M03 | `us_swing/src/us_swing/gui/main_window.py` | Ticker cell font sizes and mono prices |

---

## Issues Resolved

- Sidebar and title bar text looked small next to the mockup (user screenshot comparison).

---

## Test Coverage

No new tests (style only). GUI suite: 305 passed. Checked by a real-font render of the title bar and sidebar.
