# Broker_fix — Broker Abstraction, Simulated Exchange & Unified Ingestion

**Status:** Draft (planning)
**Tool:** EXE (with INF `broker/` package)
**Author:** USSwing
**Created:** 2026-06-04

---

## 0. Goal

Make **paper a broker, not a shortcut.** Every order — paper included — must flow
through the complete trade path (`trades` → `trade_cycles` → `positions`). `Sim`
must behave *exactly* like `IBKR` behind one shared interface, so that:

- A universal `Broker` base defines the common API; `Sim` and `IBKR` both implement it.
- A `BrokerAdapter` sits on top and decides where each order is sent / received.
- Downstream logic never knows which broker answered — the broker layer is fully
  pluggable; switching `Sim ↔ IBKR` is an Adapter decision, no downstream edits.

The current `PaperBroker` fabricates a fill synchronously inside `submit()` and
writes only `trade_cycles`, **bypassing `trades`**. That bypass is removed.

---

## 1. Equivalence Guarantee (how Sim ≡ Ibkr is enforced)

| Mechanism | What it guarantees |
|---|---|
| **Universal `Broker` base (`broker/broker.py`)** | `Sim` and `IBKR` subclass the same base; `mypy --strict` rejects any broker missing a method or event. Imports nothing from execution — a self-contained INF plugin. |
| **`BrokerAdapter` (`execution/...`)** | The single seam on the execution side: translates `TradeSignal ↔ OrderRequest`, routes to the chosen broker, and forwards `OrderEvent`s back. Downstream talks only to the Adapter — source-blind. |
| **Broker contract-test suite** | The same signals fired at either broker must produce identical `trades` / `trade_cycles` / `positions` rows. `Sim` and `IBKR` both pass ⇒ interchangeable by definition. |
| **Broker-agnostic ingestion** | The pipeline never imports a concrete broker; all persistence logic is shared. |

---

## 2. Folder Layout (one file per broker)

```
broker/                          (INF — self-contained plugins, no execution imports)
  client.py      existing IBKRClient — raw transport/connection (unchanged)
  pacing.py      existing
  broker.py      NEW — universal Broker base + OrderRequest / OrderEvent / OrderStatus
  sim.py         NEW — Sim broker (mock exchange)
  ibkr.py        NEW — IBKR broker (wraps client.py::IBKRClient)

execution/                       (EXE — the adapter that bridges to the broker plugin)
  broker_adapter.py  NEW — BrokerAdapter: TradeSignal<->OrderRequest translation,
                           broker selection + routing, forwards OrderEvents
```

`broker/` is fully independent and imports nothing from `execution/` (dependency
points one way: execution → broker). `client.py` = transport; `ibkr.py` = the IBKR
broker on top of it. The **adapter lives on the execution side** because it speaks
both languages — it is the only seam downstream code sees (selection + routing live
here — no separate factory).

---

## 3. Execution Flow (target)

```
Strategy condition met
  → _Router.run_router_loop
  → RiskValidator.validate
  → BrokerAdapter.place_order(signal, qty)   [adapter.py — single seam]
        └─ routes to Broker (Sim │ IBKR)     [broker.py contract]
              └─ returns order_id, state = SUBMITTED
  → IngestionPipeline.on_order_accepted      [broker-agnostic, source-blind]
        → trades  (insert, order_state = SUBMITTED)

  ── async, via BrokerAdapter event forwarding (OrderEvent) ──
  Broker emits PARTIAL / FILLED / REJECTED / CANCELLED → Adapter forwards
  → IngestionPipeline.on_order_event
        → trades         (update_trade_fill: order_state + filled_qty)
        → strategy_engine.on_order_fill(FillEvent)
        → trade_cycles   (advance)
        → positions      (advance)
```

Going live = the Adapter routes to `IBKR` instead of `Sim`. Everything below
`place_order` / `OrderEvent` is frozen and source-blind.

### Linkage between ledgers (already in schema)

- `trades.trade_id` ← set to the broker `order_id`.
- `trade_cycles.entry_order_id` / `exit_order_id` already store that same `order_id`
  (unique columns). The join between order ledger and cycle ledger is already
  designed — no schema change needed.

---

## 4. The Broker Contract (`broker/broker.py`)

The universal `Broker` base models the *real* broker's full lifecycle — never an
instant fill:

- `place_order(signal, qty) -> order_id`  — **accept only**, returns state `SUBMITTED`.
- `cancel_order(order_id)`
- An **event stream / callback** of order-state transitions.

`Sim` and `IBKR` both subclass this base; the `BrokerAdapter` holds them and routes.

Order-state vocabulary reuses the existing enums in `execution/_enums.py`
(`BuyOrderState` / `SellOrderState`): `NEW → SUBMITTED → PARTIAL_FILL →
FILLED → REJECTED → CANCELLED` — the common System Enums shared by every layer
(kept in place; no relocation). `Sim` and `IBKR` emit these same transitions.

---

## 5. Parts to Remove / Retire

| Part | Location | Why |
|---|---|---|
| Synchronous fill-in-`submit` | `execution/paper_broker.py` | Real brokers don't fill inside submit; replaced by async event emission in `sim.py` |
| `_on_paper_fill` (dual role) | `gui/app_service.py:1829` | Splits into broker callback + shared ingestion |
| `_record_paper_entry` / `_record_paper_exit` | `gui/app_service.py:1850 / 1923` | Paper-only persistence → broker-agnostic ingestion |
| `execute_signal` paper route | `gui/app_service.py:1813` | Becomes a normal `place_order`, not a special path |
| `ExecutionEngine` | `execution/execution_engine.py` | Legacy unwired `trades` writer; logic moves to ingestion, then delete |
| `PaperEngine` | `execution/paper_engine.py` | Legacy unwired paper writer; superseded by `SimulatedBroker` |
| `MonitoringSessionService` trade writes | `core/monitoring_session/_service.py` | Confirm dead, then drop `insert_trade_with_anchor` calls |

**Keep & reuse (do NOT remove):** `ExecutionSubmitter` protocol, `Buy/SellOrderState`
enums, `db/manager.py::insert_trade` + `update_trade_fill`, the `trades` table,
`trade_cycles.entry_order_id` / `exit_order_id` linkage.

---

## 6. Phased Plan

### Phase 1 — Broker interface + lifecycle events
- `broker/broker.py`: universal `Broker` base (`place_order`, `cancel_order`, event channel).
- Define `OrderEvent` payloads reusing `Buy/SellOrderState` (enums stay where they are).
- No behaviour change yet — interface only.

### Phase 2 — Unified ingestion pipeline (broker-agnostic)
- New component subscribes to broker events.
- On accept → `insert_trade` (state SUBMITTED, `trade_id = order_id`).
- On event → `update_trade_fill` + `on_order_fill` + advance `trade_cycles` + `positions`.
- Move logic out of `_on_paper_fill` / `_record_paper_*`.

### Phase 3 — SimulatedBroker (`broker/sim.py`, replaces PaperBroker)
- Internal order book + configurable fill model (price source, latency, slippage, partials).
- Emit lifecycle events **asynchronously** — remove synchronous fill.
- Inject REJECTED / PARTIAL / CANCELLED on demand for functionality testing.
- **Broker contract test** added here.

### Phase 4 — IBKR broker (`broker/ibkr.py`)
- Wrap `broker/client.py` order ops behind the `Broker` base.
- Bridge IBKR `orderStatus` / `execDetails` into `OrderEvent`s.
- Must pass the same broker contract test.

### Phase 5 — Routing + wiring (`execution/broker_adapter.py`)
- `BrokerAdapter` (execution side) translates `TradeSignal ↔ OrderRequest`, builds
  the `OrderContext` (risk snapshot from `StrategyConfig`), routes each order, and
  forwards `OrderEvent`s into `OrderIngestion`.
- Selects `Sim` vs the user's live broker from `users.mode` (+ system gate
  `live_mode_enabled`). With no selection UI yet, mode stays `paper` → `SimBroker`.
- Wire `OrderIngestion` + `BrokerAdapter` into `app_service`, replacing the
  `_on_paper_fill` / `_record_paper_*` bypass. `Sim` stays available for dry-run.

### Phase 6 — Mode/Broker selection + remove legacy
- **Mode/Broker selection (Settings → Users):** add `"live"` to the existing Mode
  dropdown (`settings_panel.py:62`) and a new **Broker** dropdown (`IBKR`, extensible).
  Add a `broker` column to `users` + `UserProfile`/`UserRecord`. Selecting Live saves
  through the existing `UserManager.switch_mode` guard (`live_mode_enabled` + confirm
  token). Dashboard view label already shows Paper/Live — extend to `LIVE · <broker>`.
- Adapter routes by the user's `(mode, broker)`: paper → `Sim`; live + `IBKR` →
  `IBKRBroker`; future brokers registered by name.
- **Remove legacy:** delete `ExecutionEngine`, `PaperEngine`, `PaperBroker`,
  paper-specific `app_service` methods, confirmed-dead `MonitoringSessionService`
  writers; drop the legacy `positions` table and repoint `health.py` to `trade_cycles`.
- Update TRACE / DD / MD / RN.

---

## 7. Open Decisions

1. **Async fill model** — paper must stop filling inside `submit()`. Router must
   handle "order accepted, fill comes later." Engine already supports async fills
   via `call_soon_threadsafe`; confirm router ordering is safe.
2. **Tool boundary** — *Resolved.* `broker/` (INF) is a self-contained plugin and
   imports nothing from `execution/`; it holds only the `Broker` base + concrete
   brokers, speaking neutral `OrderRequest`/`OrderEvent` types. The `BrokerAdapter`
   and ingestion live on the **execution** side (EXE), since they translate to/from
   `TradeSignal`/`FillEvent`. Enums stay in `execution/_enums.py` — no relocation;
   the broker mirrors their values in its own `OrderStatus`, mapped 1:1 by the adapter.
3. **Fill price source for Sim** — signal price vs next-candle open vs configurable.
4. **Per-user vs single-user engine** — today one `user_id_provider`; multi-user broker
   routing may need the signal/fill to carry `user_id` end-to-end.
5. **Mode/Broker selection placement** — *Resolved.* Lives in **Settings → Users**
   (existing Mode dropdown + a new Broker dropdown), guarded by `UserManager.switch_mode`
   (`live_mode_enabled` + confirm token). No title-bar control. The Dashboard view label
   already surfaces Paper/Live per user. Scheduled for **Phase 6** (not Phase 5).

---

## 8. FO Skeleton (to formalise)

- `FO-EXE-0NN` — Broker abstraction: `Sim` and `IBKR` interchangeable behind one
  `Broker` base + `BrokerAdapter`; all orders flow through `trades` → `trade_cycles`
  → `positions`.
  - SRD: `Broker` base contract, order-lifecycle events, ingestion persistence rules,
    Adapter selection/routing, contract-test requirement.
