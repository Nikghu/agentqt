# Revision Note — RN-SCR-2.3.0-20261022

**Version:** 2.3.0
**Date:** 2026-10-22
**Tool:** SCR
**Artifact:** FO-SCR-014 / SRD-SCR-016.001–016.015
**Type:** Feature

---

## Summary

The screener's price action filter now uses a shared pattern catalogue (`core/price_patterns`) with 47 patterns: 27 TA-Lib candlesticks and 20 breakout, trend, volatility and chart-shape patterns. A symbol passes when its share of matched rules reaches the threshold. Legacy `patterns` configs are read and mapped to rules, so old presets still load, but saved values outside the new ranges are clamped. The price action logic no longer imports from the analysis tool.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-SCR-016.001.M27 | `src/us_swing/core/price_patterns/_spec.py`, `_catalogue.py` | New: pattern categories, directions, spec type; assembled 47-entry `PATTERNS` catalogue |
| MD-SCR-016.003.M28 | `src/us_swing/core/price_patterns/_candles.py` | New: 27 TA-Lib candlestick specs from one sign table |
| MD-SCR-016.005.M29 | `src/us_swing/core/price_patterns/_breakouts.py` | New: 20 breakout, trend, volatility and chart-shape specs (numpy) |
| MD-SCR-016.007.M30 | `src/us_swing/core/price_patterns/_rules.py` | New: `PatternRule` model, schema-2 config, legacy `patterns` mapping, summary text |
| MD-SCR-016.011.M31 | `src/us_swing/core/price_patterns/_evaluate.py` | New: evaluates one rule on one symbol with clamped params |
| — | `src/us_swing/core/price_patterns/__init__.py` | New: public surface of the package (no separate MD row) |
| MD-SCR-002.005.M08 | `src/us_swing/screener/screeners/price_action.py` | Rewritten: `apply()` and `screen_detailed()` use `core.price_patterns`; private pattern helpers and the analysis import removed |
| MD-SCR-015.006.M24 | `src/us_swing/core/indicator_rules/_rules.py` | Param-text code moved into a shared `format_param_values()` helper; output unchanged |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-SCR-016.001 | Read-only `PATTERNS` catalogue of `PatternSpec` entries (frozen, unique ids, reuses `ParamSpec`) | Implemented |
| SRD-SCR-016.002 | `PatternCategory` (7 values, enum order) and `Direction` (bullish, bearish, neutral) | Implemented |
| SRD-SCR-016.003 | 27 candlestick patterns use TA-Lib `CDL*`; two-sided functions match by sign, others by any non-zero value | Implemented |
| SRD-SCR-016.004 | Each candlestick pattern has a "within N bars" parameter (1–5, default 1) | Implemented |
| SRD-SCR-016.005 | 20 breakout, trend, volatility and chart-shape patterns computed from daily OHLCV with numpy | Implemented |
| SRD-SCR-016.006 | Near 52-Week High, Volume Breakout, NR7 and EMA Pullback keep legacy ids, params and results | Implemented |
| SRD-SCR-016.007 | `PatternRule` holds pattern id, params and enabled flag; missing params use catalogue defaults | Implemented |
| SRD-SCR-016.008 | `pattern_rules_to_config()` writes schema 2 and `pattern_rules_from_config()` reads it back losslessly | Implemented |
| SRD-SCR-016.009 | Legacy `patterns` dict maps to 5 rules when no `rules` key exists; `engulfing` maps to Bullish Engulfing | Implemented |
| SRD-SCR-016.010 | Unknown ids, bad params and malformed rule lists raise `PatternRuleError` | Implemented |
| SRD-SCR-016.011 | `evaluate_pattern()` clamps params to range; too few bars or NaN values give no match | Implemented |
| SRD-SCR-016.012 | `PriceActionScreener.apply()` scores matched ÷ enabled and passes score ≥ threshold | Implemented |
| SRD-SCR-016.013 | `screen_detailed()` returns a match flag per enabled rule, keyed by short label | Implemented |
| SRD-SCR-016.014 | `pattern_config_summary()` builds the Details text (threshold plus one label per enabled rule) | Implemented |
| SRD-SCR-016.015 | `price_action.py` uses only `core/price_patterns`; no analysis-tool import; registry id unchanged | Implemented |

---

## Design Decisions

- Scope: 47 patterns in one catalogue, so the GUI library and the screener share one source.
- The 4 legacy patterns (Near 52W High, Volume Breakout, NR7, EMA Pullback) give identical results to the old code (tested on 200 windows). EMA Pullback keeps the first-close-seeded EMA.
- Legacy `engulfing` maps to TA-Lib Bullish Engulfing. It needs 3 bars instead of 2 and may differ when open and close prices are equal.
- Saved legacy params outside the new ranges are clamped (for example, 52W lookback below 20 becomes 20; Volume Breakout lookback below 5 becomes 5).
- Double Bottom and Cup with Handle are rough checks and can give false matches.
- Bollinger Squeeze needs a strict new low, so a flat series never matches.
- One-sided TA-Lib functions (for example Gravestone Doji, which returns +100) match on any signal. Only Engulfing, Harami, 3 Inside and 3 Outside are split by sign.
- Review (code-reviewer): APPROVE. Fixed: non-finite params and non-object legacy sections now raise `PatternRuleError`.

---

## Issues Resolved

None

---

## Test Coverage

35 unit test rows (UT-SCR-016.*) Pass. Parametrised cases: 27 candlestick plus 16 + 16 breakout. Legacy tests T01–T08 in `tests/screener/test_price_action_screener.py` are kept and pass. Coverage not measured (pytest-cov and coverage are not installed). ruff and mypy --strict: 0 errors in new and changed modules. Known unrelated failures: `tests/screener/test_preset.py` t17/t18 (old `ai_model` default).
