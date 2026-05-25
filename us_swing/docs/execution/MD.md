# Module Decomposition — Execution & Risk Management (EXE)

**Document ID:** MD-EXE
**Version:** 1.6.0
**Traces To:** SRD-EXE v1.7.0 / DD-EXE v1.7.0
**Status:** Draft
**Last Updated:** 2026-05-22
**Project:** US Swing Trading System

> v1.6.0: MD-EXE-011.* (Strategy Engine, 7 modules) and MD-EXE-012.* (Trade Cycle Ledger, 6 modules) added.

---

## EXE Modules

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP | Status |
|---|---|---|---|---|---|---|---|
| MD-EXE-001.001.M01 | SRD-EXE-001.001–002, SRD-EXE-005.004 | `src/us_swing/execution/risk_manager.py` | `RiskManager` — signal validation, position size calculation, capital availability check, `RiskConfig` dataclass | `validate_signal(signal, account_state, cb_active) -> ValidationResult`, `can_enter_new(signal, account_state, user_id) -> bool`, `calculate_position_size(signal, account_state) -> int` | `data/models.py`, `config/settings.py` | No | Draft |
| MD-EXE-001.001.M02 | SRD-EXE-001.003–006, SRD-EXE-002.003, SRD-EXE-004.005, SRD-EXE-005.005 | `src/us_swing/execution/execution_engine.py` | `ExecutionEngine` — submit entry/exit orders, handle fills, route to paper/live, user qty override, update DB and PositionTracker | `submit_signal(signal, account_state, quantity_override=None) -> int \| None`, `exit_position(symbol) -> int \| None`, `handle_order_fill(fill)` | `broker/client.py`, `risk_manager.py`, `position_tracker.py`, `paper_engine.py`, `db/manager.py`, `data/models.py` | No | Draft |
| MD-EXE-002.001.M01 | SRD-EXE-002.001–005, SRD-EXE-005.001–003, SRD-EXE-005.006 | `src/us_swing/execution/position_tracker.py` | `PositionTracker` — thread-safe in-memory + DB-mirrored open position state with state machine, per-user scoping, startup restore | `open(pos)`, `close(user_id, symbol) -> OpenPosition`, `update_stop(user_id, symbol, new_stop)`, `update_state(user_id, symbol, new_state, filled_qty=None)`, `has_open(user_id, symbol) -> bool`, `get_all(user_id=None) -> list[OpenPosition]`, `load_from_db(user_id)`, `reconcile(ibkr_positions) -> list[str]` | `db/manager.py`, `data/models.py`, `threading` | No | Draft |
| MD-EXE-003.001.M01 | SRD-EXE-003.001–002 | `src/us_swing/execution/circuit_breaker.py` | `DailyPnLTracker` and `CircuitBreaker` — track daily realised PnL, evaluate breach condition | `DailyPnLTracker.add(pnl)`, `DailyPnLTracker.reset()`, `DailyPnLTracker.daily_pnl`, `CircuitBreaker.check(daily_pnl, equity) -> bool` | `data/models.py`, `threading` | No | Draft |
| MD-EXE-003.001.M02 | SRD-EXE-003.003–006 | `src/us_swing/execution/emergency.py` | `EmergencyShutdown` — cancel orders, close positions, halt engine, log CRITICAL, write shutdown JSON. Callable via CLI, SIGTERM, or GUI button. | `run(reason: str)` async | `broker/client.py`, `execution_engine.py`, `position_tracker.py`, `analysis/live_engine.py`, `monitoring/alerts.py`, `pathlib` | No | Draft |
| MD-EXE-004.001.M01 | SRD-EXE-004.001–004 | `src/us_swing/execution/paper_engine.py` | `PaperEngine` — simulated order filling for paper mode. Market orders fill at current price; limit orders fill on price cross. Uses live `DataProvider` for price reference. | `simulate_fill(signal, quantity, order_type) -> PaperFill`, `simulate_exit(symbol) -> PaperFill` | `data/providers/*`, `position_tracker.py`, `db/manager.py`, `data/models.py` | No | Draft |
| MD-EXE-004.001.M02 | SRD-EXE-004.005 | `src/us_swing/execution/execution_router.py` | `ExecutionRouter` — routes signals to `PaperEngine` or `ExecutionEngine` based on active user's mode. Mode is checked per-signal, not cached. | `route_signal(user_id, signal, **kwargs) -> int \| None` | `execution_engine.py`, `paper_engine.py`, `user/manager.py` | No | Draft |
| MD-EXE-006.001.M01 | SRD-EXE-006.001–006 | `src/usswing/execution/intraday_candle_loader.py` | `IntradayCandleLoader(QThread)` — delta-fetches 1 m bars from IBKR for a stock list, validates ≥ 390 candles per timeframe (3 m, 5 m, 1 h), persists via `DatabaseManager`, emits progress/completion signals. `CandleLoadResult` and `SymbolReadiness` dataclasses. | `load(symbols) → None` (QThread.start), `get_readiness_report(symbols) -> dict[str, SymbolReadiness]`, signals: `load_progress(str, int, int)`, `load_complete(list[CandleLoadResult])` | `broker/client.py` (IBKRClient), `db/manager.py` (DatabaseManager), `data_engine/engine.py` (HistoricalDataEngine), `PyQt6.QtCore.QThread` | No | Draft |
| MD-EXE-007.001.M01 | SRD-EXE-007.003–008 | `src/us_swing/execution/live_bar_worker.py` | `LiveBarWorker(QThread)` — subscribes to IBKR tick-by-tick trade data via `reqTickByTick('Last', numberOfTicks=0)`, applies RTH guard per tick, converts each trade to `RealtimeBar(open=high=low=close=price, volume=size)`, delegates aggregation to `CandleBuilder` (3m + 15m time-based windows), persists completed bars to `price_3m` / `price_15m` via raw SQLite INSERT OR IGNORE, emits `candle_closed(str)` signal. Falls back to yfinance 60s polling when IBKR is unavailable. | `request_stop() -> None`; signal: `candle_closed(str)` | `analysis/candle_builder.py` (CandleBuilder), `data/models.py` (RealtimeBar, OHLCVBar), `PyQt6.QtCore.QThread`, `asyncio`, `sqlite3`, `zoneinfo`, `ib_insync` (optional), `yfinance` (optional fallback) | No | Draft |
| MD-EXE-008.001.M01 | SRD-EXE-008.001–006 | `src/us_swing/execution/live_tick_worker.py` | `LiveTickWorker(QThread)` — owns `ib_insync.IB()` with dedicated clientId (default 14); maintains `reqMktData` subscriptions for a caller-supplied `dict[str, Contract]`; emits `tick_price(tag, price)` via `pendingTickersEvent` with `last → close` price fallback; emits `subscription_failed(tag, code)` on IBKR errors 200/354/420; `set_contracts()` reconciles subscriptions in batches of 10 with 200 ms pause; `request_stop()` cancels all subscriptions and disconnects within 3 s; clientId collision (error 326) retried up to 3 times | `set_contracts(contracts: dict[str, Contract]) -> None`, `request_stop() -> None`; signals: `tick_price(str, float)`, `subscription_failed(str, int)` | `ib_insync` (IB, Contract, Ticker), `PyQt6.QtCore.QThread`, `asyncio`, `threading`, `math.isnan` | No | Draft |
| MD-EXE-009.001.M01 | SRD-EXE-009.012 | `src/us_swing/core/monitoring_session/_dto.py` + `_enums.py` | Frozen `@dataclass(slots=True)` DTOs and string enums shared across the package. `_dto.py` defines `KeepSet`, `ReconcileReport`, `ReconcileError`, `MonitoringSessionRow`, `FillEvent`, `InvariantReport`, `PositionSnapshot`. `_enums.py` defines `LifecycleState`, `TradeOrigin`, `Side`. Every DTO carries `schema_version: int = 1`. No SQLAlchemy or PyQt6 imports. | Dataclass + enum constructors (auto-generated). No methods beyond `__slots__` / `__init__`. | `dataclasses`, `enum`, `datetime` | No | Draft |
| MD-EXE-009.001.M02 | SRD-EXE-009.010, SRD-EXE-009.011 | `src/us_swing/core/monitoring_session/_protocols.py` | `typing.Protocol` declarations for `MonitoringQuery`, `MonitoringCommand`, `MonitoringEventBus`, `Subscription`. All `@runtime_checkable`. Pure interface module — no runtime logic. Broken out from `__init__.py` to avoid a circular import between `_service.py` (implementer) and `_dto.py` (DTO consumer). | `MonitoringQuery` (5 read methods + `check_invariant`), `MonitoringCommand` (3 mutating methods), `MonitoringEventBus` (subscribe/publish), `Subscription` (cancel) | `typing.Protocol`, `_dto`, `_enums` | No | Draft |
| MD-EXE-009.001.M03 | SRD-EXE-009.011 | `src/us_swing/core/monitoring_session/_events.py` | `MonitoringEvent` sealed union of 7 frozen dataclasses (`SymbolStartedMonitoring`, `SymbolEnteredPosition`, `SymbolPositionScaled`, `SymbolExitedPosition`, `SymbolSkipped`, `SymbolEvicted`, `ReconcileCompleted`) plus `_InProcessBus` concrete implementation of `MonitoringEventBus`. Synchronous in-thread dispatch; handler exceptions caught and logged with `[Lifecycle]` topic; subscription lifetimes managed via explicit `Subscription.cancel()`. | 7 event classes; `_InProcessBus(subscribe, publish)` | `_dto`, `_enums`, `_protocols`, `threading`, `uuid`, `logging`, `collections.defaultdict` | No | Draft |
| MD-EXE-009.002.M01 | SRD-EXE-009.001, SRD-EXE-009.005–007, SRD-EXE-009.009, SRD-EXE-010.002 | `src/us_swing/core/monitoring_session/_repository.py` | `MonitoringRepository` — the only file under `core/monitoring_session/` permitted to import SQLAlchemy. Wraps every ledger / trades / positions DB access; uses SQLite `RETURNING` for atomic eviction; per-symbol single-transaction eviction across `price_1m/3m/15m`. | `insert_monitoring_rows`, `fetch_earliest_open_monitoring_row`, `transition_to_entered`, `transition_to_exited`, `bulk_skip_stale_monitoring`, `evict_symbol_atomic`, `fetch_history`, `fetch_session`, `open_system_position_symbols`, `has_open_system_position`, `position_anchor`, `insert_trade_with_anchor`, `upsert_position_with_anchor`, `entered_symbols`, `stale_lifecycle_symbols` | `sqlalchemy` (Engine, text, Connection), `_dto`, `_enums` | No | Draft |
| MD-EXE-009.002.M02 | SRD-EXE-009.004–010 | `src/us_swing/core/monitoring_session/_service.py` | `MonitoringSessionService` — concrete class implementing both `MonitoringQuery` and `MonitoringCommand`. Owns the `on_fill` decision tree, the `RLock`-guarded state transitions, and the single-flight reconciler. Publishes events to the injected bus; never touches SQLAlchemy directly (delegates to `MonitoringRepository`). Reconciler implementation per DD-EXE-010.001.D01 (per-symbol failure isolation, retry-once on `OperationalError`). | All `MonitoringQuery` + `MonitoringCommand` methods | `_repository`, `_events`, `_dto`, `_enums`, `_protocols`, `threading`, `uuid`, `datetime`, `time`, `logging`, `screener.storage.ScreenerResultsStorage` (read-only) | No | Draft |
| MD-EXE-009.002.M03 | SRD-EXE-009.010, SRD-EXE-009.012 | `src/us_swing/core/monitoring_session/__init__.py` | Public surface — re-exports `MonitoringQuery`, `MonitoringCommand`, `MonitoringEventBus`, `Subscription`, all DTOs/enums, all 7 event classes, and the `build_default_service` factory. Concrete classes (`MonitoringSessionService`, `MonitoringRepository`, `_InProcessBus`) are NOT re-exported. Explicit `__all__` enumerates the surface. | `build_default_service(engine, *, today_provider=None, clock=None) -> tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]` | `_service`, `_repository`, `_events`, `_protocols`, `_dto`, `_enums` (all internal) | No | Draft |
| MD-EXE-010.001.M01 | SRD-EXE-010.004 | `src/us_swing/core/monitoring_session/_scheduler.py` | `_ReconcileScheduler` — registers a `15 9 * * MON-FRI` cron on the injected `cron_register` callable; provides `maybe_run_on_startup()` for catch-up; subscribes to `ReconcileCompleted` to track per-day "already-ran" state. Pure orchestration — single-flight protection lives inside `MonitoringSessionService.reconcile_preopen`. | `start() -> None`, `maybe_run_on_startup() -> ReconcileReport \| None` | `_protocols`, `_events`, `zoneinfo`, `datetime` | No | Draft |

---

## Cross-Tool Modifications for FO-EXE-007

These existing modules in other tools require targeted changes to support Phase 2. They are not new EXE modules but must be updated as part of the FO-EXE-007 implementation.

| Module ID | File | Change Required | SRD |
|---|---|---|---|
| MD-INF-004.001.M02 | `src/us_swing/db/schema.py` | Add `price_3m` SQLAlchemy table, `idx_price_3m_sym_dt` index, and `PRICE_TABLES["3m"]` entry. Additive — `create_schema(checkfirst=True)` handles existing databases with no migration. | SRD-EXE-007.001 |
| MD-EXE-006.001.M01 | `src/us_swing/execution/intraday_candle_loader.py` | Update `get_readiness_report()`: replace the time-windowed `COUNT(*) FROM price_1m` query for `candles_3m` with `COUNT(*) FROM price_3m WHERE symbol = :sym` (no cutoff; every row is a completed bar). `candles_5m` and `candles_1h` queries are unchanged. | SRD-EXE-007.009 |

---

## Cross-Tool Modifications for FO-EXE-009 / FO-EXE-010

These existing modules require targeted patches as part of the monitoring-session feature. They are not new MD entries but must be updated alongside the new `core/monitoring_session/` package.

| Module ID | File | Change Required | SRD |
|---|---|---|---|
| MD-INF-004.001.M02 | `src/us_swing/db/schema.py` | Declare `monitoring_session` table with columns (`session_date`, `symbol`, `preset_id`, `run_timestamp`, `added_at`, `lifecycle_state`, `entered_at`, `exited_at`, `evicted_at`, `trade_id`), composite PK `(session_date, symbol)`, indexes `idx_monitoring_session_state` and `idx_monitoring_session_symbol`. Declare new columns `trade_origin TEXT` and `monitoring_session_date TEXT` on `trades`; `origin TEXT` and `anchor_session_date TEXT` on `positions`. All additive — `create_schema(checkfirst=True)` provisions fresh DBs. | SRD-EXE-009.001, SRD-EXE-009.002, SRD-EXE-009.003 |
| MD-INF-004.001.M01 | `src/us_swing/db/manager.py` | Add `migrate_lifecycle_columns(engine)` function. Idempotent `PRAGMA table_info(...)` check + `ALTER TABLE ADD COLUMN` for each of the 4 new columns on `trades` and `positions`. Called once from `DatabaseManager.__init__` after `create_schema(...)`. | SRD-EXE-009.002, SRD-EXE-009.003 |
| MD-EXE-001.001.M02 | `src/us_swing/execution/execution_engine.py` | In `handle_order_fill(fill)`, after the existing `PositionTracker` mutation, build a `FillEvent` and call `self._lifecycle_command.on_fill(fill_event)`. `TradeOrigin.SYSTEM` when the originating signal came from `StrategyEngine`, `TradeOrigin.MANUAL` when from the GUI execution panel. `_lifecycle_command` injected via constructor; defaults to a no-op stub if unset (preserves backward compatibility for non-lifecycle code paths). | SRD-EXE-009.004–008, SRD-EXE-010.006 |
| MD-INF-001.001.M03 (or AppService home module) | `src/us_swing/app_service.py` | In `__init__`: call `build_default_service(engine)` once; store the returned `(query, command, bus)` triple; instantiate `_ReconcileScheduler(command, bus, cron_register=self._scheduler.register_cron)`; call `scheduler.start()` then `scheduler.maybe_run_on_startup()` BEFORE constructing `LiveBarWorker`. Replace `_on_screener_results_updated` body to route through `command.on_screener_results(result)` and feed `keep_set` into `IntradayCandleLoader` + `LiveBarWorker.set_symbols`. Subscribe to `ReconcileCompleted` to push the post-reconcile keep set into a running `LiveBarWorker`. | SRD-EXE-010.004, SRD-EXE-010.006, SRD-EXE-009.004 |
| (Future) GUI bridge module | `src/us_swing/gui/lifecycle_bridge.py` | NEW Qt bridge — wraps `MonitoringEventBus` subscriptions and re-emits as `pyqtSignal` for the GUI thread. Out of scope for the v1 implementation of this feature; tracked as a follow-up GUI MD once a "Lifecycle History" panel is requested. | (deferred) |

---

## Module Dependency Graph

```
data/models.py

execution/risk_manager.py     ← data/models.py, config/settings.py
execution/position_tracker.py ← db/manager.py, data/models.py, threading
execution/circuit_breaker.py  ← data/models.py, threading
execution/paper_engine.py     ← data/providers/*, position_tracker.py, db/manager.py
execution/execution_engine.py ← broker/client.py, risk_manager.py, position_tracker.py, paper_engine.py, db/manager.py
execution/execution_router.py        ← execution_engine.py, paper_engine.py, user/manager.py
execution/emergency.py               ← broker/client.py, execution_engine.py, position_tracker.py,
                                        analysis/live_engine.py, monitoring/alerts.py
execution/intraday_candle_loader.py  ← broker/client.py, db/manager.py, data_engine/engine.py,
                                        PyQt6.QtCore
execution/live_bar_worker.py         ← analysis/candle_builder.py, data/models.py,
                                        PyQt6.QtCore, asyncio, sqlite3, ib_insync (opt), yfinance (opt)
execution/live_tick_worker.py        ← ib_insync, PyQt6.QtCore, asyncio, threading, math

core/monitoring_session/
  _enums.py        ← (stdlib only)
  _dto.py          ← _enums
  _protocols.py    ← _dto, _enums, typing
  _events.py       ← _dto, _enums, _protocols, threading, uuid, logging
  _repository.py   ← _dto, _enums, sqlalchemy
  _scheduler.py    ← _protocols, _events, zoneinfo, datetime
  _service.py      ← _repository, _events, _protocols, _dto, _enums,
                       screener/storage.py (read-only), threading, uuid
  __init__.py      ← all above (public surface only)
```

`execution/execution_engine.py` and `app_service.py` import only from `core.monitoring_session` (the public `__init__.py`). No module outside the package imports `core.monitoring_session._*`.

---

## Full Project Module Map (All Tools)

```
src/us_swing/
├── __init__.py
├── __main__.py                        # CLI: `python -m us_swing [run|health|kill]`
├── config/
│   └── settings.py                    # MD-INF-001.001.M03
├── user/
│   └── manager.py                     # MD-INF-006.001.M01
├── data/
│   ├── models.py                      # MD-INF-004.001.M03  (shared across all tools)
│   └── providers/
│       ├── ibkr_provider.py           # MD-INF-007.001.M01
│       └── dummy_provider.py          # MD-INF-007.001.M02
├── broker/
│   ├── client.py                      # MD-INF-001.001.M01
│   └── pacing.py                      # MD-INF-001.001.M02
├── db/
│   ├── schema.py                      # MD-INF-004.001.M02
│   └── manager.py                     # MD-INF-004.001.M01
├── universe/
│   └── manager.py                     # MD-INF-002.001.M01
├── data_engine/
│   └── engine.py                      # MD-INF-003.001.M01
├── monitoring/
│   ├── logging_setup.py               # MD-INF-005.001.M01
│   ├── alerts.py                      # MD-INF-005.001.M02
│   └── health.py                      # MD-INF-005.001.M03
├── screener/
│   ├── config.py                      # MD-SCR-001.001.M03
│   ├── filters.py                     # MD-SCR-001.001.M02
│   ├── engine.py                      # MD-SCR-001.001.M01
│   └── watchlist.py                   # MD-SCR-002.001.M01
├── analysis/
│   ├── indicators.py                  # MD-ANA-001.001.M04  (shared utility)
│   ├── candle_builder.py              # MD-ANA-001.001.M01
│   ├── db_persister.py                # MD-ANA-001.001.M03
│   ├── live_engine.py                 # MD-ANA-001.001.M02
│   ├── strategy_engine.py             # MD-ANA-002.001.M01
│   ├── exit_manager.py                # MD-ANA-002.001.M04
│   └── strategies/
│       ├── breakout.py                # MD-ANA-002.001.M02
│       └── pullback.py                # MD-ANA-002.001.M03
├── execution/
│   ├── risk_manager.py                # MD-EXE-001.001.M01
│   ├── execution_engine.py            # MD-EXE-001.001.M02  (patched for on_fill routing)
│   ├── position_tracker.py            # MD-EXE-002.001.M01
│   ├── circuit_breaker.py             # MD-EXE-003.001.M01
│   ├── emergency.py                   # MD-EXE-003.001.M02
│   ├── paper_engine.py                # MD-EXE-004.001.M01
│   ├── execution_router.py            # MD-EXE-004.001.M02
│   ├── intraday_candle_loader.py      # MD-EXE-006.001.M01
│   ├── live_bar_worker.py             # MD-EXE-007.001.M01
│   └── live_tick_worker.py            # MD-EXE-008.001.M01
└── core/
    └── monitoring_session/
        ├── __init__.py                # MD-EXE-009.002.M03 (public surface + build_default_service)
        ├── _enums.py                  # MD-EXE-009.001.M01 (combined with _dto.py)
        ├── _dto.py                    # MD-EXE-009.001.M01
        ├── _protocols.py              # MD-EXE-009.001.M02
        ├── _events.py                 # MD-EXE-009.001.M03
        ├── _repository.py             # MD-EXE-009.002.M01
        ├── _service.py                # MD-EXE-009.002.M02
        └── _scheduler.py              # MD-EXE-010.001.M01
```

> **Note:** `core/` is a new top-level package introduced by this feature. It hosts cross-tool shared services per `.claude/rules/code-style.md` ("Shared cross-cutting code goes in `src/usswing/core/` — never duplicate across tools"). Subsequent cross-tool services (future Intraday Strategy Execution, Backtesting) will live as sibling subpackages under `core/`.

---

## FO-EXE-011 — Strategy Engine Modules

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP | Status |
|---|---|---|---|---|---|---|---|
| MD-EXE-011.001.M01 | SRD-EXE-011.001 — .003, .013 | `src/us_swing/execution/strategy_engine/_engine.py` | `StrategyEngine(QThread)` — owns asyncio loop, registry, signal queue; subscribes to `candle_closed`; orchestrates `_router_loop`, `_end_time_watcher_loop`, `_emergency_drain_loop` | `start()`, `request_stop()`, `emergency_stop()`, `reload_registry()` | `_context`, `_router`, `_evaluator`, `_events`, `_signals`, `PyQt6.QtCore.QThread`, `asyncio` | No | Approved |
| MD-EXE-011.001.M02 | SRD-EXE-011.002, .004, .005, .007, .010 | `src/us_swing/execution/strategy_engine/_context.py` | `_StrategyContext` dataclass + `_CycleState(StrEnum)` — symbol-scope filter, schedule guard, per-`(strategy,symbol)` cycle state, `asyncio.Lock` map | `_StrategyContext.accepts(symbol)`, `lock_for(symbol)`, `state(symbol)`; `_CycleState` enum | `dataclasses`, `enum`, `asyncio`, FO-GUI-013 `StrategyConfig` | No | Approved |
| MD-EXE-011.001.M03 | SRD-EXE-011.006 | `src/us_swing/execution/strategy_engine/_evaluator.py` | `ConditionEvaluator` — tokenizer + recursive-descent parser + `FUNCTION_MAP` of 14 indicators; stateless; evaluates expression against candle dict | `evaluate(expr, candles, symbol) -> bool` | `pandas`, `numpy`, `talib`, `re` | No | Approved |
| MD-EXE-011.001.M04 | SRD-EXE-011.008, .009, .011, .012 | `src/us_swing/execution/strategy_engine/_router.py` | Signal-queue consumer + Mode/auto_trade dispatch; calls `RiskManager.validate()` and `ExecutionRouter.submit()` for auto path or `PendingSignalStore.add()` for manual path; owns `_end_time_watcher_loop` | `_router_loop()`, `_force_exit(ctx, symbol, reason)` (coroutines, internal) | `risk_manager`, `execution_router`, `pending_signal_store`, `_signals`, `_events` | No | Approved |
| MD-EXE-011.001.M05 | SRD-EXE-011.015 | `src/us_swing/execution/strategy_engine/_events.py` | Sealed `StrategyEvent` union: `StrategyEntered`, `StrategyExited`, `StrategySquaredOff`, `StrategyErrored`, `StrategySignalDropped`, `StrategySignalPending`; each frozen `@dataclass(slots=True)` with `schema_version: int = 1` | Event class constructors | `dataclasses`, FO-EXE-009 event bus | No | Approved |
| MD-EXE-011.001.M06 | SRD-EXE-011.008 | `src/us_swing/execution/strategy_engine/_signals.py` | `TradeSignal` frozen dataclass — payload pushed onto the engine queue (`action`, `symbol`, `strategy_id`, `entry_price`, `stop_loss`, `target`, `qty_recommended`, `reason`) | `TradeSignal(...)` constructor; `Action` `StrEnum` (`ENTRY`/`EXIT`) | `dataclasses`, `enum` | No | Approved |
| MD-EXE-011.001.M07 | SRD-EXE-011.001 — .015 | `src/us_swing/execution/strategy_engine/__init__.py` | Public surface — re-exports `StrategyEngine`, `StrategyEvent` union members, `TradeSignal`, `Action`. Concrete internals (`_context`, `_router`, `_evaluator`) NOT re-exported. Explicit `__all__`. | `StrategyEngine`, event classes, `TradeSignal`, `Action` | All internal `_*` modules | No | Approved |

### Cross-Module Modifications for FO-EXE-011

| Module ID | File | Change Required | SRD |
|---|---|---|---|
| MD-EXE-001.001.M01 | `src/us_swing/execution/risk_manager.py` | Add `can_allocate(strategy_id, capital_max_pct, entry_price, qty) -> CanAllocateResult` method per-strategy capital cap check used at signal-emit time. | SRD-EXE-011.011 |
| — | `src/us_swing/execution/pending_signal_store.py` | **NEW** — `PendingSignalStore`: in-memory `dict[str, TradeSignal]` keyed by `signal_id`, with `add()`, `dismiss()`, `execute()`, `list()`, signals `pending_signal_added(signal)` / `pending_signal_removed(signal_id)`. Consumed by FO-GUI-014 Active Cycles Panel. | SRD-EXE-011.009 |
| MD-GUI-013.001.M01 | `src/us_swing/gui/strategy_builder_dialog.py` | `load_strategies()` / `save_strategies()` and the `commit()` helper are re-used by the engine for `strategy_signal` runtime writeback. No code change — engine imports the same module. | SRD-EXE-011.014 |

---

## FO-EXE-012 — Trade Cycle Ledger Modules

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP | Status |
|---|---|---|---|---|---|---|---|
| MD-EXE-012.001.M01 | SRD-EXE-012.001 | `src/us_swing/execution/trade_cycle/_schema.py` | `trade_cycles` SQLAlchemy Table + composite indexes (`idx_trade_cycles_state_symbol`, `idx_trade_cycles_strategy_symbol_state`); re-exported through `db/schema.py` | Module-level `trade_cycles` Table, index objects | `sqlalchemy`, `db/schema.metadata` | No | Approved |
| MD-EXE-012.001.M02 | SRD-EXE-012.010, .011 | `src/us_swing/execution/trade_cycle/_dto.py` | `CycleSnapshot` frozen `@dataclass(slots=True)` with `schema_version: int = 1`; enum frozensets (`CYCLE_STATES`, `EXIT_REASONS`, `TARGET_TYPES`, `STOPLOSS_TYPES`, `TRAILING_MODES`); validation helpers used by repository | `CycleSnapshot`, frozenset constants, `validate_state()`, `validate_exit_reason()` | `dataclasses`, `enum` | No | Approved |
| MD-EXE-012.001.M03 | SRD-EXE-012.012 | `src/us_swing/execution/trade_cycle/_events.py` | Sealed `TradeCycleEvent` union: `CycleOpened`, `CycleUpdated`, `ExitTrigger`, `CycleClosing`, `CycleClosed`, `CycleAborted`, `RiskUpdated`; all frozen dataclasses with `schema_version: int = 1` | Event class constructors | `_dto`, `dataclasses`, FO-EXE-009 event bus | No | Approved |
| MD-EXE-012.002.M01 | SRD-EXE-012.003, .007 — .010, .013 | `src/us_swing/execution/trade_cycle/_repository.py` | `TradeCycleRepository` — only file under `trade_cycle/` permitted to import SQLAlchemy. Same-tx duplicate-open guard, compare-and-swap `update_state`, allowed-transitions dict | `open_cycles()`, `cycle(id)`, `history(...)`, `find_open(strategy_id, symbol)`, `find_by_entry_order(id)`, `insert_open(row)`, `update_live(id, fields)`, `update_state(id, new_state)`, `update_risk(id, fields)`, `close(id, exit_fields)`, `abort(id, reason)` | `sqlalchemy`, `_schema`, `_dto`, `datetime` | No | Approved |
| MD-EXE-012.002.M02 | SRD-EXE-012.002 — .009, .011, .013 | `src/us_swing/execution/trade_cycle/_service.py` | `TradeCycleService` — owns `_TickAccumulator` map, subscribes to `LiveTickWorker.tick_price` (FO-EXE-008), receives FO-EXE-002 fill events, runs throttle + flush + exit-trigger evaluation, publishes `TradeCycleEvent` payloads | `on_entry_fill(fill)`, `on_exit_fill(fill)`, `on_entry_failed(id, reason)`, `update_risk(id, **fields)`, `reload() -> int`, `start()`, `stop()` | `_repository`, `_events`, `_dto`, FO-EXE-009 bus, FO-EXE-008 tick worker, `asyncio`, `datetime`, `logging` | No | Approved |
| MD-EXE-012.002.M03 | SRD-EXE-012.002, .010, .011, .012 | `src/us_swing/execution/trade_cycle/__init__.py` | Public surface — re-exports `TradeCycleQuery`, `TradeCycleCommand`, `MonitoringEventBus` re-use, `CycleSnapshot`, all `TradeCycleEvent` classes, `build_default_service(engine, bus, tick_worker) -> tuple[Query, Command]`. Concrete `_service.py` / `_repository.py` NOT re-exported. | `build_default_service(...)`, public types | All internal `_*` modules | No | Approved |
| MD-EXE-012.002.M04 | SRD-EXE-012.010, .011 | `src/us_swing/execution/trade_cycle/_protocols.py` | `TradeCycleQuery` + `TradeCycleCommand` Protocols — CQRS-lite read/write split; `@runtime_checkable` for test doubles. Added during implementation to keep the concrete `_service.py` swappable. | `TradeCycleQuery`, `TradeCycleCommand` | `typing.Protocol`, `_dto` | No | Approved |

### Cross-Module Modifications for FO-EXE-012

| Module ID | File | Change Required | SRD |
|---|---|---|---|
| MD-INF-004.001.M02 | `src/us_swing/db/schema.py` | Import `trade_cycles` Table from `execution/trade_cycle/_schema.py` and register so `create_schema(checkfirst=True)` picks it up on startup. Additive, no migration. | SRD-EXE-012.001 |
| MD-EXE-001.001.M02 | `src/us_swing/execution/execution_engine.py` | Subscribe to `ExitTrigger` events; on receive call `submit_market_sell(symbol, qty, user_id, cycle_id, reason_tag)`. On entry-fill and exit-fill events, call `TradeCycleCommand.on_entry_fill(fill)` / `on_exit_fill(fill)` respectively. | SRD-EXE-012.003, .006, .007 |
| MD-EXE-008.001.M01 | `src/us_swing/execution/live_tick_worker.py` | `TradeCycleService` calls `LiveTickWorker.set_contracts(...)` on cycle open/close to add/remove the symbol. No code change to `LiveTickWorker`; pattern matches existing FO-GUI-012 reconciliation. | SRD-EXE-012.005 |

---

## File Tree for FO-EXE-011 + FO-EXE-012

```
us_swing/src/us_swing/execution/
├── strategy_engine/
│   ├── __init__.py                       # MD-EXE-011.001.M07
│   ├── _engine.py                        # MD-EXE-011.001.M01
│   ├── _context.py                       # MD-EXE-011.001.M02
│   ├── _evaluator.py                     # MD-EXE-011.001.M03
│   ├── _router.py                        # MD-EXE-011.001.M04
│   ├── _events.py                        # MD-EXE-011.001.M05
│   └── _signals.py                       # MD-EXE-011.001.M06
├── trade_cycle/
│   ├── __init__.py                       # MD-EXE-012.002.M03
│   ├── _schema.py                        # MD-EXE-012.001.M01
│   ├── _dto.py                           # MD-EXE-012.001.M02
│   ├── _events.py                        # MD-EXE-012.001.M03
│   ├── _protocols.py                     # MD-EXE-012.002.M04
│   ├── _repository.py                    # MD-EXE-012.002.M01
│   └── _service.py                       # MD-EXE-012.002.M02
└── pending_signal_store.py               # NEW (MD-EXE-011 cross-cut)
```
