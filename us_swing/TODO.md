# US Swing Trading System — ToDo Backlog

**Document:** TODO.md
**Project:** us_swing
**Last Updated:** 2026-06-02 (Session 58)

---

Short, living task list. Keep each description ≤ 50 words; cite module + priority. Add/close rows as work lands.

| # | Task | Module | Priority | Status |
|---|---|---|---|---|
| T1 | FO-EXE-003 CircuitBreaker + EmergencyShutdown; also carries deferred SRD-EXE-014 wiring (live reject/cancel routing, real `order_state` to `on_fill`, `on_order_failed → on_entry_failed` map). | `execution/` | High | Open |
| T2 | `watchlist` DB table is orphaned — GUI watchlist is in-memory only. Decide: wire persistence or drop the table + index. | `db/schema.py` | Medium | Open |
| T3 | Unify table creation — register `strategy_rex_counters` in `create_schema()` like `trade_cycles`, instead of self-creating in repo `__init__`. | `db/schema.py`, `execution/strategy_engine/_rex_counter.py` | Medium | Open |
| T4 | GUI test coverage for active panels (FO-GUI-004 / FO-GUI-014). | `gui/` | Medium | Open |
| T5 | Consolidate raw `CREATE TABLE` for `price_1d`/`price_1w` onto `schema.metadata` — remove duplicate hand-maintained DDL. | `gui/app_service.py` | Low | Open |
| T6 | `positions.origin`/`anchor_session_date` written only by the monitoring path; `PositionTracker.upsert` + `DatabaseManager.upsert_position` leave them NULL, so those rows are invisible to SYSTEM-position reconciliation. Unify the write paths. | `execution/position_tracker.py`, `db/manager.py` | High | Open |
| T7 | Lifecycle `insert_trade_with_anchor` hardcodes `trades.strategy_id=None` and `mode="paper"` — live trades mis-tagged. Thread real strategy_id + mode through. | `core/monitoring_session/_repository.py` | Medium | Open |
| T8 | Partial-quantity accounting for cycles. Buy/Sell `PARTIAL_FILLED` only hold the intermediate state (OPENING/CLOSING); they don't split qty (e.g. sell 40 of 100 → 60-share residual position). Accumulate filled qty + reduce/re-open position. Ref Final_Execution §5.3.5. | `execution/trade_cycle/` | Medium | Open |
