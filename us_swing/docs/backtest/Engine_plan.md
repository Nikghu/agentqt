# Engine_plan — Backtest Engine (Stocks → Signals → Portfolio → Report)

**Status:** Phase 0 to 3 done (code); Phase 4a done (code); Phase 4b and 5 next
**Tool:** BKT (engine) + GUI (Backtest workspace) + MCP (last)
**Author:** USSwing
**Created:** 2026-10-29
**Branch:** `feat/backtest-phase0` (plan + 15m/1w merged via PR #93)
**Design page:** https://claude.ai/artifact/EKKhu8pb3KSLYpXqpbsQrm (diagrams, mockups, worked example)

This plan is the hand-over document between sessions. Read §0 (status) first, then the
section for the phase in progress. Update §0 at the end of every session.

---

## 0. Status Tracker

| Phase | Name | Docs (FO/SRD) | Backend | GUI | User check | Commit |
|---|---|---|---|---|---|---|
| 0 | Foundation | Approved | Done | Done | OK | see DEVLOG 2026-10-29 |
| 1 | Step 1 · Stocks | Approved | Done | Done | OK | see DEVLOG 2026-10-29 |
| 2 | Step 2 · Signals | Approved | Done | Done | OK | see DEVLOG 2026-10-29 |
| 3 | Step 3 · Portfolio | Approved | Done | Done | Pending | see DEVLOG 2026-10-29 |
| 4 | Step 4 · Report | Approved (4a) | Done (4a) | Done (4a) | Pending (4a) | see DEVLOG 2026-10-29 |
| 5 | Quick test in Screener | Not started | — | — | — | — |
| 6 | MCP tools | Not started | — | — | — | — |

Cell values: `Not started` → `Draft` → `Approved` (docs) / `In progress` → `Done` (code) /
`Pending` → `OK` (user check) / commit hash.

**Done before Phase 0 (2026-10-29):** store keeps 15m and 1w built from 3m and 1d (SRD-BKT-001.012–.014, SRD-GUI-030.010, RN-BKT-1.1.0).

**Done 2026-10-29:** Phase 0 and 1 (FO-BKT-002, FO-GUI-031; SRD-BKT-002.001–.017, SRD-GUI-031.001–.004, .010–.012; RN-BKT-1.2.0, RN-GUI-1.39.0). Minimal requirements, approved by user for code. R2 answered: scores are per stock except the RS-rank rule, so Step 1 caches one file per day keyed by the whole stock list (not per stock). AI ranking tick and weekly presets are refused for now. SPY is not in the backtest store.

**Done 2026-10-29 (Phase 2):** SRD-BKT-002.020–.029, SRD-GUI-031.020–.023 (minimal, approved by user for code; RN-BKT-1.3.0, RN-GUI-1.40.0). User choices: the parser is re-exported from live in `core/expr` (live code not moved, R7 avoided); VWAP resets each session (R5). Parity gate: 50 real stocks, 60,000 values, 0 mismatches. Price reads the forming 15m bar like live; other indicators use closed bars, so inside a forming 15m bar they can differ from live (R4). Found in live (not fixed): VWAP adds up 30 days with no daily reset; `PNL` always returns 0.

**Done 2026-10-29 (Phase 3):** SRD-BKT-002.030–.039, SRD-GUI-031.030–.034 (minimal, approved by user for code; RN-BKT-1.4.0, RN-GUI-1.41.0). User choices (D10–D12): Rex count resets each day; daily loss stop blocks new entries (live only warns); stop counts when stop and target are in one bar (live checks ticks, target first). Money rules copy live `_size_entry` / `can_allocate` / `margin_available`. Deferred: shadow P&L, equity Parquet, variant pool, trailing levels, PNL conditions, Grow with P&L (refused with a message), trade detail drawer.

**Done 2026-10-29 (closed candles + session dates):** user found the session-date issue while checking Step 3; fixed (SRD-BKT-002.050–.051, SRD-GUI-031.013, SRD-EXE-006.014; RN-BKT-1.5.0, RN-GUI-1.42.0, RN-EXE-1.38.0). PRICE reads closed bars only (replaces SRD-BKT-002.023). Step 1 lists are keyed by session date (built from the previous trading day). Phase 3 user check stays Pending. Open: ST_AUTO `Last` (TODO T63); 2026-10-29 session missing until its 1d bar is in the store.

**Done 2026-10-29 (Phase 4a):** Step 4 Report: SRD-BKT-002.040–.047, SRD-GUI-031.040–.045 (RN-BKT-1.6.0, RN-GUI-1.43.0). Stats per variant from `results.db`, equal-weight benchmark ("S&P 500 (equal weight)", no SPY; TODO T64 Done), Report tab with KPIs, equity vs benchmark, drawdown, heat map, breakdown, compare, CSV. Real run (IT, Price Action, ST_AUTO, $2,000): 118 trades, net P&L -$544.36. Phase 4b (later, TODO T68): MAE / MFE and profit given back, hold time, P&L by score / rank, Monte Carlo, first vs second half, without top 5, shadow P&L, capital × per-trade heat map. Phase 4 user check Pending.

**Next action:** user checks the Report tab in the app (Run, then Report, variant picker, CSV). Then Phase 4b, or Phase 5 if the user prefers. Phase 3 user check is still Pending. Open: ST_AUTO is `current` (T63 Done); SRD-BKT-002.023 status (TODO T66); 2026-10-29 session missing until its 1d bar is in the store (TODO T65). SPY is not downloaded: the user wants backtest data to be S&P 500 only (2026-10-29), so presets with the RS rule are refused with a plain message (SRD-BKT-002.018).

---

## 1. Goal

A flexible, fast backtest engine that:

- Runs a screener over history, then the user's live strategies on the screened stocks,
  then applies the same money rules as live, then reports deep statistics.
- Re-runs only the steps whose inputs changed (cached per step and per stock).
- Uses the **same strategies as live** — one strategy definition, no copy.
- Is headless: GUI, a CLI and (last) MCP all call one `BacktestService`.

---

## 2. Locked Decisions (user, 2026-10-29)

| # | Topic | Decision |
|---|---|---|
| D1 | Accounts | **One shared account** for all strategies in a run. No separate accounts. |
| D2 | Stock choice per day | User picks all screener stocks or **top N by score**. |
| D3 | Signals > money | User picks the rule: **first signal in time** or **highest screener score**. |
| D4 | Screener AI ranking | **Tick box, default OFF** (cost). AI answers cached per preset + date. For short periods. |
| D5 | Holding style | **Intraday and swing** both work from the first build. |
| D6 | Build order | Backend + GUI per step; **MCP last**. |
| D7 | Money | **Same rules as live** (see §6). Defaults from user/strategy settings; any value allowed in backtest. No broker leverage, no PDT. |
| D8 | Strategies | Read from the **live strategy store**. Edits and new strategies appear automatically. |
| D9 | Stocks | S&P 500, sector(s) or names, plus add/remove on top. |
| D10 | Rex count | Resets each trading day in the backtest (live never resets). (user, 2026-10-29) |
| D11 | Daily loss stop | Blocks new entries for the rest of the day (live only warns). (user, 2026-10-29) |
| D12 | Stop and target in one bar | The stop counts. (user, 2026-10-29) |

---

## 3. Pipeline Summary

| Step | Input | Output | Runs |
|---|---|---|---|
| 0 Data check | Run plan, Parquet store | Missing-candle list | Before every run |
| 1 Stocks | Universe, screener preset, 1d candles | Daily list (§5.1) | Per stock, parallel |
| 2 Signals | Strategy entry/exit text, 3m/1d candles | Signal periods (§5.2) | Per stock × strategy, parallel |
| 3 Portfolio | Daily list, signal periods, money rules, stop/target, costs | Trades, day log, money table (§5.3) | Per variant, variants parallel |
| 4 Report | Step 3 output, SPY 1d | Stats (§5.4) | Per variant |

Timing rule (no look-ahead):

- The list made from day D's close is used on day D+1.
- Daily indicator values inside a 3m bar come from the previous close.
- Every fill is at the **next bar's open**.

### 3.1 What re-runs when something changes

| Change | Step 1 | Step 2 | Step 3–4 |
|---|---|---|---|
| Screener settings | All stocks | Reused | Run |
| AI tick turned on | Days not yet cached | Reused | Run |
| Top N or ranking rule | Reused | Reused | Run |
| Strategy entry/exit text | Reused | That strategy | Run |
| New strategy added | Reused | New strategy only | Run |
| Stop, target, time exit | Reused | Reused | Run |
| Capital, allocation %, per-trade %, daily loss stop | Reused | Reused | Run |
| Costs | Reused | Reused | Run |
| Stocks added | New stocks only | New stocks only | Run |
| Stocks removed | Reused | Reused | Run |
| New candles downloaded | Stocks with new bars | Stocks with new bars | Run |

---

## 4. Run Plan (input contract)

Frozen, versioned dataclass `RunPlan` (`backtest/spec.py`), saved as JSON with every run.

```json
{
  "schema": 1,
  "name": "Momentum vs Pullback, Tech",
  "period": { "from": "2026-01-02", "to": "2026-10-28" },
  "universe": { "mode": "sector", "sectors": ["Information Technology"],
                "add": ["PLTR"], "remove": ["INTC"] },
  "screener": { "preset_id": "abc-momentum", "top_n": 5, "ai_ranking": false },
  "strategies": [
    { "id": "st-orb", "allocation_pct": 60, "per_trade_pct": 50 },
    { "id": "st-vwap", "allocation_pct": 40, "per_trade_pct": 100 }
  ],
  "account": { "capital": [2000, 5000], "grow_with_pnl": false,
               "max_daily_loss_pct": 2.0, "when_full": "first_signal" },
  "costs": { "per_order": 1.0, "slippage_bps": 5 }
}
```

- `strategies[].id` points to the live strategy store. Entry/exit text, stop, target,
  hours, days, direction and trade type are read at run time; any field given in the plan
  overrides the store value for this run only.
- The run saves a **snapshot** of each strategy's text; results show "strategy changed
  since this run" when the store differs.
- List values (`capital`, `allocation_pct`, `per_trade_pct`) expand into a variant grid.
  Limit: 64 variants per run.

---

## 5. Data Contracts (outputs)

### 5.1 Step 1 — Daily list

Cache file per stock: `cache/stocks/<key>/<SYM>.parquet`

| Column | Type | Note |
|---|---|---|
| date | date | Session D; list is used on D+1 |
| passed | bool | Only `True` rows are kept |
| score | float | Screener score |

Joined view (built at Step 3 start): `date, symbol, score, rank, ai_rank`.

- `rank` is by score within the date.
- `ai_rank` is set only when D4 is ticked. AI answers are stored at
  `cache/ai/<preset_key>/<date>.json`.

### 5.2 Step 2 — Signal periods

Cache file per stock per strategy: `cache/signals/<key>/<SYM>.parquet`

| Column | Type | Note |
|---|---|---|
| kind | str | `entry` or `exit` |
| start | timestamp | First bar where the condition is true |
| end | timestamp | Last bar where it is still true |
| close_at_start | float | Close of the start bar |
| values | json | Indicator values at start (for drill-down) |

- The strategy's trading hours and days are applied before saving.
- Conditions that use `PNL` are flagged; Step 3 checks them per held bar.

### 5.3 Step 3 — Portfolio (SQLite `results.db` + Parquet)

| Table | Key columns |
|---|---|
| runs | run_id, plan_json, strategy_snapshot_json, status, started, finished |
| variants | variant_id, run_id, capital, allocation/per-trade per strategy |
| trades | variant_id, strategy_id, symbol, direction, entry_ts, entry_px, qty, exit_ts, exit_px, exit_reason, costs, net_pnl, mae, mfe, score, rank |
| day_log | variant_id, ts, symbol, strategy_id, decision, reason, margin_available, strategy_deployed |
| money_daily | variant_id, date, start_capital, deployed, margin_min, margin_close, open_value, equity |
| equity (Parquet) | `runs/<run>/<variant>/equity.parquet` at 3m resolution |

`decision` values: `entered`, `strategy_limit`, `no_margin`, `already_held`,
`too_expensive`, `daily_loss_stop`. Shadow P&L is stored for skipped signals.

### 5.4 Step 4 — Stats

| Group | Measures |
|---|---|
| Returns | Net P&L, CAGR, vs SPY, monthly heat map, % time invested |
| Risk | Max DD ($/%), longest DD days, Sharpe, Sortino, Calmar, worst day/trade |
| Trade quality | Win rate, avg win/loss, payoff, profit factor, expectancy (R), streaks |
| Entry analysis | P&L by entry hour, score bucket, rank, days since first screener pass |
| Exit analysis | Share and P&L by exit reason, MAE/MFE, profit given back |
| Holding | Hold-time spread, P&L by hold time |
| Capital use | Taken vs skipped, shadow P&L, margin use, "stop and target in one bar" count |
| Robustness | Monte Carlo of trade order, first vs second half, without top 5 trades |

All measures can be grouped by strategy, sector, stock, hour, weekday and month.

---

## 6. Money Rules (copied from live)

Source of truth in live code:

- `execution/strategy_engine/_router.py::_size_entry`
- `execution/risk_manager.py::can_allocate`
- `execution/risk_manager.py::margin_available`

| Rule | Formula |
|---|---|
| Per-trade $ | capital × allocation % × per-trade % |
| Shares | floor(per-trade $ ÷ fill price); 0 → `too_expensive` |
| Strategy limit | cost of this strategy's open trades < capital × allocation % |
| Margin available | capital − cost of all open trades − buys placed on this bar |
| Daily loss stop | day loss ≥ max daily loss % → no new entries until next day |
| Risk per trade, max position | Warn only (as live); counted in the report |
| Capital | Fixed (as live). Option `grow_with_pnl` uses equity instead. |

Order on each bar:

1. Exits: stop, then target, then time exit, then exit condition. If stop and target are in one bar, count the stop.
2. Collect candidates: in the D−1 list (top N), not held by any strategy, inside hours.
3. Rank by D3.
4. Size.
5. Check strategy limit and margin.
6. Fill at the next open plus slippage, and charge commission.
7. Log.

Swing positions carry overnight. A gap through the stop fills at the open.

### 6.1 Live defaults → backtest fields

| Live setting | Where | Backtest field |
|---|---|---|
| Max capital | Edit User → Risk | Capital $ |
| Strategy Allocation | Edit Strategy → Strategy Info | Allocation % |
| Per-Trade Size | Edit Strategy → Strategy Info | Per-trade % |
| Max daily loss | Edit User → Risk | Daily loss stop % |

---

## 7. Live Parity (same strategy for live and backtest)

| Item | Live | Backtest |
|---|---|---|
| Parser | `execution/strategy_engine/_evaluator.py` | Re-exported by `core/expr/` (user choice 2026-10-29, live code unchanged); backtest = full series in `core/expr/series.py` |
| Functions | Number, PNL, VWAP, Price, RSI, ADX, EMA, SUPERTREND, SWING, MACD | All 10, as series |
| Timeframes | 3m, 15m, 1d, 1w | All 4 read from the store; 15m and 1w are built on every save (SRD-BKT-001.012–.014, done 2026-10-29). 1w has a `days` column; an unfinished week is never used before that day's close |
| `PNL` | From open position | Checked in Step 3 per held bar |
| Check timing | Every minute / N seconds (can fire inside a forming bar) | At each 3m close; live may enter up to 2 min earlier — noted in report |
| `VWAP` | Cumulative over loaded candles | Must reset per session; confirm live window, then match |
| Price "current" | May be the forming bar | Last closed bar |

**Parity test (Phase 2 gate):** for 50 stocks, for each function and timeframe, live
last-value equals the series value on the same candles.

---

## 8. Package Layout

```
src/us_swing/
├─ core/expr/              shared parser (moved from execution/_evaluator)
│  ├─ parser.py
│  ├─ last_bar.py          live evaluator API (unchanged behaviour)
│  └─ series.py            backtest evaluator
├─ backtest/
│  ├─ store.py planner.py downloader.py settings.py schedule.py   (exist, FO-BKT-001; store has 1d, 3m, 15m, 1w)
│  ├─ spec.py              RunPlan + sub-specs (frozen, versioned)
│  ├─ universe.py          resolve S&P / sector / names
│  ├─ cache.py             keyed step cache, atomic writes, cleanup
│  ├─ steps/stocks.py      Step 1 — screener replay
│  ├─ steps/recorded.py    Step 1 source — saved screener lists (Phase 5)
│  ├─ steps/signals.py     Step 2
│  ├─ steps/portfolio.py   Step 3
│  ├─ steps/report.py      Step 4
│  ├─ orchestrator.py      asyncio jobs + process pool + progress events
│  ├─ results.py           results repository (SQLite + Parquet)
│  ├─ service.py           BacktestService: estimate, start, status, cancel, results
│  └─ cli.py               python -m us_swing.backtest.cli run plan.json
├─ gui/backtest_*.py       workspace, builder, step strip, views
└─ mcp/backtest_tools.py   Phase 6
```

Rules:

- No imports across tools. Screener replay goes through a small adapter in `core/`.
- Steps are pure functions: frames in, frame out.
- No business logic in GUI files.

Cache key = sha256 of `{step, step_version, params, symbol, data_fp}`.
`data_fp` = last bar time + row count of the stock's candles for the period plus warm-up.

Cache location: `~/.usswing/backtest/cache/`. Size limit + 30-day cleanup. Writes are atomic,
because the app and the MCP server share the cache.

---

## 9. Phases

Each phase follows the project chain:

1. FO/SRD rows written as Draft.
2. User approves them.
3. DD, MD, UTCD.
4. Backend code + tests.
5. GUI part.
6. ruff + mypy --strict.
7. User checks in the real app window.
8. Commit, then RN/TRACE/CONTEXT/DEVLOG.

Push and PR only when the user says.

SRD numbering: `SRD-BKT-002.0xx` (engine), `SRD-GUI-031.0xx` (workspace). Each phase uses
its own block of numbers so phases can be approved one at a time.

### Phase 0 — Foundation

| Part | Work |
|---|---|
| Backend | `spec.py` RunPlan (+ JSON load/save, validation, variant expansion, 64 limit); `universe.py` (S&P 500 / sectors / names + add/remove from the universe table); `cache.py` (key, read/write, atomic, cleanup); `results.py` schema; `service.py` skeleton (`estimate` returns data check + step plan); `cli.py` |
| GUI | New **Backtest** workspace in the sidebar (frameless rules, Carbon theme). Left builder: Stocks group (S&P 500 / Sector chips / Names + add/remove), period. Step strip with 4 steps (all "waiting"). Data check line: "72 stocks · 3 missing 3m candles · Download" (reuses FO-BKT-001 downloader) |
| SRD block | BKT-002.001–.009, GUI-031.001–.009 |
| Tests | RunPlan round-trip and validation; universe resolve per mode; cache hit/miss/atomic; estimate on a fake store |
| User check | Pick a sector, see the stock count and missing-candle line |

### Phase 1 — Step 1 · Stocks

| Part | Work |
|---|---|
| Backend | `steps/stocks.py`: for each stock and date, run the preset's rule stages on 1d bars up to D (replay through the core adapter); save the per-stock cache; join + rank; top N is applied later in Step 3. AI tick: send each day's list to the preset's AI stage, cache per preset + date, estimate shows calls and cost. Orchestrator v1: process pool, per-stock progress |
| GUI | Builder: Screener picker, "Stocks per day" (All / Top N), "Use AI ranking" tick (off, with cost). Step 1 view: date list on the left; on select, stocks with score and rank; pass-count chart over time |
| SRD block | BKT-002.010–.019, GUI-031.010–.019 |
| Tests | Replay of one recorded date equals the saved screener result (rule stages only); cache reuse when only top N changes; new stock computes only that stock; AI off → zero AI calls |
| User check | "On 3 Mar, ABC gave these 5 stocks" matches the screener history |
| Check first | Are preset scores **per stock** or normalised across all stocks? If across, per-stock cache needs a join step for scores (see §11 R2) |

### Phase 2 — Step 2 · Signals

| Part | Work |
|---|---|
| Backend | Move parser to `core/expr/` (live behaviour unchanged, EXE docs get a cross-tool note); `series.py` for all 10 functions; read 15m/1w from the store; daily values aligned to the previous close; `steps/signals.py` builds entry/exit periods, applies hours/days, flags PNL conditions |
| GUI | Builder: Strategies list loaded from the live store (auto refresh), allocation % / per-trade % shown. Step 2 view: per strategy and stock, a periods table; click opens the Charts view with period shading |
| SRD block | BKT-002.020–.029, GUI-031.020–.029 |
| Tests | **Parity test** (§7); existing live evaluator tests still pass after the move; VWAP session reset; hours filter; PNL flag |
| User check | "NVDA entry was true 10:09–10:15" on the chart |

### Phase 3 — Step 3 · Portfolio

| Part | Work |
|---|---|
| Backend | `steps/portfolio.py`: merged timeline, §6 rules and order, intraday + swing, gap stop, costs, day log, shadow P&L, money table, variants in parallel |
| GUI | Builder: Capital $, Daily loss stop %, Grow with P&L, When money short, costs. Results: trades table (strategy column), day log tab, money-by-day tab, trade detail drawer |
| SRD block | BKT-002.030–.039, GUI-031.030–.039 |
| Tests | Hand cases: per-trade sizing; strategy limit; margin across 2 strategies; first signal vs highest score; already held; too expensive; daily loss stop; stop+target same bar; gap stop; swing overnight; next-open fill |
| User check | Trades and margin at each decision look right for one known day |

### Phase 4 — Step 4 · Report

| Part | Work |
|---|---|
| Backend | `steps/report.py` all §5.4 groups; SPY benchmark; compare variants |
| GUI | KPI row, equity vs SPY chart, stats tabs, by-stock / by-sector, compare heat map (capital × per-trade %), CSV export |
| SRD block | BKT-002.040–.049, GUI-031.040–.049 |
| Tests | Each measure on a small known trade list; Monte Carlo is repeatable with a seed |
| User check | Full report for a 1-year run on one sector |

### Phase 5 — Quick test in Screener

| Part | Work |
|---|---|
| Backend | `steps/recorded.py`: read `~/.usswing/screener_results/preset_<id>/<date>.json` as the Step 1 source (keeps the real AI picks) |
| GUI | Screener run history → "Quick test" drawer: strategy, recorded days, capital, per-trade; per-day result list; "Open in Backtest workspace" |
| SRD block | BKT-002.050–.059, GUI-031.050–.059 |
| Tests | Recorded list → same Step 2/3 path; missing candles reported |
| User check | Test on the lists really seen in the app |

### Phase 6 — MCP tools (last)

| Part | Work |
|---|---|
| Backend | FO-MCP-007: `bt_catalog`, `bt_validate_rule`, `bt_estimate`, `bt_run`, `bt_quick_from_screener`, `bt_status`, `bt_cancel`, `bt_summary`, `bt_trades`, `bt_day_log`, `bt_breakdown`, `bt_compare`. Jobs with polling. Limits: 64 variants, 2 jobs, 30 min |
| Note | The MCP server (FO-MCP-001..006) has design only, no code — it may need its own phase first |
| Tests | JSON schema tests; one full session over stdio |

---

## 10. Speed Targets (estimates, measure in Phase 1–3)

| Situation | First run | Capital change | Strategy change | Add 10 stocks |
|---|---|---|---|---|
| 500 stocks · 1 yr 3m · 1 strategy · 1 variant | 30–60 s | 2–4 s | 15–30 s | 3–6 s |

The engine only reads the Parquet store. Downloads stay in FO-BKT-001 (about 25 s per
3-month 3m request on TWS).

---

## 11. Risks and Open Points

| # | Risk / point | Plan |
|---|---|---|
| R1 | Survivorship bias (only today's S&P 500) | Warning on every report |
| R9 | RS rule needs SPY, which is not an S&P 500 member | User 2026-10-29: S&P 500 only; RS presets refused (SRD-BKT-002.018) |
| R2 | Screener scores may be normalised across stocks | Check in Phase 1 before building the per-stock cache |
| R3 | Composite presets (groups, weights, logic) | Replay through the preset executor without the AI stage; check in Phase 1 |
| R4 | Live checks inside forming bars; backtest at 3m close | Accept; note in report |
| R5 | VWAP definition over long data | Match the live window in Phase 2 |
| R6 | AI look-ahead (model knows the outcome) | Warning when AI tick is on |
| R7 | Moving the parser touches live trading | Phase 2 gate: all existing EXE tests + parity test pass |
| R8 | Rules file `artifact-conventions.md` Active Tools lacks BKT | User decides (CLAUDE.md/rules are user-maintained) |

---

## 12. Session Protocol

At the start of a session:

1. Read §0 of this file.
2. Read memory `feature_backtest_engine_design.md`.
3. Read the active phase section.

At the end of a session:

1. Update §0 (the cells and the next action).
2. Update the TODO row T61.
3. Update CONTEXT §0 and DEVLOG.
4. Update memory if a decision changed.

Never change §2 (Locked Decisions) without the user saying so. Add new decisions as D10, D11, ….
