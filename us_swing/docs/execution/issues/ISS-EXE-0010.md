# Issue Report — ISS-EXE-0010

**Tool:** EXE (Execution)
**Severity:** High (two exit orders are placed for one position; harmless in paper mode but in live mode the second SELL would oversell — selling shares no longer held, risking an unintended short or a broker reject)
**Status:** Resolved
**Date Opened:** 2026-06-17
**Date Resolved:** 2026-06-17
**Reporter:** User (saw `[Orders] Could not close the trade cycle for TER → InvalidStateTransitionError` in the June 16 log)
**Resolution:** RN-EXE-1.30.0-20260617 (SRD-EXE-011.024, SRD-EXE-011.025, SRD-EXE-012.014; DD-EXE-011.024.D01)
**Related reference:** `docs/execution/ARCHITECTURE_FLOW.md`, ISS-EXE-0009 (Notes — `in_flight` gap)

---

## Symptom

An ERROR with a full traceback appeared in `~/.usswing/logs/us_swing_2026-06-16.log`:

```
[Orders] Could not close the trade cycle for TER
...
InvalidStateTransitionError: no open SUPERTREND/TER cycle accepts exit_order_id='1781621880517'
```

The app did not crash — the error is caught by the try/except in
`order_ingestion._close_cycle` (`order_ingestion.py:294-306`); it only logs.

## Timeline (from the June 16 log)

| Line | Time (UTC) | Event | Open cycles |
|---|---|---|---|
| 139–140 | 19:45:45 | TER **BUY** accepted (order …246) | 3 → **4** |
| 154 | 20:28:00 | TER still held | **4** |
| 205–206 | 23:28:18 | TER **SELL** accepted — order **…516**; cycle closed | 4 → **3** |
| 207–213 | 23:28:29 | **ERROR** — exit fill for order **…517** has no open cycle | 3 |
| 215 | 23:28:29 | TER **SELL** accepted — order **…517** (acceptance logged *after* its own fill) | 3 |
| 216 | 23:29:07 | SUPERTREND entry blocked for TER — rex limit reached | 3 |

The cycle count holds at 4 from 19:45 to 23:28:18, so the TER cycle was **closed by
order …516**, not earlier in the session. Two separate SELL orders (**…516** and
**…517**, sequential ids) were placed for the same single-share TER position near
session end. …516 closed the cycle; …517's fill 11 s later had nothing to close.

## Root Cause

A position has **multiple, independent ways to be exited, and exiting via one route
does not invalidate the others.** No exit-submission path checks that the cycle is still
open before submitting, so a second exit order goes out for a position already flat.

**Primary trigger — stale pending exit signal (confirmed on PRU).**
When a strategy exit fires in manual-confirm mode it parks as a **pending EXIT signal**
in `PendingSignalStore`, shown in Active Trades with a ► (execute) button. The same
open position also shows the red **square (force-exit)** button. These are two live exit
routes for one position:

1. The user force-exits via the square → `force_exit_position` (`app_service.py:2235`)
   submits the exit and the cycle goes `OPEN → CLOSING → CLOSED`.
2. **The pending exit signal is never removed.** `PendingSignalStore` exposes only
   `add` / `dismiss` / `execute` / `list` (`pending_signal_store.py`); `dismiss` is wired
   only to the user's X button and `execute` only to the ► button. Nothing clears a
   pending signal by `(strategy, symbol)` when the position closes by another route.
3. The stale ► remains clickable. `execute_signal` (`app_service.py:1970-1983`) pops the
   signal and calls `_submitter.submit(...)` **with no open-cycle guard** → a second SELL
   order is placed against a position already flat → orphan fill → the error.

Screenshot evidence (Active Trades): PRU appears as both an `OPEN` row (qty 4, square
button) and a `PENDING` row (qty 4, ► button) at the same time.

**Underlying reason no guard catches it.** The three programmatic exit paths use two
different, non-shared duplicate guards, and none checks open-cycle state at submission:

| Path | Mechanism | Duplicate guard |
|---|---|---|
| I — Strategy-condition exit (Supertrend) | router `evaluate` → queue; in manual mode parks as pending signal | sets/checks `ctx.in_flight` |
| II — Tick exit (target / SL / trailing) | `_check_exit_triggers` → `ExitTrigger` → `force_exit_position` | **none** — submits directly (`app_service.py:2235-2280`) |
| III — Router force-exit (end_time / square-off / emergency) | `_force_exit` (`_router.py:451`) | sets/checks `ctx.in_flight` |
| IV — Pending-signal execute (► button) | `execute_signal` → `_submitter.submit` | **none** — submits directly (`app_service.py:1970`) |

Paths II and IV neither set nor check `ctx.in_flight`, so they can fire an exit for a
symbol another path is already exiting (and the pending signal of Path I lingers after
Path II/III closes the position).

This is compounded by **`CLOSING` counting as "open."** `open_cycles()`,
`has_open_cycle()`, and `open_cycles_for_strategy()` all filter on
`NON_TERMINAL_STATE_VALUES` (`trade_cycle/_repository.py:96,156,166`), which includes
`CLOSING`. So even after the cycle moves `OPEN→CLOSING` and …516 is submitted, the second
route still sees the cycle as open and submits …517. The only "an exit is already out"
marker — `exit_order_id is None` — is checked at the **sink** (`on_exit_fill`,
`_service.py:298-310`), never at submission time.

When …517's fill arrives, `on_exit_fill` finds no cycle with that `exit_order_id` and no
open SUPERTREND/TER cycle (it is now CLOSED), so it raises `InvalidStateTransitionError`
(`_service.py:307`). The raise is correct defensively, but it surfaces as an alarming
ERROR + traceback for what is a benign duplicate fill.

## Proposed Fix (two layers — settle scope in SRD/DD)

**Part A — prevent the duplicate exit order at submission (primary).**
Make every exit route idempotent per open cycle, so a position that is already
exiting/flat cannot receive a second exit order. Two complementary changes:
- **Invalidate the stale pending signal.** When a cycle leaves `OPEN` (force-exit, tick
  exit, router square-off, or auto-exit), clear any pending EXIT signal for the same
  `(strategy, symbol)` from `PendingSignalStore`. Add a `dismiss_for(strategy, symbol)`
  (or `invalidate_open`) method and wire it to cycle-close / `CycleClosed`. This removes
  the stale ► the user could otherwise click.
- **Guard submission state.** Have `force_exit_position`, `_force_exit`, and
  `execute_signal` treat a cycle already in `CLOSING`/closed (or whose symbol is
  `in_flight`) as "exit already in progress" and return without submitting — while still
  allowing the path's own first submit. Consider a single shared in-flight registry (or a
  persisted "exit submitted" marker on the cycle) so all routes read one source of truth.

**Part B — fail soft at the sink (defense in depth).**
In `on_exit_fill`, when no open cycle is found but a recently-CLOSED cycle for the same
`(strategy_id, symbol)` exists in today's session, log a WARNING
(`[Orders] Ignoring duplicate exit fill for TER — cycle already closed`) and return,
instead of raising `InvalidStateTransitionError`. This stops the scary ERROR + traceback
for a duplicate fill without masking a genuine missing-cycle bug.

Part A removes the cause; Part B keeps the symptom benign if any future path slips through.

## Affected Artifacts (proposed)

| Artifact | Change |
|---|---|
| FO-EXE-011 / FO-EXE-012 | Confirm parent FO for "a position never receives two exit orders" before writing SRD |
| SRD-EXE-011.NNN | **New (Draft)** — exit submission is idempotent per open cycle across all three exit paths |
| SRD-EXE-012.NNN | **New (Draft)** — a duplicate/orphan exit fill is logged as a warning, never an error |
| DD-EXE-011.NNN.D01 | **New** — shared in-flight / CLOSING guard design across tick + router exit paths |
| `execution/pending_signal_store.py` | new `dismiss_for(strategy, symbol)` to clear stale exit signals on cycle-close (Part A) |
| `gui/app_service.py` | `force_exit_position` / `execute_signal` guard against a cycle already exiting; clear matching pending signal on cycle-close (Part A) |
| `execution/strategy_engine/_router.py` | align `_force_exit` with the shared guard (Part A) |
| `execution/trade_cycle/_service.py` | `on_exit_fill` soft-handles a duplicate orphan fill (Part B) |
| UTCD | new cases: closing a cycle removes its pending exit signal; executing a stale pending exit is suppressed; orphan duplicate fill logs WARNING not ERROR |

## Notes / Deviations

- This is the same `in_flight` gap family flagged in ISS-EXE-0009 Notes (line 110–114):
  Path II / tick exits live outside the router's `ctx.in_flight` bookkeeping.
- In **paper mode** the duplicate is cosmetic (the orphan fill is rejected at the sink). In
  **live mode** the second SELL would reach the broker against a position already flat →
  oversell / unintended short / reject. Hence Severity High despite the caught error.
- The …517 acceptance logged *after* its own fill (lines 207 vs 215) reflects SimBroker's
  fill callback firing ahead of the acceptance callback — not itself the bug, but it is why
  the error appears before the second "Accepted" line.
