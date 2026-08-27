# Revision Note — RN-EXE-1.32.0-20260827

**Tool:** EXE
**Version:** 1.32.0
**Date:** 2026-08-27
**Type:** bugfix
**Author:** Claude Opus 5 under user direction
**Phase:** IBKR_Live_Execution_Plan Phases 1–4 + F4 + stale-test revival

---

## Summary

Closed Phases 1–4 of `IBKR_Live_Execution_Plan.md`, the F4 duplicate-entry guard
from the T15 audit, and revived 21 long-dead tests. Phase 0 shipped separately
(`RN-GUI-1.4.0-20260826`, `T15_Record_Resolution_Audit.md`).

The through-line: an order that did not fill cleanly used to strand its symbol.
Four separate faults each produced the same outcome — a symbol stuck `in_flight`
with its capital reserved and no event ever coming to free it.

| PR | Phase | Fault closed |
|---|---|---|
| #60 | 1 | Reject/cancel never reached the engine |
| #61 | 2 | Ledger rows always tagged `"paper"` |
| #62 | 3 | IBKR outcomes mis-read three ways |
| #63 | 4 | Orders placed into a dead socket |
| #64 | F4 | Manual entry could open a duplicate cycle |
| #65 | — | 21 stale tests revived |

---

## Phase 1 — reject and cancel feedback (PR #60)

`order_ingestion` updated the ledger on REJECTED/CANCELLED, called `_forget`, and
returned. The engine was never told, so the symbol stayed `in_flight` with its
capital reserved for the rest of the session.

The consumer chain already existed and had **zero producers**:
`RejectEvent → engine.on_order_reject → _apply_reject → router.on_order_reject`,
which discards `in_flight`, calls `risk.release`, and re-checks quiesce. Nothing
ever constructed a `RejectEvent`.

- `order_ingestion` gained a **required** `reject_sink` and `_notify_reject()`
- the router's dispatch-exception handler now rolls back, covering the
  submit-raised / TWS-stall leak that previously only logged

An exit reject still leaves the cycle OPEN — the stock is held, so the exit has to
stay retryable. Already correct via the `is_entry` guard; now tested.

**Deviations from the plan, both deliberate:** one sink instead of the planned
`reject_sink` + `cancel_sink` (both would have wired to the same handler with
identical lambdas); and `reject_sink` is required rather than defaulting to
`None`, because an optional sink silently does nothing — the exact failure this
phase removes.

## Phase 2 — real mode on ledger rows (PR #61)

Records were stamped `"paper"` whatever the mode, while the account poller tags
its positions `"live"` (`app_service.py:290`). A live session kept two disagreeing
sets of records and every mode-filtered view hid the live ones.

Four values replaced with the active user's mode: `mode_provider` (which fixes the
ledger end to end — it feeds `OrderContext.mode` → `TradeRecord.mode`), the three
rehydrated rows, `get_active_strategy_positions`, and `_CyclePositionSource`.

Two `"paper"` literals kept deliberately: the first-run default profile, and the
fallback `build_broker` call when TWS is unreachable.

**TODO T7 closed, not actioned** — `insert_trade_with_anchor` no longer exists
anywhere; the broker refactor had already routed the ledger through `OrderContext`.

## Phase 3 — IBKR status mapping (PR #62)

Three faults in `broker/ibkr.py`:

1. **`PendingCancel` treated as terminal.** It is a cancel in progress, not an
   outcome. Mapping it to CANCELLED popped `client_ref`, so a cancel that lost the
   race and filled anyway produced a `Filled` with no reference — which ingestion
   drops. The shares moved at IBKR and the app recorded nothing.
2. **Margin rejections invisible.** The gateway only listened to
   `trade.statusEvent`; TWS reports margin and risk rejections *solely* through
   `errorEvent`. Phase 1 built the path that clears a symbol on rejection, but for
   margin rejects no event existed to send down it.
3. **`reason` hardcoded `""`** — every rejection logged "no reason given".

Order-scoped codes now map: 103/201 → rejection, 202 → cancel. Everything else is
ignored — `errorEvent` is account-wide chatter (399 order notices, 2104/2106/2158
data-farm messages) and rejecting on those would kill healthy orders. Errors for
order ids this gateway did not place are ignored too.

`_error_to_update` and `_reason_from_trade` are module-level pure functions, so the
reqId filter and code map carry real coverage without TWS.

## Phase 4 — liveness gate (PR #63)

`IBKRClientGateway._require_live()` raises `BrokerConnectionError` before submit or
cancel touch the socket; `IBKROrderConnection.is_live()` delegates to the client.

Raising rather than returning a sentinel is the point: the router's dispatch
handler catches `Exception` and rolls back, so a refused placement clears
`in_flight` via the Phase 1 path.

**Order pacing deliberately not implemented.** `broker/pacing.py` is the
historical-data limiter (50 per 600 s, awaited before every `req_historical_data`).
Routing orders through it would apply the wrong rule and block the 51st order in
0.5 s busy-wait sleeps — an exit carrying a stop loss could be held for minutes.
It is also `async` while `_place` is sync. Recorded in the audit doc.

## F4 — duplicate manual entry (PR #64)

`execute_signal` guarded EXIT but not ENTRY. With two cycles of 10 and 5 on one
pair, `_router._open_cycle_qty` sizes an automatic exit from the **first** match,
so a target or stop sells 10 and silently leaves 5 held.

Reachable through a narrow race: `on_order_event` calls `fill_sink` (clearing
`in_flight`) *before* `_open_cycle` writes the row, so a bar evaluated in that gap
passes both router guards.

There is **no manual "add to position" feature** — `active_cycles_panel` uses
`sig.qty_recommended` and the user cannot type a quantity. The race was the only
way in.

## Test revival (PR #65)

21 failures that had become background noise. None was a broken feature — all
asserted against APIs that had moved, so Market Watch, tick subscription and the
candle loader had no working coverage.

- **9** — Market Watch rewritten from Yahoo indices to four ETFs
- **6** — `set_contracts` became a router; the diff moved to `_apply_contracts`
- **5** — date decay against a 30-day rolling window, plus timeframes 3m/5m/1h → 3m/15m
- **1** — expected 14 indicators; four BOSS/BOS stubs were removed in `d6c4f4db`

Two findings: the candle tests were fast *because* they were broken (aggregation
was trivial on an empty fetch), and the 24 000-bar fixture was sized for the old 1h
timeframe — 6 000 covers 15m, cutting 92 s to 28 s. And
`test_on_pending_tickers_no_emit_when_both_nan` was passing for the wrong reason.

---

## Files Changed

| File | Change |
|---|---|
| `execution/order_ingestion.py` | `RejectSink`, required `reject_sink`, `_notify_reject` |
| `execution/strategy_engine/_router.py` | rollback on dispatch exception |
| `execution/ibkr_order_connection.py` | `is_live()` |
| `broker/ibkr.py` | `PendingCancel` mapping, `errorEvent`, `reason`, `_require_live` |
| `gui/app_service.py` | `reject_sink` wiring, mode threading, ENTRY guard |
| `tests/execution/test_order_ingestion.py` | New — 10 tests |
| `tests/gui/test_app_service_mode_threading.py` | New — 8 tests |
| `tests/broker/test_broker_contract.py` | +15 (equivalence, mapping, liveness) |
| `tests/gui/test_app_service_duplicate_exit.py` | +5 (F4) |
| `tests/execution/test_strategy_router.py` | +3 (rollback) |
| 4 stale test files | revived |
| `docs/execution/Phase4_Live_Smoke_Test.md` | New — runbook |
| `docs/execution/T15_Record_Resolution_Audit.md` | F4 + Phase 4 status |

## Verification

- gui + execution + broker: **380 passed, 0 failed** (was 357 passed / 21 failed)
- `ruff` per-file counts at or below their HEAD baselines throughout
- `mypy --strict` clean on every changed source file; `app_service.py` unchanged at
  its pre-existing 38

Every phase was checked against the same 21-failure baseline before the revival, so
no regression hid behind it.

## Outstanding

- **Phase 4 live smoke test — NOT RUN.** Deferred by the user 2026-08-27; runbook
  at `docs/execution/Phase4_Live_Smoke_Test.md`. The only part of the plan that
  cannot be proven without a real TWS.
- **F5** — a partial unique index on `(strategy_id, symbol)` for non-terminal
  states would make the single-cycle invariant structural rather than enforced by
  two code paths. Needs a migration.
- **N1** — cancel is a silent no-op after a reconnect; `ib.trades()` only holds the
  current session's orders.
- **N2** — `cancel_all_orders` / `close_all_positions` act on every order in the
  account, including ones this app never placed. No callers today; scope them
  before wiring FO-EXE-003.
- **Multi-user caveat** — `app_service.py:1307` builds the broker from
  `_users[0].mode`, not the active user.
- **SRD drift** — `SRD-GUI-013.006` still documents 15 indicators; 10 exist.
