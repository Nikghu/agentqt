# Revision Note — RN-BKT-1.12.0-20261103

**Version:** 1.12.0
**Date:** 2026-11-03
**Tool:** BKT (also GUI)
**Artifact:** FO-BKT-002 / SRD-BKT-002.088, FO-GUI-031 / SRD-GUI-031.087
**Type:** Enhancement

---

## Summary

The Backtest From / To dates now follow the saved candles. The data check returns the days every chosen stock has in both 1d and 3m. The pickers only allow those days, and until the user picks a date, To is the last saved day and From one year before it.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.008.M05 | `backtest/service.py` | `_data_check()` reads each coverage once; `Estimate.data_span` from `_common_span()` |
| MD-GUI-031.002.M02 | `gui/backtest_builder.py` | `set_data_range()` limits and fills From / To; `_on_date()` notes a user pick |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Passes `data_span` to the builder after each data check |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.088 | Data check gives the common saved range | Implemented |
| SRD-GUI-031.087 | From / To follow the saved data | Implemented |

---

## Design Decisions

- User chose 2026-11-03: limit and auto-fill; common range of all chosen stocks (no missing candles inside it).
- Stocks with no saved data at all are left out of the range; they still show as missing.
- With no saved data the pickers allow 2000 to today, so a period can still be chosen to download.
- To fetch older history for stocks that already have data, the period cannot go before their first saved day; use Settings → Backtest data.

---

## Test Coverage

- New UT-BKT-002.088.M05.T01–T02, UT-GUI-031.087.M02.T01–T02. `tests/backtest` + backtest GUI: 222 passed.
- `ruff` clean; `mypy --strict` no new errors.
