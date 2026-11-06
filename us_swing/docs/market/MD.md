# Module Decomposition — Market Analytics (MKT)

**Document ID:** MD-MKT
**Version:** 0.3.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.4.0: MD-MKT-003.*.M01–M07 added — money flow, setups, readiness score and ideas (P3).
> v0.3.0: MD-MKT-002.*.M01–M05 added — sector strength, rotation and stock RS (P2).
> v0.2.0: MD-MKT-001.*.M01–M05 added — regime, breadth and fear (P1).
> v0.1.0: Empty. Rows are added per phase, starting with the first FO of this tool.

---

## FO-MKT-001: Market Regime, Breadth and Fear

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-001.001.M01 | SRD-MKT-001.001 | `us_swing/src/us_swing/market/candles.py` | Read-only daily bars for SPY and S&P 500 members | `CandleReader`, `member_symbols()` | `sqlite3`, `pandas`, `core.backtest_bridge` | No |
| MD-MKT-001.002.M02 | SRD-MKT-001.002 | `us_swing/src/us_swing/market/regime.py` | Pure rules: regime, volatility, breadth, fear | `regime_series()`, `volatility_series()`, `breadth_frame()`, `fear_reading()` | `pandas`, `numpy` | No |
| MD-MKT-001.005.M03 | SRD-MKT-001.005 | `us_swing/src/us_swing/market/vix.py` | Fetch daily VIX and VIX3M from Yahoo Finance | `fetch_vix()` | `yfinance` | No |
| MD-MKT-001.007.M04 | SRD-MKT-001.007 | `us_swing/src/us_swing/market/store.py` | Market tables in `desk.db` | `MarketStore` | `sqlite3` | No |
| MD-MKT-001.011.M05 | SRD-MKT-001.011 | `us_swing/src/us_swing/market/step.py` | Desk step: incremental compute and save | `RegimeStep` | M01–M04, `core.desk_contract` | No |

SRD coverage: .001 by M01; .002, .003, .004, .006 by M02; .005 by M03; .007 by M04; .008, .009, .010, .011, .012 by M05.

## FO-MKT-002: Sector Strength and Rotation

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-002.001.M01 | SRD-MKT-002.001 | `us_swing/src/us_swing/market/candles.py` | Sector of each member (added to the P1 reader) | `member_sectors()` | `core.backtest_bridge` | No |
| MD-MKT-002.002.M02 | SRD-MKT-002.002 | `us_swing/src/us_swing/market/sectors.py` | Pure rules: sector lines, relative moves, rank, RS-ratio, RS-momentum, quadrant | `sector_lines()`, `sector_table()`, `quadrant()` | `pandas`, `numpy` | No |
| MD-MKT-002.006.M03 | SRD-MKT-002.006 | `us_swing/src/us_swing/market/rs.py` | Pure rules: stock RS score, rating and sector rank | `rs_scores()`, `rs_table()` | `pandas`, `numpy` | No |
| MD-MKT-002.008.M04 | SRD-MKT-002.008 | `us_swing/src/us_swing/market/store.py` | `sector_daily` and `stock_rs` tables (added to the P1 store) | `SectorRow`, `StockRsRow`, `MarketStore.write_sector_days()`, `stored_sector_dates()` | `sqlite3` | No |
| MD-MKT-002.009.M05 | SRD-MKT-002.009 | `us_swing/src/us_swing/market/sector_step.py` | Desk step "Sectors" | `SectorStep` | M01–M04, `core.desk_contract` | No |

SRD coverage: .001 by M01; .002, .003, .004, .005 by M02; .006, .007 by M03; .008 by M04; .009, .010 by M05.

## FO-MKT-003: Money Flow, Setups, Readiness Score and Ideas

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-003.001.M01 | SRD-MKT-003.001 | `us_swing/src/us_swing/market/candles.py` | Volume in the daily bars (added to the P1 reader) | `DailyBars.volumes` | `pandas` | No |
| MD-MKT-003.002.M02 | SRD-MKT-003.002 | `us_swing/src/us_swing/market/flow.py` | Pure rules: liquidity and money flow | `dollar_volume()`, `money_flow()`, `roll()` | `pandas`, `numpy` | No |
| MD-MKT-003.003.M03 | SRD-MKT-003.003 | `us_swing/src/us_swing/market/setups.py` | Pure rules: long and short setups with trigger, stop and tightness | `long_setups()`, `short_setups()`, `long_candidates()`, `short_candidates()` | `pandas`, `numpy` | No |
| MD-MKT-003.005.M04 | SRD-MKT-003.005 | `us_swing/src/us_swing/market/score.py` | Score parts, penalty, ideas, Watch and reasons | `score_frame()`, `readiness_score()`, `pick_ideas()` | M02, M03 | No |
| MD-MKT-003.009.M05 | SRD-MKT-003.009 | `us_swing/src/us_swing/market/earnings.py` | Next earnings dates from Yahoo Finance | `next_earnings()` | `yfinance` | No |
| MD-MKT-003.010.M06 | SRD-MKT-003.010 | `us_swing/src/us_swing/market/store.py` | `stock_score`, `ideas` and `idea_reasons` tables (added to the P1 store) | `ScoreRow`, `IdeaRow`, `ReasonRow`, `MarketStore.write_idea_days()`, `stored_idea_dates()` | `sqlite3` | No |
| MD-MKT-003.011.M07 | SRD-MKT-003.011 | `us_swing/src/us_swing/market/idea_step.py` | Desk step "Ideas" | `IdeaStep` | M01–M06, `core.desk_contract` | No |

SRD coverage: .001 by M01 and M02; .002 by M02; .003, .004 by M03; .005, .006, .007, .008 by M04; .009 by M05; .010 by M06; .011, .012 by M07.
