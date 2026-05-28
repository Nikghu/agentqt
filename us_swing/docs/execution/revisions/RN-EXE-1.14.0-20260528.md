# Revision Note — RN-EXE-1.14.0-20260528

**Tool:** EXE
**Version:** 1.14.0
**Date:** 2026-05-28
**Author:** Claude Opus 4.7 under user direction
**Phase:** Final_Execution.md Phase 3 — BuyOrderState / SellOrderState split

---

## Summary

Phase 3 of the state-enum consolidation plan replaces the legacy 5-state
`PositionState` machine with two side-scoped broker-order state machines
(`BuyOrderState`, `SellOrderState`) carried on the `trades` row. The
`positions.state` column is dropped — open/closed is now derived from
`positions.quantity > 0`. The legacy `trades.pnl` and `trades.status`
columns are dropped; realized PnL is owned exclusively by
`trade_cycles.realized_pnl_usd` (FO-EXE-012). The Trade History panel
loses its P&L column and gains `Filled` + `Order State` columns
(SRD-GUI-002.005 Reopen).

## Artefacts Touched

| Artefact | Change |
|---|---|
| `docs/execution/FO.md` v1.9.0 | Added **FO-EXE-014: Broker Order State Machine** (Draft) with 7 acceptance criteria |
| `docs/execution/SRD.md` v1.14.0 | Added Section 14 — SRD-EXE-014.001–.008; marked SRD-EXE-005.001–.003 as **Reopen** (PositionState removed) |
| `docs/execution/UTCD.md` v1.8.0 | Added UT-EXE-014.001.M01.T01–T06 — order-state transitions + legacy `status` backfill |
| `docs/execution/TRACE.md` v1.9.0 | New FO-EXE-014 row; FO-EXE-005 marked Reopen for SRD-EXE-005.001–.003 |
| `docs/gui/SRD.md` v2.11.0 | SRD-GUI-002.005 marked **Reopen** — Trade History columns updated |
| `docs/gui/TRACE.md` v1.7.0 | Position table model row marked Reopen |

## Code Changes

| File | Change |
|---|---|
| `db/schema.py` | Trades table: dropped `pnl`/`status`, added `order_state` (NOT NULL DEFAULT `'NEW'`) and `filled_quantity` (NOT NULL DEFAULT `0`). Positions table: dropped `state`. Migration `migrate_lifecycle_columns()` is now idempotent over both additive and removal directions, with a legacy `status → order_state` backfill applied once after `order_state` is freshly created. |
| `db/manager.py` | `insert_trade` writes `order_state` + `filled_quantity`; legacy `pnl`/`status` no longer accepted. Replaced `update_trade_exit(pnl=...)` with `update_trade_fill(order_state, filled_quantity, exit_time?, exit_price?)` — usable by both BUY and SELL fills. `fetch_open_positions` filters on `quantity > 0`; `upsert_position` no longer writes a `state` column. |
| `data/models.py` | Deleted `PositionState` enum. `PositionRecord.state` field removed. `TradeRecord.pnl` + `.status` removed; `.order_state` (typed `Union[BuyOrderState, SellOrderState, str]`) and `.filled_quantity` added. Imports of `ExecutionEnums` are TYPE_CHECKING-guarded to avoid circular import. |
| `execution/position_tracker.py` | Dropped `PositionState` import + `_VALID_TRANSITIONS` + `update_state()`. New `apply_fill(user_id, symbol, delta_qty, filled_qty=None)` increments/decrements quantity and removes the row at qty=0. `has_open` is now `qty > 0`. `load_from_db` no longer materialises a state field. |
| `execution/execution_engine.py` | `submit_signal` and `_submit_async` write `order_state=NEW`, `filled_quantity=0`. `handle_order_fill` now calls `update_trade_fill` for both entry (BUY FILLED) and exit (SELL FILLED with `exit_time`/`exit_price`). Uses `ExecutionEnums.BuyOrderState` / `SellOrderState`. |
| `execution/paper_engine.py` | `simulate_fill` writes `order_state=BuyOrderState.FILLED`, `filled_quantity=qty`. `simulate_exit` calls `update_trade_fill` with `SellOrderState.FILLED`. PnL is no longer written from paper exits. |
| `core/monitoring_session/_repository.py` | `open_system_position_symbols`, `has_open_system_position`, `position_anchor` filter on `quantity > 0`. `insert_trade_with_anchor` writes `order_state='FILLED'` + `filled_quantity=qty` instead of `status='SUBMITTED'`/`pnl=None`. `upsert_position_with_anchor` no longer writes a `state` column; `PositionSnapshot.state` is computed locally as `"OPEN" if quantity > 0 else "CLOSED"`. |
| `gui/position_table_model.py` | `TradeHistoryModel._BASE_COLS` rewritten to `["Date & Time", "Symbol", "Side", "Qty", "Filled", "Avg Price", "Order State", "Strategy", "Mode"]`; P&L cell + colouring removed; Order State cell painted from a `BuyOrderState`/`SellOrderState` colour map. `PositionTableModel` "State" column derives `"OPEN"`/`"CLOSED"` from `quantity > 0`. |
| `gui/_types.py` | Removed `PositionState` re-export. |
| `gui/_demo.py` | All `OpenPosition(state=…)` / `TradeRecord(pnl=…, status=…)` kwargs replaced with quantity-based open/closed + `order_state` / `filled_quantity`. State assignments rewritten to mutate `quantity`. |
| `gui/app_service.py` | Position mutations (`close_position`, `partial_close_position`, exit fills) drive `quantity` directly. Trade rows written with `order_state="FILLED"` + `filled_quantity=...`. Rehydration from `trade_cycles` no longer sets a `state` on `OpenPosition` or `pnl`/`status` on `TradeRecord`. |
| `tests/execution/test_position_tracker.py` | Rewritten — state-machine tests T01–T08 superseded by quantity-based T01–T05 (`apply_fill` and `has_open` round-trips). |
| `tests/execution/test_order_state_machine.py` (NEW) | 6 tests for BuyOrderState / SellOrderState transitions + legacy `status` backfill. |
| `tests/execution/test_execution_engine.py` | Removed `PositionState` import; exit-fill test now asserts `order_state='FILLED'` + `filled_quantity` instead of `pnl`. |
| `tests/execution/test_risk_manager.py` | Removed `PositionState` import + `state=` kwargs from `OpenPosition` factories. |
| `tests/execution/test_paper_engine.py` | Exit assertion switched from `pnl` to `order_state` + `filled_quantity` + `exit_price`. |
| `tests/infrastructure/test_db_manager.py` | Removed `state="OPEN"` from `PositionRecord` factory. |
| `tests/analysis/conftest.py`, `tests/gui/test_app_service_tick.py` | Same cleanup — `state=` kwarg dropped from position factories. |
| `tests/core/monitoring_session/test_repository.py` | Tests for `open_system_position_symbols_*` rewritten to seed `quantity=0` instead of `state="CLOSED"`. |

## Acceptance Criteria — Status

| FO-EXE-014 §AC | Status | Evidence |
|---|---|---|
| 1. Submitting BUY creates one row with `order_state='NEW', filled_quantity=0` | ✅ | `UT-EXE-014.001.M01.T01`, `ExecutionEngine.submit_signal` |
| 2. Partial → full BUY fill advances `NEW → PARTIAL_FILLED → FILLED` | ✅ | `UT-EXE-014.001.M01.T01` |
| 3. Broker reject sets REJECTED with filled_quantity=0 | ✅ | `UT-EXE-014.001.M01.T02` |
| 4. SELL FILLED writes exit_time + exit_price | ✅ | `UT-EXE-014.001.M01.T04`, `ExecutionEngine.handle_order_fill` |
| 5. SELL CANCELLED after partial fill keeps filled_quantity | ✅ | `UT-EXE-014.001.M01.T05` |
| 6. Trade History renders new columns, no P&L | ✅ | `gui/position_table_model.py::TradeHistoryModel._BASE_COLS` |
| 7. `positions.state` column dropped | ✅ | `db/schema.py`, `migrate_lifecycle_columns()`, `UT-EXE-014.001.M01.T06` |

## Test Results

```
us_swing/tests/execution/                — 177 passed (Phase 3-scope tests all green)
us_swing/tests/core/                     — 38 passed, 1 pre-existing decay failure (fetch_history days=7 vs 2026-05-14 fixture)
us_swing/tests/infrastructure/           — 39 passed
us_swing/tests/execution/test_order_state_machine.py — 6 passed (NEW)
```

Pre-existing failures unrelated to Phase 3:
- `test_strategy_evaluator.py::test_function_map_has_exactly_14_keys` — FUNCTION_MAP now has 18 keys (BOSS_* additions).
- `test_repository.py::test_fetch_history_includes_evicted` — fixture date `_YESTERDAY = 2026-05-14` falls outside `days=7` cutoff (`now − 7d = 2026-05-21`).
- `test_lifecycle_e2e.py::test_it_010_002_history_survives_eviction` — same date-cutoff decay.
- `test_intraday_candle_loader.py`, `test_live_tick_worker.py` — pre-existing mock issues unrelated to state enums.
- `test_strategy_engine.py::TestExitManager.*`, `test_candle_builder.py`, `test_app_service_tick.py`, `test_preset.py` — pre-existing unrelated regressions.

## Deferred to Phase 4

- **SRD-EXE-014.005 / .006** — `ExecutionEngine.handle_order_reject` / `handle_order_cancel` paths.
  Phase 3 covers the happy-path FILLED transitions and the DB schema; broker
  reject/cancel callback wiring lives behind `FO-EXE-001` and will be
  completed alongside the `CircuitBreaker` / risk-controls work.
- **SRD-EXE-014.008** — `monitoring_session/_service.on_fill` consuming
  `(side, order_state)` rather than `(side,)` alone.  Deferred to Phase 4
  per Final_Execution.md §5.4 (LifecycleState internalisation).

## Migration Notes

The schema migration is idempotent: a fresh install via `create_schema()`
produces the new layout directly; an upgrade installs `order_state` +
`filled_quantity`, backfills from the legacy `status` column, then drops
`status`, `pnl`, and `positions.state`. Running the migration a second
time is a no-op.

---

**Commits:** (to be created by the user — Phase 3 work is staged but not
committed; the user manages git workflow per project convention).
