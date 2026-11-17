# Issue Report — ISS-GUI-0020

**Tool:** GUI
**Severity:** Low (small windows flash for a moment)
**Status:** Resolved (user check pending)
**Date Opened:** 2026-11-17
**Date Resolved:** 2026-11-17
**Resolution:** SRD-GUI-000.010 (Draft)
**Reporter:** User — "check if we have still similar problem when we launch the tool GUI flash comes"

---

## Symptom

Same kind of flash as the AI feed fix (982d38e5): small windows show for a split second when the app starts and when a saved preset is opened for editing.

## Root Cause

| Point | Detail |
|---|---|
| Show before parent | A widget made visible before it has a parent is shown by Qt as its own top-level window until the next line adds it to a layout. |
| Places found | `sidebar.py` row detail labels (IBKR Feed, Market, Backtest data) and `screener_views.py` chart box at app start; `screener_panel.py` Save As button when editing a preset. |

## Fix

| File | Change |
|---|---|
| `gui/sidebar.py` | Detail label only hidden when not needed |
| `gui/screener_views.py` | Chart box only hidden when there is no chart |
| `gui/screener_panel.py` | Save As only hidden for a new preset |
| `tests/gui/test_no_stray_windows.py` | UT-GUI-000.010.M01.T01–T03 watch for any window shown while building; all 3 fail on the old code |

## Console flash hook (`pyi_rth_quiet_platform.py`)

Removed on the user's call (2026-11-17), with its entries in `USSwing.spec` and `usswing_installer.yaml`. `run_gui.py` still calls `quiet_platform.install()`. Risk: in the built app the bundled setuptools hook runs before `run_gui.py`, and Python 3.11 still runs `cmd /c ver` in `platform.win32_ver()`, so a console flash at start may return (ISS-GUI-0008). Check with a built installer (T192); if it flashes, restore the hook from git. SRD-GUI-000.007 (Implemented) left as is.

## User step

Restart the app and watch the start; open a saved preset with Edit (T191).
