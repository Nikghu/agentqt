# Revision Note — RN-GUI-1.24.0-20261023

**Version:** 1.24.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-024 / SRD-GUI-024.008 (changed)
**Type:** Fix (user feedback)

---

## Summary

After checking the app, the user asked for smaller gaps and no chart header row. The Execution screen now lays out its own cards on the gutter like the Screener: header, watchlist, tabs and charts are separate cards 4 px apart (no 16 px margins or 8–12 px gaps). The chart row with symbol, price, change and the Hide button is removed; **Hide charts / Show charts** now sits in the page header after the broker chip and hides the whole chart card. The choice is still remembered.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-024.008.M06 | `us_swing/src/us_swing/gui/execution_panel.py` | Gutter + cards with `GAP`; chart header row, `price_change()` and `_show_price()` removed; chart card hidden when charts are hidden |
| MD-GUI-024.001.M01 | `us_swing/src/us_swing/gui/execution_header.py` | `charts_btn`, `show_charts_state()` |
| MD-GUI-001.001.M01 | `us_swing/src/us_swing/gui/main_window.py` | Execution not wrapped in one card (same as Screener) |
| MD-GUI-017.001.M02 | `us_swing/src/us_swing/gui/theme.py` | `chart_head` QSS removed |
| MD-GUI-024.008.M06 | `us_swing/tests/gui/test_execution_charts.py`, `test_execution_header.py` | Toggle test updated; price tests removed with the row; header button test added |

---

## Verification

GUI suite 345 passed. `ruff` and `mypy --strict` clean on the header. Panel re-rendered offscreen and checked.
