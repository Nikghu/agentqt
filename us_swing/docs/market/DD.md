# Design Document — Market Analytics (MKT)

**Document ID:** DD-MKT
**Version:** 0.3.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.3.0: DD-MKT-002.001.D01 added — sector strength, rotation and stock RS (P2).
> v0.2.0: DD-MKT-001.001.D01 added — regime, breadth and fear (P1).
> v0.1.0: Empty. Rows are added per phase, starting with the first FO of this tool.

---
> Architecture, `desk.db` contract and phase plan live in `docs/desk/DD.md` §0.

---

## DD-MKT-001.001.D01 — Market Regime, Breadth and Fear (P1)

**Traces:** SRD-MKT-001.001–.012

**Data in.** `candles.db` opened with `mode=ro`; `price_1d(symbol, datetime, open, high, low, close, volume)`. Members come from `core/backtest_bridge.load_universe()` (saved S&P 500 list); a member matches a candle symbol by its `ibkr_symbol` or `symbol`. SPY is read the same way.

**Rules** (pure functions on pandas Series/DataFrames, `market/regime.py`):

```
sma(n)         = rolling mean of close over n days
regime         = Uptrend   if close > sma50 and close > sma200 and sma50 > sma50.shift(10)
                 Downtrend if close < sma50 and close < sma200 and sma50 < sma50.shift(10)
                 else Choppy
vol20          = std(log returns, 20) * sqrt(252)
vol_pct        = percent rank of vol20 within the past 252 values
volatility     = Calm if vol_pct < 30, High if vol_pct > 70, else Normal
breadth        = pct_above_20/50/200 (members with >= n bars), new_highs (today's high is the highest
                 high of the past 252 days incl. today), new_lows (today's low is the lowest low), advancers (close >
                 prev close), decliners (close < prev close)
gaps           = a member needs 95% of the days in each window (one missing day must not
                 drop it from the 200-day or 52-week measures)
fear points    = VIX >= 30: 2 | VIX >= 20: 1 | else 0
               + 2 if VIX > VIX3M (fear curve inverted)
               + 1 if volatility == High
               + 1 if pct_above_50 < 40
fear           = Calm 0-1, Nervous 2-3, Fearful >= 4
```

**Tables in `desk.db`** (created by `market/store.py`, `CREATE TABLE IF NOT EXISTS`, `INSERT OR REPLACE`):

```
regime_snapshot(date TEXT PRIMARY KEY, regime, volatility, vol20 REAL, vol_pct REAL,
                spy_close REAL, sma50 REAL, sma200 REAL, vix REAL, vix3m REAL,
                fear, fear_score INTEGER, note TEXT, created_at TEXT)
breadth_daily(date TEXT PRIMARY KEY, members INTEGER, pct_above_20 REAL, pct_above_50 REAL,
              pct_above_200 REAL, new_highs INTEGER, new_lows INTEGER, advancers INTEGER,
              decliners INTEGER)
vix_daily(date TEXT PRIMARY KEY, vix REAL, vix3m REAL)
```

**Step** (`market/step.py`, `RegimeStep`, name "Market regime"): open stores → fetch missing VIX days (from the last stored day, or 2023-01-01) → read bars → compute every candle date after the last stored date that has 210 SPY bars → skip days below 80% member coverage → write rows → log. The step opens `desk.db` itself from `StepContext.home`; it runs inside the desk process, so the desk stays the only writer.

**After code review.** Members are aligned to SPY's trading days before breadth, so a stray date row cannot spoil the windows. Every run recomputes the last 7 days (and any earlier day not stored), so a day saved from a partial candle download or before Yahoo published VIX is corrected on the next run; VIX is re-fetched from 7 days before the last stored day. Coverage counts against the full S&P 500 list. A missing `candles.db` or missing SPY logs a warning and the step adds nothing instead of failing the desk run.

**Registration.** `core/desk_steps.py` holds `STEP_PATHS = ("us_swing.market.step:RegimeStep",)` and `load_steps()` (importlib). The desk CLI passes `load_steps()` to `DeskProcess` (SRD-DSK-001.021), so `desk` never imports `market`.

**Floor.** `core/desk_floor.py` `DeskFloorData` implements `FloorData`: products `regime.today` and `breadth.daily` come from `desk.db` (read-only, `sample=False`); other products come from the sample provider (SRD-GUI-034.011).

**Limit in P1.** The desk does not download candles yet. With the app closed, the data date is the last day the app saved; the note shows it as stale.

---

## DD-MKT-002.001.D01 — Sector Strength and Rotation (P2)

**Traces:** SRD-MKT-002.001–.010

**Members and sectors.** `market/candles.member_sectors()` returns `{candle symbol: sector}` from the saved list (`core/backtest_bridge.load_universe()`, field `sector`), matching `symbol` or `ibkr_symbol` like `member_symbols()`. All member frames are reindexed to SPY's dates, as in P1.

**Rules** (pure, `market/sectors.py` and `market/rs.py`):

```
ret            = close / close.shift(1) - 1            (NaN when either day is missing)
sector_ret     = mean of ret over the sector's members (skipna)
line           = 100 * cumprod(1 + sector_ret.fillna(0))
rel_n          = line.pct_change(n) - spy.pct_change(n)   n = 21, 63, 126
rank           = rank of mean(rel_21, rel_63, rel_126), 1 = best, among sectors that day
rs             = line / spy
rs_ratio       = 100 * rs / rs.rolling(50).mean()
rs_momentum    = 100 * rs_ratio / rs_ratio.shift(10)
quadrant       = Leading    ratio >= 100 and momentum >= 100
                 Weakening  ratio >= 100 and momentum <  100
                 Lagging    ratio <  100 and momentum <  100
                 Improving  ratio <  100 and momentum >= 100
score          = 0.4 * r63 + 0.2 * r126 + 0.2 * r189 + 0.2 * r252,  r_n = close / close.shift(n) - 1
                 (needs at least 95% of the 252 days present)
rs_rating      = ceil(percentile rank of score among scored members that day * 99), 1..99
sector_rank    = rank of score inside the sector that day, 1 = best; sector_size = scored members
```

**Tables in `desk.db`** (`market/store.py`, `CREATE TABLE IF NOT EXISTS`, `INSERT OR REPLACE`):

```
sector_daily(date TEXT, sector TEXT, line REAL, rel_1m REAL, rel_3m REAL, rel_6m REAL,
             rank INTEGER, rs_ratio REAL, rs_momentum REAL, quadrant TEXT, members INTEGER,
             PRIMARY KEY (date, sector))
stock_rs(date TEXT, symbol TEXT, sector TEXT, score REAL, rs_rating INTEGER,
         sector_rank INTEGER, sector_size INTEGER, PRIMARY KEY (date, symbol))
```

**Step** (`market/sector_step.py`, `SectorStep`, name "Sectors"): read members and sectors → bars aligned to SPY → compute lines, ranks, ratios, quadrants and stock ratings → choose days to write the same way as the P1 step (not stored yet, or within 7 days of the last stored day; 80% coverage against the full list; first ready day is when rs_ratio, rs_momentum, rel_6m and ratings exist) → write rows → log. `core/desk_steps.STEP_PATHS` becomes `("us_swing.market.step:RegimeStep", "us_swing.market.sector_step:SectorStep")`.

**Floor** (SRD-GUI-034.012): `core/desk_floor.DeskFloorData` serves `sectors.rank` (rank, sector, rel_1m, rel_3m, rel_6m, quadrant), `sectors.rrg` (sector, rs_ratio, rs_momentum, quadrant) and a new product `rs.leaders` (symbol, sector, rs_rating, sector_rank; top 30 by rating; filter by sector) from the latest stored day.
