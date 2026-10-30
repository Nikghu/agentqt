# Revision Note — RN-GUI-1.50.0-20261030

**Version:** 1.50.0
**Date:** 2026-10-30
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.075–.078
**Type:** Feature

---

## Summary

The Backtest workspace is polished. The header now shows a numbered step stepper and a labelled field grid (Run, Stocks, Screener, Strategy, Account) with Hide details, remembered in QSettings (option A). The trade chart loads candles from before entry to the exit day, with ringed IN / OUT dots, a path, IN / OUT price callouts and a P&L · % · sessions badge; candles outside the trade are dimmed (option D). The Chart panel title row holds the trade line and a 3m / 15m / 1D toggle (15m default). Names, Add and Remove fields suggest S&P 500 symbols for the name being typed. Also: the Sessions table is sorted oldest first with a Screened count instead of "Data up to", and the bold axis label bug is fixed.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.075.M11 | `gui/backtest_header.py` | New: `StepStrip`, `PlanFields`, Hide details |
| MD-GUI-031.052.M06 | `gui/backtest_trade_chart.py` | Trade path, IN / OUT dots and callouts, P&L badge, dimmed outside candles |
| MD-GUI-031.050.M05 | `gui/backtest_dock.py` | `PanelSpec.head` for the title row toggle |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Header wiring, 3m / 15m / 1D toggle, Sessions order and Screened count |
| MD-GUI-031.002.M02 | `gui/backtest_builder.py` | `_NameCompleter` for Names / Add / Remove fields |
| — | `gui/theme.py` | QSS for header, stepper and title row |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.075 | Header stepper and field grid with Hide details, remembered | Implemented |
| SRD-GUI-031.076 | Trade chart with path, IN / OUT dots, callouts, P&L badge, dimmed outside | Implemented |
| SRD-GUI-031.077 | Chart title row holds trade line and 3m / 15m / 1D toggle | Implemented |
| SRD-GUI-031.078 | Names / Add / Remove fields suggest S&P 500 symbols | Implemented |

---

## Design Decisions

- Header uses option A (stepper and field grid); trade chart uses option D (trade path with result badge).
- Chart timeframe toggle sits in the panel title row, styled like the Charts page; no second header row.
- Sessions table: oldest first; "Data up to" replaced by a Screened count.

---

## Issues Resolved

None

---

## Test Coverage

UT-GUI-031.075.M11.T01 (Pass), UT-GUI-031.052.M06.T03–T05 (Pass), UT-GUI-031.078.M02.T01 (Pass); updated workspace tests. 46 backtest GUI tests pass; ruff and mypy clean on changed files. Real-app check by user pending.
