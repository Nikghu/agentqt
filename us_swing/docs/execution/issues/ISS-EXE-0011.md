# Issue Report — ISS-EXE-0011

**Tool:** EXE (Execution)
**Severity:** High (a screened stock silently gets no 1m history for the whole session, so every candle-based entry and exit for it is un-evaluable)
**Status:** Resolved
**Date Opened:** 2026-09-01
**Date Resolved:** 2026-09-01
**Reporter:** User (repeating `[Strategy] SUPERTREND entry-expr failed for CDW / DG: SUPERTREND: insufficient bars to compute (NaN)` warnings in the live log)
**Resolution:** RN-EXE-1.32.2-20260901 (SRD-EXE-006.008 drain trigger corrected)
**Related:** ISS-EXE-0009 (the NaN guard that made this visible)

---

## Symptom

From 09:34 ET onward the log repeated, once per evaluation cycle, for two symbols:

```
09:37:01-0400 WARNING [Strategy] SUPERTREND entry-expr failed for CDW: SUPERTREND: insufficient bars to compute (NaN)
09:52:01-0400 WARNING [Strategy] SUPERTREND entry-expr failed for DG:  SUPERTREND: insufficient bars to compute (NaN)
```

ST_AUTO (15m) reported the same symbols as `No candle data for timeframe '15m'`, then
`Insufficient bars for Price('Last')`.

The 3m warnings stopped on their own at 09:59, when the 11th live 3m bar of the day formed.

## Evidence

`SUPERTREND('Spot', 10, 3, 'No', '3m')` uses ATR length 10. Reproduced against
`_supertrend_value`: it returns NaN at ≤ 10 bars and a real value from 11 bars onward — so
the indicator was correct; the frame was short.

`~/.usswing/candles.db` at the time of the incident:

| Symbol | `price_1m` rows | 3m bars before 09:52 ET |
|---|---|---|
| CDW | **0** | 8 |
| DG | **0** | 8 |
| TSLA | 11,700 | 8 |

All three carried the same 8 live bars from the 09:30 open. TSLA evaluated fine because its
30-day 1m history backed the aggregation; CDW and DG had none, so their 3m frame began at
09:30.

The download that should have supplied that history never ran:

```
09:22:23 [Candles] TSLA — no local data, fetching 30 days of history
09:22:40 [Candles] Download already in progress — 3 stock(s) queued for next run
09:22:41 [Candles] IBKR download complete — 6 of 6 stock(s) ready
09:22:41 [Candles] All 6 stock(s) are ready for strategy indicators
09:22:41 [Candles] Download already in progress — 3 stock(s) queued for next run   ← re-queued itself
```

Only 4 `[Candles]` lines appear in the whole log after 09:22:41 — the queued batch
(CDW, DG, TSLA) was never started. IBKR was never asked for CDW/DG history.

## Root Cause

The deferred-batch queue drained itself into a dead end.

`IntradayCandleLoader` is a `QThread` that emits `load_complete` from **inside** its `run()`
(`intraday_candle_loader.py:347`), before the thread returns. `AppService._on_candle_load_complete`
drained the queue by calling `_start_intraday_loader(pending)` — but at that moment the
thread was still alive, so the already-running guard (SRD-EXE-006.008) saw
`self._intraday_loader.isRunning()` as True, wrote the same list straight back into
`_pending_candle_symbols`, and returned.

Nothing drained it after that: the drain lived only in `_on_candle_load_complete`, which
fires once per loader run. The batch stayed queued for the rest of the session, and the two
symbols in it went the whole day with no 1m history.

The requirement text of SRD-EXE-006.008 specifies the faulty trigger directly ("In
`_on_candle_load_complete`, after processing results … immediately start a new loader"), so
the defect is in the requirement, not only the code.

## Fix

Drain on the thread's `finished` signal instead, which Qt emits only after `run()` returns:

| File | Change |
|---|---|
| `gui/app_service.py` | New `_on_intraday_loader_finished(loader)` — releases `_intraday_loader` then starts any queued batch; `loader.finished` connects to it, replacing the lambda that only cleared the reference |
| `gui/app_service.py` | Queue-drain block removed from `_on_candle_load_complete` |

The new handler also only clears `_intraday_loader` when it still points at the loader that
finished, so a late `finished` from a superseded loader cannot blank out a newer one and let
two IBKR candle connections run at once.

Logs a new INFO line when the queue drains: `[Candles] Starting queued download for N stock(s)`.

## Verification

`tests/gui/test_app_service_candle_queue_drain.py` — 6 cases (UT-EXE-006.008.M01.T01–T06):
batch is queued while busy; queued batch starts on `finished`; `load_complete` no longer
drains; the busy guard is clear when the drain restarts; a stale loader never clears the
current one; an empty queue is a no-op. 5 of the 6 fail against the pre-fix code.

Full `tests/gui/` + `tests/execution/` suites: 357 passed. `ruff` and `mypy --strict` counts
on `app_service.py` unchanged from baseline (19 / 147, all pre-existing).

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| SRD-EXE-006.008 | Drain trigger must be the loader thread's `finished` signal, not `load_complete` | **Needs user `Reopen`** — currently `Implemented`, which the agent may not edit |
| `gui/app_service.py` | `_on_intraday_loader_finished` added; drain removed from `_on_candle_load_complete` | Done |
| `tests/gui/test_app_service_candle_queue_drain.py` | New regression suite | Done |
| UTCD (EXE) | UT-EXE-006.008.M01.T01–T06 rows | Pending SRD reopen |
| TRACE (EXE) | SRD-EXE-006.008 row → test + RN references | Pending SRD reopen |

## Notes

- Only the *entry* branch logged. Neither symbol held a position, so no exit was missed —
  unlike ISS-EXE-0009. The NaN guard added by that issue is what made this visible at all;
  before it, the condition would have read silently False.
- The router logs this warning on every evaluation cycle with no dedupe
  (`strategy_engine/_router.py:210`), and the message names neither the timeframe nor the bar
  count. Both are worth fixing separately — they are not part of this issue.
- The 3m symptom self-heals about 30 minutes after the open; the 15m one persists until
  roughly 12:15 ET. The underlying data gap does not heal — it lasts until the next
  successful loader run.
