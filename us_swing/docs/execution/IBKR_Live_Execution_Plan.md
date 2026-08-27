# IBKR Live Execution — Safe Round-Trip on TWS Paper

> Planning document — for review before implementation. Not yet started.
> Scope: Phases 0–4 (safe live round-trip). Circuit breaker (FO-EXE-003) and dashboard
> routing / reconnect resync / startup reconciliation are deferred to a follow-up.

## Context

The goal is to exercise the **real IBKR execution code** end-to-end against a TWS **paper**
account (DU7078110, `127.0.0.1:7497`). In this codebase `mode="live"` means "route orders to a
real TWS socket" — the account logged into TWS decides paper vs real money.

Three exploration passes + direct code verification found the broker abstraction (Broker_fix
Phases 1–5) is **built and tested**, but the live path has state-corrupting gaps that would bite
even during paper-account testing. The live gateway (`IBKRClientGateway`) is entirely
`# pragma: no cover` — never run against TWS. This plan fixes the data-integrity gaps (provable
against SimBroker + the contract suite, **no TWS needed**), then does one controlled live smoke
test.

**Scope decisions (user-confirmed):**
- Do **Phases 0–4** now (safe live round-trip). Defer dashboard routing (Phase 5), reconnect
  resync (Phase 6), and startup reconciliation (Phase 8) to a follow-up.
- **Circuit breaker (FO-EXE-003) is OUT** of this plan — keep the current manual CB flag that
  only blocks new entries.
- **T15 unique-key audit is a HARD GATE** — must pass before any live order (Phase 4).
- **Dashboard close/square-off buttons are DISABLED in live mode** (quick Phase 0 safety fix)
  until properly routed later. Active Trades ■ force-exit already routes correctly and stays.
- Engine mode threading uses the single active-user mode (`get_active_user().mode`) — matches the
  current single-registry engine; true per-user is out of scope.

Outcome: a rejected/cancelled/timed-out live order never strands a symbol or leaks capital, live
trades are correctly tagged, IBKR rejects actually map with a reason, and a 1-share BUY/SELL/reject
round-trip is verified on TWS paper.

---

## Phase 0 — Safety gate (no live orders yet)

**Goal:** clear the pre-live blockers before any socket order.

1. **T15 record-resolution audit (hard gate).** Sweep `execution/` for first-match / partial-key
   lookups like ISS-EXE-0007. Concrete targets found:
   - `gui/app_service.py:2142` — `next(t for t in self._trades if t.trade_id == …)`
   - `gui/app_service.py:2356` (`force_exit_position`) — `next(...)` by strategy+symbol
   - `execution/strategy_engine/_router.py:116-139` — `_open_cycle_qty/_price/_open_cycle_symbols`
   - `broker/client.py:214` / `broker/ibkr.py:186` (`_cancel`) — linear scan of `ib.trades()` by orderId
   - `execution/trade_cycle/_service.py` `on_exit_fill` resolution by `(strategy_id, symbol)` (already
     ISS-EXE-0010-guarded — confirm it holds)
   Fix any that can match the wrong record; record the rest as an issue list. **This must be green
   before Phase 4.**

2. **Disable dashboard mutators in live mode (quick safety fix).** In `gui/dashboard_panel.py`
   (Square Off All `:1293/1307`, Manage dialog `:1539/1553`) and `gui/position_monitor_panel.py`
   (`:215`), grey out / block the close / square-off / set-SL actions when
   `demo.get_active_user().mode == "live"`, with a tooltip. Prevents the silent in-memory no-op
   (`app_service.close_position/partial_close_position/set_stop_loss` never hit the broker). Active
   Trades ■ (`force_exit_position`) is unaffected.

**Test:** audit is a written checklist; dashboard-disable verified by a paper→live toggle UI smoke.
**Risk:** low. **Artifacts:** DEVLOG note for the audit; no new SRD.

---

## Phase 1 — Reject/cancel feedback + submit-failure rollback (highest-value fix)

**Goal:** a reject, cancel, placement exception, or TWS-stall timeout on **any** order always clears
`in_flight`, releases the capital reservation, and notifies the engine — no permanent strand, no
leak. Fully provable against SimBroker.

Root cause: `order_ingestion.py:196-211` aborts/forgets on REJECTED/CANCELLED but **never notifies
the engine**. The handlers `_router.on_order_reject` (`_router.py:411-426`) and
`_engine.on_order_reject → _apply_reject` (`_engine.py:352-360`) are fully built but have **zero
producers** — `RejectEvent` is never constructed.

**Changes (reuse the existing `fill_sink` pattern at `app_service.py:1321`):**
- `execution/order_ingestion.py`
  - `OrderIngestion.__init__`: add `reject_sink` and `cancel_sink` callbacks (mirror `fill_sink`);
    import `RejectEvent` from `strategy_engine._protocols`.
  - REJECTED branch: after ledger update + (entry-only) `abort_entry_order`, build a `RejectEvent`
    and call `reject_sink`. **Exit-reject must NOT abort the cycle** — you still hold stock (TODO T9);
    keep it OPEN and notify so `in_flight` clears and the exit can retry.
  - CANCELLED branch: emit via `cancel_sink` (reason `"cancelled"`), preserve any partial fill.
- `execution/strategy_engine/_router.py`
  - `run_router_loop:325-334`: on dispatch exception, add `await self._rollback(ctx, signal.symbol)`
    (currently only logs) — covers the submit-timeout leak (gap 5). `_rollback` (`:367-372`) already
    clears `in_flight` + `risk.release`.
- `gui/app_service.py:1319`
  - Pass `reject_sink=lambda r: self._strategy_engine.on_order_reject(r)` and the same for
    `cancel_sink` (the engine slot already marshals onto its loop).

**Test:** new `tests/execution/test_order_ingestion.py` (none exists) — drive REJECTED/CANCELLED
entry & exit events, assert sink calls with correct `is_entry` and that exit-reject does **not**
abort the cycle. Router test: submitter that raises / returns None → `in_flight` discarded +
`risk.release` called. Extend `tests/broker/test_broker_contract.py` so the same reject script through
Sim and IBKR yields identical `reject_sink` calls. **No TWS.**
**Risk:** medium (hot fill path) — mitigated by the idempotent-insert guard + contract coverage.
**Artifacts:** extends Implemented SRD-EXE-015.002/.003/.005 (no new SRD approval); add MD/UTCD rows + RN.

---

## Phase 2 — Real mode threading

**Goal:** `trades` ledger + rehydrated positions carry the active user's real mode, not a hardcoded
`"paper"`, so live rows match the account poller (which tags `"live"`).

**Changes (`gui/app_service.py`):**
- `:1331` `mode_provider=lambda: "paper"` → `lambda: self.get_active_user().mode`.
- `_rehydrate_positions_from_cycles` (`:2208/2226/2242`): stamp `self.get_active_user().mode`.
- `get_active_strategy_positions:2257` filters `p.mode == "paper"` — widen to include live, in
  lockstep, or the Pending Signals table hides live positions.
- TODO T7: `insert_trade_with_anchor` (in `data/` DatabaseManager) hardcodes `mode="paper"`,
  `strategy_id=None` — thread real mode/strategy from the ingestion `OrderContext`.

**Test:** unit on ingestion `_new_trade_record` (mode propagates); rehydrate with a fake `tc_query`
asserting stamped mode; regression that paper mode still returns paper positions. **No TWS.**
**Risk:** low-medium (the filter widening changes what Pending Signals shows — verify by UI smoke).
**Artifacts:** MD/UTCD/RN; no new SRD.

---

## Phase 3 — IBKR status-mapping correctness (no TWS)

**Goal:** IBKR rejections map to REJECTED with a real reason, and `PendingCancel` is not treated as
terminal. Provable through the fake-gateway contract suite.

**Changes (`broker/ibkr.py`):**
- `_map_status` (the `("Cancelled","ApiCancelled","PendingCancel")` tuple): remove `PendingCancel`;
  return `None` (ack-only) so context is retained until a true terminal — otherwise a later real
  `Filled` arrives with a dropped `client_ref` and dies at `order_ingestion.py:157-170`.
- `IBKRClientGateway`: subscribe to `self._client.ib.errorEvent`, filter by `reqId/orderId`
  (so warnings like 399/2109 don't reject), and map order-scoped error codes (201 margin, 202
  cancelled, duplicate-order) onto `IbkrOrderUpdate(status=…, reason=<errorString>)`. Today the
  gateway only listens to `trade.statusEvent`, so margin/risk rejects are **never observed**.
- `_make_handler`: populate `reason` (from `trade.log` / status) instead of the hardcoded `""`.

**Test:** extend `tests/broker/test_broker_contract.py` — `PendingCancel` then `Filled` (must yield
FILLED, not stranded); `Inactive` + reason → REJECTED carries reason; error-code 201 → REJECTED;
noise error events (399) → no reject. Assert Sim's equivalent scripted reject produces the same
neutral `OrderEvent`. **No TWS.**
**Risk:** medium — the reqId/orderId filter is the critical correctness point; unit-test with noise events.
**Artifacts:** extends Implemented SRD-INF-009.005; add UTCD + MD note + RN.

---

## Phase 4 — First live TWS-paper round-trip

**Goal:** first controlled run of the real gateway against DU7078110 on 7497, with a liveness gate
(no placement mid-reconnect) and order pacing. **Gated on Phase 0 T15 audit being green.**

**Changes:**
- `broker/ibkr.py` `_place`: route `ib.placeOrder` through the client's `PacingQueue` (`IBKRClient`
  already owns `_pacing`) so bursts respect IBKR limits.
- `broker/ibkr.py` `submit`/`_place`: before placing, check `client.is_connected()`; if not, raise a
  typed `BrokerNotReady` so Phase 1's rollback clears the symbol instead of leaking (minimum half of
  the reconnect gap — full resync is deferred).
- `execution/ibkr_order_connection.py`: add an `is_live()` gate delegating to `client.is_connected()`.
- `gui/app_service.py`: confirm the dedicated order connection uses `ibkr_order_client_id` (distinct
  from tick/account/candle ids) and `_system_cfg.ibkr_port == 7497`; keep the boot fallback-to-Sim on
  connect failure (`:1304-1318`, already correct).

**Live smoke test (DU7078110, 1-share, manual pending-execute only — no auto-trade):**
1. Boot with active user `mode="live"`, TWS paper on 7497. Confirm the order connection opens under
   its own client id.
2. MARKET BUY via pending-signal execute → acceptance → `trades` NEW row (mode `live`) → FILLED →
   cycle opens → position shows.
3. MARKET SELL (force-exit) → cycle closes, SELL ledger row.
4. Oversized order → REJECTED via errorEvent → symbol clears (validates Phases 1+3 live).
5. Kill TWS mid-flight → `BrokerNotReady` + rollback, no strand.

**Provable without TWS:** mapping, reject/cancel feedback, rollback, pacing order. **Live-only:**
socket acceptance latency, real errorEvent codes/text, PendingCancel real sequencing, disconnect
behaviour.
**Risk:** high (first real socket, even on paper) — mitigate: 1-share orders, manual only, documented
rollback runbook.
**Artifacts:** extends SRD-EXE-015.004 (Partial→Implemented) + SRD-INF-009.005; UTCD for pacing +
liveness gate; RN documenting the live run; TRACE + CONTEXT + DEVLOG.

---

## Critical files
- `us_swing/src/us_swing/execution/order_ingestion.py` — Phases 1, 2 (add sinks, mode)
- `us_swing/src/us_swing/broker/ibkr.py` — Phases 3, 4 (mapping, errorEvent, pacing, liveness)
- `us_swing/src/us_swing/gui/app_service.py` — wiring hub (Phases 1, 2, 4) + dashboard-disable (0)
- `us_swing/src/us_swing/execution/strategy_engine/_router.py` — Phase 1 rollback
- `us_swing/src/us_swing/gui/dashboard_panel.py` + `position_monitor_panel.py` — Phase 0 disable
- `us_swing/tests/broker/test_broker_contract.py` — the Sim≡IBKR gate (extended in Phases 1, 3)
- `us_swing/tests/execution/test_order_ingestion.py` — NEW (Phase 1)

## Verification (end-to-end)
1. `python -m pytest us_swing/tests/broker us_swing/tests/execution -q` — Phases 1–3 green, contract
   suite proves Sim≡IBKR reject/cancel/mapping **without TWS**.
2. `ruff check` + `mypy --strict` clean on every changed file.
3. Confirm the 21 pre-existing failures in `test_app_service_tick.py` / candle-loader / tick-worker /
   evaluator are unchanged (baseline noise, per CONTEXT.md).
4. Phase 0 T15 audit checklist signed off (hard gate).
5. Phase 4 live smoke on DU7078110: the 5-step BUY/SELL/reject/kill sequence, watching the log panel
   + `trades` ledger + Active Trades tab.

## Deferred (follow-up plan)
Dashboard order routing (Phase 5), reconnect-mid-order resync (Phase 6), FO-EXE-003 circuit breaker +
emergency flatten (Phase 7), FO-EXE-002 startup reconciliation (Phase 8). These need their own
approved SRDs (FO-EXE-003 SRDs are currently Draft).
