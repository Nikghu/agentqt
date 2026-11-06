# Revision Note — RN-MKT-0.5.0-20261106

**Version:** 0.5.0
**Date:** 2026-11-06
**Tool:** MKT
**Artifact:** FO-MKT-005 (ATLAS part) / SRD-MKT-005.001–.005
**Type:** Feature

---

## Summary

ATLAS, the first AI expert, is the desk's market regime expert. After each desk run it reads the rule-based regime (last 20 days), breadth, fear and VIX, sector ranks and quadrants, today's idea counts and the latest score proof. It answers with a typed view (regime, confidence, 1–3 reasons, a brief), keeps it in `atlas_view`, and posts the brief to the AI feed. It says so when it disagrees with the rule regime. It runs on the P5a desk harness (RN-DSK-0.2.0-20261106).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-005.001.M01 | `us_swing/src/us_swing/market/atlas.py` | New: `Atlas` (facts, freshness check, act) and `AtlasView` schema |
| MD-MKT-005.003.M02 | `us_swing/src/us_swing/market/store.py` | Changed: `atlas_view` table, `write_atlas()`, `read_frame()` takes parameters |
| MD-MKT-005.005.M03 | `us_swing/src/us_swing/market/employees/atlas/soul.md`, `job.yaml` | New: ATLAS soul and job (Claude CLI primary, OpenRouter backup, 3 calls a day, USD 3 a month) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-005.001 | Facts from desk.db; fresh only when the regime day equals the latest SPY candle day. | Implemented |
| SRD-MKT-005.002 | Typed view: regime, confidence 0–1, 1–3 reasons, brief of at most 400 characters. | Implemented |
| SRD-MKT-005.003 | View kept in `atlas_view` with the rule regime and whether they agree. | Implemented |
| SRD-MKT-005.004 | Brief in the AI feed, with a plain note when ATLAS disagrees. | Implemented |
| SRD-MKT-005.005 | Ships `soul.md` and `job.yaml`, trigger `after_run`. | Implemented |

---

## Design Decisions

- The reason length (140 characters) is in the JSON schema the model sees, not only checked in code. This was found in the first real run.
- ATLAS uses only `core` types and never imports the desk harness.

---

## Issues Resolved

None

---

## Test Coverage

- UT-MKT-005.*: 16 tests (`tests/market/test_atlas.py`) Pass. They use real P1–P3 steps on synthetic candles and a fake model.
- Real run 2026-11-06 (Claude Code CLI, claude-haiku-5-5): view Choppy, confidence 0.55, agreeing with the rule regime. Brief: "Breadth leans up, with 65 new highs against 3 new lows and VIX calm at 16.6. But the rule regime has been Choppy for 10 days and tech is lagging, so the signals conflict. I call it Choppy with moderate confidence." Every number in it is in the facts.
