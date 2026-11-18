# Revision Note — RN-SCR-2.10.0-20261118

**Version:** 2.10.0
**Date:** 2026-11-18
**Tool:** SCR (with GUI)
**Artifact:** FO-SCR-011 / SRD-SCR-013.010–.011, FO-GUI-022 / SRD-GUI-022.014–.015
**Type:** Feature

---

## Summary

AI Ranking can now use Claude Code CLI as well as OpenRouter. Each preset saves its AI Provider; old presets open as OpenRouter. With Claude Code CLI the stocks are ranked in one CLI request with the features and the Query (if any) in the prompt; the CLI cannot fetch extra candles, so the tool loop is OpenRouter only. A CLI failure or a bad answer gives the plain Stage 2 results with a note in the transcript. In Edit Preset the checkbox reads "Enable AI Ranking"; Top N, AI Provider and Model share one row and Query has its own row. Switching provider swaps in that provider's default model unless the user typed their own; Validate checks the chosen provider answers. The Model box is a dropdown of the chosen provider's models (OpenRouter list with your custom models, or Sonnet / Haiku / Opus 5.5 for Claude) and still takes a typed ID; a chevron in the box opens the list (the app theme draws combos without an arrow) and typing shows matching models.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-SCR-001.001.M01 | `src/us_swing/screener/preset.py` | Added: `ai_provider`, provider check; model format checked only for OpenRouter |
| MD-SCR-002.003.M06 | `src/us_swing/screener/screeners/cloud_ai.py` | Added: `_apply_claude()`, `_claude_instruction()`, shared `_RANKING_FORMAT` |
| MD-SCR-003.001.M10 | `src/us_swing/screener/executor.py` | Changed: Stage 3 config carries `ai_provider` |
| MD-GUI-022.001.M01 | `src/us_swing/gui/screener_panel.py` | Changed: AI Ranking box layout, AI Provider combo, Model dropdown, provider-aware Validate |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-SCR-013.010 | Preset AI Provider | Implemented (approved by user 2026-11-18) |
| SRD-SCR-013.011 | Claude Code CLI ranking path | Implemented (approved by user 2026-11-18) |
| SRD-GUI-022.014 | AI Ranking box layout and provider choice | Implemented (approved by user 2026-11-18) |
| SRD-GUI-022.015 | Model dropdown per provider | Implemented (approved by user 2026-11-18) |

---

## Tests

9 new UT cases Pass (UT-SCR-013.010.M01.T01–T02, .011.M06.T01–T02, .011.M10.T01, UT-GUI-022.014.M01.T01–T02, UT-GUI-022.015.M01.T01–T02). Ruff clean on new code; no new mypy errors. Layout checked by an offscreen screenshot.

## Known

- `test_preset.py` T17/T18 already failed before this change (they expect an old default model name).
- `test_llm_claude_screener.py` imports a removed module and cannot be collected (old issue).
- A real Claude Code CLI ranking run in the app is still to be checked by the user.
