# Revision Note — RN-GUI-1.37.1-20261027

**Version:** 1.37.1
**Date:** 2026-10-27
**Tool:** GUI
**Artifact:** SRD-GUI-000.007 / ISS-GUI-0008
**Type:** Fix

---

## Summary

The packaged app no longer flashes small console windows at start. Python's Windows-version check is answered without running `cmd /c ver`.

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-000.007.M01 | `gui/quiet_platform.py` | New `install()` |
| — | `pyi_rth_quiet_platform.py` | New PyInstaller runtime hook |
| — | `run_gui.py` | Calls `install()` first |
| — | `usswing_installer.yaml` | `--runtime-hook pyi_rth_quiet_platform.py` |

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-000.007 | No console window flash at start | Implemented (approved by user 2026-10-27) |

## Tests

UT-GUI-000.007.M01.T01–T03. GUI suite 502 passed. Scratch build: 0 `cmd /c ver` calls at start (was 2).

## Known

Takes effect only after the installer is rebuilt; the released v1.6.0 still flashes.
