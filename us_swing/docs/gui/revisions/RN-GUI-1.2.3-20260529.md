# Revision Note — RN-GUI-1.2.3-20260529

**Tool:** GUI
**Version:** 1.2.3
**Date:** 2026-05-29
**Type:** fix
**Author:** USSwing

---

## Summary

Fixed a bug where a strategy stuck in `SQUARING_OFF` (due to a missing `trades.db` or all cycles already gone) could never be reset to `STOPPED` from the UI. The Stop button on a `SQUARING_OFF` strategy previously hard-returned, permanently locking the badge until the last open cycle closed via the engine — which could never happen if no cycle ledger existed.

---

## Root Cause

`_StrategyTablePane._on_run()` in `execution_panel.py` contained an unconditional early return for the `SQUARING_OFF` branch:

```python
elif current == "SQUARING_OFF":
    return   # user locked out — no escape path
```

When `trades.db` was absent, `get_open_symbols_for_strategy()` already returned `[]` (safe, no exception), but the early return fired before that check was reached.

---

## Fix

Replaced the early return with a guard that allows force-STOPPED when no open cycles remain:

```python
elif current == "SQUARING_OFF":
    if self._demo.get_open_symbols_for_strategy(cfg.name):
        return    # genuine squaring-off in progress
    cfg.strategy_signal["run_state"] = "STOPPED"
    new_state = "STOPPED"
```

The existing `save_strategies → _notify_engine_run_state → _refresh_table` tail is reused unchanged.

---

## Files Changed

| File | Change |
|---|---|
| `us_swing/src/us_swing/gui/execution_panel.py` | `_StrategyTablePane._on_run()` — SQUARING_OFF force-clear guard |
| `us_swing/tests/gui/test_execution_panel.py` | New — T06 (positive) + T07 (negative) for the fixed branch |
| `us_swing/docs/gui/UTCD.md` | T06–T07 added under MD-GUI-004.001.M01 |
| `us_swing/docs/gui/TRACE.md` | FO-GUI-004 row updated, version bumped |

---

## Traceability

| Artifact | ID |
|---|---|
| FO | FO-GUI-004 |
| SRD | SRD-GUI-004.001 |
| MD | MD-GUI-004.001.M01 |
| New Tests | UT-GUI-004.001.M01.T06, UT-GUI-004.001.M01.T07 |

---

## Test Results

| ID | Description | Result |
|---|---|---|
| UT-GUI-004.001.M01.T06 | SQUARING_OFF → STOPPED when no open cycles remain | Pass |
| UT-GUI-004.001.M01.T07 | SQUARING_OFF stays locked while open cycles exist | Pass |
