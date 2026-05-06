# Software Requirement Document — Execution & Risk Management (EXE)

**Document ID:** SRD-EXE
**Version:** 1.2.0
**Traces To:** FO-EXE v1.2.0
**Status:** Draft
**Last Updated:** 2026-05-06
**Project:** US Swing Trading System

---

## Compact Format Key

| Column | Meaning |
|---|---|
| P | Priority: **Must** / Should / Could |
| Status | Draft / Approved / Implemented / Verified / Reopen |

---

## Section 1: Requirements for FO-EXE-001 — Risk-Controlled Order Submission

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-EXE-001.001 | FO-EXE-001 | Must | `RiskManager.validate_signal(signal, account_state)` checks: (1) max position size, (2) max capital allocation, (3) circuit breaker state. Returns `ValidationResult(ok: bool, reason: str)`. | `TradeSignal`, `AccountState` | `ValidationResult` | Must be synchronous; must not call IBKR API | Draft |
| SRD-EXE-001.002 | FO-EXE-001 | Must | `RiskManager.calculate_position_size(signal, account_state)` computes share count = `floor((account_equity × risk_per_trade_pct / 100) / abs(entry_price − stop_loss))`. Cap result at `max_position_value / entry_price`. | `TradeSignal`, `AccountState` | `int` shares | Fractional shares are not permitted; always `floor()` | Draft |
| SRD-EXE-001.003 | FO-EXE-001 | Must | `ExecutionEngine.submit_order(signal, quantity, order_type)` builds an IBKR `Order` object (MKT or LMT), submits via `IBKRClient.place_order()`, and receives an IBKR order ID. | `TradeSignal`, quantity int, order_type | IBKR order ID; order persisted to `trades` table | Submission must complete within 2 s; timeout raises `OrderSubmissionError` | Draft |
| SRD-EXE-001.004 | FO-EXE-001 | Must | Immediately on `submit_order()` success, write a `TradeRecord(trade_id=ibkr_order_id, user_id, symbol, entry_time, entry_price=signal.entry_price, quantity, mode, status='SUBMITTED')` to the `trades` table. | IBKR order ID, `TradeSignal`, `user_id`, `mode` | row in `trades` table | Must insert before returning the order ID to the caller | Draft |
| SRD-EXE-001.005 | FO-EXE-001 | Must | Rejected signals (failed validation) must be logged at WARNING: `Signal REJECTED for {symbol}: {reason}`. No order submitted. | `ValidationResult(ok=False)` | WARNING log | Rejection must not raise an exception; caller receives `None` order ID | Draft |
| SRD-EXE-001.006 | FO-EXE-001 | Should | When `order_type = 'LMT'`, limit price = `signal.entry_price`. Accept a configurable `slippage_ticks` offset (default 0) added to limit price for BUY orders to improve fill probability. | config `slippage_ticks`, tick size | adjusted limit price | Tick size obtained from IBKR contract details at subscription time | Draft |

---

## Section 2: Requirements for FO-EXE-002 — Position Tracking & Exit Execution

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-EXE-002.001 | FO-EXE-002 | Must | `PositionTracker` maintains an in-memory `dict[tuple[int,str], OpenPosition]` keyed by `(user_id, symbol)`, and mirrors state to the `positions` table in the database. On every state change, DB update is performed asynchronously. | position events | in-memory + DB state synchronised | Must be thread-safe; concurrent reads from `StrategyEngine` must not corrupt state | Draft |
| SRD-EXE-002.002 | FO-EXE-002 | Must | `ExecutionEngine.handle_order_fill(fill_event)` receives IBKR fill callback; if fill is for an **entry** order: creates `OpenPosition` and registers it in `PositionTracker`. If fill is for an **exit** order: removes `OpenPosition`, updates `trades` table with `exit_time`, `exit_price`, `pnl`. | IBKR `Fill` event | updated `PositionTracker`; updated `trades` row | `pnl = (exit_price − entry_price) × quantity` for long; must handle partial fills by updating quantity | Draft |
| SRD-EXE-002.003 | FO-EXE-002 | Must | On receiving a SELL signal from `StrategyEngine`, `ExecutionEngine.exit_position(symbol)` looks up the full open quantity from `PositionTracker` and submits a market SELL order for the exact quantity. | SELL `TradeSignal`, `PositionTracker` | IBKR SELL order submitted | Exit order must be submitted within 1 s of receiving the signal | Draft |
| SRD-EXE-002.004 | FO-EXE-002 | Must | On application startup, `PositionTracker.reconcile(ibkr_positions)` compares IBKR-reported open positions against the local `positions` table. Any discrepancy (position in IBKR not in DB) is adopted into `PositionTracker` and logged at WARNING. | IBKR account positions list | reconciled `PositionTracker` state | Must run before `StrategyEngine` begins evaluating signals | Draft |
| SRD-EXE-002.005 | FO-EXE-002 | Must | On position close, emit a `PositionClosedEvent(symbol, pnl, strategy_id, duration)` to all subscribers (Logger, DailyPnLTracker). | filled exit order | `PositionClosedEvent` dispatched | Event dispatch must be non-blocking | Draft |

---

## Section 3: Requirements for FO-EXE-003 — Daily Loss Circuit Breaker & Emergency Controls

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-EXE-003.001 | FO-EXE-003 | Must | `DailyPnLTracker` accumulates realised PnL from all `PositionClosedEvent` emissions. Exposes `daily_pnl: float` property. Resets to 0 at market open each day. | `PositionClosedEvent` | running `daily_pnl` float | Must be thread-safe; UI or CLI may read at any time | Draft |
| SRD-EXE-003.002 | FO-EXE-003 | Must | `CircuitBreaker.check(daily_pnl, account_equity)` returns True (breach) when `daily_pnl ≤ −(account_equity × max_daily_loss_pct / 100)`. Called after every `PositionClosedEvent`. | `daily_pnl`, `account_equity`, `max_daily_loss_pct` | `bool` breach flag | Must use start-of-day equity snapshot (taken at startup), not live equity to avoid feedback loops | Draft |
| SRD-EXE-003.003 | FO-EXE-003 | Must | `EmergencyShutdown.run(reason)` executes: (1) cancel all pending IBKR orders, (2) submit market close orders for all open positions, (3) set `circuit_breaker_active = True` flag, (4) log CRITICAL with reason, (5) send alert, (6) stop `LiveEngine` event loop. | trigger reason string | complete halt; all positions closed | Must complete within 60 s; IBKR errors during shutdown are logged but not re-raised | Draft |
| SRD-EXE-003.004 | FO-EXE-003 | Must | While `circuit_breaker_active = True`, any entry signal arriving at `ExecutionEngine.submit_order()` is silently discarded and logged at DEBUG: `Signal discarded: circuit breaker active`. | `TradeSignal`, `circuit_breaker_active` flag | signal discarded + DEBUG log | Must also block new exit submissions that are not part of the emergency shutdown sequence | Draft |
| SRD-EXE-003.005 | FO-EXE-003 | Must | Manual kill-switch: `EmergencyShutdown.run(reason='manual')` must be callable via: (a) CLI `python -m us_swing kill`, (b) a SIGTERM signal handler, (c) GUI emergency button. All routes must call the same `EmergencyShutdown.run()` implementation. | CLI command, SIGTERM, or GUI button | `EmergencyShutdown.run('manual')` executed | SIGTERM handler must be registered on `main.py` startup | Draft |
| SRD-EXE-003.006 | FO-EXE-003 | Should | After `EmergencyShutdown.run()` completes, write a shutdown summary to `logs/shutdown_YYYYMMDD_HHMMSS.log`: date, trigger reason, positions closed, final daily PnL, any IBKR errors encountered during shutdown. | shutdown state | shutdown summary log file | File must be machine-readable JSON for automated post-mortem analysis | Draft |

---

## Section 4: Requirements for FO-EXE-004 — Paper Trading Mode

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-EXE-004.001 | FO-EXE-004 | Must | `PaperEngine` class implements the same interface as the live `ExecutionEngine` for order submission but simulates fills without calling IBKR API. Market orders fill immediately at current market price; limit orders fill when price crosses limit level. | `TradeSignal`, quantity, order_type | simulated fill event | Must produce identical `TradeRecord` and `OpenPosition` structures as live engine | Draft |
| SRD-EXE-004.002 | FO-EXE-004 | Must | `PaperEngine` writes all trades to the `trades` table with `mode = 'paper'`. Position updates go to `positions` table with `mode = 'paper'`. | simulated fill | DB rows with `mode='paper'` | Paper and live records are in the same tables; differentiated solely by `mode` column | Draft |
| SRD-EXE-004.003 | FO-EXE-004 | Must | `PaperEngine` calculates P&L identically to live: `pnl = (exit_price − entry_price) × quantity` for long positions. | simulated exit fill | `pnl` value | Rounding behaviour must match live P&L calculation exactly | Draft |
| SRD-EXE-004.004 | FO-EXE-004 | Must | `PaperEngine` uses live market data (from `DataProvider`) for fill price reference. No synthetic price generation for paper fills. | current market price from live feed | fill at market price | If no live feed available (e.g., after hours), paper fills are queued until next live price | Draft |
| SRD-EXE-004.005 | FO-EXE-004 | Should | `ExecutionRouter` selects `PaperEngine` or live `ExecutionEngine` based on the active user's `mode` setting. Routing is determined at signal submission time. | `user.mode`, `TradeSignal` | routed to correct engine | Mode check must be per-signal, not cached at startup; user can switch mid-session | Draft |

---

## Section 5: Requirements for FO-EXE-005 — Position State Machine & Capital Check

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-EXE-005.001 | FO-EXE-005 | Must | `OpenPosition.state` field tracks position lifecycle: `NEW` (order submitted), `PARTIAL_ENTRY` (partial fill on entry), `OPEN` (entry fully filled), `PARTIAL_EXIT` (partial fill on exit), `CLOSED` (fully exited). State stored in `positions.state` column. | fill events | updated `state` | State transitions must be strictly ordered; invalid transitions (e.g., CLOSED → OPEN) raise `InvalidStateTransitionError` | Draft |
| SRD-EXE-005.002 | FO-EXE-005 | Must | On partial entry fill: update `positions.quantity` to partial amount, set `state = 'PARTIAL_ENTRY'`. On subsequent fill that completes entry: update quantity to full amount, set `state = 'OPEN'`. | partial fill event | updated position | Partial fill amounts are cumulative; track `filled_quantity` vs `total_quantity` | Draft |
| SRD-EXE-005.003 | FO-EXE-005 | Must | On partial exit fill: update `positions.quantity` to remaining amount, set `state = 'PARTIAL_EXIT'`. On full exit: set `state = 'CLOSED'`, record final P&L. | exit fill event | updated position | Partial exit P&L = `(exit_price − avg_entry) × partial_quantity` | Draft |
| SRD-EXE-005.004 | FO-EXE-005 | Must | `RiskManager.can_enter_new(signal, account_state, user_id)` checks: `available_capital = total_equity - sum(open_position_values_for_user)`. Returns True only if the projected position fits within `max_allocation_pct`. | `TradeSignal`, `AccountState`, `user_id` | `bool` | Capital calculation is per-user; each user has independent allocation limits | Draft |
| SRD-EXE-005.005 | FO-EXE-005 | Must | User quantity override: `ExecutionEngine.submit_signal()` accepts an optional `quantity_override: int | None` parameter. If provided, this quantity is used instead of `RiskManager.calculate_position_size()`. Override must still pass capital availability check. | `quantity_override` int, `TradeSignal` | order with overridden quantity | Override quantity must be > 0; override does not bypass risk validation, only position sizing | Draft |
| SRD-EXE-005.006 | FO-EXE-005 | Must | Positions with state != CLOSED persist across application restarts. On startup, `PositionTracker.load_from_db(user_id)` restores all non-CLOSED positions. | DB `positions` rows | restored in-memory `PositionTracker` | Must run before `StrategyEngine` begins evaluating signals; reconcile with IBKR positions after loading from DB | Draft |

---

## Section 6: Requirements for FO-EXE-006 — Intraday Candle Readiness (Phase 1: Download)

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-EXE-006.001 | FO-EXE-006 | Must | `IntradayCandleLoader.load(symbols: list[str])` is the single entry point triggered when a screened stock list is available. It orchestrates delta-fetch of 1 m bars for every symbol and persists them via `DatabaseManager.insert_bars()`. Runs in a background thread; emits `load_progress(symbol, done, total)` and `load_complete(failed: list[str])` signals upon completion. | `list[str]` symbols, `IBKRClient`, `DatabaseManager` | 1 m bars in `price_1m`; progress + completion signals | Must not block the calling thread; per-symbol failures must not abort other symbols | Implemented |
| SRD-EXE-006.002 | FO-EXE-006 | Must | **Delta fetch logic:** `IntradayCandleLoader._fetch_symbol(symbol)` calls `DatabaseManager.get_last_timestamp(symbol, '1m')` to find the last stored bar. If result is None, fetch the full historical window. If a timestamp exists, fetch only bars after that timestamp. Uses `IBKRClient.req_historical_data()` via the pacing queue (SRD-INF-001.005). | symbol, last stored timestamp | new 1 m bars (0 rows if already current); no duplicate inserts | Duplicate prevention: `DatabaseManager.insert_bars()` uses INSERT OR IGNORE; method is idempotent | Implemented |
| SRD-EXE-006.003 | FO-EXE-006 | Must | **Minimum candle window:** The historical fetch window must be large enough to produce ≥ 390 aggregated candles for each required timeframe: 3 m (requires 1 170 minutes of 1 m bars ≈ 3 trading days), 5 m (1 950 min ≈ 5 days), 1 h (23 400 min ≈ 60 trading days). On first fetch (no prior data), the loader requests **65 trading days** of 1 m bars per symbol to satisfy all three timeframes with a 5-day safety margin. | symbol, target timeframes | sufficient 1 m bar rows to aggregate 390+ candles for 3 m / 5 m / 1 h | IBKR 1 m bar limit: maximum 30 calendar days per request; for 65 trading-days the loader splits into sequential paged requests and concatenates results | Implemented |
| SRD-EXE-006.004 | FO-EXE-006 | Must | **Post-fetch validation:** After inserting bars for a symbol, `IntradayCandleLoader._validate_candle_counts(symbol)` calls `HistoricalDataEngine.aggregate_timeframe(symbol, tf)` for tf ∈ {`'3m'`, `'5m'`, `'1h'`} and checks that each returns ≥ 390 bars. If any timeframe is short, the symbol is added to `load_complete.failed` list with reason `'insufficient_candles:{tf}:{count}'`. | symbol, `DatabaseManager`, `HistoricalDataEngine` | pass/fail per timeframe; short symbols in failed list | Validation is read-only; does not re-fetch; caller decides whether to retry | Implemented |
| SRD-EXE-006.005 | FO-EXE-006 | Must | **Per-symbol error isolation:** Any exception raised during `_fetch_symbol()` or `_validate_candle_counts()` (IBKR timeout, pacing error, DB write failure) is caught, the symbol is appended to an internal `_failed` list with the exception message, and processing continues with the next symbol. After all symbols, the failed list is included in the `load_complete` signal payload and logged at WARNING. | exception from IBKR or DB | symbol in failed list; WARNING log entry | Must not re-raise; failed symbols are eligible for manual retry via `load([failed_symbol])` | Implemented |
| SRD-EXE-006.006 | FO-EXE-006 | Should | `IntradayCandleLoader.get_readiness_report(symbols: list[str]) -> dict[str, dict]` returns a per-symbol dict with keys: `candles_3m`, `candles_5m`, `candles_1h` (int counts), `ready` (bool — True if all three ≥ 390), `last_1m_bar` (datetime or None). Used by the GUI to display candle readiness before market open. | `list[str]` symbols, `DatabaseManager`, `HistoricalDataEngine` | readiness dict | Must complete in < 2 s for ≤ 500 symbols; uses cached count queries, not full bar fetches | Implemented |
