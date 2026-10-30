# Revision Note — RN-GUI-1.48.0-20261030

**Version:** 1.48.0
**Date:** 2026-10-30
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.060–.061
**Type:** Feature

---

## Summary

Phase 5 on screen. The builder Screener group has a "Use saved screener lists" tick with the preset's saved-day count and range; the data check says "saved screener lists for X of Y sessions". The Screener screen has a Quick test button: it opens Backtest with S&P 500, that preset, saved lists ticked and the period set to the saved days.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.002.M02 | `gui/backtest_builder.py` | Saved-lists tick, `preset_id`, `set_saved_days()`, `quick_test()` |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Saved-day count, `quick_test()`, data check text |
| — | `gui/screener_panel.py` | Quick test button and `quick_test_requested` |
| MD-GUI-031.001.M01 | `gui/main_window.py` | Quick test opens the Backtest screen |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.060 | Use saved screener lists tick with count | Implemented |
| SRD-GUI-031.061 | Quick test button on the Screener screen | Implemented |

---

## Tests

3 new tests; all backtest tests 203 pass; screener and main window tests 59 pass. Real-window check on Momentun_Price saved lists (see RN-BKT-1.10.0).
