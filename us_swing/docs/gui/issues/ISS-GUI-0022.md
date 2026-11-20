# Issue Report — ISS-GUI-0022

**Tool:** GUI
**Severity:** Medium (a waiting order is invisible)
**Status:** Resolved (user check pending)
**Date Opened:** 2026-11-21
**Date Resolved:** 2026-11-21
**Resolution:** SRD-GUI-002.005 (Reopen) and SRD-EXE-015.002 — no new requirement
**Reporter:** User — "in order history the order shall be added as New then it should change to FILLED; now I see directly FILLED. In case of CANCELLED also it should be"

---

## Symptom

Trade History shows every order as FILLED. A sell that is waiting, cancelled or rejected never shows.

## Root Cause

| Point | Detail |
|---|---|
| Wrong source | `app_service.py::_rehydrate_positions_from_cycles()` built Trade History from trade cycles, which exist only after a fill, and wrote `order_state="FILLED"` on every row. |
| Ledger unused | The `trades` ledger already holds NEW → FILLED / CANCELLED / REJECTED per order (SRD-EXE-015.002), but no screen read it. |
| No refresh on accept | The GUI refreshed only on fill, cancel or reject events, so a NEW order did not appear until it filled. |

## Fix

| File | Change |
|---|---|
| `db/manager.py` | `fetch_trades(since)` reads `trades` rows with their order state |
| `gui/app_service.py` | `_load_order_rows()` fills Trade History from the ledger (30 days); exit rows show the fill price; cycle rows only fill in older history not in the ledger; refresh also on NEW |
| `execution/broker_adapter.py` | After acceptance the listener gets a NEW event so screens refresh before the fill |
| Tests | UT-EXE-015.002.M01.T24, UT-EXE-015.005.M01.T16, UT-GUI-002.005.M01.T04–T05; T01 adapter test now expects NEW then FILLED events |

## User step

Paper fills almost at once, so NEW may only flash. With IBKR live, an Exit shows SELL · NEW until it fills, then FILLED; a cancelled order shows CANCELLED (T219).
