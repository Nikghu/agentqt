# Revision Note — RN-MKT-0.2.0-20261106

**Version:** 0.2.0
**Date:** 2026-11-06
**Tool:** MKT
**Artifact:** FO-MKT-002 / SRD-MKT-002.001–.010, SRD-GUI-034.012
**Type:** Feature

---

## Summary

Second market tool phase (P2). The desk now works out sector strength for the 11 S&P 500 sectors (equal-weight lines from member candles), a rotation view (RS-ratio and RS-momentum quadrants), and a stock relative strength score with a 1–99 rating and sector rank. It runs as the desk step "Sectors" after "Market regime", and the Floor shows real sector strength, sector rotation and RS leaders with their data date (no Sample tag).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-002.001.M01 | `us_swing/src/us_swing/market/candles.py` | Changed: `member_sectors()` gives each member's sector (`SectorMembers`) |
| MD-MKT-002.002.M02 | `us_swing/src/us_swing/market/sectors.py` | New: sector lines, sector table and quadrant rules |
| MD-MKT-002.006.M03 | `us_swing/src/us_swing/market/rs.py` | New: stock RS score, 1–99 rating and sector rank |
| MD-MKT-002.008.M04 | `us_swing/src/us_swing/market/store.py` | Changed: `sector_daily` and `stock_rs` tables; day-wise write and read of dates |
| MD-MKT-002.009.M05 | `us_swing/src/us_swing/market/sector_step.py` | New: desk step "Sectors" (recompute, coverage check, save) |

Cross-tool files (plain-text note, not MD rows in this tool):
- `core/desk_steps.py` (MD-DSK-001.021.M07): `STEP_PATHS` adds `SectorStep` after `RegimeStep`.
- `core/desk_floor.py` (MD-GUI-034.012.M11): serves `sectors.rank`, `sectors.rrg` and `rs.leaders` (top 30, sector filter, listed only when stock RS rows exist).

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-002.001 | Each member stock gets its sector from the saved S&P 500 list; candles are aligned to SPY days. | Implemented |
| SRD-MKT-002.002 | Sector line starts at 100 and moves by the average daily move of its members. | Implemented |
| SRD-MKT-002.003 | Sectors ranked 1–11 by average of 1, 3 and 6-month moves minus SPY. | Implemented |
| SRD-MKT-002.004 | RS-ratio and RS-momentum, both on a base of 100, against SPY. | Implemented |
| SRD-MKT-002.005 | Quadrant: Leading, Weakening, Lagging or Improving. | Implemented |
| SRD-MKT-002.006 | Stock RS score (40% 3-month, 20% each for 6, 9, 12-month) and rating 1–99. | Implemented |
| SRD-MKT-002.007 | Rank of each rated stock inside its sector, with sector size. | Implemented |
| SRD-MKT-002.008 | Results in `sector_daily` and `stock_rs` in `desk.db`; re-run replaces the day. | Implemented |
| SRD-MKT-002.009 | Desk step "Sectors" after "Market regime"; fills history, recomputes last 7 days, skips days under 80% coverage. | Implemented |
| SRD-MKT-002.010 | Each run logs days added, top 3 sectors and quadrant changes with `[Sectors]` prefix. | Implemented |

Cross-tool requirement (plain-text note): SRD-GUI-034.012 (Sector strength, Sector rotation and RS leaders panels read `desk.db` with data date, no Sample tag), Implemented.

---

## Design Decisions

- Sector lines are equal weight from member candles; industry groups come later.
- Look-back close uses the last close up to 5 days before when the exact day is missing.
- Rating is the percentile among members (`ceil(pct × 99)`, 1–99); stocks with under 95% of 252 bars get no rating.
- Missing candles never fail the desk run; the step logs and continues.
- Speed (code review): rows built in one pass; first run 38 s → about 15 s, daily run about 5 s.
- Known limit: a late backfill can change a stored sector line; ranks and ratios are not affected (TODO T115).

---

## Issues Resolved

None

---

## Test Coverage

- UT-MKT-002.* : 22 Pass (`tests/market/test_sectors.py` 17, `tests/market/test_sector_step.py` 5).
- UT-GUI-034.012.M11.T01–T02: Pass (2 new in `tests/gui/test_market_floor.py`).
- Market tests 52 pass; floor tests 19 pass; ruff and mypy --strict clean on changed files.
- Full suite: 1999 pass, 12 fail. The same 12 fail on a clean HEAD worktree (pre-existing, TODO T112).
- Real checks: smoke run on real candles gave 360 days (2025-06-02 to 2026-11-04), 11 sectors, 487 rated stocks. Hand check in plain Python on 2026-04-15 and 2026-11-04 matches all 11 ranks and quadrants (max number diff 7e-14). Real desk run ok in 13 s. Real app check of Sectors tab and RS leaders (filter Energy) OK; user check pending (TODO T114).
