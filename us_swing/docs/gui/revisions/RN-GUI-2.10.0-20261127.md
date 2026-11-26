# Revision Note — RN-GUI-2.10.0-20261127

**Version:** 2.10.0
**Date:** 2026-11-27
**Tool:** GUI
**Artifact:** FO-GUI-017, FO-GUI-022, FO-GUI-030, FO-GUI-031, FO-GUI-032 / SRD-GUI-017.006, SRD-GUI-022.022, SRD-GUI-030.013, SRD-GUI-031.089–.090, SRD-GUI-032.009
**Type:** Bugfix

---

## Summary

The backtest trade list now shows Entry and Exit rows in time order, with an Available capital column that also works for old runs. Several style fixes followed: the sidebar power button, the Stop and Trip buttons, the status pills and the Charts 1D / 1W chip gaps. Settings → Universe now lists SPY, RSP and the 11 sector ETFs.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.053.M07 | `gui/backtest_trade_list.py` | Entry and Exit rows in time order; Trade and Time columns; one Price column; Available capital with red shade above 80%; P&L, Duration and Exit reason on Exit rows only |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Feeds start capital and trades to the trade list |
| MD-GUI-031.040.M04 | `gui/backtest_report_view.py` | Risk panel hold time shown in days |
| MD-GUI-017.001.M02 | `gui/theme.py` | New "stop" role: red text, theme border, red hover; sidebar power button has no blue armed fill |
| MD-GUI-017.003.M01 | `gui/icons.py` | `mark_danger(role)` supports "stop"; Start icons neutral |
| MD-GUI-018.001.M01 | `gui/sidebar.py` | Connections power button icon always uses theme text colour |
| MD-GUI-024.001.M01 | `gui/execution_header.py` | Stop and Trip buttons use role "stop" |
| MD-GUI-032.002.M02 | `gui/strategies_views.py` | Status pills: theme text on a light tint, no border |
| MD-GUI-032.003.M03 | `gui/strategies_pane.py` | Stop and Trip use role "stop"; pill style |
| MD-GUI-022.001.M01 | `gui/screener_views.py` | ChipGroup keeps its own height in taller rows |
| MD-GUI-030.008.M06 | `gui/app_service.py`, `gui/settings_panel.py` | `get_backtest_etf_rows()`; Universe lists SPY, RSP and sector ETFs after stocks |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-017.006 | Stop and Trip breaker buttons: red text and icon, theme border, red hover; Start icons neutral | Implemented |
| SRD-GUI-022.022 | Chip group keeps an even gap on all four sides in a taller row | Implemented |
| SRD-GUI-030.013 | Universe lists SPY, RSP and 11 sector ETFs after stocks, daily backtest status, no fill tick box | Implemented |
| SRD-GUI-031.089 | Trade list Entry and Exit rows in time order, Available capital after each row | Implemented |
| SRD-GUI-031.090 | Trade list shades Available capital light red above 80% of start capital | Implemented |
| SRD-GUI-032.009 | Status pills use theme text on a light tint, no border | Implemented |

No SRD for the sidebar power button (style fix) or the risk panel hold time in days (UT-GUI-031.046.M04.T01 updated).

---

## Design Decisions

- Available capital = start capital less open trades, worked out from saved trades, so old runs show it too. Old runs with no start capital show a dash.
- Red shade starts above 80% of start capital; exactly 80% stays plain.
- New "stop" role for the breaker buttons only; other risky buttons keep role "danger".
- ETF rows in Universe have no fill tick box and are not counted in the stock totals.

---

## Issues Resolved

None

---

## Test Coverage

- New, Pass: UT-GUI-031.089.M07.T01–T03; UT-GUI-031.090.M07.T01; UT-GUI-017.006.M01.T01; UT-GUI-022.022.M01.T01; UT-GUI-030.013.M02.T01; UT-GUI-030.013.M03.T01; UT-GUI-032.009.M02.T01.
- Updated, Pass: UT-GUI-031.046.M04.T01 (hold time in days); UT-GUI-030.008.M02.T02 (fixed a stale test that failed since the sector ETFs were added).
- Replaced: UT-GUI-031.088.M07.T01–T02 (by UT-GUI-031.089.M07).
- Open user checks are in TODO.md (T257, T262).
