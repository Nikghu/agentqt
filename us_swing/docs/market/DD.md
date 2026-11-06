# Design Document — Market Analytics (MKT)

**Document ID:** DD-MKT
**Version:** 0.3.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.5.0: DD-MKT-005.001.D01 added — ATLAS (P5a).
> v0.4.0: DD-MKT-004.001.D01 added — proof on past data (P4).
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

**After code review.** `member_sectors()` returns `SectorMembers(sectors, listed)` so the step can apply the 80% rule to the full list. A look-back close (63–252 days ago) that is missing uses the last close up to 5 days before it, so one missing day does not drop a stock; today's close and the 95% rule still use the real bars. Re-running a day deletes its old rows first, so a stock that lost its rating does not keep a stale row. Rows are built in one pass, not row by row: the first run on 519 stocks takes about 15 s, a daily run about 5 s.

**Floor** (SRD-GUI-034.012): `core/desk_floor.DeskFloorData` serves `sectors.rank` (rank, sector, rel_1m, rel_3m, rel_6m, quadrant), `sectors.rrg` (sector, rs_ratio, rs_momentum, quadrant) and a new product `rs.leaders` (symbol, sector, rs_rating, sector_rank; top 30 by rating; filter by sector) from the latest stored day. Each title carries the data date; `rs.leaders` is listed only once `stock_rs` has rows.

---

## DD-MKT-003.001.D01 — Money Flow, Setups, Readiness Score and Ideas (P3)

**Traces:** SRD-MKT-003.001–.012

**Data in.** `CandleReader.read()` also returns `volumes` (wide frame, like closes). Members, sectors and SPY alignment are as in P2. From `desk.db` the step reads `regime_snapshot.regime`, `sector_daily` (quadrant, rank) and `stock_rs` (rs_rating) for the same days. A day without a regime row or sector rows is not scored.

**Liquidity** (`market/flow.py`): `dollar_vol20 = rolling mean(close * volume, 20)`; a stock-day with `dollar_vol20 < 20_000_000` gets no score.

**Money flow** (`market/flow.py`, pure, wide frames):

```
avg50v      = rolling mean(volume, 50)
acc_day     = close > prev close and volume > avg50v
dist_day    = close < prev close and volume > avg50v
net_ad      = sum(acc_day, 25) - sum(dist_day, 25)
cmf20       = sum(((c - l) - (h - c)) / (h - l) * v, 20) / sum(v, 20)      (h == l → 0)
ud50        = sum(v on up days, 50) / sum(v on down days, 50)
flow_long   = mean( clip(net_ad / 10 + 0.5, 0, 1),
                    clip(cmf20 / 0.4 + 0.5, 0, 1),
                    clip((ud50 - 0.5) / 1.5, 0, 1) )
flow_short  = 1 - flow_long
```

**Setups** (`market/setups.py`, pure; `atr_n` = mean true range over n days, `hi_n` / `lo_n` = highest high / lowest low of the last n days including today):

```
Long
Squeeze     close > sma50, sma50 > sma50.shift(10),
            bb_width20 (= 4 * std20 / sma20) <= 1.1 * its 126-day low, atr10 / atr50 < 0.8
            trigger = hi_20      stop = lo_20
Flat base   close >= 0.9 * hi_252, (hi_25 - lo_25) / hi_25 <= 0.15, close > sma50
            trigger = hi_25      stop = lo_25
Pullback    close > sma50, sma50 > sma50.shift(10), lo_3 <= sma21 * 1.02, close >= sma21
            trigger = hi_3       stop = lo_5
Short
Failed breakout  some day in the last 10 closed above the 25-day high before it (pivot),
                 and today's close is below that pivot and below sma20
                 trigger = lo_5       stop = highest high since that breakout day
Lower highs      close < sma50, sma50 < sma50.shift(10),
                 hi of days 1–10 < hi of days 11–20 < hi of days 21–30 (day 1 = today)
                 trigger = lo_10      stop = hi_10
Breakdown        close < sma50, prev close >= prev sma50, volume >= 1.5 * avg50v
                 trigger = low today  stop = max(sma50, hi_5)
tightness   = 0.5 * clip(1 - atr10 / atr50, 0, 1)
            + 0.5 * clip(1 - |trigger - close| / (2 * atr14), 0, 1)
```

When several setups match on one side, the one with the highest tightness is kept (ties: the order listed above). No match gives setup part 0.

**Score** (`market/score.py`, per stock, day and side):

```
rs_part      long: 0.75 * rating / 99 + 0.25 * (rs line at its 63-day high)
             short: 0.75 * (100 - rating) / 99 + 0.25 * (rs line at its 63-day low)
             rs line = close / SPY close
flow_part    flow_long or flow_short
setup_part   tightness of the kept setup, else 0
sector_part  0.7 * quadrant value + 0.3 * (11 - sector rank) / 10            (short: 0.3 * (rank - 1) / 10)
             long quadrant value: Leading 1, Improving 0.75, Weakening 0.25, Lagging 0
             short quadrant value: Lagging 1, Weakening 0.75, Improving 0.25, Leading 0
regime_part  long: Uptrend 1, Choppy 0.5, Downtrend 0;  short: Downtrend 1, Choppy 0.5, Uptrend 0
raw          = 20 * rs + 20 * flow + 20 * setup + 15 * sector + 15 * regime     (max 90)
score        = max(0, raw * 100 / 90 - penalty), rounded to 1 decimal
penalty      10 when long and close > 1.08 * sma20, or short and close < 0.92 * sma20; else 0
```

**Ideas** (`market/score.py`): per day and side, stocks with `score >= 60` sorted by score (ties: symbol). Watch when the side is against the regime (short in Uptrend, long in Downtrend) or the next earnings date is within 5 trading days after the data day. The first 10 not on Watch are `list` (rank 1–10); every Watch name scoring 60+ is kept as `watch` (no cap). A stock with no setup can still be listed; its trigger is `hi_20` (long) or `lo_20` (short) and its stop `lo_20` / `hi_20`, and its setup reads "No setup".

**Reasons** (up to 5, in this order, only when they hold): "RS rating 94, RS line at a 3-month high" · "6 accumulation and 1 distribution days in 25 sessions" · "Sector Leading, rank 2 of 11" · "Squeeze, 3.1% below the trigger" · "Regime Uptrend" · Watch notes: "Earnings in 3 days", "Against the Uptrend". Extended penalty adds "8.6% above the 20-day average".

**Earnings** (`market/earnings.py`): `next_earnings(symbols, today) -> {symbol: date | None}` from `yfinance.Ticker(s).calendar["Earnings Date"]`, one call per symbol with a 10 s total budget per 30 names; any failure gives `None` and the idea note "earnings not checked". Called once per run, for the latest scored day, on the 30 best-scored stocks per side (before Watch).

**Tables in `desk.db`** (`market/store.py`, `CREATE TABLE IF NOT EXISTS`; a re-run deletes the day's rows first):

```
stock_score(date TEXT, symbol TEXT, side TEXT, score REAL, rs_part REAL, flow_part REAL,
            setup_part REAL, sector_part REAL, regime_part REAL, penalty REAL, setup TEXT,
            trigger REAL, stop REAL, PRIMARY KEY (date, symbol, side))
ideas(date TEXT, side TEXT, symbol TEXT, status TEXT, rank INTEGER, score REAL, sector TEXT,
      setup TEXT, trigger REAL, stop REAL, PRIMARY KEY (date, side, symbol))
idea_reasons(date TEXT, side TEXT, symbol TEXT, seq INTEGER, reason TEXT,
             PRIMARY KEY (date, side, symbol, seq))
```

`stock_score` keeps every liquid stock for both sides (about 1,000 rows a day) so P4 can test score buckets on history.

**Step** (`market/idea_step.py`, `IdeaStep`, name "Ideas"): read members, sectors and bars (with volume) → read regime, sector and RS rows from `desk.db` → compute flow, setups and scores for every day → choose days as in P2 (not stored, or within 7 days of the last stored day; 80% coverage; needs regime, sector and RS rows) → fetch earnings for the latest chosen day → pick ideas and reasons → write → log. `core/desk_steps.STEP_PATHS` adds `"us_swing.market.idea_step:IdeaStep"` after the sector step.

**Floor** (SRD-GUI-034.013): `core/desk_floor.DeskFloorData` serves `ideas.top` from the latest `ideas` day with columns `symbol, side, score, setup, sector, trigger, stop, why` (why = first reason), filters `side` (long, short) and `status` (list, watch; default list when no filter is set), title "Top ideas (date)". The Overview and Ideas tabs already show this product.

**After code review.** Failed breakout's stop is the 10-day high (it always holds the breakout day). Watch notes come first in the reasons so they are never cut; the RS reason shows when the rating is 70+ (short: 30 or less) or the RS line is at its 3-month extreme; the sector reason reads "Financials sector leading, rank 3"; a setup within 0.05% of its trigger reads "at the trigger". A 50-day volume window with a gap gives no money flow, so the stock is not scored that day. Earnings: up to 6 Yahoo calls at once, 10 s per 30 names; a name not answered in time (or with no date on Yahoo) is "not checked". Trading days for earnings ignore market holidays. Only the 30 best per side are checked, so in a busy earnings week a name ranked 31+ can be listed without a check. Re-running a day clears it first even when it now has no rows. Speed: rolling windows use one numpy helper (`flow.roll`, same results as pandas) and only the last 460 rows before the first day to write; real data: first run about 19 s, daily run about 7 s including the Yahoo check.

**Limits in P3.** No news, so no gap-risk penalty yet (P5c). Earnings are checked only for the latest day, so past days in `ideas` never carry the earnings Watch. Survivorship: the S&P 500 list is today's.

## DD-MKT-004.001.D01 — Proof on Past Data (P4)

**Traces:** SRD-MKT-004.001–.009, SRD-DSK-001.022, SRD-GUI-034.014

**Data in** (`market/proof_data.py`). The Backtest Data store keeps one file per stock, `~/.usswing/backtest/1d/<SYM>.parquet`, with columns `ts, open, high, low, close, volume` (`ts` is the trading day). MKT reads these files with `pandas.read_parquet` and never imports `us_swing.backtest`: the file layout is the contract. Members and sectors come from `member_sectors(available, universe)` as in P2 (today's S&P 500 list). All frames are aligned to SPY's days; a stock-day missing a bar stays NaN. `history_years = (last SPY day − first SPY day) / 365.25`.

**Replay** (`market/proof.py`), all in memory, nothing written to the daily desk tables:

```
regime     = regime_series(spy.close)                        P1
lines      = sector_lines(closes, sector_of); table = sector_table(lines, spy)    P2
ratings    = rs_table(rs_scores(closes), sector_of).rs_rating                     P2
inputs     = MarketInputs(bars, spy, ratings, sector_of, quadrant, rank, regime)  P3
days       = SPY days with a regime, quadrants and ratings, and data for >= 80% of members
for each chunk of 250 days:  frames += score_frame(inputs, chunk)   (trims its own history)
for each day and side:       status = pick_ideas(day_rows, side, day, earnings=None)
                             -> list / watch ; every other scored stock = none
```

Every rule is a rolling window or a shift back in time, so the value on day d uses only bars up to d. A test changes later bars and checks that earlier scores stay the same. Earnings are not known for past days, so `earnings=None` (no earnings Watch); the regime Watch rule still applies.

**Forward returns** for stock-day (s, d) and horizon h in (5, 10, 20), with t = position of d in SPY's days:

```
entry   = open[s, t+1]
exit    = close[s, t+h]
r       = exit / entry - 1               spy_r = spy.close[t+h] / spy.open[t+1] - 1
long:   ret = r          vs_spy = r - spy_r
short:  ret = -r         vs_spy = spy_r - r
```

Missing entry or exit means no sample for that horizon. Days in the last h sessions have no h-day sample.

**Groups.** Band edges: `[0,40) [40,50) [50,60) [60,70) [70,80) [80,100]`. Setup = the stored setup name, or "No setup". Status = list, watch or none. Per (side, kind, group, horizon): `n` stock-days, `days` distinct dates, `win_rate = mean(ret > 0)`, `avg_ret = mean(ret)`, `avg_vs_spy = mean(vs_spy)`.

**Pass rule** per side at h = 10. `top` = score ≥ 70, `low` = score < 40. If either has fewer than 100 samples, the result is "not enough data". Otherwise it is a pass when `top.avg_vs_spy > 0` and `top.avg_vs_spy > low.avg_vs_spy`, else a fail.

**Tables** (`market/store.py`):

```
proof_run(run_id INTEGER PRIMARY KEY, created TEXT, data_first TEXT, data_last TEXT,
          scored_first TEXT, scored_last TEXT, years REAL, stocks INTEGER, days INTEGER,
          long_result TEXT, short_result TEXT, seconds REAL)
proof_stats(run_id INTEGER, side TEXT, kind TEXT, grp TEXT, horizon INTEGER, n INTEGER,
            days INTEGER, win_rate REAL, avg_ret REAL, avg_vs_spy REAL,
            PRIMARY KEY (run_id, side, kind, grp, horizon))
```

`kind` is band, setup or status. A run's rows are written in one transaction after the replay finishes.

**Report** (`report_text(run, stats)`), plain text. A header has the data range, years, stocks and scored days. Then for each side three tables (bands, setups, status), each row showing `group | stock-days | win 10d | vs SPY 5d / 10d / 20d`, then `Long: pass` / `Short: fail` with the two 10-day numbers. When `years < 5` it ends with: "Daily history covers N years from <date>. For a fuller test, set Start date in Settings → Backtest Data to 2020-01-01 and download (this also downloads 3-minute bars)."

**CLI** (SRD-DSK-001.022). `desk proof` imports `PROOF_PATH = "us_swing.market.proof:run_proof"` from `core/desk_steps.py` by import path, as it does for steps, so `desk` never imports `market` directly. `run_proof(home, root) -> str | None` returns the report, or None when there is no data. Exit code 0 when a report is printed, 1 when there is no data. The proof can run while the desk is running; it only adds rows to the two proof tables.

**Floor** (SRD-GUI-034.014). `DeskFloorData` serves `proof.bands` from the latest `proof_run`. Columns are `group, n, win_10d, vs_spy_5d, vs_spy_10d, vs_spy_20d`, shown as percentages. Filters are `side` (long, short; default long) and `kind` (band, setup, status; default band). The title is "Score proof (<scored_first> to <scored_last>) · Long <result> · Short <result>", plus "· only N years of data" when under 5 years. The product is listed in the catalog only when `proof_run` has a row.

**Speed.** P3 scores 341 days in about 19 s. 6 years is about 1,250 scored days, so roughly 70 s for scoring plus reading about 500 files. Chunks of 250 days keep memory near the P3 first run.

**Limits.** Survivorship (today's member list). No earnings Watch. Overlapping samples. No costs, slippage or stop exits. No tuning (T117 stays open until the proof is read).

**After code review.** Group stats and the pass rule count only stock-days where both the return and the return against SPY exist, so `n` and the averages use the same rows; the Floor shows "-" for a missing average. The report says the S&P 500 list is today's. Report text is plain ASCII (bands `40-50`, `Settings > Backtest Data`) because the Windows console cannot print some symbols. Real run: candles 2024-01-02 to 2026-11-04, 503 stocks, 443 scored days, 21 s. On the same candles the replay equals the desk's `stock_score` exactly; against the Backtest Data candles 89.9–95.4% of scores are within 1 point on 3 days, the rest from price differences between the two candle sources.

## DD-MKT-005.001.D01 — ATLAS, Market Regime Expert (P5a)

**Traces:** SRD-MKT-005.001–.005

**Files.** `market/atlas.py` (class `Atlas`, the `Employee` from `core/desk_agents.py`), `market/employees/atlas/soul.md`, `market/employees/atlas/job.yaml`, plus the `atlas_view` table in `market/store.py`. ATLAS uses only `core` types; it does not import `desk`.

**Facts** (`Atlas.facts(home)`), plain text from `desk.db`:

```
Data day: 2026-11-04 (fresh)
Regime (rules) last 20 days: date regime volatility fear vix
Breadth today: % above 20/50/200-day, new highs, new lows, advancing, declining
Sectors today: rank, sector, quadrant, rel_1m (and rank 5 days ago)
Ideas today: long N (watch M), short N (watch M)
Score proof: data range, long result, short result, 70+ vs SPY at 10 days per side
```

`fresh` is true when the latest `regime_snapshot` day equals the latest SPY day in `candles.db`; otherwise `why_stale` names both days.

**Answer schema** (pydantic, `extra="forbid"`):

```
class AtlasView:
    regime: Literal["Uptrend", "Choppy", "Downtrend"]
    confidence: float  (0..1)
    reasons: list[str] (1..3 items, each 5..140 chars)
    brief: str (20..400 chars)
```

**Act.** `view = ctx.ask(facts.text, AtlasView)`. When None, nothing is stored and there is no feed item. Otherwise `agrees = view.regime == rule regime`, and `atlas_view(date PK, regime, confidence, reasons (JSON list), brief, rule_regime, agrees)` is written (insert or replace). It returns `FeedItem("ATLAS", "info", brief + note, day)`, where note = `" I read the market as <regime>; the rules say <rule regime>."` when it disagrees.

**soul.md** (system prompt). ATLAS is the desk's market regime expert. It weighs trend, breadth, volatility, fear and sector rotation. It is careful and plain-spoken, says when signals conflict, never gives trade orders, and never makes up numbers that are not in the facts.

**job.yaml.** trigger `after_run`; primary `openrouter` with a cheap model; backup `claude` / `claude-haiku-5-5`; `calls_per_day: 3`; `monthly_cost_usd: 3.0`. KPIs: agreement rate with the rule regime, and the share of valid answers.
