# Revision Note — RN-EXE-1.25.0-20260612

**Tool:** EXE (+ GUI surface)
**Version:** 1.25.0
**Date:** 2026-06-12
**Author:** Claude Opus 4.8 under user direction
**Phase:** Feature — FO-EXE-017 capital-allocation gaps (global Margin Available ceiling)

---

## Summary

Capital allocation only enforced a *per-strategy* cap (`can_allocate`). Nothing
enforced the *global* ceiling — total deployed across all of a user's strategies
must not exceed Max Capital. The method meant to do this (`can_enter_new`) was
dead code. As a result multiple strategies could each draw a full slice of the
same budget and over-commit, and same-bar entries could collectively exceed the
budget because the gate only saw *filled* positions. Paper mode also reported
`open_position_value = 0`, so the account-level margin and the GUI capital
indicator were always wrong, and the live User View never showed Max Capital or
Margin Available.

## Behaviour Changes

- **Global Margin Available ceiling.** New `RiskManager.margin_available()` =
  `effective_capital − deployed(all strategies) − reservations`, floored at 0.
  The router blocks any entry that would breach it (`reason='margin_exhausted'`,
  one edge-triggered WARNING per crossing).
- **In-flight reservation.** When the router commits to an entry it reserves the
  projected value, so two symbols firing on the same bar can no longer both pass.
  The reservation is released on entry fill, reject, or rollback.
- **Per-entry clamp.** Entry quantity is clamped to `floor(min(strategy_slice,
  margin_available) / price)`; a single entry can never exceed remaining margin.
- **Paper open-position value.** `get_account_state` now sums the user's open
  cycles instead of hardcoding `0.0`, fixing paper margin and the capital
  indicator. Live (IBKR) value is untouched.
- **Live margin-drift advisory.** On each live account refresh the system warns
  once per crossing when its margin diverges from broker cash (paper exempt).
- **User View.** The single-user `_AdminContextBar` now shows `Cap $X · Avail $Y`
  (green when margin > 0, red otherwise), refreshed on `account_updated`.
- `can_enter_new` (unused) was removed; `margin_available` supersedes it.

## Code Changes

| File | Change | SRD |
|---|---|---|
| `execution/risk_manager.py` | Add `margin_available()`, `reserve()`, `release()` + reservation ledger; remove `can_enter_new` | SRD-EXE-017.015, .017 |
| `execution/strategy_engine/_protocols.py` | `RiskValidator` gains `margin_available`/`reserve`/`release` | SRD-EXE-017.015, .017 |
| `execution/strategy_engine/_router.py` | Margin clamp + gate in `evaluate`; reserve on commit; release in `on_order_fill`/`_rollback`/`on_order_reject` | SRD-EXE-017.016, .018 |
| `execution/strategy_engine/_context.py` | `margin_warned` edge-trigger flag | SRD-EXE-017.016 |
| `gui/app_service.py` | Paper `open_position_value` sum; `margin_available()`; live `_reconcile_margin_drift()` | SRD-EXE-017.019, .020, .021 |
| `gui/main_window.py` | `_AdminContextBar` capital cell | SRD-EXE-017.021, SRD-GUI-000.006 |

## Acceptance — Status

| Check | Status | Evidence |
|---|---|---|
| Margin nets deployed across all strategies | ✅ | T01/T02 (M10) |
| Reservation lowers margin; release restores (idempotent) | ✅ | T03/T04 (M10) |
| Entry clamped to remaining margin | ✅ | T01 (M12) |
| Entry dropped when margin exhausted | ✅ | T02 (M12) |
| Entry fill releases reservation | ✅ | T03 (M12) |
| Paper open-position value summed | ✅ | T01 (M14) |
| AppService margin nets deployed / floors at zero | ✅ | T02/T03 (M14) |

## Tests

| Check | Result |
|---|---|
| `tests/execution/test_capital_allocation.py` + `tests/gui/test_capital_allocation_gui.py` | All pass (10 new cases) |
| `tests/execution/test_risk_manager.py` | 11 passed (3 `can_enter_new` tests converted to `margin_available`) |
| `tests/execution/test_strategy_router.py`, `test_strategy_engine.py` | Pass (risk fakes updated with `margin_available`) |
| `ruff` | Clean on all changed files (16 pre-existing `app_service.py` errors unchanged from HEAD) |
| `mypy --strict` | Zero errors on `risk_manager`/`_router`/`_protocols`/`_context`; GUI files keep their pre-existing `active_palette()` typing pattern |

## Notes / Deviations

- Margin is **derived, not stored** — no field can drift; reservations live only
  for the enqueue→fill window.
- The GUI `margin_available()` view is fill-based (it does not subtract router
  reservations), which are an engine-internal concern.
- Pre-existing, unrelated test failures remain on this branch (candle loader,
  live tick worker, evaluator function-map; identical on clean HEAD) and the
  pre-existing `app_service.py` ruff debt — neither introduced here.

---

**Commit:** pending — Refs: SRD-EXE-017.015–.021, SRD-GUI-000.006
