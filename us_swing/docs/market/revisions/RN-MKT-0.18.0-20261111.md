# Revision Note — RN-MKT-0.18.0-20261111

**Version:** 0.18.0
**Date:** 2026-11-11
**Tool:** MKT
**Artifact:** FO-MKT-016 / SRD-MKT-016.001–.011
**Type:** Feature

---

## Summary

Step F of the autonomous desk, skill 2: pick post-mortem research. A `post_mortem` ticket studies closed lead picks, losers and winners, and writes per-pick notes, up to 3 candidate lessons and up to 2 follow-up tickets. Steps run in order: pick (AI), gather (code), study (AI). Gain means at least one lesson was saved.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-016.001.M01 | `src/us_swing/market/post_mortem.py` | New: pick, gather and study steps, lessons, follow-ups, logs |
| MD-MKT-016.004.M02 | `src/us_swing/market/post_mortem_facts.py` | New: stored facts per pick, daily bars (Backtest Data first, then candles.db), price path |
| MD-MKT-016.001.M01 | `src/us_swing/market/employees/emp-014/` | New: default employee "Expert 11", skill `post_mortem`, trigger `research_done` |
| MD-MKT-016.001.M01 | `SKILL_PATHS`, `USSwing.spec` | Changed: skill path added; build includes the new modules |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-016.001 | The post-mortem skill works `post_mortem` tickets in three steps: pick, gather and study | Implemented |
| SRD-MKT-016.002 | The pick step shows closed lead picks of the last 30 days (at most 120, newest first) and asks for up to 10 losers and 5 winners | Implemented |
| SRD-MKT-016.003 | Code keeps only chosen picks that exist, are closed and have the right sign of R; fewer than 2 losers ends the ticket `failed` | Implemented |
| SRD-MKT-016.004 | The gather step builds one record per pick from stored desk facts, with no tokens | Implemented |
| SRD-MKT-016.005 | Code adds each pick's price path (entry gap, best and worst move in R, SPY move); Backtest Data first, candles.db only for missing days | Implemented |
| SRD-MKT-016.006 | The study step makes one AI call: a note per pick, up to 3 candidate lessons, up to 2 follow-ups and a summary | Implemented |
| SRD-MKT-016.007 | A lesson is stored as a candidate only when all its proof picks were studied | Implemented |
| SRD-MKT-016.008 | Follow-up tickets go to the research queue in the name of the lead that raised the post-mortem | Implemented |
| SRD-MKT-016.009 | The ticket ends `done` with notes and summary; gain is yes when at least one lesson was saved | Implemented |
| SRD-MKT-016.010 | Default employee `emp-014` ("Expert 11", skill `post_mortem`) ships; skill path is in `SKILL_PATHS` and the app build | Implemented |
| SRD-MKT-016.011 | Each step logs the pick count, lessons kept and follow-ups raised | Implemented |

---

## Design Decisions

- Pick step: AI picks up to 10 losers and 5 winners from closed lead picks of the last 30 days (120 shown at most).
- Bars: Backtest Data first; candles.db only for days it lacks.
- Study outputs: per-pick notes, up to 3 candidate lessons (kept only if all proof picks were studied), up to 2 follow-up tickets in the raising lead's name.
- Follow-ups of kind `post_mortem` are dropped, so no chains.
- Code review fixes: wider candles.db error catch; `post_mortem` follow-ups dropped (no chains).

---

## Issues Resolved

None

---

## Test Coverage

UT-MKT-016.* — 22 cases, all Pass (`tests/market/test_post_mortem.py`). Follow-up tickets use UT-DSK-010.015 (see RN-DSK-0.12.0-20261111).

Real-data check: records for real picks build in 0.2 s. Only 1 closed lead pick exists so far, so a real ticket needs more closed picks (TODO T166).

Test runs by folder (`.venv`): market 464 pass; desk 347; core 276; AI Desk GUI files 194.
