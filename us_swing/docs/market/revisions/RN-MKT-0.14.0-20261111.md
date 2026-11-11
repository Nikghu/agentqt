# Revision Note — RN-MKT-0.14.0-20261111

**Version:** 0.14.0
**Date:** 2026-11-11
**Tool:** MKT
**Artifact:** FO-MKT-012 / SRD-MKT-012.001–.006
**Type:** Feature

---

## Summary

Step C of the autonomous desk, market side: the desk now learns from closed paper picks. A default employee "Expert 8" (`emp-010`) asks for up to 3 candidate lessons once a day, only on days with newly closed picks. The setup review, news review, risk check and lead brief read up to 5 active lessons in their prompts; if the memory fails they get plain facts only.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-012.002.M01 | `src/us_swing/market/lesson_reflect.py` | New: closed-pick stats by tag, reflect skill, answer form, candidate save, log line |
| MD-MKT-012.004.M02 | `src/us_swing/market/employees/emp-010/`, `src/us_swing/core/desk_steps.py` | New default employee Expert 8 (skill `lesson_reflect`); skill path added |
| MD-MKT-012.005.M03 | `src/us_swing/market/setup_review.py`, `news_review.py`, `risk_check.py`, `lead_brief.py` | Lessons block added at the end of the facts |
| MD-MKT-009.001.M01 | `src/us_swing/market/pick_results.py` | Changed: calls `review_lessons()` after results are written |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-012.001 | Stats of closed paper picks by side, setup, regime, sector, grade and news tone | Implemented |
| SRD-MKT-012.002 | The reflect skill asks for at most 3 candidates; fresh only on days with new closed picks | Implemented |
| SRD-MKT-012.003 | The answer is a typed form (text up to 200 characters, fixed tags, claim, 1–20 pick keys) | Implemented |
| SRD-MKT-012.004 | Default expert employee `emp-010` ("Expert 8") with trigger `after_run` | Implemented |
| SRD-MKT-012.005 | The four pick makers end their facts with the lessons block; regime and sector views get none | Implemented |
| SRD-MKT-012.006 | Each reflect run logs how many candidates were kept and dropped | Implemented |

---

## Design Decisions

- Unknown pick keys in a candidate are dropped; the rest of the candidate is kept.
- The Master may rename Expert 8; its files are copied only when missing.
- Lessons are advice to the pick makers only; the hard risk limits stay in code.

---

## Issues Resolved

None

---

## Test Coverage

UT-MKT-012.* — 13 cases, all Pass. Full suite: 12 failed (same as TODO T112), plus the old collection error in `tests/screener/test_llm_claude_screener.py` (TODO T136).
