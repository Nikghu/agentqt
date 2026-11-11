# Design Document — Market Analytics (MKT)

**Document ID:** DD-MKT
**Version:** 0.6.0
**Status:** Draft
**Last Updated:** 2026-11-11
**Project:** US Swing Trading System

> v0.17.0: DD-MKT-015.001.D01 added — setup tuning research (Autonomous desk step F (2026-11-11)).
> v0.16.0: DD-MKT-014.001.D01 added — lead research tickets (Autonomous desk step E (2026-11-11)).
> v0.15.0: DD-MKT-013.001.D01 added — intraday watchers and check-in notes (Autonomous desk step D (2026-11-11)).
> v0.14.0: DD-MKT-012.001.D01 added — learning from pick results (Autonomous desk step C (2026-11-11)).
> v0.13.0: DD-MKT-001.013.D01 added — candle check with a Yahoo desk-only copy, morning brief (Autonomous desk step A, 2026-11-10).
> v0.12.0: DD-MKT-011.001.D01 added — ask the desk for new data (P10).
> v0.11.0: DD-MKT-010.001.D01 added — lead chat (P9).
> v0.10.0: DD-MKT-009.001.D01 added — pick results (P8).
> v0.9.0: DD-MKT-008.001.D01 added — link to Execution (P7).
> v0.8.0: DD-MKT-007.001.D01 added — AI report pages (P5d).
> v0.7.0: DD-MKT-006.001.D01 added — news, economic calendar and event risk (P5c).
> v0.6.0: DD-MKT-005.006.D01 added — sector/flow view, setup review, risk check and lead brief (P5b).
> v0.5.0: DD-MKT-005.001.D01 added — regime view skill (P5a).
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

## DD-MKT-005.001.D01 — Regime View Skill (P5a)

**Traces:** SRD-MKT-005.001–.005

**Files.** `market/regime_view.py` (class `RegimeViewSkill`, key `regime_view`, the `Skill` from `core/desk_agents.py`), the default employee `market/employees/emp-001/` (`soul.md`, `job.yaml`; generic name "Expert 1", level expert), plus the `regime_view` table in `market/store.py`. The skill uses only `core` types, does not import `desk`, and never knows which employee runs it.

**Facts** (`RegimeViewSkill.facts(home)`), plain text from `desk.db`:

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
class RegimeView:
    regime: Literal["Uptrend", "Choppy", "Downtrend"]
    confidence: float  (0..1)
    reasons: list[str] (1..3 items, each 5..140 chars)
    brief: str (20..400 chars)
```

**Act.** `view = ctx.ask(facts.text, RegimeView)`. When None, nothing is stored and there is no feed item. Otherwise `agrees = view.regime == rule regime`, and `regime_view(date PK, regime, confidence, reasons (JSON list), brief, rule_regime, agrees)` is written (insert or replace). It returns `FeedItem("info", brief + note, day)` (the desk adds the employee's id and name), where note = `" I read the market as <regime>; the rules say <rule regime>."` when it disagrees.

**soul.md** (system prompt). The default soul uses `{name}` and `{title}` from `job.yaml`; it describes the regime view work. It weighs trend, breadth, volatility, fear and sector rotation. It is careful and plain-spoken, says when signals conflict, never gives trade orders, and never makes up numbers that are not in the facts.

**job.yaml.** id `emp-001`, name `Expert 1`, title `Expert`, level `expert`, skill `regime_view`; trigger `after_run`; primary `claude` / `default`, backup `openrouter` / `default`; `calls_per_day: 3`; `monthly_cost_usd: 3.0`. KPIs: agreement rate with the rule regime, and the share of valid answers.

**After the real run.** The first real answers broke the 140-character reason rule, which was checked in code but not shown in the JSON schema. The limit is now in the schema (`StringConstraints`), and `soul.md` says so too. Real run 2026-11-06 (Claude Code CLI, claude-haiku-5-5): valid on the 4th try, about 3,400 tokens, 7 s, cost 0; view Choppy 0.55, agreeing with the rule regime.

## DD-MKT-005.006.D01 — Sector/Flow View, Setup Review, Risk Check and Lead Brief (P5b)

**Traces:** SRD-MKT-005.006–.018

**Files.** One skill per file, each a `Skill` from `core/desk_agents.py` with `key`, `needs` and `answer`. None imports `desk`, and none knows which employee runs it:

| File | Class | key | needs |
|---|---|---|---|
| `market/sector_view.py` | `SectorViewSkill` | `sector_flow_view` | — |
| `market/setup_review.py` | `SetupReviewSkill` | `setup_review` | — |
| `market/risk_limits.py` | `code_vetoes()` + constants | — | — |
| `market/risk_check.py` | `RiskCheckSkill` | `risk_check` | `regime_view`, `sector_flow_view`, `setup_review` |
| `market/lead_brief.py` | `LeadBriefSkill` | `lead_brief` | `regime_view`, `sector_flow_view`, `setup_review`, `risk_check` |

`RegimeViewSkill` gets `needs = ()` and `answer = RegimeView`. Tables are added to `market/store.py`; every write for a data day is a delete-then-insert in one transaction, so a re-run replaces it.

```
sector_view(date PK, favour JSON, avoid JSON, rotation, brief)
setup_review(date, side, symbol, grade, note, PRIMARY KEY (date, side, symbol))
risk_check(date, side, symbol, verdict ('pass'|'veto'), by ('code'|'ai'), reason,
           PRIMARY KEY (date, side, symbol))
lead_picks(date, side, symbol, rank, reason, PRIMARY KEY (date, side, symbol))
```

The view tables have no employee column. A skill gets only the desk folder and `ask` (SRD-DSK-002.005), so it never knows who runs it; `activity` and `briefs` already record the employee for every answer.

**Freshness.** All four use the P5a check with their own source day: the sector view uses the latest `sector_daily` day, and the others use the latest `ideas` day. Each must equal the latest SPY candle day. "Listed ideas" are `ideas` rows with `status = 'list'` for that day.

**Sector/flow view.** Facts: rule regime; for the last 5 sector days, rank, sector, quadrant, rel_1m and rel_3m; and for today, each sector's average `flow_part` per side over its scored stocks (`stock_score` joined with `stock_rs.sector`). Answer:

```
class SectorView:   favour: list[str] (1..3)   avoid: list[str] (0..3)
                    rotation: str (10..200)    brief: str (20..400)
```

`act` asks with a subclass whose list items are `Literal[<that day's sector names>]`, so the JSON schema lists the allowed names. A sector in both lists fails the check (model validator). It writes `sector_view` and returns `FeedItem("info", brief, day)`.

**Setup review.** Facts: rule regime, then per listed idea (at most 10 per side, by rank) side, symbol, score, the five parts, penalty, setup, trigger, stop and its reasons. Answer:

```
class SetupGrade:   side: Literal["long","short"]  symbol: str  grade: Literal["A","B","C"]
                    note: str (5..120)
class SetupReview:  grades: list[SetupGrade] (1..20)
```

Grades for an idea not in the facts, or a second grade for the same idea, are dropped with one log line: `[AI Desk] Setup review named 2 stock(s) not in today's ideas or twice`. It writes `setup_review` and returns one short feed item, `Setup review: 12 idea(s) graded - A 4, B 5, C 3`. That brief also marks the day done (P5a rule), so the employee is not asked again on a second run.

**Hard risk limits** (`market/risk_limits.py`). These are plain constants in code. No file an agent reads or writes holds them, and no prompt can change them:

```
MIN_TRIGGER_USD = 5.0          STOP_MIN_PCT = 1.0         STOP_MAX_PCT = 10.0
MAX_PER_SECTOR_SIDE = 3

def code_vetoes(ideas, rule_regime) -> dict[(side, symbol), reason]:
    long  and regime == "Downtrend"           -> "Long idea while the market is in a Downtrend"
    short and regime == "Uptrend"             -> "Short idea while the market is in an Uptrend"
    stop_pct = abs(trigger - stop) / trigger * 100
    stop_pct < 1 or > 10                      -> "Stop is 0.6% from the trigger (allowed 1% to 10%)"
    trigger < 5                               -> "Trigger is below $5"
    per (side, sector), by rank: 4th and later -> "Fourth idea in Technology on the long side"
```

The sector count counts only ideas not already vetoed by an earlier rule, so one bad idea does not push out a good one. Ideas missing a trigger or stop are vetoed: "No trigger or stop".

**Risk check.** `act`:

```
vetoes = code_vetoes(listed ideas, rule regime)
write risk_check: code vetoes as veto/code; all others as pass/code ("Within the hard limits")
passed = listed ideas not vetoed
if passed:
    view = ctx.ask(facts + passed list, RiskVetoes)     # facts: regime, sector and setup views
    for v in view.vetoes if view else []:
        if (v.side, v.symbol) in passed: update row to veto/ai with v.reason
        else: count as dropped (logged)
return [FeedItem("info", "Risk check: 3 of 14 ideas vetoed (2 by the hard limits, 1 by review)", day)]
```

```
class RiskVeto:    side, symbol, reason: str (5..120)
class RiskVetoes:  vetoes: list[RiskVeto] (0..20)
```

The code rows are written before the model is asked. A failed call, a used-up budget or a refusal still leaves the code vetoes in place. In that case no brief is posted, so the day stays open and a later run tries the review again. When every listed idea is already vetoed by code, the model is not asked. An AI answer can only turn a `pass` into a `veto`; a `veto/code` row is never touched. The facts list each missing view as `Sector view: not available today`.

**Lead brief.** Facts: the regime view, sector view, setup grades and risk rows of the day (each missing view noted), and the passed ideas with score, setup, trigger, stop, grade and reasons. Passed means not vetoed in `risk_check`, and `code_vetoes` is always applied again here. So with no risk employee at all, the lead still never sees an idea that breaks a hard limit. Answer:

```
class LeadPick:    side, symbol, reason: str (5..120)
class LeadBrief:   picks: list[LeadPick] (0..10)     evening: str (40..1200)
```

`act` keeps at most 5 picks per side, in the given order, and drops picks that are not in the passed list (logged). It writes `lead_picks` (rank = order) and returns `FeedItem("evening", evening, day)`. The evening brief is the model's own text; the picks are not added by code, so the soul tells the lead to name each pick and why.

**Default employees** (`market/employees/`), all `trigger: after_run`, `calls_per_day: 3`, `monthly_cost_usd: 3.0`, primary `claude/default`, backup `openrouter/default`:

| Folder | name | title | level | reports_to | skill |
|---|---|---|---|---|---|
| `emp-002` | Expert 2 | Expert | expert | emp-005 | sector_flow_view |
| `emp-003` | Expert 3 | Expert | expert | emp-005 | setup_review |
| `emp-004` | Expert 4 | Expert | expert | emp-005 | risk_check |
| `emp-005` | Lead 1 | Lead | lead | null | lead_brief |

`reports_to` is data only and does not decide the run order. The shipped `emp-001` stays as it is; the Master user may set its `reports_to` to `emp-005`. Each `soul.md` uses `{name}` and `{title}` and covers its work: it never gives trade orders, never makes up numbers that are not in the facts, and keeps the length limits that are also in the schema.

**Skill list** (`core/desk_steps.py`, cross-tool note in DSK):

```
SKILL_PATHS = {
    "regime_view":      "us_swing.market.regime_view:RegimeViewSkill",
    "sector_flow_view": "us_swing.market.sector_view:SectorViewSkill",
    "setup_review":     "us_swing.market.setup_review:SetupReviewSkill",
    "risk_check":       "us_swing.market.risk_check:RiskCheckSkill",
    "lead_brief":       "us_swing.market.lead_brief:LeadBriefSkill",
}
```

**After code review and the real run.**
- Code review changes: when a second wake of the risk check gets no valid answer, it keeps the AI vetoes already stored for that day.
- Real run on 2026-11-06, on a copy of the desk folder with data day 2026-11-04 (Claude Code CLI, claude-haiku-5-5): all four employees answered validly on the first try, lead last. That was about 19,000 tokens in about 34 s, cost 0.
- Results: sector view favoured Health Care and Consumer Staples. Setup grades were A 3, B 13, C 4. The risk check vetoed 15 of 20 ideas (14 by the hard limits, 1 by review), and the lead picked 4 longs.
- All 14 code vetoes were "stop over 10% from the trigger". 12 were shorts, with stops 10–68% away, so the P3 short setups give very wide stops (see T117).

**Regime change event** (cross-tool, for SRD-DSK-003.005). After writing its rows, the regime step (`market/step.py`, `RegimeStep`) calls `core.desk_events.post_event(home, "regime_change", latest_day, now)` when the latest day's regime differs from the day before. It is posted once per day.

## DD-MKT-006.001.D01 — News, Economic Calendar and Event Risk (P5c)

**Traces:** SRD-MKT-006.001–.012; reopened SRD-MKT-003.005, SRD-MKT-005.012, SRD-MKT-005.014; GUI SRD-GUI-034.018–.021

**Files.**

| File | What |
|---|---|
| `core/econ_calendar.py` | Yearly economic calendar as plain data, plus `events_between()` and `next_trading_day()`; in `core` because the Floor (`core/desk_floor.py`) and `market` both read it |
| `market/news.py` | Headline fetch: `fetch_symbol()`, `fetch_market()`, `NEWS_FEEDS`; the HTTP getter is injectable |
| `market/news_step.py` | Desk step "News" (`NewsStep`), after "Ideas" |
| `market/news_review.py` | `NewsReviewSkill` (key `news_review`, needs nothing), `news_points()` |
| `market/store.py` | `news_items`, `news_tags` tables |
| `market/employees/emp-006/` | Default employee "Expert 5" (level expert) |

**Sources** (checked 2026-11-06). The yfinance `Ticker.news` call fails with "Yahoo Finance is currently down", while Yahoo's per-symbol RSS works, so stock headlines come from RSS:

```
stock:  https://feeds.finance.yahoo.com/rss/2.0/headline?s=<SYM>&region=US&lang=en-US
        (one call per stock; the multi-symbol form mixes stocks and caps at 20 items)
market: CNBC top news   https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114
        CNBC economy    https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258
        Yahoo SPY       the stock URL with s=SPY
```

Each feed is fetched with `httpx` (10 s time limit, user agent `USSwing/1.0`) and parsed with `feedparser` from the text, so a slow feed never blocks the run. A dot in a symbol (`BRK.B`) becomes a dash for Yahoo.

**Tables** (`market/store.py`):

```
news_items(id INTEGER PK, date, symbol, source, published, title, link, fetched,
           UNIQUE(symbol, link), UNIQUE(symbol, title))
           date = ideas data day it was fetched for; symbol '' = market; published UTC ISO
news_tags(date, side, symbol, tone, reason, points, final_score, PRIMARY KEY (date, side, symbol))
           tone 'positive'|'neutral'|'negative'|'none' ('none' = no answer yet)
```

**News step** (`NewsStep`, `name = "News"`):

```
day = latest ideas day; no ideas -> log and return
for each listed idea of day (best 10 per side, as setup review):
    items = fetch_symbol(sym): published within 3 days of now, newest first, at most 10
for market: fetch_market(): published within 24 hours, newest first, at most 30 in total
INSERT OR IGNORE (date=day, ...)          # the unique keys stop repeats
DELETE FROM news_items WHERE published < now - 30 days
log: [News] Headlines for 18 of 20 stock(s), 27 market headline(s), 1 feed failed, 41 old row(s) deleted
```

A feed error, a bad XML document or a missing published time skips that item or feed with a log line, and the step never raises. `STEP_PATHS` gets "News" after "Ideas", before "AI employees".

**Economic calendar** (`core/econ_calendar.py`). Dates come from the official schedules (Federal Reserve FOMC calendar, BLS CPI and Employment Situation schedules, BEA release schedule), taken on 2026-11-06 for 2026-11-01 to 2027-12-31:

```
EconEvent(day: date, time: time (NY), name: str, importance: "high"|"medium")
FOMC decision 14:00 (high):   2026-12-09; 2027-01-27, 03-17, 04-28, 06-09, 07-28, 09-15, 10-27, 12-08
CPI 08:30 (high):             2026-11-10, 12-10; 2027-01-13, 02-11, 03-10, 04-13, 05-12, 06-10,
                              07-14, 08-11, 09-14, 10-14, 11-10, 12-10
Jobs report 08:30 (high):     2026-11-06, 12-04; 2027-01-08, 02-05, 03-05, 04-02, 05-07, 06-04,
                              07-02, 08-06, 09-03, 10-08, 11-05, 12-03
PCE 08:30 (medium):           2026-11-25, 12-23; 2027-01-28, 02-25, 03-31, 04-29, 05-27, 06-25,
                              07-29, 08-25, 09-30, 10-28, 11-24, 12-22
GDP 08:30 (medium):           the same days as PCE (BEA releases both together)
COVERED_YEARS = (2026, 2027)
events_between(first, last) -> list[EconEvent]     # a year not covered: one warning per process
next_trading_day(day) -> date                       # data/market_calendar NYSE rule
```

FOMC dates are tentative until the meeting before confirms them. BLS or BEA dates may move (for example in a shutdown). The file is updated once a year, with the NYSE holidays (T125).

**News points** (`news_points(tone, day)`, pure):

```
base = {"positive": 10, "neutral": 6, "none": 6, "negative": 2}[tone]
if any high event on next_trading_day(day): base -= 3
return max(base, 0)
final_score = round(0.9 * score + points, 1)        # score = the P3 idea score
```

**News review skill.** Facts are fresh when the newest `news_items.date` equals the latest ideas day and the SPY candle day. With listed ideas but no headlines at all, it is still fresh, and the facts say "no headlines". The facts text:

```
Data day, rule regime
Economic events in the next 5 trading days: date, time, event, importance
Listed ideas: side, symbol, sector, score
Headlines per idea: up to 5 newest, "date | title"
Market headlines: up to 15 newest
```

Answer:

```
class NewsTag:     side, symbol, tone: Literal["positive","neutral","negative"], reason: str (5..120)
class NewsReview:  tags: list[NewsTag] (1..20)    market: str (20..400)
```

`act` follows the risk check pattern. First it writes code rows for every listed idea (tone `none`, reason "No news review yet", points from `news_points("none")`, final score), before any model call. Then it asks:
- With no valid answer, the code rows stay (the event points hold) and it returns no brief, so a later run tries again.
- With a valid answer, the tags of known ideas replace the code rows. Unknown or repeated ideas are dropped with one log line. It returns `FeedItem("info", market, day)`.

**Risk check and lead (reopened rows).** `views_text` gets a `news_review` part: the day's `news_tags` (side, symbol, tone, points, final score, reason), or "News review: not available today". `RiskCheckSkill.needs` and `LeadBriefSkill.needs` add `news_review`, so LangGraph runs the news review first. The lead's passed-ideas table adds a `final` column (final score, or `-`). The risk limits and the rule that the lead picks only passed ideas do not change.

**Floor panels** (`core/desk_floor.py`, GUI SRD-GUI-034.018–.021):

```
news.latest (real when news_items has rows):
    columns time ("MM-DD HH:MM" NY), headline, symbol ("market" for ''), tone (latest news_tags
    tone of that symbol, else "-"); newest 50; filter tone (positive, neutral, negative)
news.tags (always listed; title "News tags (<day>)" once tags exist, empty before):
    columns symbol, side, tone, points, final, reason; filter side; latest day; by final desc
calendar.week (always real):
    columns date ("Wed 11-10"), time, event, importance; events_between(today, 10th trading
    day after today) in NY time; filter importance (high, medium)
```

`gui/floor_layouts.py` default "News & Calendar" tab: Latest news (cols 0–6, rows 0–13), News tags (cols 0–6, rows 13–26), Calendar (cols 7–11, rows 0–26). A layout the user already saved is kept.

**Default employee** `emp-006`: name "Expert 5", title "Expert", level `expert`, reports_to `emp-005`, skill `news_review`, `trigger: after_run`, primary `claude/default`, backup `openrouter/default`, calls per day 3, monthly cap USD 3. The soul says to judge only the headlines given, to never invent news, to call a headline negative only for real risk (downgrade, guidance cut, probe, offering), and to keep the length limits.

**After the real run** (2026-11-06, copy of the desk folder, data day 2026-11-04, Claude Code CLI haiku):
- The News step kept 203 headlines (all 20 listed stocks plus 30 market headlines; no feed failed).
- In the first pass, good company news on short ideas was tagged positive, so their final score went up. The tone is now judged **for the idea's side**: for a short, bad company news is positive and good company news is negative. This is said in both the soul and the `tone` field description of the schema, so `news_points` needs no flip by side.
- Second pass: the order was Expert 2 → Expert 3 → Expert 5 (news) → Expert 4 (risk) → Lead 1, with 5 of 5 answers valid on the first try, about 30,700 tokens and cost 0. Shorts with buybacks or beats fell to final 58–61, and the lead's facts held the news view and the `final` column.

**After code review.**
- A headline seen again on a later day is moved to that day (`add_news` updates `date` and `fetched` on the same link or title), so the story stays in the day's facts.
- A missing link is stored as NULL, so two linkless headlines don't collide.
- The News step catches every error (`[News] Could not collect headlines`), so it never fails the desk run. It stops fetching more stocks after a 90-second budget (`[News] Time limit reached; N stock(s) not fetched`).
- `is_trading_day` uses year-aware NYSE closures (`NYSE_CLOSED`, 2026 and 2027). The app-wide `data/market_calendar.py` list has no year (T125).
- A later news review that fails keeps the day's earlier real tags.
- Failed-feed log lines say only "timed out", "HTTP 404" or "connection failed", and name the stock.

**Dependencies.** `feedparser>=6.0` in `pyproject.toml`. `USSwing.spec` hidden imports: `us_swing.market.news_step`, `us_swing.market.news_review`, `feedparser`.

## DD-MKT-007.001.D01 — AI Report Pages (P5d)

**Traces:** SRD-MKT-007.001–.008; GUI SRD-GUI-034.022–.026

**Files.**

| File | What |
|---|---|
| `core/report_html.py` | Allow-list HTML cleaner `clean_page()` and the sealed page shell `sealed_document()`; in `core` because `market` (before store) and the GUI (before show) both use it |
| `market/report_page.py` | `ReportPageSkill` (key `report_page`, needs `lead_brief`) |
| `market/store.py` | `canvas_pages` table, `MarketStore.add_page()` |
| `market/employees/emp-007/` | Default employee "Expert 6" (level expert) |
| `core/desk_floor.py` | `DeskFloorData.report_pages()`, `report_page()` (read-only) |
| `gui/ai_desk_pages.py` | AI Desk "Pages" section: version list and sealed preview |
| `gui/sealed_view.py` | `SealedView`: QWebEngineView with a sealed profile and request filter |

**Table** (`market/store.py`, in `desk.db`):

```
canvas_pages(id INTEGER PK, date TEXT, version INTEGER, title TEXT, html TEXT, created TEXT,
             UNIQUE(date, version))
TRIGGER canvas_pages_no_update  BEFORE UPDATE  -> RAISE(ABORT, 'canvas_pages is append-only')
TRIGGER canvas_pages_no_delete  BEFORE DELETE  -> RAISE(ABORT, 'canvas_pages is append-only')
add_page(day, title, html, created) -> version
    in one transaction: version = COALESCE(MAX(version), 0) + 1 WHERE date = day; INSERT
```

On a copy of the real desk, drop both triggers before removing rows (as for `briefs_no_delete`).

**Facts** (`ReportPageSkill.facts`). Fresh when `ideas_day()` is fresh (ideas day = SPY candle day) and an evening brief exists for that day. The evening brief text is read with plain SQL from the desk `briefs` table (`kind = 'evening' AND data_day = day`, newest row); `market` still never imports `desk`. A missing `briefs` table counts as no brief.

```
Data day, rule regime
Lead evening brief: <text>
Lead picks: side, symbol, rank, reason, score, final, setup, trigger, stop
views_text(store, day, ("regime_view", "sector_flow_view", "news_review"))
```

**Answer** (`ReportPage`, `extra="forbid"`): `title` 5–80 chars; `html` 200 to 200 000 chars. Schema descriptions repeat the rules: body HTML with one `<style>` block, tables and inline SVG charts, no scripts, no links, no outside images, images only as `data:image/png|jpeg|gif|webp;base64`, aim for 20–40 KB.

**Cleaner** (`clean_page(html) -> CleanPage(html, removed)`), built on `html.parser.HTMLParser`; the output is rebuilt from scratch, never patched:

```
ALLOWED tags: div span p br hr h1-h6 strong b em i u small sub sup ul ol li dl dt dd
              table thead tbody tfoot tr th td caption colgroup col section article header
              footer figure figcaption blockquote pre code img style
              svg g rect line polyline polygon circle ellipse path text tspan title
DROP WITH CONTENT: script iframe object embed frame frameset noscript template applet
                   link meta base form input button select textarea audio video source
                   canvas math foreignobject
other tags (html, head, body, a, font, ...): tag removed, text kept
attributes: global class style title colspan rowspan align width height
            img: src, alt;  svg/shapes: viewBox x y x1 y1 x2 y2 cx cy r rx ry d points fill
            stroke stroke-width opacity fill-opacity stroke-dasharray transform
            text-anchor font-size font-family font-weight dominant-baseline
            preserveAspectRatio
            any on* attribute, href, xlink:href, src outside img: removed
            a repeated attribute: only the first is kept; every value but img src is CSS-cleaned
img src: only ^data:image/(png|jpeg|gif|webp);base64,[A-Za-z0-9+/=\s]+$  else the img is removed
CSS (<style> text, style="" and other attribute values): first remove every '<' and '\'
            (no CSS escapes), then remove @import, @font-face, url(), image-set(), image(),
            src(), cross-fade(), element(), expression(), local() (also -webkit- forms),
            behavior:, -moz-binding and javascript:, again and again until nothing changes
a self-closed <style/> is removed (a browser would read the rest of the page as CSS)
text: re-escaped; comments, doctype and processing instructions removed
removed = count of tags, attributes and CSS parts taken out
```

`sealed_document(body, title)` wraps the clean body in a fixed page with
`<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">`,
so even a cleaner miss cannot load anything.

**Act** (`ReportPageSkill.act`):

```
page = ctx.ask(facts.text, ReportPage)
if page is None: return []                                  # no row, no brief -> retried later
clean = clean_page(page.html)
size = len(clean.html.encode("utf-8"))
if size > 200_000 or not clean.html.strip():
    log.warning("[Report] Page for %s is too big or empty after cleaning ..."); return []
version = store.add_page(day, page.title, clean.html, now UTC ISO)
log.info("[Report] Page for %s saved as version %d: %d KB written, %d KB kept, %d item(s) removed")
return [FeedItem("info", f"Report page ready: {title} (version {version})", day)]
```

**Sealed view** (`gui/sealed_view.py`, GUI only):

```
one shared QWebEngineProfile(parent=QApplication)  # no storage name -> off the record
    setHttpCacheType(NoCache); setPersistentCookiesPolicy(NoPersistentCookies)
    setUrlRequestInterceptor(_PageOnly)
_PageOnly.interceptRequest(info): if not allowed_scheme(scheme): info.block(True); DEBUG [Pages] log
allowed_scheme(s) = s in {"data", "about"}           # setHtml loads the page itself as data:
_SealedPage(QWebEnginePage).acceptNavigationRequest: only data/about
settings off: JavascriptEnabled, JavascriptCanOpenWindows, JavascriptCanAccessClipboard,
    LocalContentCanAccessRemoteUrls, LocalContentCanAccessFileUrls, LocalStorageEnabled,
    PluginsEnabled, PdfViewerEnabled, ScreenCaptureEnabled, WebGLEnabled
no context menu; show_page(body, title): setHtml(sealed_document(clean_page(body).html, title))
```

**Pages section** (`pages_frame(name, home)`): a live section (rebuilt each time it is shown). Left: table Day · Version · Title · Saved (NY time), newest day first and newest version first, from `report_pages()`. Right: one `SealedView`, created only when there is a page; the first row is shown. A row click loads `report_page(id)`. No pages, or no table yet: a muted note and no web view.

**Sample data.** `gui/ai_desk_sample.py` and `gui/floor_sample.py` use generic names only (Lead 1, Expert 1–6, Champion 1–3, Engineer 1, Secretary 1). The old Studio sample rows are removed.

**Limits.** The gateway time limit is 90 s (SRD-DSK); a very large page may time out, so the schema asks for 20–40 KB.

## DD-MKT-008.001.D01 — Link to Execution (P7)

**Traces:** SRD-MKT-008.001–.006; EXE SRD-EXE-021.001–.007 (see `execution/DD.md` DD-EXE-021.001.D01); GUI SRD-GUI-034.034–.036

**Files.**

| File | What |
|---|---|
| `core/desk_trades.py` (new) | Trade picks, target, state and expiry, trade approval rows, approved picks; the `DeskTradeSink` Protocol |
| `core/desk_ai_settings.py` | New field `trade_target_r: float = 2.0` (above 0) |
| `execution/desk_signals.py` (new) | AI Desk strategy name and type, `build_desk_signal()`, `desk_signal_close()` |
| `execution/broker_adapter.py` | AI Desk entries take stop and target from the signal |
| `gui/app_service.py` | AI Desk strategy row, `desk_pick_qty()`, `send_desk_pick()`, `dismiss_desk_pick()`, close sweep, re-send on start |
| `gui/ai_desk_hiring.py` | `approvals_box()` gains trade pick rows with Approve and Reject |
| `gui/ai_desk.py`, `gui/main_window.py` | `AiDeskWorkspace(poller, sink)`; the main window passes the `AppService` |

**Process rule.** Only the app process writes trade approvals and signals. `core/desk_trades.py` reads `desk.db` with plain SQL and imports neither `desk`, `market` nor `gui`; the desk process never calls it.

**Trade picks** (`trade_picks(home, now, r) -> list[TradePick]`):

```
day = SELECT MAX(date) FROM lead_picks          -- no table or no rows -> []
rows = SELECT l.date, l.side, l.symbol, l.rank, l.reason, i.trigger, i.stop
       FROM lead_picks l
       JOIN ideas i      ON (i.date, i.side, i.symbol) = (l.date, l.side, l.symbol)
       JOIN risk_check r ON (r.date, r.side, r.symbol) = (l.date, l.side, l.symbol)
       WHERE l.date = day AND r.verdict = 'pass'
       ORDER BY l.side, l.rank
for each row: target = pick_target(side, trigger, stop, r); skip when None or trigger/stop NULL
state = pick_state(...)                         -- every state is returned; the GUI shows waiting only
```

`TradePick` (frozen): `day, side, symbol, rank, reason, entry, stop, target, expires, state`; property `subject = f"{day}:{side}:{symbol}"`.

**Target** (`pick_target(side, entry, stop, r) -> float | None`), rounded to 2 places:

```
long : stop < entry -> entry + r * (entry - stop)   else None
short: stop > entry -> entry - r * (stop - entry)   else None
```

**State and expiry.** `pick_expiry(day) = datetime.combine(next_trading_day(day), 09:30, ET)` with `core.econ_calendar.next_trading_day`. `pick_state` reads the newest `approvals` row with `kind = 'trade'` and this subject: decision approve → `approved`, reject → `rejected`; no row and `now >= expires` → `expired`; else `waiting`. Nothing is stored for waiting or expired.

**Decision** (`record_trade_decision(home, pick, decision, qty, now) -> str`; empty string means saved):

```
decision not in {approve, reject}          -> "unknown decision"
executescript(_APPROVALS)                  -- from core.desk_hiring, creates table + triggers if missing
state(pick, now) != waiting                -> "already decided" / "expired"
INSERT approvals (created, kind, subject, decision, detail)
       VALUES (now ISO, 'trade', subject, decision,
               json {"entry", "stop", "target", "qty", "side", "symbol", "day"})
log INFO "[AI Desk] Trade pick %s %s %s"  (side, stock, approved/rejected)
sqlite3.Error -> log ERROR, return "could not save"
```

`trade_picks` logs `[AI Desk] %d trade pick(s) expired` at INFO when the count of expired picks is above 0.

**Approved picks** (`approved_picks(home, trading_day) -> list[TradePick]`): `approve` rows of kind `trade` whose `next_trading_day(day) == trading_day` and that have no `trade_done` row, rebuilt from the detail JSON (state `approved`). Used by the restart re-send. `record_trade_outcome(home, subject, outcome, now)` adds the `trade_done` row (`executed` or `dismissed`) when a desk signal leaves Execution.

**Sink Protocol** (in `core/desk_trades.py`, so the GUI types it without importing `gui.app_service`):

```
class DeskTradeSink(Protocol):
    def desk_pick_qty(self, pick: TradePick) -> int: ...
    def send_desk_pick(self, pick: TradePick) -> tuple[int, str]: ...   # (qty, "") or (0, reason)
    def dismiss_desk_pick(self, pick: TradePick) -> None: ...
```

**GUI — Approvals waiting** (`approvals_box(home, open_hiring, sink=None)`). Hire lines stay as today. Below them, one row per waiting pick, newest day only:

```
LONG  AAPL  entry 101.20  stop 97.40  target 108.80  qty 45   [Approve] [Reject]
```

Quantity comes from `sink.desk_pick_qty(pick)`; with no sink the quantity shows "—" and both buttons are disabled. The empty note shows only when there are no hires and no waiting picks. Buttons use `C.BTN_H` from the global QSS; no fixed heights.

```
Approve: state now != waiting -> show reason, disable row
         qty, why = sink.send_desk_pick(pick); why -> show why in the row, keep buttons on
         err = record_trade_decision(home, pick, "approve", qty, now)
         err -> sink.dismiss_desk_pick(pick); show err
         ok  -> remove the row
Reject : err = record_trade_decision(home, pick, "reject", 0, now); ok -> remove the row
```

The Command section is live, so a rebuild on each show drops decided and expired picks (SRD-GUI-034.036).

## DD-MKT-009.001.D01 — Pick Results (P8)

**Traces:** SRD-MKT-009.001–.008; GUI SRD-GUI-034.037–.038

**Files.**

| File | What |
|---|---|
| `market/pick_results.py` (new) | `paper_result()` (pure rule) and the desk step `PickResultsStep` ("Pick results") |
| `market/store.py` | Table `pick_results`, `MarketStore.replace_pick_results()` |
| `core/desk_results.py` (new) | Table `pick_trades`, `record_pick_trade()` (app), `results_view()` and `results_lines()` (GUI and weekly report) |
| `core/desk_steps.py` | `PickResultsStep` path after `NewsStep` (so after Ideas), before AI employees |
| `gui/app_service.py` | `CycleClosed` of the AI Desk strategy → `record_pick_trade()` |
| `desk/weekly_report.py` | Pick results section |
| `gui/ai_desk_results.py` (new), `gui/ai_desk.py` | Live AI Desk section "Results" after "Reports" |

**Paper rule** (`paper_result(side, trigger, stop, target, bars, day) -> PaperResult | None`). `bars` holds the daily highs, lows and closes of one stock with dates after the pick's data day, oldest first.

```
valid: long needs stop < trigger < target; short needs target < trigger < stop; else None
entry: first of the first 5 bars where (long) high >= trigger / (short) low <= trigger
       none of 5 bars touched -> no_fill (when 5 bars exist), else open with no entry yet
from the entry bar (day 1) to day 10:
       stop reached  (long low <= stop / short high >= stop)        -> stop,   exit = stop
       target reached (long high >= target / short low <= target)   -> target, exit = target
       both on one bar                                              -> stop
       day 10 without either                                        -> time,   exit = close of day 10
fewer bars than needed -> open, exit = latest close (mark), exit day blank
R = (exit - entry) / (entry - stop) for long, (entry - exit) / (stop - entry) for short, 2 places
```

Entry is the trigger and exits are the stop or target price; daily bars have no open, so gaps are not modelled. Target is `pick_target(side, trigger, stop, trade_target_r)` from `core.desk_trades`, with the desk setting.

**Step** (`PickResultsStep`, name "Pick results", after "Ideas" and "News", before "AI employees"). Reads every `lead_picks` row joined with `ideas` (trigger, stop), the daily bars of those symbols from `candles.db` (`CandleReader`), works out each pick, and calls `replace_pick_results(rows)`. No candle file → one warning, nothing written. Logs `[Results] %d pick(s) worked out, %d still open`.

**Table** (`market/store.py`, in `desk.db`):

```
pick_results(date, side, symbol, status, entry_day, entry, exit_day, exit, r,
             PRIMARY KEY (date, side, symbol))
replace_pick_results(rows): one transaction, DELETE all, INSERT rows; status not in
             (no_fill, open, stop, target, time) -> ValueError
```

**Real trades** (`core/desk_results.py`, written by the app only):

```
pick_trades(id INTEGER PK, created, subject, symbol, side, entry_time, entry, exit_time, exit,
            qty, pnl, r, exit_reason)   + no-update and no-delete triggers
record_pick_trade(home, snap, now):
    side = "long" if snap.direction == "LONG" else "short"
    subject = newest approvals row kind 'trade_done', decision 'executed',
              subject ending ":{side}:{symbol}"  ("" when none)
    r = from entry, exit and snap.hard_stop_loss as in the paper rule (None when risk is 0)
    one INSERT; sqlite3.Error -> log ERROR
```

`AppService._on_cycle_closed_clear_pending` also calls `_record_desk_trade(evt.snapshot)` when `strategy_id == "AI Desk"`; it runs on the cycle thread and opens its own connection.

**Results view** (`results_view(home, first=None, last=None) -> ResultsView`), plain SQL, every table optional:

```
picks: lead_picks LEFT JOIN pick_results, setup_review (grade), news_tags (tone)
       decision = first 'trade' approvals row of the subject, else expired/waiting by pick_expiry
       real P&L = SUM(pick_trades.pnl) for the subject
       only data days in [first, last] when given; newest first
Group(label, picks, fills, finished, targets, hit_rate, avg_r)
       fills = status not in (no_fill) and has entry; finished = stop/target/time
       hit_rate = targets / finished; avg_r over finished
totals: Group("All", ...); breakdowns: "Decision", "Setup grade" (A/B/C/none), "News tone"
real: trades, wins (pnl > 0), pnl, avg_r over pick_trades in the range (by exit day)
```

`results_lines(view)` gives short text lines for the weekly report: paper totals, the three breakdowns, real totals; "No lead picks this week" when there are none.

**Weekly report.** `build_report` adds a blank line, "Pick results", and `results_lines(results_view(home, first, friday))`.

**GUI Results** (`results_frame(name, home)`). Top line: paper picks, fills, hit rate, average R; real trades, wins, P&L. Three small tables (Decision, Setup grade, News tone: Group · Picks · Fills · Finished · Hit rate · Avg R). Then the pick table: Day · Side · Stock · Decision · Paper · R · Real P&L, newest first. Empty note "No lead picks yet" when there are none. Labels are skills and inputs only; employee names never appear.

## DD-MKT-010.001.D01 — Lead Chat (P9)

**Traces:** SRD-MKT-010.001–.008; GUI SRD-GUI-034.039–.041

**Files.**

| File | What |
|---|---|
| `core/desk_chat.py` (new) | Append-only `chat` table; `ask_question()` (GUI), `open_question()`, `add_reply()` (desk), `chat_turns()`, `question_note()` |
| `core/desk_events.py` | Event kind `chat_question`; one key per question |
| `market/lead_chat.py` (new) | `LeadChatSkill` (key `lead_chat`, no needs) and `LeadChatAnswer` |
| `market/employees/emp-008/` (new) | Default employee "Lead 2" (level lead, skill `lead_chat`, trigger `chat_question`) |
| `core/desk_steps.py` | `lead_chat` skill path |
| `gui/ai_desk_chat.py` (new) | `ChatPanel`: turns, Ask box, 2-second check while a question waits |
| `gui/ai_desk_sections.py`, `gui/ai_desk.py` | `command_frame(name, approvals, chat)`; the workspace passes a `ChatPanel` with the poller |

**Table** (`core/desk_chat.py`, in `desk.db`):

```
chat(id INTEGER PK, created TEXT, role TEXT, text TEXT, reply_to INTEGER, state TEXT)
  role master: a question (state 'asked');  role lead: a reply (state 'answered' or 'failed')
  + no-update and no-delete triggers
ask_question(home, text, now) -> int:
    text stripped; 1..500 chars else ValueError
    INSERT master row; post_event(home, "chat_question", now date, now, run_id=id)
open_question(home, now) -> ChatTurn | None:
    oldest master row with no lead reply and created within 30 minutes
add_reply(home, question_id, text, ok, now): INSERT lead row (answered / failed)
chat_turns(home, limit=50) -> list[ChatTurn]   oldest first, last ``limit`` rows
question_note(home, question_id, now, desk_up) -> str:
    "" when replied; "Waiting for the answer" when desk_up; "Start the desk to get an answer"
    otherwise; "No answer: the question expired" after 30 minutes
```

**Event.** `EVENT_RULES["chat_question"] = EventRule(0, 2 min, 30 min)`. The key is `chat_question|<day>|<question id>` (`post_event` uses `run_id` for `after_run` and `chat_question`), so every question is its own event. Priority 0 skips the 30-minute wake gap; the once-per-day rule is only for `after_run`.

**Skill** (`LeadChatSkill`, key `lead_chat`, needs `()`):

```
facts(home):
    q = open_question(home, now NY)              none -> fresh False, "no open question"
    day = latest lead_picks / ideas day ("" when none)
    text = "Question #<id>: <text>"
         + "Recent chat:" last 6 turns before q (Master / Lead lines)
         + "Today (<day>):" LeadBriefSkill().facts(home).text  (views, passed ideas, grades)
         + "Picks of the last 10 trading days:" results_view(home, now, first) lines per pick:
           day side symbol decision paper-status R real-P&L
act(ctx, facts):
    q = open_question(ctx.home, now)             gone -> []
    ans = ctx.ask(facts.text, LeadChatAnswer)
    add_reply(home, q.id, ans.answer if ans else FAILED_TEXT, ok=ans is not None, now)
    log "[Chat] Question %d answered in %.1f s" / "[Chat] Question %d got no answer"
    return []                                    no feed item
```

`LeadChatAnswer(answer: str, 1..1500 chars, extra forbid)`. The schema has one text field and the chat has no tools, so it cannot act (SRD-MKT-010.006). `FAILED_TEXT = "The desk could not answer this question. Please ask again later."`

**Employee** `emp-008`: name "Lead 2", title "Chat lead", level lead, skill `lead_chat`, trigger `chat_question`, models as the lead, `calls_per_day: 200`, `monthly_cost_usd: 3.0`. The soul says: answer only from the facts, short plain words, say "I do not know" when the facts do not say, never claim to approve or trade.

**GUI** (`ChatPanel(home, poller)`, built in the live Command section):

```
list of turns: "<b>Master</b>" or "<b><chat employee name></b>" (current name of the active
               employee with skill lead_chat, else "Lead"), failed replies muted
Ask box (QLineEdit, max 500) + Ask button; Ask disabled when empty or a question waits
Ask: ask_question(); clear box; note = question_note(); start 2 s QTimer
tick: rebuild turns; note = question_note(..., desk_up = poller state Running or Sleeping);
      stop the timer when replied or expired
```

The panel reads `desk.db` on the GUI thread (small reads, as the other live sections) and only adds `chat` rows and one event through `core`.

## DD-MKT-011.001.D01 — Ask the Desk for New Data (P10)

**Traces:** SRD-MKT-011.001–.009; GUI SRD-GUI-034.042–.044

**Files.**

| File | What |
|---|---|
| `core/desk_recipes.py` (new) | The fixed menu, `DataRecipe` (pydantic), `check_recipe()`, `run_recipe()`, `recipe_words()` |
| `core/desk_data_asks.py` (new) | Append-only `data_requests` and `asked_products` tables; `ask_data()` (GUI), `open_request()`, `add_asked()` (desk), `waiting_products()`, `failed_products()`, `approved_products()`, `decide_product()` |
| `core/desk_events.py` | Event kind `data_request`; one key per request |
| `market/data_recipe.py` (new) | `DataRecipeSkill` (key `data_recipe`, no needs) and `DataRecipeAnswer` |
| `market/employees/emp-009/` (new) | Default employee "Expert 7" (level expert, skill `data_recipe`, trigger `data_request`) |
| `core/desk_steps.py` | `data_recipe` skill path |
| `core/desk_floor.py` | Approved asked products in `products()` and `rows()` |
| `core/desk_feed.py`, `gui/floor_feed.py`, `gui/ai_desk_hiring.py` | Data product Ask cards with Approve and Reject; failed request cards |
| `gui/floor_dialogs.py`, `gui/market_floor.py` | Ask box in the Add panel catalog |

**Process rule.** The GUI only adds `data_requests` rows, `approvals` rows and one event through `core`. The desk adds `asked_products` rows. Every recipe runs on a read-only connection (`?mode=ro`). No model text is ever put into SQL: table and column names come only from the menu in code, and filter values are bound as parameters.

**Menu** (`core/desk_recipes.py`). Each source is a fixed `FROM` text, a day column and a map of column name → (SQL expression, type):

```
scores       stock_score s LEFT JOIN stock_rs r ON r.date = s.date AND r.symbol = s.symbol
             day s.date; symbol, side, score, setup, sector (r.sector), trigger, stop,
             rs_part, flow_part, setup_part, sector_part, regime_part, penalty
ideas        ideas; day date; symbol, side, status, rank, score, sector, setup, trigger, stop
stock_rs     stock_rs; day date; symbol, sector, score, rs_rating, sector_rank, sector_size
sectors      sector_daily; day date; sector, rank, rel_1m, rel_3m, rel_6m, rs_ratio,
             rs_momentum, quadrant, members
pick_results pick_results; day date; symbol, side, status, entry_day, entry, exit_day, exit, r
```

Types are `text` or `number`. Labels for words: Scores, Ideas, Stock RS, Sectors, Pick results.

**Recipe** (`DataRecipe`, pydantic, `extra="forbid"`, frozen):

```
title: str 1..60
source: Literal["scores", "ideas", "stock_rs", "sectors", "pick_results"]
columns: list[str] 1..8
filters: list[RecipeFilter] 0..5   RecipeFilter(column: str, op: Literal["=", "!=", ">",
                                   ">=", "<", "<="], value: str | float)
sort: str | None = None;  descending: bool = True
limit: int 1..100 = 20
```

**Check** (`check_recipe(recipe) -> str`; empty string means fine):

```
column not in menu[source]               -> "unknown column <c>"
duplicate column                         -> "column <c> twice"
filter column not in menu                -> "unknown filter column <c>"
text column with op not in (=, !=)       -> "<c> takes = or != only"
number column with a non-number value    -> "<c> needs a number"
sort not None and not in menu            -> "unknown sort column <c>"
```

**Run** (`run_recipe(home, recipe) -> list[dict[str, Any]]`):

```
check_recipe(recipe) != ""   -> ValueError
no desk.db                   -> []
sql = SELECT <expr AS name, ...> FROM <from>
      WHERE <day> = (SELECT MAX(<day col>) FROM <day table>)
        AND <expr> <op> ? ...                  -- values bound, op from the Literal set
      ORDER BY <sort expr> IS NULL, <sort expr> DESC|ASC   (when sort is set)
      LIMIT ?                                  -- min(limit, 100)
connect f"{path.as_uri()}?mode=ro"; sqlite3.Error -> []
```

Number values are rounded to 2 places. The latest data day is found again on every call, so an approved panel shows the new day's rows after each evening run without a rebuild (refresh choice).

**Words** (`recipe_words(recipe) -> str`), for example: `Scores · symbol, side, score, sector · side = long, score > 80, sector = Technology · score high to low · up to 20 rows`.

**Tables** (`core/desk_data_asks.py`, in `desk.db`):

```
data_requests(id INTEGER PK, created TEXT, text TEXT)
asked_products(id INTEGER PK, created TEXT, request_id INTEGER UNIQUE, state TEXT,
               title TEXT, recipe TEXT, reason TEXT)     state 'proposed' or 'failed'
  + no-update and no-delete triggers on both tables
ask_data(home, text, now) -> int:
    text stripped; 1..300 chars else ValueError
    INSERT data_requests; post_event(home, "data_request", now date, now, run_id=id)
open_request(home, now) -> DataRequest | None:
    oldest request with no asked_products row and created within 2 hours
add_asked(home, request_id, recipe | None, reason, now) -> int:
    INSERT asked_products: proposed (title, recipe JSON) when recipe, else failed (reason)
waiting_products(home) -> list[AskedProduct]     proposed with no 'data_product' approval
failed_products(home, now) -> list[AskedProduct]  failed within the last day, newest first
approved_products(home) -> list[AskedProduct]    proposed with an 'approve' row
decide_product(home, product_id, decision, now) -> str:
    decision not in {approve, reject} -> "unknown decision"
    not a proposed product            -> "not found"
    a decision row exists             -> "already decided"
    INSERT approvals (now, 'data_product', str(id), decision, title)
    sqlite3.Error                     -> "could not save"
```

`AskedProduct` (frozen): `id, created, request_id, request, state, title, recipe (DataRecipe | None), reason`. A stored recipe that no longer parses or checks is `None`, and the product is left out of the catalog.

**Event.** `EVENT_RULES["data_request"] = EventRule(0, 5 min, 2 h)`. The key is `data_request|<day>|<request id>`, like `chat_question`.

**Skill** (`DataRecipeSkill`, key `data_recipe`, needs `()`):

```
facts(home):
    r = open_request(home, now NY)              none -> fresh False, "no open request"
    text = "Request #<id>: <text>"
         + "Menu:" one line per source: label (key): column (type), ...
         + "Known values:" sides long/short, idea status list/watch, pick status list,
           sector names of the latest sector_daily day
         + the rules: one source; menu columns only; empty recipe and a reason when the
           menu cannot serve the request
act(ctx, facts):
    r = open_request(ctx.home, now)             gone -> []
    ans = ctx.ask(facts.text, DataRecipeAnswer)
    ans None                -> failed "The desk could not answer this request"
    ans.recipe None         -> failed ans.reason (or "The menu cannot serve this request")
    check_recipe() != ""    -> failed "The recipe did not pass the check: <why>"
    else                    -> proposed
    log INFO "[Data] Request %d proposed: %s" (title) / WARNING "[Data] Request %d failed: %s"
    return []                                   no feed item
```

`DataRecipeAnswer(recipe: DataRecipe | None, reason: str 0..300, extra forbid)`.

**Employee** `emp-009`: name "Expert 7", title "Data analyst", level expert, skill `data_recipe`, trigger `data_request`, models as the other experts, `calls_per_day: 20`, `monthly_cost_usd: 3.0`. The soul says: choose from the menu only, never write SQL, keep the title short, say why when the menu cannot serve the request.

**Floor catalog** (`DeskFloorData`). `products()` appends one product per approved asked product: id `asked.<id>`, title `<title> (asked)`, kind `table`, views `("table",)`, columns the recipe columns, no filters. `rows("asked.<id>", _)` runs the recipe; an unknown id gives `[]`.

**GUI — Ask box** (`CatalogDialog(products, parent, ask=None)`). Under the list: a `QLineEdit` (max 300, placeholder "Ask the desk for new data") and an Ask button, disabled while the box is empty. `ask(text) -> str` returns an empty string when the request was saved (the box is cleared and "Sent. The new panel will wait for you in AI Desk → Command." shows) or the reason it was not (the text is kept). Ask is the default button while the box has text, so Enter sends the request instead of adding a panel. `MarketFloor` passes `_ask_desk`, which calls `ask_data(feed home, text, now)`, and refreshes its product list each time the catalog opens. With no `ask` the box is hidden.

**GUI — Approvals waiting.** `ask_cards()` adds one Ask card per waiting product: sender "Data", subject `New panel · <title>`, time = created, text = recipe words + the first 5 preview rows (`a · b · c` per row, or "No rows on the latest day"), `ref = "data"`, `item = product id`. The card has Approve and Reject; each calls `decide_product()`, and the box reloads, so a decided product leaves the list. `failed_cards()` gives one Desk card per failed request of the last day (subject `Request not built`, text `<request> — <reason>`, no buttons). `WaitingBox` shows them after the Asks; they do not count in the heading.

## DD-MKT-001.013.D01 — Candle Check, Yahoo Desk Copy and Morning Brief (Autonomous desk step A)

**Traces:** SRD-MKT-001.013–.017, SRD-MKT-005.015–.016, SRD-DSK-007.007.

**Why a desk copy.** `candles.db` daily bars come only from IBKR "Update now", which downloads only stocks that are behind (ISS-GUI-0018). Writing Yahoo bars there would mix sources for good. The desk keeps its own short copy in `desk.db` and drops each row as soon as IBKR has that day.

**Table.** `candle_topup(symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, fetched TEXT, PRIMARY KEY (symbol, date))`, created by `MarketStore` like the other market tables. `symbol` uses the `candles.db` spelling (e.g. `BRK.B`).

**Target day.** `last_closed_day(now)`: in ET, today when it is an NYSE trading day and the time is 16:00 or later, else the trading day before (walk back over weekends and holidays).

**Step `CandleCheckStep` ("Candle check", first in `STEP_PATHS`).**

```
target = last_closed_day(now)
reader = CandleReader(candles)                      # missing file -> CandleCheckError
wanted = member_symbols(reader.symbols(), universe).symbols + [SPY]
db_last = last candles.db day per wanted symbol
store.trim_topup(db_last)                           # delete copy rows on/before db_last[sym]
store.drop_unsettled_topup()                        # copy rows fetched before 16:30 ET of their day (bar may not be final)
behind = [s for s in wanted if max(db_last[s], copy_last[s]) < target]
if behind:
    yahoo = fetch(behind, start = min(db_last of behind) - 20 days, end = target)
    rows  = topup_rows(db_bars(behind, last 20 days), yahoo, target)
    store.write_topup(rows)
still = behind after the copy
log "[Candles] %d stock(s) behind %s, %d filled from Yahoo, %d still behind"
if SPY in still or len(still - {SPY}) > 2% of members:
    raise_alert(home, "candles", "", run_id, "...N of M stocks still behind <target>")
    raise CandleCheckError("Candles not up to date: N of M stocks behind <target>")
```

The error fails the run before any AI step; the desk retries per SRD-DSK-001.015. A stock not in `candles.db` at all (new to the index) is not counted, as the other steps already leave it out.

**`topup_rows` (pure).** Per stock, the overlap is the days in both sources (up to the last 10):
- fewer than 3 overlap days, or any overlap close off by more than 0.5% → skip the stock (logged at DEBUG); this guards against split or symbol mix-ups.
- volume scale = median of IBKR volume / Yahoo volume on the overlap days. IBKR counts regular-hours trades only; on 2026-11-09 the ratio was 0.36–0.63 (SPY, AAPL, BRK.B, JPM). Prices matched exactly with `auto_adjust=False`.
- new rows = Yahoo days after the stock's last `candles.db` day and on or before `target`; volume = round(Yahoo volume × scale).

**Fetch.** `fetch_daily(symbols, start, end)`: `yf.download(tickers=[yahoo_symbol(s)...], start, end + 1 day, interval="1d", auto_adjust=False, group_by="ticker", threads=True, progress=False)`; returns `{symbol: frame(open, high, low, close, volume)}` by our spelling; any error → empty dict (logged as a warning). Injectable for tests.

**Reader merge.** `CandleReader(path, topup=home)`: `read()` reads `price_1d` (dedupe keep last, as today), then `candle_topup` rows of the same symbols from `home/desk.db` (read-only; missing table = none), concat with `candles.db` first and `drop_duplicates(["symbol", "date"], keep="first")`, so IBKR always wins. `symbols()` returns the union. Steps pass `topup=ctx.home`. `latest_spy_day(candles, store)` returns the later of the `candles.db` SPY day and the copy's SPY day, so skill freshness checks (`ideas_day`, regime and sector views) see the filled day.

**Morning brief.** `LeadBrief.evening` is renamed `morning` (same limits); the skill posts `FeedItem("morning", ...)`. `core/desk_agents.FEED_KINDS` adds `morning`; `core/desk_feed` titles it "Morning plan" and keeps "Evening result" for old rows. `report_page` reads the newest brief of kind `morning` or `evening` for the day and labels it "Lead brief". The shipped lead `employee.md` prompt says "morning brief".

## DD-MKT-012.001.D01 — Learning from Pick Results (Autonomous desk step C)

**Traces:** SRD-MKT-012.001–.006. The full design (tags, stats, reflect skill, default employee, lessons block in the four pick-making skills, daily review called by the "Pick results" step) is in DSK DD-DSK-009.001.D01, because the lesson rules live in `core/desk_lessons.py`. MKT owns `market/lesson_reflect.py`, `market/employees/emp-010/` and the one-line facts change in `setup_review.py`, `news_review.py`, `risk_check.py` and `lead_brief.py`; `pick_results.py` calls `review_lessons()` after it writes the results.

## DD-MKT-013.001.D01 — Intraday Watchers and Check-in Notes (Autonomous desk step D)

**Traces:** SRD-MKT-013.001–.012. Full design (bars, watcher rules, flag and check-in skills, default employees) is in DSK DD-DSK-003.020.D01. MKT owns `market/watch.py`, `market/watch_flag.py`, `market/checkin_note.py` and `market/employees/emp-011/`, `emp-012/`.

## DD-MKT-014.001.D01 — Lead Research Tickets (Autonomous desk step E)

**Traces:** SRD-MKT-014.001–.005. Full design (ticket form, rules, research block) is in DSK DD-DSK-010.001.D01. MKT owns the `tickets` field of `LeadBrief` and `CheckinNote`, the `with_research()` wrap in both skills' facts and the `raise_tickets()` call in both skills' `act`.

## DD-MKT-015.001.D01 — Setup Tuning Research (Autonomous desk step F, skill 1)

**Traces:** SRD-MKT-015.001–.012. Runner, caps, stalls, pauses and `research_done` stay in DSK (DD-DSK-010.001.D01); this skill only implements `ResearchSkill.step`.

### 1. Steps of one ticket

The runner does one `step()` per desk tick, so a ticket runs as a short chain and a watcher flag can pause it between any two steps. The plan lives in `ticket.state` (JSON).

| Step | Kind | What happens | Note / call |
|---|---|---|---|
| 1 `pick` | AI (1 call) | Facts: ticket topic, goal, done test; the 6 desk setups with knobs (default, low, high); live strategies with a fixed stop and their numeric values. Answer `TuningPlan`. Code checks the target and drops bad changes. | "Picked 3 variant(s) for Pullback" / `pick` |
| 2 `run base` | code | Baseline (default values, or the live strategy as it is). | "Baseline: 1,204 trades, win 47%, +0.08R" / `run base` |
| 3..5 `run v1..v3` | code | One variant per step. | same form / `run v1` |
| last `verdict` | AI (1 call) + code | Code computes the gain; AI reads the table and writes `TuningVerdict`. A desk-setup gain writes the candidate lesson. Outcome `done`. | verdict text / `verdict` |

Worst case 6 steps, inside the default step cap of 8. Code steps spend no tokens. `step_tokens = 3_000` (one AI step). A failed AI answer returns an empty note; the runner's stall rule ends the ticket after 2 such steps.

State:

```json
{"phase": "run", "target": "Pullback", "kind": "setup", "side": "long",
 "variants": [{"label": "v1", "changes": {"near_sma": 1.01}}],
 "stocks": [], "rows": [{"label": "base", "changes": {}, "trades": 1204,
 "win": 0.47, "exp_r": 0.08}]}
```

Ends `failed` (SRD-MKT-015.001/.003/.005): target is not a desk setup or a live strategy; no valid variant left; strategy with no fixed stop; strategy with no stocks; backtest estimate errors; no data at all.

### 2. Answer forms

```python
class Change(BaseModel):      # extra="forbid" on all four
    knob: str = Field(min_length=1, max_length=40)
    value: float
class VariantAsk(BaseModel):
    changes: list[Change] = Field(min_length=1, max_length=2)
class TuningPlan(BaseModel):
    target: str = Field(min_length=1, max_length=60)
    variants: list[VariantAsk] = Field(min_length=1, max_length=3)
    stocks: list[str] = Field(default_factory=list, max_length=30)
class TuningVerdict(BaseModel):
    verdict: str = Field(min_length=10, max_length=600)
```

Change checks: a knob not in the target's list, a value outside its range, a repeat knob in one variant, or a variant equal to the baseline is dropped. Whole-number knobs are rounded.

### 3. Desk setup knobs (SRD-MKT-015.002)

`market/setup_knobs.py` holds `Knob(name, default, low, high, whole)` and `KNOBS: dict[setup, tuple[Knob, ...]]`. `setups.long_candidates(bars, values=None)` and `short_candidates(bars, values=None)` read each limit through `knob_value(values, setup, name)`. With `values=None` every limit is today's number, so live picks stay exactly the same.

| Setup | Knob | Default | Range |
|---|---|---|---|
| Squeeze | `width_vs_min` | 1.1 | 1.0–1.5 |
| Squeeze | `atr_ratio` | 0.8 | 0.5–1.0 |
| Flat base | `near_high` | 0.9 | 0.8–0.97 |
| Flat base | `depth` | 0.15 | 0.08–0.25 |
| Pullback | `near_sma` | 1.02 | 1.0–1.05 |
| Pullback | `sma_days` | 21 (whole) | 10–50 |
| Failed breakout | `pivot_days` | 25 (whole) | 10–50 |
| Failed breakout | `recent_days` | 10 (whole) | 5–20 |
| Lower highs | `swing_days` | 10 (whole) | 5–20 |
| Breakdown | `volume_x` | 1.5 | 1.0–3.0 |

### 4. Desk setup replay (SRD-MKT-015.004, .006, .007)

`market/tuning_replay.py`:

1. Data: `proof_data.read_daily` on the S&P 500 members (`candles.member_sectors`) plus SPY, from the Backtest Data daily files, aligned to SPY days. This is the same input as the score proof (the SRD In cell says `candles.db`; the desk's 5-year replay data is the Backtest Data daily store). No SPY or no members → `None` (ticket `failed`).
2. Window: signals only on the last 5 years of SPY days (`proof.FULL_YEARS`); older bars only warm up the averages.
3. Signals: the target setup's own match, trigger and stop from `long_candidates` / `short_candidates` with the variant values (not the best-of-six pick).
4. Trades: per stock, oldest first. On a match day with a valid trigger and stop, target = trigger ± 2 × |trigger − stop|; `pick_results.paper_result` runs on the bars after that day. The stock is busy until the exit day (filled) or for 5 days (no fill), so one setup run gives one trade.
5. Row: closed trades (stop, target, time), win = share with R > 0, `exp_r` = mean R.

Gain (SRD-MKT-015.007), `gain(rows)`: the best variant by `exp_r − base.exp_r`; a gain when that change is ≥ 0.05 and the variant has ≥ 100 trades. Pure code; the AI only sees the table.

### 5. Strategy run (SRD-MKT-015.005)

`market/tuning_strategy.py`. The backtest service is imported inside the run function (heavy; the desk loads it only when a strategy ticket runs).

- Knobs: `target_value`, `stoploss_value` and each number in `entry_condition` / `exit_condition` as `entry#1`, `entry#2`, `exit#1`… (number tokens counted left to right). Range 0.5× to 1.5× the current value.
- Copy: `dict(live)`, name `"<name> (tune <label>)"`, each change replaces that one number in the text.
- Fixed stop needed: `stoploss_enabled` and `stoploss_type == "fixed"`; else `failed`.
- Stocks (user 2026-11-11): the strategy's `symbols_include` when `symbol_mode` is not `all` and the list is not empty; else the AI's `stocks` (≤ 30), kept only if in the S&P 500 list; none left → `failed`.
- Plan: `RunPlan(period = last 5 years, universe names, screener skip, one strategy, default account and costs)`. `estimate()` first; errors → `failed`; `data_span` narrows the period.
- Run: a `BacktestService` whose strategy loader returns only the copy; `run_stocks(record=False)`, `run_signals(record=False)`, then `steps.portfolio.run_portfolio` directly, so nothing is saved as a Backtest run and the live list is never written. `workers=0` (no child processes in the desk).
- R per trade = `net_pnl / (qty × entry_px × stoploss_value / 100)`. Row as in §4.

### 6. Verdict, lesson and report (SRD-MKT-015.008–.010)

Verdict facts: target, the table rows (label, changes, trades, win, R, change), the code's gain line, and the done test. The note is the verdict, so the ticket result holds every step's row plus the verdict.

Lesson (desk-setup gain only): `add_candidate(home, text, {"setup": target, "side": side}, "worse", proof, now)`. Text: "<Setup> <side>s with today's limits did worse than <changes> in the backtest (<base>R vs <best>R)", cut to 200 characters. Proof: one line with the ticket id and both rows. `claim = "worse"` because a lesson may only make the desk stricter: it tells the desk the current setup is weaker, and real pick cases decide whether it goes active (FO-MKT-012). A strategy gain writes no lesson. Nothing writes to the setup limits, the strategies table or employee files.

### 7. Employee and wiring (SRD-MKT-015.011, .012)

- `market/employees/emp-013/employee.md`: name "Expert 10" (generic Level N rule of UT-MKT-005.017; SRD cell says "Researcher 1"), title "Research analyst", level expert, `reports_to: null`, skill `setup_tuning`, trigger `research_done` (the trigger list may not be empty; `facts()` always says it works research tickets only, so the event only gives one sleep log line).
- `SKILL_PATHS["setup_tuning"] = "us_swing.market.setup_tuning:SetupTuningSkill"`; the `USSwing.spec` hidden imports gain `us_swing.market.setup_tuning` (it imports the other three).
- Logs (`[Research]`): "Ticket 12 will test 3 variant(s) of Pullback", "Ticket 12 Pullback v1: 1,180 trades, +0.15R", "Ticket 12 Pullback found a gain: v1 +0.07R" or "found no gain".
