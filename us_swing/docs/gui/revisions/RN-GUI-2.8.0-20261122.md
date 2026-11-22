# Revision Note — RN-GUI-2.8.0-20261122

**Version:** 2.8.0
**Date:** 2026-11-22
**Tool:** GUI
**Artifact:** FO-GUI-027 / SRD-GUI-027.001; FO-GUI-030 / SRD-GUI-030.006, .008, .009, .011, .012
**Type:** Bugfix (ISS-BKT-0003, GUI part)

---

## Summary

Settings sections now scroll on their own, so a short section fits without the outer scroll bar. The Universe marks a stock Partial when its BT From / BT To do not cover the Backtest Data range, or it has no 3m data. The user can tick Partial and missing stocks and fill only those; Fill selected now shows its progress. Ticks can be cleared in one click, and the Universe top line is shorter.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-027.001.M01 | `src/us_swing/gui/settings_dialog.py` | Outer scroll bar removed; each section scrolls on its own |
| MD-GUI-027.001.M01 | `src/us_swing/gui/settings_panel.py` (`_section_card`) | Section card holds its own scroll area |
| MD-GUI-030.008.M06 | `src/us_swing/gui/settings_panel.py` | Partial and missing rows get tick boxes; Select partial; Fill selected shows progress; header box and toggle clear ticks; short top line |
| MD-GUI-030.008.M06 | `src/us_swing/gui/app_service.py` | Coverage marks Partial from the range check and 3m data; Fill selected drops floors for the ticked stocks only |
| MD-GUI-030.004.M02 | `src/us_swing/gui/app_service.py` | Stats set the count of Partial stocks |
| MD-GUI-030.001.M01 | `src/us_swing/gui/backtest_data_panel.py` | Card shows "N stocks partial" and a disabled Partial button instead of Up to date |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-027.001 | Settings dialog; each section scrolls on its own | Implemented |
| SRD-GUI-030.006 | Backtest data section dot; Partial shown as not up to date | Implemented |
| SRD-GUI-030.008 | Universe shows each stock's status, BT From and BT To; Partial rows get tick boxes | Implemented |
| SRD-GUI-030.009 | Backtest status line and one button; Partial button added | Implemented |
| SRD-GUI-030.011 | Universe marks a late 3m start | Implemented |
| SRD-GUI-030.012 | Universe row updates per stock; top line count shortened | Implemented |

SRD rows are not edited (status Implemented). The new wording differs from SRD-GUI-030.009, .011 and .012 (see Design Decisions).

---

## Design Decisions

- Partial means the stock's BT From / BT To do not cover the Backtest Data range, or it has no 3m data. Floors are not used (user decision, ISS-BKT-0003).
- Data that IBKR does not have stays Partial. The user can fill it again later.
- Top line is "503 stocks · N complete · N partial" (plus "N not downloaded" or "list is old" when needed). It replaces the SRD-GUI-030.012 wording; that row is left unchanged.
- The Partial button text and the Universe Partial status are not in SRD-GUI-030.009, .011 and .012. The user decides whether to Reopen those rows or add new ones.

---

## Issues Resolved

- ISS-BKT-0003 (GUI part): Universe shows Partial stocks; Fill selected fills only the ticked stocks. Planner part in RN-BKT-1.14.0-20261122. App check open (TODO T223).

---

## Test Coverage

- New: UT-GUI-027.001.M01.T03; UT-GUI-030.006.M01.T03; UT-GUI-030.008.M02.T02–T03; UT-GUI-030.008.M03.T02–T06; UT-GUI-030.009.M02.T02; UT-GUI-030.011.M02.T02.
- Changed: UT-GUI-030.008.M02.T01; UT-GUI-030.011.M02.T01; UT-GUI-030.012.M06.T01.
- Status per `docs/gui/UTCD.md` (Pass).
- User app check: TODO T223.
