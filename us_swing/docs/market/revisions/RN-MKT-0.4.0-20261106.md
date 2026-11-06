# Revision Note — RN-MKT-0.4.0-20261106

**Version:** 0.4.0
**Date:** 2026-11-06
**Tool:** MKT
**Artifact:** FO-MKT-004 / SRD-MKT-004.001–.009, SRD-DSK-001.022, SRD-GUI-034.014
**Type:** Feature

---

## Summary

Fourth market tool phase (P4): proof on past data. `desk proof` replays the P1–P3 rules for every past day on the Backtest Data daily candles, using only data up to that day. It measures the 5, 10 and 20-day return of every scored stock-day, entering at the next day's open, and its return against SPY. It groups the results by score band, setup and idea status, gives each side a pass or fail, keeps the run in `desk.db` and prints a report. A new Score proof panel on the Market Floor shows the latest run. Nothing was tuned.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-004.001.M01 | `us_swing/src/us_swing/market/proof_data.py` | New: reads `~/.usswing/backtest/1d/*.parquet` into daily bars with opens |
| MD-MKT-004.002.M02 | `us_swing/src/us_swing/market/proof.py` | New: replay, forward returns, groups, pass rule, report and run |
| MD-MKT-004.006.M03 | `us_swing/src/us_swing/market/store.py` | Changed: `proof_run` and `proof_stats` tables; `write_proof()`, `latest_proof()` |
| MD-GUI-034.014.M13 | `us_swing/src/us_swing/core/desk_floor.py` | Changed: serves `proof.bands` (filters side and kind) from the latest proof run |

Cross-tool files (plain-text note, not MD rows in this tool):
- `desk/cli.py` (MD-DSK-001.020.M06): new `desk proof` sub-command (SRD-DSK-001.022).
- `core/desk_steps.py` (MD-DSK-001.021.M07): `PROOF_PATH` and `load_proof()`; the desk loads the runner by import path.

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-004.001 | Daily bars of members and SPY come from the Backtest Data daily files, read only. | Implemented |
| SRD-MKT-004.002 | Every past day is recomputed with the P1–P3 rules from data up to that day; no earnings Watch. | Implemented |
| SRD-MKT-004.003 | 5, 10 and 20-day returns per side from the next open, and the same against SPY. | Implemented |
| SRD-MKT-004.004 | Results grouped by score band, setup and idea status per side and horizon. | Implemented |
| SRD-MKT-004.005 | A side passes when, at 10 days, 70+ beats SPY and beats under 40 (100 stock-days each). | Implemented |
| SRD-MKT-004.006 | Each run kept in `proof_run` and `proof_stats` in `desk.db`. | Implemented |
| SRD-MKT-004.007 | Under 5 years of daily history the report and panel point to Settings > Backtest Data. | Implemented |
| SRD-MKT-004.008 | Each run logs data range, stocks, days, time and result per side with `[Proof]`. | Implemented |
| SRD-MKT-004.009 | A run on 6 years of about 500 stocks finishes in under 10 minutes (2.8 years: 21 s). | Implemented |
| SRD-DSK-001.022 | `desk proof` runs the proof and prints its report; exit 1 when there is no data. | Implemented |
| SRD-GUI-034.014 | Score proof panel shows the latest run per side and group kind with data range and result. | Implemented |

---

## Design Decisions

- Daily candles come from the Backtest Data store (user choice). MKT reads its files directly, so it never imports the backtest tool.
- The same P1–P3 functions are reused in memory. Nothing is written to the daily desk tables.
- No tuning in P4 (user choice), so the proof is not fitted to the same data. T117 stays open.
- Report text is plain ASCII because the Windows console cannot print some symbols.
- After code review: `n` and the averages use the same rows; the Floor shows "-" for a missing value; the report states the survivorship limit.
- Known limits: today's S&P 500 list (survivorship); no earnings Watch for past days; overlapping daily samples; no costs, slippage or stop exits; only 2.8 years of daily data so far (TODO T118).

---

## Issues Resolved

None

---

## Test Coverage

- UT-MKT-004.* : 23 Pass (`tests/market/test_proof.py`).
- UT-DSK-001.022.M06.T01–T02: Pass (`tests/desk/test_cli.py`).
- UT-GUI-034.014.M13.T01–T02: Pass (`tests/gui/test_market_floor.py`).
- ruff and mypy --strict clean on changed files. Code review: code-reviewer APPROVE; 2 low findings fixed.
- Full suite: 2063 pass, 12 fail. The 12 are the same old failures (T112): candle_builder 9, sidebar_shell 1, preset 2. `test_llm_claude_screener.py` is left out because its module was never in the repo.
- Acceptance 1: forward returns of 3 stock-days x 3 horizons match a plain-Python hand check on the raw files (9 of 9 exact).
- Acceptance 2: against the desk's stored scores, 89.9% (2026-10-01), 95.2% (2026-10-20) and 95.4% (2026-11-04) are within 1 point. The first day is just under the 90% bar. The cause is proven to be the candle source: fed with `candles.db`, the replay equals the desk exactly on all 3 days (970, 968 and 968 rows). The two sources differ for some stocks (e.g. APH, MNST, CRWD), and `candles.db` is missing about 3,600 cells in the year before.
- Acceptance 3 and 4: `desk proof` printed the report with the reminder (exit 0, 21 s). In the real app the Score proof panel was added from the catalog and showed the same numbers, with the short / setup filter working. The layout file was restored afterwards.

## First Reading (2024-01-02 to 2026-11-04, 443 scored days)

- Long: **pass**. 10-day return against SPY rises with the band: under 40 −0.04%, 40–50 −0.11%, 50–60 +0.12%, 60–70 +0.32%, 70–80 +0.51%, 80+ +0.25%. Idea list +0.54%; Watch −1.15%.
- Short: **pass**. 70–80 +1.88% and 80+ +1.48% against SPY; under 40 −0.10%. Idea list +0.43%.
- Setups did not help: long Flat base −0.11%, Pullback −0.13% and Squeeze −0.81% (672 stock-days), against +0.09% for No setup. Short Breakdown +0.34%; Lower highs −0.20%. This is input for T117.
- Only 2.8 years, mostly one market type. Read with care until 5–6 years are downloaded (T118).
