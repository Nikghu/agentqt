# Module Decomposition — Infrastructure (INF)

**Document ID:** MD-INF
**Version:** 1.1.0
**Traces To:** SRD-INF v1.1.0 / DD-INF v1.1.0
**Status:** Draft
**Last Updated:** 2026-03-06
**Project:** US Swing Trading System

---

## Compact Format

| Column | Meaning |
|---|---|
| MCP | Exposed as MCP tool (Yes/No) |
| Deps | Internal module dependencies |

---

## INF Modules

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP | Status |
|---|---|---|---|---|---|---|---|
| MD-INF-001.001.M01 | SRD-INF-001.001–005 | `src/us_swing/broker/client.py` | `IBKRClient` — connect, disconnect, reconnect, pacing, realtime bars, orders, account | `connect()`, `disconnect()`, `is_connected()`, `req_historical_data()`, `subscribe_realtime_bars()`, `place_order()`, `cancel_all_orders()`, `close_all_positions()`, `get_account_summary()`, `get_open_positions()` | `ib_insync`, `pacing.py`, `models.py`, `config/settings.py` | No | Approved |
| MD-INF-001.001.M02 | SRD-INF-001.005 | `src/us_swing/broker/pacing.py` | `PacingQueue` — asyncio token-bucket enforcing ≤ 50 IBKR historical requests per 600 s | `acquire()` async, `release_expired()` | `asyncio` | No | Approved |
| MD-INF-002.001.M01 | SRD-INF-002.001–004 | `src/us_swing/universe/manager.py` | `UniverseManager` — load, refresh, schedule auto-refresh | `load_universe()`, `refresh_universe()`, `schedule_refresh()` | `db/manager.py`, `models.py`, `pandas`, `config/settings.py` | No | Draft |
| MD-INF-003.001.M01 | SRD-INF-003.001–005 | `src/us_swing/data/engine.py` | `HistoricalDataEngine` — bootstrap, incremental update, timeframe aggregation | `bootstrap_symbol()`, `bootstrap_all()`, `update_missing_data()`, `aggregate_timeframe()` | `broker/client.py`, `db/manager.py`, `models.py`, `asyncio` | No | Approved |
| MD-INF-004.001.M01 | SRD-INF-004.001–006 | `src/us_swing/db/manager.py` | `DatabaseManager` — all CRUD operations, backend-agnostic repository | `insert_bars()`, `fetch_bars()`, `get_last_timestamp()`, `upsert_universe()`, `fetch_universe()`, `insert_trade()`, `update_trade_exit()`, `upsert_position()`, `delete_position()`, `fetch_open_positions()` | `db/schema.py`, `models.py`, `sqlalchemy` | No | Approved |
| MD-INF-004.001.M02 | SRD-INF-004.001–002 | `src/us_swing/db/schema.py` | SQLAlchemy ORM model definitions + `create_schema()` / `drop_schema()` | `create_schema(engine)`, `drop_schema(engine)`, ORM classes: `UniverseORM`, `Price1mORM`, `Price1dORM`, `Price1wORM`, `TradeORM` | `sqlalchemy` | No | Approved |
| MD-INF-004.001.M03 | SRD-INF-001.001 | `src/us_swing/data/models.py` | Shared dataclasses: `OHLCVBar`, `UniverseRecord`, `TradeRecord`, `PositionRecord`, `AccountState`, `IBKRPosition`, `IBKRFill`, `ConnectionStatus` enum | All dataclasses (pure data, no logic) | `dataclasses`, `datetime` | No | Approved |
| MD-INF-005.001.M01 | SRD-INF-005.001–002 | `src/us_swing/monitoring/logging_setup.py` | Configure rotating file handler, stream handler, set root log level from env, install `sys.excepthook` | `configure_logging(log_dir: Path, level: str)` | `logging`, `pathlib` | No | Draft |
| MD-INF-005.001.M02 | SRD-INF-005.003 | `src/us_swing/monitoring/alerts.py` | `AlertDispatcher` + `AlertHandler(logging.Handler)` — console, file, webhook outputs | `AlertDispatcher.send(level, msg)` | `logging`, `requests` (optional) | No | Draft |
| MD-INF-005.001.M03 | SRD-INF-005.004 | `src/us_swing/monitoring/health.py` | `HealthCheck.report()` — returns dict with broker/DB/universe status | `report() -> dict` | `broker/client.py`, `db/manager.py` | No | Draft |
| MD-INF-001.001.M03 | SRD-INF-001.001 | `src/us_swing/config/settings.py` | All config dataclasses: `BrokerConfig`, `DataConfig`, `UniverseConfig`, `RiskConfig`, `LiveConfig`, `LogConfig`. Load from env vars or TOML file. | `load_config() -> AppConfig` | `dataclasses`, `os`, `tomllib` (3.11+) | No | Approved |
| MD-INF-006.001.M01 | SRD-INF-006.001–007 | `src/us_swing/user/manager.py` | `UserManager` — CRUD for user profiles, mode switching, settings parsing | `create_user()`, `get_user()`, `update_user()`, `delete_user()`, `list_users()`, `switch_mode()` | `db/manager.py`, `data/models.py`, `config/settings.py` | No | Approved |
| MD-INF-007.001.M01 | SRD-INF-007.001–002 | `src/us_swing/data/providers/ibkr_provider.py` | `IBKRProvider` — production data provider delegating to `IBKRClient` | `req_historical_data()`, `subscribe_realtime_bars()`, `unsubscribe_realtime_bars()`, `on_realtime_bar()` | `broker/client.py`, `data/models.py` | No | Approved |
| MD-INF-007.001.M02 | SRD-INF-007.003, 005 | `src/us_swing/data/providers/dummy_provider.py` | `DummyProvider` — synthetic data provider for dev/test; random-walk OHLCV generation | `req_historical_data()`, `subscribe_realtime_bars()`, `unsubscribe_realtime_bars()`, `on_realtime_bar()` | `data/models.py`, `random`, `asyncio` | No | Approved |

---

## Module Dependency Graph

```
config/settings.py         ← no internal deps
data/models.py             ← no internal deps


broker/pacing.py           ← asyncio
broker/client.py           ← pacing.py, models.py, config/settings.py

db/schema.py               ← sqlalchemy
db/manager.py              ← schema.py, models.py, sqlalchemy

universe/manager.py        ← db/manager.py, models.py, config/settings.py
user/manager.py            ← db/manager.py, models.py, config/settings.py

data/providers/ibkr_provider.py  ← broker/client.py, models.py
data/providers/dummy_provider.py ← models.py, random, asyncio
data/engine.py             ← data/providers (DataProvider), db/manager.py, models.py

monitoring/logging_setup.py ← logging
monitoring/alerts.py        ← logging, requests
monitoring/health.py        ← broker/client.py, db/manager.py
```
