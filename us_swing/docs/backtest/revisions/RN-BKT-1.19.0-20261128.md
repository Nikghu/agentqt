# Revision Note — RN-BKT-1.19.0-20261128

**Version:** 1.19.0
**Date:** 2026-11-28
**Tool:** BKT
**Artifact:** FO-BKT-002 / SRD-BKT-002.098–.099
**Type:** Feature + Bugfix

---

## Summary

Backtest Grow with P&L: a strategy's limit grows with its own closed-trade P&L (never below 0), and free cash counts all closed P&L. Also fixes an app freeze in Step 3 of full S&P 500 runs by removing the whole-period time index from each stock's bars. On the IT sector test, Step 3 memory fell from 2,459 MB to 857 MB and time from 182 s to 139 s, with the same trades and net P&L.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.030.M12 | `us_swing/src/us_swing/backtest/steps/portfolio.py` | Grow with P&L limit and free cash (SRD-BKT-002.098–.099); `_Bars.index` removed, `_Sim.run_day` builds a per-day time map (ISS-BKT-0004) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.098 | With Grow with P&L on, a strategy's limit = start capital × allocation % + its closed net P&L, never below 0 | Implemented |
| SRD-BKT-002.099 | With Grow with P&L on, free cash = start capital + all closed P&L − open cost | Implemented |

---

## Design Decisions

- Grow with P&L uses closed trades only. It replaces the Grow-with-P&L refusal part of SRD-BKT-002.036. See DD-BKT-002.098.D01.
- Grow with P&L is on when the run switch or the strategy's own tick is on. Off keeps today's sizing exactly.
- ISS-BKT-0004 fix: no SRD change, behaviour unchanged.

---

## Issues Resolved

- ISS-BKT-0004 — App froze in Step 3 of a full S&P 500 run. Code fixed; app check T272 pending.

---

## Test Coverage

- New, Pass (6 tests): UT-BKT-002.098.M12.T01–T05, UT-BKT-002.099.M12.T01.
- Backtest suite: 226 pass.

---

## Open items

- User check T274 (Grow with P&L in a backtest).
- App check T272 (ISS-BKT-0004: full S&P 500 run no longer freezes).
