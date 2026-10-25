# Revision Note — RN-GUI-1.32.0-20261025

**Version:** 1.32.0
**Date:** 2026-10-25
**Tool:** GUI
**Artifact:** FO-GUI-027 / SRD-GUI-027.001–.013 (new)
**Type:** Feature (user design choice: canvas Option 5 + Open A)

---

## Summary

Settings is no longer a screen. A **Settings** item at the bottom of the sidebar opens a frameless modal dialog over the current screen, with a title bar and a Restore defaults / Cancel / Apply / OK footer. The dialog lists nine sections: Users, Risk, Connection, Scheduler, Telegram, Universe, Candle data, Appearance and Updates. Each has a status dot. The System and Data side panels are gone: theme, updates and the candle database are now dialog sections. The right strip keeps Details, Watchlist and Log. While candles download, the sidebar Settings item shows the percent, a tick or !. Trip / Reset breaker moves to the Execution page header.

Edits are saved only on Apply or OK, and Cancel / Esc / ✕ drops them. A theme click is applied only on Apply. The per-section Save buttons are removed. One dialog is reused for the whole session, so a candle download keeps running after it closes.

Supersedes SRD-GUI-018.001 (five screens), SRD-GUI-021.001 (Settings page), SRD-GUI-021.003 (System panel) and SRD-GUI-021.004 (Data panel and strip badge).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-027.001.M01 | `us_swing/src/us_swing/gui/settings_dialog.py` | New: `SettingsDialog`, `open_at()`, footer, reject reverts |
| MD-GUI-027.004.M02 | `us_swing/src/us_swing/gui/sidebar.py` | `settings_requested`, Settings item, `set_data_state()` badge |
| MD-GUI-027.004.M03 | `us_swing/src/us_swing/gui/main_window.py` | Four screens; one reused dialog; `_RIGHT_PANELS` = details, watch; dots refreshed on feed and download changes |
| MD-GUI-027.005.M04 | `us_swing/src/us_swing/gui/settings_panel.py` | Nine sections; title, Save buttons, System panel and breaker removed; dirty tracking, `apply()`, `revert()`, `restore_defaults()`, `set_section_state()`, `refresh_states()`; section `load` methods |
| MD-GUI-019.001.M01 | `us_swing/src/us_swing/gui/side_panels.py` | System and Data buttons and data badge removed |
| MD-GUI-027.009.M05 | `us_swing/src/us_swing/gui/execution_header.py` | Trip / Reset breaker button |
| — | `us_swing/tests/gui/test_settings_dialog.py`, `test_settings_sections.py`, `test_sidebar_shell.py`, `test_execution_header.py`, `test_data_panel.py` | UT-GUI-027.* added; System / Data strip tests replaced |

---

## Verification

GUI suite 368 passed (351 before). `ruff` clean on changed files. `mypy --strict` clean on `settings_dialog.py`, `sidebar.py`, `side_panels.py` and `execution_header.py`, with no new errors on changed lines in `main_window.py` and `settings_panel.py` (80 old errors there). The dialog was rendered offscreen with a stub service (Risk, Appearance, Updates; dots and an unsaved edit) and checked. The full app was not launched: it would auto-connect the feed and fill the TWS login. The user should check the whole flow in the real app.
