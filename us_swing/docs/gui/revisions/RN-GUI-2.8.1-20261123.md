# Revision Note — RN-GUI-2.8.1-20261123

**Version:** 2.8.1
**Date:** 2026-11-23
**Tool:** GUI (+ BKT and EXE, see RN-BKT-1.14.1-20261123 and RN-EXE-1.41.2-20261123)
**Artifact:** FO-GUI-031, FO-GUI-030, FO-GUI-013 / SRD-GUI-031.073, .080, .087; SRD-GUI-030.009; SRD-GUI-013.024
**Type:** Bugfix

---

## Summary

Backtest From / To calendars could not change month or year. They now use the Backtest Data settings range. Download "time left" uses the run's measured speed after 5 requests. The setup strategy table shows a Direction column. The BOSS_ST Swing Lookback accepts 1 to 500. The report chart benchmark can be hidden by clicking its legend item, and is hidden by default.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.002.M02 | `src/us_swing/gui/backtest_builder.py` | From / To range comes from the Backtest Data settings range; Strategies table shows Direction after Strategy |
| MD-GUI-030.001.M01 | `src/us_swing/gui/backtest_data_panel.py` | `_seconds_each` uses the measured speed after `_PACE_MIN_REQUESTS = 5` requests |
| MD-GUI-013.001.M01 | `src/us_swing/gui/strategy_builder_dialog.py` | BOSS_ST Swing Lookback range 1–500 (was 1–20) |
| MD-GUI-031.080.M13 | `src/us_swing/gui/backtest_report_chart.py` | Benchmark legend click hides or shows the benchmark; $ axis refits; hidden by default |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.087 | From / To limited to the run range (reopened 2026-11-22) | Implemented |
| SRD-GUI-030.009 | Status line shows time left from the measured speed | Implemented |
| SRD-GUI-031.073 | Strategies table shows a Direction column | Implemented |
| SRD-GUI-031.080 | Report chart benchmark toggle, hidden by default | Implemented |
| SRD-GUI-013.024 | BOSS_ST Swing Lookback 1–500 (reopened 2026-11-22) | Implemented |

SRD rows are not edited (status Implemented). The SRD-GUI-031.073 wording does not name the Direction column; the user decides whether to Reopen it.

---

## Design Decisions

- The calendar range follows the Backtest Data settings range, not the common span of all stocks (see RN-BKT-1.14.1-20261123).
- Time left uses this run's measured speed after 5 requests. Before that, the fixed guess is kept.
- The report chart benchmark is hidden by default; the $ axis refits when it is shown or hidden.

---

## Issues Resolved

None

---

## Test Coverage

- Backtest GUI tests: 116 passed.
- UT-GUI-031.087.M02.T01–T02 (range rules, Pass); UT-GUI-030.006.M01.T04 (time left, Pass); UT-GUI-031.073.M02.T02 (Direction column, Pass); UT-GUI-031.080.M13.T02 (benchmark hidden by default, Pass); UT-GUI-013.024.M01.T02 (Swing Lookback 22 accepted, 501 refused, Pass).
- App checks: TODO T225 (date pickers), TODO T226 (time left, Direction, Swing Lookback 22, benchmark key).
