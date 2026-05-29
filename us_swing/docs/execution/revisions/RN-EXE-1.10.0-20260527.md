# Revision Note — RN-EXE-1.10.0-20260527

**Version:** 1.10.0
**Date:** 2026-05-27
**Tool:** EXE (+ cross-cut GUI)
**Artifact:** FO-EXE-011 / SRD-EXE-011.020
**Type:** Feature + Bugfix

---

## Summary

Active Trades panel Phase-2 fixes from manual testing. `TradeSignal` now carries a `user_id` field populated by a `user_id_provider` injected through `StrategyEngine` → `_Router`; `AppService` wires it to the active user so the panel's USER column resolves to the logged-in display name. Default `qty_recommended` raised from `0` → `1` so manual-mode pending rows render with a non-zero testing minimum. Active Cycles model gained a `#` row-number column and a `DISMISSED` state. Execute / Dismiss / Edit Risk / Close cell buttons redrawn as compact icon glyphs (▶ / ✕ / ✎ / ■) matching the strategy table's Delete / Play / Reset style, and the Actions column is now a fixed 88 px to prevent overlap. `PendingSignalStore.dismiss()` and `execute()` now emit dedicated `pending_signal_dismissed` / `pending_signal_executed` Qt signals instead of `pending_signal_removed`, so the row stays visible in the Active Trades table with its state transitioned rather than disappearing entirely after a user action.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-011.001.M06 | `src/us_swing/execution/strategy_engine/_signals.py` | Added `user_id: int = 0` field; bumped `schema_version` to `2` |
| MD-EXE-011.001.M04 | `src/us_swing/execution/strategy_engine/_router.py` | Added `user_id_provider` constructor param; threaded `user_id=self._user_id_provider()` into `_build_entry_signal`, strategy-EXIT path, and `_force_exit`; `_build_entry_signal` now sets `qty_recommended=1` so default-route signals render a non-zero minimum |
| MD-EXE-011.001.M01 | `src/us_swing/execution/strategy_engine/_engine.py` | Added `user_id_provider` constructor param; forwards to `_Router` |
| MD-EXE-011.001.M09 | `src/us_swing/execution/pending_signal_store.py` | Added `pending_signal_dismissed` and `pending_signal_executed` Qt signals; `dismiss()` and `execute()` now emit the new signals (no longer fire `pending_signal_removed`) so rows persist in the GUI table |
| MD-GUI-014.001.M02 | `src/us_swing/gui/active_cycles_model.py` | Added `Col.NUM` at index 0 (shifted all subsequent columns by +1); added `user_name_provider` constructor param + display lookup; added `DISMISSED` state colour; added `on_pending_dismissed` slot; pending rows now propagate `signal.user_id` and default `qty` to 1 |
| MD-GUI-014.001.M01 | `src/us_swing/gui/active_cycles_panel.py` | Wired `pending_signal_dismissed` → `_model.on_pending_dismissed`; passed `user_name_provider=self._lookup_user_name` to the model; fixed Actions column to 88 px and NUM column to 32 px via `setSectionResizeMode(Fixed)`; redrew row-action buttons as 26×22 icon-glyph buttons (▶ Execute, ✕ Dismiss, ✎ Edit Risk, ■ Close) — replaced text labels and the `80+60` two-button widths |
| MD-INF-004.002.M02 | `src/us_swing/gui/app_service.py` | Passed `user_id_provider=lambda: self._active_uid` to `StrategyEngine`; connected `pending_signal_dismissed` and `pending_signal_executed` to `pending_signals_updated` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-011.020 | `TradeSignal.user_id` propagation via engine `user_id_provider`; default `qty_recommended` raised to 1 | Implemented |

---

## Design Decisions

- **Lightweight provider over strategy ownership.** The strategy registry is global (one `strategies.json` across users); attaching a user to each `_StrategyContext` would have forced a per-user registry refactor. Using a `Callable[[], int]` provider on the engine lets `AppService` resolve the current `_active_uid` per signal without changing the registry semantics.
- **`schema_version` bump (1 → 2).** Required because a new field broadens the persisted shape — event-bus consumers compare versions when deserialising stored events.
- **Row stays after Dismiss/Execute.** Earlier behaviour popped the row entirely because `dismiss()`/`execute()` emitted `pending_signal_removed`. Splitting them into dedicated signals keeps the store's "active pending" semantics correct while letting the model transition the row state in-place. `DISMISSED` rows show no action buttons; `OPENING` rows surface the cycle spinner.
- **Icon-glyph buttons inside the delegate.** Switching to `setIndexWidget` (the pattern used by the strategy table) would have broken the FO-GUI-014 delegate contract. Drawing single-character glyphs in `_RowActionsDelegate` keeps the painted-delegate model and still matches the visual style of `_make_cell_btn`.
- **`qty_recommended=1` default.** Real position sizing belongs in the (still-stubbed) `RiskManager.calculate_position_size`; for now `1` is the minimum testable quantity that lets the panel render a non-blank QTY cell.

---

## Issues Resolved

User-reported defects from screenshot review (no ISS file — direct manual test feedback):
1. Empty USER column on pending signals.
2. No row numbering in Active Trades.
3. QTY rendered as `0`.
4. Execute / Dismiss buttons overlap and don't match Delete / Play / Reset style.
5. Trade signal disappears after Execute or Dismiss.

---

## Test Coverage

3 new router tests appended to `tests/execution/test_strategy_router.py`:
- `test_entry_signal_propagates_user_id_from_provider` (UT-EXE-011.001.M04.T18)
- `test_entry_signal_default_qty_is_one` (UT-EXE-011.001.M04.T19)
- `test_forced_exit_signal_carries_user_id` (UT-EXE-011.001.M04.T20)

GUI-side changes are covered behaviourally by the existing FO-GUI-014 panel test suite; no model column-index hard-codes in those tests required updating (they rely on `Col` enum lookups).

---

## Notes

`TradeSignal` in `data/models.py` (the legacy dataclass with `side`/`recommended_qty`/`target_price` fields) is unrelated to the FO-EXE-011 `TradeSignal` in `execution/strategy_engine/_signals.py` and was not touched — the two live in different layers; the new field exists only on the strategy-engine signal.
