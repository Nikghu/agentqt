# Revision Note — RN-INF-1.9.0-20261105

**Tool:** INF (+ GUI Test AI)
**Version:** 1.9.0
**Date:** 2026-11-05
**Type:** feature
**Author:** Claude Opus 5.5 under user direction
**Phase:** AI notes client — first basic AI call

---

## Summary

New `ask_ai()` sends one short request to the user's default AI and returns the answer text. Claude Code CLI runs headless (no tools, no saved session, no console window, subscription login, no API key in env); OpenRouter uses the shared Cloud AI key and the picked model. With AI Fallback on and both providers ticked, the other provider is tried when the default fails. It never raises: failures come back as error text. Settings → Telegram → Test AI now makes a real call in the background and shows the provider, time and answer, or the error. The Morning brief is not part of this.

## Changes

| File | Change |
|---|---|
| `core/notifications/_ai_client.py` | New: `AiConfig`, `AiAnswer`, `ask_ai()`, `provider_name()` |
| `core/notifications/__init__.py` | Exports the AI client |
| `gui/ai_settings_block.py` | Test AI runs `ask_ai` in a daemon thread; `ai_config()` helper |
| `tests/core/notifications/test_ai_client.py` | UT-INF-011.* (7 cases) |
| `tests/gui/test_ai_settings_block.py` | UT-GUI-033.007.M01.T01–T02 |

## Requirements

FO-INF-011 (approved by user 2026-11-05); SRD-INF-011.001–.003 and SRD-GUI-033.007 approved by user → Implemented.

## Verification

- 735 tests pass (core/notifications + gui); ruff clean; mypy --strict clean on the new and changed files.
- Live: `ask_ai` with Claude Code CLI (Haiku 5.5) answered "OK" in about 4 s; a 0.5 s timeout gave "Claude Code CLI: no answer in 0 seconds" and killed the process.
- Review (pyqt-code-reviewer): approve; 3 medium points fixed (error text, process-tree kill and system prompt file, no QThread at app exit).

## Known limits

- OpenRouter not called live (it would spend from the user's key); covered by a mock test.
- Timeout text rounds to whole seconds.
