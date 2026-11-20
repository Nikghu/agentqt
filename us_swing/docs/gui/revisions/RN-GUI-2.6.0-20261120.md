# Revision Note — RN-GUI-2.6.0-20261120

**Version:** 2.6.0
**Date:** 2026-11-20
**Tool:** GUI
**Artifact:** FO-GUI-045 / SRD-GUI-045.001–.006
**Type:** Feature

---

## Summary

Charts → Inspector → Send to Execution now turns the trade plan into a one-time auto strategy, "Chart plan - SYM", for that stock only. It buys once, today, when a 3-minute candle closes above Entry, with no approval step. Stop and target are saved as percent of the buy price, measured from Entry. The size is the Inspector's 1% risk size, given as a whole percent of capital. The trade is held overnight (Positional). The strategy is removed when its trade closes, when its pick is removed, or at the next start after its day, but never while its trade is open. Sending again replaces the plan unless its trade is open. Send without a valid plan shows a warning and sends nothing (SRD-GUI-045.006, which replaces "no plan adds the pick only"). The Strategies tab reloads when this list changes. No engine change: it uses the existing include scope, rex count and percent stop and target. All choices were made by the user on 2026-11-20.

The same session also fixed the Watchlist losing its selected row on every price update and added a right-click Delete (branch `fix/gui-watchlist-selection`, UT-GUI-019.004.M02.T04–T06).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-045.001.M01 | `src/us_swing/gui/chart_plan.py` | New: builds the chart plan strategy, risk size as capital %, expiry check |
| MD-GUI-045.001.M02 | `src/us_swing/gui/app_service.py` | `send_chart_plan()`, `purge_old_chart_plans()`, removal on trade close and pick removal, `strategies_changed` signal |
| MD-GUI-045.001.M02 | `src/us_swing/gui/chart_workspace.py` | Send uses the plan; warns when there is no valid plan |
| MD-GUI-045.001.M02 | `src/us_swing/gui/strategies_pane.py` | Reloads its list on `strategies_changed` |
| MD-GUI-045.001.M02 | `src/us_swing/gui/chart_inspector.py` | Send button tooltip |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-045.001 | Send saves "Chart plan - SYM" for that stock only | Implemented |
| SRD-GUI-045.002 | Buys on a 3m close above Entry, today only | Implemented |
| SRD-GUI-045.003 | Stop and target as percent; risk size as capital % | Implemented |
| SRD-GUI-045.004 | Resend replaces unless the trade is open | Implemented |
| SRD-GUI-045.005 | Removed on trade close, pick removal or next start after its day | Implemented |
| SRD-GUI-045.006 | No valid plan: warning, nothing sent | Implemented |

---

## Tests

UT-GUI-045.001.M01.T01–T08, UT-GUI-045.006.M02.T01 and updated UT-GUI-026.010.M01.T01–T02: all Pass (34 chart tests). ruff and mypy: no new errors.

## Open

- T215: paper app check of the whole flow.
