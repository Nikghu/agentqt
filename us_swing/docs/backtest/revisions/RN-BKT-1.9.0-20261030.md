# Revision Note — RN-BKT-1.9.0-20261030

**Version:** 1.9.0
**Date:** 2026-10-30
**Tool:** BKT
**Artifact:** FO-BKT-002 / SRD-BKT-002.070–.073
**Type:** Feature

---

## Summary

Phase 4b report extras. Each report now adds average MAE, MFE, profit given back (MFE minus P&L), median and longest hold; breakdowns by hold time, score bucket and rank; robustness numbers (Monte Carlo of trade order, 1,000 runs, seed 7: bad 5% / median / good 5% max drawdown; first vs second half P&L; P&L without the top 5 trades); and a return grid of capital × per-trade % when the variants differ in both. Shadow P&L for skipped signals is left out (needs an engine change).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.040.M13 | `backtest/steps/report.py` | `exit_hold_stats()`, `robustness_stats()`, `heat_map()`, new groups, `Report.per_trade_pct` |
| MD-BKT-002.008.M05 | `backtest/service.py` | `build_reports()` sets `per_trade_pct` from the variant's first strategy |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.070 | MAE, MFE, profit given back, hold time | Implemented |
| SRD-BKT-002.071 | Groups by hold time, score bucket and rank | Implemented |
| SRD-BKT-002.072 | Monte Carlo drawdown, halves, without top 5 | Implemented |
| SRD-BKT-002.073 | Capital × per-trade % return grid | Implemented |

---

## Tests

8 new tests, Pass. Real run (IT, Jan–Oct 2026, 103 trades): trades held 3 h–1 day lost $1,009 while under-3 h trades made $462; P&L without the top 5 trades -$1,093.73; Monte Carlo max drawdown -26% to -46%.
