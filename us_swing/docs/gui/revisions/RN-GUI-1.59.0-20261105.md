# Revision Note — RN-GUI-1.59.0-20261105

**Version:** 1.59.0
**Date:** 2026-11-05
**Tool:** GUI
**Artifact:** FO-GUI-033 / SRD-GUI-033.001–.006
**Type:** Feature

---

## Summary

Settings → Telegram now starts with an AI notes block. The user can turn AI notes on, tick Claude Code CLI and/or OpenRouter, pick a default and an optional fallback, and set models. Apply and OK stay off until the AI settings are valid. The OpenRouter key is stored in the OS keychain, shared with the Cloud AI screener key. This note adds the settings only; the AI notes service itself is not built yet.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-033.001.M01 | `gui/ai_settings_block.py` | New: Enable AI notes tick, Claude and OpenRouter cards, fallback rule, problem text, readiness checks, Test AI (local check) |
| MD-GUI-033.004.M02 | `gui/settings_panel.py` | AI block at top of Telegram page; save and load; keychain error kept non-fatal with a note; Telegram dot warns when default AI not ready; `valid_changed` / `is_valid` |
| MD-GUI-033.004.M02 | `gui/settings_dialog.py` | Apply enabled when dirty and valid; OK enabled when valid; tooltip when blocked |
| MD-GUI-033.005.M03 | `gui/user_store.py` | Save and load the AI fields per user; no key written to users.json |
| MD-GUI-033.005.M03 | `data/models.py` | `UserProfile.ai_*` fields with defaults (AI off) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-033.001 | Telegram page starts with an Enable AI notes tick and two cards (Claude Code CLI, OpenRouter) | Implemented |
| SRD-GUI-033.002 | Each card has Use tick, Default radio, model choice and status; OpenRouter also has an API key field | Implemented |
| SRD-GUI-033.003 | Default only on a ticked provider; fallback only when both are ticked | Implemented |
| SRD-GUI-033.004 | Apply and OK disabled while the AI settings are not valid; hint names what is missing | Implemented |
| SRD-GUI-033.005 | AI settings saved per user on Apply; key kept in OS keychain, never in users.json | Implemented |
| SRD-GUI-033.006 | Telegram dot shows warn when AI notes are on and the default AI is not ready | Implemented |

---

## Design Decisions

- OpenRouter key reuses the Cloud AI screener key store, so one key serves both. A blank key field never deletes the stored key.
- OpenRouter key field is locked when the `OPENROUTER_API_KEY` environment variable is set.
- Test AI is a local check only (`claude` program found on PATH). A live AI call waits for the AI notes service.
- Known gap (low, not fixed): an unknown saved Claude model falls back to Sonnet without a message.

---

## Issues Resolved

None

---

## Test Coverage

UT-GUI-033.* (11 rows) all Pass. 13 tests in `tests/gui/test_ai_settings_block.py`; GUI suite 691 passed; ruff clean; no new mypy errors. pyqt-code-reviewer WARNING items fixed. Not yet checked in the real app window (TODO T98).
