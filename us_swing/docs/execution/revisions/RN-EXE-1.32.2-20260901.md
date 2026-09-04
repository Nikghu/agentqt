# Revision Note — RN-EXE-1.32.2-20260901

**Tool:** EXE
**Version:** 1.32.2
**Date:** 2026-09-01
**Type:** bugfix
**Author:** Claude Opus 5 under user direction
**Phase:** Candle-loader deferred-batch queue (ISS-EXE-0011)

---

## Summary

The user asked why the live log kept repeating
`[Strategy] SUPERTREND entry-expr failed for CDW / DG: SUPERTREND: insufficient bars to
compute (NaN)`. The indicator was fine. Two of the three traded symbols had **zero** stored
1m history because their candle download was queued behind a running one and then never
started.

## The fault

`IntradayCandleLoader` is a `QThread`, and `load_complete` is emitted from inside its `run()`
(`intraday_candle_loader.py:347`) — before the thread returns. The queue drain lived in
`_on_candle_load_complete`, so when it called `_start_intraday_loader(pending)`, the
already-running guard from SRD-EXE-006.008 still saw `isRunning() is True`, wrote the same
symbol list back into `_pending_candle_symbols`, and returned.

The drain fires once per loader run, so nothing ever picked the batch up again. From today's
log:

```
09:22:40 [Candles] Download already in progress — 3 stock(s) queued for next run
09:22:41 [Candles] All 6 stock(s) are ready for strategy indicators
09:22:41 [Candles] Download already in progress — 3 stock(s) queued for next run   ← re-queued itself
```

Four `[Candles]` lines follow in the entire log. CDW and DG ended the session with 0 rows in
`price_1m`, so their 3m frame held only the 8 live bars since the 09:30 open, against the 11
that `ATR(10)` needs.

The requirement itself names the wrong trigger — SRD-EXE-006.008 says the restart happens
"in `_on_candle_load_complete`, after processing results". So this is a requirement defect,
not only a coding slip.

## The fix

Drain on `QThread.finished`, which Qt emits only after `run()` has returned. New
`_on_intraday_loader_finished(loader)` replaces the lambda that previously did nothing but
null out the reference: it releases `_intraday_loader`, then starts any queued batch.

It clears `_intraday_loader` only when that attribute still points at the loader that
finished. A `finished` signal is delivered queued, so a superseded loader's signal can land
after a newer loader has been assigned; without the identity check it would blank out the
live reference and let a second IBKR candle connection start alongside the first.

A queued restart is now visible in the log: `[Candles] Starting queued download for N stock(s)`.

## Deliberately not fixed

- **`[Strategy] … entry-expr failed` has no dedupe** (`strategy_engine/_router.py:210`). It
  logs every evaluation cycle — roughly once a minute per symbol for 25 minutes today. The
  message also names neither the timeframe nor the bar count, which is what made the
  diagnosis slower than it should have been. Both belong in their own change, not folded in
  here.
- **Symbols already missing history are not back-filled by this fix.** The next successful
  loader run repairs them; nothing re-checks mid-session.

## Files Changed

| File | Change |
|---|---|
| `src/us_swing/gui/app_service.py` | `_on_intraday_loader_finished` added; queue drain removed from `_on_candle_load_complete`; `loader.finished` rewired |
| `tests/gui/test_app_service_candle_queue_drain.py` | New — 6 cases |
| `docs/execution/issues/ISS-EXE-0011.md` | New issue report |

## Verification

- `pytest us_swing/tests/gui us_swing/tests/execution` — **357 passed**
- New suite alone — 6 passed; **5 of the 6 fail** when the `app_service.py` change is stashed,
  confirming they pin the actual defect
- `ruff` on `app_service.py` — 19 findings, byte-identical to the pre-existing baseline
  (E402 imports, unused `math`, `E741`); new test file clean
- `mypy --strict` on `app_service.py` — 147 errors, identical to baseline; none in the edited
  region

## Outstanding

- **SRD-EXE-006.008 still describes the broken trigger.** Its status is `Implemented`, which
  the agent may not edit under the SRD status guard. The user needs to set it to `Reopen`
  before the requirement text, the UTCD rows (UT-EXE-006.008.M01.T01–T06) and the TRACE row
  can be corrected.
- Unchanged from RN-EXE-1.32.1: Phase 4 live smoke test still not run (TODO T19), TODO T20–T22.
