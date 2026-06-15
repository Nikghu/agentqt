# US Swing Trading System — ToDo Backlog

**Document:** TODO.md
**Project:** us_swing
**Last Updated:** 2026-06-12 (Session 68)

---

Short, living task list. Keep each description ≤ 50 words; cite module + priority. Add/close rows as work lands.

| # | Task | Module | Priority | Status |
|---|---|---|---|---|
| T1 | FO-EXE-003 CircuitBreaker + EmergencyShutdown — pre-trade risk gate + global kill-switch. (Deferred SRD-EXE-014 wiring removed: .005–.008 now Implemented via RN-EXE-1.14.0→1.17.0.) | `execution/` | High | Open |
| T2 | `watchlist` DB table is orphaned — GUI watchlist is in-memory only. Decide: wire persistence or drop the table + index. | `db/schema.py` | Medium | Open |
| T3 | Unify table creation — register `strategy_rex_counters` in `create_schema()` like `trade_cycles`, instead of self-creating in repo `__init__`. | `db/schema.py`, `execution/strategy_engine/_rex_counter.py` | Medium | Open |
| T4 | GUI test coverage for active panels (FO-GUI-004 / FO-GUI-014). | `gui/` | Medium | Open |
| T5 | Consolidate raw `CREATE TABLE` for `price_1d`/`price_1w` onto `schema.metadata` — remove duplicate hand-maintained DDL. | `gui/app_service.py` | Low | Open |
| T6 | `positions.origin`/`anchor_session_date` written only by the monitoring path; `PositionTracker.upsert` + `DatabaseManager.upsert_position` leave them NULL, so those rows are invisible to SYSTEM-position reconciliation. Unify the write paths. | `execution/position_tracker.py`, `db/manager.py` | High | Open |
| T7 | Lifecycle `insert_trade_with_anchor` hardcodes `trades.strategy_id=None` and `mode="paper"` — live trades mis-tagged. Thread real strategy_id + mode through. | `core/monitoring_session/_repository.py` | Medium | Open |
| T8 | Partial-quantity accounting for cycles. Buy/Sell `PARTIAL_FILLED` only hold state (OPENING/CLOSING); qty not split (sell 40 of 100 → 60 residual). NOTE: `OrderEvent.filled_quantity` is **cumulative per order id** (`broker.py:90`, sim/ibkr confirmed) — **overwrite** within an order, never `+=`; drive state off cumulative vs `entry_qty`. Multi-order-per-cycle (N order ids) needs a one-cycle→many-orders link + SUM — do single-order overwrite first, multi-order as follow-up. Ref Final_Execution §5.3.5. | `execution/trade_cycle/` | Medium | Open |
| T10 | FO-EXE-017 advisory pop-up — `MainWindow._on_risk_warning` connects `risk_warning_raised` to a debounced (30 s/kind) non-blocking `QMessageBox` (SRD-EXE-017.013). | `gui/main_window.py` | Medium | Done |
| T11 | FO-EXE-017 global Margin Available ceiling — `margin_available()`, in-flight reservation ledger, per-entry clamp, paper open-value fix, live drift advisory, User View capital cell. SRD-EXE-017.015–.021 + SRD-GUI-000.006 Implemented; RN-EXE-1.25.0; merged PR #41. | `execution/`, `gui/` | High | Done |
| T12 | No pytest-qt render test for the `_AdminContextBar` capital cell (SRD-GUI-000.006). Underlying `margin_available`/`effective_capital` logic is covered; add a GUI smoke test. | `gui/main_window.py` | Low | Open |
| T13 | ISS-EXE-0007 fixed — `on_exit_fill` now matches the cycle by (strategy_id, symbol), not the oldest open cycle. Follow-up: decide whether to repair the corrupted historical row (QCOM cycle 25, wrong exit $16.965 / PNL −$371.97). RN-EXE-1.26.0. | `execution/trade_cycle/_service.py` | High | Done |
| T14 | Uncommitted Active-Trades work on the working tree — commit on a branch + PR. Three pieces: (a) pending blank Entry + live LTP + Exit $ column; (b) ISS-EXE-0007 exit-routing fix; (c) SRD-EXE-017.022 manual-monitor + popup affordability gate. SRD-GUI-014.002/.004/.005 + SRD-EXE-014.007/-017.022 amended. | `gui/active_cycles_{model,panel}.py`, `gui/app_service.py`, `execution/trade_cycle/*`, `execution/order_ingestion.py`, `execution/strategy_engine/_router.py` | High | Open |
| T15 | **Before enabling Live broker:** audit all record-resolution sites for "first match" / partial-key bugs like ISS-EXE-0007 (exit closed wrong cycle). Sweep `next(...)`, `open_cycles()`, `find_by_*` across `execution/` — every entry/exit/risk/position lookup must use the full unique key. Warn the user that this audit is required before any live trade. | `execution/` | High | Open |
| T9 | Reject path didn't abort the cycle — fixed. Added `TradeCycleService.abort_entry_order`; `OrderIngestion` REJECTED branch now aborts a partial-filled OPENING cycle. SRD-EXE-014.005 corrected (was naming the removed `ExecutionEngine.handle_order_reject`). Note: entry-only by design — exit reject must keep the cycle OPEN (you still hold the stock); the partial-sell-then-reject residual case is left to T8. | `execution/order_ingestion.py`, `execution/trade_cycle/_service.py` | High | Done |
