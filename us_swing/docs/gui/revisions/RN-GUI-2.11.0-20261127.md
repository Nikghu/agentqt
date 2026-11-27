# Revision Note — RN-GUI-2.11.0-20261127

**Version:** 2.11.0
**Date:** 2026-11-27
**Tool:** GUI
**Artifact:** FO-GUI-047, FO-GUI-031 / SRD-GUI-047.001–.002, SRD-GUI-031.091–.094
**Type:** Feature

---

## Summary

Settings → Universe now shows Added and Left dates for each S&P 500 stock, with left stocks greyed at the end. The backtest report shows the new skip chips, the Leading sectors card and details row, and the Same stocks and Edge stats.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-047.001.M01 | `us_swing/src/us_swing/gui/settings_panel.py` | Added and Left columns; left rows greyed and last; "N stocks · M left" |
| MD-GUI-047.001.M01 | `us_swing/src/us_swing/gui/app_service.py` | `get_sp500_history` feeds the Universe table |
| MD-GUI-031.040.M04 | `us_swing/src/us_swing/gui/backtest_report_view.py` | "Not in index yet" chip; Same stocks return, Same stocks worst drop, Edge rows (green/red) |
| MD-GUI-031.002.M02 | `us_swing/src/us_swing/gui/backtest_builder.py` | Leading sectors card on the Stocks page |
| MD-GUI-031.055.M09 | `us_swing/src/us_swing/gui/backtest_reports.py` | "Sector not leading" and "Sector not weak" chips; Leading sectors row in Report details |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-047.001 | Settings → Universe shows Added and Left columns (DD-MM-YYYY; "—" when missing) | Implemented |
| SRD-GUI-047.002 | Left stocks stay in the table, greyed, after current stocks | Implemented |
| SRD-GUI-031.091 | Report chip "Not in index yet N" for skips before Added date | Implemented |
| SRD-GUI-031.092 | Stocks page has a Leading sectors card (on/off, Top N, Period, Must beat RSP) | Implemented |
| SRD-GUI-031.093 | Chips "Sector not leading N" / "Sector not weak N"; Report details shows the setting | Implemented |
| SRD-GUI-031.094 | Returns stats show Same stocks return, Same stocks worst drop, Edge; Edge green above 0, red below | Implemented |

---

## Design Decisions

- Left stocks are greyed and listed last, so current members come first.
- Dates use DD-MM-YYYY; missing dates show "—".
- Chart benchmark line for Same stocks stays hidden by default.

---

## Issues Resolved

None

---

## Test Coverage

- New, Pass (7 tests): UT-GUI-047.001.M01.T01, .002.M01.T01; UT-GUI-031.091.M04.T01; UT-GUI-031.092.M02.T01, .093.M04.T01, .093.M09.T01; UT-GUI-031.094.M04.T01.

---

## Open items

- User checks T264, T265 and T268 (TODO.md).
- SRD-GUI-031.085 row in GUI TRACE is still Pending; not part of this RN.
