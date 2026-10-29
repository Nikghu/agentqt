# Revision Note — RN-BKT-1.3.1-20261029

**Version:** 1.3.1
**Date:** 2026-10-29
**Tool:** BKT
**Artifact:** FO-BKT-002 / SRD-BKT-002.018–.019
**Type:** Bugfix

---

## Summary

Running the Backtest with a preset that has the RS rule failed with "Benchmark data for 'Benchmark data for 'SPY' …' …". The RS rule compares each stock with SPY, and SPY is not in the backtest data. The user decided the backtest data stays S&P 500 only (SPY is an ETF, not a member). Such presets now stop in the data check and in Step 1 with one plain sentence, and Run stays disabled. Errors from worker processes no longer repeat their text.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.010.M07 | `backtest/steps/stocks.py` | `needs_benchmark()`, `has_benchmark()`, RS refusal in `refusals()`; `_run_day` sends errors back as plain `RuntimeError` |
| MD-BKT-002.008.M05 | `backtest/service.py` | Estimate passes SPY presence to `refusals()` |
| MD-BKT-002.009.M06 | `backtest/cli.py` | "SPY has no 1d candles" line removed |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | "· SPY missing" note removed from the data check line |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.018 | RS-rule preset refused plainly when SPY is missing | Implemented |
| SRD-BKT-002.019 | Worker errors reach the user once, in plain text | Implemented |

---

## Tests

- 4 new tests (UT-BKT-002.018–.019); backtest + Backtest GUI tests 102 passed. `ruff` and `mypy --strict` clean.
- Real data check (CLI) for the user's 3 presets: Momentun_Price shows the RS message; Price Action and Test run as before.
