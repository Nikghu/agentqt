# ISS-EXE-0014 — SWING can never fire a breakout; unused args; bad Candles diverge

**Tool:** EXE (also BKT, GUI) · **Severity:** Medium · **Status:** Fixed · **Date:** 2026-10-31
**Affected:** MD-EXE-011.001.M03, MD-BKT-002.021.M10, MD-GUI-013.001.M01

## Expected
`Price(close) > SWING(High, N)` fires when the close breaks the last N highs, in live and backtest alike.

## Actual
| # | Problem | Effect |
|---|---|---|
| 1 | The window includes the latest bar | `close > SWING(High)` and `close < SWING(Low)` are always false, with no error |
| 2 | `LookbackDays` and `Type` are required in the form but ignored | Misleading; dead code after a `raise` in `_fn_swing` |
| 3 | Candles 0 / negative accepted | Live `tail(-5)` drops the first 5 bars; backtest gives NaN — engines disagree |

## Root cause
Scope gap: no SRD defined SWING's window or arguments (only listed in SRD-EXE-011.006 / SRD-GUI-013.006 / SRD-BKT-002.021).

## Fix
New SRD-EXE-011.026, SRD-BKT-002.082, SRD-GUI-013.022. `Type` becomes `Window` (`Previous` / `Current`), `LookbackDays` removed, Candles ≥ 1. One shared `swing_args` parser for both engines; legacy 6-arg strings read as `Current`.
