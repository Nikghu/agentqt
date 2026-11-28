# Revision Note — RN-EXE-1.45.0-20261128

**Version:** 1.45.0
**Date:** 2026-11-28
**Tool:** EXE
**Artifact:** FO-EXE-017 / SRD-EXE-017.029–.031
**Type:** Feature

---

## Summary

Live and paper strategies can now grow with their own closed-trade P&L. A strategy's allocation = Max Capital × allocation % + that strategy's all-time closed P&L for the user (never below 0). The shared budget = max(0, Max Capital + closed P&L of the growing strategies). Live keeps the 90%-of-broker-cash cap. Growth turns on from the strategy's tick or the user's account switch; fixed-share strategies do not grow. Both switches are saved and off by default.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-017.029.M09 | `us_swing/src/us_swing/gui/app_service.py` | `_grow_pnl()`, `budget_capital()`, `strategy_allocation()`, `_cash_capped()`; both providers wired into RiskManager and StrategyEngine |
| MD-EXE-017.029.M01 | `us_swing/src/us_swing/execution/risk_manager.py` | Optional `allocation_provider`; `can_allocate` uses it for the strategy limit |
| MD-EXE-017.029.M03 | `us_swing/src/us_swing/execution/strategy_engine/_router.py`, `_engine.py` | Provider passed through the engine; `_size_entry` sizes from it |
| MD-EXE-017.031.M07 | `us_swing/src/us_swing/gui/strategy_store.py`, `gui/user_store.py`, `user/manager.py`, `data/models.py` | `grow_with_pnl` on StrategyConfig (DB column, added on load) and RiskConfig (users.json); missing = off |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-017.029 | Grow with P&L on: strategy allocation = Max Capital × allocation % + its closed P&L for the user, never below 0 | Implemented |
| SRD-EXE-017.030 | Grow with P&L on for any strategy: shared budget = Max Capital + closed P&L of growing strategies; live keeps 90%-of-cash cap | Implemented |
| SRD-EXE-017.031 | Strategy settings and user risk settings each save a Grow with P&L switch, off by default | Implemented |

---

## Design Decisions

- Budget is floored at 0. Found during tests: big losses could make the budget negative.
- Growth follows the strategy's tick OR the user's account switch. See DD-EXE-017.029.D01.
- Known limits: no P&L reset button; renaming a strategy starts it from $0.

---

## Issues Resolved

None

---

## Test Coverage

- New, Pass (8 tests): UT-EXE-017.029.M01.T01, .029.M03.T01, .029.M09.T01–T03, .030.M09.T01–T02, .031.M07.T01.
- 4 old failures in `tests/gui/test_manual_picks.py` also fail without these changes (T267). Not from this RN.
