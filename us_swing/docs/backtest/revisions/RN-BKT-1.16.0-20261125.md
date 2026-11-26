# Revision Note — RN-BKT-1.16.0-20261125

**Version:** 1.16.0
**Date:** 2026-11-25
**Tool:** BKT (+ GUI trade list, SRD-GUI-031.088)
**Artifact:** FO-BKT-002 / SRD-BKT-002.053; FO-GUI-031 / SRD-GUI-031.088
**Type:** Enhancement

---

## Summary

The backtest trade list now shows how long each trade was held in days, how much money it used and how much capital was free when it opened. Available capital is the account capital minus money in open trades; an exit gives its money back. When too little is free, the entry is cut or skipped (unchanged behaviour, logged as no margin).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.030.M12 | `src/us_swing/backtest/steps/portfolio.py` | `avail` saved per trade (free capital just before entry); new `TRADE_COLUMNS` entry |
| MD-BKT-002.007.M04 | `src/us_swing/backtest/results.py` | `_add_missing_columns`: an older results file gets new columns on save |
| MD-BKT-002.083.M15 | `src/us_swing/backtest/html_report.py` | All trades table adds Allocated and Available |
| MD-GUI-031.053.M07 | `src/us_swing/gui/backtest_trade_list.py` | Duration (days) replaces hours; Allocated capital and Available capital columns |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.053 | Available capital per trade; HTML columns (approved by user 2026-11-25, chat) | Implemented |
| SRD-GUI-031.088 | Trade list days, allocated and available capital (approved by user 2026-11-25, chat) | Implemented |

SRD-GUI-031.053 is not edited (Implemented); SRD-GUI-031.088 replaces its hours column.

---

## Design Decisions

- Days = elapsed hours ÷ 24, one decimal (user choice: calendar days).
- Available uses the start capital, as the sizing does today (Grow with P&L is not built yet).
- Runs saved before this change show a dash for Available; re-run to fill it.
- CSV export and the MCP trade rows include `avail` automatically.

---

## Issues Resolved

None

---

## Test Coverage

- UT-BKT-002.053.M12.T01, .M04.T01, .M15.T01; UT-GUI-031.088.M07.T01–T02: Pass.
- Backtest, trade list, workspace and MCP tests: 236 passed.
- App check: re-run a backtest and open Report → Trade list (TODO T254).
