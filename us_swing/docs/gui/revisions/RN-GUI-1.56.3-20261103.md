# Revision Note — RN-GUI-1.56.3-20261103

**Tool:** GUI
**Version:** 1.56.3
**Date:** 2026-11-03
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Popup headers stand out from the dialog body

---

## Summary

Popup title bars (Backtest setup, Settings, Scheduler, Strategy builder, Candle DB diagnostics,
confirm dialogs) looked the same colour as the dialog body. User picked option 1 of 4: a lighter
header strip with a divider line and a thin dialog border (Carbon theme).

## Changes

| File | Change |
|---|---|
| `gui/scheduler_dialog.py`, `gui/execution_panel.py`, `gui/strategy_builder_dialog.py` | Title bar classes set `WA_StyledBackground`, so their style-sheet background is painted at all |
| `gui/theme.py` | Carbon: dialog title bars `#1a2029` + `#2f3845` bottom line, `QDialog` border `#232a35`; title label transparent in Mocha and VS Code |

## Requirements

No SRD change: styling only, under FO-GUI-017 (Carbon workspace look). Main window title bar unchanged (rule matches title bars inside a `QDialog` only).

## Notes

- Root cause: custom `QWidget` subclasses do not paint a style-sheet background without `WA_StyledBackground`; the header colour in every theme was never shown.
- Mocha and VS Code popups now also show their (darker) header colour.

## Verification

- Rendered Settings dialog in Carbon: header `#1a2029` across full width, divider `#2f3845`
- `pytest tests/gui`: 629 passed; 22 errors in `test_chart_workspace.py` are pre-existing (same on main)
- `ruff` clean; `mypy` same count as main (260, pre-existing)
