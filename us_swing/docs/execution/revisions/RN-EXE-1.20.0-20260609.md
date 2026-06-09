# Revision Note — RN-EXE-1.20.0-20260609

**Tool:** EXE
**Version:** 1.20.0
**Date:** 2026-06-09
**Author:** Claude Opus 4.8 under user direction
**Phase:** Feature — FO-EXE-017 (Absolute Capital Allocation, Capital-Max Sizing & Advisory Risk Warnings)

---

## Summary

Replaces the percentage-of-equity capital model with an **absolute per-user dollar
budget** (Max Capital), sizes every entry from the owning strategy's **Capital Max**
percentage of that budget, and downgrades the non-capital risk limits (Max Position,
Risk per trade, Max Daily Loss) from blocking rejections to **advisory warnings**.
Also wires the real `RiskManager` into the engine (it was running on a no-op
`PassthroughRiskValidator`, with quantity hard-coded to 1) and fixes the Rex column
`-1` display defect.

## Behaviour Changes

- **Max Capital is now `$` absolute**, not `%`. Paper uses it as the account equity /
  budget. Live compares it to broker cash on connect: if Max Capital exceeds cash, a
  one-time LIVE-LOG warning fires and sizing uses **90% of available cash**; the stored
  setting is never changed.
- **Position sizing** = `floor(effective_capital × capital_max% / 100 / entry_price)`.
  If even one share exceeds the strategy budget the entry is dropped with a
  "Capital Max insufficient for entry" warning (blocking).
- **Capital cap is blocking**; Max Position / Risk per trade / Max Daily Loss are
  **advisory** (Live Log + pop-up, never block/resize/close). Daily loss is aggregated
  across all active trades with a one-warning-per-crossing latch.
- **Rex auto-resets** on a `STOPPED → RUNNING` strategy start (previously only the
  manual "Reset rex counters" action did this). The Active Trades Rex column now shows
  remaining re-entries (never negative) and no longer leaks an open cycle's exhausted
  counter onto a pending duplicate row.

## Code Changes

| File | Change | MD |
|---|---|---|
| `data/models.py`, `config/settings.py` | `RiskConfig.max_allocation_pct` → `max_capital_value: float = 2000.0` | MD-EXE-017.006.M06 |
| `gui/user_store.py`, `user/manager.py` | Serialize `max_capital_value`; one-time load migration (drop legacy `max_allocation_pct`, fall back to default + INFO log) | MD-EXE-017.007.M07 |
| `gui/_demo.py` | Demo users seeded with absolute `max_capital_value` | MD-EXE-017.007.M07 |
| `execution/risk_manager.py` | `size_for_strategy` static sizer; budget-based `can_allocate`; advisory `validate_signal` (only CB blocks); `effective_capital_provider` + `warning_sink` ctor args; `validate` uses the sized `qty_recommended` | MD-EXE-017.001.M01 |
| `execution/strategy_engine/_events.py` | `RiskWarning` event added to the `StrategyEvent` union | MD-EXE-017.002.M02 |
| `execution/strategy_engine/_router.py` | `_size_entry`; capital-insufficient drop; sized `qty` into `_build_entry_signal`; `effective_capital_provider` wired | MD-EXE-017.003.M03 |
| `execution/strategy_engine/_engine.py` | Rex reset on `STOPPED → RUNNING`; thread `effective_capital_provider` to the router | MD-EXE-017.004.M04 |
| `gui/app_service.py` | Wire `RiskManager` (replaces `PassthroughRiskValidator`); `effective_capital()` + live reconcile; `_CyclePositionSource` adapter; daily-loss aggregation; `RiskWarning` → `risk_warning_raised` + Live Log; paper `get_account_state` seeds equity from Max Capital | MD-EXE-017.009.M09 |
| `gui/active_cycles_model.py` | `_rex_display` — never negative, suppress pending-duplicate shared counter | MD-EXE-017.011.M05 |
| `gui/settings_panel.py` | "Max capital" control `%` → `$` (dialog, table, risk tab) | MD-EXE-017.008.M08 |
| `gui/main_window.py` | `_on_risk_warning` — connects `risk_warning_raised` to a debounced (30 s/kind) non-blocking `QMessageBox` | MD-EXE-017.009.M09 (SRD-017.013) |

## Acceptance — Status

| AC | Status | Evidence |
|---|---|---|
| #1 paper $2000 × 25% / $96 → 5 shares | ✅ | `test_size_for_strategy_standard`, `test_router_builds_sized_entry_signal` |
| #2 price > budget → no order + warning | ✅ | `test_size_for_strategy_price_over_budget`, `test_router_drops_entry_when_capital_insufficient` |
| #3 live cap > cash → 90% + warning, setting kept | ✅ | `test_effective_capital_live_over_cash_uses_90pct` |
| #4 advisory limits warn, never block | ✅ | `test_validate_advisory_max_position_warns_not_blocks`, `test_daily_loss_warns_on_crossing` |
| #5 one entry/stock/strategy, allowed across strategies | ✅ | existing `_has_open_cycle` gate (unchanged) |
| #6 rex=0 → 1 entry; rex=3 → 4 entries | ✅ | existing rex gate (`test_rex_counter`) |
| #7 rex resets on STOPPED→RUNNING; no negative display | ✅ | `test_rex_reset_on_start`, `test_rex_no_reset_on_stop`, `test_rex_exhausted_shows_zero`, `test_rex_pending_duplicate_suppressed` |

## Tests

| Check | Result |
|---|---|
| `tests/execution/test_capital_allocation.py` | 12 passed |
| `tests/gui/test_capital_allocation_gui.py` | 10 passed |
| `tests/execution/test_risk_manager.py` (updated for new semantics) | 11 passed |
| `test_strategy_router.py`, `test_strategy_engine.py`, `test_rex_counter.py` | Pass (sizing falls back to qty=1 when no budget provider — legacy path intact) |
| Full execution + gui suites | 204 passed; 21 failures all pre-existing (candle loader, live tick worker, evaluator 14-key, app_service tick — verified identical with changes stashed) |
| `ruff` | Clean on changed files |
| `mypy --strict` | No new errors in changed files |

## Notes / Deviations

- `RiskWarning` was placed in `strategy_engine/_events.py` (joining the `StrategyEvent`
  union the bus already accepts) rather than `_protocols.py` as the MD row suggested —
  cleaner bus integration, same intent.
- `RiskManager` constructor stays backward-compatible: `effective_capital_provider`
  defaults to `account.equity`, so existing unit tests and any non-budget caller keep
  working.
- No global cap across strategies beyond each strategy's own Capital Max (per FO AC #5).

---

**Commit:** branch `fix/inf-drop-orphaned-watchlist` (pending) — Refs: MD-EXE-017.001.M01
