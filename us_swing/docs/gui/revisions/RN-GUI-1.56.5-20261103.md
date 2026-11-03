# Revision Note — RN-GUI-1.56.5-20261103

**Tool:** GUI
**Version:** 1.56.5
**Date:** 2026-11-03
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Risk warning pop-up uses the app's frameless style

---

## Summary

The risk warning (for example "Margin Available differs from broker cash") opened as a native Windows
message box with OS chrome. It now uses the app's frameless themed pop-up with a yellow accent and one
OK button. It still never blocks and is still shown at most once per 30 s per warning kind.

## Changes

| File | Change |
|---|---|
| `gui/main_window.py` | `_on_risk_warning` shows the shared `_ConfirmDialog` (from `active_cycles_panel.py`, one-button mode, non-modal) instead of `QMessageBox` |
| `tests/gui/test_risk_warning_popup.py` | UT-EXE-017.013.M09.T01 (new) |

## Requirements

SRD-EXE-017.013 unchanged (non-blocking pop-up); fixes the GUI Window Style rule. MD-EXE-017.009.M09.

## Verification

- `pytest tests/gui/test_risk_warning_popup.py tests/gui/test_sidebar_shell.py`: 27 passed
- `ruff` clean on both files
- Pop-up rendered with the real message and theme; real-app check pending (TODO T93)
