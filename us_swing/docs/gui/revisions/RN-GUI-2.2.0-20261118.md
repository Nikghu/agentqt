# Revision Note — RN-GUI-2.2.0-20261118

**Version:** 2.2.0
**Date:** 2026-11-18
**Tool:** GUI
**Artifact:** FO-GUI-022 / SRD-GUI-022.013
**Type:** Improvement

---

## Summary

Screener results for Accumulation / Distribution showed "RULES · 0 OF 3" with the short names RallyVol, DropVol and UD. These are numbers, not pass/fail rules, so the count was misleading. They now show as "Rally volume 1.34×", "Drop volume 1.67×" and "Up/down ratio 0.77", each with a one-line tooltip. A stock with only numbers shows the heading "Details" and no count; the list row shows no "0/3". Pass/fail rules are counted as before, without any numbers mixed in.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-022.001.M01 | `src/us_swing/gui/screener_views.py` | Added: `RuleCheck.tip`, shown names for RallyVol / DropVol / UD, `ResultRow.rule_count` and `rules_text`; tooltips on detail lines and card chips |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-022.013 | Plain names for number-only details; numbers not counted as rules | Implemented (approved by user 2026-11-18) |

---

## Tests

UT-GUI-022.013.M01.T01–T02 added; UT-GUI-022.011.M01.T01 updated to "1 OF 2" (its RSI value is a number). 28 screener view tests pass. Ruff and mypy --strict clean.
