# Revision Note — RN-EXE-1.24.0-20260612

**Tool:** EXE
**Version:** 1.24.0
**Date:** 2026-06-12
**Author:** Claude Opus 4.8 under user direction
**Phase:** Bugfix — ISS-EXE-0006 (forced exits filled at $0 in paper mode)

---

## Summary

Forced exits — end-of-day square-off, strategy-stop square-off, and emergency
shutdown — built their EXIT signal without a price. In paper mode the simulator
fills a no-reference MARKET order at $0, so these cycles closed at exit price $0
and recorded a fake ~−100% realized loss. Normal strategy exits (which carry the
bar close) and all live-mode exits were unaffected.

## Behaviour Changes

- Forced EXIT signals now carry `entry_price` = the open cycle's last known price
  (`current_price` when positive, else `entry_price`), so a paper fill uses a
  realistic reference instead of $0.
- A non-positive `current_price` (halted symbol / missing tick) falls back to the
  always-positive `entry_price`, so a $0 fill can never recur.
- Live MARKET orders are unchanged — they ignore the reference price.

## Code Changes

| File | Change | SRD |
|---|---|---|
| `execution/strategy_engine/_router.py` | New `_open_cycle_price()` helper (mirrors `_open_cycle_qty`); `_force_exit` sets `entry_price` from it; module-header SRD list updated | SRD-EXE-011.022 |

## Acceptance — Status

| Check | Status | Evidence |
|---|---|---|
| Forced exit carries cycle's last price | ✅ | `test_forced_exit_carries_open_cycle_price` (T27) |
| Falls back to entry_price when current_price is None | ✅ | `test_forced_exit_price_falls_back_to_entry_price` (T28) |
| Falls back when current_price is a 0.0 tick | ✅ | `test_forced_exit_price_rejects_non_positive_tick` (T29) |
| Strategy exit (bar.close) path unchanged | ✅ | existing exit tests still pass |

## Tests

| Check | Result |
|---|---|
| `tests/execution/test_strategy_router.py` | 31 passed (3 new) |
| `ruff` | Clean on changed files |
| `mypy` | No errors attributable to `_router.py` (pre-existing errors in other imported modules unchanged) |

## Notes / Deviations

- Scope-gap fix: no SRD covered the forced-exit fill-reference price, so new
  SRD-EXE-011.022 was added (Approved → Implemented), validated GO by the
  artifact-validator.
- Code review (code-reviewer) flagged a truthiness check (`current_price or
  entry_price`) that would let a real `0.0` tick re-introduce a $0 fill; corrected
  to an explicit positive-value guard and locked in with test T29.
- Complements ISS-EXE-0005 (realized P&L quantity). The screenshot's inflated
  exit prices were a separate price-feed concern, deferred by the user.

---

**Commit:** pending — Refs: SRD-EXE-011.022
