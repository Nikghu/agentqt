# Revision Note — RN-BKT-1.6.0-20261029

**Version:** 1.6.0
**Date:** 2026-10-29
**Tool:** BKT
**Artifact:** FO-BKT-002 / SRD-BKT-002.040–.047
**Type:** Feature

---

## Summary

Phase 4a of the backtest engine: Step 4 Report. A saved run's results are read from `results.db` and turned into stats per variant (returns, risk, trade quality, breakdowns, skip counts, equal-weight benchmark, compare table), without running Steps 1–3 again. The benchmark is the equal-weight average daily return of the run's stocks, not SPY, as the user decided on 2026-10-29 (closes TODO T64). The rest of Phase 4 (MAE/MFE, Monte Carlo and more) is deferred to Phase 4b.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.040.M13 | `backtest/steps/report.py` | New: `build_report()`, `breakdown()`, `compare()`, `equal_weight_benchmark()`, `Report` / `Stat` |
| MD-BKT-002.007.M04 | `backtest/results.py` | `list_variants()` added to read variant labels from `results.db` |
| MD-BKT-002.008.M05 | `backtest/service.py` | `build_reports()`, `report_for_run()`, `variant_label()` added |

GUI side of SRD-BKT-002.040–.047 is in RN-GUI-1.43.0-20261029.

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.040 | Report reads a saved run from `results.db` and computes stats per variant without running Steps 1–3 again | Implemented |
| SRD-BKT-002.041 | Returns: net P&L, return %, CAGR, % of days with money deployed, P&L by month | Implemented |
| SRD-BKT-002.042 | Risk: max drawdown ($ and %), longest drawdown, Sharpe, Sortino, Calmar, worst day and worst trade | Implemented |
| SRD-BKT-002.043 | Trade quality: count, win rate, average win and loss, payoff, profit factor, expectancy, streaks | Implemented |
| SRD-BKT-002.044 | Breakdowns by strategy, stock, sector, exit reason, entry hour and weekday | Implemented |
| SRD-BKT-002.045 | Capital use: entries taken and each skip reason, counted from the day log | Implemented |
| SRD-BKT-002.046 | Benchmark: capital grown by the equal-weight average daily return of the run's stocks | Implemented |
| SRD-BKT-002.047 | Compare: one row of key stats per variant | Implemented |

---

## Design Decisions

- User (2026-10-29): benchmark is the equal-weight average daily return of the run's stocks, shown as "S&P 500 (equal weight)". No SPY (TODO T64 Done).
- User (2026-10-29): Phase 4 split into 4a (this RN) and 4b (later): MAE / MFE and profit given back, hold time, P&L by score and rank, Monte Carlo, first vs second half, without top 5, shadow P&L, capital × per-trade heat map. Tracked in TODO T68.
- Stats are computed from stored results, so a report can be rebuilt after a restart.

---

## Issues Resolved

None

---

## Test Coverage

- New: UT-BKT-002.040–.047.M13 — 14 tests, all Pass.
- `tests/backtest` + `tests/gui/test_backtest_workspace.py` + `tests/gui/test_backtest_report_view.py`: 153 passed. `ruff` and `mypy --strict` clean on changed files.
- Real-window check (real data, IT sector, Price Action, ST_AUTO and a copy, $2,000, 2026-01-02..2026-10-28): 118 trades, net P&L -$544.36, return -27.2%, max drawdown -31.9%, Sharpe -1.49, profit factor 0.66. Benchmark $2,022 → $3,049. Entries taken 118; skipped: already held 161, daily loss stop 57, no margin 54, Rex limit 6, too expensive 1.
- Phase 3 user check still Pending.
