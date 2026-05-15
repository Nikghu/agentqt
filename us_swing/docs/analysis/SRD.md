# Software Requirement Document — Analysis / Live Signal Engine (ANA)

**Document ID:** SRD-ANA
**Version:** 1.1.0
**Traces To:** FO-ANA v1.1.0
**Status:** Draft
**Last Updated:** 2026-03-06
**Project:** US Swing Trading System

---

## Compact Format Key

| Column | Meaning |
|---|---|
| P | Priority: **Must** / Should / Could |
| Status | Draft / Approved / Implemented / Verified / Reopen |

---

## Section 1: Requirements for FO-ANA-001 — Real-Time Bar Ingestion & Candle Construction

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-ANA-001.001 | FO-ANA-001 | Must | `LiveEngine.subscribe(symbols)` calls `IBKRClient.subscribe_realtime_bars(symbol, bar_size=5)` for each symbol in the watchlist (max 20). Unsubscribes any symbol no longer in the list. Note: `LiveBarWorker` (EXE tool) uses `reqTickByTick` directly and bypasses `LiveEngine`; this SRD governs the ANA-tool `LiveEngine` path only. | `list[str]` symbols, `IBKRClient` | active IBKR subscriptions | Subscription count must never exceed 20; excess symbols are queued with warning | Draft |
| SRD-ANA-001.002 | FO-ANA-001 | Must | `CandleBuilder` maintains one rolling buffer per (symbol, timeframe) using time-based windows. On each incoming `RealtimeBar`: compute `window_start = _floor_to_tf(bar.datetime, tf_secs)` (Unix-timestamp floor-aligned); if `bar.datetime >= window_start + timedelta(seconds=tf_secs)`, close the current window and emit the candle; otherwise append bar to the current window's buffer. Supported timeframes: 1m, 3m, 5m, 15m, 1h. Input may be individual trade ticks (open=high=low=close=price) or pre-aggregated bars. | `RealtimeBar(symbol, datetime, open, high, low, close, volume)` | `OHLCVBar` emitted on window close | Window boundaries are time-based, not count-based; buffer is in-memory only — cleared via `reset(symbol)` | Draft |
| SRD-ANA-001.003 | FO-ANA-001 | Must | Candle aggregation rules: `open` = first-bar open, `high` = max(high), `low` = min(low), `close` = last-bar close, `volume` = sum(volume), `datetime` = `window_start` (floor-aligned boundary, not the first tick's timestamp). Applied identically for all timeframes and input granularities (individual ticks or pre-aggregated bars). | list of `RealtimeBar` within time window | `OHLCVBar` | Same aggregation used for both tick-level and 5s-bar input; using `window_start` as candle datetime guarantees alignment with the timeframe grid regardless of when the first tick arrived | Draft |
| SRD-ANA-001.004 | FO-ANA-001 | Must | On candle close, `CandleBuilder` fires `on_candle_closed(symbol, timeframe, bar: OHLCVBar)` callback. `LiveEngine` receives this callback and dispatches to: (a) `StrategyEngine` for signal evaluation, (b) `DatabasePersister` for async write. | `OHLCVBar` | dispatched to strategy + DB | Dispatch to `StrategyEngine` must be synchronous (same tick); DB write must be asynchronous | Draft |
| SRD-ANA-001.005 | FO-ANA-001 | Should | When a gap in tick delivery spans one or more complete windows (e.g., no trades in a 3m period due to low liquidity or a trading halt), those windows produce no candle — they are silently skipped. `CandleBuilder` does not synthesise flat gap candles. Strategy engines reading from the `price_3m` / `price_15m` tables must handle sparse sequences (missing rows) without error. | time gap between ticks | no candle emitted for windowless periods | Gap detection is implicit in the time-based close condition; no explicit gap-fill logic required | Draft |
| SRD-ANA-001.006 | FO-ANA-001 | Must | `DatabasePersister.persist_candle(symbol, timeframe, bar)` queues the completed candle for async bulk insert via `DatabaseManager.insert_bars()`. Uses a thread-safe queue; dedicated writer thread drains the queue every 5 seconds. | `OHLCVBar` | bar committed to `price_*` table | Writer thread failure must log ERROR but not crash `LiveEngine` | Draft |

---

## Section 2: Requirements for FO-ANA-002 — Multi-Timeframe Entry & Exit Signal Generation

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-ANA-002.001 | FO-ANA-002 | Must | `StrategyEngine.on_candle_closed(symbol, timeframe, bar)` is called by `LiveEngine`. The engine maintains a per-symbol bar cache (last N candles per timeframe, N configurable, default 50). Updates cache on each call, then evaluates all enabled strategies. | `OHLCVBar`, bar cache | `TradeSignal \| None` | Evaluation must complete < 50 ms per symbol to keep up with 5s bar cadence | Draft |
| SRD-ANA-002.002 | FO-ANA-002 | Must | `BreakoutStrategy.evaluate(symbol, bar_cache)` triggers a BUY signal when the 15m (or 5m, configurable) close exceeds the highest high of the prior N 15m bars (configurable N default 20). Trend filter: 1h close > 1h EMA(50). | 15m, 5m, and 1h bar caches | `TradeSignal(BUY)` or None | Trend filter must pass before entry filter is evaluated; both conditions must be true | Draft |
| SRD-ANA-002.003 | FO-ANA-002 | Must | `PullbackStrategy.evaluate(symbol, bar_cache)` triggers a BUY signal when: 1h close > 1h EMA(21) (uptrend), AND the 5m close crosses back above 5m EMA(21) after being below it (pullback recovery). | 1h, 5m bar caches | `TradeSignal(BUY)` or None | EMA must be computed from at least 21 complete bars; insufficient bars → no signal | Draft |
| SRD-ANA-002.004 | FO-ANA-002 | Must | `TradeSignal` data class: `{symbol, direction: Literal['BUY','SELL'], entry_price, stop_loss, target_price, timeframe, strategy_id, timestamp}`. `stop_loss` = entry − ATR(14) × `atr_multiplier` (config). `target_price` = entry + (entry − stop_loss) × `r_multiple` (config, default 2.0). | entry bar, ATR, config | `TradeSignal` instance | All prices must be > 0; stop > 0; target > entry for BUY | Draft |
| SRD-ANA-002.005 | FO-ANA-002 | Must | `ExitManager.evaluate(symbol, bar_cache, open_position)` emits a SELL signal when any of: (a) price closes below `stop_loss`, (b) price reaches `target_price`, (c) trailing stop (ATR-trail) is triggered. | bar cache, `OpenPosition` | `TradeSignal(SELL)` or None | Only one SELL signal per open position per evaluation cycle | Draft |
| SRD-ANA-002.006 | FO-ANA-002 | Must | `TrailingStop.update(symbol, bar, open_position)` advances the trailing stop upward (for longs) when price moves `activation_r` × R above entry. Trail = highest close seen − ATR(14) × `trail_multiplier`. Stop is never moved downward. | current bar, `OpenPosition` | updated `open_position.trailing_stop` | Trail activation and step must be logged at DEBUG level for every update | Draft |
| SRD-ANA-002.007 | FO-ANA-002 | Must | `StrategyEngine` must not emit an entry signal for a symbol that has an existing open position **for the active user** (checked via `PositionTracker.has_open(user_id, symbol)`). No pyramiding by default; configurable per user. | `PositionTracker` state, `user_id` | entry signal suppressed if position exists for user | Emit DEBUG log: `Signal suppressed for {symbol} (user={user_id}): existing position` | Draft |
| SRD-ANA-002.008 | FO-ANA-002 | Should | Each emitted signal is logged at INFO level with full metadata: `Signal: {strategy_id} {direction} {symbol} @ {entry_price} SL={stop_loss} TP={target_price} TF={timeframe}`. | `TradeSignal` | INFO log entry | Must appear in log file within 1 s of signal emission | Draft |

---

## Section 3: Requirements for Per-User Strategy Configuration

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-ANA-003.001 | FO-ANA-002 | Must | `StrategyEngine` shall accept a `StrategyConfig` object at construction that specifies which strategies are enabled and their parameter overrides. This config is loaded from the active user's `settings_json["strategy_config"]`. | `StrategyConfig` from user settings | engine configured per user | Missing keys in settings_json fall back to system defaults | Draft |
| SRD-ANA-003.002 | FO-ANA-002 | Must | `StrategyConfig` contains: `breakout_enabled: bool`, `pullback_enabled: bool`, `atr_multiplier: float`, `r_multiple: float`, `trail_multiplier: float`, `activation_r: float`, plus per-strategy parameter overrides. | user `settings_json` | typed `StrategyConfig` | Must validate: `atr_multiplier > 0`, `r_multiple > 0`, `trail_multiplier > 0` | Draft |
| SRD-ANA-003.003 | FO-ANA-002 | Should | Strategy parameters shall be editable from the GUI Settings Panel. Changes are persisted to the user's `settings_json` and take effect on the next signal evaluation cycle (no restart required). | GUI input fields | updated `users.settings_json` | Validation before persistence: reject values out of acceptable range with GUI error display | Draft |
