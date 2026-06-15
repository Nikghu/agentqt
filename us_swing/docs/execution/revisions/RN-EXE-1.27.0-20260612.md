# Revision Note — RN-EXE-1.27.0-20260612

**Version:** 1.27.0
**Date:** 2026-06-12
**Tool:** EXE (+ GUI surface)
**Artifact:** SRD-EXE-017.022 / SRD-GUI-014.005
**Type:** Refactor (behaviour change, user-directed)

---

## Summary

Manual strategies now **monitor and surface entries regardless of available
capital**. Previously the engine dropped any entry it could not fund and logged
a warning on almost every tick (e.g. repeating `SUPERTREND Capital Max
insufficient for entry on SNDK`). Now a manual strategy turns the fired entry
into a PENDING signal so the user can choose which of several satisfied stocks
to take; the capital/margin check moved to the confirm popup, where the **Enter
button is disabled with a red warning** when global Margin Available cannot cover
the trade. Auto-trade strategies are unchanged — they still block at the engine
(one edge-triggered warning per crossing), because no human confirms them.

---

## Behaviour Changes

- **Manual path no longer blocks on capital/margin.** `_router.evaluate` splits
  on `mode == "manual" or not auto_trade`: the manual branch builds the entry
  signal (qty = capital-max size, floored at 1), adds it to the pending queue,
  and does **not** reserve capital or warn.
- **No capital freeze while pending.** Reservation happens only when the user
  confirms (auto path still reserves at signal time). Several stocks can sit
  pending at once without locking each other's margin.
- **Confirm popup affordability gate.** For a BUY, `ActiveCyclesPanel` checks
  `qty × live price` vs `AppService.margin_available()` (global free cash, not
  the per-strategy Capital Max). If it cannot be covered the confirm button is
  disabled and a red line shows below it. A SELL is never blocked.
- **Auto-trade unchanged** except all three engine drops (capital insufficient,
  capital cap, margin exhausted) are now edge-triggered — one warning per
  crossing, not one per tick.
- **Rex-limit block log is now edge-triggered too.** A rex-exhausted symbol
  re-fires its entry every tick; the `ENTRY blocked … rex limit reached` INFO
  line now logs once per episode (DEBUG thereafter), self-clearing via a new
  `ctx.rex_warned` set when the counter frees up.

---

## Code Changes

| File | Change | SRD |
|---|---|---|
| `execution/strategy_engine/_router.py` | `evaluate` entry branch splits manual vs auto; manual skips the gate + reservation; auto keeps the gate with edge-triggered warnings; rex-block log edge-triggered via `ctx.rex_warned` | SRD-EXE-017.022 |
| `execution/strategy_engine/_context.py` | `_StrategyContext.rex_warned: set[str]` latch for the per-symbol rex-block log | SRD-EXE-017.022 |
| `gui/active_cycles_panel.py` | `_ConfirmDialog` gains `confirm_enabled` + `warning`; new `_affordability()` disables Enter + shows the margin warning for an unaffordable BUY | SRD-GUI-014.005 |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-017.022 | Manual strategies surface entries as pending regardless of capital; auto-trade still gated; capital frozen only on confirm | Implemented |
| SRD-GUI-014.005 | BUY confirm popup disables Enter + warns when global Margin Available can't cover the trade | Implemented |

---

## Tests

| Check | Result |
|---|---|
| `tests/execution/test_strategy_router.py` — UT-EXE-011.001.M04.T30 (manual entry bypasses gate) + T31 (rex-block log edge-triggered, 3 ticks → 1 INFO) | 33 passed |
| `tests/gui/test_capital_allocation_gui.py` | 13 passed |
| `ruff` | clean on changed files |
| `mypy --strict` | clean on `_router.py` and on the changed lines of `active_cycles_panel.py` (only pre-existing PyQt override baseline remains) |

---

## Notes / Deviations

- Decision (user-directed): the popup blocks on **global Margin Available only**,
  not the per-strategy Capital Max — a manual entry may override the soft
  per-strategy budget but never the real free-cash ceiling.
- `margin_available()` is fill-based, so with no pending reservations it reflects
  actual deployed capital — exactly what the popup should check.

---

**Commit:** pending — Refs: SRD-EXE-017.022, SRD-GUI-014.005
