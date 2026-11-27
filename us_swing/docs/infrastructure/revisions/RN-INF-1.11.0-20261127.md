# Revision Note — RN-INF-1.11.0-20261127

**Version:** 1.11.0
**Date:** 2026-11-27
**Tool:** INF
**Artifact:** FO-INF-013 / SRD-INF-013.001–.004
**Type:** Feature

---

## Summary

The saved S&P 500 list now keeps each stock's Added date and Left date. A stock that drops out of the index stays in the saved list with a Left date. The current-member list used by the screener and backtest is unchanged.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-INF-013.001.M01 | `us_swing/src/us_swing/universe/store.py` | Added and Left fields; CSV DateAdded and LeftOn columns; Wikipedia "Date added" parsed; merge keeps missing stocks with Left = today; under 90% guard; `load_sp500()` current only, `load_sp500_all()` everyone |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-INF-013.001 | Each saved S&P 500 record carries an added date and a left date, both optional | Implemented |
| SRD-INF-013.002 | A refresh merges with the saved list; a stock no longer listed gets today's left date | Implemented |
| SRD-INF-013.003 | A stock listed again has its left date cleared | Implemented |
| SRD-INF-013.004 | Current-member list leaves out left stocks; full list includes them | Implemented |

---

## Design Decisions

- Left dates are tracked from the first refresh; no back-fill of past exits.
- A fresh list under 90% of saved members marks nobody as left (guards against a bad page).
- An existing left date is never overwritten.

---

## Issues Resolved

None

---

## Test Coverage

- New, Pass: UT-INF-013.001.M01.T01–T02, .002.M01.T01–T03, .003.M01.T01, .004.M01.T01 (7 tests).
- Tests in `tests/infrastructure/test_universe_store.py`.

---

## Open items

- None for INF. The user check of the Universe table is in the GUI RN.
