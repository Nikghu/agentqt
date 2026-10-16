# Short_Trade — Long / Short Direction per Strategy

**Status:** Draft (planning)
**Tool:** EXE (with GUI Strategy Builder + trade-cycle views)
**Author:** USSwing
**Created:** 2026-09-17

---

## 0. Goal

Let the user choose **Long** or **Short** when creating a strategy. A Short strategy
opens a trade with a SELL (sell short) and closes it with a BUY (buy to cover). Stop,
target, trailing stop, P&L and every screen must work the right way for both directions.

Existing strategies stay **Long**. No behaviour change for them.

---

## 1. Key Idea — Direction vs Side

| Term | Lives on | Values | Changes during a trade? |
|---|---|---|---|
| **Direction** | Strategy + trade cycle | `LONG` / `SHORT` | No — fixed for the life of the cycle |
| **Action** | `TradeSignal` | `ENTRY` / `EXIT` | — |
| **Side** | Broker order + `trades` row | `BUY` / `SELL` | Derived: `side = f(direction, action)` |

| Direction | Entry side | Exit side | Profit when | Stop sits | Target sits |
|---|---|---|---|---|---|
| LONG | BUY | SELL | price goes up | below entry | above entry |
| SHORT | SELL | BUY | price goes down | above entry | below entry |

**Rule:** no code may read `BUY` as "entry" or `SELL` as "exit". Use `Action` / `is_entry`,
and direction for price maths.

---

## 2. Analysis — Long-only Assumptions Found

The user-built strategy path is `strategy_store` → `strategy_engine/_router` →
`broker_adapter` → `order_ingestion` → `trade_cycle/_service` → GUI.

| # | File : line | Long-only assumption | Change needed |
|---|---|---|---|
| A1 | `gui/strategy_store.py:34,66` | No direction field / column | Add `direction` (default `LONG`) + additive column migration |
| A2 | `gui/strategy_builder_dialog.py:1100` | No selector | Add **Direction: Long / Short** combo beside Trade Type; load/save it |
| A3 | `gui/strategy_table_model.py` | No column | Add Direction column |
| A4 | `strategy_engine/_router.py:541-544` | SL = entry×(1−%), target = entry×(1+%) | Flip for SHORT |
| A5 | `execution/broker_adapter.py:62` | `BUY if is_entry else SELL` | Side from direction + `is_entry` |
| A6 | `execution/broker_adapter.py:135-136` | Same SL/target maths as A4 | Flip for SHORT (share one helper with A4) |
| A7 | `execution/order_ingestion.py:340` | Picks `BuyOrderState` by `side` | Pick by `is_entry` (both enums have the same values — no data change) |
| A8 | `trade_cycle/_schema.py`, `_dto.py` | Cycle has no direction | Add `direction` column (default `LONG`) on `trade_cycles` + `CycleSnapshot` |
| A9 | `trade_cycle/_service.py:617-619` | Live P&L = (price − entry) × qty | SHORT: (entry − price) × qty |
| A10 | `trade_cycle/_service.py:623-636` | Trailing uses highest price; stop = `max(...)` | SHORT: track lowest price; trail = low + offset; stop = `min(...)` |
| A11 | `trade_cycle/_service.py:655-663` | Target when `price >=`; stop when `price <=` | SHORT: target `<=`, stop `>=` |
| A12 | `trade_cycle/_service.py:399-401` | Realized P&L = (exit − entry) × qty | SHORT: (entry − exit) × qty |
| A13 | `strategy_engine/_router.py:175` | Duplicate guard is per (strategy, symbol) only | Block an entry if another strategy holds the **opposite** direction on the same symbol (IBKR nets them) |
| A14 | `execution/signal_bridge.py:16` | `BUY if ENTRY else SELL` | Use the shared side helper |
| A15 | `gui/pending_signals_table_model.py:106,127,144` | `BUY` = pending entry; side shown as `"LONG"` | **Dropped** — `_build_signals_pane` is never called (dormant legacy pane) |
| A16 | `gui/active_cycles_panel.py:608,615,656` | "Sell" to close; "BUY needs margin, SELL never blocked" | Verb from direction ("Buy to cover"); margin check on **entry**, not on BUY |
| A17 | `trade_cycle/_service.py:483-489` | `update_risk`: stop ≤ price, target ≥ price | SHORT: stop ≥ price, target ≤ price |
| A18 | `gui/risk_editor_widget.py:46,53` | Stop max = price, target min = price | Swap ranges for SHORT |
| A19 | `data/models.py:127-134` | `OpenPosition.unrealised_pnl` = (price − avg) × qty | Sign by direction; IBKR negative qty → SHORT |
| A20 | `broker_adapter.py:136` + `_service.py:634` | Disabled stop stored as `0.0` | For SHORT, `price ≥ 0.0` would exit at once — treat `≤ 0` as disabled |

P0 docs written 2026-09-17: FO-EXE-018, SRD-EXE-018.001–.015, SRD-GUI-013.016–.019,
SRD-GUI-014.016–.018, DD/MD/UTCD (49 EXE + 21 GUI tests), TRACE rows. All SRDs Draft.

**Already OK (verify with a test, no change expected):**

| Area | Why it is fine |
|---|---|
| `broker/broker.py` `OrderSide`, `broker/ibkr.py` | Send BUY/SELL as given; IBKR opens a short on SELL with no holding (margin account) |
| `broker/sim.py:57` | Slippage by side is correct for both directions |
| `broker/client.py:230` | Emergency close-all already buys back negative positions |
| Rex counter, capital sizing (`_size_entry`) | Direction-neutral |
| Evaluator `PNL` indicator | Returns 0, supplied by router — no direction maths |

**Out of scope:** legacy ANA engine (`analysis/strategies/pullback.py`, `breakout.py`,
`exit_manager.py`). It does not use the Strategy Builder config.

---

## 3. Decisions (approved by user 2026-09-17)

| # | Question | Recommendation |
|---|---|---|
| D1 | One strategy, one direction? | Yes. Each strategy is Long **or** Short. |
| D2 | Same symbol Long in strategy A and Short in strategy B at once? | **Block** the second entry, log a warning. IBKR keeps one net position per symbol, so both cannot exist. |
| D3 | Change direction when editing a strategy with open trades? | **Block** the edit of that field until trades close. Open cycles keep their stored direction anyway. |
| D4 | Capital / margin for a short | Reserve the same amount as a long of the same size. Simple and safe. Real short margin rules are left to the broker. |
| D5 | Shares not available to borrow (live) | No pre-check in v1. IBKR rejects the order → existing reject path aborts the cycle and logs it. Pre-check (shortable data) is a later item. |
| D6 | Paper (Sim) borrow rules | None — paper allows every short. |
| D7 | `highest_price_seen` column for a short | Keep the column; store the **best** price seen (lowest for a short). Rename in the GUI label only. Avoids a migration. |

---

## 4. Artifact Plan

| Artifact | ID(s) | Notes |
|---|---|---|
| FO | **FO-EXE-018** "Short Trade Direction" (new) | Depends on FO-EXE-011/012/014/017, FO-GUI-013 |
| SRD | SRD-EXE-018.001 … ~.012 | One row per A-item group above |
| SRD (GUI) | SRD-GUI-013.016 (Direction selector) + SRD-GUI-014.x (row labels / verbs) | Additive rows under Approved FOs |
| DD / MD / UTCD | DD-EXE-018.* , MD-EXE-018.* , UT-EXE-018.* | UTCD before code; +1 positive, +1 negative per Must SRD |
| RN | RN-EXE-1.33.0-YYYYMMDD, RN-GUI-1.5.0-YYYYMMDD | After implementation |

---

## 5. Phased Implementation

| Phase | Scope | Items | Verify |
|---|---|---|---|
| **P0** | Docs: FO-EXE-018, SRDs, DD, MD, UTCD | — | User approves SRDs |
| **P1** | Data: `direction` on strategy + trade cycle (additive columns, default `LONG`) and one shared `order_side(direction, is_entry)` + `risk_levels(direction, price, cfg)` helper | A1, A8 | Old DB opens; old rows read as LONG |
| **P2** | Engine + adapter: flipped SL/target, side mapping, order-state by `is_entry`, opposite-direction guard | A4–A7, A13, A14 | Unit tests: SHORT entry → SELL order with SL above / target below |
| **P3** | Trade cycle: live P&L, trailing, exit triggers, realized P&L | A9–A12 | Unit tests: SHORT price drop → profit + target exit; price rise → hard/trailing stop |
| **P4** | GUI: builder combo, strategy table column, pending/active trade rows, close verb, margin check | A2, A3, A15, A16 | pytest-qt + manual run in paper |
| **P5** | End-to-end: Sim broker full short cycle; then IBKR paper account (DU) smoke test of one short | — | Cycle closes with correct realized P&L in both |

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| A missed `BUY == entry` check sends the wrong order | Grep gate in P2/P4 for `"BUY"` / `OrderSide.BUY` outside the helper; E2E test in P5 |
| Unlimited loss on a short with no stop | Warn in the builder when Short is chosen and Stop Loss is off |
| Opposite positions net to zero at IBKR | D2 guard |
| Short squeeze / gap up past the stop | Market exit as today; no extra logic in v1 |
