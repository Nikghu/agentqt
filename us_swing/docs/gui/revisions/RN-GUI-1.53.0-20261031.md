# Revision Note — RN-GUI-1.53.0-20261031

**Version:** 1.53.0
**Date:** 2026-10-31
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.079–.081
**Type:** Feature

---

## Summary

The Detail Report Report panel is a tear sheet (option A of https://claude.ai/artifact/9FtQ5stYsFFDbewpJZUw9C). One title row shows the variant, the run's stocks and period, and Export CSV. KPI tiles (Net P&L, Return, Max drawdown, Win rate, Profit factor, Sharpe) each have a context line, such as "vs benchmark +64.3 pts" or "lasted 105 days". Entries and skip reasons show as pills with "N of M entry signals were taken". All stats sit in four group cards (Returns, Risk, Trades, Exits and robustness), coloured only for money and returns. The monthly table shows $ values, a narrow Total column and no empty rows.

The chart has a $ axis on the left, month ticks, a start-capital line, end labels, a max drawdown marker and a drawdown % scale. A vertical line follows the mouse; the date, strategy equity, benchmark and drawdown show in the legend row with a date tag on the time axis, so nothing covers the curves.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.080.M13 | `gui/backtest_report_chart.py` | New: `ReportChart` moved here and redrawn; `index_at()`, `hover_lines()`, hover line |
| MD-GUI-031.040.M04 | `gui/backtest_report_view.py` | Title and context, KPI notes (`kpi_notes()`), signal pills, stat group cards, compact monthly table; `set_reports(reports, context)` |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Worker `plan` property; passes stocks and period to the Report panel |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.079 | Report tear sheet layout | Implemented |
| SRD-GUI-031.080 | Chart axes, ticks, labels and markers | Implemented |
| SRD-GUI-031.081 | Mouse-following line with day values | Implemented |

---

## Design Decisions

- Hover values sit in the legend row, not a floating box, because a box always hid part of a curve near peaks.
- The Trades KPI tile became Sharpe; the trade count shows in the Win rate note and the Trades group.
- Stats are grouped by name in the GUI; `backtest.steps.report` is unchanged.

---

## Issues Resolved

None

---

## Test Coverage

UT-GUI-031.079.M04.T01–T02, UT-GUI-031.080.M13.T01, UT-GUI-031.081.M13.T01–T03 added; report view and workspace tests updated. Full GUI suite 598 passed, same 22 test-order errors as main. ruff clean, no mypy errors in changed files. Checked on the real run "$2,000 · ST_10_2_LONG". Real-app check by user pending.
