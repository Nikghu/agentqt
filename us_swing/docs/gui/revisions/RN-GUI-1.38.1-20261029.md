# Revision Note — RN-GUI-1.38.1-20261029

**Version:** 1.38.1
**Date:** 2026-10-29
**Tool:** GUI
**Artifact:** FO-GUI-030 / SRD-GUI-030.010
**Type:** Enhancement

---

## Summary

Settings → Backtest data shows one more short line under the coverage: "15-minute and weekly candles are built from these". The background stats worker first builds any missing 15m/1w files (RN-BKT-1.1.0-20261029), then reads the stats.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-030.001.M01 | `gui/backtest_data_panel.py` | Coverage text gets the built-candles note |
| MD-GUI-030.004.M02 | `gui/app_service.py` | `_BacktestStatsWorker.run()` calls `store.build_missing()` and logs the stock count |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-030.010 | One short line: 15-minute and weekly candles are built from these | Implemented |

---

## Tests

- UT-GUI-030.001.M01.T01 and UT-GUI-030.006.M01.T02 updated for the second line. Backtest GUI tests pass.
