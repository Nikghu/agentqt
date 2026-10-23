# Revision Note — RN-SCR-2.6.0-20261023

**Version:** 2.6.0
**Date:** 2026-10-23
**Tool:** SCR
**Artifact:** FO-SCR-011 / SRD-SCR-013.009
**Type:** Feature

---

## Summary

The tool-augmented AI ranking prompt now asks for an optional entry, stop and target price per stock. A plan is kept only when all three are finite numbers above zero, and is stored in `last_plan`. The executor saves a kept plan with the result as `ai_plan`, so the new GUI result views can show it. Old result files load unchanged, and the legacy single-shot path sets no plan.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-SCR-002.003.M06 | `us_swing/src/us_swing/screener/screeners/cloud_ai.py` | `_tool_system_prompt` asks for optional entry / stop / target; `_plan_from_entry` validates and fills `last_plan` |
| MD-SCR-003.001.M10 | `us_swing/src/us_swing/screener/executor.py` | Merges `last_plan` into `result.results[sym]["ai_plan"]` only where a plan is present |
| MD-SCR-002.003.M06 | `us_swing/tests/screener/test_cloud_ai_plan.py` | New file: UT-SCR-013.009.M06.T01–T03 |
| MD-SCR-003.001.M10 | `us_swing/tests/screener/test_executor.py` | UT-SCR-013.009.M10.T01 added |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-SCR-013.009 | Ranking prompt asks for optional entry, stop and target; all three positive numbers are kept as `ai_plan`, otherwise no plan | Implemented |

---

## Design Decisions

- All-or-nothing per symbol: if any of the three prices is missing or invalid, the symbol gets no plan. Its score and reasoning are still kept.
- The legacy single-shot path does not produce plans.

---

## Issues Resolved

None

---

## Test Coverage

4 new UTCD cases (UT-SCR-013.009.M06.T01–T03, UT-SCR-013.009.M10.T01), all Pass. Screener suite: 182 passed. ruff and mypy --strict: mypy errors in both changed files are unchanged (all pre-existing).

Failures that already existed and are not caused by this change: `tests/screener/test_llm_claude_screener.py` cannot import the removed module `screeners.llm_claude`; `tests/screener/test_preset.py::test_t17` and `test_t18` fail. Tracked in TODO T42.
