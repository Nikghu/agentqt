# Module Decomposition — Infrastructure (INF)

**Document ID:** MD-INF
**Version:** 1.4.0
**Traces To:** SRD-INF v1.9.0 / DD-INF v1.3.0
**Status:** Draft
**Last Updated:** 2026-07-10
**Project:** US Swing Trading System

> v1.2.0: MD-INF-010.001.M01–M07 added — Telegram Notification Service (`core/notifications/`).
> v1.3.0: MD-INF-010.001.M08–M09 added — app wiring (keychain token store + notification worker thread).
> v1.4.0: M04 now enforces per-event toggles (adds SRD-INF-010.006); M09 extended with AppService per-event config mapping + guarded day-end trigger.

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
| MD-INF-004.001.M01 | SRD-INF-004.001–006 | `src/us_swing/db/manager.py` | `DatabaseManager` — all CRUD operations, backend-agnostic repository | `insert_bars()`, `fetch_bars()`, `get_last_timestamp()`, `upsert_universe()`, `fetch_universe()`, `upsert_watchlist()`, `fetch_watchlist()`, `insert_trade()`, `update_trade_exit()`, `upsert_position()`, `delete_position()`, `fetch_open_positions()` | `db/schema.py`, `models.py`, `sqlalchemy` | No | Approved |
| MD-INF-004.001.M02 | SRD-INF-004.001–002 | `src/us_swing/db/schema.py` | SQLAlchemy ORM model definitions + `create_schema()` / `drop_schema()` | `create_schema(engine)`, `drop_schema(engine)`, ORM classes: `UniverseORM`, `Price1mORM`, `Price1dORM`, `Price1wORM`, `WatchlistORM`, `TradeORM`, `PositionORM` | `sqlalchemy` | No | Approved |
| MD-INF-004.001.M03 | SRD-INF-001.001 | `src/us_swing/data/models.py` | Shared dataclasses: `OHLCVBar`, `UniverseRecord`, `TradeRecord`, `PositionRecord`, `AccountState`, `IBKRPosition`, `IBKRFill`, `ConnectionStatus` enum | All dataclasses (pure data, no logic) | `dataclasses`, `datetime` | No | Approved |
| MD-INF-005.001.M01 | SRD-INF-005.001–002 | `src/us_swing/monitoring/logging_setup.py` | Configure rotating file handler, stream handler, set root log level from env, install `sys.excepthook` | `configure_logging(log_dir: Path, level: str)` | `logging`, `pathlib` | No | Draft |
| MD-INF-005.001.M02 | SRD-INF-005.003 | `src/us_swing/monitoring/alerts.py` | `AlertDispatcher` + `AlertHandler(logging.Handler)` — console, file, webhook outputs | `AlertDispatcher.send(level, msg)` | `logging`, `requests` (optional) | No | Draft |
| MD-INF-005.001.M03 | SRD-INF-005.004 | `src/us_swing/monitoring/health.py` | `HealthCheck.report()` — returns dict with broker/DB/universe status | `report() -> dict` | `broker/client.py`, `db/manager.py` | No | Draft |
| MD-INF-001.001.M03 | SRD-INF-001.001 | `src/us_swing/config/settings.py` | All config dataclasses: `BrokerConfig`, `DataConfig`, `UniverseConfig`, `RiskConfig`, `LiveConfig`, `LogConfig`. Load from env vars or TOML file. | `load_config() -> AppConfig` | `dataclasses`, `os`, `tomllib` (3.11+) | No | Approved |
| MD-INF-006.001.M01 | SRD-INF-006.001–007 | `src/us_swing/user/manager.py` | `UserManager` — CRUD for user profiles, mode switching, settings parsing | `create_user()`, `get_user()`, `update_user()`, `delete_user()`, `list_users()`, `switch_mode()` | `db/manager.py`, `data/models.py`, `config/settings.py` | No | Approved |
| MD-INF-007.001.M01 | SRD-INF-007.001–002 | `src/us_swing/data/providers/ibkr_provider.py` | `IBKRProvider` — production data provider delegating to `IBKRClient` | `req_historical_data()`, `subscribe_realtime_bars()`, `unsubscribe_realtime_bars()`, `on_realtime_bar()` | `broker/client.py`, `data/models.py` | No | Approved |
| MD-INF-007.001.M02 | SRD-INF-007.003, 005 | `src/us_swing/data/providers/dummy_provider.py` | `DummyProvider` — synthetic data provider for dev/test; random-walk OHLCV generation | `req_historical_data()`, `subscribe_realtime_bars()`, `unsubscribe_realtime_bars()`, `on_realtime_bar()` | `data/models.py`, `random`, `asyncio` | No | Approved |
| MD-INF-010.001.M01 | SRD-INF-010.001 | `src/us_swing/core/notifications/_events.py` | Frozen `NotificationEvent` variants (`ToolStartedEvent`, `ScreenerApprovedEvent`, `DayEndPnLEvent`) + in-process `_InProcessBus` | event classes, `_InProcessBus.subscribe()`, `_InProcessBus.publish()` | `dataclasses`, `_protocols.py` | No | Approved |
| MD-INF-010.001.M02 | SRD-INF-010.002 | `src/us_swing/core/notifications/_protocols.py` | `NotificationChannel`, `NotificationBus` Protocols | Protocol definitions | `typing` | No | Approved |
| MD-INF-010.001.M03 | SRD-INF-010.003 | `src/us_swing/core/notifications/_telegram.py` | `TelegramChannel` — delivers via Telegram Bot API over HTTP | `send(message)` async | `httpx`, `_dto.py`, `_protocols.py` | No | Approved |
| MD-INF-010.001.M04 | SRD-INF-010.004, .006, .007 | `src/us_swing/core/notifications/_dispatcher.py` | `NotificationDispatcher` — subscribe, render, queue, per-chat rate limit, bounded retry, per-channel isolation; drops events whose kind is toggled off (`event_toggles`) | `dispatch(event)`, `run()` async, `deliver(message)` async | `asyncio`, `_formatters.py`, `_protocols.py` | No | Implemented |
| MD-INF-010.001.M05 | SRD-INF-010.005 | `src/us_swing/core/notifications/_formatters.py` | `FormatterRegistry` — event type → message formatter; default registrations | `register()`, `render()`, `default_registry()` | `_events.py`, `_dto.py` | No | Approved |
| MD-INF-010.001.M06 | SRD-INF-010.006 | `src/us_swing/core/notifications/_dto.py` | `NotificationMessage`, `NotificationConfig` frozen DTOs + `load_config()` | dataclasses, `load_config(settings_json)` | `dataclasses` | No | Approved |
| MD-INF-010.001.M07 | SRD-INF-010.008 | `src/us_swing/core/notifications/__init__.py` | Public surface + `build_default_dispatcher()` factory wiring bus + channels from config | `build_default_dispatcher()`, event classes, Protocols | all package modules | No | Approved |
| MD-INF-010.001.M08 | SRD-INF-010.011 | `src/us_swing/gui/telegram_token_store.py` | Per-user Telegram bot token in the OS keychain | `save(user_id, token)`, `load(user_id)` | `keyring` | No | Implemented |
| MD-INF-010.001.M09 | SRD-INF-010.004, .010 | `src/us_swing/gui/notification_worker.py`, `src/us_swing/gui/app_service.py` | `NotificationWorker(QThread)` hosts the async dispatcher + httpx + inbound poller; `AppService` emit points map per-user toggles into config and fire the guarded once-per-day day-end summary at market close (`_maybe_publish_day_end`) | `publish_event(event)`, `shutdown()`, `ready` signal, `_maybe_publish_day_end(today)` | `PyQt6`, `httpx`, `core/notifications` | No | Implemented |
| MD-INF-010.001.M10 | SRD-INF-010.012, .013, .014 | `src/us_swing/core/notifications/_inbound.py` | `TelegramPoller` (getUpdates long-poll + chat authorization) and `CommandRouter` (parse, dispatch table for 7 read-only commands, unknown-command hint) | `TelegramPoller.run()` async, `CommandRouter.route(text)` | `httpx`, `_protocols.py` | No | Implemented |
| MD-INF-010.001.M11 | SRD-INF-010.015 | `src/us_swing/gui/telegram_commands.py` | `TelegramCommandBridge(QObject)` — `CommandPort` adapter marshalling each query onto the GUI thread; formats `AppService` reads into reply text | `status()`, `pnl()`, `positions()`, `signals()`, `screener()`, `cycles()` | `PyQt6`, `gui/app_service.py` | No | Implemented |

> Cross-tool wiring (not new MD rows — edits to existing modules): `gui/app_service.py` builds the worker + command bridge, publishes the three events, and exposes `reconfigure/send_test/shutdown_notifications`; `gui/settings_panel.py` adds the Telegram settings section; `gui/user_store.py` + `data/models.py` round-trip `telegram_enabled`/`telegram_chat_id`. Inbound support also extends `_protocols.py` (M02: `CommandPort`) and `__init__.py` (M07: `build_command_poller`) and `notification_worker.py` (M09: hosts the poller).

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

core/notifications/_protocols.py  ← typing
core/notifications/_dto.py        ← dataclasses
core/notifications/_events.py     ← _protocols.py
core/notifications/_formatters.py ← _events.py, _dto.py
core/notifications/_telegram.py   ← httpx, _dto.py, _protocols.py
core/notifications/_dispatcher.py ← _formatters.py, _protocols.py, asyncio
core/notifications/__init__.py    ← all core/notifications submodules
```
