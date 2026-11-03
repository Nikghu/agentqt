# Issue Report — ISS-GUI-0016

**Tool:** GUI
**Severity:** Low (look and feel; Delete Preset also showed an empty name)
**Status:** Resolved (user check pending)
**Date Opened:** 2026-11-03
**Date Resolved:** 2026-11-03
**Resolution:** RN-GUI-1.57.1-20261103
**Reporter:** User — "why this pop has old style can you fix it"

---

## Symptom

Delete Preset opened a native Windows message box (OS title bar, system icon) over the dark app, and asked `Delete preset ""?` with an empty name. 26 other popups in 6 panels had the same native style.

## Root Cause

| Point | Detail |
|---|---|
| 27 calls used `QMessageBox` | Written before the frameless `_ConfirmDialog` existed; never moved over |
| Empty preset name | `_on_delete_preset` read `item.text()`, but preset rows are drawn by a `PresetItem` widget, so the item text is blank |

**SRD root cause:** no requirement said every popup must use the app's style. SRD-GUI-000.009 added (approved by user, Implemented).

## Fix

| File | Change |
|---|---|
| `gui/popups.py` (new) | `confirm()` and `notify()` on the shared `_ConfirmDialog` |
| 7 panel files | All 27 popups call the helpers; same wording |
| `gui/screener_panel.py` | Delete Preset reads the name from the row widget |
