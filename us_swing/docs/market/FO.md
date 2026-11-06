# Functional Overview — Market Analytics (MKT)

**Document ID:** FO-MKT
**Version:** 0.3.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.6.0: FO-MKT-005 written as Draft for its ATLAS part (P5a); TIDE, PIVOT, SENTINEL and HELM stay for P5b.
> v0.5.0: FO-MKT-004 written in full as Draft (daily candles from the Backtest Data store; bands, setups and idea status; pass rule at 10 days; Score proof panel; no tuning).
> v0.4.0: FO-MKT-003 written in full as Draft (news points rescaled until P5c; earnings from Yahoo for top names; shorts gated by regime; top 10 per side at 60+).
> v0.3.0: FO-MKT-002 written in full as Draft (sector lines from member candles; industry groups later).
> v0.2.0: FO-MKT-001 written in full and approved (user, 2026-11-06).
> v0.1.0: Tool created by architecture review. All FOs are outlines; each is filled in full at the start of its phase.

MKT finds S&P 500 stocks before they move, long or short, with a top-down funnel: regime → sectors → industry groups → relative strength → money flow → pre-breakout setups → AI review. It produces a Swing Readiness Score (0–100) and a ranked idea list. MKT runs inside the DSK desk process and writes to `desk.db`. Phases P1–P4 use no AI. Design source: https://claude.ai/artifact/4JJKX2kVZ9bvNkurFRuQkx.

---

## FO-MKT-001: Market Regime, Breadth and Fear

**Status:** Approved (user, 2026-11-06: draft approved, VIX from Yahoo Finance, option A)
**Priority:** Must
**Phase:** P1
**Depends on:** FO-DSK-001 (desk process), FO-GUI-034 (Market Floor panels), daily candles in `candles.db`

The system shall describe the state of the whole US market each day, so later phases can judge every stock idea against it. No AI is used.

- The system shall classify each day's market regime from SPY as Uptrend, Downtrend or Choppy.
- The system shall classify market volatility as Calm, Normal or High from SPY's recent price swings compared with the past year.
- The system shall compute daily breadth for S&P 500 stocks: share above their 20, 50 and 200-day averages, 52-week new highs and lows, and advancing against declining stocks.
- The system shall give a daily fear reading (Calm, Nervous, Fearful) from volatility, breadth and VIX, using daily VIX and VIX3M from Yahoo Finance.
- The system shall run this as a desk step in the evening run and keep the results in `desk.db`.
- The system shall fill the whole available history on its first run, then add only new days.
- The system shall show the real regime and breadth on the Market Floor in place of sample data.

### Acceptance Criteria

1. For 3 chosen dates the regime, volatility and breadth match a hand check on the same candles.
2. With the app closed, the evening run adds the latest day and the Floor shows it after the app opens.
3. When Yahoo Finance is not reachable, the day is still stored and the fear reading says it was made without VIX.
4. The Market regime and Breadth panels show the data date and no "Sample data" tag.

## FO-MKT-002: Sector Strength and Rotation

**Status:** Approved (user, 2026-11-06)
**Priority:** Must
**Phase:** P2
**Depends on:** FO-MKT-001 (desk step and member candles), saved S&P 500 list with sectors

The system shall show which of the 11 sectors money is moving into or out of, and which stocks are the strongest, so later phases can favour strong stocks in strong sectors. No AI is used. Industry groups come later.

- The system shall build a daily strength line for each sector from the equal-weight daily moves of its member stocks.
- The system shall rank the sectors by their performance against SPY over 1, 3 and 6 months.
- The system shall place each sector in a rotation quadrant: Leading, Weakening, Lagging or Improving.
- The system shall give every member stock a relative strength rating from 1 to 99 and its rank inside its sector.
- The system shall run this as a desk step after the market regime step and keep the results in `desk.db`.
- The system shall show the real sector strength, sector rotation and the strongest stocks on the Market Floor.

### Acceptance Criteria

1. For 2 chosen dates the sector ranks, quadrants and three stock ratings match a hand check on the same candles.
2. The evening run adds the latest day for sectors and stock ratings.
3. The Sector strength, Sector rotation and RS leaders panels show real data with the data date and no "Sample data" tag.

## FO-MKT-003: Money Flow, Setups, Readiness Score and Ideas

**Status:** Approved (user, 2026-11-06)
**Priority:** Must
**Phase:** P3
**Depends on:** FO-MKT-001 (regime), FO-MKT-002 (sectors and stock RS), daily candles with volume in `candles.db`

The system shall turn the regime, sector and RS results into a short daily list of long and short stock ideas, each with a trigger, a stop and its reasons, before the move starts. No AI is used. News joins the score in P5c.

- The system shall measure money flow for each stock from price and volume: accumulation and distribution days, Chaikin money flow and up against down volume.
- The system shall detect pre-breakout setups for longs (squeeze, flat base, pullback) and shorts (failed breakout, lower highs, breakdown), each with a trigger price and a stop.
- The system shall give each stock a Swing Readiness Score from 0 to 100 for long and for short, from RS, money flow, setup, sector and regime, minus penalties.
- The system shall leave out stocks that trade less than $20M a day.
- The system shall publish up to 10 long and 10 short ideas a day with a score of 60 or more; ideas with earnings within 5 days or against the regime go to a Watch list.
- The system shall run this as a desk step after the sector step and keep scores, ideas and reasons in `desk.db`.
- The system shall show the real idea list on the Market Floor.

### Acceptance Criteria

1. For 2 chosen dates, the score parts, setup, trigger and stop of three stocks match a hand check on the same candles.
2. The evening run adds the latest day of scores and ideas; earnings are checked for the latest day.
3. The Top ideas panels show real long and short ideas with the data date and no "Sample data" tag.

## FO-MKT-004: Proof on Past Data

**Status:** Implemented (approved by user 2026-11-06)
**Priority:** Must
**Phase:** P4
**Depends on:** FO-MKT-001–003 (score rules), FO-BKT-001 (daily candles in the Backtest Data store)

The system shall replay the P1–P3 score on years of past daily candles and show whether high scores were followed by better moves, before any AI is added. No AI is used and no rule is tuned in P4.

- The system shall read daily candles of the S&P 500 members and SPY from the Backtest Data store, read only.
- The system shall recompute regime, sectors, RS ratings, scores, setups and the idea list for every past day, using only data up to that day.
- The system shall measure the 5, 10 and 20-day return of every scored stock-day per side, entering at the next day's open, and its return against SPY.
- The system shall report count, win rate, average return and average return against SPY by score band, by setup and by idea status.
- The system shall give each side a pass or fail: at 10 days, stocks scoring 70+ beat SPY on average and beat stocks scoring under 40.
- The system shall keep each run's results in `desk.db`; `desk proof` runs it and prints the report.
- The system shall show the latest proof on the Market Floor in a Score proof panel.
- The system shall warn when daily history is shorter than 5 years and say how to download more.

### Acceptance Criteria

1. For 3 chosen stock-days, the forward returns and returns against SPY match a hand check on the same candles.
2. On 3 recent days, at least 90% of the replayed scores are within 1 point of the desk's stored scores; differences come only from the candle source.
3. `desk proof` prints the band, setup and status tables with the pass result per side; the Score proof panel shows the same with the data range.
4. With less than 5 years of daily data, the report and the panel show the download reminder.

**Data note (user to do).** The Backtest Data store now starts on 2024-01-02. After the 1-year warm-up for RS ratings that leaves under 2 years of scored days. To test on 5–6 years, set Start date in Settings → Backtest Data to 2020-01-01 and download. That setting also downloads 3-minute bars for those years, which is very large (TODO T118).

**Limits.** Today's S&P 500 list only (survivorship bias). No past earnings dates, so the earnings Watch rule is not applied. Daily samples overlap, so they are not independent. No costs, slippage or stop exits.

## FO-MKT-005: AI Experts, Risk Manager and Trade Manager

**Status:** ATLAS part Implemented (approved by user 2026-11-06); P5b open
**Priority:** Must
**Phase:** P5a (ATLAS); P5b (TIDE, PIVOT, SENTINEL, HELM)
**Depends on:** FO-DSK-002–005, FO-MKT-001–004

The system shall add AI experts on top of the funnel. P5a adds the first one, ATLAS, the market regime expert.

- The system shall wake ATLAS after each desk run to read the regime, breadth, fear, sectors, idea counts and the latest proof.
- The system shall have ATLAS give a typed view: regime, confidence and up to 3 reasons, plus a short brief.
- The system shall keep each view with the rule regime and whether ATLAS agrees.
- The system shall show the ATLAS brief in the AI feed, and say so when ATLAS disagrees with the rule regime.
- Later (P5b): TIDE (sector and flow) and PIVOT (setup) experts, SENTINEL vetoes ideas that break hard risk limits kept in code, and HELM picks the final ideas and writes the evening brief.

### Acceptance Criteria

1. One full ATLAS run on real data with a real model is recorded in `activity` within budget.
2. The AI feed on the Market Floor shows the ATLAS brief with its time and data day.
3. `atlas_view` holds the typed view; a disagreement with the rule regime shows in the brief.

## FO-MKT-006: News and Global Events (SCOUT)

**Status:** Draft (outline)
**Priority:** Should
**Phase:** P5c

- The system shall collect news and calendar events and tag their impact on sectors and stocks.

## FO-MKT-007: AI Canvas Pages (CANVAS)

**Status:** Draft (outline)
**Priority:** Could
**Phase:** P5d

- The system shall let CANVAS write HTML/CSS pages shown in a sealed web view with no network access.

## FO-MKT-008: Link to Execution

**Status:** Draft (outline)
**Priority:** Should
**Phase:** P7
**Depends on:** DD-DSK §0.7 Q5 — the Master User approves every trade

- The system shall send only Master-approved ideas to the Execution tool as watchlist entries or trade signals.
- The system shall never let HELM place a trade without Master approval.
