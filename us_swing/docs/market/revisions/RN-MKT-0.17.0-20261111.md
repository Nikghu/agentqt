# Revision Note — RN-MKT-0.17.0-20261111

**Version:** 0.17.0
**Date:** 2026-11-11
**Tool:** MKT
**Artifact:** FO-MKT-015 / SRD-MKT-015.001–.012
**Type:** Feature

---

## Summary

Step F of the autonomous desk, skill 1: setup tuning research. A research ticket can now ask the desk to test a variant of one desk setup (5-year replay on daily bars) or of one live strategy (backtest engine, renamed copies). The skill only reports the result and names the winning values; it never changes a live setup or strategy. A desk-setup gain of +0.05R on 100+ trades writes one candidate lesson.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-015.001.M01 | `src/us_swing/market/setup_tuning.py` | New: setup tuning skill (pick, run, verdict, candidate lesson, logs) |
| MD-MKT-015.002.M02 | `src/us_swing/market/setup_knobs.py` | New: named setup limits with default and range |
| MD-MKT-015.002.M02 | `src/us_swing/market/setups.py` | Changed: reads its limits from knobs; defaults unchanged |
| MD-MKT-015.004.M03 | `src/us_swing/market/tuning_replay.py` | New: 5-year replay of one desk setup, result table, gain rule |
| MD-MKT-015.005.M04 | `src/us_swing/market/tuning_strategy.py` | New: strategy knobs, renamed copies, backtest run, R per trade |
| MD-MKT-015.001.M01 | `src/us_swing/market/employees/emp-013/` | New: default employee "Expert 10", skill `setup_tuning`, trigger `research_done` |
| MD-MKT-015.001.M01 | `SKILL_PATHS`, `USSwing.spec` | Changed: skill path added; build includes the new modules |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-015.001 | The setup tuning skill works `setup_tuning` tickets whose target is one desk setup or one live strategy | Implemented |
| SRD-MKT-015.002 | Each desk setup exposes its fixed limits as named knobs, with default and fixed range | Implemented |
| SRD-MKT-015.003 | The first step picks up to 3 variants, each changing at most 2 knobs or numeric strategy values | Implemented |
| SRD-MKT-015.004 | Code replays the baseline and each desk-setup variant on the last 5 years of daily bars for S&P 500 members | Implemented |
| SRD-MKT-015.005 | Code runs the baseline and each strategy variant on the backtest engine as renamed copies | Implemented |
| SRD-MKT-015.006 | Code builds a result table of trades, win rate, expectancy in R and change against the baseline | Implemented |
| SRD-MKT-015.007 | Code marks a gain when a variant beats the baseline by at least 0.05R on at least 100 trades | Implemented |
| SRD-MKT-015.008 | The last step makes one AI call that reads the table and writes a verdict of at most 600 characters | Implemented |
| SRD-MKT-015.009 | A desk-setup gain writes one candidate lesson tagged with setup and side, claim worse | Implemented |
| SRD-MKT-015.010 | The skill never changes a live setup, a strategy or the strategy list; it only names the winning values | Implemented |
| SRD-MKT-015.011 | Default employee ships as `emp-013` (skill `setup_tuning`) and its skill path is in `SKILL_PATHS` and the app build | Implemented |
| SRD-MKT-015.012 | Each step logs the target, the variant count and the gain | Implemented |

---

## Design Decisions

- Desk setup target: 5-year replay on Backtest Data daily bars (no tokens used).
- Live strategy target: backtest engine, renamed copies made by its strategy loader; copies are not saved as Backtest runs; workers 0.
- Strategy stocks: the strategy's own include list, else up to 30 AI-picked S&P 500 stocks.
- Gain (+0.05R on 100+ trades) is decided by code only; the AI reads the table and writes the verdict.
- Desk-setup gain writes one candidate lesson (claim worse, tags setup and side). Strategy gain writes none.
- Report only (user answer, 2026-11-11). Master applies changes by hand.
- Code review fixes: gain is filtered before the best variant is picked; number swap writes plain decimals and skips time and timeframe numbers; include list capped at 30; lesson save errors are caught.
- Known deviations (TODO T163): SRD-MKT-015.004 "In" cell says `candles.db`, but code uses Backtest Data. SRD-MKT-015.011 says "Researcher 1", but the generic-name rule (UT-MKT-005.017) forced "Expert 10".

---

## Issues Resolved

None

---

## Test Coverage

UT-MKT-015.* — 31 cases, all Pass (`tests/market/test_setup_tuning.py`).

Real-data check: 503 stocks load in about 5 s; one variant takes about 1 s. Backtest Data holds only 718 days (about 2.8 years), so the 5-year window is shorter in practice.

Test runs by folder (`.venv`): market 442 pass; desk 344; core 276; backtest 171; execution 375; broker 38; infrastructure 50; integration 8 (+2 skipped); mcp 8; GUI AI Desk files 194 pass. Pre-existing failures on main are unchanged: analysis `test_candle_builder` 9; screener `test_llm_claude_screener` import error and 2 model-id failures (TODO T112).

Coverage not measured: pytest-cov is not installed (TODO T165).
