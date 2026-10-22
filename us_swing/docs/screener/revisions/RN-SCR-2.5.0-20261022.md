# Revision Note — RN-SCR-2.5.0-20261022

**Version:** 2.5.0
**Date:** 2026-10-22
**Tool:** SCR
**Artifact:** FO-SCR-014 / SRD-SCR-016.018
**Type:** Feature

---

## Summary

Two Fibonacci retracement patterns were added under **Trend**. The catalogue grows from 49 to
51 patterns, and Trend from 6 to 8. The dialog picks them up from the catalogue, with no GUI
change.

| Pattern | Matches when |
|---|---|
| **Fib Retracement (Sell)** (bear) | Last swing in the window is a fall (swing high → swing low, ≥ 5 bars apart, ≥ min swing %). The latest bar's high reaches the zone, and no close since the low is above the zone top |
| **Fib Retracement (Buy)** (bull) | Mirror: last swing is a rise; the latest bar's low dips into the zone, and no close since the high is below the zone bottom |

Settings: Lookback 60 · Zone from 50 % · Zone to 61.8 % · Min swing 10 %. The zone is measured
from the swing end, as on a chart's Fibonacci tool (Sell: from the low up; Buy: from the high
down). A zone with "from" above "to" never matches.

User decisions (2026-10-22): both directions as two patterns; match while price is in the
zone (rejection is confirmed by the user); default golden zone 50–61.8 %.

## Results on the current DB

Daily: 54 Sell, 10 Buy. Weekly: 7 Sell, 33 Buy. ABT daily checked by hand: fall 117.34 →
95.06, zone 106.20–108.83, last high 106.35, close 100.51.

## Files

| File | Change |
|---|---|
| `core/price_patterns/_breakouts.py` | `_fib_retracement_sell()`, `_fib_retracement_buy()`, `_FIB_PARAMS`, 2 catalogue entries |
| `tests/core/test_price_pattern_breakouts.py` | 2 built series (positive + flat-negative via T01/T02) and 3 tests (UT-SCR-016.018.M29.T01–T03) |
| `tests/core/test_price_pattern_catalogue.py`, `test_price_pattern_rules.py` | Counts 49 → 51, Trend 6 → 8 |

## Verification

- `tests/core` + `tests/screener/test_price_action_screener.py`: 273 passed
- `ruff` and `mypy --strict` on `core/price_patterns/`: clean

## Notes

- The swing is the lowest low (Sell) or highest high (Buy) in the lookback, so a longer
  lookback measures a bigger swing. Match on a wick is allowed — "in zone now", not a confirmed
  rejection.
