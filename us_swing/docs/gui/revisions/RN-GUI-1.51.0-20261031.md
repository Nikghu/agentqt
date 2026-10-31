# Revision Note — RN-GUI-1.51.0-20261031

**Version:** 1.51.0
**Date:** 2026-10-31
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.062–.066
**Type:** Feature

---

## Summary

The Detail Report Breakdown is redesigned (option A of https://claude.ai/artifact/EwvB839pqWBrsjbQy4TCRY). Chips with group counts replace the Group by list; a grouping with one group is off with a reason. Entry hour, weekday, hold time, rank and score keep natural order with "No trades" slots; other groups stay best net P&L first. Rows show readable exit names, trades with share, a win rate meter, average and net P&L in green / red, a zero-line bar on one scale and an All trades total. Groups under 5 trades are greyed and marked n<5. Stock shows the best 5 and worst 5 with Show all, a search box and a minimum-trades filter. Clicking a row narrows the Trade list to that group; clicking it again or the total clears it.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.062.M12 | `gui/backtest_breakdown.py` | New: `BreakdownView`, `rows()`, `visible()`, `group_label()` |
| MD-GUI-031.040.M04 | `gui/backtest_report_view.py` | Group by list and table replaced by `BreakdownView` |
| MD-GUI-031.053.M07 | `gui/backtest_trade_list.py` | `trade_keys()`, `set_group_filter()`; summary names the group |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Breakdown row click wired to the Trade list |
| — | `gui/theme.py` | Disabled filter chip colour |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.062 | Group chips with counts; single-group chips off | Implemented |
| SRD-GUI-031.063 | Natural order with empty slots for ordered groups | Implemented |
| SRD-GUI-031.064 | Readable names, meter, bar, total, n<5 grey | Implemented |
| SRD-GUI-031.065 | Stock best / worst, search, minimum trades | Implemented |
| SRD-GUI-031.066 | Row click filters the Trade list | Implemented |

---

## Design Decisions

- Ordering is done in the GUI; `breakdown()` (SRD-BKT-002.044, best first) is unchanged.
- Trades are matched between the report and the Trade list by symbol and entry time.
- Bars share one scale with the All trades total so the total bar is not clipped.

---

## Issues Resolved

None

---

## Test Coverage

10 new or rewritten tests (UT-GUI-031.062–.066), all Pass; UT-GUI-031.043.M04.T01 and .047.M04.T01 replaced. Full GUI suite 590 passed, same 22 test-order errors as main. ruff clean, no mypy errors in changed files. Checked on the real saved run "Demo - Price Action + ST_AUTO_10_2_SL5%". Real-app check by user pending.
