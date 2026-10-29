# Revision Note — RN-BKT-1.4.0-20261029

**Version:** 1.4.0
**Date:** 2026-10-29
**Tool:** BKT
**Artifact:** FO-BKT-002 / SRD-BKT-002.030–.039
**Type:** Feature

---

## Summary

Backtest engine Phase 3 (Step 3 · Portfolio). For each variant, one shared account trades the signals of the picked strategies, only on stocks in the previous day's top-N list. It copies the live money rules (per-trade size, strategy limit, margin cut), fills at the next 3m open with slippage and commission, exits by stop, target, end time or the exit condition, limits re-entries per day by the Rex count, and stops new entries after the daily loss limit. Every decision is logged, and trades, the day log and money by day are saved in `results.db`. Minimal requirements; approved by the user for code on 2026-10-29.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.030.M12 | `backtest/steps/portfolio.py` | New — day loop, money rules, exits, logs, refusals |
| MD-BKT-002.007.M04 | `backtest/results.py` | `save_variant()`, `read_table()`; `variants`, `trades`, `day_log`, `money_daily` tables |
| MD-BKT-002.008.M05 | `backtest/service.py` | `run_portfolio()`; run row helper passes the run id |
| MD-BKT-002.009.M06 | `backtest/cli.py` | `run` prints trades, net P&L and win rate per variant |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.030 | One timeline, yesterday's top-N list, D3 ranking | Implemented |
| SRD-BKT-002.031–.032 | Sizing, strategy limit, margin | Implemented |
| SRD-BKT-002.033–.034 | Next-open fills with costs; one position per stock; Rex per day | Implemented |
| SRD-BKT-002.035–.037 | Exit order, % levels, SHORT, end time, swing overnight | Implemented |
| SRD-BKT-002.038 | Daily loss stop | Implemented |
| SRD-BKT-002.039 | Results saved | Implemented |

---

## Tests

- 16 new tests (UT-BKT-002.030–.039, hand-made bars), all pass; backtest + Backtest GUI + live evaluator tests 159 passed. `ruff` and `mypy --strict` clean.
- Real data, CLI: ST_AUTO on IT top 5 (2026-01-02 to 2026-10-28), capital $2,000 and $5,000 → 104 and 103 trades; decisions entered 104, no_margin 26, rex_limit 17, daily_loss_stop 10; 12 s for Steps 1–3.

---

## Notes

- Differences from live, chosen by the user: Rex resets daily; daily loss blocks entries; the stop wins when stop and target are in one bar. Live checks levels per tick; the backtest uses 3m high / low.
- Deferred: shadow P&L of skipped signals, 3m equity Parquet, parallel variants, trailing levels, PNL conditions, Grow with P&L (the last three stop the run with a message).
