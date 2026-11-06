# Revision Note — RN-MKT-0.6.0-20261106

**Version:** 0.6.0
**Date:** 2026-11-06
**Tool:** MKT
**Artifact:** FO-MKT-005 (P5b) / SRD-MKT-005.006–.018
**Type:** Feature

---

## Summary

P5b market AI skills, on the P5a desk harness (RN-DSK-0.3.0-20261106). Four new skills:
- `sector_flow_view`: which sectors to favour or avoid;
- `setup_review`: an A, B or C grade for each listed idea;
- `risk_check`: vetoes, after the hard limits in code have run;
- `lead_brief`: up to 5 picks per side from the passed ideas, and an evening brief.

The hard risk limits are constants in code (`risk_limits.py`). The AI can only add vetoes. The regime step now posts `regime_change` events. The shipped default employees are `emp-002` to `emp-005`, with generic level names.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-005.001.M01 | `us_swing/src/us_swing/market/regime_view.py` | Changed: `needs = ()` and `answer = RegimeView` on the skill |
| MD-MKT-005.006.M04 | `us_swing/src/us_swing/market/sector_view.py` | New: `SectorViewSkill` (key `sector_flow_view`): facts, answer schema, act |
| MD-MKT-005.009.M05 | `us_swing/src/us_swing/market/setup_review.py` | New: `SetupReviewSkill` (key `setup_review`): facts, grades, act |
| MD-MKT-005.011.M06 | `us_swing/src/us_swing/market/risk_limits.py` | New: hard limits as constants and `code_vetoes()` |
| MD-MKT-005.012.M07 | `us_swing/src/us_swing/market/risk_check.py` | New: `RiskCheckSkill` (key `risk_check`): code vetoes first, then AI vetoes |
| MD-MKT-005.014.M08 | `us_swing/src/us_swing/market/lead_brief.py` | New: `LeadBriefSkill` (key `lead_brief`): picks from passed ideas and the evening brief |
| MD-MKT-005.003.M02 | `us_swing/src/us_swing/market/store.py` | Changed: tables `sector_view`, `setup_review`, `risk_check`, `lead_picks` |
| MD-MKT-005.017.M09 | `us_swing/src/us_swing/market/employees/emp-002/` to `emp-005/` | New: default employees; each soul uses `{name}` and `{title}` |
| MD-MKT-001.011.M05 | `us_swing/src/us_swing/market/step.py` | Changed: after writing its rows, posts `regime_change` through `core/desk_events.py` when today's regime differs from the day before |
| MD-DSK-001.021.M07 | `us_swing/src/us_swing/core/desk_steps.py` | Changed: four new skill paths in `SKILL_PATHS` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-005.006 | Sector/flow facts: last 5 days of ranks and quadrants, 1- and 3-month relative moves, money flow per side, rule regime. Fresh only when the sector day equals the SPY day. | Implemented |
| SRD-MKT-005.007 | Sector/flow answer: 1 to 3 sectors to favour, 0 to 3 to avoid, rotation note up to 200 characters, brief up to 400. | Implemented |
| SRD-MKT-005.008 | Sector view kept in `sector_view` per data day; brief goes to the AI feed. | Implemented |
| SRD-MKT-005.009 | Setup review facts: listed ideas per side with score parts, setup, trigger, stop and reasons, plus rule regime. | Implemented |
| SRD-MKT-005.010 | Each idea gets grade A, B or C and a note up to 120 characters, kept in `setup_review`. Ideas not in the facts are dropped and logged. | Implemented |
| SRD-MKT-005.011 | Hard limits in code veto: long in Downtrend, short in Uptrend, stop under 1% or over 10% from trigger, trigger under $5, and more than 3 per sector per side. | Implemented |
| SRD-MKT-005.012 | Risk check AI reads the passed ideas and may add vetoes with a reason up to 120 characters. It cannot undo a code veto. | Implemented |
| SRD-MKT-005.013 | One `risk_check` row per listed idea per data day: pass or veto, by code or AI, and the reason. | Implemented |
| SRD-MKT-005.014 | Lead facts: the four views (a note for any missing one) and the passed ideas. | Implemented |
| SRD-MKT-005.015 | Lead answer: up to 5 picks per side, each with a reason up to 120 characters, and an evening brief up to 1,200 characters. | Implemented |
| SRD-MKT-005.016 | Picks kept in `lead_picks` per data day; evening brief goes to the AI feed as kind `evening`. | Implemented |
| SRD-MKT-005.017 | Default employees: `emp-002` "Expert 2" (sector/flow view), `emp-003` "Expert 3" (setup review), `emp-004` "Expert 4" (risk check), `emp-005` "Lead 1" (lead brief); all `after_run`. | Implemented |
| SRD-MKT-005.018 | The four new skills are added to the skill list in `core/desk_steps.py`. | Implemented |

---

## Design Decisions

- Hard limits are constants in code. No file an agent reads or writes holds them (SRD-MKT-005.011).
- Code vetoes are written before the AI is asked. A failed call, a used-up budget or a refusal leaves them in place; the day stays open so a later run can retry the review.
- The AI can only turn a pass into a veto. A code veto is never changed.
- The lead brief applies `code_vetoes()` again, so it never sees an idea that breaks a hard limit, even when no risk employee is hired.
- Skills name the views they need by function: the risk check needs regime, sector and setup; the lead needs all four.
- Skills never know which employee runs them, and the view tables have no employee column.
- After code review: when a second wake of the risk check gets no valid answer, it keeps the AI vetoes already stored for that day.
- No employee names in code or tests. Defaults use generic level names; the Master user can rename them.

---

## Issues Resolved

None

---

## Test Coverage

- UTCD P5b rows: 38 in `docs/market/UTCD.md`, all Pass. P5b overall (desk and market): 76 UTCD cases plus 10 extra, all Pass.
- Full suite: 2236 passed, 12 failed (the same old failures, T112), 2 skipped. Coverage of new modules 86–100% (total 95%).
- Real run 2026-11-06 (Claude Code CLI, claude-haiku-5-5) on a copy of the desk folder, data day 2026-11-04. All four employees answered validly on the first try, lead last. About 19,000 tokens in about 34 s; cost 0.
  - Sector view favoured Health Care and Consumer Staples.
  - Setup grades: A 3, B 13, C 4.
  - Risk check vetoed 15 of 20 ideas (14 by the hard limits, 1 by review); the lead picked 4 longs.
  - All 14 code vetoes were "stop over 10% from the trigger"; 12 were shorts with stops 10–68% away (see T124).
