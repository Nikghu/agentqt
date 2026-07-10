# Unit Test Case Document — Infrastructure (INF)

**Document ID:** UTCD-INF
**Version:** 1.6.0
**Traces To:** MD-INF v1.4.0
**Status:** Draft
**Last Updated:** 2026-07-10
**Project:** US Swing Trading System

> Tests written BEFORE implementation per process.md §7.
> v1.3.0: notification-service cases added (MD-INF-010.001.M01–M07).
> v1.4.0: keychain token store + user-store persistence cases added (MD-INF-010.001.M08).
> v1.5.0: inbound command cases added (MD-INF-010.001.M10 router/poller, M11 GUI bridge).
> v1.6.0: per-event toggle enforcement (M04.T07–09, M07.T03), toggle persistence (M08.T06–07), day-end trigger (M09.T01–03).

---

## Compact Format

| Column | Meaning |
|---|---|
| Type | Unit / Integration / Edge |
| Expected Output | What must be true for the test to PASS |

---

## Module: `broker/sim.py` — SimBroker

> The full broker contract suite lives in `tests/broker/test_broker_contract.py` (SRD-INF-009.004/.006); only the live-price-provider cases (SRD-INF-009.007) are tracked as IDs here.

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-009.004.M01.T01 | MD-INF-009.004.M01 | Positive | MARKET order fills at the price provider's live price, not the request's reference (SRD-INF-009.007, ISS-INF-0002) | `SimBroker(price_provider=lambda s: 191.3)`; market buy `reference_price=50.0` | `OrderEvent.fill_price == 191.3` | Pass |
| UT-INF-009.004.M01.T02 | MD-INF-009.004.M01 | Negative | Falls back to `reference_price` when the provider returns no live price | `price_provider=lambda s: None`; market buy `reference_price=50.0` | `OrderEvent.fill_price == 50.0` | Pass |
| UT-INF-009.004.M01.T03 | MD-INF-009.004.M01 | Edge | Non-positive (`0.0`) provider price falls back to `reference_price` | `price_provider=lambda s: 0.0`; market buy `reference_price=50.0` | `OrderEvent.fill_price == 50.0` | Pass |
| UT-INF-009.004.M01.T04 | MD-INF-009.004.M01 | Edge | LIMIT order ignores the provider and fills at `limit_price` | `price_provider=lambda s: 191.3`; limit buy `limit_price=48.0` | `OrderEvent.fill_price == 48.0` | Pass |

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

---

## Module: `core/notifications/_events.py` — Events & Bus

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-010.001.M01.T01 | MD-INF-010.001.M01 | Positive | `ScreenerApprovedEvent` stores its symbols and carries `schema_version` | `ScreenerApprovedEvent(symbols=("AAPL","MSFT"))` | `event.symbols == ("AAPL","MSFT")`; `event.schema_version == 1` | Pass |
| UT-INF-010.001.M01.T02 | MD-INF-010.001.M01 | Negative | Event is frozen — mutation is rejected | Set `event.symbols = ()` on a built event | `FrozenInstanceError` raised | Pass |
| UT-INF-010.001.M01.T03 | MD-INF-010.001.M01 | Positive | Bus `publish` calls a subscribed handler with the event | Subscribe handler; publish a `ToolStartedEvent` | Handler invoked once with that event | Pass |
| UT-INF-010.001.M01.T04 | MD-INF-010.001.M01 | Edge | A raising handler is isolated — sibling still runs, no exception propagates | Two handlers, first raises; publish event | Second handler still called; `publish` returns without raising | Pass |

---

## Module: `core/notifications/_protocols.py` — Channel Protocol

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-010.001.M02.T01 | MD-INF-010.001.M02 | Positive | `TelegramChannel` structurally satisfies `NotificationChannel` | `isinstance(telegram, NotificationChannel)` | `True` | Pass |
| UT-INF-010.001.M02.T02 | MD-INF-010.001.M02 | Negative | An object without `send` does not satisfy the Protocol | `isinstance(object(), NotificationChannel)` | `False` | Pass |

---

## Module: `core/notifications/_telegram.py` — TelegramChannel

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-010.001.M03.T01 | MD-INF-010.001.M03 | Positive | `send` POSTs `sendMessage` with chat id and text | `TelegramChannel(token, chat_id, mock_client)`; send a message | Request URL ends `/bot<token>/sendMessage`; body has `chat_id` + `text` | Pass |
| UT-INF-010.001.M03.T02 | MD-INF-010.001.M03 | Negative | A non-2xx Telegram response raises so the dispatcher can catch it | Mock client returns HTTP 400 | Exception raised from `send` | Pass |

---

## Module: `core/notifications/_dispatcher.py` — NotificationDispatcher

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-010.001.M04.T01 | MD-INF-010.001.M04 | Positive | An event is rendered and delivered to an enabled channel | Dispatcher with one recording channel; deliver a `ToolStartedEvent` | Channel received one message with non-empty text | Pass |
| UT-INF-010.001.M04.T02 | MD-INF-010.001.M04 | Edge | One channel failing does not stop another and does not propagate | Two channels, first always raises; deliver a message | Second channel still received the message; no exception propagates | Pass |
| UT-INF-010.001.M04.T03 | MD-INF-010.001.M04 | Positive | A channel failing once then succeeding is retried and delivers | Channel raises on first send, succeeds on second; `max_retries=1` | Message eventually delivered; two send attempts made | Pass |
| UT-INF-010.001.M04.T04 | MD-INF-010.001.M04 | Negative | Retries exhausted are logged, not raised | Channel always raises; `max_retries=1` | No exception propagates; failure logged under `[Notify]` | Pass |
| UT-INF-010.001.M04.T05 | MD-INF-010.001.M04 | Positive | `dispatch` enqueues without blocking the caller | Call `dispatch(event)` (no worker running) | Returns immediately; internal queue size is 1 | Pass |
| UT-INF-010.001.M04.T06 | MD-INF-010.001.M04 | Negative | `dispatch` of an event with no formatter is swallowed, not raised | Registry without a formatter for the event type | `dispatch` returns without raising; failure logged | Pass |
| UT-INF-010.001.M04.T07 | MD-INF-010.001.M04 | Negative | An event whose kind is toggled off is dropped before enqueue | Dispatcher with `event_toggles={"ToolStartedEvent": False}`; dispatch one | Queue size stays 0 | Pass |
| UT-INF-010.001.M04.T08 | MD-INF-010.001.M04 | Positive | An event whose kind is toggled on is enqueued | Dispatcher with `event_toggles={"ToolStartedEvent": True}`; dispatch one | Queue size is 1 | Pass |
| UT-INF-010.001.M04.T09 | MD-INF-010.001.M04 | Edge | An event kind absent from the toggle map defaults to on | Dispatcher with a map covering only another kind; dispatch the uncovered one | Queue size is 1 | Pass |

---

## Module: `core/notifications/_formatters.py` — FormatterRegistry

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-010.001.M05.T01 | MD-INF-010.001.M05 | Positive | Default registry renders `ScreenerApprovedEvent` listing the symbols | `render(ScreenerApprovedEvent(symbols=("AAPL","MSFT")))` | Message text contains `AAPL` and `MSFT` | Pass |
| UT-INF-010.001.M05.T02 | MD-INF-010.001.M05 | Negative | Rendering an unregistered event type raises a clear error | `render(event)` for a type with no formatter | `KeyError` raised naming the missing type | Pass |
| UT-INF-010.001.M05.T03 | MD-INF-010.001.M05 | Positive | A newly registered event type renders without touching existing formatters | Register formatter for a new event class; render it | Correct message returned; existing renders still work | Pass |

---

## Module: `core/notifications/_dto.py` — Config

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-010.001.M06.T01 | MD-INF-010.001.M06 | Positive | `load_config` parses telegram settings and per-event toggles | `settings_json` with enabled telegram + token + chat id | `NotificationConfig(telegram_enabled=True, bot_token=…, chat_id=…)` | Pass |
| UT-INF-010.001.M06.T02 | MD-INF-010.001.M06 | Edge | Missing `notifications` key yields a disabled config, no crash | `settings_json = {}` | `telegram_enabled == False`; no exception | Pass |
| UT-INF-010.001.M06.T03 | MD-INF-010.001.M06 | Negative | Enabled telegram with a blank token is treated as disabled | enabled True but `bot_token=""` | `telegram_enabled == False` | Pass |

---

## Module: `core/notifications/__init__.py` — Factory & Publish

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-010.001.M07.T01 | MD-INF-010.001.M07 | Positive | Factory with telegram enabled builds a dispatcher wired with a Telegram channel | `build_default_dispatcher(enabled config, http)` | Dispatcher has one channel | Pass |
| UT-INF-010.001.M07.T02 | MD-INF-010.001.M07 | Negative | Factory with telegram disabled builds a dispatcher with no channels; publish is a safe no-op | `build_default_dispatcher(disabled config)`; publish an event | Zero channels; `publish` does not raise | Pass |
| UT-INF-010.001.M07.T03 | MD-INF-010.001.M07 | Positive | Factory passes `event_toggles` through so a toggled-off event is dropped end-to-end | Enabled config with `event_toggles={"ToolStartedEvent": False}`; publish one | Queue size stays 0 | Pass |

---

## Module: `gui/telegram_token_store.py` + `gui/user_store.py` — Settings persistence

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-010.001.M08.T01 | MD-INF-010.001.M08 | Positive | A saved bot token round-trips per user | `save(7, "secret-token")` then `load(7)` | `"secret-token"` | Pass |
| UT-INF-010.001.M08.T02 | MD-INF-010.001.M08 | Negative | An unset user's token loads as empty | `load(999)` on empty store | `""` | Pass |
| UT-INF-010.001.M08.T03 | MD-INF-010.001.M08 | Edge | Saving a blank token clears the stored entry | `save(7, "x")` then `save(7, "")`; `load(7)` | `""` | Pass |
| UT-INF-010.001.M08.T04 | MD-INF-010.001.M08 | Positive | `telegram_enabled` + `telegram_chat_id` survive user-store round-trip | `_to_dict`→`_from_dict` of a user with the fields set | fields preserved | Pass |
| UT-INF-010.001.M08.T05 | MD-INF-010.001.M08 | Edge | Legacy records without telegram fields default to off | `_from_dict` of a dict missing the fields | `telegram_enabled=False`, `telegram_chat_id=""` | Pass |
| UT-INF-010.001.M08.T06 | MD-INF-010.001.M08 | Positive | Per-event notify toggles survive user-store round-trip | `_to_dict`→`_from_dict` of a user with mixed toggle values | three `notify_*` fields preserved | Pass |
| UT-INF-010.001.M08.T07 | MD-INF-010.001.M08 | Edge | Legacy records without toggle fields default all on | `_from_dict` of a dict missing the toggle fields | three `notify_*` fields are True | Pass |

---

## Module: `gui/app_service.py` — Day-end P&L trigger

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-010.001.M09.T01 | MD-INF-010.001.M09 | Positive | The day-end summary is sent at most once per trading day | Call `_maybe_publish_day_end` twice with the same date | Exactly one publish; guard date set | Pass |
| UT-INF-010.001.M09.T02 | MD-INF-010.001.M09 | Positive | A new trading day sends a fresh summary | Call `_maybe_publish_day_end` for two consecutive dates | Two publishes | Pass |
| UT-INF-010.001.M09.T03 | MD-INF-010.001.M09 | Edge | Nothing sent and guard not consumed before the notification worker starts | Call with `_notif_worker=None` | No publish; guard date still `None` | Pass |

---

## Module: `core/notifications/_inbound.py` — Command router & poller

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-010.001.M10.T01 | MD-INF-010.001.M10 | Positive | Router dispatches `/pnl` to the port and returns its reply | Router over a fake port; `route("/pnl")` | Port `pnl()` called once; its text returned | Pass |
| UT-INF-010.001.M10.T02 | MD-INF-010.001.M10 | Positive | `/help` returns the list of all seven commands | `route("/help")` | Text lists `/status`, `/pnl`, `/positions`, `/signals`, `/screener`, `/cycles`, `/help` | Pass |
| UT-INF-010.001.M10.T03 | MD-INF-010.001.M10 | Negative | An unknown command returns a help hint, not an error | `route("/foo")` | Reply names `/foo` and points to `/help`; no exception | Pass |
| UT-INF-010.001.M10.T04 | MD-INF-010.001.M10 | Edge | Plain non-command text is ignored | `route("hello there")` | Returns `None` | Pass |
| UT-INF-010.001.M10.T05 | MD-INF-010.001.M10 | Edge | A trailing `@botname` and case are normalized before dispatch | `route("/PnL@usswing_bot")` | Port `pnl()` called; its text returned | Pass |
| UT-INF-010.001.M10.T06 | MD-INF-010.001.M10 | Negative | A handler that raises yields a plain apology, not a stack trace | Fake port whose `status()` raises; `route("/status")` | Reply is a plain apology; no exception propagates | Pass |
| UT-INF-010.001.M10.T07 | MD-INF-010.001.M10 | Positive | Poller handles an authorized update, replies, and advances the offset | Fake transport returns one `/help` update from the configured chat | Reply sent via `sendMessage`; next `getUpdates` uses `offset = update_id + 1` | Pass |
| UT-INF-010.001.M10.T08 | MD-INF-010.001.M10 | Negative | A message from an unauthorized chat is ignored and unanswered | Update whose chat id differs from the configured one | No `sendMessage`; offset still advances | Pass |
| UT-INF-010.001.M10.T09 | MD-INF-010.001.M10 | Positive | Poller registers its command menu with Telegram on start | `_register_commands()` against a fake transport | One `setMyCommands` POST carrying the 7 commands with descriptions | Pass |

---

## Module: `gui/telegram_commands.py` — Command bridge

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-INF-010.001.M11.T01 | MD-INF-010.001.M11 | Positive | Bridge structurally satisfies `CommandPort` | `isinstance(bridge, CommandPort)` | `True` | Pass |
| UT-INF-010.001.M11.T02 | MD-INF-010.001.M11 | Positive | `positions()` formats the open positions from `AppService` | Fake app with two open positions; call `positions()` on the GUI thread | Text names both symbols and the count | Pass |
| UT-INF-010.001.M11.T03 | MD-INF-010.001.M11 | Edge | `pnl()` reports zero cleanly when there are no positions | Fake app with flat account and no positions | Text shows realized and unrealized P&L without error | Pass |
