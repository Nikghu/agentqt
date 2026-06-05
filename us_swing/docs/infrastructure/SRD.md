# Software Requirement Document — Infrastructure (INF)

**Document ID:** SRD-INF
**Version:** 1.5.0
**Traces To:** FO-INF v1.4.0
**Status:** Draft
**Last Updated:** 2026-06-04
**Project:** US Swing Trading System

> v1.5.0: Section 9 added — SRD-INF-009.001–.006 (Pluggable Broker Abstraction; Broker_fix.md Phases 1/3/4).

---

## Compact Format Key

| Column | Meaning |
|---|---|
| P | Priority: **Must** / Should / Could |
| Status | Draft / Approved / Implemented / Verified / Reopen |
| In | Primary inputs |
| Out | Primary outputs / side-effects |

---

## Section 1: Requirements for FO-INF-001 — IBKR Broker Gateway Connection Management

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-INF-001.001 | FO-INF-001 | Must | Establish TCP connection to IBKR TWS/Gateway using `ib_insync`. Expose `IBKRClient` class wrapping the `IB` instance. | host, port, clientId from config | connected `IB` instance | Connection must complete within 5 s configurable timeout | Approved |
| SRD-INF-001.002 | FO-INF-001 | Must | Validate connection by requesting account summary after connect. Raise `BrokerConnectionError` (custom exception from `exceptions.py`) if validation fails — not built-in `ConnectionError`. | connected `IB` instance | validation flag True/False | Must not proceed to data operations if validation fails | Approved |

> **Discrepancy fixed (2026-03-15):** Original text used built-in `ConnectionError`; corrected to project-specific `BrokerConnectionError`. Set to Draft for re-review.
| SRD-INF-001.003 | FO-INF-001 | Must | Auto-reconnect on disconnect. Use exponential backoff starting at 2 s, doubling up to 60 s max, for configurable max retry count (default 10). | disconnect event | reconnected state or shutdown signal | Backoff delays must not block the broker event loop (use asyncio sleep) | Approved |
| SRD-INF-001.004 | FO-INF-001 | Must | Expose `connection_status` observable (asyncio Event or callback list). Signal state changes: CONNECTED, DISCONNECTED, RECONNECTING. | state change | notified subscribers | Thread-safe; must work with both asyncio and QThread consumers | Approved |
| SRD-INF-001.005 | FO-INF-001 | Must | Implement request pacing queue that enforces ≤ 50 historical data requests per 10-minute rolling window. Queue excess requests and release when window allows. | list of pending requests | ordered, paced request dispatch | Must never raise IBKR error 162; pacing state must survive reconnect | Approved |
| SRD-INF-001.006 | FO-INF-001 | Must | `SystemConfig` has `ibkr_system_client_id: int` (default 0). The system IBKR connection (market data, account polling) uses this clientId exclusively. Validation on startup: `ibkr_system_client_id` must not equal any `UserProfile.ibkr_client_id`; raise `ConfigurationError` if clash detected. | `SystemConfig` | validated system clientId | Same TWS instance may host both system and user connections; clientIds must be unique per TWS | Approved |

---

## Section 2: Requirements for FO-INF-002 — S&P 500 Universe Management

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-INF-002.001 | FO-INF-002 | Must | `UniverseManager.load_universe()` queries the `universe` table from the database and returns a list of `UniverseRecord(symbol, name, sector)` dataclasses. | database connection | `list[UniverseRecord]` | Must complete within 2 s; returns empty list (not error) if table is empty | Approved |
| SRD-INF-002.002 | FO-INF-002 | Must | `UniverseManager.refresh_universe()` downloads the current S&P 500 constituent list from a configurable source (default: Wikipedia S&P 500 page via `pandas.read_html`) and upserts records into the `universe` table. | HTTP source URL | updated `universe` table; count of added/removed symbols logged | Must not truncate existing records — use upsert (insert-or-update by symbol) | Approved |
| SRD-INF-002.003 | FO-INF-002 | Should | Schedule `refresh_universe()` automatically every 7 days using an asyncio `PeriodicTask`. Configurable interval; disable with `refresh_interval_days = 0`. | config `refresh_interval_days` | periodic execution | Must log execution start/end and any errors without crashing the main loop | Approved |
| SRD-INF-002.004 | FO-INF-002 | Must | Each `UniverseRecord` must have non-null `symbol` (string, 1–5 uppercase alpha), `name` (string), `sector` (string). Validation must reject malformed records before insert. | raw constituent data | validated records inserted | Invalid records are logged and skipped; do not halt refresh | Approved |
| SRD-INF-002.005 | FO-INF-002 | Must | `UniverseRecord` has 3 additional fields: `candle_start_date: date \| None`, `candle_last_date: date \| None`, `data_status: str` (values: `'missing'` / `'stale'` / `'up_to_date'`; default `'missing'`). Populated by `HistoricalDataEngine` after bootstrap or sync; not modified by `UniverseManager.refresh_universe()`. | universe table row | typed candle fields on `UniverseRecord` | `data_status` must be one of the three defined values; any other value treated as `'missing'` | Approved |
| SRD-INF-002.006 | FO-INF-002 | Must | `SystemConfig` shall expose `benchmark_symbol: str` (default `"SPY"`). This symbol is used by screener RS calculations and fetched/stored separately from universe constituents. Validation: non-empty uppercase string, 1–5 chars. Startup check: `benchmark_symbol` must not be a symbol in the `universe` table; raise `ConfigurationError` if clash detected. | `SystemConfig` | accessible `benchmark_symbol` field | Must not appear in universe constituent list; validated at startup | Draft |

---

## Section 3: Requirements for FO-INF-003 — Historical OHLCV Data Acquisition & Incremental Update

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-INF-003.001 | FO-INF-003 | Must | `HistoricalDataEngine.bootstrap_symbol(symbol)` fetches **5 trading days** of 1m bars and **2 years** of 1d/1w bars for the given symbol via `IBKRClient.req_historical_data()` and stores them in the corresponding price tables. 2 years of 1d/1w history is required for reliable screener indicator baselines (ATR, RSI, BB). | symbol str, `IBKRClient`, `DatabaseManager` | populated `price_1m`, `price_1d`, `price_1w` rows | Must use pacing queue; must not duplicate bars if called again after partial completion | Approved |
| SRD-INF-003.002 | FO-INF-003 | Must | `HistoricalDataEngine.update_missing_data(symbol)` calls `DatabaseManager.get_last_timestamp(symbol, timeframe)` for 1m, 1d, 1w, then fetches only bars after each last timestamp. | symbol, `DatabaseManager`, `IBKRClient` | newly appended bars; 0 bars inserted if already up to date | Must handle case where no data exists (falls back to bootstrap) | Approved |
| SRD-INF-003.003 | FO-INF-003 | Must | `HistoricalDataEngine.aggregate_timeframe(symbol, target_tf, source_tf='1m')` synthesises target-TF bars from stored 1m bars using OHLCV aggregation: open=first, high=max, low=min, close=last, volume=sum. Supported targets: 3m, 5m, 15m, 1h, 4h. | symbol, target timeframe, date range | `list[OHLCVBar]` | Aggregation is always done in-process; never call IBKR API for derived timeframes | Approved |
| SRD-INF-003.004 | FO-INF-003 | Must | Candle consistency guarantee: a live-built candle for timestamp T must equal the stored historical bar for the same symbol and T. Enforce by using the same aggregation function for both live and historical bars. | live bars, stored bars | verified equality (tested) | Any discrepancy must raise a `CandleConsistencyError` in test mode | Approved |
| SRD-INF-003.005 | FO-INF-003 | Should | `HistoricalDataEngine.bootstrap_all(universe)` bootstraps all symbols in the universe concurrently up to a configurable `max_concurrent` workers (default 5) to respect pacing limits. Logs progress symbol by symbol. | `list[UniverseRecord]`, `max_concurrent` int | fully populated price tables | Must not exceed IBKR pacing limit; failures per symbol are logged but do not halt other symbols | Approved |
| SRD-INF-003.006 | FO-INF-003 | Must | After completing bootstrap or incremental sync for a symbol, `HistoricalDataEngine` updates the `universe` table row: `candle_start_date` = earliest 1d bar date, `candle_last_date` = latest 1d bar date, `data_status` = `'up_to_date'` if `candle_last_date` ≥ last completed trading day (per `MarketCalendar`), else `'stale'`. | completed bar insert | updated `universe` row | Update is atomic with the bar insert (same transaction); `candle_start_date` is set only on first bootstrap, not overwritten on incremental sync | Approved |
| SRD-INF-003.007 | FO-INF-003 | Must | `AppService.sync_candle_data()` calls `HistoricalDataEngine.sync_candles_all(universe)` for 1d and 1w timeframes only (not 1m). Runs in a background `QThread`; emits `candle_sync_updated = pyqtSignal()` on completion; logs per-symbol progress via `AppService.log_message`. On startup, `sync_candle_data()` is called automatically after the universe is loaded. | `AppService` call or app startup | incremental 1d/1w bars appended; `candle_sync_updated` emitted | Respects pacing queue; `max_concurrent` default 5; symbol failures are logged and do not abort the sync of other symbols | Approved |
| SRD-INF-003.008 | FO-INF-003 | Must | `HistoricalDataEngine.bootstrap_benchmark()` fetches **2 years** of 1d and 1w OHLCV bars for `SystemConfig.benchmark_symbol` (default `"SPY"`) via `IBKRClient.req_historical_data()` and stores them in `price_1d` / `price_1w`. Benchmark symbol is **NOT** added to the `universe` table. `AppService.sync_candle_data()` shall call `bootstrap_benchmark()` on first run (no bars exist) or `update_benchmark()` on subsequent runs, after the constituent sync loop completes. | `SystemConfig.benchmark_symbol`, `IBKRClient`, `DatabaseManager` | populated `price_1d` / `price_1w` rows for SPY; identifiable by symbol string alone | Benchmark must not appear in `universe` table; pacing queue applies; failure is logged but does not abort constituent sync | Draft |
| SRD-INF-003.009 | FO-INF-003 | Must | `HistoricalDataEngine.update_benchmark()` calls `DatabaseManager.get_last_timestamp(benchmark_symbol, "1d")` and fetches only bars after the last stored timestamp. Falls back to `bootstrap_benchmark()` if no bars exist. Called by `AppService.sync_candle_data()` after the constituent `update_missing_data()` loop completes. | `SystemConfig.benchmark_symbol`, `DatabaseManager`, `IBKRClient` | newly appended 1d/1w bars for benchmark; 0 inserts if already up to date | Same error handling as SRD-INF-003.002; failure is logged and does not abort other sync operations | Draft |

---

## Section 4: Requirements for FO-INF-004 — Database Storage & Retrieval

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-INF-004.001 | FO-INF-004 | Must | Define SQLAlchemy (or raw SQL) schema for tables: `universe`, `price_1m`, `price_1d`, `price_1w`, `trades`, `users`. Create tables if they do not exist on first run. The `watchlist` table is retired (GUI watchlist is in-memory only — dropped via idempotent `DROP TABLE IF EXISTS`). `trades` must include `user_id` and `mode` columns; `positions` must include `user_id`, `mode`, and `state` columns; `users` must include `user_id`, `username`, `display_name`, `ibkr_client_id`, `settings_json`, `mode`. `universe` must include `candle_start_date DATE DEFAULT NULL`, `candle_last_date DATE DEFAULT NULL`, `data_status TEXT DEFAULT 'missing'` columns. | database URL (from config) | created schema | Schema must be identical between SQLite and PostgreSQL backends | Approved |
| SRD-INF-004.002 | FO-INF-004 | Must | Compound index on `(symbol, datetime)` for all `price_*` tables. Index must be created as part of schema migration. | DDL execution | indexed tables | Query for 1 year of 1d bars for one symbol must complete < 500 ms on dev SQLite | Approved |
| SRD-INF-004.003 | FO-INF-004 | Must | `DatabaseManager.insert_bars(symbol, timeframe, bars)` bulk-inserts a list of `OHLCVBar` records. Uses INSERT OR IGNORE (SQLite) / ON CONFLICT DO NOTHING (PostgreSQL) to prevent duplicates. | symbol, timeframe, `list[OHLCVBar]` | rows committed; duplicate count logged | Write on a dedicated thread; caller does not block | Approved |
| SRD-INF-004.004 | FO-INF-004 | Must | `DatabaseManager.fetch_bars(symbol, timeframe, start, end)` returns `list[OHLCVBar]` for the given range, inclusive. Returns empty list if no data. | symbol, timeframe, start datetime, end datetime | `list[OHLCVBar]` | Must complete < 500 ms for one year of daily bars | Approved |
| SRD-INF-004.005 | FO-INF-004 | Must | `DatabaseManager.get_last_timestamp(symbol, timeframe)` returns the latest stored datetime or `None` if no data. | symbol, timeframe | `datetime \| None` | Must be accurate — incorrect result causes data gap or duplication in incremental update | Approved |
| SRD-INF-004.006 | FO-INF-004 | Must | Backend selection via `DATABASE_URL` config key: `sqlite:///./data/us_swing.db` (dev default) or `postgresql://...` (prod). No code change required to switch backends. | config `DATABASE_URL` | correctly initialised session factory | Must validate URL scheme on startup and raise `ConfigurationError` for unsupported backends | Approved |

---

## Section 5: Requirements for FO-INF-005 — Logging, Error Recovery & Monitoring

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-INF-005.001 | FO-INF-005 | Must | Configure Python `logging` with a custom daily file handler (`_DailyDateHandler`): one file per calendar day, named `~/.usswing/logs/us_swing_YYYY-MM-DD.log`. At local midnight the handler opens a new dated file without renaming the old one. Default level INFO; override via `LOG_LEVEL` env var. Retain last 30 files (configurable); delete oldest beyond limit. `configure_logging()` must be called once in `__main__.main()` before any other module initialises. | startup config | configured root logger; new file each day | All modules must obtain their logger via `logging.getLogger(__name__)` — no `print()` | Implemented |
| SRD-INF-005.002 | FO-INF-005 | Must | Install a global `sys.excepthook` that logs all uncaught exceptions at CRITICAL level with full traceback, then triggers the alert system before allowing normal Python exit. | uncaught exception | CRITICAL log entry + alert | Must not swallow exceptions or prevent normal exit code propagation | Approved |
| SRD-INF-005.003 | FO-INF-005 | Must | Implement alert dispatcher supporting: console (always on), file-append to `logs/alerts.log`, and optional webhook POST (configurable URL). Emit on WARNING or above via a `LoggingHandler` subclass. | log record ≥ WARNING | dispatched alert to configured outputs | Webhook failures must not crash the logger; retry once, then log warning | Approved |
| SRD-INF-005.004 | FO-INF-005 | Must | `HealthCheck.report()` returns a dict: `{broker_connected: bool, last_update: datetime, universe_count: int, open_positions: int, db_reachable: bool}`. Expose as CLI command `python -m us_swing health`. | system state | JSON-serialisable dict printed to stdout | Must complete within 2 s even under load | Approved |
| SRD-INF-005.005 | FO-INF-005 | Must | On broker disconnect persisting > configurable `max_disconnect_minutes` (default 5), the system calls `EmergencyShutdown.run()`: cancel pending orders, close all positions, log CRITICAL, shut down event loop cleanly. | disconnect duration | clean shutdown with CRITICAL log | Must complete within 60 s; any IBKR API error during shutdown is logged but not re-raised | Approved |

---

## Section 6: Requirements for FO-INF-006 — Multi-User Profile Management

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-INF-006.001 | FO-INF-006 | Must | `UserManager.create_user(username, display_name, ibkr_client_id, mode='paper')` creates a new user record in the `users` table with default settings. Returns `UserProfile` dataclass. | username, display_name, ibkr_client_id | `UserProfile` inserted into DB | `username` must be unique; `ibkr_client_id` must be unique; raise `DuplicateUserError` on conflict | Approved |
| SRD-INF-006.002 | FO-INF-006 | Must | `UserManager.get_user(user_id)` retrieves a user profile from the `users` table. Returns `UserProfile` or raises `UserNotFoundError`. | `user_id` | `UserProfile` | Must parse `settings_json` into typed config objects (risk, strategy, screener) | Approved |
| SRD-INF-006.003 | FO-INF-006 | Must | `UserManager.update_user(user_id, **kwargs)` updates any subset of user fields (display_name, ibkr_client_id, settings_json, mode). Non-provided fields remain unchanged. | `user_id`, keyword args | updated `users` row | Must validate `mode` is one of 'paper' or 'live'; reject invalid values with `ValueError` | Approved |
| SRD-INF-006.004 | FO-INF-006 | Must | `UserManager.delete_user(user_id)` soft-deletes or removes the user record. Historical `trades` and `positions` rows with that `user_id` are NOT deleted. | `user_id` | user removed from `users` table | Orphan trade/position records retained for audit purposes | Approved |
| SRD-INF-006.005 | FO-INF-006 | Must | `UserManager.list_users()` returns all user profiles from the `users` table as `list[UserProfile]`. | — | `list[UserProfile]` | Returns empty list if no users; does not raise | Approved |
| SRD-INF-006.006 | FO-INF-006 | Must | `UserProfile` dataclass contains: `user_id: int`, `username: str`, `display_name: str`, `ibkr_client_id: int`, `mode: str`, `risk_config: RiskConfig`, `strategy_config: dict`, `screener_config: dict`. | `users` table row | typed dataclass | `settings_json` is parsed at load time; parse errors logged as WARNING with fallback to defaults | Approved |
| SRD-INF-006.008 | FO-INF-006 | Must | `UserProfile` has `is_admin: bool` field. First user created when the `users` table is empty automatically receives `is_admin=True`. All subsequent users default to `is_admin=False`. Field persisted in `settings_json`. | empty users table or explicit param | `is_admin` set on `UserProfile` | `is_admin` is part of `UserProfile` dataclass and serialised in `settings_json` | Draft |
| SRD-INF-006.009 | FO-INF-006 | Must | `UserManager.create_user()` accepts optional `is_admin: bool = False` parameter. When `users` table is empty at call time, `is_admin` is forced to `True` regardless of the passed value. | username, display_name, ibkr_client_id, is_admin | `UserProfile` with correct `is_admin` | Overrides passed `is_admin=False` only on the very first user | Draft |
| SRD-INF-006.010 | FO-INF-006 | Must | `UserManager.delete_user(user_id)` raises `LastAdminError` if the target user is the only user with `is_admin=True`. `UserManager.update_user(user_id, is_admin=False)` raises `LastAdminError` under the same condition. | `user_id` | `LastAdminError` raised | Does not delete or modify any record if error is raised | Draft |
| SRD-INF-006.007 | FO-INF-006 | Should | `UserManager.switch_mode(user_id, new_mode)` changes active mode between 'paper' and 'live'. Must require explicit confirmation token (not just a mode string) when switching to 'live'. In Phase 0 development, `LIVE_MODE_ENABLED=False` in config disables live mode entirely — `switch_mode(user_id, 'live', ...)` raises `LiveModeDisabledError`. | `user_id`, `new_mode`, `confirm_token` | updated mode | Switching to 'live' without valid `confirm_token` raises `ConfirmationRequiredError`; switching when config disables live mode raises `LiveModeDisabledError` | Approved |

---

## Section 7: Requirements for FO-INF-007 — Data Provider Abstraction

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-INF-007.001 | FO-INF-007 | Must | Define `DataProvider` protocol with methods: `req_historical_data(symbol, end_datetime, duration, bar_size) -> list[OHLCVBar]`, `subscribe_realtime_bars(symbol, bar_size)`, `unsubscribe_realtime_bars(symbol)`, `on_realtime_bar(callback)`. | — | protocol definition | Must be a `typing.Protocol` class; concrete implementations provide actual logic | Approved |
| SRD-INF-007.002 | FO-INF-007 | Must | `IBKRProvider` implements `DataProvider` by delegating to `IBKRClient`. All calls pass through to the existing IBKR wrapper. | `IBKRClient` instance | delegated IBKR calls | Must not duplicate pacing logic — `IBKRClient` already handles pacing | Approved |
| SRD-INF-007.003 | FO-INF-007 | Must | `DummyProvider` implements `DataProvider` returning synthetic OHLCV bars: random-walk price series with configurable seed, realistic volume distribution, correct timestamps. | config: seed, base_price, volatility | `list[OHLCVBar]` with valid structure | Bars must pass the same validation as real bars; `open <= high`, `low <= close`, `volume >= 0` | Approved |
| SRD-INF-007.004 | FO-INF-007 | Must | Provider selection via config key `DATA_PROVIDER`. `HistoricalDataEngine` receives a `DataProvider` instance (not `IBKRClient` directly) via dependency injection. | config `DATA_PROVIDER` | correct provider instantiated | Factory function: `create_provider(config) -> DataProvider` | Approved |
| SRD-INF-007.005 | FO-INF-007 | Should | `DummyProvider` supports `subscribe_realtime_bars()` by emitting synthetic 5-second bars on a timer for testing live engine without IBKR. | symbol, bar_size | periodic synthetic bars via callback | Timer interval configurable; default 5 seconds; bars generated from random walk continuation | Approved |

---

## 8. Internet Connectivity Monitoring (FO-INF-008)

| ID | Parent | Priority | Requirement | Input | Output | Constraint | Status |
|----|--------|----------|-------------|-------|--------|------------|--------|
| SRD-INF-008.001 | FO-INF-008 | Must | `NetWatcher(QObject)` probes `8.8.8.8:53` (Google Public DNS) via TCP every 15 s (configurable via `PROBE_INTERVAL_MS`) inside a background `QThread` (`_ProbeWorker`). Emits `status_changed(bool)` **only when reachability flips** (True = online, False = offline). Module: `us_swing/monitoring/connectivity.py`. | initial state unknown | `status_changed` signal on each state flip | Probe timeout = 3 s; skip tick if previous probe still running; never block GUI thread | Implemented |
| SRD-INF-008.002 | FO-INF-008 | Must | `AppService` instantiates `NetWatcher` and exposes `internet_status_changed = pyqtSignal(bool)` for GUI consumers. `is_internet_online() -> bool` returns last-known state synchronously. | `NetWatcher.status_changed` | `AppService.internet_status_changed` emitted | Watcher started on `AppService.__init__`; first probe fires within 15 s (immediately via `start()`) | Implemented |
| SRD-INF-008.003 | FO-INF-008 | Must | When internet drops (`status_changed(False)`): emit `log_message("WARNING", "[Network] ⚠  Internet connection lost — market data paused.")` to the GUI Live Log panel. Record whether the IBKR feed was active at the time (`_was_feed_connected`). | connectivity drop event | WARNING in Live Log | Message must appear in the Live Log within one probe cycle | Implemented |
| SRD-INF-008.004 | FO-INF-008 | Must | When internet is restored (`status_changed(True)`): emit `log_message("INFO", "[Network] Internet connectivity restored.")`. If `_was_feed_connected` is True and feed is currently disconnected, automatically call `connect_feed()` and log `"[Network] Reconnecting data feed automatically…"`. | connectivity restore event | INFO in Live Log + optional auto-reconnect | Auto-reconnect must not trigger if user had manually disconnected before the outage | Implemented |
| SRD-INF-008.005 | FO-INF-008 | Must | Main window status bar leftmost pill shows internet status: `⬤  Internet: Online` (green, `C.GREEN`) when reachable; `⬤  Internet: Offline` (red, `C.RED`) when unreachable; `⬤  Internet: Checking…` (muted) until first probe completes. Updated via `svc.internet_status_changed` signal. | `internet_status_changed(bool)` | status bar pill colour + text | Replaces the former IBKR feed connection pill | Implemented |

---

## Section 9: Requirements for FO-INF-009 — Pluggable Broker Abstraction

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-INF-009.001 | FO-INF-009 | Must | Universal `Broker` ABC in `broker/broker.py` exposes `place_order(OrderRequest) -> str` (acceptance only) and `cancel_order(broker_order_id)`; provides `on_event(callback)` registration and `_emit(OrderEvent)` dispatch for asynchronous fill reporting. | `OrderRequest` | broker order id + later `OrderEvent`s | Module imports nothing from `us_swing.execution.*`; `place_order` returns before any fill event is emitted | Implemented |
| SRD-INF-009.002 | FO-INF-009 | Must | Neutral frozen DTOs: `OrderRequest(client_ref, symbol, side, quantity, order_type, limit_price)` and `OrderEvent(broker_order_id, client_ref, status, filled_quantity, fill_price, reason)`. `client_ref` is echoed unchanged on every event so the adapter matches fills to the originating order. | caller fields | `@dataclass(frozen, slots)` containers | Each DTO carries `schema_version: int`; `limit_price` required only when `order_type=LIMIT`; `OrderRequest.reference_price` is an advisory price simulated brokers fill at | Implemented |
| SRD-INF-009.003 | FO-INF-009 | Must | Broker-native enums `OrderSide` (BUY/SELL), `OrderType` (MARKET/LIMIT), `OrderStatus` (NEW/PARTIAL_FILLED/FILLED/REJECTED/CANCELLED). `OrderStatus` values mirror `ExecutionEnums.BuyOrderState`/`SellOrderState` exactly. | — | `StrEnum` definitions | Values must stay string-identical to the execution enums so the adapter maps 1:1 with no lookup table | Implemented |
| SRD-INF-009.004 | FO-INF-009 | Must | `SimBroker` (`broker/sim.py`) implements `Broker` with an internal order book and a configurable fill model (price source, latency, partial fills). Emits lifecycle `OrderEvent`s asynchronously — never a synchronous fill inside `place_order`. | `OrderRequest` | async `OrderEvent` stream | Must support injecting `REJECTED` / `PARTIAL_FILLED` / `CANCELLED` for functionality testing; order ids unique across app restarts | Implemented |
| SRD-INF-009.005 | FO-INF-009 | Must | `IBKRBroker` (`broker/ibkr.py`) implements `Broker` over an `OrderGateway` seam; maps IBKR order statuses (`Filled`/`Submitted`+partial/`Inactive`/`Cancelled`) onto `OrderStatus` and emits `OrderEvent`s. Live binding `IBKRClientGateway` wraps `IBKRClient` (added `ib` accessor) and builds ib_insync orders. | `OrderRequest` | async `OrderEvent` stream | Status mapping unit-tested via a fake gateway; `IBKRClientGateway` is live-only (`# pragma: no cover`), reuses `IBKRClient` transport | Implemented |
| SRD-INF-009.006 | FO-INF-009 | Must | A single broker contract-test suite runs identical `OrderRequest` scenarios against both brokers and asserts identical `OrderEvent` sequences (states, filled quantities, terminal status). | `OrderRequest` scenarios | pass/fail per broker | Both `SimBroker` and `IBKRBroker` must pass the same suite to be declared interchangeable. Suite `tests/broker/test_broker_contract.py` parametrized over `BROKER_FACTORIES`; both brokers pass the shared fixture scenarios plus per-broker mapping cases — 16 cases green | Implemented |

