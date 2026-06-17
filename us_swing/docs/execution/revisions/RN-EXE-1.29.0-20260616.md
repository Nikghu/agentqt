# Revision Note — RN-EXE-1.29.0-20260616

**Version:** 1.29.0
**Date:** 2026-06-16
**Tool:** EXE
**Artifact:** SRD-EXE-006.013, SRD-EXE-011.023
**Type:** Bugfix (ISS-EXE-0009)

---

## Summary

A position opened intraday with the manual Buy button (strategy `SUPERTREND`,
manual mode) went into loss and never exited, even though its Supertrend exit
condition should have fired; the exit only appeared as a pending signal after the
tool was closed and reopened (observed 2026-06-16 for WDC / LRCX / TER).

Root cause was two linked defects. (1) Opening a trade cycle armed the **tick**
feed for the symbol but not the two **candle** feeds the strategy-condition exit
depends on — the historical download (`IntradayCandleLoader`) and the live 3m/15m
subscription (`LiveBarWorker`). Those were only (re)armed at startup / screener
run / reconcile, never on cycle-open. So a held off-screen symbol was evaluated by
the engine against an empty/sparse candle frame. (2) When an indicator could not
be computed for lack of bars, the ATR-based `SUPERTREND` returned `NaN`, and
`price < NaN` collapsed to `False`, so the un-computable exit silently read as "do
not exit" with no log. A restart re-downloaded the full day's 1m history, after
which the indicator computed and the exit fired.

---

## Behaviour Changes

- **Open positions are candle-armed.** When a trade cycle opens for a symbol not
  already in the screened/keep set, its historical download and live 3m/15m
  subscription are started immediately — symmetric with the existing tick feed —
  so a held position always has data for indicator evaluation.
- **Un-computable indicators surface instead of hiding.** An indicator that
  returns `NaN` (insufficient bars) now raises `EvaluatorError`. The router
  already catches this on both the entry and exit branch, logging
  `WARNING [Strategy] … exit-expr failed …` and publishing `StrategyErrored`, so a
  missed exit is visible rather than silently treated as false.
- Unchanged: tick-based exits (target / stop-loss / trailing), screener-driven
  arming, and any indicator that has enough bars to compute a finite value.

---

## Code Changes

| File | Change | SRD |
|---|---|---|
| `gui/app_service.py` | New `_arm_candle_feeds_requested` signal (connected in the trade-cycle init block). `_on_cycle_symbols_changed` computes just-opened symbols not already covered and emits it; new GUI-thread slot `_arm_candle_feeds` unions them into `_filtered_symbols`, calls the existing `_start_intraday_loader` (delta-fetch, idempotent), and `LiveBarWorker.set_symbols` when a worker is running. Marshalled to the GUI thread because the callback fires on the trade-cycle background thread (the loader creates `parent=self` QThreads). | SRD-EXE-006.013 |
| `execution/strategy_engine/_evaluator.py` | Added `import math`; the `_eval` FUNC branch raises `EvaluatorError` when an indicator returns `NaN`, so an un-computable condition can no longer read as a silent `False`. | SRD-EXE-011.023 |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-006.013 | Opening a trade cycle arms the historical + live candle feeds for its symbol, even when off-screen | Implemented |
| SRD-EXE-011.023 | An indicator that cannot be computed for lack of bars raises `EvaluatorError` instead of returning NaN→false | Implemented |

---

## Tests

| Check | Result |
|---|---|
| `tests/gui/test_app_service_candle_arming.py` — UT-EXE-006.013.M01.T01–T04 (off-screen open arms both feeds; already-covered no-op; no-worker download-only; signal marshal) | 4 passed |
| `tests/execution/test_strategy_evaluator.py` — UT-EXE-011.001.M03.T10–T13 (short SUPERTREND/RSI/EMA raise; finite result passes guard) | 4 passed |
| Full `tests/execution` + `tests/gui` | 235 passed, 21 pre-existing failures (identical with changes stashed — candle-loader / tick-worker / app-service-tick / function-map count) |
| `ruff` | clean on `_evaluator.py` + both test files; `app_service.py` error count unchanged (16 = 16, all pre-existing) |
| `mypy --strict` | no new errors in `_evaluator.py` (pre-existing GUI-module debt unchanged) |

---

## Notes / Deviations

- Part A removes the cause (held positions always have candle data); Part B is the
  safety net that makes any remaining data gap loud. Part B does not force an exit —
  it surfaces the un-computable condition and skips that pass; the position stays
  open with a logged warning.
- `carryover` already includes today's open positions
  (`open_system_position_symbols`), so the architecture intended to monitor open
  positions; the only missing trigger was on cycle-open, which this change adds.
- **Separate latent bug (not this incident):** `pending_signal_dismissed` is never
  wired to `StrategyEngine.on_pending_dismissed`, so dismissing a pending signal
  does not clear the engine `in_flight` flag. Flagged in ISS-EXE-0009 Notes for a
  future issue; it did not cause this incident (the entry condition kept throwing,
  so `in_flight` was never set for the traded symbols).

---

**Commit:** pending — Refs: MD-EXE-006.013.M01, MD-EXE-011.001.M03
