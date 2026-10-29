# Revision Note — RN-BKT-1.3.0-20261029

**Version:** 1.3.0
**Date:** 2026-10-29
**Tool:** BKT
**Artifact:** FO-BKT-002 / SRD-BKT-002.020–.029
**Type:** Feature

---

## Summary

Backtest engine Phase 2 (Step 2 · Signals). For each live strategy and each stock in Step 1's top-N list, the engine finds the periods when the entry and exit conditions are true at each 3m bar close, inside the strategy's hours and days. It uses the live condition parser (re-exported, live code unchanged) and a new series evaluator whose values equal the live values on the same bars. Results are cached per strategy and stock. Minimal requirements; approved by the user for code on 2026-10-29.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.020.M09 | `core/expr/__init__.py` | New — re-export of the live parser, `parse()` |
| MD-BKT-002.021.M10 | `core/expr/series.py` | New — 10 functions as series, as-of alignment, forming 15m bar for Price, session VWAP |
| MD-BKT-002.026.M11 | `backtest/steps/signals.py` | New — periods, hours and days, stock filter, cache, process pool |
| MD-BKT-002.011.M08 | `core/backtest_bridge.py` | `load_strategies()` |
| MD-BKT-002.008.M05 | `backtest/service.py` | `run_signals()`, shared run-row helper |
| MD-BKT-002.009.M06 | `backtest/cli.py` | `run` also does Step 2 |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.020 | Shared parser (re-export) | Implemented |
| SRD-BKT-002.021–.025 | Series parity, alignment, Price, VWAP, NaN | Implemented |
| SRD-BKT-002.026–.028 | Periods, PNL flag, Step 2 run and cache | Implemented |
| SRD-BKT-002.029 | Strategies from the live store; service and CLI | Implemented |

---

## Tests

- 17 new tests (UT-BKT-002.020–.029), all pass; `tests/backtest` 86 passed. `ruff` and `mypy --strict` clean on the new files.
- Phase 2 gate (plan §7): 50 real stocks, 8 functions × 4 timeframes, 60,000 sampled values: 0 mismatches against the live functions.
- Real data, CLI: ST_AUTO on the IT sector's top-5 stocks (35 stocks, 2026-01-02 to 2026-10-28) → 6,457 entry and 6,261 exit periods; 13 s first run, 4 s cached.

---

## Notes

- R4: Price reads the forming 15m bar like live; other indicators use closed bars, so inside a forming 15m bar they can differ from live. At each 15m close they match.
- Live findings (not changed): VWAP in live adds up all 30 loaded days with no daily reset; live `PNL` always returns 0.
- Periods use the strategy's hours and days; its start and end dates are not used (the run plan's period is).
