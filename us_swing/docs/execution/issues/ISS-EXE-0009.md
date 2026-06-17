# Issue Report — ISS-EXE-0009

**Tool:** EXE (Execution)
**Severity:** High (a strategy-condition exit silently never fires for an open position, so a losing trade can be left open all session)
**Status:** Resolved
**Date Opened:** 2026-06-16
**Date Resolved:** 2026-06-16
**Reporter:** User (manually bought a position that went into loss; the Supertrend exit never triggered live, but appeared as a pending exit only after closing and reopening the tool)
**Resolution:** RN-EXE-1.29.0-20260616 (SRD-EXE-006.013 + SRD-EXE-011.023)
**Related reference:** `docs/execution/ARCHITECTURE_FLOW.md`

---

## Symptom

A position opened intraday with the manual Buy button went into loss. The strategy's
Supertrend **exit** condition should have fired but did not. After the tool was closed and
reopened, the same exit immediately appeared as a pending signal.

Evidence — `~/.usswing/logs/us_swing_2026-06-16.log`:

- Session 1 entry-branch evaluation was failing for the traded names:
  `[Strategy] SUPERTREND entry-expr failed for TER / STX / WDC / LRCX: Insufficient bars for Price('Last')` (19:03–19:06).
- Manual buys filled at 19:43–19:45 (PRU, WDC, LRCX, TER) → 4 open cycles.
- **No exit ever fired and no exit-expr error was logged** for the held symbols across the
  whole session.
- On restart (20:28) the loader logged `[Candles] WDC / LRCX / TER / STX — no local data,
  fetching 30 days of history` — proving these symbols had **zero stored candle history**
  during session 1. Once the full history was downloaded, the Supertrend exit fired.

## Root Cause

Opening a position arms some feeds for the symbol but **not the two candle feeds the
strategy-condition exit depends on.**

When a cycle opens, `TradeCycleService` calls `set_active_symbols` →
`AppService._on_cycle_symbols_changed` (`gui/app_service.py:2759`), which only re-syncs the
**tick** feed (`_sync_tick_subscriptions`). It never:

- starts a historical 1m download for the new symbol (`_start_intraday_loader`), nor
- adds the symbol to the live-bar subscription (`LiveBarWorker.set_symbols`).

The historical download + live-bar set are only (re)computed at three triggers — startup
(`_boot_candle_check`), a screener run (`_on_screener_results_updated`), and a reconcile
(`_on_lifecycle_reconcile_completed`) — never on cycle-open. So a symbol entered intraday
that is **not in the current screened set** (e.g. a manual off-screen buy) gets ticks and is
still evaluated by the engine (`_evaluate_ctx` adds open-cycle symbols, `_engine.py:211-219`),
but its candle frame from `load_execution_frames` is empty/sparse.

The exit indicator then fails **silently**: `Price()` raises on too few bars (hence the
logged *entry* failures), but the ATR-based `SUPERTREND` (`_supertrend_value`,
`_evaluator.py:246`) returns **NaN** when `talib.ATR` has fewer than `length` bars, and
`price < NaN` collapses to `False`. So the exit branch runs every cadence but can never
trigger, and nothing is logged. A restart re-downloads the full day's 1m history (the symbol
is now in `carryover`), the frame is complete, Supertrend computes a real value, and the
exit fires.

Summary of what is armed when a position opens intraday off-screen:

| Feed | Armed on cycle-open? |
|---|---|
| Ticks (`LiveTickWorker`) | ✅ yes (`_sync_tick_subscriptions`) |
| Strategy evaluation (`_strategy_tick_loop`) | ✅ yes (via `open_cycles_for_strategy`) |
| Historical download (`IntradayCandleLoader`) | ❌ no |
| Live bars (`LiveBarWorker` 3m/15m) | ❌ no |

This also explains why tick-based exits (target/SL/trailing, path II) would still work for
the same position — they need only the live price, not candle frames.

## Proposed Fix

**Part A — arm the candle feeds on cycle-open (primary).**
Make opening a position symmetric with the tick path. In `_on_cycle_symbols_changed`, union
open-cycle symbols into `_filtered_symbols` and, for any newly-open symbol not already
covered:
1. trigger a historical 1m download via `_start_intraday_loader` (delta-fetch is idempotent), and
2. add it to the live-bar subscription via `LiveBarWorker.set_symbols`.

This guarantees every open position has historical + live candle data for as long as it is
held, regardless of whether it is in today's screened set.

**Part B — fail loudly on insufficient data (defense in depth).**
An exit condition that *cannot* be computed must not silently read as "do not exit." Options
(to be settled in the SRD/DD):
- gate strategy evaluation for a symbol on candle readiness (`check_candle_readiness`), and/or
- have ATR-based indicators raise `EvaluatorError("insufficient bars")` (like `Price()`
  already does) instead of returning NaN, so the condition is logged as un-evaluable rather
  than quietly false.

Part A removes the cause; Part B ensures any future data gap surfaces instead of hiding a
missed exit.

## Affected Artifacts (proposed)

| Artifact | Change |
|---|---|
| FO-EXE-006 / FO-EXE-009 | Confirm parent FO for "open positions are always candle-armed" before writing SRD |
| SRD-EXE-006.NNN | **New (Draft)** — opening a cycle arms historical + live candle feeds for its symbol |
| SRD-EXE-011.NNN | **New (Draft)** — an un-evaluable exit indicator is logged/skipped, never silently false |
| DD-EXE-006.NNN.D01 | **New** — cycle-open → loader + live-bar resubscribe design |
| `gui/app_service.py` | `_on_cycle_symbols_changed` also arms loader + live-bar feeds |
| `execution/strategy_engine/_evaluator.py` | ATR-based indicators signal insufficient data (Part B) |
| UTCD | new positive/negative cases: cycle-open arms feeds; exit on insufficient bars is surfaced not swallowed |

## Notes / Deviations

- **`carryover` already includes today's positions** (`open_system_position_symbols`,
  `monitoring_session/_repository.py:278`) — so the architecture *intends* to monitor open
  positions. The defect is purely the missing cycle-open trigger, not the keep-set contents.
- **Separate latent bug (not this incident):** `pending_signal_dismissed` is wired only to a
  GUI refresh + tick re-sync (`app_service.py:1202`), never to `StrategyEngine.on_pending_dismissed`
  (`_engine.py:368`), so dismissing a pending signal never clears the engine's `in_flight`
  flag. This did not cause ISS-EXE-0009 (the entry condition kept throwing, so `in_flight`
  was never set for the traded symbols), but it is a real gap worth its own issue.
- Source reliability is a contributing amplifier: session 1 fell back to Yahoo Finance
  (IBKR refused), which caps 1m history and validates only 3m — narrowing data further for
  newly-added symbols.
