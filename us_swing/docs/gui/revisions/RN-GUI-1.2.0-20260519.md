# Revision Note — RN-GUI-1.2.0-20260519

**Version:** 1.2.0
**Date:** 2026-05-19
**Tool:** GUI
**Artifact:** FO-GUI-012 / SRD-GUI-012.001–007
**Type:** Refactor

---

## Summary

Market Watch redesigned: index symbols (`^GSPC`/`^IXIC`/`^DJI`) and IBKR index contracts replaced with 4 liquid ETF proxies (SPY / QQQ / DIA / IWM) subscribed via standard STK contracts. Market Watch data model unified with `WatchlistItem`; static metadata (prev_close, open, volume, etc.) fetched once via `_WatchlistQuoteWorker`. Live LTP continues to flow through the existing `_on_watchlist_tick` slot. A dedicated `_MarketWatchTab` (with `_MarketWatchModel` table) added to the dashboard; `_MWCell` rich-text hover labels in the main window admin bar replace the previous three-label strip.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-012.001.M01 | `gui/app_service.py` | Replace `MarketWatchItem` + `_watch` list with `WatchlistItem` + `_mw_items`; remove `_YAHOO_TO_IBKR` and `_fetch_mw_prev_close_once`; add `_refresh_mw_quotes` + `_on_mw_data`; route MW tick through `_on_watchlist_tick`; switch MW contracts to `_make_stk_contract` |
| MD-GUI-012.001.M02 | `gui/dashboard_panel.py` | Add `_MarketWatchModel` (QAbstractTableModel, 9 columns) and `_MarketWatchTab` widget; add "📊 Market Watch" tab to `_dash_tabs` |
| MD-GUI-012.001.M03 | `gui/main_window.py` | Add `_MWCell` (QLabel subclass with hover highlight, rich-text LTP + change%); replace old 3-label MW header strip in `_AdminContextBar` |
| MD-GUI-004.001.M01 | `gui/execution_panel.py` | Add `_CandleDbDiagDialog` + `_DiagTitleBar` — diagnostic-only, gated by `_SHOW_DB_DIAGNOSTICS` flag |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-012.001 | LiveTickWorker lifecycle in AppService | Implemented |
| SRD-GUI-012.002 | Market Watch — stream via IBKR (ETF proxies replace index contracts) | Implemented |
| SRD-GUI-012.003 | Market Watch tick slot updates ltp and change_pct | Implemented |
| SRD-GUI-012.004 | Watchlist price streaming via `_on_watchlist_tick` | Implemented |
| SRD-GUI-012.005 | Position current_price streaming | Implemented |
| SRD-GUI-012.006 | `_sync_tick_subscriptions` builds merged contract dict | Implemented |
| SRD-GUI-012.007 | Disconnect clears Market Watch prices | Implemented |

---

## Design Decisions

- **ETF proxies over index contracts** — SPY/QQQ/DIA/IWM are available as standard STK contracts with reliable L1 tick data; IBKR IND contracts for ^GSPC/^IXIC/^DJI were unavailable on paper trading accounts.
- **Unified data model** — MW items now use `WatchlistItem` (same as the watchlist) so the metadata-fetch path (`_WatchlistQuoteWorker`) is reused without duplication.
- **Dedicated dashboard tab** — Market Watch moved from the admin context bar alone to a full table tab in the dashboard, exposing Open/High/Low/Volume columns not visible in the header strip.

---

## Issues Resolved

None

---

## Test Coverage

19 existing unit tests (`tests/gui/test_app_service_tick.py`, T01–T19) — status **Pending re-run** against refactored `app_service.py`. No new UTCD cases added this cycle.
