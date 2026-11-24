# Revision Note — RN-EXE-1.42.3-20261124

**Version:** 1.42.3
**Date:** 2026-11-24
**Tool:** EXE
**Artifact:** FO-EXE-022 / SRD-EXE-022.005
**Type:** Bugfix

---

## Summary

The installed v1.14.0 app failed at start with "No module named 'usswing'". The start chain imports the indicator check (`core/indicator_plugins/_check.py`), which needs the `usswing` library in `us_swing/sdk/`. The build rewrites `USSwing.spec` from `usswing_installer.yaml`, and the sdk path was only ever added to the spec, so each build dropped it. The YAML now adds the sdk path and the `sdk/usswing` data files, so the installed app ships the library.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| — (installer config, no MD row) | `us_swing/usswing_installer.yaml` | `package.extra_paths` set to `src;sdk`; added `--add-data sdk/usswing/*.py;sdk/usswing` to `package.pyinstaller_extra_args` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-022.005 | Plugin check module imports `usswing`; the installed build must ship the library | Implemented |

---

## Design Decisions

- `usswing_installer.yaml` is the source of truth for PyInstaller options. `USSwing.spec` is rewritten on every build, so edits made only to the spec are lost.

---

## Issues Resolved

None

---

## Test Coverage

Pending. No new tests (packaging config only). The YAML was checked to load and to give the expected PyInstaller arguments. No build has been run yet. Installed-app check is open (TODO T239, T240).
