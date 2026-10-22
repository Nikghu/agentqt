# Revision Note — RN-SCR-2.4.0-20261022

**Version:** 2.4.0
**Date:** 2026-10-22
**Tool:** SCR
**Artifact:** FO-SCR-014 / SRD-SCR-016.016–016.017
**Type:** Feature

---

## Summary

Two bearish chart shapes were added for sell setups, and Double Bottom now ignores stale
breakouts. The catalogue grows from 47 to 49 patterns, and Chart shapes from 2 to 4. The
dialog picks them up from the catalogue, with no GUI change.

| Pattern | Matches when | Settings (default) |
|---|---|---|
| **Double Top** (new, bear) | Two similar highs, then the first close below the neck (lowest low between the tops) is in the last N bars and the last close is still below it | Lookback 60 · Tolerance 3 % · Breakdown within 5 |
| **Double Top Pullback** (new, bear) | Double Top breakdown 1–N bars ago, every close since is below the neck, and the last bar's high is within `near` % of the neck — the retest / sell-entry zone | Lookback 60 · Tolerance 3 % · Breakdown within 10 · Near neck 2 % |
| **Double Bottom** (changed) | As before, plus the first close above the neck must be in the last N bars | New: Breakout within 5 |

User decisions (2026-10-22): breakdown and pullback as two separate patterns; Double Bottom
gets "breakout within N bars".

## Behaviour change

Saved presets that use Double Bottom pick up `within` = 5 by default, so stale breakouts no
longer match. On the current DB: daily 39 → 15 matches, weekly 22 → 4.

New patterns on the current DB: Double Top — 5 daily (AMAT, DXCM, FIX, KLAC, LRCX), 1 weekly
(ES); Double Top Pullback — 0 daily, 3 weekly (AON, DOV, MAA). AMAT and AON checked by hand.

## Files

| File | Change |
|---|---|
| `core/price_patterns/_breakouts.py` | `_bars_since_first()`, `_double_top_breakdown()`, `_double_top()`, `_double_top_pullback()`; `within` in `_double_bottom()`; 2 new catalogue entries |
| `tests/core/test_price_pattern_breakouts.py` | 2 built series (positive + flat-negative via the parametrised T01/T02) and 3 negative tests |
| `tests/core/test_price_pattern_catalogue.py`, `test_price_pattern_rules.py` | Counts 47 → 49, chart shapes 2 → 4 |

## Verification

- `tests/core` + `tests/screener/test_price_action_screener.py`: 266 passed
- `ruff` and `mypy --strict` on `core/price_patterns/`: clean

## Notes

- All four chart shapes stay rough checks; expect some loose matches.
