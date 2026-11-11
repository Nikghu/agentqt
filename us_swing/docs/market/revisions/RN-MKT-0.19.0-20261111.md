# Revision Note — RN-MKT-0.19.0-20261111

**Version:** 0.19.0
**Date:** 2026-11-11
**Tool:** MKT
**Artifact:** FO-MKT-017 / SRD-MKT-017.001–.010
**Type:** Feature

---

## Summary

Step F of the autonomous desk, skill 3: sentiment research. A `sentiment` ticket reads news for up to 30 stocks from the latest ideas and open trades, and gives each stock a tone card (supports, neutral, against or none). Cards show in the lead's plan prompt; idea scores never change. Steps run in order: pick (AI), gather (code), judge (AI). Gain means at least one stock is against its side.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-017.001.M01 | `src/us_swing/market/sentiment.py` | New: pick, gather and judge steps, result, gain, logs |
| MD-MKT-017.004.M02 | `src/us_swing/market/sentiment_news.py` | New: stored headlines first, fetch only gaps within the budget, record lines |
| MD-MKT-017.006.M03 | `src/us_swing/market/sentiment_cards.py` | New: `sentiment_cards` table, card saving, lead cards block |
| MD-MKT-005.014.M08 | `src/us_swing/market/lead_brief.py` | Changed: lead plan facts show the cards block |
| MD-MKT-017.001.M01 | `src/us_swing/market/employees/emp-015/` | New: default employee "Expert 12", skill `sentiment`, trigger `research_done` |
| MD-MKT-017.001.M01 | `SKILL_PATHS`, `USSwing.spec` | Changed: skill path added; build includes the new modules |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-017.001 | The sentiment skill works `sentiment` tickets in three steps: pick, gather and judge | Implemented |
| SRD-MKT-017.002 | The pick step shows the latest listed and watch ideas and open trades, and asks for up to 30 stocks | Implemented |
| SRD-MKT-017.003 | Code keeps only chosen stocks that are in that list; none left ends the ticket `failed` | Implemented |
| SRD-MKT-017.004 | The gather step uses stored headlines of the last 7 days; fetches only for stocks with none in the last 3 days | Implemented |
| SRD-MKT-017.005 | The judge step gives each stock a tone for its side with a short reason, and a summary | Implemented |
| SRD-MKT-017.006 | Each judged stock is saved as a sentiment card; unknown stocks dropped; idea scores not changed | Implemented |
| SRD-MKT-017.007 | The lead plan facts show the newest card of the last 7 days for each idea it may pick | Implemented |
| SRD-MKT-017.008 | The ticket ends `done` with tones and summary; gain is yes when at least one stock is against its side | Implemented |
| SRD-MKT-017.009 | Default employee `emp-015` ("Expert 12", skill `sentiment`) ships; skill path in `SKILL_PATHS` and the app build | Implemented |
| SRD-MKT-017.010 | Each step logs the stock count, headlines fetched and stocks judged against | Implemented |

---

## Design Decisions

- Pick step: AI picks up to 30 stocks from the latest listed and watch ideas and open trades.
- Headlines: stored ones first (7 days, at most 5 per stock); Yahoo fetch only for stocks with none in 3 days, 90 s budget; fetched headlines are stored.
- Tone cards (supports, neutral, against, none) feed the lead's plan prompt only; scores never change.
- Code review fixes: cards made after the ideas day (weekend tickets) now show to the lead; any cards read problem gives an empty block so the lead plan never fails.

---

## Issues Resolved

None

---

## Test Coverage

UT-MKT-017.* — 22 cases, all Pass (`tests/market/test_sentiment.py`).

Real-data read-only check: 22 choices, 54 stored headlines read in 0.06 s, 9 stocks would be fetched.

Test runs by folder (`.venv`): market 486 pass; desk 347; core 276; AI Desk GUI files 194.
