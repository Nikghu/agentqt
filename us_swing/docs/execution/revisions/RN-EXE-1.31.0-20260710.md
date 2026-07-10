# Revision Note — RN-EXE-1.31.0-20260710

**Tool:** EXE (+ GUI surface)
**Version:** 1.31.0
**Date:** 2026-07-10
**Author:** Claude Opus 4.8 under user direction
**Phase:** Feature — per-trade sizing (ISS-EXE-0011; SRD-EXE-017.023–.026)

---

## Summary

Splits the single per-strategy **Capital Max** control into two independent
settings so one strategy can hold **multiple concurrent positions** instead of a
single all-in position:

- **Strategy Allocation** (`capital_max`) — the strategy's budget ceiling.
- **Per-Trade Size** (`per_trade_pct`, 5–100%) — the size of each entry as a
  percentage of that allocation.

A strategy may now open up to `floor(100 / per_trade_pct)` positions before its
allocation cap (or the global Margin Available backstop) is reached. With
`per_trade_pct = 100` the behaviour is identical to the old one-position model.

## Design

- **Sizing (SRD-EXE-017.024).** `_router._size_entry` computes
  `budget = effective_capital × capital_max × per_trade_pct / 10000`
  (i.e. `eff_cap × allocation% × per-trade%`) and floors `budget / entry_price`.
  `can_allocate` is unchanged — it still caps the strategy at its full
  `capital_max`, so per-trade sizing only controls *how many slices* fit inside
  that unchanged ceiling. The global `margin_available()` clamp remains the hard
  backstop for the whole account.
- **Config + storage (SRD-EXE-017.023).** `StrategyConfig` gains
  `per_trade_pct: int = 100`; a `strategies.per_trade_pct` column is added with
  an additive `ALTER TABLE ... DEFAULT 100` migration so existing databases and
  legacy rows keep the old one-trade-per-allocation behaviour.
- **GUI (SRD-EXE-017.025).** The strategy builder replaces the single "Capital
  Max" spinbox with "Strategy Allocation" and "Per-Trade Size" spinboxes plus a
  live read-only hint (dollar budget, dollars per trade, and max trade count from
  the user's Max Capital). `execution_panel` passes Max Capital into the dialog.
- **Non-reserved ceiling (SRD-EXE-017.026).** An emergent invariant: a strategy's
  allocation is a ceiling, not a reservation. Only live open positions and
  in-flight entries consume `margin_available()`; a `STOPPED` strategy holding no
  positions frees its whole share back to the shared pool. No new gate — covered
  by the existing margin/run-state tests.

## Behaviour Changes

- The strategy builder now exposes two percentages instead of one. Existing
  strategies load with `per_trade_pct = 100`, so their sizing is unchanged.
- A strategy with a smaller per-trade size will take several entries over time
  rather than one large entry, up to its allocation cap.

## Code Changes

| File | Change | SRD |
|---|---|---|
| `execution/strategy_engine/_router.py` | `_size_entry` multiplies the allocation slice by `per_trade_pct/100` | SRD-EXE-017.024 |
| `gui/strategy_store.py` | `StrategyConfig.per_trade_pct` field, `strategies` column, additive migration | SRD-EXE-017.023 |
| `gui/strategy_builder_dialog.py` | Strategy Allocation + Per-Trade Size spinboxes + live hint; save/load | SRD-EXE-017.025 |
| `gui/execution_panel.py` | Passes the user's Max Capital into the builder dialog | SRD-EXE-017.025 |

## Tests

| Check | Result |
|---|---|
| `tests/execution/test_strategy_router.py` | +4 (UT-EXE-017.024.M03.T04–T07: allocation×per-trade sizing, `per_trade_pct=100` back-compat, room for a second entry, sub-share slice dropped) |
| Full execution suite (router, capital allocation, context, engine) | 73 passed |
| `ruff check` | Clean on all changed files |
| `mypy --strict` | Clean on `_router.py` (the builder dialog retains pre-existing GUI theme-constant debt, not held to strict) |

## Acceptance — Status

| Check | Status | Evidence |
|---|---|---|
| Per-trade size = allocation × per-trade % | ✅ | UT-EXE-017.024.M03.T04 |
| `per_trade_pct=100` reproduces old sizing | ✅ | UT-EXE-017.024.M03.T05 |
| Smaller per-trade allows a second concurrent entry | ✅ | UT-EXE-017.024.M03.T06 |
| Slice too small to afford one share drops the entry | ✅ | UT-EXE-017.024.M03.T07 |
| Existing strategies keep one-position behaviour | ✅ | additive migration default 100 |

## Notes / Deviations

- Code and doc chain (SRD/DD/MD/UTCD) were delivered in PR #53; this close-out
  flips SRD-EXE-017.023–.026 from `Approved` to `Implemented`, writes this note,
  and adds the TRACE row.

---

**Commit:** docs close-out on `docs/exe-per-trade-closeout` — Refs: MD-EXE-017.023.M03
