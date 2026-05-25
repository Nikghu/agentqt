# Functional Objectives — Infrastructure (INF)

**Document ID:** FO-INF
**Version:** 1.3.0
**Status:** Draft
**Last Updated:** 2026-03-17
**Project:** US Swing Trading System

> Traces to: `us_swing/requirements.md` §2, §4, §5, §6, §7, §11, §12, §13, §22, §24, §26
> v1.3.0 changes: FO-INF-002 candle metadata; FO-INF-003 history extended to 2 years + candle sync.

---

## FO-INF-001: IBKR Broker Gateway Connection Management
- **Status:** Approved

- The system shall establish and maintain a connection to the Interactive Brokers (IBKR) TWS/Gateway API using the `ib_insync` library.
- The system shall validate the API connection on startup and abort the startup sequence if the connection cannot be established within a configurable timeout.
- The system shall implement automatic reconnection on unexpected disconnection, using exponential backoff with a configurable maximum retry count.
- The system shall expose connection status (connected / disconnected / reconnecting) to all dependent subsystems via an observable event interface.
- The system shall respect IBKR API pacing limits by throttling historical data requests (maximum 50 requests per 10 minutes per session).
- The system shall use a dedicated **system IBKR clientId** (`ibkr_system_client_id` from `SystemConfig`) for its market data and account polling connection. Each user's trading connection uses the user's own `ibkr_client_id`. Both connect to the same TWS/Gateway instance; `ibkr_system_client_id` must not equal any user's `ibkr_client_id`.
- **Acceptance Criteria:**
  - Given a running IBKR Gateway on the configured host/port, the system connects within 5 seconds.
  - Given a disconnection event, the system automatically reconnects and notifies all subscribers within 30 seconds.
  - Given 60 historical data requests sent in rapid succession, the system queues and paces them without triggering IBKR error code 162 (pacing violation).

---

## FO-INF-002: S&P 500 Universe Management
- **Status:** Approved

- The system shall maintain a list of all S&P 500 constituent symbols (approximately 500 stocks) persisted in the database.
- The system shall load the universe from the database at application startup.
- The universe shall be refreshable on demand or automatically on a weekly schedule to reflect index constituent changes.
- The universe record shall include symbol, company name, and GICS sector.
- Each universe record shall track candle data readiness: `candle_start_date`, `candle_last_date`, and `data_status` (`missing` / `stale` / `up_to_date`). These are populated by the historical data engine after bootstrap or sync.
- **Acceptance Criteria:**
  - On startup, the system loads the universe from the database within 2 seconds.
  - After a refresh, the universe table in the database reflects the latest S&P 500 constituents (≥ 490 symbols verifiable from a reference source).
  - Each universe record contains non-null values for symbol, name, and sector.
  - After a full candle sync, each symbol's `candle_last_date` reflects the most recent stored 1d close and `data_status` is `up_to_date` or `stale`.

---

## FO-INF-003: Historical OHLCV Data Acquisition & Incremental Update
- **Status:** Approved

- For each symbol in the universe, the system shall download **5 trading days** of 1m bars and **2 years** of 1d/1w bars directly from IBKR. (2 years of 1d history is required to compute reliable baselines for ATR, RSI, Bollinger Bands, and breakout levels used by the screener.)
- Higher timeframes (3m, 5m, 15m, 1h, 4h) shall be synthesised locally by aggregating the stored 1m bars — they shall **not** be fetched from the API to minimise pacing consumption.
- The system shall perform an **incremental candle sync** on demand (and optionally at startup): query the last stored timestamp per symbol for 1d and 1w, then fetch only the missing bars up to the current time and append them.
- Intraday timeframes (1m) shall be stored for at least 5 trading days by default; daily/weekly bars shall be stored for **2 years**.
- Historical and live-synthesised candles must be byte-identical in OHLCV values for overlapping timestamps once the market closes.
- After each symbol's bootstrap or incremental sync, the system shall update `candle_start_date`, `candle_last_date`, and `data_status` in the `universe` table. `data_status` is `up_to_date` if `candle_last_date` ≥ last trading day, else `stale`.
- `AppService.sync_candle_data()` triggers the incremental 1d/1w sync for all universe symbols concurrently and emits `candle_sync_updated` signal on completion.
- **Acceptance Criteria:**
  - Given an empty database, the bootstrap process downloads 2 years of 1d bars for all 500 symbols and stores them correctly within a configurable time window.
  - Given a database with data up to yesterday's close, the incremental sync fetches only today's bars and appends them without duplication.
  - After sync, each symbol in the `universe` table has `data_status = 'up_to_date'` when `candle_last_date` matches the last trading day.
  - A 3m candle synthesised from three stored 1m bars has `open` = first-bar open, `high` = max of three, `low` = min of three, `close` = last-bar close, `volume` = sum of three.

---

## FO-INF-004: Database Storage & Retrieval
- **Status:** Approved

- The system shall use **PostgreSQL** in production and **SQLite** in development as the database backend, selectable via configuration.
- The database schema shall include: `universe`, `price_1m`, `price_1d`, `price_1w`, `watchlist`, `trades`, `positions`, `users` tables (as defined in `requirements.md` §7).
- All price tables shall have a compound index on `(symbol, datetime)` to ensure sub-second query performance for any single symbol's time-series.
- The database layer shall expose a clean repository interface (insert, fetch-range, get-last-timestamp, upsert) that is backend-agnostic.
- All write operations shall be performed on dedicated worker threads to avoid blocking the broker event loop.
- **Acceptance Criteria:**
  - Fetching 1 year of 1d bars for one symbol completes in under 500 ms on the dev SQLite backend.
  - Inserting 1,000 1m bars for one symbol completes in under 200 ms.
  - Calling `get_last_timestamp(symbol, timeframe)` returns the correct latest datetime with zero SQL errors.
  - Switching from SQLite to PostgreSQL requires only a configuration change — no code change.

---

## FO-INF-005: Logging, Error Recovery & Monitoring
- **Status:** Approved

- The system shall log all events (INFO level by default, DEBUG configurable) to rotating log files, one per day, stored in the `logs/` directory.
- All unhandled exceptions shall be caught, logged at ERROR level with full stack trace, and trigger an alert notification (configurable: email, console, or webhook).
- The system shall expose a structured health-check endpoint or CLI command reporting: connection status, last data update timestamp, DB record counts.
- Critical failures (DB unreachable, broker disconnect persisting > 5 minutes) shall trigger a clean shutdown with an error-state log entry.
- **Acceptance Criteria:**
  - All WARNING and ERROR events appear in the daily log file within 1 second of occurrence.
  - A simulated broker disconnect lasting > 5 minutes results in a clean shutdown and a CRITICAL log entry.
  - Running the health-check CLI returns structured JSON with at least: `broker_connected`, `last_update`, `universe_count`.

---

## FO-INF-006: Multi-User Profile Management
- **Status:** Approved

> Traces to: `requirements.md` §22

- The system shall support multiple user profiles, each identified by a unique `user_id`.
- Each user profile shall store: username, display name, IBKR client ID, `is_admin` flag, risk settings, strategy preferences, screener configuration, and current mode (paper / live).
- User profiles shall be persisted in the `users` database table with per-user `settings_json` for extensible configuration.
- The system shall provide CRUD operations for user management: create, read, update, delete.
- On application startup, the system shall load the active user profile (or prompt for selection if multiple users exist).
- Each user's IBKR connection shall use a distinct `clientId` to allow simultaneous sessions.
- **Exactly one user must hold `is_admin=True` at all times.** The first user created on a fresh system defaults to admin. The system shall refuse to delete or demote (`is_admin=False`) a user if they are the only remaining admin.
- **Acceptance Criteria:**
  - Given a new system, the first user created automatically receives `is_admin=True`.
  - Given 3 user profiles, switching between users loads the correct settings, risk config, and IBKR client ID.
  - Deleting a user profile does not delete their historical trades or position records (orphan data retained).
  - Each user can independently toggle paper/live mode without affecting other users.
  - Attempting to delete the only admin user raises `LastAdminError`.

---

## FO-INF-007: Data Provider Abstraction
- **Status:** Approved

> Traces to: `requirements.md` §26

- The system shall abstract OHLCV data sourcing behind a `DataProvider` interface so the IBKR dependency is replaceable.
- Two concrete providers shall be available:
  - **IBKRProvider** — production provider using `IBKRClient.req_historical_data()`.
  - **DummyProvider** — development/test provider returning synthetic or cached OHLCV bars with the same interface.
- Provider selection shall be via configuration: `DATA_PROVIDER = "ibkr"` or `DATA_PROVIDER = "dummy"`.
- `HistoricalDataEngine` and `LiveEngine` shall depend on the `DataProvider` interface, not on `IBKRClient` directly.
- **Acceptance Criteria:**
  - Given `DATA_PROVIDER = "dummy"`, the system starts and bootstraps data without an IBKR connection.
  - Given `DATA_PROVIDER = "ibkr"`, the system uses the real IBKR API for data fetching.
  - Switching providers requires only a config change — no code modification.
  - `DummyProvider.req_historical_data()` returns valid `OHLCVBar` objects with realistic synthetic values.

---

## FO-INF-008: Internet Connectivity Monitoring
- **Status:** Implemented

> Traces to: `requirements.md` §27

- The system shall continuously monitor internet reachability via a background TCP probe and expose the current state to all consumers through a single `AppService` signal.
- A `NetWatcher` component shall probe `8.8.8.8:53` every 15 s (configurable) and emit `status_changed(bool)` only when reachability flips.
- `AppService` shall re-emit the flip as `internet_status_changed(bool)` and provide a synchronous `is_internet_online() -> bool` accessor.
- On connectivity loss the system shall log a warning and record whether the IBKR data feed was active at the time.
- On connectivity restore the system shall log an info message and, if the data feed was active at the time of loss and is still disconnected, automatically attempt to reconnect.
- The main-window status bar shall display a real-time internet-status pill (Online / Offline / Checking…) driven by the signal.
- **Acceptance Criteria:**
  - The probe fires in a background thread — the GUI thread is never blocked.
  - `status_changed` is emitted at most once per reachability flip, not on every probe tick.
  - Auto-reconnect does not trigger if the user had manually disconnected before the outage.
  - The status-bar pill updates within one probe cycle of a state change.
