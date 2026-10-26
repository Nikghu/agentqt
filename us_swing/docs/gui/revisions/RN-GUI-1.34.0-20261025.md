# Revision Note — RN-GUI-1.34.0-20261025

**Version:** 1.34.0
**Date:** 2026-10-25
**Tool:** GUI
**Artifact:** FO-GUI-028 / SRD-GUI-028.001–.005 (new)
**Type:** Feature (user design choice: Option A, https://claude.ai/artifact/BdzCz7hUddmW7Ps9sTp8si)

---

## Summary

The Candle data section of Settings is redesigned. One summary line ("Updating 260 of 503 stocks", "Up to date · 503 stocks", "1 trading day behind", "No candle data yet") sits next to one state pill. While a download runs, a 4 px bar and "51% · IQV · ~4 min left" show under it. A four-cell strip shows Data to, Last trading day, Stocks and Candles, each with a plain note; stored stocks above the index size now read "503 / 503 · +15 left the index". One footer row holds Update now (Build, Fill Delta or Resume) or Cancel download, Open Candle DB, and a red "Reset database…" link that asks in the app's frameless dialog.

Removed: the big percent, the DOWNLOAD / STATUS / ACTIONS heads, the refresh button (status still refreshes at start and after each download) and the disabled "Downloading…" button. The `state` tuple and `state_changed` signal are unchanged, so the sidebar badge and section dot work as before. A status check no longer overwrites the summary while a download runs.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-028.001.M01 | `us_swing/src/us_swing/gui/settings_panel.py` | `_DataPanel` layout, texts, ETA, days behind, reset confirm |
| — | `us_swing/src/us_swing/gui/theme.py` | `data_summary`, `data_stat_value`, `link_danger`; `data_pct` removed |

## Tests

`tests/gui/test_data_panel.py` rewritten: UT-GUI-028.* (11 cases) plus UT-GUI-021.004.M01.T04. GUI suite 454 passed; `test_theme_waits_for_apply` fails on main too (depends on the saved theme on this machine).
