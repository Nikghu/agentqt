# Revision Note — RN-DSK-0.2.0-20261106

**Version:** 0.2.0
**Date:** 2026-11-06
**Tool:** DSK (with GUI)
**Artifact:** FO-DSK-002–005 / SRD-DSK-002.001–.005, 003.001–.003, 004.001–.005, 005.001–.004; SRD-GUI-034.015–.017
**Type:** Feature

---

## Summary

P5a lean harness. AI employees are loaded from a `soul.md` (the prompt) and a `job.yaml` (rules enforced in code). A new desk step, "AI employees", runs after "Ideas". It wakes each employee at most once per data day, and only on fresh data. Every model call goes through one gateway:
- Sources are Claude Code CLI (subscription: tokens only, cost 0) and OpenRouter (API: has cost).
- Answers must match a schema. A bad answer is retried once, then the backup model is tried.
- A budget guard enforces the monthly API budget, a cap for each employee, calls per day, and a daily CLI token cap.

Every try is kept in an append-only `activity` table, and feed briefs in `briefs`. In the GUI, the AI feed shows real briefs, AI Desk → Desk settings edits the desk AI settings, and Cost & budget shows the real month.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-002.001.M08 | `us_swing/src/us_swing/core/desk_agents.py` | New: `Employee`, `AgentContext`, `Facts`, `FeedItem` |
| MD-DSK-002.002.M09 | `us_swing/src/us_swing/desk/registry.py` | New: job file schema, loading, `employees` table |
| MD-DSK-003.001.M10 | `us_swing/src/us_swing/desk/employees_step.py` | New: desk step "AI employees" with the wake rule |
| MD-DSK-004.001.M11 | `us_swing/src/us_swing/desk/gateway.py` | New: sources, schema check, retry, backup, recording |
| MD-DSK-004.003.M12 | `us_swing/src/us_swing/desk/budget.py` | New: budget, caps and token cap |
| MD-DSK-004.005.M13 | `us_swing/src/us_swing/core/desk_ai_settings.py` | New: `desk_ai.json` and the OpenRouter key in the keychain |
| MD-DSK-005.001.M14 | `us_swing/src/us_swing/desk/recorder.py` | New: append-only `activity` and `briefs` |
| MD-DSK-001.021.M07 | `us_swing/src/us_swing/core/desk_steps.py` | Changed: "AI employees" step path and `EMPLOYEE_PATHS` |
| MD-GUI-034.015.M14 | `us_swing/src/us_swing/core/desk_floor.py`, `gui/floor_feed.py`, `gui/market_floor.py` | Real AI feed, refreshed after each desk run |
| MD-GUI-034.016.M15 | `us_swing/src/us_swing/gui/ai_desk_settings.py`, `gui/ai_desk.py`, `gui/desk_control.py` | Editable desk AI settings; AI Desk uses the poller's desk folder |
| MD-GUI-034.017.M16 | `us_swing/src/us_swing/core/desk_floor.py`, `gui/ai_desk_sections3.py` | Real month cost, rebuilt each time the page opens |

Also: `USSwing.spec` bundles `market/employees` and lists the modules the desk loads by import path as hidden imports (the P1–P4 steps were missing too).

---

## Requirements Addressed

All SRDs listed above: Implemented. Rule from the user (2026-11-06): Claude Code CLI is a subscription, so only its tokens count (cost recorded as 0, daily token cap). Only API sources carry cost.

---

## Design Decisions

- A lean harness for P5a (user): there is only one trigger (`after_run`). The full router, market clock and replay come in P5b. LangGraph comes in P5b (user).
- Desk AI settings are separate from AI notes (user). Both sources start off. A `job.yaml` model of `default` means the model chosen in Desk settings.
- After code review: 4 tries per call; cost checks apply only to OpenRouter; a missing OpenRouter cost fails the try; a day is done only once a brief is posted; model names starting with `-` are refused; feed text is plain text; the keychain is not read at build time.

---

## Issues Resolved

None

---

## Test Coverage

- UT-DSK-002–005: 42 tests (`tests/desk/test_harness.py`) Pass. UT-GUI-034.015–.017: 6 tests Pass. The AI Desk sample-tag test now leaves out Desk settings (real from P5a).
- ruff and mypy --strict clean on changed files. Code review: code-reviewer NEEDS CHANGES (no high issues), fixed; pyqt-code-reviewer 2 high, fixed.
- Full suite: 2130 pass, 12 fail. The 12 are the same old failures (T112): candle_builder 9, sidebar_shell 1, preset 2.
- Real run (2026-11-06): desk run-now with Claude Code CLI (claude-haiku-5-5). ATLAS was recorded in `activity`: the first run had 2 invalid tries (a schema gap, fixed in ATLAS) and no backup, because OpenRouter was off. The second run gave a valid answer on try 2: about 3,400 tokens, 7 s, cost 0. Real app: the AI feed shows the ATLAS brief with no Sample tag; Cost & budget shows ATLAS 4 tries, 12,419 tokens, USD 0.00 API spend; Desk settings shows the saved values.
