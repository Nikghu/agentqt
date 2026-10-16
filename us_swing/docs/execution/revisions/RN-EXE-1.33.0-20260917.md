# Revision Note — RN-EXE-1.33.0-20260917

**Tool:** EXE
**Version:** 1.33.0
**Date:** 2026-09-17
**Type:** feat
**Author:** Claude Opus 5 under user direction
**Phase:** FO-EXE-018 Short Trade Direction — P1 to P3 (storage, engine wiring, cycle maths)

---

## Summary

The user asked whether a trade can start with a sell and finish with a buy. It could not:
every strategy was long-only. A strategy now carries a **direction**, Long or Short. A Short
strategy opens with a SELL (sell short) and closes with a BUY (buy to cover), with the stop
above the entry and the target below it.

Every existing strategy and every stored trade cycle reads as `LONG`, so nothing that was
running changes behaviour.

## What was long-only

The user-built strategy path is `strategy_store` → `strategy_engine/_router` →
`broker_adapter` → `order_ingestion` → `trade_cycle/_service` → GUI. Twenty separate
assumptions were found and are listed in `docs/execution/Short_Trade_plan.md` §2. The ones
that would have caused real losses rather than cosmetic errors:

- The order side was derived from the action (`BUY if is_entry else SELL`), and the order
  state enum from the side, so a short entry would have been recorded as an exit.
- Live and realized P&L, the trailing stop and both exit checks only worked upward.
- A disabled stop is stored as `0.0`. For a short, `price >= 0.0` is always true, so the
  first tick would have closed the trade.
- Nothing stopped one strategy holding AAPL long while another shorted it. IBKR nets those
  into a single position, which would have broken both cycles' exits.

## The change

| Area | Change |
|---|---|
| `execution/_enums.py` | `TradeDirection` (`LONG` / `SHORT`) |
| `gui/strategy_store.py` | `StrategyConfig.direction`, `strategies.direction` column, additive migration, unknown value → Long with one warning |
| `execution/trade_cycle/{_schema,_dto,_repository}.py`, `db/schema.py` | `trade_cycles.direction` column + `CycleSnapshot.direction`, additive migration |
| `execution/direction.py` (new) | `order_side(direction, is_entry)` and `risk_levels(...)` — the only place either is derived |
| `execution/strategy_engine/{_signals,_router,_context,_engine}.py` | `TradeSignal.direction`; entry levels from `risk_levels`; exit direction read from the open cycle; `direction_conflict` gate with one warning per crossing; `StrategyEngine.has_direction_conflict` |
| `execution/broker_adapter.py`, `execution/signal_bridge.py` | Side and entry risk from the shared helpers; `OrderContext.direction` |
| `execution/order_ingestion.py` | Order state chosen by entry/exit instead of side; cycle direction passed on the entry fill; short-reject warning |
| `execution/trade_cycle/_service.py` | Signed live and realized P&L; SHORT trailing stop follows the lowest price and ratchets down; SHORT exit checks; `hard_stop_loss <= 0` treated as no stop; SHORT risk-edit invariants |
| `data/models.py`, `gui/app_service.py` | `OpenPosition.direction` with signed P&L; cycle-derived and IBKR portfolio builders set it (negative IBKR quantity → Short) |

The GUI surfaces ship in RN-GUI-1.5.0-20260917.

## Decisions taken with the user

1. One direction per strategy, fixed for the life of a trade.
2. Opposite directions on the same stock are blocked, because the broker nets them.
3. Direction cannot be changed while the strategy has open trades.
4. A short reserves capital exactly like a long of the same size; no separate short-margin model.
5. No borrow check before a live short — the broker's reject is the answer, logged in plain English.
6. Paper mode allows every short.
7. `highest_price_seen` stores the best price seen (the lowest for a short), so no column rename.
8. On an open short the stop cannot be removed from the risk editor; the trade always keeps one.

## Verification

- 52 new unit tests (`UT-EXE-018.*`), all passing, plus `IT-EXE-018.001/.002`: a full short
  cycle through `SimBroker` — SELL to open, target exit at $96 booking +$40, and the stop
  exit at $102 booking −$20, asserting the real order sides and stored order states.
- `UT-EXE-018.007.M08.T16` asserts long behaviour is byte-for-byte unchanged.
- Full suite: **799 passed**, with the same 11 pre-existing failures
  (`tests/analysis/test_candle_builder.py`, `tests/screener/test_preset.py`) and the
  pre-existing collection error in `tests/screener/test_llm_claude_screener.py`.
- `ruff` and `mypy --strict`: counts identical to the pre-change baseline on every touched file.
- Three code reviews (P1, P2, P3). One real issue was found and fixed: the GUI-thread conflict
  check now runs on the engine loop, and an engine that does not answer within 2 s blocks the
  entry rather than guessing.

## Follow-ups

- The manual IBKR paper-account check of one live short is not done (TODO T30).
- `update_risk` cannot clear the stop on an open short. Confirmed intentional by the user.
- The legacy ANA engine (`analysis/strategies/*`, `exit_manager.py`) stays long-only; it does
  not use the Strategy Builder configuration.
