# Revision Note — RN-GUI-1.44.0-20261030

**Version:** 1.44.0
**Date:** 2026-10-30
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.050–.052
**Type:** Feature

---

## Summary

Backtest redesign phase 1 (Dock Panels, user picked option C). The result area now has two section tabs, Trade Inspector and Detail Report, each made of titled panels. A right icon strip and each panel's ✕ turn panels on or off; the choice is kept across restarts. The Inspector has a Sessions list (All sessions row plus each session with picks, trades and day P&L); picking a day filters the Screener list, Signals, Trades, Decisions and Money panels. A new Chart panel shows the selected trade's stock for that day (3m, 15m or 1d) with entry and exit markers. The Detail Report holds the existing report; the variant picker sits by the section tabs.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.050.M05 | `gui/backtest_dock.py` | New: `DockSection`, `Panel`, `PanelSpec` |
| MD-GUI-031.052.M06 | `gui/backtest_trade_chart.py` | New: `TradeChart` (QPainter candles + markers) |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Six tabs replaced by two dock sections; Sessions list; day filter; chart wiring; `settings` argument |

Backend: `BacktestService.bars()` added (reads saved bars for the chart).

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.050 | Three sections made of panels turned on/off by a right icon strip | Implemented (Reports section comes with .055) |
| SRD-GUI-031.051 | Inspector Sessions list; picking a day filters the panels | Implemented |
| SRD-GUI-031.052 | Chart panel with entry and exit markers | Implemented |

---

## Tests

38 backtest GUI tests pass (8 new). Real-window check on IT sector, Jan 2 – Oct 28 2026: picking a day takes about 2 ms; HPE short trade shows on 15m and 3m charts.
