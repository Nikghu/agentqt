# Revision Note — RN-BKT-1.5.0-20261029

**Version:** 1.5.0
**Date:** 2026-10-29
**Tool:** BKT
**Artifact:** FO-BKT-002 / SRD-BKT-002.050–.051 (SRD-BKT-002.023 superseded by .050)
**Type:** Bugfix

---

## Summary

Two fixes found while the user checked Step 3. (1) Strategy PRICE now reads closed bars only, the same as live, so a backtest cannot see a bar that is still forming. (2) Step 1 now keys each stock list by session date: the list for a session is built from the trading day before it, as the pre-market screener run does. The first session trades its own list. Signals cache version is 2, so old signal caches rebuild.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.021.M10 | `core/expr/series.py` | PRICE uses the same as-of-bar-close path as other functions; `_price` removed |
| MD-BKT-002.010.M07 | `backtest/steps/stocks.py` | `sessions()` maps session to previous trading day; `run_stocks` returns a dict keyed by session |
| MD-BKT-002.030.M12 | `backtest/steps/portfolio.py` | `picks_by_day` has no shift; first session trades its own list |
| MD-BKT-002.008.M05 | `backtest/service.py` | `DailyList` gains `data_days`; daily list keyed by session |
| MD-BKT-002.026.M11 | `backtest/steps/signals.py` | `STEP_VERSION` 1 → 2 (cache rebuild) |

GUI side of SRD-BKT-002.051 is in RN-GUI-1.42.0-20261029.

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.050 | Strategy PRICE reads only closed bars on every timeframe | Implemented |
| SRD-BKT-002.051 | Step 1 keys each list by session date, built from the previous trading day's close | Implemented |

---

## Design Decisions

- User (2026-10-29): PRICE reads closed bars only; replaces SRD-BKT-002.023 (its row is still `Implemented` — user to decide its status).
- User (2026-10-29): session date keying matches the pre-market screener run. Step 1 cache files stay per data day.
- Open (not changed here): ST_AUTO uses `Price('Spot','Last','close','15m')`. With closed-bar frames, `Last` is now the bar before the last closed bar. User to decide whether to change it to `current` (TODO T63).

---

## Issues Resolved

None

---

## Test Coverage

- New: UT-BKT-002.050.M10.T01–T02, UT-BKT-002.051.M07.T01, UT-BKT-002.051.M12.T01 — all Pass.
- `tests/backtest` + `tests/gui/test_backtest_workspace.py`: 126 passed. `ruff` clean; `mypy` no errors in changed files.
- Real-window check (IT sector, Price Action, 2026-10-01..10-29, ST_AUTO): 20 sessions; 2026-10-01 uses 2026-09-30; 11 trades. NVDA exit moved 09:48 → 10:00 after the PRICE change.
