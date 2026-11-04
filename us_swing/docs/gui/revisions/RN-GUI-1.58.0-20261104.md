# Revision Note — RN-GUI-1.58.0-20261104

**Version:** 1.58.0
**Date:** 2026-11-04
**Tool:** GUI
**Artifact:** FO-GUI-030 / SRD-GUI-030.012
**Type:** Enhancement

---

## Summary

While a backtest download runs, the Settings > Universe table updates each stock's Backtest, BT From and BT To as soon as that stock is done. The top line now also says "backtest complete for N of M stocks". Only that one row changes; the table is not rebuilt, so scroll, sort and search stay.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-030.012.M02 | `gui/app_service.py` | `get_backtest_coverage_for(ibkr_symbol)`; shared `_backtest_coverage_fn()` also used by `get_backtest_symbol_coverage()` |
| MD-GUI-030.012.M06 | `gui/settings_panel.py` | `_UniverseTab` listens to `backtest_progress`; a new symbol means the previous stock is done → one-row JS `updateBt()`; complete count in the meta line |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-030.012 | Universe row updates per finished stock; complete count | Implemented |

---

## Design Decisions

- Relies on the download finishing one stock before the next (RN-BKT-1.13.1-20261104).
- One stock's coverage reads only its Parquet metadata, so no lag; the last stock and any drift are fixed by the existing full reload when the download ends.

---

## Test Coverage

UT-GUI-030.012.M02.T01, UT-GUI-030.012.M06.T01, both Pass. test_settings_sections.py + test_app_service_backtest.py + tests/backtest: 196 passed. Not yet checked in the real app window.
