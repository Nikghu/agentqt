# Revision Note — RN-GUI-1.59.1-20261105

**Tool:** GUI
**Version:** 1.59.1
**Date:** 2026-11-05
**Type:** enhancement
**Author:** Claude Opus 5.5 under user direction
**Phase:** Test AI button removed from Settings → Telegram

---

## Summary

User asked to remove the Test AI button (screenshot, 2026-11-05). The button, its note line, the background test call and its test are gone. The AI cards, status lines, AI Fallback and the Apply gate are unchanged; the "Found on this PC" check runs when Settings opens. The AI notes client (`ask_ai`, FO-INF-011) stays and is used by the Morning brief.

## Changes

| File | Change |
|---|---|
| `gui/ai_settings_block.py` | Test AI button, note, worker relay and handlers removed |
| `tests/gui/test_ai_settings_block.py` | UT-GUI-033.007.M01.T01–T02 removed |

## Requirements

SRD-GUI-033.007 marked Removed by user request; SRD-GUI-033.006 text no longer mentions Test AI.

## Verification

GUI and notification tests pass; ruff and mypy --strict clean on `ai_settings_block.py`.
