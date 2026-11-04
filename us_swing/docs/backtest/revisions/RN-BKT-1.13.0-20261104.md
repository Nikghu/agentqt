# Revision Note — RN-BKT-1.13.0-20261104

**Version:** 1.13.0
**Date:** 2026-11-04
**Tool:** BKT (+ GUI)
**Artifact:** FO-BKT-001, FO-GUI-030 / SRD-BKT-001.017, SRD-GUI-030.011
**Type:** Bugfix (ISS-BKT-0002)

---

## Summary

3m candles started in April or July 2024 for most stocks while the start date was 01-01-2024, and Download missing never asked for the gap. Empty 3m answers had saved a floor that blocked the older range. Floors now come only from listed-late daily data, old 3m floors are dropped, and the Universe table marks a late 3m start.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-001.017.M04 | `backtest/downloader.py` | `_update_floor` sets a floor only from 1d data; an empty 3m answer is asked again next run |
| MD-BKT-001.017.M02 | `backtest/settings.py` | `DownloadState` saves floors under `listed`; the old `floors` key is not read |
| MD-GUI-030.011.M02 | `gui/app_service.py` | `get_backtest_symbol_coverage` gives `late` when 3m starts more than 7 days after the start date or listing date |
| MD-GUI-030.011.M02 | `gui/settings_panel.py` | Universe: warning icon with "3m starts after the start date" tip and amber BT From for `late` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-001.017 | Floor only from listed-late daily data; empty 3m answer asked again | Implemented |
| SRD-GUI-030.011 | Universe marks a late 3m start | Implemented |

---

## Design Decisions

- User chose: if IBKR still sends no 3m data, the stock stays missing and every Download missing asks again (no "IBKR limit" mark). A backtest needs 3m data.
- 7-day slack, the same as the planner's backfill slack, so `late` matches what the plan will ask for.

---

## Issues Resolved

- ISS-BKT-0002 (`docs/backtest/issues/ISS-BKT-0002.md`).

---

## Test Coverage

UT-BKT-001.006.M04.T03 (changed), UT-BKT-001.017.M02.T01, UT-BKT-001.017.M04.T01, UT-GUI-030.011.M02.T01, all Pass. tests/backtest + test_app_service_backtest.py: 175 passed.

Real store dry run (no TWS): 1,277 3m requests for 503 stocks; AAPL asks 2024-01-01 to 2024-04-04.
