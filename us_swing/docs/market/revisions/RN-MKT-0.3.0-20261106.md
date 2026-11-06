# Revision Note — RN-MKT-0.3.0-20261106

**Version:** 0.3.0
**Date:** 2026-11-06
**Tool:** MKT
**Artifact:** FO-MKT-003 / SRD-MKT-003.001–.012, SRD-GUI-034.013
**Type:** Feature

---

## Summary

Third market tool phase (P3). The desk now scores each stock for a long and a short idea: money flow, a setup (long: Squeeze, Flat base, Pullback; short: Failed breakout, Lower highs, Breakdown), RS, sector and regime. Each side keeps its top 10 stocks with a score of 60 or more; a stock with earnings within 5 trading days, or against the market regime, goes to Watch. It runs as the desk step "Ideas" after "Sectors", and the Floor shows the real Top ideas with their data date (no Sample tag).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-003.001.M01 | `us_swing/src/us_swing/market/candles.py` | Changed: daily bars include volume |
| MD-MKT-003.002.M02 | `us_swing/src/us_swing/market/flow.py` | New: dollar volume, money flow and rolling helper |
| MD-MKT-003.003.M03 | `us_swing/src/us_swing/market/setups.py` | New: long and short setups with trigger, stop and tightness |
| MD-MKT-003.005.M04 | `us_swing/src/us_swing/market/score.py` | New: score parts, extended penalty, ideas, Watch and reasons |
| MD-MKT-003.009.M05 | `us_swing/src/us_swing/market/earnings.py` | New: next earnings dates from Yahoo Finance |
| MD-MKT-003.010.M06 | `us_swing/src/us_swing/market/store.py` | Changed: `stock_score`, `ideas` and `idea_reasons` tables; day-wise write and read |
| MD-MKT-003.011.M07 | `us_swing/src/us_swing/market/idea_step.py` | New: desk step "Ideas" (history fill, last 7 days, safety checks) |
| MD-GUI-034.013.M12 | `us_swing/src/us_swing/core/desk_floor.py` | Changed: serves `ideas.top` (filters side and status) from `desk.db` |
| MD-GUI-034.013.M12 | `us_swing/src/us_swing/gui/floor_panel.py` | Changed: "why" column takes spare width before "trigger" so prices show in full |

Cross-tool files (plain-text note, not MD rows in this tool):
- `core/desk_steps.py` (MD-DSK-001.021.M07): `STEP_PATHS` adds `IdeaStep` after `SectorStep`.

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-003.001 | Daily bars include volume; stocks under $20M average dollar volume (20 days) are not scored. | Implemented |
| SRD-MKT-003.002 | Money flow (0–1): net accumulation days, 20-day Chaikin money flow and 50-day up vs down volume; short is 1 minus long. | Implemented |
| SRD-MKT-003.003 | Long setups: Squeeze, Flat base, Pullback; best match kept with trigger, stop and tightness. | Implemented |
| SRD-MKT-003.004 | Short setups: Failed breakout, Lower highs, Breakdown; best match kept with trigger, stop and tightness. | Implemented |
| SRD-MKT-003.005 | Score: RS 20, money flow 20, setup 20, sector 15, regime 15, scaled by 100/90 while news is not scored. | Implemented |
| SRD-MKT-003.006 | Stock more than 8% past its 20-day average in the idea's direction loses 10 points; score never below 0. | Implemented |
| SRD-MKT-003.007 | Per side, top 10 stocks scoring 60 or more are ideas; earnings within 5 trading days or against the regime goes to Watch. | Implemented |
| SRD-MKT-003.008 | Each idea and Watch name keeps up to 5 plain-word reasons with setup, trigger and stop. | Implemented |
| SRD-MKT-003.009 | Next earnings dates from Yahoo Finance for the top 30 per side, latest day only; a failed fetch gives a note. | Implemented |
| SRD-MKT-003.010 | Results kept in `stock_score`, `ideas` and `idea_reasons` in `desk.db`; re-run replaces the day. | Implemented |
| SRD-MKT-003.011 | Desk step "Ideas" after "Sectors"; fills history, recomputes last 7 days, skips days under 80% coverage. | Implemented |
| SRD-MKT-003.012 | Each run logs days added, idea and Watch counts per side and top 3 ideas per side with `[Ideas]` prefix. | Implemented |
| SRD-GUI-034.013 | Top ideas panels read the latest ideas from `desk.db` with data date, trigger, stop and first reason, no Sample tag. | Implemented |

---

## Design Decisions

- News is not scored yet: the 10 news points are left out and the score is scaled by 100/90 until P5c.
- Earnings are checked from Yahoo only for the top 30 per side on the latest day (speed and rate limits).
- A stock against the regime (shorts in an Uptrend, longs in a Downtrend) goes to Watch on both sides.
- Failed-breakout stop is the 10-day high (after code review).
- Watch notes come first in the reasons list (after code review).
- Speed (code review): history trimmed to 460 rows, ATR computed once, numpy rolling helper, earnings calls in parallel with a 10 s timeout per 30 names. First run 43 s → 19 s; daily run 15 s → 7 s.
- Incomplete volume window gives no money flow for that stock.
- Known limits: no news or gap-risk penalty until P5c; earnings only for the latest day; Squeeze is rare (TODO T117); survivorship (today's S&P 500 list).

---

## Issues Resolved

None

---

## Test Coverage

- UT-MKT-003.* : 35 Pass (`tests/market/test_ideas.py` 30, `tests/market/test_idea_step.py` 5).
- UT-GUI-034.013.M12.T01–T02: Pass (2 tests in `tests/gui/test_market_floor.py`).
- Market tests 87 pass; floor tests 21 pass; ruff and mypy --strict clean on changed files.
- Full suite: 2036 pass, 12 fail. The same 12 fail on a clean HEAD (pre-existing, TODO T112).
- Code review: code-reviewer NEEDS CHANGES (no formula bugs) — fixed; pyqt-code-reviewer approve.
- Real checks: smoke run on real candles and a copy of real `desk.db` gave 341 days (2025-06-30 to 2026-11-04) and 329,714 score rows. Plain-Python hand check on 2026-03-17, 2026-11-03 and 2026-11-04: 18 stock-days, all six setup types, every score part, setup, trigger and stop match. Real desk run ok in 25 s; latest day 10 long and 10 short ideas, 7 + 1 on Watch. Real app: Overview and Ideas tabs show real Top ideas (2026-11-04) without Sample tag; trigger and stop shown in full after the column fix.
- Latest real reading (2026-11-04, regime Choppy): top longs TRV (Flat base 72), EL, WSM; top shorts NVDA (Lower highs 73), AVGO, TER.
