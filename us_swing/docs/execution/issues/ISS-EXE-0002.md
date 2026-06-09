# Issue Report — ISS-EXE-0002

**Tool:** EXE (Execution)
**Severity:** High
**Status:** Resolved
**Date Opened:** 2026-06-08
**Date Resolved:** 2026-06-08
**Reporter:** User (USSwing)
**Resolution:** RN-EXE-1.19.0-20260608

---

## Symptom

A manual buy from the Active Trades panel (click Play → buy) filled, but the
order then vanished: it disappeared from Active Trades, no position opened, and
nothing was written to Trade History. The GUI log showed
`[Orders] Order fill confirmed: 1 share(s) at 418.45` (subject "Order", not the
symbol), while the command window logged
`WARNING [Orders] Received an update for an unknown order — skipping (1780936826644)`.

## Root Cause

A cross-thread race in the order pipeline. `BrokerAdapter.submit()` ran on the
GUI thread and called `broker.place_order()` — which schedules the simulated fill
onto the engine `QThread` via `call_soon_threadsafe` — **before** calling
`OrderIngestion.on_order_accepted()`, which stored the order context on the GUI
thread. The context was keyed by `broker_order_id`.

When the engine thread delivered the fill before the GUI thread stored the
context, `OrderIngestion.on_order_event()` did `self._context.get(broker_order_id)`,
found `None`, logged "unknown order — skipping", and returned early — so no
ledger advance, no `on_entry_fill`, no cycle opened, no lifecycle mark. The
pending signal had already been popped by `execute_signal`, so the row vanished;
Trade History is rebuilt from `trade_cycles`, which had no cycle. The GUI's
"fill confirmed" line still ran (it is a separate listener) but could not resolve
the symbol, so it printed the default subject "Order".

Automated strategy entries did not hit this because the router submits **on the
engine loop thread**, where `call_soon_threadsafe` defers the fill until after
`submit` returns. Only GUI-thread manual submits (`execute_signal`,
`force_exit_cycle`) raced. Introduced in commit `efb612e4` (broker abstraction).

## Diagnosis Evidence

- `1780936826644` is an epoch-millisecond id → confirms the paper `SimBroker`.
- `SimBroker.place_order` schedules `_resolve` inside `place_order`; `BrokerAdapter.submit` records context only afterwards (broker_adapter.py:71-74, pre-fix).
- `IBKRBroker._on_update` echoes `client_ref` on every `OrderEvent` (ibkr.py:102) — so a real broker delivering fills on its socket thread would hit the same race; a GUI-thread-marshalling fix would not be broker-safe.

## Fix

Remove the ordering dependency entirely — register the context **before**
placing the order, keyed by `client_ref` (the unique `signal_id`), which the
adapter knows up front and every `OrderEvent` carries back.

- `OrderIngestion`: `_context` keyed by `client_ref`; new `register(ctx)` called before placement; `on_order_accepted(client_ref, broker_order_id)` backfills the broker id and inserts the NEW `trades` row; `on_order_event` resolves by `event.client_ref`, guards empty refs, backfills `broker_order_id` from the event, and calls the (now idempotent) `insert_trade` before `update_trade_fill`; a `threading.Lock` guards the dict; `discard()` drops a context if placement raises.
- `BrokerAdapter.submit`: build context → `register` → `place_order` (in try/except → `discard` on failure) → `on_order_accepted`.
- `DatabaseManager.insert_trade`: `INSERT ... ON CONFLICT DO NOTHING` (idempotent) so a fill that still races ahead of the acceptance insert is tolerated.

This is broker- and thread-agnostic: identical for `SimBroker` (engine loop) and
live `IBKRBroker` (socket thread).

## Affected Artifacts

| Artifact | Change |
|---|---|
| SRD-EXE-015.002 | No change (stays Implemented) — code now upholds its "insert before fill" intent across threads |
| SRD-EXE-015.003 | No change (stays Implemented) — single broker-agnostic handler preserved |
| `execution/order_ingestion.py` | Context keyed by `client_ref`; `register`/`discard`; backfill; lock; idempotent ensure-insert |
| `execution/broker_adapter.py` | `submit` registers before placing; cleans up on placement failure |
| `db/manager.py` | `insert_trade` idempotent |
| `tests/execution/test_broker_adapter.py` | + `test_fill_arriving_before_acceptance_is_not_dropped` (regression) |

## Known Limitation (pre-existing, out of scope)

A `PARTIAL_FILLED` that is the final fill for an order does not pop the context
(only FILLED/REJECTED/CANCELLED do). Under live IBKR partial-fill streams this is
a slow memory growth, not data loss. Unchanged by this fix; tracked for a future
EXE pass.

## Verification

- `tests/execution/test_broker_adapter.py` — 3 passed (incl. the fill-before-accept regression).
- `test_order_state_machine.py`, `test_trade_cycle_service.py`, `test_user_manager.py`, the 2 `_on_order_event_gui` fill tests — all pass.
- ruff clean; mypy clean on changed files (remaining repo mypy errors are pre-existing and unrelated).

[Class: D · Tool: EXE · Phase: Code]
