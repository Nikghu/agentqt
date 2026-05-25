# Unit Test Case Document — Infrastructure (INF)

**Document ID:** UTCD-INF
**Version:** 1.1.0
**Traces To:** MD-INF v1.1.0
**Status:** Draft
**Last Updated:** 2026-03-06
**Project:** US Swing Trading System

> Tests written BEFORE implementation per process.md §7.

---

## Compact Format

| Column | Meaning |
|---|---|
| Type | Unit / Integration / Edge |
| Expected Output | What must be true for the test to PASS |

---

## Module: `broker/pacing.py` — PacingQueue

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-001.001.M02.T01 | MD-INF-001.001.M02 | Unit | 50 slots available initially | Fresh `PacingQueue(limit=50, window_s=600)` | `available == 50` | Draft |
| UT-INF-001.001.M02.T02 | MD-INF-001.001.M02 | Unit | Acquiring a slot decrements count | `acquire()` once | `available == 49` | Draft |
| UT-INF-001.001.M02.T03 | MD-INF-001.001.M02 | Edge | Acquiring when 0 slots available suspends until a slot expires | Fill 50 slots; attempt 51st `acquire()` | Coroutine suspends; does not raise | Draft |
| UT-INF-001.001.M02.T04 | MD-INF-001.001.M02 | Unit | `release_expired()` frees slots older than window | Add slot with timestamp 601 s ago | `available` increments after `release_expired()` | Draft |

---

## Module: `broker/client.py` — IBKRClient

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-001.001.M01.T01 | MD-INF-001.001.M01 | Unit | `connect()` calls `IB.connectAsync()` with correct args | Mock `IB`; call `connect("127.0.0.1", 7497, 1)` | `IB.connectAsync("127.0.0.1", 7497, 1)` called once | Draft |
| UT-INF-001.001.M01.T02 | MD-INF-001.001.M01 | Unit | `is_connected()` returns False before connect | Fresh `IBKRClient` | `False` | Draft |
| UT-INF-001.001.M01.T03 | MD-INF-001.001.M01 | Edge | `connect()` raises `ConnectionError` on timeout | Mock `IB.connectAsync()` to never complete; timeout=0.1s | `ConnectionError` raised | Draft |
| UT-INF-001.001.M01.T04 | MD-INF-001.001.M01 | Unit | Status change callback fires on disconnect event | Register callback; simulate disconnect event | Callback called with `ConnectionStatus.DISCONNECTED` | Draft |
| UT-INF-001.001.M01.T05 | MD-INF-001.001.M01 | Edge | Reconnect backoff sequence is correct | Simulate 3 consecutive disconnects | Delays ≈ [2, 4, 8] seconds (within 10% tolerance) | Draft |

---

## Module: `universe/manager.py` — UniverseManager

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-002.001.M01.T01 | MD-INF-002.001.M01 | Unit | `load_universe()` returns records from DB | DB seeded with 3 records | Returns list of 3 `UniverseRecord` with correct fields | Draft |
| UT-INF-002.001.M01.T02 | MD-INF-002.001.M01 | Edge | `load_universe()` returns empty list if table empty | Empty `universe` table | `[]` returned; no exception | Draft |
| UT-INF-002.001.M01.T03 | MD-INF-002.001.M01 | Unit | `refresh_universe()` upserts records correctly | Mock HTML source with 5 symbols; 2 already in DB | DB has 5 records; existing 2 updated; 3 new inserted | Draft |
| UT-INF-002.001.M01.T04 | MD-INF-002.001.M01 | Edge | Malformed record (empty symbol) is skipped | Source includes record with `symbol = ""` | Record not inserted; WARNING logged; other valid records inserted | Draft |

---

## Module: `data/engine.py` — HistoricalDataEngine

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-003.001.M01.T01 | MD-INF-003.001.M01 | Unit | `aggregate_timeframe()` — 3m bar from three 1m bars | 3 consecutive 1m bars: O=10,H=12,L=9,C=11; O=11,H=13,L=10,C=12; O=12,H=14,L=11,C=13 | `OHLCVBar(open=10, high=14, low=9, close=13, volume=sum)` | Draft |
| UT-INF-003.001.M01.T02 | MD-INF-003.001.M01 | Edge | `aggregate_timeframe()` — incomplete group (1 bar, target 3m) | One 1m bar | No output bar (group not yet complete) | Draft |
| UT-INF-003.001.M01.T03 | MD-INF-003.001.M01 | Unit | `update_missing_data()` fetches only bars after last stored timestamp | DB has data up to T; mock IBKR returns bars from T+1 onwards | Only bars after T are inserted; count = new bars only | Draft |
| UT-INF-003.001.M01.T04 | MD-INF-003.001.M01 | Edge | `update_missing_data()` when no data in DB falls back to bootstrap | `get_last_timestamp` returns `None` | `bootstrap_symbol()` is called | Draft |
| UT-INF-003.001.M01.T05 | MD-INF-003.001.M01 | Unit | Candle consistency: live-built bar equals historical bar for same timestamp | Same 3 bars aggregated via `aggregate_timeframe()` and via `CandleBuilder.add_bar()` | Both `OHLCVBar` instances are equal in all OHLCV fields | Draft |

---

## Module: `db/manager.py` — DatabaseManager

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-004.001.M01.T01 | MD-INF-004.001.M01 | Unit | `insert_bars()` inserts new bars | 5 `OHLCVBar` for AAPL 1d | `fetch_bars("AAPL","1d", ...)` returns 5 bars | Draft |
| UT-INF-004.001.M01.T02 | MD-INF-004.001.M01 | Edge | `insert_bars()` does not duplicate on re-insert | Insert same 5 bars twice | Only 5 bars in DB (no duplicates) | Draft |
| UT-INF-004.001.M01.T03 | MD-INF-004.001.M01 | Unit | `get_last_timestamp()` returns max datetime | 10 bars with datetimes T1…T10 | Returns T10 | Draft |
| UT-INF-004.001.M01.T04 | MD-INF-004.001.M01 | Edge | `get_last_timestamp()` returns `None` if no data | Empty table | `None` | Draft |
| UT-INF-004.001.M01.T05 | MD-INF-004.001.M01 | Unit | `fetch_bars()` respects date range boundaries | 10 bars; request bars [T3, T7] | Returns exactly bars T3 through T7 | Draft |
| UT-INF-004.001.M01.T06 | MD-INF-004.001.M01 | Unit | `upsert_position()` + `delete_position()` round-trip | Insert AAPL position; delete it | `fetch_open_positions()` returns empty list | Draft |
| UT-INF-004.001.M01.T20 | MD-INF-004.001.M01 | Unit | `migrate_lifecycle_columns` adds the 4 new columns when absent | Fresh DB missing all 4 columns | `PRAGMA table_info(trades)` shows `trade_origin`, `monitoring_session_date`; `PRAGMA table_info(positions)` shows `origin`, `anchor_session_date` | Pass |
| UT-INF-004.001.M01.T21 | MD-INF-004.001.M01 | Unit | `migrate_lifecycle_columns` is idempotent | Run T20 twice | Second call produces no `ALTER TABLE` execution; column count unchanged | Pass |

---

## Module: `db/schema.py` — DatabaseSchema

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-004.001.M02.T05 | MD-INF-004.001.M02 | Unit | `create_schema(checkfirst=True)` provisions `monitoring_session` table and indexes | Fresh engine; call `create_schema` | Table exists; both indexes (`idx_monitoring_session_state`, `idx_monitoring_session_symbol`) present | Pass |

---

## Module: `monitoring/` — Logging & Alerts

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-005.001.M01.T01 | MD-INF-005.001.M01 | Unit | `configure_logging()` creates rotating file handler | Call `configure_logging(log_dir, "INFO")` | A `TimedRotatingFileHandler` is attached to root logger | Draft |
| UT-INF-005.001.M01.T02 | MD-INF-005.001.M01 | Unit | Global `sys.excepthook` logs uncaught exception | Manually call `sys.excepthook` with a `ValueError` | CRITICAL entry appears in log with full traceback | Draft |
| UT-INF-005.001.M02.T01 | MD-INF-005.001.M02 | Unit | `AlertDispatcher.send()` appends to alerts.log | Send WARNING alert | `logs/alerts.log` contains the message | Draft |
| UT-INF-005.001.M02.T02 | MD-INF-005.001.M02 | Edge | Webhook failure does not crash dispatcher | Configure bad URL; send alert | WARNING logged about webhook failure; no exception propagates | Draft |
| UT-INF-005.001.M03.T01 | MD-INF-005.001.M03 | Unit | `HealthCheck.report()` returns expected keys | Mock broker connected, DB reachable | Dict has keys: `broker_connected`, `last_update`, `universe_count`, `open_positions`, `db_reachable` | Draft |

---

## Module: `user/manager.py` — UserManager

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-006.001.M01.T01 | MD-INF-006.001.M01 | Unit | `create_user()` inserts a new user and returns `UserProfile` | `create_user("trader1", "Trader One", 101)` | `UserProfile` with `username="trader1"`, mode=`"paper"` | Draft |
| UT-INF-006.001.M01.T02 | MD-INF-006.001.M01 | Edge | `create_user()` raises `DuplicateUserError` on duplicate username | Create user with same username twice | `DuplicateUserError` raised | Draft |
| UT-INF-006.001.M01.T03 | MD-INF-006.001.M01 | Unit | `get_user()` returns correct profile with parsed settings | User exists with risk_per_trade_pct=2 in settings_json | `profile.risk_config.risk_per_trade_pct == 2.0` | Draft |
| UT-INF-006.001.M01.T04 | MD-INF-006.001.M01 | Edge | `get_user()` raises `UserNotFoundError` for non-existent ID | `get_user(9999)` | `UserNotFoundError` raised | Draft |
| UT-INF-006.001.M01.T05 | MD-INF-006.001.M01 | Unit | `update_user()` modifies only specified fields | `update_user(1, display_name="New Name")` | `display_name` changed; other fields unchanged | Draft |
| UT-INF-006.001.M01.T06 | MD-INF-006.001.M01 | Unit | `delete_user()` removes user but retains orphan trades | Delete user with existing trades | User gone from `users` table; trades still in `trades` table | Draft |
| UT-INF-006.001.M01.T07 | MD-INF-006.001.M01 | Unit | `list_users()` returns all users | 3 users created | Returns list of 3 `UserProfile` | Draft |
| UT-INF-006.001.M01.T08 | MD-INF-006.001.M01 | Edge | `switch_mode()` to 'live' without confirm token raises error | `switch_mode(1, "live")` (no token) | `ConfirmationRequiredError` raised | Draft |
| UT-INF-006.001.M01.T09 | MD-INF-006.001.M01 | Unit | `switch_mode()` to 'live' with valid token succeeds | `switch_mode(1, "live", confirm_token="valid")` | mode updated to 'live' | Draft |

---

## Module: `data/providers/dummy_provider.py` — DummyProvider

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-007.001.M02.T01 | MD-INF-007.001.M02 | Unit | `req_historical_data()` returns valid `OHLCVBar` list | symbol="AAPL", duration="1 Y", bar_size="1 day" | Non-empty `list[OHLCVBar]` with correct fields | Draft |
| UT-INF-007.001.M02.T02 | MD-INF-007.001.M02 | Unit | Generated bars satisfy OHLCV constraints | Any request | For each bar: `low <= open`, `low <= close`, `high >= open`, `high >= close`, `volume >= 0` | Draft |
| UT-INF-007.001.M02.T03 | MD-INF-007.001.M02 | Unit | Same seed produces identical bars | Two calls with seed=42 | Both return identical `list[OHLCVBar]` | Draft |
| UT-INF-007.001.M02.T04 | MD-INF-007.001.M02 | Edge | `subscribe_realtime_bars()` emits bars via callback | Subscribe and wait 10s | At least 1 bar received via `on_realtime_bar` callback | Draft |
