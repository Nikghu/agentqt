# Revision Note — RN-GUI-1.4.0-20260826

**Tool:** GUI
**Version:** 1.4.0
**Date:** 2026-08-26
**Type:** bugfix
**Author:** Claude Opus 5 under user direction
**Phase:** Live tick worker watchdog (FO-GUI-012 / FO-EXE-008)

---

## Summary

`LiveTickWorker` died once and never came back. When the IBKR API handshake failed, the
worker's event loop returned, its `QThread` finished, and live prices stopped for the rest
of the session — with nothing shown in the GUI log panel. `AppService._on_connect_ok`
guarded worker creation with `if self._tick_worker is None`, and that attribute was cleared
only in `disconnect_feed()`, so a later feed reconnect never rebuilt the worker.

Added a 30-second watchdog in `AppService` that restarts the worker when its thread has
finished while the feed is still connected. New **SRD-GUI-012.008–009**.

## Root Cause

Observed live on 2026-08-26. TWS was running with the API port open, but refused every API
handshake because the paper-trading disclaimer had not been accepted:

```
18:31:23  [Tick] Live tick streaming started (clientId=14)
18:31:28  ib_insync.client — API connection failed: TimeoutError()
18:31:29  ib_insync.wrapper — Error 10141: Paper trading disclaimer must first be
                              accepted for API connection.
18:31:33  [Tick] IBKR connection error:
```

The disclaimer was accepted at ~18:45 and the intraday candle loader reconnected fine at
18:47, but the tick worker was already dead and stayed dead for the remaining 80 minutes of
that single session. Symptoms: Market Watch PRICE / CHANGE / VOLUME blank, index strip
blank, and an OPEN HOOD cycle with LTP frozen at its entry price and no P&L.

The disclaimer itself is a TWS-side setting, not a defect. The defect is that a transient
handshake failure became permanent, silently. The same path is reachable on a live account
via the TWS daily restart, a dropped socket, or a clientId collision.

## Changes

| Area | Change |
|---|---|
| Watchdog | `_tick_watchdog` QTimer (30 s) started in `_on_connect_ok`, stopped in `disconnect_feed`. `_check_tick_health` restarts the worker when `isFinished()` is true and the feed is still `CONNECTED`. |
| Worker start | Inline creation in `_on_connect_ok` extracted to `_start_tick_worker()` so the watchdog reuses one code path. |
| Finished signal | `tw.finished` connects to `_on_tick_worker_finished(tw)` via `partial`, which clears `_tick_worker` and calls `deleteLater()`. Identity check stops a late signal from an old thread dropping a newer worker. |
| Stale ticks | `_last_tick_at` stamped in `_record_market_price`. `_warn_if_ticks_stale` logs once after 90 s of silence during regular trading hours — **warn only, never a restart**, so a quiet market cannot cause reconnect churn. |
| GUI visibility | `_on_tick_sub_failed` now also emits to `log_message`. Previously every `[Tick]` message went to the log file only, so the user saw blank prices with no explanation. |

## Design Notes

- **`live_tick_worker.py` is unchanged.** The worker still exits exactly as
  `SRD-EXE-008.006` specifies; the restart lives in `AppService`. No SRD needed reopening.
- **Restart only on a finished thread.** Restarting on tick silence was considered and
  rejected — it risks a reconnect loop on a quiet market or an illiquid symbol.
- **`reqMarketDataType(3)` was considered and rejected.** It is a per-client global setting,
  so requesting delayed data would degrade the live account to 15-minute delayed prices.
  Unacceptable for a system that runs stop-losses off ticks.
- **No effect on a healthy connection.** The thread never finishes, so the restart branch is
  never reached; ticks keep arriving, so the stale branch is never reached. Added cost on the
  happy path is one `time.monotonic()` per tick and a 30-second timer that returns after one
  boolean check.

## Files Changed

| File | Change |
|---|---|
| `gui/app_service.py` | `_TICK_WATCHDOG_MS` / `_TICK_STALE_S` constants; `_last_tick_at`, `_tick_restart_logged`, `_tick_stale_logged`, `_tick_watchdog` attributes; new `_start_tick_worker`, `_on_tick_worker_finished`, `_check_tick_health`, `_warn_if_ticks_stale`; `_record_market_price` stamps `_last_tick_at`; `disconnect_feed` stops the watchdog; `_on_tick_sub_failed` emits to the GUI log |
| `tests/gui/test_app_service_tick_watchdog.py` | New — UT-GUI-012.001.M01.T20–T28 |
| `docs/gui/SRD.md` | v2.14.0 — SRD-GUI-012.008–009 added |
| `docs/gui/MD.md` | v1.6.0 — MD-GUI-004.001.M01 extended |
| `docs/gui/UTCD.md` | v1.4.0 — T20–T28 added |
| `docs/gui/TRACE.md` | v1.10.0 — FO-GUI-012 row extended |

## Verification

- 9 new tests pass (`tests/gui/test_app_service_tick_watchdog.py`).
- `pytest us_swing/tests/gui us_swing/tests/execution us_swing/tests/broker` — 21 failed,
  298 passed. The 21 failures are the documented pre-existing baseline
  (`IBKR_Live_Execution_Plan.md` verification step 3). `test_app_service_tick.py` was run
  against clean HEAD and produced an identical 9 failed / 14 passed, so no regression.
- `ruff check` — 19 errors, all pre-existing (20 at HEAD; one long line removed by the
  refactor). No new errors on any changed line.
- `mypy --strict` — no error on any line touched by this change.

### Live verification (TWS kill / restart, 2026-08-26)

| Time | Event |
|---|---|
| 21:29:24 | TWS killed — `[Tick] IBKR connection dropped — tick streaming ended` |
| 21:29:52 | Watchdog restart 1 — connection refused |
| 21:30:22 | Watchdog restart 2 — connection refused |
| 21:30:52 | Watchdog restart 3 — connection refused |
| 21:31:22 | Watchdog restart 4 — TWS up, blocked by disclaimer error 10141 |
| 21:31:52 | Watchdog restart 5 — `[Tick] Connected to IBKR (clientId=14)` |

Full recovery in 2 min 28 s with no user action and no app restart. Before this change the
log showed exactly one `Live tick streaming started` per session and permanent silence after
any drop.

## Known Issues / Follow-ups

- `_connect_with_retry` in `live_tick_worker.py` catches `TimeoutError` under its generic
  `except Exception` and returns immediately, so the clientId-increment retry required by
  `SRD-EXE-008.006` never runs on that path. Observed as
  `Peer closed connection. clientId 14 already in use?` at 21:31:28. The watchdog masks it —
  the next attempt 30 s later finds the id free. Worth a separate fix.
- Recovery latency is bounded by the 30-second watchdog interval, not instant.
