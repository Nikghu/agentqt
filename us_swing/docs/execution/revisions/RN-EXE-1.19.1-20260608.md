# Revision Note — RN-EXE-1.19.1-20260608

**Tool:** EXE
**Version:** 1.19.1
**Date:** 2026-06-08
**Author:** Claude Opus 4.8 under user direction
**Phase:** Bug fix — ISS-EXE-0002 (manual-buy fill dropped as "unknown order")
**Note:** Renumbered to 1.19.1 — version 1.19.0 was concurrently used on `main` (PR #36, orphaned-ledger heal).

---

## Summary

Fixes a cross-thread race that dropped fills for **manual** orders (Active Trades
Play/buy, force-exit). The order context was stored keyed by `broker_order_id`
**after** `place_order` had already scheduled the fill onto the engine thread. When
the fill arrived first, `OrderIngestion.on_order_event` found no context, logged
"Received an update for an unknown order — skipping", and dropped it — so no cycle
opened, the signal vanished from Active Trades, and Trade History stayed empty.

The fix removes the ordering dependency: the context is now **registered before the
order is placed**, keyed by `client_ref` (the unique `signal_id`) which the adapter
knows up front and every broker echoes back on each `OrderEvent`. Automated strategy
entries were never affected (the router submits on the engine loop thread); only
GUI-thread manual submits raced.

## Root Cause

`BrokerAdapter.submit` (GUI thread): `place_order` → schedules `_resolve` on the
engine `QThread` via `call_soon_threadsafe` → returns; **then** `on_order_accepted`
stored the context. The engine thread could run the fill before the GUI thread
stored the context. Context was keyed by `broker_order_id`, which was only known
after `place_order`. Introduced in commit `efb612e4`. Full analysis in ISS-EXE-0002.

## Design

- `client_ref` (= `signal_id`) is unique per order and is carried on every
  `OrderEvent` by both `SimBroker` and `IBKRBroker` (verified ibkr.py:102), so it is
  a broker- and thread-agnostic key.
- Register context **before** `place_order`; backfill the broker-assigned id at
  acceptance and again defensively on the first event.
- `insert_trade` is made idempotent so a fill that still races ahead of the
  acceptance insert cannot be clobbered or lost.

## Code Changes

| File | Change | MD |
|---|---|---|
| `execution/order_ingestion.py` | `_context` keyed by `client_ref`; add `register()` (pre-placement) and `discard()`; `on_order_accepted(client_ref, broker_order_id)` backfills id + inserts NEW row; `on_order_event` resolves by `event.client_ref`, guards empty refs (under lock), backfills id from event, ensure-inserts before `update_trade_fill`; `threading.Lock` guards the dict; `_forget(client_ref)` pops on terminal events. | MD-EXE-015.001.M01 |
| `execution/broker_adapter.py` | `submit`: build → `register` → `place_order` (try/except → `discard` on failure) → `on_order_accepted(signal_id, id)`; `_build_context` no longer takes `broker_order_id`. | MD-EXE-015.002.M01 |
| `db/manager.py` | `insert_trade` uses SQLite `on_conflict_do_nothing()` (idempotent). | MD-INF-004.001.M01 |
| `gui/app_service.py` | `_on_order_event_gui` fill-confirmed log now shows the side — resolves the matching `trades` row and appends Buy/Sell (e.g. `[Orders] V Buy fill confirmed: 1 share(s) at 319.23`). | MD-EXE-016.001.M03 |

## Acceptance — Status

| Behaviour | Status | Evidence |
|---|---|---|
| Fill arriving before acceptance is ingested, not dropped | ✅ | `test_fill_arriving_before_acceptance_is_not_dropped` |
| Normal entry/exit flow unchanged (NEW → FILLED, cycle opens/closes) | ✅ | `test_entry_signal_flows_through_to_trades_and_cycle`, `test_exit_signal_closes_cycle` |
| Works for any broker (client_ref echoed by Sim + IBKR) | ✅ | ibkr.py:102 static check; Sim contract |
| No double-insert / clobber on race | ✅ | idempotent `insert_trade` + `_new_trade_record` |
| GUI fill-confirm path still resolves symbol | ✅ | the 2 `_on_order_event_gui` tests pass |

## Tests

| Check | Result |
|---|---|
| `tests/execution/test_broker_adapter.py` | 3 passed (incl. regression) |
| `test_order_state_machine.py`, `test_trade_cycle_service.py`, `test_user_manager.py` | Pass |
| `tests/gui/test_app_service_tick.py` (order-event/fill) | 2 passed |
| Full execution + integration suites | 171 passed; 13 failures all pre-existing (candle loader, live tick worker, strategy engine/evaluator — verified identical at base commit) |
| `ruff` | Clean on changed files |
| `mypy --strict` | No new errors in changed files (remaining repo errors pre-existing) |

## Known Limitation (pre-existing, out of scope)

`PARTIAL_FILLED` that is the final fill does not pop the context (only
FILLED/REJECTED/CANCELLED do) — a slow memory growth under live partial-fill
streams, not data loss. Unchanged here; tracked for a future EXE pass.

## SRD Note

SRD-EXE-015.002 / .003 remain `Implemented` — this was a code divergence from
their stated intent ("insert completes before fill events are processed"; one
broker-agnostic handler), not a spec change. The context-keying mechanism is an
unspecified implementation detail. No SRD/DD/UTCD cascade required.

---

**Commit:** branch `fix/inf-drop-orphaned-watchlist` (pending) — Refs: MD-EXE-015.001.M01
