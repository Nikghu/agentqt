# Functional Objectives — Execution & Risk Management (EXE)

**Document ID:** FO-EXE
**Version:** 1.2.0
**Status:** Draft
**Last Updated:** 2026-05-06
**Project:** US Swing Trading System

> Traces to: `us_swing/requirements.md` §10, §11, §12, §13, §21.4, §22, §23, §25

---

## FO-EXE-001: Risk-Controlled Order Submission

- The system shall receive trade signals from the Analysis Engine and validate each one against risk rules before submitting any order to IBKR.
- For each validated signal the system shall calculate position size using a configurable fixed-risk model: `position_size = (account_risk_per_trade × account_equity) / (entry_price − stop_loss_price)`.
- The system shall enforce the following pre-trade risk controls:
  - **Max position per symbol** — maximum dollar exposure per single position (configurable).
  - **Max capital allocation** — maximum percentage of total equity deployed across all open positions simultaneously (configurable default: 50%).
  - A signal that would breach either limit is **rejected** and logged; no order is submitted.
- Accepted orders shall be submitted to IBKR as **market orders** by default (configurable to limit orders at signal price ± configurable slippage buffer).
- The system shall persist every submitted order (order ID, symbol, side, quantity, order type, timestamp) to the `trades` table immediately upon submission.
- **Acceptance Criteria:**
  - Given a BUY signal, account equity = $100,000, risk-per-trade = 1%, entry = $50.00, stop = $48.00 → position size = 500 shares.
  - Given a BUY signal that would push total deployed capital above the max allocation limit, the signal is rejected with a logged reason and no order submitted.
  - A submitted market order appears in the `trades` table within 1 second of submission with a non-null IBKR order ID.
  - Given `order_type = limit`, the submitted order uses a limit price = entry_price (not a market order).

---

## FO-EXE-002: Position Tracking & Exit Execution

- The system shall maintain an in-memory and database-persisted snapshot of all open positions **per user** (symbol, user_id, quantity, average entry price, stop-loss level, target price, trailing-stop level, mode, state).
- Exit signals from the Analysis Engine (stop-loss, target reached, trailing-stop triggered) shall be executed immediately as market orders against the full open position size.
- On order fill confirmation from IBKR, the system shall:
  - Update the `positions` table (clear position if fully closed).
  - Update the `trades` table with exit time, exit price, and calculated PnL.
  - Emit a position-closed event to all subscribers (logging, monitoring, reporting).
- The system shall reconcile open positions against the IBKR account state on startup (in case of prior unclean shutdown) and re-adopt any unrecognised open positions.
- **Acceptance Criteria:**
  - An open long position of 500 AAPL shares receives a stop-loss exit signal → a SELL 500 AAPL market order is submitted within 1 second.
  - After fill confirmation, the `positions` table for AAPL shows quantity = 0.
  - PnL for the trade is calculated as `(exit_price − entry_price) × quantity` and stored in `trades`.
  - On startup with an existing IBKR open position not in the local database, the system re-adopts it and logs a reconciliation warning.

---

## FO-EXE-003: Daily Loss Circuit Breaker & Emergency Controls

- The system shall track total realised PnL for the current trading day.
- When the day's cumulative loss reaches or exceeds a configurable **max daily loss** threshold (default: 2% of start-of-day equity), the system shall:
  - Immediately cancel all pending open orders.
  - Close all open positions at market.
  - Suspend further signal processing for the remainder of the day.
  - Log a CRITICAL event and emit an alert notification.
- The system shall provide a manual emergency kill-switch (CLI command or keyboard shortcut in any GUI) that immediately triggers the same close-all-and-halt sequence.
- After a circuit-breaker trigger, the system shall require a manual restart to resume trading on the next trading day.
- **Acceptance Criteria:**
  - Given start-of-day equity = $100,000 and max-daily-loss = 2%, when cumulative realised loss reaches −$2,000, all positions are closed and no further orders are submitted for the rest of the day.
  - A CRITICAL log entry is produced, and the alert notification fires, within 5 seconds of the threshold breach.
  - After circuit-breaker activation, a new entry signal arriving for any symbol is silently discarded (not executed).
  - The manual kill-switch closes all positions within 10 seconds regardless of current system state.

---

## FO-EXE-004: Paper Trading Mode

> Traces to: `requirements.md` §23

- The system shall support **paper trading** (simulated execution) alongside live trading, togglable per user.
- Paper trading shall use identical strategy logic, risk rules, and position management as live trading — only order submission is simulated.
- Simulated order fills: market orders fill immediately at current price; limit orders fill when price crosses the limit level.
- Paper trades and positions shall be stored in the unified `trades` and `positions` tables with `mode = 'paper'` — no separate paper tables.
- Paper P&L shall be calculated identically to live P&L.
- No IBKR API order calls shall be made during paper execution; live market data is used for price reference.
- **Acceptance Criteria:**
  - Given a user in paper mode, a BUY signal generates a simulated fill (no IBKR `place_order()` call); the trade appears in the `trades` table with `mode = 'paper'`.
  - Paper and live trades for the same user are distinguishable by `mode` column.
  - Paper P&L matches what live P&L would have been for identical entry/exit prices.
  - Switching from paper to live mode requires confirmation and does not affect existing paper positions.

---

## FO-EXE-005: Position State Machine & Capital Availability Check

> Traces to: `requirements.md` §21.4, §21.5, §25

- Positions shall transition through states: **NEW → PARTIAL_ENTRY → OPEN → PARTIAL_EXIT → CLOSED**, persisted in the `positions` table `state` column.
- Position states shall be visible in the GUI Position Monitor Panel.
- Partial fills shall transition positions between states: a partial entry fill moves NEW → PARTIAL_ENTRY; full fill moves to OPEN.
- The system shall evaluate **capital availability** before allowing new entries:
  - `available_capital = total_equity - sum(open_position_values)`
  - `RiskManager.can_enter_new(signal, account_state)` returns True only if remaining capital covers the position.
- The GUI shall display: total equity, capital in use, capital available, max allocation limit, and "Can enter next stock? Yes/No" indicator.
- Users shall be able to **override the auto-calculated trade quantity** via the GUI Execution Panel before confirming a trade.
- **Acceptance Criteria:**
  - A new order submission sets position state to NEW; a partial fill changes state to PARTIAL_ENTRY; full fill changes to OPEN.
  - A partial exit fill changes state from OPEN to PARTIAL_EXIT; full exit changes to CLOSED.
  - `can_enter_new()` returns False when capital utilisation exceeds `max_allocation_pct`.
  - User quantity override is respected: if user enters 300 shares (vs auto-calc of 500), exactly 300 shares are submitted.
  - Position states persist across sessions and are correctly restored on startup.

---

## FO-EXE-006: Intraday Candle Readiness for Execution (Phase 1 — Download)

> Traces to: `requirements.md` §10, §21.4

- The system shall, upon receiving the latest screened stock list, download intraday OHLCV candles (3 m, 5 m, and 1 h timeframes) for every symbol in the list and persist them in the database, ensuring a minimum of **390 candles per timeframe** are available before the next trading session begins.
- The download shall be **delta-aware**: if candle data already exists for a symbol, only candles for timestamps after the last stored bar shall be fetched; no re-downloading of existing bars.
- Candles for derived timeframes (5 m, 15 m, 1 h) shall be **aggregated from 1 m source bars** using the `HistoricalDataEngine.aggregate_timeframe()` method defined in INF-003.003; IBKR API calls shall be made only for 1 m bars.
- **Acceptance Criteria:**
  - Given a stock list of N symbols and an empty database, after the download job completes, every symbol has ≥ 390 rows in the `price_1m`-derived 3 m, 5 m, and 1 h stores (or equivalent aggregated view).
  - Given a symbol with 350 existing 3 m bars, the system fetches only the missing bars and brings the count to ≥ 390 without duplicating existing rows.
  - Given a symbol that fails data fetch (IBKR error, rate-limit, etc.), that symbol is logged as failed and the download continues for remaining symbols.
  - The download job completes idempotently: running it twice on the same data produces no duplicate rows and no errors.
