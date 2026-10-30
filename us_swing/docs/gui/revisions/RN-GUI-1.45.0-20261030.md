# Revision Note — RN-GUI-1.45.0-20261030

**Version:** 1.45.0
**Date:** 2026-10-30
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.053–.054
**Type:** Feature

---

## Summary

Backtest redesign phase 2 (Detail Report). New Trade list panel matching the user's screenshot: Trade #, LONG/SHORT pill, symbol, strategy, entry and exit time, prices, P&L, P&L % (green/red), qty, duration (hrs) and exit reason, with All / Wins / Losses / LONG / SHORT chips. Clicking a row opens that day in the Trade Inspector with the trade picked and charted. New Screener use panel (picks per session, traded part first) and Margin use panel (deployed peak = start capital minus lowest margin, and lowest margin left), each with a facts line.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.053.M07 | `gui/backtest_trade_list.py` | New: `TradeList`, `numbered()`, `keep()` |
| MD-GUI-031.054.M08 | `gui/backtest_use_charts.py` | New: `UsePanel`, `StackedBars`, `screener_use()`, `margin_use()` |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Detail Report has Trade list, Screener use and Margin use panels; trade click opens the Inspector day |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.053 | Report panels plus the Trade list; row click opens that day in the Inspector | Implemented |
| SRD-GUI-031.054 | Screener use and margin use panels | Implemented |

---

## Tests

46 backtest GUI tests pass (8 new). Real-window check (IT, Jan 2 – Oct 28 2026, 103 trades): SHORT chip shows 98 trades; clicking GEN opens 2026-01-26 with GEN charted; screener use 207 sessions, 87 with picks, 99 of 152 picks traded; margin use 104 of 207 days, matching the report's 50.2% time invested.
