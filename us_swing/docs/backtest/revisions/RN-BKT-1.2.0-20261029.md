# Revision Note — RN-BKT-1.2.0-20261029

**Version:** 1.2.0
**Date:** 2026-10-29
**Tool:** BKT
**Artifact:** FO-BKT-002 / SRD-BKT-002.001–.017
**Type:** Feature

---

## Summary

Backtest engine Phase 0 (Foundation) and Phase 1 (Step 1 · Stocks) from `Engine_plan.md`. A run plan (JSON, validation, up to 64 variants) picks the stocks and a screener preset. The data check counts stocks missing 1d or 3m candles. Step 1 replays the preset's rule stages on each trading day using only the 1d bars up to that day's close, caches one file per day, and gives a ranked daily list with top N. It runs in a process pool and can be cancelled. A CLI and the GUI (RN-GUI-1.39.0) both use `BacktestService`. Minimal requirements; approved by the user for code on 2026-10-29.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.001.M01 | `backtest/spec.py` | New — `RunPlan` and sub-specs, JSON, `validate()`, `variants()` |
| MD-BKT-002.004.M02 | `backtest/universe.py` | New — `resolve()` for S&P 500, sectors, names, add, remove |
| MD-BKT-002.005.M03 | `backtest/cache.py` | New — `StepCache`, `make_key()`, atomic write, cleanup |
| MD-BKT-002.007.M04 | `backtest/results.py` | New — `ResultsStore` (`results.db`, runs table) |
| MD-BKT-002.008.M05 | `backtest/service.py` | New — `BacktestService.estimate()` and `run_stocks()` |
| MD-BKT-002.009.M06 | `backtest/cli.py` | New — `estimate` and `run` commands |
| MD-BKT-002.010.M07 | `backtest/steps/stocks.py` | New — Step 1 replay, day cache, daily list, top N |
| MD-BKT-002.011.M08 | `core/backtest_bridge.py` | New — bridge to screener presets and the universe |
| — | `screener/executor.py` | New public `PresetExecutor.screen()` (pre-filter + Stage 2 + combine); `run_preset()` calls it, results unchanged |
| — | `run_gui.py` | `multiprocessing.freeze_support()` for worker processes in the built app |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.001–.003 | Run plan, validation, variants | Implemented |
| SRD-BKT-002.004 | Universe resolve | Implemented |
| SRD-BKT-002.005–.006 | Step cache and cleanup | Implemented |
| SRD-BKT-002.007 | Results store | Implemented |
| SRD-BKT-002.008–.009 | Estimate and CLI | Implemented |
| SRD-BKT-002.010–.016 | Step 1 replay, cache, rank, pool, refusals | Implemented |
| SRD-BKT-002.017 | Service run with progress, cancel and run row | Implemented |

---

## Tests

- 32 new tests (UT-BKT-002.*), all pass; `tests/backtest` 69 passed. `ruff` and `mypy --strict` clean on the new files.
- Real data, CLI: IT sector (75 stocks), preset "Test", 2026-01-02 to 2026-10-28 → 207 days, 146 passes; 10.6 s first run with 4 workers, 3.6 s when fully cached.

---

## Notes

- R2 checked: scores are per stock except the RS-rank rule, which ranks stocks against each other. So the cache is one file per day keyed by the whole stock list, not one file per stock. Adding a stock recomputes all days.
- SPY is not in the backtest store. Days then come from the stocks' own dates, and a preset with an RS rule fails for want of a benchmark. The data check shows "SPY missing".
- AI ranking (D4) and weekly presets stop the run with a plain message; they come in a later phase. The preset's own AI stage is always skipped in replay.
- Market caps come from today's S&P 500 list (survivorship, R1).
