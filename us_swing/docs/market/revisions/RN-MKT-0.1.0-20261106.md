# Revision Note — RN-MKT-0.1.0-20261106

**Version:** 0.1.0
**Date:** 2026-11-06
**Tool:** MKT
**Artifact:** FO-MKT-001 / SRD-MKT-001.001–.012
**Type:** Feature

---

## Summary

First market tool phase (P1). The new `market/` package reads daily candles from `candles.db` (read-only), works out the SPY regime, volatility, breadth, 52-week highs and lows, and a fear score, and stores one row per trading day in `desk.db`. It runs as the desk step "Market regime", and the Floor now shows real regime and breadth data after each desk run.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-001.001.M01 | `us_swing/src/us_swing/market/candles.py` | New: read-only daily bars for SPY and S&P 500 members |
| MD-MKT-001.002.M02 | `us_swing/src/us_swing/market/regime.py` | New: pure rules for regime, volatility, breadth and fear |
| MD-MKT-001.005.M03 | `us_swing/src/us_swing/market/vix.py` | New: daily VIX and VIX3M fetch from Yahoo Finance |
| MD-MKT-001.007.M04 | `us_swing/src/us_swing/market/store.py` | New: market tables in `desk.db` |
| MD-MKT-001.011.M05 | `us_swing/src/us_swing/market/step.py` | New: desk step "Market regime" (incremental compute and save) |

Cross-tool files (plain-text note, not MD rows in this tool):
- `core/desk_steps.py` (MD-DSK-001.021.M07): loads desk steps by path.
- `core/desk_floor.py` and `gui/market_floor.py` (MD-GUI-034.011.M10): `DeskFloorData` shows real regime and breadth; refreshes after a desk run.

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-001.001 | Daily bars for SPY and S&P 500 members are read from `candles.db` read-only. | Implemented |
| SRD-MKT-001.002 | Regime: Uptrend, Downtrend or Choppy from SPY vs 50/200-day averages and 50-day slope. | Implemented |
| SRD-MKT-001.003 | Volatility: 20-day annualised swing, Calm / Normal / High by 30th and 70th percentile of 252 days. | Implemented |
| SRD-MKT-001.004 | Breadth: share above 20/50/200-day averages, 52-week highs and lows, advancers and decliners. | Implemented |
| SRD-MKT-001.005 | Daily VIX and VIX3M from Yahoo Finance kept in `desk.db`; a failure never stops the step. | Implemented |
| SRD-MKT-001.006 | Fear score (Calm 0–1, Nervous 2–3, Fearful 4+) from VIX, VIX vs VIX3M, High volatility, weak breadth. | Implemented |
| SRD-MKT-001.007 | Results in `regime_snapshot` and `breadth_daily` in `desk.db`, one row per trading day. | Implemented |
| SRD-MKT-001.008 | First run fills all days with enough history; later runs add only missing days. | Implemented |
| SRD-MKT-001.009 | A day with data for fewer than 80% of members is not stored and is logged. | Implemented |
| SRD-MKT-001.010 | Data date is the latest SPY candle; older than the last weekday is noted as stale. | Implemented |
| SRD-MKT-001.011 | Work runs as the desk step "Market regime"; `market` never imports `desk`. | Implemented |
| SRD-MKT-001.012 | Each run logs days added, latest regime and fear, and the data date. | Implemented |

Cross-tool requirements (plain-text note): SRD-DSK-001.021 (desk step loading by path) and SRD-GUI-034.011 (Floor shows real regime and breadth, refreshed after a desk run), both Implemented.

---

## Design Decisions

- Fear points: VIX ≥ 20 +1, VIX ≥ 30 +2; VIX above VIX3M +2; High volatility +1; share above 50-day below 40% +1.
- Each run recomputes the last 7 days and fills any gaps.
- Breadth uses today's S&P 500 members (survivorship bias accepted for P1).
- Missing candles never fail the desk run; the step logs and continues.

---

## Issues Resolved

None

---

## Test Coverage

- UT-MKT-001.* : 28 Pass.
- UT-DSK-001.021.M07.T01–T02 and UT-GUI-034.011.M10.T01–T03: Pass.
- 132 tests pass across desk, market and GUI desk / Floor.
- Hand check on 2025-09-15, 2026-04-08 and 2026-11-04 matches exactly.
- Real desk run filled 341 days (2025-06-30 to 2026-11-04).
- Code review: 2 HIGH and 4 MEDIUM findings fixed.
- Known limits: history starts 2025-06 (SPY has 612 daily bars; fill older SPY before P4); desk does not download candles yet (stale note shown); card label reads "Vix" not "VIX".
