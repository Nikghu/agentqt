# Revision Note — RN-GUI-1.5.0-20260917

**Tool:** GUI
**Version:** 1.5.0
**Date:** 2026-09-17
**Type:** feat
**Author:** Claude Opus 5 under user direction
**Phase:** FO-EXE-018 Short Trade Direction — P4 (GUI surfaces)

---

## Summary

The screens for picking and watching a Short trade. The engine side ships in
RN-EXE-1.33.0-20260917; without this note's changes the user had no way to choose a
direction and the Active Trades panel still said "Sell" when closing a short.

## The change

| File | Change |
|---|---|
| `gui/strategy_builder_dialog.py` | Execution page gains a **Direction** combo (Long / Short) beside Trade Type, saved to `StrategyConfig.direction`; a new `has_open_trades` flag disables it with the tooltip "Close open trades before changing direction"; the Risk page shows an amber note when Short is chosen with the stop loss off (never blocking) |
| `gui/execution_panel.py` | Edit passes `has_open_trades` from the strategy's open cycles; Direction column width |
| `gui/strategy_table_model.py` | `COL_DIRECTION` after Trade Type, rendering Long / Short |
| `gui/active_cycles_model.py` | `Col.SIDE` after Symbol with `_Row.direction`, green Long / red Short, filled from the pending signal or the cycle |
| `gui/active_cycles_panel.py` | `_order_verb(direction, is_exit)` drives both confirmations: Buy / Sell for a long, **Sell short** / **Buy to cover** for a short; the Margin Available check now reads "entry, not BUY" |
| `gui/risk_editor_widget.py` | Short flips the spinbox ranges — stop at or above the price, target at or below — and a Short with no stop no longer gains one on a plain Save |

### The save that would have closed the trade

A Short with no stop loss has `hard_stop_loss = 0.0`, which is below the Short spinbox's
minimum, so the box opens showing the current price. Pressing Save without touching it would
have sent that value as a new stop, and because a short exits when price rises to its stop,
the next tick would have closed the position. `_hsl_placeholder` remembers the untouched
value and leaves `hard_sl` out of the saved fields until the user actually edits it
(`UT-GUI-014.018.M03.T04`).

## Verification

- 22 new pytest-qt tests (`UT-GUI-013.016–.019`, `UT-GUI-014.016–.018`), all passing.
- Full suite: **822 passed**, with the same 11 pre-existing failures
  (`tests/analysis/test_candle_builder.py`, `tests/screener/test_preset.py`).
- `ruff` clean; `mypy --strict` counts identical to the pre-change baseline.
- PyQt review: the only finding was a `None` comparison in the risk editor. Checked and not
  reachable — `CycleSnapshot.hard_stop_loss` is a non-optional float, the column is `NOT NULL`,
  the repository casts it, and the single caller always passes a real snapshot. Left as is
  rather than guarding an impossible case.
- Column numbering shifted in two models; every consumer refers to the constants by name, so
  nothing else needed touching.

## Follow-ups

- The manual IBKR paper-account check of one live short is not done (TODO T30).
- The legacy Pending Signals pane (`pending_signals_table_model.py`) still assumes BUY means
  entry. It is dead code — `_build_signals_pane` has no caller — so it was left alone.
