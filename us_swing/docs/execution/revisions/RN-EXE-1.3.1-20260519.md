# Revision Note — RN-EXE-1.3.1-20260519

**Version:** 1.3.1
**Date:** 2026-05-19
**Tool:** EXE — Execution & Risk Management
**Artifact:** FO-EXE-008 / MD-EXE-008.001.M01
**Type:** Bugfix / Refactor

---

## Summary

Fixed a thread-safety race in `LiveTickWorker.set_contracts()`: the previous implementation called `time.sleep(_SUB_PAUSE)` inside a `threading.RLock`-held block on whatever thread invoked `set_contracts`, which could be the Qt main thread. Replaced the blocking path with `asyncio.run_coroutine_threadsafe(_apply_contracts(...), loop)` so all IBKR subscription work executes exclusively inside the asyncio event loop's thread. The `import time` dependency is removed.

---

## Modified File

| File | Module ID | Change |
|---|---|---|
| `execution/live_tick_worker.py` | MD-EXE-008.001.M01 | Extract `_apply_contracts` async coroutine; `set_contracts` schedules via `run_coroutine_threadsafe`; store loop ref in `self._loop`; remove `time.sleep` |

---

## Key Design Decisions

- **`asyncio.run_coroutine_threadsafe`** — ensures `ib.reqMktData()` and `ib.cancelMktData()` always run on the ib-insync event loop thread, satisfying ib-insync's thread-affinity requirement.
- **Lock scope narrowed** — the diff/cancel pass retains `_lock` for `_active` / `_tickers` mutation; the `asyncio.sleep(_SUB_PAUSE)` pacing between batches runs outside the lock to avoid holding it during I/O.
- **`self._loop` cached at connect time** — avoids calling `asyncio.get_running_loop()` from the wrong thread on every `set_contracts` call.

---

## Issues Resolved

None (pre-emptive fix — symptom was potential Qt main-thread stall during initial subscription when > 10 symbols were queued).

---

## Test Coverage

16 existing unit tests (`tests/execution/test_live_tick_worker.py`, T01–T16) — status **Pending re-run** against refactored implementation.

---

## SRDs Satisfied

SRD-EXE-008.001–006 remain Implemented (no requirement change — this is an implementation correctness fix).
