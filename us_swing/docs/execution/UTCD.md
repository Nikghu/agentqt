# Unit Test Case Document — Execution & Risk Management (EXE)

**Document ID:** UTCD-EXE
**Version:** 1.2.0
**Traces To:** MD-EXE v1.2.0
**Status:** Draft
**Last Updated:** 2026-05-06
**Project:** US Swing Trading System

> Tests written BEFORE implementation per process.md §7.

---

## Module: `execution/risk_manager.py` — RiskManager

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-001.001.M01.T01 | MD-EXE-001.001.M01 | Unit | Position size calculation: standard case | equity=$100,000; risk_pct=1%; entry=$50; stop=$48 | `500` shares (100000 × 0.01 / 2 = 500) | Draft |
| UT-EXE-001.001.M01.T02 | MD-EXE-001.001.M01 | Unit | Position size capped by max_position_value | equity=$100,000; risk_pct=1%; entry=$50; stop=$49.90 (risk/share=$0.10); max_position=$10,000 | `200` shares (capped: 10000/50=200 < uncapped=10000) | Draft |
| UT-EXE-001.001.M01.T03 | MD-EXE-001.001.M01 | Unit | `validate_signal()` passes when deployment within limit | existing_deployed=$20,000; new_required=$5,000; equity=$100,000; max_pct=50% | `ValidationResult(ok=True)` | Draft |
| UT-EXE-001.001.M01.T04 | MD-EXE-001.001.M01 | Unit | `validate_signal()` rejects when deployment exceeds limit | existing_deployed=$48,000; new_required=$5,000; equity=$100,000; max_pct=50% | `ValidationResult(ok=False, reason contains "capital allocation")` | Draft |
| UT-EXE-001.001.M01.T05 | MD-EXE-001.001.M01 | Unit | `validate_signal()` rejects when circuit breaker active | `circuit_breaker_active=True` | `ValidationResult(ok=False, reason contains "circuit breaker")` | Draft |
| UT-EXE-001.001.M01.T06 | MD-EXE-001.001.M01 | Edge | `calculate_position_size()` floors fractional shares | risk/share=$3.00; risk_dollars=$1,000 → 333.33 | Returns `333` (floor) | Draft |

---

## Module: `execution/execution_engine.py` — ExecutionEngine

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-001.001.M02.T01 | MD-EXE-001.001.M02 | Unit | `submit_signal()` calls IBKR place_order when validation passes | Mock `RiskManager.validate_signal` → `ok=True`; Mock IBKR returns order_id=123 | `submit_signal()` returns 123; IBKR `place_order()` called once | Draft |
| UT-EXE-001.001.M02.T02 | MD-EXE-001.001.M02 | Unit | `submit_signal()` returns None when validation fails | Mock `RiskManager.validate_signal` → `ok=False` | Returns `None`; IBKR `place_order()` NOT called; WARNING logged | Draft |
| UT-EXE-001.001.M02.T03 | MD-EXE-001.001.M02 | Unit | `submit_signal()` persists trade to DB on success | Successful submission | `TradeRecord` with `trade_id=123` appears in `trades` table | Draft |
| UT-EXE-001.001.M02.T04 | MD-EXE-001.001.M02 | Edge | `submit_signal()` raises `OrderSubmissionError` on IBKR timeout | Mock IBKR place_order to hang > timeout=2s | `OrderSubmissionError` raised | Draft |
| UT-EXE-001.001.M02.T05 | MD-EXE-001.001.M02 | Unit | `handle_order_fill()` on entry fill creates OpenPosition with user_id | Entry fill event for AAPL 500 shares @ $50, user_id=1 | `PositionTracker.has_open(1, "AAPL")` is True; position.state == 'OPEN' | Draft |
| UT-EXE-001.001.M02.T06 | MD-EXE-001.001.M02 | Unit | `handle_order_fill()` on exit fill updates trade PnL in DB | Exit fill for AAPL @ $55; entry was $50; qty=500; user_id=1 | `trades.pnl == 2500.0`; position.state == 'CLOSED' | Draft |
| UT-EXE-001.001.M02.T07 | MD-EXE-001.001.M02 | Unit | `exit_position()` submits SELL for full open quantity | `PositionTracker` has AAPL qty=500 | IBKR SELL 500 AAPL market order submitted | Draft |

---

## Module: `execution/position_tracker.py` — PositionTracker

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-002.001.M01.T01 | MD-EXE-002.001.M01 | Unit | `has_open()` returns False initially | Fresh tracker, user_id=1 | `has_open(1, "AAPL")` is False | Draft |
| UT-EXE-002.001.M01.T02 | MD-EXE-002.001.M01 | Unit | `open()` + `has_open()` round-trip with user_id | Open AAPL position for user_id=1 | `has_open(1, "AAPL")` is True; `has_open(2, "AAPL")` is False | Draft |
| UT-EXE-002.001.M01.T03 | MD-EXE-002.001.M01 | Unit | `close()` removes position from tracker | Open then close AAPL for user_id=1 | `has_open(1, "AAPL")` is False after close | Draft |
| UT-EXE-002.001.M01.T04 | MD-EXE-002.001.M01 | Unit | `reconcile()` adopts unrecognised IBKR positions | IBKR returns MSFT position not in local DB | `has_open("MSFT")` is True; WARNING logged | Draft |
| UT-EXE-002.001.M01.T05 | MD-EXE-002.001.M01 | Unit | `update_stop()` changes stop_loss per user | Open position with stop=48.0; call `update_stop(1, "AAPL", 49.0)` | `position.stop_loss == 49.0` | Draft |

---

## Module: `execution/circuit_breaker.py` — DailyPnLTracker & CircuitBreaker

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-003.001.M01.T01 | MD-EXE-003.001.M01 | Unit | `DailyPnLTracker` accumulates PnL | `add(-500)`, `add(-300)` | `daily_pnl == -800` | Draft |
| UT-EXE-003.001.M01.T02 | MD-EXE-003.001.M01 | Unit | `reset()` zeroes PnL | `add(-500)` then `reset()` | `daily_pnl == 0` | Draft |
| UT-EXE-003.001.M01.T03 | MD-EXE-003.001.M01 | Unit | `CircuitBreaker.check()` returns True at threshold | equity=$100,000; max_daily_loss_pct=2%; daily_pnl=-2000 | `True` (breach) | Draft |
| UT-EXE-003.001.M01.T04 | MD-EXE-003.001.M01 | Unit | `CircuitBreaker.check()` returns False below threshold | daily_pnl=-1999 | `False` | Draft |
| UT-EXE-003.001.M01.T05 | MD-EXE-003.001.M01 | Edge | Exactly at threshold triggers breach | daily_pnl=-2000.00; threshold=-2000.00 | `True` (≤ is inclusive) | Draft |

---

## Module: `execution/emergency.py` — EmergencyShutdown

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-003.001.M02.T01 | MD-EXE-003.001.M02 | Unit | `run()` cancels all pending orders | Mock IBKR; 2 pending orders | `IBKRClient.cancel_all_orders()` called exactly once | Draft |
| UT-EXE-003.001.M02.T02 | MD-EXE-003.001.M02 | Unit | `run()` closes all open positions | 2 open positions (AAPL, MSFT) | `ExecutionEngine.exit_position()` called for each symbol | Draft |
| UT-EXE-003.001.M02.T03 | MD-EXE-003.001.M02 | Unit | `run()` logs CRITICAL event | Any trigger reason | CRITICAL log entry with the reason string | Draft |
| UT-EXE-003.001.M02.T04 | MD-EXE-003.001.M02 | Unit | After `run()`, new signals are discarded | Call `submit_signal()` after `circuit_breaker_active=True` | Signal discarded; DEBUG logged; no IBKR call | Draft |
| UT-EXE-003.001.M02.T05 | MD-EXE-003.001.M02 | Unit | Shutdown JSON written to logs/ | `run("daily_loss_limit")` | File `logs/shutdown_*.json` exists with required keys | Draft |
| UT-EXE-003.001.M02.T06 | MD-EXE-003.001.M02 | Edge | IBKR error during shutdown is logged but not re-raised | Mock `cancel_all_orders()` to raise `IBKRError` | ERROR logged; shutdown continues; no exception propagates | Draft |

---

## Module: `execution/paper_engine.py` — PaperEngine

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-004.001.M01.T01 | MD-EXE-004.001.M01 | Unit | Market order fills immediately at current market price | signal BUY AAPL, order_type='MKT', mock market_price=$150 | `PaperFill` with `fill_price == 150.0` | Draft |
| UT-EXE-004.001.M01.T02 | MD-EXE-004.001.M01 | Unit | Limit buy fills when market price ≤ limit | signal BUY AAPL limit=$150, mock market_price=$149 | `PaperFill` with `fill_price == 150.0` | Draft |
| UT-EXE-004.001.M01.T03 | MD-EXE-004.001.M01 | Unit | Limit buy does NOT fill when market price > limit | signal BUY AAPL limit=$150, mock market_price=$151 | Returns None or queues pending order | Draft |
| UT-EXE-004.001.M01.T04 | MD-EXE-004.001.M01 | Unit | Paper fills stored with `mode='paper'` in DB | Simulate fill for user_id=1. | `trades` row has `mode='paper'`; `positions` row has `mode='paper'` | Draft |
| UT-EXE-004.001.M01.T05 | MD-EXE-004.001.M01 | Unit | Paper P&L matches live calculation | Entry=$50, exit=$55, qty=500 | `pnl == 2500.0` (identical to live) | Draft |
| UT-EXE-004.001.M01.T06 | MD-EXE-004.001.M01 | Unit | Paper order IDs are negative (distinguishable from IBKR) | Simulate 3 fills | All order_ids < 0 and monotonically decreasing | Draft |
| UT-EXE-004.001.M01.T07 | MD-EXE-004.001.M01 | Edge | No IBKR API calls made during paper fill | Mock IBKR client with side_effect=AssertionError | No assertion error raised; fill succeeds | Draft |

---

## Module: `execution/execution_router.py` — ExecutionRouter

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-004.001.M02.T01 | MD-EXE-004.001.M02 | Unit | Routes to PaperEngine when user mode is 'paper' | user.mode='paper', valid signal | `PaperEngine.simulate_fill()` called; `ExecutionEngine.submit_signal()` NOT called | Draft |
| UT-EXE-004.001.M02.T02 | MD-EXE-004.001.M02 | Unit | Routes to live ExecutionEngine when user mode is 'live' | user.mode='live', valid signal | `ExecutionEngine.submit_signal()` called; `PaperEngine.simulate_fill()` NOT called | Draft |
| UT-EXE-004.001.M02.T03 | MD-EXE-004.001.M02 | Unit | Mode check per-signal, not cached | User starts in 'paper', switches to 'live' mid-session | First signal → PaperEngine; second signal → ExecutionEngine | Draft |

---

## Module: `execution/position_tracker.py` — Position State Machine

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-005.001.M01.T01 | MD-EXE-002.001.M01 | Unit | New position starts in state NEW | Open position via `open()` | `position.state == 'NEW'` | Draft |
| UT-EXE-005.001.M01.T02 | MD-EXE-002.001.M01 | Unit | Partial entry fill transitions NEW → PARTIAL_ENTRY | `update_state(user_id, sym, 'PARTIAL_ENTRY', filled_qty=200)` | `state == 'PARTIAL_ENTRY'`; `filled_quantity == 200` | Draft |
| UT-EXE-005.001.M01.T03 | MD-EXE-002.001.M01 | Unit | Full entry fill transitions NEW → OPEN | `update_state(user_id, sym, 'OPEN', filled_qty=500)` | `state == 'OPEN'`; `filled_quantity == 500` | Draft |
| UT-EXE-005.001.M01.T04 | MD-EXE-002.001.M01 | Unit | PARTIAL_ENTRY → OPEN on final fill | State currently PARTIAL_ENTRY(200/500); update to OPEN(500/500) | `state == 'OPEN'`; `filled_quantity == total_quantity` | Draft |
| UT-EXE-005.001.M01.T05 | MD-EXE-002.001.M01 | Unit | OPEN → PARTIAL_EXIT on partial exit | `update_state(user_id, sym, 'PARTIAL_EXIT', filled_qty=300)` | `state == 'PARTIAL_EXIT'` | Draft |
| UT-EXE-005.001.M01.T06 | MD-EXE-002.001.M01 | Unit | PARTIAL_EXIT → CLOSED on final exit | `update_state(user_id, sym, 'CLOSED', filled_qty=500)` | `state == 'CLOSED'` | Draft |
| UT-EXE-005.001.M01.T07 | MD-EXE-002.001.M01 | Edge | Invalid transition CLOSED → OPEN raises error | Attempt `update_state(user_id, sym, 'OPEN')` on CLOSED position | `InvalidStateTransitionError` raised | Draft |
| UT-EXE-005.001.M01.T08 | MD-EXE-002.001.M01 | Edge | Invalid transition NEW → PARTIAL_EXIT raises error | Attempt `update_state(user_id, sym, 'PARTIAL_EXIT')` on NEW position | `InvalidStateTransitionError` raised | Draft |
| UT-EXE-005.001.M01.T09 | MD-EXE-002.001.M01 | Unit | `load_from_db()` restores non-CLOSED positions | DB has 2 OPEN, 1 CLOSED for user_id=1 | Tracker has 2 positions; CLOSED position excluded | Draft |

---

## Module: `execution/risk_manager.py` — Capital Check & Quantity Override

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-005.004.M01.T01 | MD-EXE-001.001.M01 | Unit | `can_enter_new()` returns True when capital available | equity=$100k, open_value=$20k, signal cost=$10k, max_pct=50% | `True` | Draft |
| UT-EXE-005.004.M01.T02 | MD-EXE-001.001.M01 | Unit | `can_enter_new()` returns False when capital exhausted | equity=$100k, open_value=$45k, signal cost=$10k, max_pct=50% | `False` | Draft |
| UT-EXE-005.004.M01.T03 | MD-EXE-001.001.M01 | Unit | `can_enter_new()` scoped per user_id | user1 has $40k deployed; user2 has $0; max_pct=50% each | user1 → True for $5k; user2 → True for $45k | Draft |
| UT-EXE-005.005.M02.T01 | MD-EXE-001.001.M02 | Unit | `submit_signal()` with `quantity_override` uses override quantity | override=100; calculated would be 500 | Order submitted for 100 shares | Draft |
| UT-EXE-005.005.M02.T02 | MD-EXE-001.001.M02 | Unit | Override quantity still checked by capital availability | override=5000 (exceeds capital), equity=$50k, max_pct=50% | Order rejected; returns None | Draft |
| UT-EXE-005.005.M02.T03 | MD-EXE-001.001.M02 | Edge | Override quantity ≤ 0 raises ValueError | `quantity_override=0` | `ValueError` raised | Draft |

---

## Module: `execution/intraday_candle_loader.py` — IntradayCandleLoader

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-EXE-006.001.M01.T01 | MD-EXE-006.001.M01 | Positive | Full fetch for new symbol inserts 1 m bars into DB | Symbol with no prior `price_1m` rows; mock IBKR returns 1 000 1 m bars across 4 paged requests | `DatabaseManager.insert_bars()` called; `price_1m` has 1 000 rows for symbol | Pass |
| UT-EXE-006.001.M01.T02 | MD-EXE-006.001.M01 | Positive | Delta fetch inserts only bars after last stored timestamp | Symbol with last `price_1m` timestamp = T; mock IBKR returns 50 bars with datetime > T | 50 rows inserted; IBKR request duration covers only period after T | Pass |
| UT-EXE-006.001.M01.T03 | MD-EXE-006.001.M01 | Negative | Delta fetch is idempotent — re-run inserts 0 duplicate rows | Symbol already up-to-date; IBKR returns 0 new bars | `insert_bars()` called with empty list; row count unchanged; no error | Pass |
| UT-EXE-006.001.M01.T04 | MD-EXE-006.001.M01 | Positive | Validation passes when all three timeframes have ≥ 390 candles | Symbol with 2 000 1 m bars (≈ 5 trading days worth) in DB; `aggregate_timeframe()` returns counts: 3 m=666, 5 m=400, 1 h=32 ← 1 h < 390, so adjust: use 14 000 bars (≈ 60+ days) | `_validate_candle_counts()` returns `CandleLoadResult(ok=True)` when all counts ≥ 390 | Pass |
| UT-EXE-006.001.M01.T05 | MD-EXE-006.001.M01 | Negative | Validation fails when a timeframe has < 390 candles | Symbol with only 400 1 m bars; 3 m → 133, 5 m → 80, 1 h → 6 (all < 390) | `_validate_candle_counts()` returns `CandleLoadResult(ok=False, reason='insufficient_candles:3m:133')` | Pass |
| UT-EXE-006.001.M01.T06 | MD-EXE-006.001.M01 | Negative | IBKR error for one symbol does not abort remaining symbols | 3-symbol list; IBKR raises `IBKRHistoricalDataError` for symbol[1] | symbol[0] and symbol[2] processed successfully; symbol[1] in `load_complete.failed`; WARNING logged | Pass |
| UT-EXE-006.001.M01.T07 | MD-EXE-006.001.M01 | Positive | `load_complete` signal emitted with full result list | 3 symbols, 1 success + 1 validation fail + 1 IBKR error | `load_complete` fires once; payload is `list[CandleLoadResult]` with 3 items; failed count = 2 | Pass |
| UT-EXE-006.001.M01.T08 | MD-EXE-006.001.M01 | Positive | `load_progress` signal emitted once per symbol | 5-symbol list | `load_progress` fired 5 times; final call has `done == total == 5` | Pass |
| UT-EXE-006.001.M01.T09 | MD-EXE-006.001.M01 | Positive | `get_readiness_report()` returns ready=True when all counts ≥ 390 | DB has 14 000 1 m bars for AAPL spanning ≥ 60 trading days | `report['AAPL'].ready == True`; `report['AAPL'].candles_3m >= 390` | Pass |
| UT-EXE-006.001.M01.T10 | MD-EXE-006.001.M01 | Negative | `get_readiness_report()` returns ready=False when any timeframe < 390 | DB has 300 1 m bars for MSFT | `report['MSFT'].ready == False`; at least one candle count < 390 | Pass |
| UT-EXE-006.001.M01.T11 | MD-EXE-006.001.M01 | Edge | Full-fetch paging: 65 trading-day window requires multiple IBKR requests | New symbol; full fetch mode | `IBKRClient.req_historical_data()` called ≥ 3 times (pages); all results concatenated before insert | Pass |
| UT-EXE-006.001.M01.T12 | MD-EXE-006.001.M01 | Negative | `load()` with empty symbol list completes immediately with no DB writes | `symbols=[]` | `load_complete` emitted with empty results list; `insert_bars()` never called | Pass |
| UT-EXE-006.001.M01.T13 | MD-EXE-006.001.M01 | Negative | Minimum candle window check — IBKR returns fewer bars than 65-day target (truncated history for new listing) | New symbol; IBKR returns only 800 1 m bars (≈ 2 days) for full-fetch window | Symbol included in failed list with reason `'insufficient_candles'`; no exception propagates; remaining symbols continue | Pass |
