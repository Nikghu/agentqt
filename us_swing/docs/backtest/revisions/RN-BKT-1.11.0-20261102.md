# Revision Note — RN-BKT-1.11.0-20261102

**Version:** 1.11.0
**Date:** 2026-11-02
**Tool:** BKT
**Artifact:** FO-BKT-001, FO-BKT-002 / SRD-BKT-001.016, SRD-BKT-002.037, SRD-BKT-002.083–.085
**Type:** Feature

---

## Summary

Adds a 30m timeframe to the backtest store and Step 2, a one-file HTML report for a saved run (trade analysis layout), and a candle loading progress callback for Step 3. Also fixes ISS-BKT-0001: the last equity row was saved before the test-end closes, so Net P&L was about $14 too high.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.083.M15 | `backtest/html_report.py` | New: offline HTML report of a saved run (`run_facts`, trade analysis layout, inline hover script) |
| MD-BKT-002.008.M05 | `backtest/service.py` | `BacktestService.export_html` writes the report from saved run rows |
| MD-BKT-002.030.M12 | `backtest/steps/portfolio.py` | `run_portfolio` loading callback; `_Sim.finish()` closes test-end positions before the last equity row (ISS-BKT-0001) |
| MD-BKT-001.001.M01 | `backtest/store.py` | `_to_30m`, `_build_from_3m`: 30m built from 3m, 13 bars a day from 09:30 ET |
| MD-BKT-002.021.M10 | `core/expr/series.py` | Step 2 conditions accept 30m; a 30m bar is visible only after it closes |
| MD-BKT-002.026.M11 | `backtest/steps/signals.py` | 30m frame loaded for Step 2 |

Cross-tool note: `core/dates.py` now gives DD-MM-YYYY engine error dates. Its MD row is MD-GUI-031.083.M14 (see GUI RN-GUI-1.54.0-20261102).

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.083 | Saved run can be written as one offline HTML report | Implemented |
| SRD-BKT-002.084 | HTML report uses the trade analysis layout | Implemented |
| SRD-BKT-001.016 | Store keeps 30m candles built from saved 3m candles | Implemented |
| SRD-BKT-002.085 | Step 2 conditions can use 30m; visible at bar close | Implemented |
| SRD-BKT-002.037 | Test-end closes are in the last equity row (ISS-BKT-0001) | Implemented |
| (none given) | Step 3 candle loading progress (UT-BKT-002.030.M12.T03) | Done — no SRD ID in session input |

---

## Design Decisions

- 30m follows the same closed-bar rule as 15m (SRD-BKT-002.050, SRD-BKT-002.085).
- Engine error dates use DD-MM-YYYY via `core/dates.py`; stored data stays ISO.

---

## Issues Resolved

- ISS-BKT-0001 (`docs/backtest/issues/ISS-BKT-0001.md`): last equity row saved before test-end closes, Net P&L about $14 too high. Fixed in `steps/portfolio.py` `_Sim.finish()`; UT-BKT-002.037.M12.T02 Pass.

---

## Test Coverage

15 UT cases, all Pass: UT-BKT-001.016.M01.T01–T02, UT-BKT-002.030.M12.T03, UT-BKT-002.037.M12.T02, UT-BKT-002.083.M15.T01–T09, UT-BKT-002.085.M10.T01, UT-BKT-002.085.M11.T01.

Real store: 503 stocks built to 30m in 29 s.
