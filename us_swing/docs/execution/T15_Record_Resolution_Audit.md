# T15 — Record-Resolution Audit (Phase 0 hard gate)

**Status:** Phase 0 complete — F1–F3 applied, mutators guarded; F4 held; F5 deferred
**Date:** 2026-08-27
**Scope:** `execution/`, `broker/`, `gui/app_service.py`, `gui/execution_panel.py`
**Gate:** must be green before any live order (Phase 4)
**Baseline commit:** `e710d967`

---

## What we were looking for

The ISS-EXE-0007 / ISS-EXE-0010 pattern: code that knows a record's **exact identity**
at the point of the user's click, then re-resolves it by a **partial key** (symbol,
or strategy+symbol) and takes the first match. With one open position the bug is
invisible. With two it closes the wrong one.

---

## Findings

| # | Site | Resolves by | Verdict |
|---|---|---|---|
| A1 | `execution_panel.py:1303` `_exit_by_cycle_id` | has `cycle_id`, **discards it** | **FIX** |
| A2 | `app_service.py:2931` `_handle_auto_exit` | has `cycle_id`, **discards it** | **FIX** |
| A3 | `app_service.py:2366` `force_exit_position` | `(strategy_id, symbol)` first-match | **FIX** |
| A4 | `execution_panel.py:1512` square-off row | `(strategy_id, symbol)` | **DEAD CODE** — see F3 |
| A5 | `trade_cycle/_service.py:303` `on_exit_fill` | unique `exit_order_id` first, then `(strategy, symbol)` | **HOLDS** |
| A6 | `app_service.py:2152` fill-confirmed log | unique `broker_order_id` | **SAFE** |
| A7 | `broker/ibkr.py:186`, `broker/client.py:214` `_cancel` | unique `orderId` | **SAFE match**, silent no-op — see N1 |
| A8 | `app_service.py:2004/2020/2038` dashboard mutators | `(symbol, user_id)` first-match | Covered by Phase 0 item 2 |

### A1–A4 — the real finding

Three call sites collapse a known identity into a partial key:

```python
# execution_panel.py:1303 — the function is NAMED for the id it throws away
def _exit_by_cycle_id(cycle_id: int, reason: str) -> None:
    snap = cycle_query.cycle(cycle_id)
    demo.force_exit_position(snap.strategy_id, snap.symbol)   # cycle_id dropped

# app_service.py:2931 — ExitTrigger carries cycle_id, same discard
snap = self._tc_query.cycle(cycle_id)
order_id = self.force_exit_position(snap.strategy_id, snap.symbol, reason=reason)
```

`force_exit_position` then does the first-match scan:

```python
snap = next(
    (s for s in self._tc_query.open_cycles()
     if s.strategy_id == strategy and s.symbol == symbol),
    None,
)
```

This is textbook ISS-EXE-0007. The user clicks ■ on one row; the code walks back to
"first open cycle for this strategy and symbol".

### A5 — holds, with a documented residual

`on_exit_fill` tries the unique `exit_order_id` first and only falls back to
`(strategy_id, symbol)` when the cycle was never stamped. The fallback is reachable
only if two open cycles share that pair — see the reachability analysis below.

### A6, A7 — cleared

`broker_order_id` and `orderId` are unique keys, so these are correct lookups, not
partial-key bugs.

---

## Reachability — can two open cycles share (strategy, symbol) today?

This decides whether A1–A4 are a live bug or a latent one. Checked all four routes:

| Route | Guard | Result |
|---|---|---|
| Auto entry | `_router.evaluate:175` — `has_open_cycle` true → takes the exit branch, never re-enters | Blocked |
| Duplicate pending entry | `_router.evaluate:250` adds `symbol` to `ctx.in_flight` *before* queueing; `:170` suppresses the next one | Blocked |
| Restart with a stale pending entry | `PendingSignalStore` is **in-memory only** — no DB writes, nothing survives a restart | Not reachable |
| Manual execute | `app_service.execute_signal:2059` guards **EXIT** only. **No ENTRY guard.** | **Open hole** |

`has_open_cycle` is called from `_router.py` and nowhere else. There is also **no DB
constraint** — `trade_cycles` has unique indexes on `entry_order_id` and
`exit_order_id`, but nothing on `(strategy_id, symbol, state)`.

**Conclusion:** A1–A4 are **latent, not currently firing**. The single-open-cycle
invariant holds today, but it rests entirely on one in-memory check inside the router,
with no constraint behind it. Every consumer downstream assumes the invariant while
nothing enforces it.

---

## Proposed fixes, and what each one risks

### F1 — Add `force_exit_cycle(cycle_id, reason)` (A1–A3)

New method resolving via `self._tc_query.cycle(cycle_id)`, which is a primary-key
lookup. `force_exit_position(strategy, symbol)` stays as a thin wrapper that resolves
to a cycle then delegates, so no caller breaks.

*Risk:* low. Additive. The existing signature keeps working.
*Watch:* `force_exit_position` returns `None` for "no open cycle" and `-1` for "no
submitter". `force_exit_cycle` must keep both, or callers misread failures.

### F2 — Point A1 and A2 at `force_exit_cycle` (A1, A2)

One-line change each — they already hold `cycle_id`.

*Risk:* very low. Strictly narrows what can be selected.
*Watch:* `_handle_auto_exit` logs "found no open cycle" on `None`; that stays valid.

### F3 — A4 is unreachable; no change made

`_on_table_force_exit` is wired only from `_inject_action_buttons`, which is reached
only from `_refresh_signals_pane`, which is reached only from `_build_signals_pane` —
and `_build_signals_pane` is **defined but never called**. The whole legacy signals
pane is dormant, already slated for Phase 2 removal.

Editing unreachable code adds churn and a false sense of coverage. Left as-is and
recorded here. When the legacy pane is deleted in Phase 2, A4 goes with it. If it is
ever revived instead, it must be pointed at `force_exit_cycle` first.

### F4 — Guard ENTRY in `execute_signal` (the reachability hole)

Refuse a manual ENTRY when `has_open_cycle(strategy_id, symbol)` is already true,
mirroring the existing EXIT guard.

*Risk:* **medium — the only change here that can reject something a user asked for.**
This closes the one route to duplicate cycles, but a user who deliberately wants a
second position in the same symbol under the same strategy would now be blocked.
Today that is a data-corrupting action, not a feature, so blocking is correct — but it
is a behaviour change and should be logged clearly, not silently swallowed.
*Watch:* must not block a *different* strategy on the same symbol. Key on both fields.

### F5 — Not now: DB constraint

A partial unique index on `(strategy_id, symbol)` where state is non-terminal would
make the invariant real. Deferred — it needs a migration and a decision about what
should happen when it fires. Logged as a follow-up.

---

## Notes (no action this phase)

**N1 — Silent cancel no-op.** `broker/ibkr.py:185` and `broker/client.py:213` scan
`ib.trades()` and `return` quietly when the id is absent. `ib.trades()` only holds
orders from the current client session, so after a reconnect a cancel can silently do
nothing while the caller believes it succeeded. Belongs with Phase 4's liveness work.

**N2 — Account-wide weapons.** `broker/client.py:219 cancel_all_orders` and
`:224 close_all_positions` act on **every** order and position in the account,
including ones this app never placed — on a live account, the user's own manual TWS
orders. Both currently have **no callers**. Flagged for whoever wires FO-EXE-003
(EmergencyShutdown): they must be scoped to app-placed orders first.

---

## Phase 0 item 2 — dashboard mutators (verified, worse than described)

`close_position` (`:2004`), `partial_close_position` (`:2020`), `set_stop_loss`
(`:2038`) do **not** reach the broker — confirmed. Three further problems the plan
did not record:

1. They do not write to `trade_cycles` either. The ledger keeps the position OPEN, so
   the strategy engine goes on evaluating stops on a position the user believes is
   closed.
2. The mutation is on `self._positions`, which `_rehydrate_positions_from_cycles()`
   rebuilds from the ledger — so the "close" visually reverts on the next refresh.
3. `close_position:2008` sets `p.quantity = 0` then logs `qty={p.quantity}`, always
   printing `qty=0`.

They also use `(symbol, user_id)` first-match (A8), so with two strategies holding the
same symbol they hit whichever comes first.

Disabling them in live mode is the right Phase 0 action. In paper mode they are still
misleading and should carry a follow-up.

---

## Gate status

| Item | State |
|---|---|
| A1, A2 — callers use the cycle id | **Done** (F2) |
| A3 — `force_exit_cycle` added | **Done** (F1) |
| A4 — dead code | **Closed as won't-fix** (F3) |
| A5 confirmed holding | Done |
| Dashboard mutators disabled in live | **Done** — Phase 0 item 2 |
| F4 ENTRY guard | **Held** — awaiting the behaviour-change decision |
| F5 DB constraint | Deferred |

**Phase 0 as specified is COMPLETE.** Both items are done: the T15 audit is green and
its fixes are applied, and the unrouted dashboard mutators are blocked in live mode.

**One known risk remains open by decision — F4.** `SRD-EXE-014.007` states the exit
resolves by `(strategy_id, symbol)`, *"unique among open cycles"*. Nothing enforces
that: the manual-execute path can still open a second cycle on the same pair, which is
the only way to reach the wrong-record behaviour A1–A3 just closed downstream. Acceptable
while testing on a paper account; should be closed before real money.

## Phase 0 item 2 — how it was blocked

Guarded at two layers, deliberately:

- **`AppService`** — `live_mutations_blocked()` plus a `_refuse_live_mutation()` early
  return in all three methods. This is the authoritative block: it covers every caller,
  including the dormant legacy pane and anything added later, and reports the refusal in
  the log panel rather than failing silently.
- **The two panels** — `dashboard_panel._live_mode_blocked()` (Square Off All, Manage)
  and `position_monitor_panel._on_close` intercept before the confirmation dialog and
  explain why, pointing the user at the Active Trades stop button, which does route a
  real exit order.

A greyed-out button was considered and passed over: mode changes require an app restart,
so a build-time disable would be correct but silent, and a user hitting a dead button
learns nothing. Explaining beats hiding here.

## Applied

| Change | Where |
|---|---|
| `force_exit_cycle(cycle_id, reason)` — primary-key resolution | `app_service.py:2353` |
| `_submit_cycle_exit(snap, reason)` — shared submit path | `app_service.py:2405` |
| `force_exit_position` kept as a partial-key wrapper | `app_service.py:2379` |
| Auto target/SL exit now passes the id | `app_service.py:2969` |
| Active Trades stop button now passes the id and its reason | `execution_panel.py:1303` |
| 9 regression tests, `UT-EXE-014.007.M01.T04–T12` | `tests/gui/test_app_service_force_exit_cycle.py` |
| `live_mutations_blocked()` + `_refuse_live_mutation()` | `app_service.py:2004` |
| Live guard on the three mutators | `app_service.py:2026/2054/2075` |
| Square Off All + Manage blocked with an explanation | `dashboard_panel.py:1522/1571` |
| Position Monitor close blocked with an explanation | `position_monitor_panel.py:198` |
| 9 guard tests, `UT-EXE-015.004.M01.T20–T28` | `tests/gui/test_app_service_live_mutation_guard.py` |

Verified: 18 new tests pass; gui+execution+broker **21 failed / 316 passed**, the 21
being the unchanged pre-existing baseline. `ruff` per-file counts unchanged against HEAD
(`app_service` 19, `dashboard_panel` 38, `position_monitor_panel` 11; both test files
clean). `mypy --strict` error count on `app_service.py` unchanged at 38.


---

## Phase 4 — liveness gate (code half complete, live run pending)

| Plan item | State |
|---|---|
| `is_live()` on `IBKROrderConnection` | Done |
| Refuse placement / cancel when the socket is down | Done — `IBKRClientGateway._require_live` raises `BrokerConnectionError` |
| Dedicated order client id, distinct from the rest | Verified — 10 system / 12 intraday / 13 live / 14 tick / **15 order** |
| Port 7497 | Verified — `SystemConfig.ibkr_port` default |
| Boot fallback to SimBroker on connect failure | Verified unchanged |
| Route `placeOrder` through `PacingQueue` | **Not done — deliberately.** See below |
| Live TWS-paper smoke test | Pending — needs a manual run |

### Why orders are not routed through `PacingQueue`

The plan says to pace placements through the client's existing `PacingQueue`.
Doing that would be actively harmful:

1. **Wrong limit.** `broker/pacing.py` documents itself as *"the IBKR
   historical-data pacing limit: ≤ 50 requests per 600-second rolling window"*,
   and its `acquire()` docstring says it "must be awaited before every
   `req_historical_data()` call". Order placement is governed by a different and
   far more permissive rule (message rate per second), not the historical-data
   window.
2. **It would delay stop-losses.** After 50 orders in ten minutes the 51st would
   *block*, busy-waiting in 0.5 s sleeps until a slot frees. An exit order
   carrying a stop loss could be held for minutes. That is a worse hazard than
   the burst it is meant to prevent.
3. **Structurally incompatible.** `acquire()` is `async`; the gateway's `_place`
   is synchronous, running on the client's loop via `_on_client_loop`.

If order-rate limiting is genuinely wanted later it needs its own limiter sized
to IBKR's order rules, never this one. Recorded rather than silently skipped.

### Liveness gate — why it raises rather than returns

`_require_live` raises `BrokerConnectionError` (reused; it already means
"connection could not be established or validated", and is only caught around
`build_broker` construction, never around placement). The router's
dispatch-exception handler catches `Exception` and rolls back, so a refused
placement clears `in_flight` and releases the capital reservation — the Phase 1
path. Returning a sentinel instead would leave the signal in flight with no
broker event ever coming to free it.
