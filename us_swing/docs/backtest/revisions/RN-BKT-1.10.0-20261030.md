# Revision Note — RN-BKT-1.10.0-20261030

**Version:** 1.10.0
**Date:** 2026-10-30
**Tool:** BKT
**Artifact:** FO-BKT-002 / SRD-BKT-002.080–.081
**Type:** Feature

---

## Summary

Phase 5. Step 1 can use the screener lists the app saved (`~/.usswing/screener_results/preset_<id>/<date>.json`) instead of replaying the preset, so the real picks, AI picks included, are tested. A list run before 09:30 ET trades that day, a later one the next session (at most 4 days later); when two lists land on one session the newer wins; only passed stocks in the run's stock list are kept, ranked by score. The data check counts sessions with a saved list and stops when there is none. No step cache is used (the files are read directly).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.080.M14 | `backtest/steps/recorded.py` | New: `load_lists()`, `saved_days()`, `trade_day()` |
| MD-BKT-002.008.M05 | `backtest/service.py` | Saved-list estimate and Step 1; `saved_days()`; `screener_results` argument |
| MD-BKT-002.001.M01 | `backtest/spec.py` | `ScreenerSpec.recorded` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.080 | Step 1 from saved screener lists | Implemented |
| SRD-BKT-002.081 | Run time to session; sessions without a list have no picks | Implemented |

---

## Tests

5 new tests, Pass. Real run (Momentun_Price, 90 saved days, ST_AUTO, $2,000, S&P 500): lists for 74 of 133 sessions, 423 picks, 173 trades, -$297.27 (-14.9%), 56 s.
