# Revision Note — RN-GUI-1.57.1-20261103

**Tool:** GUI
**Version:** 1.57.1
**Date:** 2026-11-03
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** All popups in the app's frameless style (ISS-GUI-0016)

---

## Summary

27 popups in 7 panels opened native Windows message boxes. They now use the app's frameless popup
(title bar, accent bar, Cancel / confirm or one OK button). Accent: blue for questions and info, yellow
for warnings, red for deletes, live switch, force exit and errors. Wording and Yes / No behaviour are
unchanged. Delete Preset now shows the preset's name instead of `""`.

## Changes

| File | Change |
|---|---|
| `gui/popups.py` (new) | `confirm(parent, title, text, confirm_text, danger) -> bool`, `notify(parent, title, text, kind)` |
| `gui/settings_panel.py` | 8 popups |
| `gui/execution_panel.py` | 7 popups (Confirm Order → Submit, Confirm Force Exit → Exit) |
| `gui/strategies_pane.py` | 5 popups |
| `gui/screener_panel.py` | 2 popups; preset name from the row widget |
| `gui/position_monitor_panel.py`, `gui/dashboard_panel.py` | 2 popups each |
| `gui/sidebar.py` | 1 popup |
| `tests/gui/test_popups.py` (new) | UT-GUI-000.009.M01.T01–T02, M02.T01–T02 |
| `tests/gui/test_dashboard_tiles.py`, `test_settings_sections.py`, `test_sidebar_shell.py` | Patch the new helpers instead of `QMessageBox` |

## Requirements

SRD-GUI-000.009 (new, approved by user 2026-11-03, Implemented). `main_window._ConfirmDialog` (older copy) left as is.

## Verification

- `pytest tests/gui`: 649 passed; 22 `test_chart_workspace.py` errors pre-existing (same on main, TODO T92)
- `ruff`: no new findings in the changed files (44 vs 45 on main; the rest are older)
- Delete Preset popup rendered: frameless, red accent, name shown, Cancel / Delete
- Real-app check pending (TODO T96)
