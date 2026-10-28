# Revision Note — RN-GUI-1.38.0-20261028

**Version:** 1.38.0
**Date:** 2026-10-28
**Tool:** GUI
**Artifact:** FO-GUI-030 / SRD-GUI-030.001–.006
**Type:** Feature

---

## Summary

New "Backtest data" section in Settings, right after Candle data (Option A, single card). It shows 1d / 3m progress and stats, holds the date range and auto delta settings (saved on Apply), and has Start / Pause, Fill delta now and a type-CLEAR Clear database.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-030.001.M01 | `gui/backtest_data_panel.py` | New panel and `build_clear_dialog()` |
| MD-GUI-030.004.M02 | `gui/app_service.py` | Backtest downloader, stats worker, 60 s auto delta check, clear guard, exit stop |
| MD-GUI-030.006.M03 | `gui/settings_panel.py` | Section registered with Apply/Cancel; dot; `QDateEdit` dirty tracking; Universe backtest columns (MD-GUI-030.008.M06) |
| MD-GUI-030.004.M04 | `gui/system_store.py` | `ibkr_backtest_client_id` (default 16) |
| MD-GUI-030.007.M05 | `gui/main_window.py` | Calls `shutdown_backtest_download()` on close; status bar shows backtest progress |
| — | `gui/theme.py` | `QDateEdit` styled like `QTimeEdit` (also fixes the Candle data start date) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-030.001 | Status card, progress lines and stat strip | Implemented |
| SRD-GUI-030.002 | Range card; latest check disables End date; start never after end | Implemented |
| SRD-GUI-030.003 | Auto delta switch, US/Eastern time, day chips | Implemented |
| SRD-GUI-030.004 | Actions disabled with "Connect TWS to download" | Implemented |
| SRD-GUI-030.005 | Clear needs typed CLEAR | Implemented |
| SRD-GUI-030.006 | Section dot | Implemented |
| SRD-GUI-030.007 | Status bar shows backtest progress (user request after testing) | Implemented |
| SRD-GUI-030.008 | Universe table shows backtest status, BT From, BT To (user request) | Implemented |

---

## Design Decisions

- Auto delta tries at most once per scheduled time per session, so a paused or failed delta does not restart every minute.
- Stats are read in a background worker (`backtest_stats_changed`), like the candle DB status.
- The summary shows both ranges (`1d … to … · 3m from …`) and the pill shows BEHIND when 3m starts more than 7 days after the start date. Before this, the pill looked only at 1d and said UP TO DATE while 3m was months short.
- Clear confirm reuses the frameless `_ConfirmDialog` and adds a text field.

---

## Tests

15 UT-GUI-030.* pass; the section-order test was updated for 9 sections. GUI + backtest suites: 552 passed.
