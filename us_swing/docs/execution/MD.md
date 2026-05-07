# Module Decomposition — Execution & Risk Management (EXE)

**Document ID:** MD-EXE
**Version:** 1.3.0
**Traces To:** SRD-EXE v1.3.0 / DD-EXE v1.3.0
**Status:** Draft
**Last Updated:** 2026-05-06
**Project:** US Swing Trading System

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
| MD-EXE-007.001.M01 | SRD-EXE-007.002–008 | `src/us_swing/execution/live_candle_aggregator.py` | `LiveCandleAggregator(QThread)` — subscribes to IBKR 5-second real-time bars, accumulates them into per-symbol `PartialBar` accumulators, closes each 3m window on wall-clock boundary, persists completed bars to `price_3m` via `DatabaseManager`, emits `candle_updated` and `candle_closed` signals. RTH guard (09:30–16:00 ET). `PartialBar` dataclass defined here. | `set_symbols(symbols: list[str]) -> None`, `on_disconnect() -> None`, `on_reconnect(symbols: list[str]) -> None`; signals: `candle_updated(str, object)`, `candle_closed(str, object)` | `broker/client.py` (IBKRClient), `db/manager.py` (DatabaseManager), `data/models.py` (RealtimeBar, OHLCVBar), `zoneinfo`, `threading.Lock`, `PyQt6.QtCore.QThread`, `PyQt6.QtCore.QTimer` | No | Draft |

---

## Cross-Tool Modifications for FO-EXE-007

These existing modules in other tools require targeted changes to support Phase 2. They are not new EXE modules but must be updated as part of the FO-EXE-007 implementation.

| Module ID | File | Change Required | SRD |
|---|---|---|---|
| MD-INF-004.001.M02 | `src/us_swing/db/schema.py` | Add `price_3m` SQLAlchemy table, `idx_price_3m_sym_dt` index, and `PRICE_TABLES["3m"]` entry. Additive — `create_schema(checkfirst=True)` handles existing databases with no migration. | SRD-EXE-007.001 |
| MD-EXE-006.001.M01 | `src/us_swing/execution/intraday_candle_loader.py` | Update `get_readiness_report()`: replace the time-windowed `COUNT(*) FROM price_1m` query for `candles_3m` with `COUNT(*) FROM price_3m WHERE symbol = :sym` (no cutoff; every row is a completed bar). `candles_5m` and `candles_1h` queries are unchanged. | SRD-EXE-007.009 |

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
execution/live_candle_aggregator.py  ← broker/client.py, db/manager.py, data/models.py,
                                        zoneinfo, threading, PyQt6.QtCore
```

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
└── execution/
    ├── risk_manager.py                # MD-EXE-001.001.M01
    ├── execution_engine.py            # MD-EXE-001.001.M02
    ├── position_tracker.py            # MD-EXE-002.001.M01
    ├── circuit_breaker.py             # MD-EXE-003.001.M01
    ├── emergency.py                   # MD-EXE-003.001.M02
    ├── paper_engine.py                # MD-EXE-004.001.M01
    ├── execution_router.py            # MD-EXE-004.001.M02
    ├── intraday_candle_loader.py      # MD-EXE-006.001.M01
    └── live_candle_aggregator.py      # MD-EXE-007.001.M01
```
