# Revision Note — RN-MKT-0.5.0-20261106

**Version:** 0.5.0
**Date:** 2026-11-06
**Tool:** MKT
**Artifact:** FO-MKT-005 (regime view skill) / SRD-MKT-005.001–.005
**Type:** Feature

---

## Summary

The first AI skill is the **regime view**. After each desk run, the employee that uses it reads:
- the rule-based regime for the last 20 days;
- breadth, fear and VIX;
- sector ranks and quadrants;
- today's idea counts and the latest score proof.

It answers with a typed view (regime, confidence, 1–3 reasons, a brief) and keeps it in `regime_view`. The brief goes to the AI feed under the employee's current name, with a plain note when the view disagrees with the rule regime. It runs on the P5a desk harness (RN-DSK-0.2.0-20261106).

Employee names, titles, levels and reporting lines are data the Master user can change. The code knows only the skill (user, 2026-11-06). The shipped default employee has a generic level-based name, "Expert 1".

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-005.001.M01 | `us_swing/src/us_swing/market/regime_view.py` | New: `RegimeViewSkill` (key `regime_view`: facts, freshness check, act) and the `RegimeView` schema |
| MD-MKT-005.003.M02 | `us_swing/src/us_swing/market/store.py` | Changed: `regime_view` table, `write_regime_view()`, `read_frame()` takes parameters |
| MD-MKT-005.005.M03 | `us_swing/src/us_swing/market/employees/emp-001/soul.md`, `job.yaml` | New: default expert-level employee (id `emp-001`, name "Expert 1", skill `regime_view`; Claude CLI primary, OpenRouter backup, 3 calls a day, USD 3 a month); the soul uses `{name}` and `{title}` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-005.001 | Facts from desk.db; fresh only when the regime day equals the latest SPY candle day. | Implemented |
| SRD-MKT-005.002 | Typed view: regime, confidence 0–1, 1–3 reasons, brief of at most 400 characters. | Implemented |
| SRD-MKT-005.003 | View kept in `regime_view` with the rule regime and whether they agree. | Implemented |
| SRD-MKT-005.004 | Brief in the AI feed under the employee's current name, with a plain note on disagreement. | Implemented |
| SRD-MKT-005.005 | A default expert-level employee for the regime view ships with a generic name, trigger `after_run`. | Implemented |

---

## Design Decisions

- No employee names or titles appear in code, tests or labels. The skill never knows who runs it (user, 2026-11-06).
- All answer limits are in the JSON schema the model sees (reason length 140, at most 3 reasons). This was found in the real runs.

---

## Issues Resolved

None

---

## Test Coverage

- UT-MKT-005.*: 17 tests (`tests/market/test_regime_view.py`) Pass. They use real P1–P3 steps on synthetic candles, a fake model and a made-up employee name.
- Real run 2026-11-06 (Claude Code CLI, claude-haiku-5-5) as default employee "Expert 1" (`emp-001`): view Choppy, confidence 0.6, agreeing with the rule regime; valid on try 2 (try 1 gave 4 reasons, so the default soul now says "1 to 3 reasons", version 2). The roster, `activity` and `briefs` hold the id and the name.
