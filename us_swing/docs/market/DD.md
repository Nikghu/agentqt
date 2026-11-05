# Design Document — Market Analytics (MKT)

**Document ID:** DD-MKT
**Version:** 0.2.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

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
breadth        = pct_above_20/50/200 (members with >= n bars), new_highs (close >= max high of
                 past 252 days incl. today), new_lows (close <= min low ...), advancers (close >
                 prev close), decliners (close < prev close)
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

**Registration.** `core/desk_steps.py` holds `STEP_PATHS = ("us_swing.market.step:RegimeStep",)` and `load_steps()` (importlib). The desk CLI passes `load_steps()` to `DeskProcess` (SRD-DSK-001.021), so `desk` never imports `market`.

**Floor.** `core/desk_floor.py` `DeskFloorData` implements `FloorData`: products `regime.today` and `breadth.daily` come from `desk.db` (read-only, `sample=False`); other products come from the sample provider (SRD-GUI-034.011).

**Limit in P1.** The desk does not download candles yet. With the app closed, the data date is the last day the app saved; the note shows it as stale.
