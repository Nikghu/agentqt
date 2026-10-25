# Revision Note — RN-GUI-1.33.0-20261025

**Version:** 1.33.0
**Date:** 2026-10-25
**Tool:** GUI
**Artifact:** FO-GUI-027 req 8 / SRD-GUI-027.002, .005, .012 (reopened and revised)
**Type:** Enhancement (user design choice: Option B, https://claude.ai/artifact/U2hKfHTWMvQVoW85QU7Nm4)

---

## Summary

Updates is no longer a Settings section. A new **Updates** item in the sidebar, below the Connections panel, opens a small popup with "Installed v<version> · last checked <date time>", a Check for Updates button and a result note. The last check time is read from the saved stamp, so it covers the start-up check and earlier runs. When a check finds a new version, an amber dot shows on the item and the existing update dialog opens. The Settings dialog now has eight sections, and the Updates section dot is gone.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-027.005.M07 | `us_swing/src/us_swing/gui/update_popup.py` | New: `UpdatePopup`, `checked_text()` |
| MD-GUI-027.004.M02 | `us_swing/src/us_swing/gui/sidebar.py` | Updates item, popup wiring, found dot |
| MD-GUI-027.005.M04 | `us_swing/src/us_swing/gui/settings_panel.py` | Updates page, handlers and dot removed |
| — | `us_swing/src/us_swing/gui/theme.py` | `QFrame#update_popup` style |
| — | `us_swing/src/updater_stub.py` | New `last_check_time()` |

## Tests

UT-GUI-027.002.M04.T01 and .005.M04.T01 revised; UT-GUI-027.005.M07.T01–T04 and .005.M02.T01 added. GUI suite: 373 passed.
