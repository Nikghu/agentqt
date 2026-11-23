# Revision Note — RN-EXE-1.42.1-20261123

**Version:** 1.42.1
**Date:** 2026-11-23
**Tool:** EXE
**Artifact:** FO-EXE-011 / SRD-EXE-011.028
**Type:** Bugfix (ISS-EXE-0016)

---

## Summary

After a restart the strategy engine checked rules on the previous day's bars before today's prices loaded, and sold PRU and APP. The engine now skips a stock until its latest 3m bar is from today's New York date.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-011.001.M01 | `src/us_swing/execution/strategy_engine/_engine.py` | New `bar_is_from_today()`; used in the per-second check and the new-bar check |
| MD-EXE-011.001.M01 | `tests/execution/test_strategy_engine.py` | New UT-EXE-011.001.M01.T09; fan-out tests use a today bar |

## Docs

SRD-EXE v1.40.0 (SRD-EXE-011.028), UTCD-EXE v1.27.0 (UT-EXE-011.001.M01.T09), ISS-EXE-0016.

## Tests

`pytest tests/execution/test_strategy_engine.py tests/execution/test_capital_allocation.py tests/execution/test_indicator_plugin_runtime.py`: 48 pass (the 3 s stop test failed once on timing, passes on re-run). `ruff` clean; `mypy --strict` reports no error in the changed file.

## User check

Restart the app before 09:30 or during market hours with an open strategy trade: no buy or sell until today's first 3m bar is in.