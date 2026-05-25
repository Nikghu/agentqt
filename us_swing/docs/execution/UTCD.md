# Unit Test Case Document â€” Execution & Risk Management (EXE)

**Document ID:** UTCD-EXE
**Version:** 1.6.0
**Traces To:** MD-EXE v1.6.0
**Status:** Draft
**Last Updated:** 2026-05-25
**Project:** US Swing Trading System

> v1.6.0: UTCD-EXE-011 (Strategy Engine, 30 tests) and UTCD-EXE-012 (Trade Cycle Ledger, 25 tests) added.

> Tests written BEFORE implementation per process.md Â§7.

---

## Module: `execution/risk_manager.py` â€” RiskManager

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-001.001.M01.T01 | MD-EXE-001.001.M01 | Unit | Position size calculation: standard case | equity=$100,000; risk_pct=1%; entry=$50; stop=$48 | `500` shares (100000 Ã— 0.01 / 2 = 500) | Draft |
| UT-EXE-001.001.M01.T02 | MD-EXE-001.001.M01 | Unit | Position size capped by max_position_value | equity=$100,000; risk_pct=1%; entry=$50; stop=$49.90 (risk/share=$0.10); max_position=$10,000 | `200` shares (capped: 10000/50=200 < uncapped=10000) | Draft |
| UT-EXE-001.001.M01.T03 | MD-EXE-001.001.M01 | Unit | `validate_signal()` passes when deployment within limit | existing_deployed=$20,000; new_required=$5,000; equity=$100,000; max_pct=50% | `ValidationResult(ok=True)` | Draft |
| UT-EXE-001.001.M01.T04 | MD-EXE-001.001.M01 | Unit | `validate_signal()` rejects when deployment exceeds limit | existing_deployed=$48,000; new_required=$5,000; equity=$100,000; max_pct=50% | `ValidationResult(ok=False, reason contains "capital allocation")` | Draft |
| UT-EXE-001.001.M01.T05 | MD-EXE-001.001.M01 | Unit | `validate_signal()` rejects when circuit breaker active | `circuit_breaker_active=True` | `ValidationResult(ok=False, reason contains "circuit breaker")` | Draft |
| UT-EXE-001.001.M01.T06 | MD-EXE-001.001.M01 | Edge | `calculate_position_size()` floors fractional shares | risk/share=$3.00; risk_dollars=$1,000 â†’ 333.33 | Returns `333` (floor) | Draft |

---

## Module: `execution/execution_engine.py` â€” ExecutionEngine

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-001.001.M02.T01 | MD-EXE-001.001.M02 | Unit | `submit_signal()` calls IBKR place_order when validation passes | Mock `RiskManager.validate_signal` â†’ `ok=True`; Mock IBKR returns order_id=123 | `submit_signal()` returns 123; IBKR `place_order()` called once | Draft |
| UT-EXE-001.001.M02.T02 | MD-EXE-001.001.M02 | Unit | `submit_signal()` returns None when validation fails | Mock `RiskManager.validate_signal` â†’ `ok=False` | Returns `None`; IBKR `place_order()` NOT called; WARNING logged | Draft |
| UT-EXE-001.001.M02.T03 | MD-EXE-001.001.M02 | Unit | `submit_signal()` persists trade to DB on success | Successful submission | `TradeRecord` with `trade_id=123` appears in `trades` table | Draft |
| UT-EXE-001.001.M02.T04 | MD-EXE-001.001.M02 | Edge | `submit_signal()` raises `OrderSubmissionError` on IBKR timeout | Mock IBKR place_order to hang > timeout=2s | `OrderSubmissionError` raised | Draft |
| UT-EXE-001.001.M02.T05 | MD-EXE-001.001.M02 | Unit | `handle_order_fill()` on entry fill creates OpenPosition with user_id | Entry fill event for AAPL 500 shares @ $50, user_id=1 | `PositionTracker.has_open(1, "AAPL")` is True; position.state == 'OPEN' | Draft |
| UT-EXE-001.001.M02.T06 | MD-EXE-001.001.M02 | Unit | `handle_order_fill()` on exit fill updates trade PnL in DB | Exit fill for AAPL @ $55; entry was $50; qty=500; user_id=1 | `trades.pnl == 2500.0`; position.state == 'CLOSED' | Draft |
| UT-EXE-001.001.M02.T07 | MD-EXE-001.001.M02 | Unit | `exit_position()` submits SELL for full open quantity | `PositionTracker` has AAPL qty=500 | IBKR SELL 500 AAPL market order submitted | Draft |

---

## Module: `execution/position_tracker.py` â€” PositionTracker

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-002.001.M01.T01 | MD-EXE-002.001.M01 | Unit | `has_open()` returns False initially | Fresh tracker, user_id=1 | `has_open(1, "AAPL")` is False | Draft |
| UT-EXE-002.001.M01.T02 | MD-EXE-002.001.M01 | Unit | `open()` + `has_open()` round-trip with user_id | Open AAPL position for user_id=1 | `has_open(1, "AAPL")` is True; `has_open(2, "AAPL")` is False | Draft |
| UT-EXE-002.001.M01.T03 | MD-EXE-002.001.M01 | Unit | `close()` removes position from tracker | Open then close AAPL for user_id=1 | `has_open(1, "AAPL")` is False after close | Draft |
| UT-EXE-002.001.M01.T04 | MD-EXE-002.001.M01 | Unit | `reconcile()` adopts unrecognised IBKR positions | IBKR returns MSFT position not in local DB | `has_open("MSFT")` is True; WARNING logged | Draft |
| UT-EXE-002.001.M01.T05 | MD-EXE-002.001.M01 | Unit | `update_stop()` changes stop_loss per user | Open position with stop=48.0; call `update_stop(1, "AAPL", 49.0)` | `position.stop_loss == 49.0` | Draft |

---

## Module: `execution/circuit_breaker.py` â€” DailyPnLTracker & CircuitBreaker

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-003.001.M01.T01 | MD-EXE-003.001.M01 | Unit | `DailyPnLTracker` accumulates PnL | `add(-500)`, `add(-300)` | `daily_pnl == -800` | Draft |
| UT-EXE-003.001.M01.T02 | MD-EXE-003.001.M01 | Unit | `reset()` zeroes PnL | `add(-500)` then `reset()` | `daily_pnl == 0` | Draft |
| UT-EXE-003.001.M01.T03 | MD-EXE-003.001.M01 | Unit | `CircuitBreaker.check()` returns True at threshold | equity=$100,000; max_daily_loss_pct=2%; daily_pnl=-2000 | `True` (breach) | Draft |
| UT-EXE-003.001.M01.T04 | MD-EXE-003.001.M01 | Unit | `CircuitBreaker.check()` returns False below threshold | daily_pnl=-1999 | `False` | Draft |
| UT-EXE-003.001.M01.T05 | MD-EXE-003.001.M01 | Edge | Exactly at threshold triggers breach | daily_pnl=-2000.00; threshold=-2000.00 | `True` (â‰¤ is inclusive) | Draft |

---

## Module: `execution/emergency.py` â€” EmergencyShutdown

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-003.001.M02.T01 | MD-EXE-003.001.M02 | Unit | `run()` cancels all pending orders | Mock IBKR; 2 pending orders | `IBKRClient.cancel_all_orders()` called exactly once | Draft |
| UT-EXE-003.001.M02.T02 | MD-EXE-003.001.M02 | Unit | `run()` closes all open positions | 2 open positions (AAPL, MSFT) | `ExecutionEngine.exit_position()` called for each symbol | Draft |
| UT-EXE-003.001.M02.T03 | MD-EXE-003.001.M02 | Unit | `run()` logs CRITICAL event | Any trigger reason | CRITICAL log entry with the reason string | Draft |
| UT-EXE-003.001.M02.T04 | MD-EXE-003.001.M02 | Unit | After `run()`, new signals are discarded | Call `submit_signal()` after `circuit_breaker_active=True` | Signal discarded; DEBUG logged; no IBKR call | Draft |
| UT-EXE-003.001.M02.T05 | MD-EXE-003.001.M02 | Unit | Shutdown JSON written to logs/ | `run("daily_loss_limit")` | File `logs/shutdown_*.json` exists with required keys | Draft |
| UT-EXE-003.001.M02.T06 | MD-EXE-003.001.M02 | Edge | IBKR error during shutdown is logged but not re-raised | Mock `cancel_all_orders()` to raise `IBKRError` | ERROR logged; shutdown continues; no exception propagates | Draft |

---

## Module: `execution/paper_engine.py` â€” PaperEngine

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-004.001.M01.T01 | MD-EXE-004.001.M01 | Unit | Market order fills immediately at current market price | signal BUY AAPL, order_type='MKT', mock market_price=$150 | `PaperFill` with `fill_price == 150.0` | Draft |
| UT-EXE-004.001.M01.T02 | MD-EXE-004.001.M01 | Unit | Limit buy fills when market price â‰¤ limit | signal BUY AAPL limit=$150, mock market_price=$149 | `PaperFill` with `fill_price == 150.0` | Draft |
| UT-EXE-004.001.M01.T03 | MD-EXE-004.001.M01 | Unit | Limit buy does NOT fill when market price > limit | signal BUY AAPL limit=$150, mock market_price=$151 | Returns None or queues pending order | Draft |
| UT-EXE-004.001.M01.T04 | MD-EXE-004.001.M01 | Unit | Paper fills stored with `mode='paper'` in DB | Simulate fill for user_id=1. | `trades` row has `mode='paper'`; `positions` row has `mode='paper'` | Draft |
| UT-EXE-004.001.M01.T05 | MD-EXE-004.001.M01 | Unit | Paper P&L matches live calculation | Entry=$50, exit=$55, qty=500 | `pnl == 2500.0` (identical to live) | Draft |
| UT-EXE-004.001.M01.T06 | MD-EXE-004.001.M01 | Unit | Paper order IDs are negative (distinguishable from IBKR) | Simulate 3 fills | All order_ids < 0 and monotonically decreasing | Draft |
| UT-EXE-004.001.M01.T07 | MD-EXE-004.001.M01 | Edge | No IBKR API calls made during paper fill | Mock IBKR client with side_effect=AssertionError | No assertion error raised; fill succeeds | Draft |

---

## Module: `execution/execution_router.py` â€” ExecutionRouter

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-004.001.M02.T01 | MD-EXE-004.001.M02 | Unit | Routes to PaperEngine when user mode is 'paper' | user.mode='paper', valid signal | `PaperEngine.simulate_fill()` called; `ExecutionEngine.submit_signal()` NOT called | Draft |
| UT-EXE-004.001.M02.T02 | MD-EXE-004.001.M02 | Unit | Routes to live ExecutionEngine when user mode is 'live' | user.mode='live', valid signal | `ExecutionEngine.submit_signal()` called; `PaperEngine.simulate_fill()` NOT called | Draft |
| UT-EXE-004.001.M02.T03 | MD-EXE-004.001.M02 | Unit | Mode check per-signal, not cached | User starts in 'paper', switches to 'live' mid-session | First signal â†’ PaperEngine; second signal â†’ ExecutionEngine | Draft |

---

## Module: `execution/position_tracker.py` â€” Position State Machine

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-005.001.M01.T01 | MD-EXE-002.001.M01 | Unit | New position starts in state NEW | Open position via `open()` | `position.state == 'NEW'` | Draft |
| UT-EXE-005.001.M01.T02 | MD-EXE-002.001.M01 | Unit | Partial entry fill transitions NEW â†’ PARTIAL_ENTRY | `update_state(user_id, sym, 'PARTIAL_ENTRY', filled_qty=200)` | `state == 'PARTIAL_ENTRY'`; `filled_quantity == 200` | Draft |
| UT-EXE-005.001.M01.T03 | MD-EXE-002.001.M01 | Unit | Full entry fill transitions NEW â†’ OPEN | `update_state(user_id, sym, 'OPEN', filled_qty=500)` | `state == 'OPEN'`; `filled_quantity == 500` | Draft |
| UT-EXE-005.001.M01.T04 | MD-EXE-002.001.M01 | Unit | PARTIAL_ENTRY â†’ OPEN on final fill | State currently PARTIAL_ENTRY(200/500); update to OPEN(500/500) | `state == 'OPEN'`; `filled_quantity == total_quantity` | Draft |
| UT-EXE-005.001.M01.T05 | MD-EXE-002.001.M01 | Unit | OPEN â†’ PARTIAL_EXIT on partial exit | `update_state(user_id, sym, 'PARTIAL_EXIT', filled_qty=300)` | `state == 'PARTIAL_EXIT'` | Draft |
| UT-EXE-005.001.M01.T06 | MD-EXE-002.001.M01 | Unit | PARTIAL_EXIT â†’ CLOSED on final exit | `update_state(user_id, sym, 'CLOSED', filled_qty=500)` | `state == 'CLOSED'` | Draft |
| UT-EXE-005.001.M01.T07 | MD-EXE-002.001.M01 | Edge | Invalid transition CLOSED â†’ OPEN raises error | Attempt `update_state(user_id, sym, 'OPEN')` on CLOSED position | `InvalidStateTransitionError` raised | Draft |
| UT-EXE-005.001.M01.T08 | MD-EXE-002.001.M01 | Edge | Invalid transition NEW â†’ PARTIAL_EXIT raises error | Attempt `update_state(user_id, sym, 'PARTIAL_EXIT')` on NEW position | `InvalidStateTransitionError` raised | Draft |
| UT-EXE-005.001.M01.T09 | MD-EXE-002.001.M01 | Unit | `load_from_db()` restores non-CLOSED positions | DB has 2 OPEN, 1 CLOSED for user_id=1 | Tracker has 2 positions; CLOSED position excluded | Draft |

---

## Module: `execution/risk_manager.py` â€” Capital Check & Quantity Override

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-005.004.M01.T01 | MD-EXE-001.001.M01 | Unit | `can_enter_new()` returns True when capital available | equity=$100k, open_value=$20k, signal cost=$10k, max_pct=50% | `True` | Draft |
| UT-EXE-005.004.M01.T02 | MD-EXE-001.001.M01 | Unit | `can_enter_new()` returns False when capital exhausted | equity=$100k, open_value=$45k, signal cost=$10k, max_pct=50% | `False` | Draft |
| UT-EXE-005.004.M01.T03 | MD-EXE-001.001.M01 | Unit | `can_enter_new()` scoped per user_id | user1 has $40k deployed; user2 has $0; max_pct=50% each | user1 â†’ True for $5k; user2 â†’ True for $45k | Draft |
| UT-EXE-005.005.M02.T01 | MD-EXE-001.001.M02 | Unit | `submit_signal()` with `quantity_override` uses override quantity | override=100; calculated would be 500 | Order submitted for 100 shares | Draft |
| UT-EXE-005.005.M02.T02 | MD-EXE-001.001.M02 | Unit | Override quantity still checked by capital availability | override=5000 (exceeds capital), equity=$50k, max_pct=50% | Order rejected; returns None | Draft |
| UT-EXE-005.005.M02.T03 | MD-EXE-001.001.M02 | Edge | Override quantity â‰¤ 0 raises ValueError | `quantity_override=0` | `ValueError` raised | Draft |

---

## Module: `execution/intraday_candle_loader.py` â€” IntradayCandleLoader

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-006.001.M01.T01 | MD-EXE-006.001.M01 | Positive | Full fetch for new symbol inserts 1 m bars into DB | Symbol with no prior `price_1m` rows; mock IBKR returns 1 000 1 m bars across 4 paged requests | `DatabaseManager.insert_bars()` called; `price_1m` has 1 000 rows for symbol | Pass |
| UT-EXE-006.001.M01.T02 | MD-EXE-006.001.M01 | Positive | Delta fetch inserts only bars after last stored timestamp | Symbol with last `price_1m` timestamp = T; mock IBKR returns 50 bars with datetime > T | 50 rows inserted; IBKR request duration covers only period after T | Pass |
| UT-EXE-006.001.M01.T03 | MD-EXE-006.001.M01 | Negative | Delta fetch is idempotent â€” re-run inserts 0 duplicate rows | Symbol already up-to-date; IBKR returns 0 new bars | `insert_bars()` called with empty list; row count unchanged; no error | Pass |
| UT-EXE-006.001.M01.T04 | MD-EXE-006.001.M01 | Positive | Validation passes when both timeframes (3m, 15m) have â‰¥ 390 candles | Symbol with 8 190 1 m bars (â‰ˆ 21 trading days) in DB; `aggregate_timeframe()` returns: 3 m=2 730, 15 m=546 | `_validate_candle_counts()` returns `CandleLoadResult(ok=True)` | Pass |
| UT-EXE-006.001.M01.T05 | MD-EXE-006.001.M01 | Negative | Validation fails when a timeframe has < 390 candles | Symbol with only 400 1 m bars; 3 m â†’ 133, 15 m â†’ 26 (both < 390) | `_validate_candle_counts()` returns `CandleLoadResult(ok=False, reason='insufficient_candles:3m:133')` | Pass |
| UT-EXE-006.001.M01.T06 | MD-EXE-006.001.M01 | Negative | IBKR error for one symbol does not abort remaining symbols | 3-symbol list; IBKR raises `IBKRHistoricalDataError` for symbol[1] | symbol[0] and symbol[2] processed successfully; symbol[1] in `load_complete.failed`; WARNING logged | Pass |
| UT-EXE-006.001.M01.T07 | MD-EXE-006.001.M01 | Positive | `load_complete` signal emitted with full result list | 3 symbols, 1 success + 1 validation fail + 1 IBKR error | `load_complete` fires once; payload is `list[CandleLoadResult]` with 3 items; failed count = 2 | Pass |
| UT-EXE-006.001.M01.T08 | MD-EXE-006.001.M01 | Positive | `load_progress` signal emitted once per symbol | 5-symbol list | `load_progress` fired 5 times; final call has `done == total == 5` | Pass |
| UT-EXE-006.001.M01.T09 | MD-EXE-006.001.M01 | Positive | `get_readiness_report()` returns ready=True when all counts â‰¥ 390 | DB has 14 000 1 m bars for AAPL spanning â‰¥ 60 trading days | `report['AAPL'].ready == True`; `report['AAPL'].candles_3m >= 390` | Pass |
| UT-EXE-006.001.M01.T10 | MD-EXE-006.001.M01 | Negative | `get_readiness_report()` returns ready=False when any timeframe < 390 | DB has 300 1 m bars for MSFT | `report['MSFT'].ready == False`; at least one candle count < 390 | Pass |
| UT-EXE-006.001.M01.T11 | MD-EXE-006.001.M01 | Edge | Full-fetch paging: 65 trading-day window requires multiple IBKR requests | New symbol; full fetch mode | `IBKRClient.req_historical_data()` called â‰¥ 3 times (pages); all results concatenated before insert | Pass |
| UT-EXE-006.001.M01.T12 | MD-EXE-006.001.M01 | Negative | `load()` with empty symbol list completes immediately with no DB writes | `symbols=[]` | `load_complete` emitted with empty results list; `insert_bars()` never called | Pass |
| UT-EXE-006.001.M01.T13 | MD-EXE-006.001.M01 | Negative | Minimum candle window check â€” IBKR returns fewer bars than 65-day target (truncated history for new listing) | New symbol; IBKR returns only 800 1 m bars (â‰ˆ 2 days) for full-fetch window | Symbol included in failed list with reason `'insufficient_candles'`; no exception propagates; remaining symbols continue | Pass |

---

## Module: `execution/live_bar_worker.py` â€” LiveBarWorker

> Test file: `tests/execution/test_live_bar_worker.py`
> Fixtures: mock `ib_insync.IB` (records `reqRealTimeBars` calls + fires `updateEvent`), in-memory SQLite for `price_3m`/`price_15m`, `CandleBuilder` instance.

### Helper tests (`_floor_3m`, `_is_rth`, `PartialBar.to_ohlcv_bar`)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-007.001.M01.T01 | MD-EXE-007.001.M01 | Positive | `_floor_3m()` floors to correct 3m ET boundary (summer, UTC-4) | `dt_utc = 2026-06-15 13:34:47 UTC` (= 09:34:47 ET) | Returns `2026-06-15 13:33:00 UTC` (= 09:33 ET) | Draft |
| UT-EXE-007.001.M01.T02 | MD-EXE-007.001.M01 | Edge | `_floor_3m()` correct under winter UTC offset (UTC-5) | `dt_utc = 2026-01-07 14:31:00 UTC` (= 09:31 ET winter) | Returns `2026-01-07 14:30:00 UTC` (= 09:30 ET) | Draft |
| UT-EXE-007.001.M01.T03 | MD-EXE-007.001.M01 | Positive | `_is_rth()` returns True at 09:30:00 ET on a weekday | `dt_utc` for a Monday at exactly 09:30:00 ET | `True` | Draft |
| UT-EXE-007.001.M01.T04 | MD-EXE-007.001.M01 | Edge | `_is_rth()` returns False at exactly 16:00:00 ET (upper boundary excluded) | `dt_utc` for Wednesday 16:00:00 ET | `False` | Draft |
| UT-EXE-007.001.M01.T05 | MD-EXE-007.001.M01 | Edge | `_is_rth()` returns False on Saturday regardless of time | `dt_utc` for Saturday 12:00:00 ET | `False` | Draft |
| UT-EXE-007.001.M01.T06 | MD-EXE-007.001.M01 | Positive | `PartialBar.to_ohlcv_bar()` returns `OHLCVBar` with `timeframe='3m'` and `datetime == window_start` | `PartialBar(symbol='AAPL', window_start=T, open=100, high=105, low=99, close=103, volume=5000, tick_count=6)` | `OHLCVBar(symbol='AAPL', datetime=T, open=100, high=105, low=99, close=103, volume=5000, timeframe='3m')` | Draft |

### Tick processing â€” `_on_realtime_bar` (SRD-EXE-007.005)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-007.001.M01.T07 | MD-EXE-007.001.M01 | Positive | First tick for a subscribed symbol creates `PartialBar` with `open == bar.open` and `tick_count == 1` | Aggregator subscribed to `'AAPL'`; one `RealtimeBar(symbol='AAPL', datetime=09:31:00 ET, open=150.0, high=150.5, low=149.8, close=150.2, volume=800)` | `_partials['AAPL'].open == 150.0`, `tick_count == 1` | Draft |
| UT-EXE-007.001.M01.T08 | MD-EXE-007.001.M01 | Positive | Same-window tick updates high, low, close, volume, tick_count; open is unchanged | Existing `PartialBar(open=150.0, high=150.5, low=149.8, close=150.2, volume=800, tick_count=1)`; second bar arrives in same 3m window: `high=151.0, low=149.5, close=150.8, volume=600` | `high=151.0, low=149.5, close=150.8, volume=1400, tick_count=2, open=150.0` (open unchanged) | Draft |
| UT-EXE-007.001.M01.T09 | MD-EXE-007.001.M01 | Positive | New-window tick finalises old `PartialBar` and creates a fresh one with correct open | One complete partial bar in window 09:30â€“09:33; new bar arrives at 09:33:05 ET | `candle_closed` emitted for the 09:30 window; new `PartialBar` created with `window_start=09:33` and `open == new_bar.open` | Draft |
| UT-EXE-007.001.M01.T10 | MD-EXE-007.001.M01 | Negative | Tick before RTH (08:00 ET) is discarded â€” no `PartialBar` created, no signal emitted | `RealtimeBar` with `datetime=08:00:05 ET` for subscribed `'AAPL'` | `_partials` remains empty; `candle_updated` NOT emitted | Draft |
| UT-EXE-007.001.M01.T11 | MD-EXE-007.001.M01 | Negative | Tick after RTH (16:01 ET) discarded; existing `PartialBar` unchanged | Partial bar exists for `'AAPL'`; bar arrives at 16:01:00 ET | `_partials['AAPL']` unchanged (`tick_count` not incremented); no signal emitted | Draft |
| UT-EXE-007.001.M01.T12 | MD-EXE-007.001.M01 | Negative | Tick for symbol not in `_subscribed` is silently discarded | `'TSLA'` not subscribed; `RealtimeBar` arrives for `'TSLA'` | `_partials` unchanged; `candle_updated` NOT emitted | Draft |

### Signal emission (SRD-EXE-007.003)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-007.001.M01.T13 | MD-EXE-007.001.M01 | Positive | `candle_updated` emitted with correct symbol and `PartialBar` on every RTH tick | Two 5-second bars arrive for `'AAPL'` in same 3m window | `candle_updated` fired twice; second emission's `PartialBar.tick_count == 2` | Draft |
| UT-EXE-007.001.M01.T14 | MD-EXE-007.001.M01 | Positive | `candle_closed` emitted with correct `OHLCVBar` when 3m boundary crossed | First window complete with 6 ticks; new bar from next window arrives | `candle_closed` emitted once with `OHLCVBar(timeframe='3m', datetime=window_start)`; `candle_updated` also emitted for the new partial | Draft |

### `_close_bar` + DB persistence (SRD-EXE-007.006)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-007.001.M01.T15 | MD-EXE-007.001.M01 | Positive | `_close_bar()` calls `insert_bars(symbol, '3m', [bar])` with the finalised `OHLCVBar` | Partial bar with `window_start=T` closed | `DatabaseManager.insert_bars` called with `timeframe='3m'`; in-memory SQLite `price_3m` contains exactly 1 row for `(symbol, T)` | Draft |
| UT-EXE-007.001.M01.T16 | MD-EXE-007.001.M01 | Edge | `_close_bar()` is idempotent â€” second call for same `(symbol, window_start)` inserts 0 rows | `_close_bar()` called twice with identical `PartialBar` | `price_3m` row count for `(symbol, T)` remains 1 (INSERT OR IGNORE); no exception | Draft |

### Dynamic subscription â€” `set_symbols` (SRD-EXE-007.004)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-007.001.M01.T17 | MD-EXE-007.001.M01 | Positive | `set_symbols()` subscribes new symbols via `subscribe_realtime_bars` | Aggregator has `_subscribed={'AAPL'}`; call `set_symbols(['AAPL', 'MSFT'])` | `subscribe_realtime_bars('MSFT')` called once; `subscribe_realtime_bars('AAPL')` NOT called again | Draft |
| UT-EXE-007.001.M01.T18 | MD-EXE-007.001.M01 | Positive | `set_symbols()` unsubscribes removed symbols and clears their `PartialBar` | `_subscribed={'AAPL','MSFT'}`; partial bar exists for both; call `set_symbols(['AAPL'])` | `unsubscribe_realtime_bars('MSFT')` called; `_partials` no longer contains `'MSFT'`; `'AAPL'` partial bar intact | Draft |
| UT-EXE-007.001.M01.T19 | MD-EXE-007.001.M01 | Edge | `set_symbols()` with identical list makes no IBKR calls | `_subscribed={'AAPL'}`; call `set_symbols(['AAPL'])` | Neither `subscribe_realtime_bars` nor `unsubscribe_realtime_bars` called | Draft |

### RTH session-end discard (SRD-EXE-007.007)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-007.001.M01.T20 | MD-EXE-007.001.M01 | Positive | `_check_session_end()` at 16:01 ET clears all partial bars without any DB writes | Two partial bars exist for `'AAPL'` and `'MSFT'`; `_check_session_end()` called with mocked time = 16:01 ET | `_partials` is empty; `insert_bars` NOT called; INFO logged with count `"2 partial bar(s) discarded"` | Draft |
| UT-EXE-007.001.M01.T21 | MD-EXE-007.001.M01 | Edge | `_check_session_end()` during RTH (13:00 ET) â€” no action | Partial bars exist; call with mocked time = 13:00 ET | `_partials` unchanged; no log message; no DB write | Draft |

### Disconnect / reconnect (SRD-EXE-007.008)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-007.001.M01.T22 | MD-EXE-007.001.M01 | Positive | `on_disconnect()` clears `_partials` and `_subscribed`; WARNING logged with discard count | Aggregator subscribed to 3 symbols with partial bars for each | `_partials == {}`; `_subscribed == set()`; WARNING log contains `"3 partial bar(s) discarded"`; `insert_bars` NOT called | Draft |
| UT-EXE-007.001.M01.T23 | MD-EXE-007.001.M01 | Positive | After `on_reconnect(symbols)`, first tick for a symbol creates a fresh `PartialBar` (no residual state) | `on_disconnect()` then `on_reconnect(['AAPL'])`; RTH tick arrives for `'AAPL'` | `subscribe_realtime_bars('AAPL')` called on reconnect; new `PartialBar` created with `tick_count == 1`; no stale data from pre-disconnect session | Draft |

### Schema extension and readiness report integration (SRD-EXE-007.001, SRD-EXE-007.009)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-007.001.M01.T24 | MD-EXE-007.001.M01 | Integration | `price_3m` table created by `create_schema(checkfirst=True)` without error; existing `price_1m` unaffected | In-memory SQLite engine with pre-existing `price_1m` rows; call `create_schema(engine)` | `price_3m` table exists and accepts INSERT; `price_1m` row count unchanged | Draft |
| UT-EXE-007.001.M01.T25 | MD-EXE-007.001.M01 | Integration | After `candle_closed` persists a 3m bar, `get_readiness_report` returns `candles_3m` = prior count + 1 | `price_3m` has 391 rows for `'AAPL'`; `_close_bar()` inserts 1 more row (new window) | `get_readiness_report(['AAPL']).candles_3m == 392` | Draft |
| UT-EXE-007.001.M01.T26 | MD-EXE-007.001.M01 | Integration | `get_readiness_report` `candles_3m` reads from `price_3m` not `price_1m` | `price_1m` has 0 rows for `'AAPL'`; `price_3m` has 400 rows for `'AAPL'` | `get_readiness_report(['AAPL']).candles_3m == 400` (not 0) | Draft |

---

## Module: `execution/live_tick_worker.py` â€” LiveTickWorker

### Class construction & signals (SRD-EXE-008.001)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-008.001.M01.T01 | MD-EXE-008.001.M01 | Positive | `LiveTickWorker` is a `QThread` subclass with `tick_price` and `subscription_failed` signals | `LiveTickWorker("127.0.0.1", 7497, 14)` | `isinstance(w, QThread) is True`; `hasattr(w, "tick_price") and hasattr(w, "subscription_failed")` | Pass |
| UT-EXE-008.001.M01.T02 | MD-EXE-008.001.M01 | Negative | Worker not started â€” no `tick_price` emitted when `_on_pending_tickers` is called directly | Instantiate worker (do not call `start()`); call `_on_pending_tickers({mock_ticker})` | `tick_price` signal not emitted (no running event loop; `_tag_by_conid` is empty) | Pass |
| UT-EXE-008.001.M01.T16 | MD-EXE-008.001.M01 | Negative | `live_tick_worker` module imports no GUI or DB module at module level | `import us_swing.execution.live_tick_worker`; inspect `sys.modules` | No `PyQt6.QtWidgets`, `gui`, or `db` module present in `sys.modules` as a side-effect of the import | Pass |

### set_contracts() reconciliation (SRD-EXE-008.002)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-008.001.M01.T03 | MD-EXE-008.001.M01 | Positive | `set_contracts({"AAPL": stk_contract})` calls `ib.reqMktData` exactly once for AAPL | Worker with mocked `ib`; call `set_contracts({"AAPL": stk_contract})` | `mock_ib.reqMktData.call_count == 1`; `"AAPL"` in `worker._active` | Pass |
| UT-EXE-008.001.M01.T04 | MD-EXE-008.001.M01 | Positive | `set_contracts({})` after subscribing AAPL calls `ib.cancelMktData` for AAPL | Subscribe AAPL; then `set_contracts({})` | `mock_ib.cancelMktData.call_count == 1`; `worker._active == {}` | Pass |
| UT-EXE-008.001.M01.T05 | MD-EXE-008.001.M01 | Negative | Calling `set_contracts` twice with the same tag does not duplicate the subscription | `set_contracts({"AAPL": c})`; `set_contracts({"AAPL": c})` | `mock_ib.reqMktData.call_count == 1` (not 2); no duplicate in `_active` | Pass |
| UT-EXE-008.001.M01.T06 | MD-EXE-008.001.M01 | Edge | 15-contract call is split into two batches of 10 + 5 with a pause between | `set_contracts({sym: contract for sym in 15_symbols})` with mocked `time.sleep` | `time.sleep` called exactly once with arg `0.20`; `reqMktData` called 15 times total | Pass |

### tick_price emission (SRD-EXE-008.003)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-008.001.M01.T07 | MD-EXE-008.001.M01 | Positive | `_on_pending_tickers` emits `tick_price` when `ticker.last` is valid | `ticker.last=150.0`; `ticker.contract.conId=123`; `_tag_by_conid={123: "AAPL"}` | `tick_price` emitted with args `("AAPL", 150.0)` | Pass |
| UT-EXE-008.001.M01.T08 | MD-EXE-008.001.M01 | Positive | Falls back to `ticker.close` when `ticker.last` is NaN | `ticker.last=nan`; `ticker.close=149.5`; conId mapped to `"AAPL"` | `tick_price` emitted with args `("AAPL", 149.5)` | Pass |
| UT-EXE-008.001.M01.T09 | MD-EXE-008.001.M01 | Negative | No emission when both `ticker.last` and `ticker.close` are NaN | `ticker.last=nan`; `ticker.close=nan`; conId mapped to `"AAPL"` | `tick_price` signal NOT emitted | Pass |

### Error handling â€” subscription_failed (SRD-EXE-008.004)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-008.001.M01.T10 | MD-EXE-008.001.M01 | Positive | IBKR error 354 â†’ `subscription_failed("AAPL", 354)` emitted; AAPL removed from `_active` | AAPL subscribed (`reqId=42` mapped); call `_on_ibkr_error(42, 354, "msg", contract)` | `subscription_failed` emitted with `("AAPL", 354)`; `"AAPL" not in worker._active` | Pass |
| UT-EXE-008.001.M01.T11 | MD-EXE-008.001.M01 | Negative | Non-subscription error code (e.g. 321) â†’ no `subscription_failed`; other subscriptions unaffected | AAPL and MSFT subscribed; call `_on_ibkr_error(reqId_AAPL, 321, "msg", contract)` | `subscription_failed` NOT emitted; `"AAPL"` and `"MSFT"` still in `_active` | Pass |

### request_stop() (SRD-EXE-008.005)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-008.001.M01.T12 | MD-EXE-008.001.M01 | Positive | `request_stop()` sets `_stop_event` and calls `cancelMktData` for every active subscription | Two symbols subscribed; call `request_stop()` | `worker._stop_event.is_set() is True`; `mock_ib.cancelMktData.call_count == 2` | Pass |
| UT-EXE-008.001.M01.T13 | MD-EXE-008.001.M01 | Positive | Thread exits within 3 s after `request_stop()` | Start worker (mocked IBKR); call `request_stop()`; join with 3 s timeout | `worker.isFinished() is True` within 3 s | Pass |

### ClientId collision retry (SRD-EXE-008.006)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-008.001.M01.T14 | MD-EXE-008.001.M01 | Positive | IBKR error 326 on first connect â†’ retry with clientId+1 succeeds; WARNING logged | Mock `ib.connectAsync` to fail with 326 once then succeed; `initial_client_id=14` | Second connect attempt uses clientId=15; WARNING contains "ClientId 14 in use"; worker not stopped | Pass |
| UT-EXE-008.001.M01.T15 | MD-EXE-008.001.M01 | Negative | 4 consecutive error 326 â†’ logs ERROR; thread exits; no `tick_price` emitted | Mock `ib.connectAsync` to always fail with 326 | `log.error` called with message containing "Cannot connect"; thread exits; `tick_price` never emitted | Pass |

---

## Module: `core/monitoring_session/_dto.py` + `_enums.py` — DTOs & Enums

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-009.001.M01.T01 | MD-EXE-009.001.M01 | Positive | Every DTO is frozen and slotted | Construct `KeepSet`, `ReconcileReport`, `MonitoringSessionRow`, `FillEvent`, `InvariantReport`, `ReconcileError` | Each instance has `__slots__`; assignment to any field raises `FrozenInstanceError` | Pass |
| UT-EXE-009.001.M02.T01 | MD-EXE-009.001.M01 | Positive | Every DTO exposes `schema_version: int = 1` | Default-construct each DTO | `instance.schema_version == 1` for every DTO type | Pass |
| UT-EXE-009.001.M03.T01 | MD-EXE-009.001.M01 | Negative | Mutation attempt fails on a frozen DTO | `ks = KeepSet(...); ks.filtered = frozenset({"X"})` | `dataclasses.FrozenInstanceError` raised | Pass |
| UT-EXE-009.001.M04.T01 | MD-EXE-009.001.M01 | Positive | `LifecycleState`, `TradeOrigin`, `Side` round-trip raw strings | `LifecycleState("ENTERED")`, `TradeOrigin("system")`, `Side("BUY")` | Each enum resolves; `.value` returns the raw string | Pass |

---

## Module: `core/monitoring_session/_protocols.py` — Protocol Surface

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-009.001.M02.T02 | MD-EXE-009.001.M02 | Positive | All three Protocols are `@runtime_checkable` | Inspect `MonitoringQuery`, `MonitoringCommand`, `MonitoringEventBus` | `typing.get_protocol_attrs(...)` non-empty; each is `runtime_checkable` | Pass |
| UT-EXE-009.001.M02.T03 | MD-EXE-009.001.M02 | Positive | Concrete service passes `isinstance` checks against both Protocols | `svc, cmd, bus = build_default_service(engine)` (svc is the same object) | `isinstance(svc, MonitoringQuery)` and `isinstance(svc, MonitoringCommand)` both `True` | Pass |

---

## Module: `core/monitoring_session/_events.py` — Event Bus & Sealed Union

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-009.001.M03.T02 | MD-EXE-009.001.M03 | Positive | `publish` invokes the registered handler synchronously | Subscribe handler for `SymbolStartedMonitoring`; publish one event | Handler called exactly once before `publish` returns; payload equals input | Pass |
| UT-EXE-009.001.M03.T03 | MD-EXE-009.001.M03 | Positive | `Subscription.cancel()` detaches the handler | Subscribe, cancel, publish | Handler is NOT called | Pass |
| UT-EXE-009.001.M03.T04 | MD-EXE-009.001.M03 | Negative | A handler exception is caught, logged, and sibling handlers still run | Two handlers; first raises `RuntimeError` | Second handler still called; ERROR log with `[Lifecycle]` topic; `publish` returns normally | Pass |
| UT-EXE-009.001.M03.T05 | MD-EXE-009.001.M03 | Edge | `publish` with no subscribers is a no-op | Publish `SymbolEvicted` with no subscriptions | No error, no log; returns immediately | Pass |
| UT-EXE-009.001.M03.T06 | MD-EXE-009.001.M03 | Positive | Subscriptions are scoped by event type | Subscribe handler A for `SymbolEnteredPosition`, B for `SymbolExitedPosition`; publish only `SymbolEnteredPosition` | A called once; B not called | Pass |

---

## Module: `core/monitoring_session/_repository.py` — DB Access Layer

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-009.002.M01.T01 | MD-EXE-009.002.M01 | Positive | `insert_monitoring_rows` inserts new symbols in MONITORING state | Empty table; insert symbols=`["A","B"]` for `today` | 2 rows present with `lifecycle_state='MONITORING'`; returned tuple == `("A","B")` | Pass |
| UT-EXE-009.002.M01.T02 | MD-EXE-009.002.M01 | Positive | `insert_monitoring_rows` is idempotent on same-day re-run | Run T01 twice with identical input | Second call returns `()`; row count unchanged | Pass |
| UT-EXE-009.002.M01.T03 | MD-EXE-009.002.M01 | Negative | `insert_monitoring_rows` with empty symbols inserts nothing | symbols=`[]` | Returns `()`; row count unchanged | Pass |
| UT-EXE-009.002.M01.T04 | MD-EXE-009.002.M01 | Positive | `fetch_earliest_open_monitoring_row` returns row with `MIN(session_date)` | MONITORING rows for X exist on `2026-05-14` and `2026-05-15` | Returned row has `session_date == "2026-05-14"` | Pass |
| UT-EXE-009.002.M01.T05 | MD-EXE-009.002.M01 | Negative | `fetch_earliest_open_monitoring_row` returns None when no MONITORING row | Only ENTERED rows for X | Returns `None` | Pass |
| UT-EXE-009.002.M01.T06 | MD-EXE-009.002.M01 | Positive | `transition_to_entered` flips MONITORING → ENTERED with timestamps | Existing MONITORING row for (`today`, "A"); call with `entered_at`, `trade_id` | Row's `lifecycle_state='ENTERED'`, `entered_at` and `trade_id` populated | Pass |
| UT-EXE-009.002.M01.T07 | MD-EXE-009.002.M01 | Positive | `transition_to_exited` flips ENTERED → EXITED | ENTERED row for ("2026-05-14", "A"); call with `exited_at` | `lifecycle_state='EXITED'`, `exited_at` set | Pass |
| UT-EXE-009.002.M01.T08 | MD-EXE-009.002.M01 | Positive | `bulk_skip_stale_monitoring` flips only stale MONITORING rows | Rows: ("2026-05-14","A")=MONITORING, ("2026-05-15","B")=MONITORING, today=2026-05-15 | Row A → SKIPPED; row B untouched; returned count == 1 | Pass |
| UT-EXE-009.002.M01.T09 | MD-EXE-009.002.M01 | Positive | `evict_symbol_atomic` deletes from all 3 price tables + flips ledger | Seed 5 rows in each of price_1m/3m/15m for "B"; SKIPPED ledger row for ("2026-05-14","B") | All price_* rows for "B" deleted; ledger row → EVICTED with `evicted_at`; returned dates == ("2026-05-14",) | Pass |
| UT-EXE-009.002.M01.T10 | MD-EXE-009.002.M01 | Negative | `evict_symbol_atomic` rolls back fully on mid-transaction failure | Patch `price_15m` DELETE to raise `OperationalError` | price_1m and price_3m rows for "B" still present; ledger row still SKIPPED | Pass |
| UT-EXE-009.002.M01.T11 | MD-EXE-009.002.M01 | Positive | `open_system_position_symbols` returns only system, non-CLOSED positions | Positions: A (system, OPEN), B (system, CLOSED), C (manual, OPEN) | Returned frozenset == `frozenset({"A"})` | Pass |
| UT-EXE-009.002.M01.T12 | MD-EXE-009.002.M01 | Negative | `open_system_position_symbols` excludes legacy NULL-origin rows | Positions: D (origin=NULL, OPEN) | "D" not in returned set | Pass |
| UT-EXE-009.002.M01.T13 | MD-EXE-009.002.M01 | Edge | `entered_symbols` equals `open_system_position_symbols` after fill round-trip | Apply T06 + corresponding `upsert_position_with_anchor` | Both queries return the same frozenset | Pass |
| UT-EXE-009.002.M01.T14 | MD-EXE-009.002.M01 | Positive | `fetch_history(symbol, days)` returns ledger rows including EVICTED | Symbol "B" with one EVICTED row from 7 days ago | Returned tuple contains the EVICTED row with `evicted_at` populated | Pass |

---

## Module: `core/monitoring_session/_service.py` — Lifecycle State Machine

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-009.002.M02.T01 | MD-EXE-009.002.M02 | Positive | `on_screener_results` inserts MONITORING rows for passed symbols and publishes `SymbolStartedMonitoring` per insert | `ScreenerRunResult` with `{A: passed=True, B: passed=True, C: passed=False}` | 2 ledger rows in MONITORING; 2 `SymbolStartedMonitoring` events for A and B; returned `KeepSet.filtered == {"A","B"}` | Pass |
| UT-EXE-009.002.M02.T02 | MD-EXE-009.002.M02 | Positive | `on_screener_results` is idempotent on same-day re-run | Call twice with identical result | Second call produces 0 new rows and 0 events | Pass |
| UT-EXE-009.002.M02.T03 | MD-EXE-009.002.M02 | Negative | `on_screener_results` ignores `passed=False` symbols | All symbols `passed=False` | 0 ledger rows inserted; 0 events; returned `KeepSet.filtered == frozenset()` | Pass |
| UT-EXE-009.002.M02.T04 | MD-EXE-009.002.M02 | Positive | First system BUY fill flips earliest MONITORING row → ENTERED + anchor + event | MONITORING row exists for ("2026-05-14","A"); `FillEvent(system, BUY, qty=100)` | Ledger row → ENTERED; `positions(A).anchor_session_date == "2026-05-14"`; one `SymbolEnteredPosition` event | Pass |
| UT-EXE-009.002.M02.T05 | MD-EXE-009.002.M02 | Positive | Scale-in BUY leaves ledger state unchanged, publishes `SymbolPositionScaled` | Position open at qty=100; `FillEvent(system, BUY, qty=50)` | Ledger row still ENTERED; trade row inserted with same `monitoring_session_date`; one `SymbolPositionScaled` event | Pass |
| UT-EXE-009.002.M02.T06 | MD-EXE-009.002.M02 | Positive | Partial SELL leaves ledger state unchanged, publishes `SymbolPositionScaled` | Position open at qty=150; SELL fill qty=70 → positions.state=PARTIAL_EXIT | Ledger row still ENTERED; one `SymbolPositionScaled` event | Pass |
| UT-EXE-009.002.M02.T07 | MD-EXE-009.002.M02 | Positive | Closing SELL flips ledger → EXITED, publishes `SymbolExitedPosition` | Position at qty=80; SELL fill qty=80 → positions.state=CLOSED | Ledger row → EXITED with `exited_at`; one `SymbolExitedPosition` event | Pass |
| UT-EXE-009.002.M02.T08 | MD-EXE-009.002.M02 | Negative | Manual-origin fill is a ledger no-op | `FillEvent(manual, BUY)` for a symbol with an open MONITORING row | Ledger row unchanged; no event published; `trades` row inserted with `trade_origin='manual'` | Pass |
| UT-EXE-009.002.M02.T09 | MD-EXE-009.002.M02 | Edge | System BUY with no MONITORING row logs ERROR and defensively records trade | Empty ledger; `FillEvent(system, BUY)` | ERROR log with `[Lifecycle]`; trade inserted with `monitoring_session_date=NULL`; no event | Pass |
| UT-EXE-009.002.M02.T10 | MD-EXE-009.002.M02 | Edge | Duplicate-filter case — re-emitted symbol stays MONITORING while prior anchor stays ENTERED | A is ENTERED via ("2026-05-14","A"); `on_screener_results` re-emits A on 2026-05-15 | New row ("2026-05-15","A") in MONITORING; old row still ENTERED; `SymbolStartedMonitoring` event for new row | Pass |
| UT-EXE-009.002.M02.T11 | MD-EXE-009.002.M02 | Positive | `keep_set(today)` returns filtered ∪ carryover | Screener for today emitted [A,B]; open system position on C | `keep_set.filtered == {"A","B"}`; `keep_set.carryover == {"C"}` | Pass |
| UT-EXE-009.002.M02.T12 | MD-EXE-009.002.M02 | Negative | `keep_set(today)` returns empty filtered when no screener run for today | No screener result file for today | `keep_set.filtered == frozenset()`; carryover still populated | Pass |
| UT-EXE-009.002.M02.T13 | MD-EXE-009.002.M02 | Positive | `check_invariant()` returns ok=True when ledger and positions agree | A in ENTERED ledger + open system position | `InvariantReport.ok is True`; both diff tuples empty | Pass |
| UT-EXE-009.002.M02.T14 | MD-EXE-009.002.M02 | Negative | `check_invariant()` flags symbol in ledger ENTERED but not in positions | Force-insert ENTERED ledger row for "X" without a position | `ok is False`; `only_in_a == ("X",)`; ERROR log emitted | Pass |
| UT-EXE-009.002.M02.T15 | MD-EXE-009.002.M02 | Positive | `reconcile_preopen` happy path evicts SKIPPED-not-in-keep-set and retains the rest | T-1 rows: A=MONITORING (entered), B=MONITORING (no entry), C=MONITORING (no entry); today=T, filtered={A,D}, A has open position | B and C → EVICTED with price_* rows deleted; A and D retained; one `SymbolEvicted` event per evicted symbol; `ReconcileCompleted` event with report | Pass |
| UT-EXE-009.002.M02.T16 | MD-EXE-009.002.M02 | Positive | `reconcile_preopen` is idempotent for the same `today` | Run T15 twice | Second `ReconcileReport.evicted_n == 0`; no further `SymbolEvicted` events | Pass |
| UT-EXE-009.002.M02.T17 | MD-EXE-009.002.M02 | Negative | Invariant violation aborts that symbol's eviction with reason `invariant_violation` | Force ledger ENTERED for "X" with no matching position; X is in stale eviction candidate set | `ReconcileReport.errors` contains `ReconcileError("X","invariant_violation",1)`; X's price_* rows untouched | Pass |
| UT-EXE-009.002.M02.T18 | MD-EXE-009.002.M02 | Negative | Concurrent `reconcile_preopen` returns sentinel report | Two threads call simultaneously | One returns normal report; the other returns `ReconcileReport(evicted_n=0, errors=(ReconcileError("__skipped__","already_running",1),))` | Pass |
| UT-EXE-009.002.M02.T19 | MD-EXE-009.002.M02 | Edge | Per-symbol failure isolates other symbols | Two SKIPPED-not-in-keep-set symbols; patch `evict_symbol_atomic` to fail permanently on first only | Failed symbol in `errors`; second symbol successfully evicted; one `SymbolEvicted` event | Pass |
| UT-EXE-009.002.M02.T20 | MD-EXE-009.002.M02 | Edge | Retry-once on transient `OperationalError` succeeds on second attempt | Patch `evict_symbol_atomic` to raise `OperationalError` first call, succeed second call | Symbol evicted; no entry in `errors`; ~200 ms back-off observed | Pass |
| UT-EXE-009.002.M02.T21 | MD-EXE-009.002.M02 | Positive | `ReconcileReport` carries expected counts and INFO log emitted | Run T15 | `filtered_n==2, carryover_n==1, skipped_n>=2, evicted_n==2`; `duration_ms > 0`; exactly one INFO log with `[Lifecycle]` topic | Pass |

---

## Module: `core/monitoring_session/__init__.py` — Public Surface

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-009.002.M03.T01 | MD-EXE-009.002.M03 | Positive | Qt-free guarantee — no module under `core/monitoring_session/` imports PyQt6 | Static scan of every `*.py` in the package | No file contains the string `PyQt6` or `pyqtSignal` | Pass |
| UT-EXE-009.002.M03.T02 | MD-EXE-009.002.M03 | Positive | Underscore-prefixed modules are not imported outside the package | Static scan of every `*.py` under `src/us_swing/` except `core/monitoring_session/` | No match for `from us_swing.core.monitoring_session._` | Pass |
| UT-EXE-009.002.M03.T03 | MD-EXE-009.002.M03 | Positive | `build_default_service(engine)` returns three references implementing the three Protocols | Call factory with an in-memory SQLite engine | `isinstance(query, MonitoringQuery)`, `isinstance(cmd, MonitoringCommand)`, `isinstance(bus, MonitoringEventBus)` all True; `query is cmd` (single concrete) | Pass |
| UT-EXE-009.002.M03.T04 | MD-EXE-009.002.M03 | Negative | Public `__all__` does not expose any underscore-prefixed name | Inspect `core.monitoring_session.__all__` | No element starts with `_`; concrete `MonitoringSessionService` not in `__all__` | Pass |

---

## Module: `core/monitoring_session/_scheduler.py` — Pre-Open Trigger

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-010.001.M01.T01 | MD-EXE-010.001.M01 | Positive | `start()` registers a `15 9 * * MON-FRI` cron job on the injected callable | Spy `cron_register`; call `start()` | Spy received cron expression `"15 9 * * MON-FRI"` and a callable | Pass |
| UT-EXE-010.001.M01.T02 | MD-EXE-010.001.M01 | Positive | `maybe_run_on_startup()` invokes `reconcile_preopen(today)` when conditions hold | Frozen clock to weekday at 10:30 ET; no prior `ReconcileCompleted` | `command.reconcile_preopen` called once with today's date | Pass |
| UT-EXE-010.001.M01.T03 | MD-EXE-010.001.M01 | Negative | `maybe_run_on_startup()` returns None on weekends | Frozen clock to Saturday 10:30 ET | Returns `None`; `command.reconcile_preopen` NOT called | Pass |
| UT-EXE-010.001.M01.T04 | MD-EXE-010.001.M01 | Negative | `maybe_run_on_startup()` returns None outside the [09:15, 16:00] ET window | Frozen clock to weekday 08:30 ET | Returns `None`; reconcile NOT called | Pass |
| UT-EXE-010.001.M01.T05 | MD-EXE-010.001.M01 | Negative | `maybe_run_on_startup()` skips when `ReconcileCompleted` already observed for today | Bus has already published `ReconcileCompleted` for today | Returns `None`; reconcile NOT called | Pass |

---

## Cross-Tool Patch Tests

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-004.001.M01.T20 | MD-INF-004.001.M01 | Positive | `migrate_lifecycle_columns` adds the 4 new columns when absent | Fresh DB missing all 4 columns | `PRAGMA table_info(trades)` shows `trade_origin`, `monitoring_session_date`; `PRAGMA table_info(positions)` shows `origin`, `anchor_session_date` | Pass |
| UT-INF-004.001.M01.T21 | MD-INF-004.001.M01 | Positive | `migrate_lifecycle_columns` is idempotent | Run T20 twice | Second call produces no `ALTER TABLE` execution; column count unchanged | Pass |
| UT-INF-004.001.M02.T05 | MD-INF-004.001.M02 | Positive | `create_schema(checkfirst=True)` provisions `monitoring_session` table + indexes | Fresh engine; call `create_schema` | Table exists; both indexes (`idx_monitoring_session_state`, `idx_monitoring_session_symbol`) present | Pass |
| UT-EXE-001.001.M02.T08 | MD-EXE-001.001.M02 | Positive | `handle_order_fill` routes system fills to `lifecycle_command.on_fill` | Inject mock `MonitoringCommand`; submit system entry fill | `on_fill` called exactly once with `origin=TradeOrigin.SYSTEM` and matching qty/price/trade_id | Skip |
| UT-EXE-001.001.M02.T09 | MD-EXE-001.001.M02 | Negative | `handle_order_fill` routes manual fills with `origin=TradeOrigin.MANUAL` | Submit fill where source signal had `strategy_id='manual'` | `on_fill` called with `origin=TradeOrigin.MANUAL` | Skip |

---

## Integration Tests — FO-EXE-009 / FO-EXE-010

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| IT-EXE-009.001 | integration | Positive | Full happy path: T-1 monitor+enter A; T-1 monitor B,C without entry; T+1 reconcile retains A, evicts B,C | Seed `ScreenerRunResult` T-1=[A,B,C]; simulate system entry on A; seed `ScreenerRunResult` T=[A,D]; run `reconcile_preopen(T)` | `price_1m/3m/15m` rows: B and C deleted, A and D retained; ledger: (T-1,A)=ENTERED, (T-1,B)=EVICTED, (T-1,C)=EVICTED, (T,D)=MONITORING; `SymbolEvicted` fired for B and C only | Pass |
| IT-EXE-009.002 | integration | Positive | Carryover position retention — A entered T-1, not filtered T | Seed: A ENTERED via T-1; screener T does not include A; A position open | After `reconcile_preopen(T)`: A's candles retained; ledger (T-1,A) still ENTERED; no `SymbolEvicted` for A | Pass |
| IT-EXE-009.003 | integration | Edge | Duplicate-filter case — A entered T-1, filtered again T | A ENTERED via T-1; screener T re-emits A; A position open | New ledger row (T,A)=MONITORING; old (T-1,A) still ENTERED; A's candles retained via keep_set; (T,A) → SKIPPED at next-day reconcile | Pass |
| IT-EXE-009.004 | integration | Positive | Scale-in across days carries the anchor forward | Day T-1: system BUY 100 A; Day T: system BUY 50 A | Both `trades` rows have `monitoring_session_date=T-1`; ledger row (T-1,A) stays ENTERED through both fills | Pass |
| IT-EXE-009.005 | integration | Positive | Lifecycle invariant holds across the full flow | Replay IT-001 + IT-002 + IT-003 + IT-004 in one test | After every state transition: `check_invariant().ok is True` | Pass |
| IT-EXE-010.001 | integration | Positive | Live feed handoff — evicted symbol never reaches `LiveBarWorker.set_symbols` | Spy `LiveBarWorker.set_symbols`; run IT-EXE-009.001 with a running worker | Spy receives `{A, D}` after reconcile; B and C never appear in any call | Pass |

---

## Module: `execution/strategy_engine/_engine.py` — StrategyEngine (FO-EXE-011)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-011.001.M01.T01 | MD-EXE-011.001.M01 | Unit | Engine starts asyncio loop on QThread.start | Construct `StrategyEngine(...)`; call `start()` | `isRunning() == True`; `_loop` is a running `AbstractEventLoop` | Pass |
| UT-EXE-011.001.M01.T02 | MD-EXE-011.001.M01 | Positive | Registry load instantiates contexts only for `mode != 'disabled'` | Stub registry with `[Auto, Manual, Disabled]` | `len(engine._registry) == 2`; both contexts have `strategy_signal.Status == 'Active'` | Pass |
| UT-EXE-011.001.M01.T03 | MD-EXE-011.001.M01 | Positive | `_on_candle_closed` triggers fan-out across accepting contexts | 3 contexts all accepting AAPL; emit `candle_closed("AAPL", bar)` | `_evaluate` invoked 3 times within 200 ms; concurrent via `asyncio.gather` | Pass |
| UT-EXE-011.001.M01.T04 | MD-EXE-011.001.M01 | Performance | Fan-out completes ≤ 200 ms for 50 strategies × 500 active symbols | Seed 50 contexts; emit `candle_closed` for one symbol | `_fanout` completion latency < 200 ms (measured on 4-core CI) | Pass |
| UT-EXE-011.001.M01.T05 | MD-EXE-011.001.M01 | Positive | `request_stop()` unwinds loop and joins thread within 3 s | Start engine; call `request_stop()` | `isRunning() == False` within 3 s; no leaked tasks | Pass |
| UT-EXE-011.001.M01.T06 | MD-EXE-011.001.M01 | Edge | No `PyQt6` import in any business-logic module (`_signals`, `_events`, `_context`, `_evaluator`, `_router`, `_protocols`); `_engine.py` is the explicit Qt boundary and is allowed | Import each business-logic module and scan its module-level globals | None of the six business-logic modules has any name bound from `PyQt6.*` | Pass |
| UT-EXE-011.001.M01.T07 | MD-EXE-011.001.M01 | Negative | `request_stop()` called before `start()` is a safe no-op | Construct engine; call `request_stop()` without prior `start()` | No exception raised; `isRunning() == False`; engine remains in a fresh constructable state | Pass |

---

## Module: `execution/strategy_engine/_context.py` — _StrategyContext & _CycleState (FO-EXE-011)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-011.001.M02.T01 | MD-EXE-011.001.M02 | Positive | `accepts()` returns True for every symbol in `all` mode | `cfg.symbol_mode="all"`; query any symbol | Returns True | Pass |
| UT-EXE-011.001.M02.T02 | MD-EXE-011.001.M02 | Positive | `include_only` accepts only listed symbols | `symbols_include=["AAPL"]`; query AAPL and MSFT | True for AAPL, False for MSFT | Pass |
| UT-EXE-011.001.M02.T03 | MD-EXE-011.001.M02 | Positive | `exclude_these` accepts every symbol except listed | `symbols_exclude=["TSLA"]`; query TSLA and NVDA | False for TSLA, True for NVDA | Pass |
| UT-EXE-011.001.M02.T04 | MD-EXE-011.001.M02 | Positive | Schedule guard returns False outside `start_time..end_time` | `start=09:30, end=15:30`; query at 08:00 ET | Returns False; context state stays `Inactive` | Pass |
| UT-EXE-011.001.M02.T05 | MD-EXE-011.001.M02 | Edge | Schedule guard returns True at exactly `start_time`, False at exactly `end_time` | Query at 09:30:00 and 15:30:00 ET | True at start, False at end (half-open interval) | Pass |
| UT-EXE-011.001.M02.T06 | MD-EXE-011.001.M02 | Positive | Schedule guard rejects weekend day | Day = Saturday | Returns False | Pass |
| UT-EXE-011.001.M02.T07 | MD-EXE-011.001.M02 | Positive | Default cycle state for unknown symbol is `Active` | Empty `ctx.cycles`; query AAPL | Returns `_CycleState.ACTIVE` | Pass |
| UT-EXE-011.001.M02.T08 | MD-EXE-011.001.M02 | Positive | Per-(symbol) lock is reused on second call | `ctx.lock_for("AAPL")` twice | Same `asyncio.Lock` instance returned | Pass |
| UT-EXE-011.001.M02.T09 | MD-EXE-011.001.M02 | Negative | Empty `load_strategies()` result yields zero contexts and no fan-out activity | Stub `load_strategies()` to return `[]`; start engine; emit `candle_closed("AAPL", bar)` | `len(engine._registry) == 0`; no `_evaluate` calls; no `StrategyEvent` published | Pass |

---

## Module: `execution/strategy_engine/_evaluator.py` — ConditionEvaluator (FO-EXE-011)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-011.001.M03.T01 | MD-EXE-011.001.M03 | Positive | Tokenizer produces correct token sequence for a comparison expression | `"RSI('Spot', 14, '3m') < 30"` | Tokens: IDENT, LPAREN, STRING, COMMA, NUMBER, COMMA, STRING, RPAREN, OP, NUMBER | Pass |
| UT-EXE-011.001.M03.T02 | MD-EXE-011.001.M03 | Positive | Parser builds correct AST for `A AND B OR C` (AND binds tighter) | `"Price('Spot','close','3m') > 100 AND RSI('Spot',14,'3m') < 30 OR Number(1) == Number(0)"` | Top-level OR with left=AND-node, right=comparison | Pass |
| UT-EXE-011.001.M03.T03 | MD-EXE-011.001.M03 | Negative | Tokenizer raises on unrecognised character | `"RSI(14) ~~ 30"` | `RuntimeError` mentioning unexpected token | Pass |
| UT-EXE-011.001.M03.T04 | MD-EXE-011.001.M03 | Positive | RSI indicator returns expected value for known DataFrame | Pre-computed `pandas_ta.rsi(close, length=14)` → 27.4 | `_fn_rsi([14, "3m"], candles, "AAPL")` returns ≈ 27.4 | Pass |
| UT-EXE-011.001.M03.T05 | MD-EXE-011.001.M03 | Positive | End-to-end `evaluate()` returns True when condition holds | `"RSI('Spot', 14, '3m') < 30"`; candles where RSI≈27.4 | Returns True | Pass |
| UT-EXE-011.001.M03.T06 | MD-EXE-011.001.M03 | Negative | `evaluate()` returns False when condition fails | Same expression; candles where RSI≈55 | Returns False | Pass |
| UT-EXE-011.001.M03.T07 | MD-EXE-011.001.M03 | Negative | Arity mismatch raises `EvaluatorError` | `"RSI(14)"` (RSI requires 3 args per catalogue) | `EvaluatorError` mentioning arity | Pass |
| UT-EXE-011.001.M03.T08 | MD-EXE-011.001.M03 | Positive | `FUNCTION_MAP` contains all 14 indicator names from the FO-GUI-013 catalogue | Inspect map keys | `set(FUNCTION_MAP.keys()) == FO_GUI_013_CATALOGUE` | Pass |
| UT-EXE-011.001.M03.T09 | MD-EXE-011.001.M03 | Edge | Parentheses correctly override AND/OR precedence | `"(A OR B) AND C"` | Top-level AND with left=OR-node | Pass |

---

## Module: `execution/strategy_engine/_router.py` — Mode Router (FO-EXE-011)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-011.001.M04.T01 | MD-EXE-011.001.M04 | Positive | `(auto, True)` signal → RiskManager.validate then ExecutionRouter.submit | Enqueue ENTRY signal; ctx mode=auto, auto_trade=True | `RiskManager.validate` called once; on pass, `ExecutionRouter.submit` called within 50 ms | Pass |
| UT-EXE-011.001.M04.T02 | MD-EXE-011.001.M04 | Positive | `(manual, *)` signal → PendingSignalStore.add | ctx mode=manual; enqueue ENTRY | `PendingSignalStore.add(signal)` called once; `ExecutionRouter.submit` NOT called | Pass |
| UT-EXE-011.001.M04.T03 | MD-EXE-011.001.M04 | Positive | `(auto, False)` signal → PendingSignalStore.add (forced) | ctx mode=auto, auto_trade=False | `PendingSignalStore.add` called; `submit` NOT called | Pass |
| UT-EXE-011.001.M04.T04 | MD-EXE-011.001.M04 | Negative | Duplicate ENTRY for `(strategy, symbol)` already UnderEntry is suppressed | Pre-set cycle to UnderEntry; emit ENTRY signal | No new signal enqueued; one DEBUG log emitted | Pass |
| UT-EXE-011.001.M04.T05 | MD-EXE-011.001.M04 | Positive | Capital-cap rejection drops signal and publishes `StrategySignalDropped` | RiskManager.can_allocate returns `(ok=False, reason="capital_cap")` | Signal not enqueued; one `StrategySignalDropped(reason="capital_cap")` event on bus | Pass |
| UT-EXE-011.001.M04.T06 | MD-EXE-011.001.M04 | Positive | End-time SquareOff fires within 30 s of crossing `end_time` for Intraday cycles | Mock wall-clock to 15:31; cycle `end_time=15:30, trade_type=Intraday, state=Running` | Within 30 s: forced EXIT signal with `reason='end_time'`; state→SquareOff | Pass |
| UT-EXE-011.001.M04.T07 | MD-EXE-011.001.M04 | Negative | Positional strategies do NOT receive end-time SquareOff | Same as T06 but `trade_type=Positional` | No EXIT signal; state remains Running | Pass |
| UT-EXE-011.001.M04.T08 | MD-EXE-011.001.M04 | Positive | `emergency_stop()` enqueues EXIT for every Running symbol and blocks until SquareOff | 3 strategies, 5 Running symbols total | 5 EXIT signals enqueued before method returns; method blocks until all 5 reach SquareOff | Pass |
| UT-EXE-011.001.M04.T09 | MD-EXE-011.001.M04 | Positive | Status writeback persists state transitions to registry | Cycle ACTIVE → UnderEntry → Running | `save_strategies` called; persisted `strategy_signal.Status == 'Running'`, `Order_Entry_Status='success'`, `Order_Entry_Timestamp` set | Pass |
| UT-EXE-011.001.M04.T10 | MD-EXE-011.001.M04 | Edge | order_reject(entry) rolls cycle UnderEntry → Active | Pre-set UnderEntry; emit `order_reject` | State → Active; `Order_Entry_Status='rejected'`; DEBUG log | Pass |

---

## Module: `execution/strategy_engine/_events.py` — StrategyEvent union (FO-EXE-011)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-011.001.M05.T01 | MD-EXE-011.001.M05 | Unit | Every `StrategyEvent` subclass is frozen and slots-based | Inspect each dataclass | `__frozen__ == True`; `__slots__` present | Pass |
| UT-EXE-011.001.M05.T02 | MD-EXE-011.001.M05 | Positive | Every event carries `schema_version: int = 1` | Construct each event with no version arg | `evt.schema_version == 1` | Pass |
| UT-EXE-011.001.M05.T03 | MD-EXE-011.001.M05 | Negative | Mutating a frozen event raises `FrozenInstanceError` | `evt.symbol = "X"` | Raises `dataclasses.FrozenInstanceError` | Pass |

---

## Module: `execution/trade_cycle/_schema.py` & `_dto.py` (FO-EXE-012)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-012.001.M01.T01 | MD-EXE-012.001.M01 | Unit | `trade_cycles` table created with all expected columns | Run `create_schema(engine, checkfirst=True)` on in-memory SQLite | `inspect(engine).has_table("trade_cycles") == True`; columns present include all 6 groups | Pass |
| UT-EXE-012.001.M01.T02 | MD-EXE-012.001.M01 | Unit | Composite indexes exist | Inspect engine | `idx_trade_cycles_state_symbol` and `idx_trade_cycles_strategy_symbol_state` both present | Pass |
| UT-EXE-012.001.M02.T01 | MD-EXE-012.001.M02 | Unit | `CycleSnapshot` is frozen with `schema_version=1` default | Construct `CycleSnapshot()` | `snap.schema_version == 1`; mutation raises `FrozenInstanceError` | Pass |
| UT-EXE-012.001.M02.T02 | MD-EXE-012.001.M02 | Unit | Enum frozensets match SRD enumeration | Inspect constants | `CYCLE_STATES == {"OPENING","OPEN","CLOSING","CLOSED","ABORTED"}`; `EXIT_REASONS` has 7 entries | Pass |

---

## Module: `execution/trade_cycle/_repository.py` — TradeCycleRepository (FO-EXE-012)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-012.002.M01.T01 | MD-EXE-012.002.M01 | Positive | `insert_open` inserts one row and returns matching `CycleSnapshot` | Valid row dict for `(boss_ema, AAPL, qty=25)` | One new row in `trade_cycles`; returned snap has `state="OPEN"`, fields populated | Pass |
| UT-EXE-012.002.M01.T02 | MD-EXE-012.002.M01 | Negative | Duplicate-open guard raises `DuplicateOpenCycleError` | Existing OPEN row for `(boss_ema, AAPL)`; call `insert_open` for same pair | Raises `DuplicateOpenCycleError`; no second row inserted | Pass |
| UT-EXE-012.002.M01.T03 | MD-EXE-012.002.M01 | Positive | `update_live` updates only live-state columns | Existing OPEN row; call `update_live(id, fields={"current_price": 185, ...})` | `current_price`, `current_pnl_usd`, `effective_stop` updated; entry/risk columns untouched | Pass |
| UT-EXE-012.002.M01.T04 | MD-EXE-012.002.M01 | Positive | `update_state` compare-and-swap succeeds when current state matches | Row in OPEN; call `update_state(id, "CLOSING")` | Row state="CLOSING"; method returns updated snapshot | Pass |
| UT-EXE-012.002.M01.T05 | MD-EXE-012.002.M01 | Negative | `update_state` rejects illegal transition CLOSED → OPENING | Row in CLOSED state | Raises `InvalidStateTransitionError`; no row mutation | Pass |
| UT-EXE-012.002.M01.T06 | MD-EXE-012.002.M01 | Positive | `close()` sets exit fields and freezes realized PnL | Row OPEN (`entry_price=182.5, qty=25`); call with `exit_price=187.8` | `realized_pnl_usd == 132.5` (±0.01); state="CLOSED" | Pass |
| UT-EXE-012.002.M01.T07 | MD-EXE-012.002.M01 | Positive | `abort()` transitions OPENING → ABORTED | Row OPENING; call `abort(id, "broker_reject")` | state="ABORTED"; `exit_reason="broker_reject"`; `closed_at` set | Pass |
| UT-EXE-012.002.M01.T08 | MD-EXE-012.002.M01 | Positive | `open_cycles()` returns only rows in OPENING/OPEN/CLOSING | Mix of states in DB | Returned tuple includes only non-terminal cycles | Pass |
| UT-EXE-012.002.M01.T09 | MD-EXE-012.002.M01 | Positive | `find_by_entry_order` returns matching row | Insert row with `entry_order_id="ord123"`; query | Returns matching `CycleSnapshot` | Pass |
| UT-EXE-012.002.M01.T10 | MD-EXE-012.002.M01 | Edge | `history(days=7)` excludes rows older than 7 days | Insert rows with `closed_at` 5 and 10 days ago | Only the 5-day row returned | Pass |

---

## Module: `execution/trade_cycle/_service.py` — TradeCycleService (FO-EXE-012)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-012.002.M02.T01 | MD-EXE-012.002.M02 | Positive | `on_entry_fill` opens cycle and publishes `CycleOpened` | `FillEvent(entry_order_id="ord1", symbol="AAPL", qty=25, price=182.5)` | New row in DB; exactly one `CycleOpened` event on bus | Pass |
| UT-EXE-012.002.M02.T02 | MD-EXE-012.002.M02 | Positive | `on_entry_fill` is idempotent on `entry_order_id` | Call twice with same fill event | One row in DB; second call returns existing snapshot; only one `CycleOpened` event | Pass |
| UT-EXE-012.002.M02.T03 | MD-EXE-012.002.M02 | Positive | Tick updates trailing stop only upward | Sequence `[185, 188, 187.40]` for cycle with `entry=182.5, offset=$2.5` | After 188: `trailing_stop_level=185.5`; after 187.40: unchanged at 185.5 | Pass |
| UT-EXE-012.002.M02.T04 | MD-EXE-012.002.M02 | Positive | `effective_stop = max(hard_sl, trailing)` | `hard_sl=179, trailing_level=185.5` | `effective_stop == 185.5` | Pass |
| UT-EXE-012.002.M02.T05 | MD-EXE-012.002.M02 | Positive | Tick at `price ≤ effective_stop` publishes `ExitTrigger(trailing_sl)` | Tick at 185.40 when `effective_stop=185.5` and trailing was the floor | Exactly one `ExitTrigger(reason="trailing_sl")` event; cycle state="CLOSING" | Pass |
| UT-EXE-012.002.M02.T06 | MD-EXE-012.002.M02 | Positive | Tick at `price ≥ target_price` publishes `ExitTrigger(target)` | Tick at 192 when target=190 | One `ExitTrigger(reason="target")` event; cycle state="CLOSING" | Pass |
| UT-EXE-012.002.M02.T07 | MD-EXE-012.002.M02 | Edge | Tick satisfying both target and stop emits target (precedence) | Cycle with `target=185`, `effective_stop=185`; tick at 185 | One `ExitTrigger(reason="target")` event | Pass |
| UT-EXE-012.002.M02.T08 | MD-EXE-012.002.M02 | Negative | Second tick after CLOSING does not emit a second `ExitTrigger` | Tick triggers exit (state→CLOSING); second tick at same price | Zero additional `ExitTrigger` events | Pass |
| UT-EXE-012.002.M02.T09 | MD-EXE-012.002.M02 | Performance | Tick throttle limits persist rate to ≤ 1 per 500 ms per cycle | Emit 100 ticks within 1 s for one cycle | `update_live` called ≤ 3 times; last tick's price reflected in DB | Pass |
| UT-EXE-012.002.M02.T10 | MD-EXE-012.002.M02 | Positive | `update_risk(hard_sl=valid)` succeeds and publishes `RiskUpdated` | Open cycle with `current_price=185.4`; call `update_risk(id, hard_sl=184.5)` | `hard_stop_loss=184.5`; one `RiskUpdated` event | Pass |
| UT-EXE-012.002.M02.T11 | MD-EXE-012.002.M02 | Negative | `update_risk(hard_sl > current_price)` raises `InvariantViolation` | Open cycle `current_price=185.4`; call with `hard_sl=200` | Raises `InvariantViolation`; row unchanged | Pass |
| UT-EXE-012.002.M02.T12 | MD-EXE-012.002.M02 | Negative | `update_risk(target < current_price)` raises `InvariantViolation` | Open cycle `current_price=185.4`; call with `target=180` | Raises `InvariantViolation`; row unchanged | Pass |
| UT-EXE-012.002.M02.T13 | MD-EXE-012.002.M02 | Positive | `on_exit_fill` freezes realized PnL and removes accumulator | Open cycle; emit `FillEvent(exit_order_id="ord2", exit_price=187.8)` | `realized_pnl_usd=132.5`; state="CLOSED"; accumulator removed; one `CycleClosed` event | Pass |
| UT-EXE-012.002.M02.T14 | MD-EXE-012.002.M02 | Positive | `reload()` re-attaches OPEN cycles after restart | Insert 2 OPEN rows directly into DB; construct new service; call `reload()` | Both accumulators created; tick subscription requested for both symbols | Pass |
| UT-EXE-012.002.M02.T15 | MD-EXE-012.002.M02 | Edge | No `PyQt6` import anywhere under `trade_cycle/` | Scan loaded module set after import | No `PyQt6` modules attributable to `trade_cycle/` | Pass |
| IT-EXE-010.002 | integration | Positive | History survives eviction | After IT-EXE-009.001 completes | `query.history("B", days=7)` returns at least one row with `lifecycle_state='EVICTED'`; `SELECT * FROM price_1m WHERE symbol='B'` is empty | Pass |