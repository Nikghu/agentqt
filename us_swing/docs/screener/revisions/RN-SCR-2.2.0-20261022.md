# Revision Note — RN-SCR-2.2.0-20261022

**Version:** 2.2.0
**Date:** 2026-10-22
**Tool:** SCR
**Artifact:** FO-SCR-013 / SRD-SCR-015.001–015.017
**Type:** Feature

---

## Summary

The screener now uses a shared indicator catalogue (`core/indicator_rules`) and a rule list instead of the six fixed legacy filters. Each rule holds an indicator, a condition and a value, and a symbol passes only if all enabled rules pass. Legacy `filters` configs are read and mapped to equivalent rules, so old presets still load. ATR and RSI now use TA-Lib Wilder math, so results for old presets may shift slightly.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-SCR-015.001.M23 | `src/us_swing/core/indicator_rules/_catalogue.py` | New: indicator catalogue (27 entries, 21 available), categories, parameter specs |
| MD-SCR-015.008.M25 | `src/us_swing/core/indicator_rules/_ta.py` | New: TA-Lib backed series (EMA, RSI, ATR %, MACD, PPO, volume ratio, breakout) |
| MD-SCR-015.006.M24 | `src/us_swing/core/indicator_rules/_rules.py` | New: Rule model, schema-2 config, legacy `filters` mapping, label and summary text |
| MD-SCR-015.009.M26 | `src/us_swing/core/indicator_rules/_evaluate.py` | New: evaluates one rule on one symbol, with RS and market-cap context |
| MD-SCR-002.001.M04 | `src/us_swing/screener/screeners/indicator.py` | `apply()` and `screen_detailed()` evaluate the rule list; removed `_atr_pct`, `_rsi`, `_volume_ratio`, `_is_breakout`, `_rs_slope` |
| MD-SCR-003.001.M10 | `src/us_swing/screener/executor.py` | Stage 2 passes `market_caps` into the screener config (`{**ref.config, "market_caps": caps}`) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-SCR-015.001 | Read-only `CATALOGUE` of `IndicatorSpec` entries (id, name, category, params, conditions, availability) | Implemented |
| SRD-SCR-015.002 | `ParamSpec` holds key, label, kind, default, min, max and step | Implemented |
| SRD-SCR-015.003 | `Category` enum with display order | Implemented |
| SRD-SCR-015.004 | `Rule` holds indicator id, condition, value, optional upper value, params, enabled flag | Implemented |
| SRD-SCR-015.005 | `Condition` enum (at least, at most, between, crosses above/below signal, price above/below, is true) | Implemented |
| SRD-SCR-015.006 | `rules_to_config()` writes schema 2; `rules_from_config()` reads it back losslessly | Implemented |
| SRD-SCR-015.007 | Legacy `filters` dict maps to equivalent rules when no `rules` key exists | Implemented |
| SRD-SCR-015.008 | Indicator series computed with TA-Lib (Wilder ATR and RSI, EMA, MACD, PPO) | Implemented |
| SRD-SCR-015.009 | Conditions compare the last bar; "between" inclusive; crosses use last two bars | Implemented |
| SRD-SCR-015.010 | `apply()` passes a symbol only if all enabled rules pass; score = passed ÷ enabled | Implemented |
| SRD-SCR-015.011 | RS Index ranks computed once per run, only when an RS rule is enabled | Implemented |
| SRD-SCR-015.012 | Market Cap rules read caps passed from `run_preset(market_caps=...)` | Implemented |
| SRD-SCR-015.013 | Release 1 available list (Price, ATR %, RSI, Breakout, Volume ratio, RVOL 1 Day, RS Index, EMA, Price/EMA, MACD, PPO, Market Cap) | Implemented |
| SRD-SCR-015.014 | Intraday RVOL and Short-Term Volume listed unavailable ("needs intraday data") | Implemented |
| SRD-SCR-015.015 | `config_summary()` builds the Details-column text from the catalogue | Implemented |
| SRD-SCR-015.016 | `screen_detailed()` returns each rule's last value keyed by rule label | Implemented |
| SRD-SCR-015.017 | Private helpers `_atr_pct`, `_rsi`, `_volume_ratio`, `_is_breakout` removed; registry id `indicator_composite` unchanged | Implemented |

---

## Design Decisions

- Scope: migrate the six legacy filters and add new daily indicators. Intraday RVOL and Short-Term Volume are shown greyed out (TODO T34).
- Fundamentals: Market Cap only. Dividends are hidden (TODO T35).
- Storage: schema-2 rule list, with a reader for the legacy `filters` dict.
- ATR and RSI now use TA-Lib Wilder math, as SRD-SCR-002.003 requires. The old code used simple averages and high−low ATR, so results for old presets may shift slightly.
- The strategy-builder catalogue for EXE is not merged (TODO T36).

---

## Issues Resolved

None

---

## Test Coverage

46 unit tests (UT-SCR-015.*) specified and all Pass. Core and screener suites: 510 passed in total with the GUI tests. Two failures are pre-existing and unrelated (`tests/screener/test_preset.py` t17/t18, which expect the old `ai_model` default). `tests/screener/test_llm_claude_screener.py` has a pre-existing import error (module `llm_claude` no longer exists). ruff and mypy --strict: 0 errors in all new and changed modules.
