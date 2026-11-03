# Revision Note — RN-EXE-1.41.0-20261102

**Version:** 1.41.0
**Date:** 2026-11-02
**Tool:** EXE (also BKT, GUI)
**Artifact:** FO-EXE-011 / SRD-EXE-011.027, FO-BKT-002 / SRD-BKT-002.087, FO-GUI-013 / SRD-GUI-013.024
**Type:** Feature

---

## Summary

New trigger indicator `BOSS_ST(SymbolType, SwingLookback, MinBreakATR, HTF, LTF, Signal)`, ported from the user's NSE BOSS_ST strategy. It returns 1 (long), -1 (short) or 0 (flat) on the last closed LTF bar; Signal `Fresh` returns the value only on the bar the position changed. No time window and no forced exit, so trades can be held overnight. Live and backtest share one core module.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-011.027.M01 | `core/market_structure.py` | New — causal swings, ATR break gate, BOS / CHOCH, HTF CHOCH on LTF at bar close, EMA200, Supertrend(10,3), position state machine |
| MD-EXE-011.001.M03 | `execution/strategy_engine/_evaluator.py` | New `boss_st_args()` and `BOSS_ST` in `FUNCTION_MAP` |
| MD-BKT-002.020.M09 | `core/expr/__init__.py` | Re-exports `boss_st_args` |
| MD-BKT-002.021.M10 | `core/expr/series.py` | BOSS_ST arity 6; walker reads it on the LTF frame, not the last arg |
| MD-GUI-013.001.M01 | `gui/strategy_builder_dialog.py` | BOSS_ST form (6 fields, defaults first); float Range validator; HTF must be above LTF |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-011.027 | BOSS_ST live indicator | Implemented |
| SRD-BKT-002.087 | BOSS_ST backtest series matches live | Implemented |
| SRD-GUI-013.024 | BOSS_ST form | Implemented |

---

## Design Decisions

- User approved 2026-11-02: one indicator returning 1 / -1 / 0; long and short as two strategies for now (Direction = Both is Phase 2); Entry uses Fresh, Exit uses State.
- Not enough history returns NaN, so the evaluator raises and skips the stock; 0 would wrongly fire an exit such as `State != 1`.
- EMA200, Supertrend(10,3) and ATR(14) are fixed, as in the source strategy.
- Supertrend direction follows the source's pandas_ta logic on a Wilder ATR (TA-Lib), so values can differ slightly from the source in the first bars.
- The state machine runs from the first loaded bar, so live (about 30 days) and backtest (45 days warm-up) can differ until both have seen the same trend turn.

---

## Test Coverage

- New: UT-EXE-011.027.M01.T01–T07, UT-EXE-011.027.M03.T01–T03, UT-BKT-002.087.M10.T01–T02, UT-GUI-013.024.M01.T01–T02 — all Pass. UT-EXE-011.001.M03.T08 updated to 11 indicators.
- `tests/core`, `tests/execution`, `tests/backtest`, strategy builder GUI tests: 784 passed.
- `ruff` clean; `mypy --strict` no new errors (82 existing).
