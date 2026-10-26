# Revision Note — RN-GUI-1.22.0-20261023

**Version:** 1.22.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-024 / SRD-GUI-024.003–.007
**Type:** Feature

---

## Summary

Phase 4 of the Execution screen redesign. The bottom `QTabWidget` (Active Trades | Strategy Builder) becomes a tab card: **Active trades · N | Strategies · N | Closed today · N**. Active trades and Closed today are the same Active Trades table, filtered by row state. The wide Strategy Builder table is replaced by a list + detail view: strategy list on the left; on the right the header (status, mode, start date), Edit / Duplicate / Reset count / Start-Stop / Delete, four setting boxes, the new **Strategy P&L** card (running total or per-trade bars, max drawdown in red, 1W / 1M / 3M / All, win rate, average win / loss, max drawdown, today) and a Today strip.

Every action of the old table is kept, with the same logic. Duplicate is new: it saves a stopped copy under a new name ("ST copy", "ST copy 2" …), so two strategies never share a P&L history. The delete confirmation now says closed trades stay in the database.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-024.004.M04 | `us_swing/src/us_swing/gui/strategies_pane.py` | New: `StrategiesPane` (list, detail, actions, Duplicate, Today strip); old `_StrategyTablePane` logic moved here |
| MD-GUI-024.006.M05 | `us_swing/src/us_swing/gui/strategy_pnl_chart.py` | New: `StrategyPnlChart` (QPainter line / bars, nice ticks), `StrategyPnlCard` |
| MD-GUI-024.003.M03 | `us_swing/src/us_swing/gui/active_cycles_panel.py` | `set_row_filter()`, `counts_changed`; filter re-applied on every model change |
| MD-GUI-024.003.M03 | `us_swing/src/us_swing/gui/active_cycles_model.py` | `is_closed_row()`, `is_editor_row()` |
| MD-GUI-004.001.M01 | `us_swing/src/us_swing/gui/execution_panel.py` | Tab card (`QTabBar#exec_tabs` + stack); `_StrategyTablePane`, `_cell_icon`, `_tab_qss` removed |
| MD-GUI-017.001.M02 | `us_swing/src/us_swing/gui/theme.py` | `exec_tabs` QSS (all themes) |
| — | `us_swing/assets/icons/chevron-down.svg`, `chevron-up.svg` | Lucide 0.460.0 (ISC), for the chart toggle |
| MD-GUI-024.004.M04 | `us_swing/tests/gui/test_strategies_pane.py` | 8 tests (UT-GUI-024.003–.006) |
| MD-GUI-004.001.M01 | `us_swing/tests/gui/test_execution_panel.py` | UT-GUI-004.001.M01.T06–T07 now target `StrategiesPane`; loads `us_swing.data` first so the file also runs alone (existing db ↔ data import cycle) |

---

## Verification

GUI suite 343 passed (`test_chart_workspace.py` cannot load QtWebEngine in the test shell — environment, not code). `ruff` and `mypy --strict` clean on the new files. Strategies tab rendered offscreen with sample data and checked against canvas F2.
