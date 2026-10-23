# Revision Note — RN-GUI-1.21.0-20261023

**Version:** 1.21.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-024 / SRD-GUI-024.002
**Type:** Feature

---

## Summary

Phase 3 of the Execution screen redesign. The "Filtered Stocks" table becomes a grouped watchlist: Manual picks first, then one group per screener (A→Z) with a count; rows show symbol, last 3m close and score (highest first). Adding a pick, removing it ("✕" on the pick row), the red tint for symbols without candles and auto-select of the top row all work as before. The selected symbol is kept when results refresh.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-024.002.M02 | `us_swing/src/us_swing/gui/execution_watchlist.py` | New: `WatchlistPane`, `group_entries()`; pick input and completer moved here unchanged |
| MD-GUI-004.001.M01 | `us_swing/src/us_swing/gui/execution_panel.py` | `_FilteredStocksModel`, `_PinnedPicksProxy`, `_FilteredStocksPane` removed; panel uses `WatchlistPane` |
| MD-GUI-017.001.M02 | `us_swing/src/us_swing/gui/theme.py` | `exec_watch` tree QSS (all themes) |
| MD-GUI-024.002.M02 | `us_swing/tests/gui/test_execution_watchlist.py` | 4 tests (UT-GUI-024.002.M02.T01–T04) |
| MD-GUI-004.001.M01 | `us_swing/tests/gui/test_manual_picks.py` | UT-GUI-004.001.M01.T19 now checks the Manual group comes first |

---

## Verification

Watchlist, manual-pick, header and execution-panel tests: 22 passed. `ruff` and `mypy --strict` clean on `execution_watchlist.py`.
