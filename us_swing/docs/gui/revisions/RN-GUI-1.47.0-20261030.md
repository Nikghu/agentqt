# Revision Note — RN-GUI-1.47.0-20261030

**Version:** 1.47.0
**Date:** 2026-10-30
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.046–.048
**Type:** Feature

---

## Summary

Phase 4b in the Detail Report: a Risk panel (MAE, MFE, profit given back, hold time, Monte Carlo drawdown, halves, without top 5), three new Group by choices (Hold time, Score bucket, Rank), and a capital × per-trade % return heat map under Compare when it applies. Stat values of kind `hours` show as "5.8 h".

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.040.M04 | `gui/backtest_report_view.py` | `RiskFacts`; group names; heat map table; `hours` format |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Risk panel in the Detail Report |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.046 | Risk panel | Implemented |
| SRD-GUI-031.047 | Hold time, Score bucket and Rank groups | Implemented |
| SRD-GUI-031.048 | Capital × per-trade % heat map | Implemented |

---

## Tests

3 new tests; report view and workspace 52 pass. Real-window check by opening the newest saved run.
