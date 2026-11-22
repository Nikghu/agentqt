# Revision Note — RN-GUI-2.7.0-20261122

**Version:** 2.7.0
**Date:** 2026-11-22
**Tool:** GUI
**Artifact:** FO-GUI-045 / SRD-GUI-045.007–.008; FO-GUI-019 / SRD-GUI-019.012–.017; FO-GUI-002 / SRD-GUI-002.005 (Reopen); other tools in "Other tools" below
**Type:** Bugfix (batch on `fix/bugfix-batch-20261120`; includes two feature commits, 924bdf2f and the EXE lock)

---

## Summary

Chart plan strategies now buy the number of shares the available capital allows, and the user can edit that number. Dashboard Exit, Stop / Trail and Square Off All now act on the strategy trade that owns the stock, not on a loose position. Trade History shows each order's real state (NEW, FILLED, CANCELLED) from the trades ledger, has a Value column, drag-resizable columns, and Mode right after Side. A price update no longer clears the selected Dashboard row.

On 2026-11-20 two app copies ran at once; both bought HRL. The app now takes a one-copy lock at start and checks it before every order, so a second copy cannot send orders. Telegram server errors now log one plain warning.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-045.007.M03 | `src/us_swing/gui/chart_inspector.py` | Shares row from available capital with cost; Edit shares box capped at the available size |
| MD-GUI-045.007.M03 | `src/us_swing/gui/chart_workspace.py` | Passes available capital (`ChartWorkspace._available()`) to the Inspector |
| MD-GUI-045.001.M01 | `src/us_swing/gui/chart_plan.py` | Plan uses the shown shares as a fixed share count |
| MD-GUI-045.007.M03 | `src/us_swing/gui/strategy_store.py` | `StrategyConfig.fixed_qty` saved for chart plan strategies |
| MD-GUI-019.012.M01 | `src/us_swing/gui/position_trades.py` | Finds a stock's open strategy trade; exit and square-off text; pick-trade question; Stop / Trail popup |
| MD-GUI-019.013.M02 | `src/us_swing/gui/dashboard_panel.py` | Exit, Stop / Trail and Square Off All route through the strategy trade; live manual positions get a message |
| MD-GUI-019.013.M02 | `src/us_swing/gui/position_table_model.py` | A price update keeps the selected row |
| MD-GUI-002.001.M02 | `src/us_swing/gui/position_table_model.py` | `TradeHistoryModel`: Mode after Side, Value column, draggable columns, real order state |
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | Trade History rows read from the trades ledger; waiting orders shown as NEW |

Other tools (see "Other tools" below) are not repeated here.

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-045.007 | Inspector Shares row from available capital, with cost; Edit shares capped at available size | Implemented |
| SRD-GUI-045.008 | Send buys exactly the shown shares; no capital shows a message and sends nothing | Implemented |
| SRD-GUI-019.012 | A Dashboard position is a tool trade when user and stock match an open trade | Implemented |
| SRD-GUI-019.013 | Exit on a tool trade: one confirm, then full exit through that trade | Implemented |
| SRD-GUI-019.014 | Stop / Trail on a tool trade edits that trade | Implemented |
| SRD-GUI-019.015 | With two or more open tool trades, the user picks one first | Implemented |
| SRD-GUI-019.016 | Square Off All exits every tool trade after one confirm; live manual positions left, with a message | Implemented |
| SRD-GUI-019.017 | Exit or Stop / Trail on a live manual position shows a message to close it in TWS | Implemented |
| SRD-GUI-002.005 | Trade History: Mode after Side; Value column; draggable columns; real order state (ISS-GUI-0022, ISS-GUI-0023) | Reopen (fix applied; SRD stays Reopen until the user approves) |

---

## Other tools

**EXE — one-copy app lock (FO-EXE-015):** SRD-EXE-015.007 and .008 Implemented. `execution/app_lock.py` holds an OS file lock. `__main__._cmd_gui` claims it at start; a second copy shows "USSwing is already running" and closes. `BrokerAdapter.submit` checks the lock before each order and blocks the order with an `[Orders]` error if the lock is lost. MD-EXE-015.007.M01. Tests UT-EXE-015.007.M01.T01–T02, UT-EXE-015.008.M01.T01–T03. Check cost about 0.43 ms.

**EXE — fixed share count (FO-EXE-017):** SRD-EXE-017.028 Implemented. A strategy with `fixed_qty` > 0 buys that many shares (MD-EXE-017.028.M03). Capital cap still applies. Test UT-GUI-045.008.M01.T02.

**EXE — Trade History order state (FO-EXE-015, ISS-GUI-0022):** `db.manager.fetch_trades` reads the trades ledger; `broker_adapter` announces a waiting exit as NEW. Tests UT-EXE-015.002.M01.T24, UT-EXE-015.005.M01.T16.

**INF — Telegram:** Telegram server errors log one plain warning (commit e7bc15cd).

**Dashboard price update (GUI):** commit 9a684774 keeps the selected position when prices update.

---

## Design Decisions

- Chart plan size is the shares the available capital buys at Entry, editable, and sent exactly. Engine still never buys more than free capital (user decision 2026-11-20).
- Dashboard exit and stop actions go through the owning strategy trade, not a loose position (user answers 2026-11-20).
- Live manual positions are not sent direct IBKR orders; the user is told to close them in TWS. Direct IBKR orders wait for a design review (open item T218).
- One app copy only; the lock is checked before each order, not only at start.

---

## Issues Resolved

- ISS-GUI-0022: Trade History shows each order's real state.
- ISS-GUI-0023: Trade History columns resize; Value column added.

Telegram fix and the one-copy lock have no ISS ID in this batch.

---

## Test Coverage

- GUI: UT-GUI-002.005.M01.T04–T07; UT-GUI-019.012–.017 (M01 and M02 cases); UT-GUI-045.007.M03.T01, UT-GUI-045.008.M01.T01–T02, UT-GUI-045.008.M02.T01. Status per `docs/gui/UTCD.md`.
- EXE: UT-EXE-015.002.M01.T24, UT-EXE-015.005.M01.T16, UT-EXE-015.007.M01.T01–T02, UT-EXE-015.008.M01.T01–T03. Status per `docs/execution/UTCD.md` (Pass).
- User app checks still open: T214–T217, T219–T222.
