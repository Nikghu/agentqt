# Issue Report — ISS-GUI-0008

**Tool:** GUI (app start, packaged EXE)
**Severity:** Low (cosmetic; small console windows flash at start)
**Status:** Resolved
**Date Opened:** 2026-10-26
**Date Resolved:** 2026-10-27
**Reporter:** User ("small small window open and suddenly close within millisecond")
**Resolution:** RN-GUI-1.37.1-20261027
**Related:** FO-GUI-000

---

## Symptom

When the installed app starts, small windows open and close at once.

## Root Cause

Python 3.11 `platform.win32_ver()` runs `cmd /c ver`; in the windowed app each run flashes a console. Three callers at start: PyInstaller's setuptools runtime hook (setuptools import), pandas (`platform.machine()`), and keyring (Telegram token load). The code is old (pandas since May, Telegram since July 2026); not caused by recent changes.

**SRD root cause: SRD gap.** New SRD-GUI-000.007 (approved by user 2026-10-27).

## Fix

| File | Change |
|---|---|
| `gui/quiet_platform.py` | New. `install()` answers the version from `sys.getwindowsversion()` |
| `pyi_rth_quiet_platform.py` | New PyInstaller runtime hook; runs before the setuptools hook |
| `run_gui.py` | Calls `install()` before anything else loads |
| `usswing_installer.yaml` | Adds `--runtime-hook pyi_rth_quiet_platform.py` |

## Verification

`tests/gui/test_quiet_platform.py` — UT-GUI-000.007.M01.T01–T03. Scratch PyInstaller build with `COMSPEC` pointed at a logging exe: installed v1.6.0 ran `cmd /c ver` 2 times; fix in `run_gui.py` only → 1 (setuptools hook); fix + runtime hook → 0, window opens normally.
