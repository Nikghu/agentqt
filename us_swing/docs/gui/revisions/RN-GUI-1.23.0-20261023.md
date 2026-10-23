# Revision Note — RN-GUI-1.23.0-20261023

**Version:** 1.23.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-024 / SRD-GUI-024.008
**Type:** Feature

---

## Summary

Phase 5, the last phase of the Execution screen redesign (canvas Option F2). The screen is now laid out as cards: the watchlist on the left, and on the right the tab card on top with the 3m + 15m charts **below** it (3 : 2 split, resizable). The chart header shows the symbol, last price and change against the previous session's close. **Hide charts** folds the charts down to that header and gives the space to the tabs; **Show charts** brings them back. The choice is remembered across restarts (`QSettings("USSwing", "ExecutionPanel")`, key `charts_hidden`).

Also fixed: watchlist groups now open expanded (found in the render check; the unit test now checks it), and the score column is wide enough for "0.94".

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-024.008.M06 | `us_swing/src/us_swing/gui/execution_panel.py` | Cards via `cards.card()`; tab card above charts; 8 px gap handles; `price_change()`; chart header row with `toggle_btn`, `set_charts_hidden()`, `charts_toggled`; settings injectable for tests |
| MD-GUI-024.002.M02 | `us_swing/src/us_swing/gui/execution_watchlist.py` | Groups expanded; LTP / Score column widths |
| MD-GUI-017.001.M02 | `us_swing/src/us_swing/gui/theme.py` | `chart_head` QSS (all themes) |
| MD-GUI-024.008.M06 | `us_swing/tests/gui/test_execution_charts.py` | 3 tests (UT-GUI-024.008.M06.T01–T03), temp INI settings (never the real registry) |

---

## Verification

GUI suite 346 passed (`test_chart_workspace.py` excluded: QtWebEngine cannot load in the test shell). `ruff` clean; no `mypy --strict` errors on new lines (`execution_panel.py` errors fell from 24 to 14, all in older code). Full panel rendered offscreen with sample data — charts shown and hidden — and matched against canvas F2.

## Not covered

The real TradingView charts were stubbed in the render; the user should check them in the running app.
