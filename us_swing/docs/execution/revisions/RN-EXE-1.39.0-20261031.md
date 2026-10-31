# Revision Note — RN-EXE-1.39.0-20261031

**Version:** 1.39.0
**Date:** 2026-10-31
**Tool:** EXE (also BKT, GUI)
**Artifact:** FO-EXE-011 / SRD-EXE-011.026, FO-BKT-002 / SRD-BKT-002.082, FO-GUI-013 / SRD-GUI-013.022
**Type:** Bugfix

---

## Summary

SWING's window included the latest bar, so `close > SWING(High, N)` could never fire. SWING now takes a Window arg: `Previous` (the N closed bars before the latest) or `Current` (old behaviour). LookbackDays and Type are gone from the form, Candles must be 1–500, and live and backtest share one arg parser.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-011.001.M03 | `execution/strategy_engine/_evaluator.py` | New `swing_args()`; `_fn_swing` honours Window; Candles < 1 raises; dead code removed |
| MD-BKT-002.020.M09 | `core/expr/__init__.py` | Re-exports `swing_args` |
| MD-BKT-002.021.M10 | `core/expr/series.py` | `_swing` uses `swing_args`, shifts one bar for `Previous`; SWING arity 5, legacy 6 |
| MD-GUI-013.001.M01 | `gui/strategy_builder_dialog.py` | SWING form: Window replaces Type, LookbackDays removed, Candles 1–500; out-of-range input refused |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-011.026 | SWING Window and arg forms in the live engine | Implemented |
| SRD-BKT-002.082 | SWING series matches live for both windows and both arg forms | Implemented |
| SRD-GUI-013.022 | SWING form fields | Implemented |

---

## Design Decisions

- User approved 2026-10-31: `Type` becomes `Window` (Previous / Current); visual explainer at https://claude.ai/artifact/Cjxy7fZRyp6i6kAX1LXioH.
- Root cause was a scope gap, so new SRD rows were added; Approved SRD-GUI-013.006 / SRD-EXE-011.006 were not edited.
- Legacy 6-arg SWING strings still load and read as `Current`, so saved strategies behave as before.
- Non-numeric Candles raises `ValueError`, like the other indicators; the form only allows integers.

---

## Issues Resolved

ISS-EXE-0014

---

## Test Coverage

- New: UT-EXE-011.026.M03.T01–T05, UT-BKT-002.082.M10.T01–T02, UT-GUI-013.022.M01.T01–T02 — all Pass (40 in the three files).
- Full suite on `main` + fix: 1648 passed; 11 failed and 22 errors are the same as on clean `main` (`test_candle_builder`, `test_preset`, `test_chart_workspace`); `test_llm_claude_screener.py` fails to import on `main` too.
- `ruff` clean; `mypy --strict` no new errors (80 existing on `main`).
