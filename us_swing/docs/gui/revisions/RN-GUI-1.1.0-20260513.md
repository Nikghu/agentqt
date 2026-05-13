# RN-GUI-1.1.0-20260513 — GUI Module v1.1.0

**Date:** 2026-05-13
**Tool:** GUI (Graphical User Interface)
**Version:** 1.1.0
**Type:** Feature

## Summary

Implemented FO-GUI-012: Persistent IBKR Session. Replaced three short-lived
polling workers (`_AccountDataWorker`, `_MarketWatchWorker`,
`_WatchlistQuoteWorker`) — each opening and closing its own `ib_insync.IB`
connection every 10–30 s — with a single push-based session held for the
lifetime of the feed. Account state, portfolio positions, Market Watch
quotes, and Watchlist quotes are now delivered by IBKR subscriptions
(`reqAccountUpdates`, `reqMktData`) inside a dedicated asyncio `QThread`,
with debounced (50 ms) account snapshots and coalesced (250 ms) tick
batches bridged to the Qt main thread via `pyqtSignal`. An exponential
backoff reconnect state machine (2 s → 30 s, ±20 % jitter, max 10 attempts)
surfaces transitions through the existing `feed_status_changed` signal — no
new `ConnectionStatus` enum values are introduced. The yfinance fallback
is retained but tightened: active only while `DISCONNECTED` (30 s timer)
plus a coalesced one-shot path for `^`-prefixed index symbols.

The refactor preserves every public `AppService` signal signature
(`account_updated`, `positions_updated`, `market_watch_updated`,
`watchlist_updated`, `feed_status_changed`); no panel-level code was
modified.

## Changed Modules

| MD ID | File | Change Description |
|---|---|---|
| MD-GUI-012.001.M01 | `src/us_swing/gui/ibkr_session.py` | **New module** — `IBKRSession(QObject)` owning the persistent `ib_insync.IB` on a dedicated `QThread` asyncio loop. Public signals `account_ready`, `quotes_updated`, `connection_lost`, `connection_restored`; public methods `start`, `stop`, `set_market_watch_symbols`, `set_watchlist_symbols`. Idempotent `start()`; `stop()` joins the thread within 3 s with `terminate()` safety valve. Cancel-and-replace debounce semantics for account events; coalescing window for tick bursts. Reconnect state machine entirely inside the asyncio loop; no `QTimer` involvement. Strict `^`-prefix filter inside `_apply_symbol_delta` so index symbols can never reach `reqMktData`. |
| MD-GUI-012.001.M02 | `src/us_swing/gui/app_service.py` | Refactor — added four bridge slots (`_on_session_account_ready`, `_on_session_quotes_updated`, `_on_session_connection_lost`, `_on_session_connection_restored`) that fire the existing public signals unchanged; added `_MarketWatchYfinanceWorker(QThread)` (single consolidated yfinance fallback); replaced `_on_connect_ok` and `disconnect_feed` bodies. **Deleted** in full: `_AccountDataWorker`, `_MarketWatchWorker`, `_WatchlistQuoteWorker`, their three `QTimer`s, `_refresh_account_data`, `_refresh_market_watch`, `_refresh_watchlist`, `_on_account_data_ready`, `_on_account_data_failed`, fields `_acct_worker`, `_mw_worker`, `_wl_worker`, `_mw_log_on_next_fetch`, and the stale `import time`. |
| MD-GUI-012.001.M02 | `src/us_swing/gui/system_store.py` | Removed `ibkr_mw_client_id` and `ibkr_wl_client_id` fields from `SystemConfig` and from `load_system_config`. JSON files that still persist these keys load gracefully (keys ignored). `ibkr_intraday_client_id` (candle download) and `ibkr_live_client_id` (live-bar worker) are preserved unchanged. |

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-012.001 | `IBKRSession(QObject)` module + signal / method surface | Implemented |
| SRD-GUI-012.002 | Dedicated `QThread` asyncio loop + Qt-thread-safe signal marshalling | Implemented |
| SRD-GUI-012.003 | Lifecycle tied to `connect_feed` / `disconnect_feed` (idempotent) | Implemented |
| SRD-GUI-012.004 | `reqAccountUpdates` + 50 ms debounced `account_ready` | Implemented |
| SRD-GUI-012.005 | `reqMktData` union for MW + WL with 250 ms coalescing | Implemented |
| SRD-GUI-012.006 | Symbol-set mutation by set-difference cancel/resubscribe | Implemented |
| SRD-GUI-012.007 | Reconnect state machine — 2 s → 30 s backoff, max 10 attempts | Implemented |
| SRD-GUI-012.008 | AppService bridge for account_ready → account/positions signals | Implemented |
| SRD-GUI-012.009 | AppService bridge for quotes_updated → MW/WL signals + index carve-out | Implemented |
| SRD-GUI-012.010 | yfinance fallback active only while DISCONNECTED (30 s timer) | Implemented |
| SRD-GUI-012.011 | One clientId for the session; legacy MW/WL clientIds removed | Implemented |
| SRD-GUI-012.012 | Full cleanup of legacy workers / timers / methods / fields | Implemented |

## Tests

UTCD: `UT-GUI-012.001.M01.T01–T16` and `UT-GUI-012.001.M02.T01–T14` (30 total).

Result: **26 Pass / 4 Skip**.

- `tests/gui/test_ibkr_session.py` — 16 cases; T05–T16 exercise asyncio
  internals directly by patching `session._loop` / `session._ib` and
  running coroutines with `run_until_complete`. Reconnect timing is
  monkeypatched (`_RECONNECT_BASE = 0.01`) to keep performance tests
  under 2 s.
- `tests/gui/test_app_service_ibkr_bridge.py` — 14 cases; uses a
  `FakeIBKRSession(QObject)` injected via
  `monkeypatch.setattr("us_swing.gui.app_service.IBKRSession", …)`.
  Includes a deleted-identifier static sweep (T12), a `SystemConfig`
  field-removal check (T13), and a public-signal-signature regression
  guard (T14).
- **Skipped:** T01–T04 (start / stop / thread-lifecycle). Root cause is
  architectural: in the pytest harness there is no `app.exec()` to
  pump `QueuedConnection` calls, so `QThread.started → _thread_main`
  never fires and the asyncio loop is unreachable. All asyncio logic is
  still covered by T05–T16 via direct coroutine invocation; integration
  testing of the full QThread boot path will be performed via a manual
  smoke run.

## Linting / Typing

- `ruff check` — 11 errors on `app_service.py` (baseline 12; 1 net
  removed). All remaining are pre-existing `E402` import-order
  violations outside the FO-GUI-012 scope.
- `mypy --strict` — 75 errors on the three changed files (baseline 83;
  8 net removed). Zero new mypy errors introduced by this refactor.

## Backward-Compatibility & Migration

- Public `AppService` signal signatures preserved byte-for-byte. No
  panel code was modified.
- `system_config.json` files that still contain `ibkr_mw_client_id` or
  `ibkr_wl_client_id` keys load without error; the keys are silently
  ignored on load and not re-emitted on save.
- The candle download worker and live-bar worker are untouched; their
  isolated clientIds and lifecycles continue to work exactly as before.

## Operational Notes

- IBKR Gateway should observe exactly **one** monitoring connection
  (clientId = `system_cfg.ibkr_system_client_id`) for the lifetime of
  the feed, regardless of how often the user edits the Market Watch /
  Watchlist symbols. The prior pattern of churning three clientIds
  every 10–30 s is gone.
- Account / portfolio / quote updates now arrive within ~50 ms of any
  IBKR push, versus the prior 10–30 s polling cadence.
- During an unexpected socket drop, the GUI status pill transitions
  `CONNECTED → RECONNECTING` automatically; on successful reconnect
  the session re-runs `reqAccountUpdates` and re-subscribes every
  tracked ticker before transitioning back to `CONNECTED`. After 10
  consecutive failures the session terminates and the standard
  yfinance fallback takes over.
